import logging
from typing import Dict, Any, List, Optional, Tuple, Set

from apps.sysai.agent.toolsets import (
    CORE_TOOLS, TOOLSETS, TOOLSET_PROFILES,
    get_core_tools, get_toolset_tools, get_profile_tools,
    match_toolsets_by_keywords, resolve_tools_by_toolsets,
    ai_match_toolsets, get_minimal_tools, TASK_TOOLS, DOC_TOOLS,
)

logger = logging.getLogger(__name__)

_CRONTAB_KEYWORDS = {'定时任务', '计划任务', 'cron', 'crontab', '定时执行', '定期备份', '周期性', '定时脚本', '调度', '定时备份', '自动执行', '定时运行', '设定', '每天', '每周', '每月', '凌晨', '定时发送', '定时分析', '定时检查', '定时监控'}

_TODO_KEYWORDS = {'待办', '任务列表', '任务进度', 'todo', '任务跟踪', '多步骤任务'}

_VULN_KEYWORDS = {'漏洞', 'cve', '安全漏洞', '内核漏洞', '漏洞扫描', '漏洞检测', '最新漏洞', '漏洞分析', '提权漏洞', 'dirty frag', 'copy fail', 'fragnesia'}


def _is_vuln_intent(user_input: str) -> bool:
    input_lower = user_input.lower()
    return any(kw in input_lower for kw in _VULN_KEYWORDS)


def _is_crontab_intent(user_input: str) -> bool:
    input_lower = user_input.lower()
    crontab_hits = sum(1 for kw in _CRONTAB_KEYWORDS if kw in input_lower)
    todo_hits = sum(1 for kw in _TODO_KEYWORDS if kw in input_lower)

    if crontab_hits > 0 and todo_hits == 0:
        return True

    if crontab_hits > 0 and todo_hits > 0:
        action_keywords = ['创建', '添加', '新建', '设置', '配置', '删除', '执行', '查看', '列表', '管理', '启用', '停用']
        has_action = any(kw in input_lower for kw in action_keywords)
        if has_action:
            return True

    return False


def resolve_tools(
    user_input: str,
    agent_id: str = None,
    smart_mode: bool = False,
    enabled_tools: List[str] = None,
    profile: str = None,
    ai_model=None,
) -> Tuple[List[str], Optional[str]]:
    if smart_mode:
        return None, None

    if enabled_tools:
        return enabled_tools, None

    if profile and profile in TOOLSET_PROFILES:
        tool_names = get_profile_tools(profile)
        return tool_names, None

    if agent_id:
        agent_tools, agent_prompt = _resolve_skill_agent(agent_id)
        if agent_tools is not None:
            return agent_tools, agent_prompt

    if _is_vuln_intent(user_input):
        vuln_toolsets = ['vulnerability']
        tool_names = resolve_tools_by_toolsets(vuln_toolsets)
        tool_names.extend(t for t in DOC_TOOLS if t not in tool_names)
        logger.info(f'意图路由: 检测到漏洞检测意图, 加载vulnerability工具集({len(tool_names)}个工具)')
        return tool_names, None

    ai_result = ai_match_toolsets(user_input, ai_model=ai_model)
    if ai_result is not None:
        ts_names = ai_result['toolsets']
        need_task = ai_result.get('need_task', False)
        need_doc = ai_result.get('need_doc', False)
        if ts_names:
            tool_names = resolve_tools_by_toolsets(ts_names)
            if need_task:
                tool_names.extend(t for t in TASK_TOOLS if t not in tool_names)
            if need_doc:
                tool_names.extend(t for t in DOC_TOOLS if t not in tool_names)
            if _is_crontab_intent(user_input):
                todo_tools = {'TodoRead', 'TodoWrite'}
                tool_names = [t for t in tool_names if t not in todo_tools]
                crontab_tools = get_toolset_tools('crontab')
                for ct in crontab_tools:
                    if ct not in tool_names:
                        tool_names.append(ct)
                logger.info(f'意图路由: 检测到crontab意图, 移除Todo工具, 保留crontab工具')
            logger.info(f'意图路由(AI): Toolset={ts_names}, task={need_task}, doc={need_doc}, 加载{len(tool_names)}个工具')
            return tool_names, None
        else:
            tool_names = get_minimal_tools()
            logger.info(f'意图路由(AI): 闲聊, 仅加载{len(tool_names)}个基础工具')
            return tool_names, None

    ts_names = match_toolsets_by_keywords(user_input)
    if ts_names:
        tool_names = resolve_tools_by_toolsets(ts_names)

        if _is_crontab_intent(user_input):
            todo_tools = {'TodoRead', 'TodoWrite'}
            tool_names = [t for t in tool_names if t not in todo_tools]
            crontab_tools = get_toolset_tools('crontab')
            for ct in crontab_tools:
                if ct not in tool_names:
                    tool_names.append(ct)
            logger.info(f'意图路由: 检测到crontab意图, 移除Todo工具, 保留crontab工具')

        logger.info(f'意图路由(关键词): 匹配Toolset {ts_names}, 加载{len(tool_names)}个工具')
        return tool_names, None

    tool_names = get_minimal_tools()
    logger.info(f'意图路由: 无匹配Toolset, 仅加载{len(tool_names)}个基础工具')
    return tool_names, None


def _resolve_skill_agent(agent_id: str) -> Tuple[Optional[List[str]], Optional[str]]:
    try:
        from apps.sysai.agent.skill_agent_manager import skill_agent_manager
        agent_config = skill_agent_manager.get(agent_id)
        if agent_config:
            tools = set(CORE_TOOLS)
            for ts_name in agent_config.toolsets:
                tools.update(get_toolset_tools(ts_name))
            tools.update(agent_config.tools)
            logger.info(f'SkillAgent路由: 加载Agent [{agent_id}], {len(tools)}个工具')
            return list(tools), agent_config.system_prompt
    except Exception as e:
        logger.debug(f'SkillAgent路由降级: {e}')

    try:
        from apps.sysai.agent.specialized import get_agent_class
        agent_cls = get_agent_class(agent_id)
        if agent_cls:
            agent_instance = agent_cls()
            agent_tools = set(CORE_TOOLS)
            for step in agent_instance.get_auto_collect_steps():
                tool_name = step.get('tool', '')
                if tool_name:
                    agent_tools.add(tool_name)
            agent_tools.add('execute_command')
            agent_tools.add('request_user_input')
            logger.info(f'SpecializedAgent路由: 加载Agent [{agent_id}], {len(agent_tools)}个工具')
            return list(agent_tools), agent_instance.system_prompt or None
    except Exception as e:
        logger.debug(f'SpecializedAgent路由降级: {e}')

    return None, None


def get_toolset_info_for_api() -> Dict[str, Any]:
    return {
        'toolsets': [
            {
                'id': ts_name,
                'name': ts_config['name'],
                'description': ts_config['description'],
                'trigger_keywords': ts_config['trigger_keywords'],
                'tools': ts_config['tools'],
            }
            for ts_name, ts_config in TOOLSETS.items()
        ],
        'profiles': [
            {
                'id': p_name,
                'name': p_config['name'],
                'description': p_config['description'],
                'toolsets': p_config['toolsets'],
            }
            for p_name, p_config in TOOLSET_PROFILES.items()
        ],
        'core_tools': CORE_TOOLS,
    }
