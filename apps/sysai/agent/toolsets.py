import json
import logging
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)

CORE_TOOLS = [
    'execute_command',
    'request_user_input',
    'Skills',
    'TodoRead',
    'TodoWrite',
    'agent_call',
    'read_file',
    'list_directory',
    'search_in_file',
    'search_docs',
    'list_docs',
]

MINIMAL_TOOLS = [
    'request_user_input',
]

TOOLSET_CORE_TOOLS = {
    'system': ['execute_command', 'read_file', 'search_in_file'],
    'service': ['execute_command', 'read_file'],
    'docker': ['execute_command'],
    'database': ['execute_command'],
    'website': ['execute_command', 'read_file', 'search_in_file'],
    'security': ['execute_command', 'read_file'],
    'file': ['execute_command', 'read_file', 'list_directory', 'search_in_file'],
    'panel_shop': ['execute_command'],
    'panel_docker': ['execute_command'],
    'panel_website': ['execute_command', 'read_file', 'search_in_file'],
    'panel_database': ['execute_command'],
    'crontab': ['execute_command'],
    'alert': ['execute_command'],
    'waf': ['execute_command', 'read_file'],
    'vulnerability': ['execute_command', 'read_file'],
}

TASK_TOOLS = ['TodoRead', 'TodoWrite']
AGENT_TOOLS = ['Skills', 'agent_call']
DOC_TOOLS = ['search_docs', 'list_docs']

TOOLSETS: Dict[str, Dict[str, Any]] = {
    'system': {
        'name': '系统监控',
        'description': '系统资源监控和信息获取',
        'trigger_keywords': ['cpu', '内存', '磁盘', '负载', '系统信息', '进程', '性能', '运行时间', 'uptime', '内存使用', '磁盘空间'],
        'tools': ['get_system_info', 'get_cpu_info', 'get_memory_info',
                  'get_disk_info', 'get_network_info', 'get_process_list',
                  'get_system_logs'],
    },
    'service': {
        'name': '服务管理',
        'description': '系统服务状态查询和管理',
        'trigger_keywords': ['服务', 'nginx', 'mysql', 'redis', 'php', '启动', '停止', '重启', 'systemctl', '服务状态'],
        'tools': ['get_service_status', 'list_services', 'manage_service', 'get_service_logs'],
    },
    'docker': {
        'name': 'Docker管理',
        'description': 'Docker容器和镜像管理',
        'trigger_keywords': ['容器', 'docker', '镜像', 'compose', 'dockerfile', '容器日志'],
        'tools': ['docker_list_containers', 'docker_container_info',
                  'docker_container_logs', 'docker_manage_container',
                  'docker_list_images', 'docker_stats'],
    },
    'database': {
        'name': '数据库管理',
        'description': 'MySQL和Redis数据库操作',
        'trigger_keywords': ['数据库', 'mysql', 'redis', 'sql', '查询', '慢查询', '数据库状态'],
        'tools': ['mysql_status', 'mysql_execute', 'mysql_list_databases',
                  'redis_status', 'redis_execute'],
    },
    'website': {
        'name': '网站管理',
        'description': '网站配置和状态管理',
        'trigger_keywords': ['网站', '域名', 'nginx配置', 'ssl', '证书', '站点', 'https', '虚拟主机'],
        'tools': ['list_websites', 'get_website_config', 'check_website_status',
                  'get_nginx_status', 'reload_nginx', 'restart_nginx'],
    },
    'vulnerability': {
        'name': '漏洞检测',
        'description': 'Linux内核和软件包漏洞扫描与评估，内置CVE知识库，确定性风险评估',
        'trigger_keywords': ['漏洞', 'cve', '安全漏洞', '内核漏洞', '漏洞扫描', '漏洞检测', '最新漏洞', '漏洞分析', '提权漏洞', 'dirty', 'copy fail', 'fragnesia'],
        'tools': ['vuln_scan_kernel', 'vuln_get_cve_info', 'vuln_scan_packages',
                  'get_security_updates', 'get_open_ports', 'get_ssh_config',
                  'get_firewall_status', 'get_login_history'],
    },
    'security': {
        'name': '安全管理',
        'description': '防火墙、SSH、端口、安全风险扫描等安全相关',
        'trigger_keywords': ['防火墙', 'ssh', '安全配置', '端口', '登录', '攻击', '入侵', 'iptables', 'ufw', '安全加固', '安全检查', '安全事件', '安全分析', '安全审计', '安全报告', '登录失败', '可疑登录', '安全扫描', '安全评分', '安全风险', '漏洞扫描'],
        'tools': ['get_firewall_status', 'get_ssh_config', 'get_login_history',
                  'get_open_ports', 'get_security_updates', 'manage_firewall_rule',
                  'security_scan', 'security_scan_result'],
    },
    'file': {
        'name': '文件操作',
        'description': '文件写入和搜索',
        'trigger_keywords': ['写文件', '修改文件', '保存文件', '搜索文件', '配置文件修改'],
        'tools': ['write_file', 'search_files'],
    },
    'panel_shop': {
        'name': '应用商店',
        'description': '如意面板应用商店管理',
        'trigger_keywords': ['应用', '安装软件', '已安装', '软件商店', '软件列表', '卸载软件', '更新软件'],
        'tools': ['panel_shop_list', 'panel_shop_install',
                  'panel_shop_manage', 'panel_shop_task_status'],
    },
    'panel_docker': {
        'name': 'Docker广场',
        'description': '如意面板Docker广场应用管理',
        'trigger_keywords': ['docker广场', 'docker应用', '一键安装', 'docker模板', 'docker部署'],
        'tools': ['panel_docker_square_list', 'panel_docker_square_catalog',
                  'panel_docker_square_install', 'panel_docker_square_manage'],
    },
    'panel_website': {
        'name': '面板网站管理',
        'description': '如意面板网站站点管理',
        'trigger_keywords': ['面板网站', '创建网站', '站点管理', '添加网站', '绑定域名', '网站列表'],
        'tools': ['panel_site_list', 'panel_site_create',
                  'panel_site_manage', 'panel_site_domains'],
    },
    'panel_database': {
        'name': '面板数据库管理',
        'description': '如意面板数据库管理',
        'trigger_keywords': ['面板数据库', '创建数据库', '重置密码', '数据库密码', 'root密码', '删除数据库'],
        'tools': ['panel_database_list', 'panel_database_create',
                  'panel_database_delete', 'panel_database_reset_pass',
                  'panel_database_root_pass'],
    },
    'crontab': {
        'name': '定时任务管理',
        'description': '服务器定时任务/计划任务管理，支持Shell脚本任务和AI智能定时任务',
        'trigger_keywords': ['定时任务', '计划任务', 'cron', 'crontab', '定时执行', '定期备份', '周期性', '定时脚本', '调度', '定时备份', '自动执行', '定时运行', '设定', '每天', '每周', '每月', '凌晨', '定时发送', '定时分析', '定时检查', '定时监控'],
        'tools': ['crontab_list', 'crontab_create', 'crontab_create_ai',
                  'crontab_delete', 'crontab_toggle', 'crontab_run',
                  'crontab_logs', 'crontab_ai_result'],
    },
    'alert': {
        'name': '告警监控',
        'description': '系统资源告警、网站监控告警、SSL证书告警、定时任务失败告警等，支持多渠道通知（邮件/钉钉/飞书/企微/Webhook）',
        'trigger_keywords': ['告警', '监控告警', '报警', '阈值告警', '通知渠道', 'cpu告警', '内存告警', '磁盘告警', 'ssl告警', '证书过期', '网站宕机', '网站监控', '发邮件', '发通知', '邮件通知', '钉钉通知', '飞书通知', '企微通知', 'webhook'],
        'tools': ['alert_list', 'alert_create', 'alert_toggle',
                  'alert_delete', 'alert_test', 'notify_channel_list',
                  'notify_channel_test'],
    },
    'waf': {
        'name': 'WAF防护',
        'description': 'Web应用防火墙管理，包括防护状态、攻击日志、IP黑白名单、防护规则、URL黑白名单、站点WAF配置',
        'trigger_keywords': ['waf', 'web防火墙', '攻击拦截', '攻击日志', 'cc防护', 'sql注入防护', 'xss防护', 'ip封禁', 'ip黑名单', 'ip白名单', 'url黑名单', 'url白名单', '攻击分析', '防护规则', '观察模式', '防护模式', '网站防护', 'web应用防火墙', '安全事件', '安全分析', '安全审计', '安全报告', 'web攻击'],
        'tools': ['waf_get_status', 'waf_set_status', 'waf_get_dashboard',
                  'waf_get_attack_logs', 'waf_manage_ip', 'waf_manage_rule',
                  'waf_manage_url_rule', 'waf_get_site_config', 'waf_set_site_status',
                  'waf_ip_attack_analysis'],
    },
}

TOOLSET_PROFILES = {
    'minimal': {
        'name': '最小模式',
        'description': '仅核心工具',
        'toolsets': [],
    },
    'coding': {
        'name': '开发模式',
        'description': '核心+文件+系统+服务',
        'toolsets': ['system', 'service', 'file'],
    },
    'ops': {
        'name': '运维模式',
        'description': '核心+系统+服务+Docker+网站+安全+漏洞+WAF+定时任务+告警',
        'toolsets': ['system', 'service', 'docker', 'website', 'security', 'vulnerability', 'waf', 'crontab', 'alert'],
    },
    'panel': {
        'name': '面板模式',
        'description': '核心+所有面板工具+定时任务',
        'toolsets': ['panel_shop', 'panel_docker', 'panel_website', 'panel_database', 'crontab'],
    },
    'full': {
        'name': '全量模式',
        'description': '所有工具',
        'toolsets': list(TOOLSETS.keys()),
    },
}


def get_core_tools() -> List[str]:
    return list(CORE_TOOLS)


def get_toolset_tools(toolset_name: str) -> List[str]:
    ts = TOOLSETS.get(toolset_name)
    if not ts:
        return []
    return list(ts.get('tools', []))


def get_profile_tools(profile_name: str) -> List[str]:
    profile = TOOLSET_PROFILES.get(profile_name)
    if not profile:
        return list(CORE_TOOLS)
    tools = set(CORE_TOOLS)
    for ts_name in profile.get('toolsets', []):
        tools.update(get_toolset_tools(ts_name))
    return list(tools)


def match_toolsets_by_keywords(user_input: str) -> List[str]:
    matched = []
    input_lower = user_input.lower()
    for ts_name, ts_config in TOOLSETS.items():
        for keyword in ts_config['trigger_keywords']:
            if keyword in input_lower:
                if ts_name not in matched:
                    matched.append(ts_name)
                break
    return matched


def resolve_tools_by_toolsets(toolset_names: List[str]) -> List[str]:
    tools = set()
    for ts_name in toolset_names:
        tools.update(get_toolset_tools(ts_name))
        core_for_ts = TOOLSET_CORE_TOOLS.get(ts_name, MINIMAL_TOOLS)
        tools.update(core_for_ts)
    tools.update(MINIMAL_TOOLS)
    return list(tools)


def get_minimal_tools() -> List[str]:
    return list(MINIMAL_TOOLS)


def get_all_toolset_info() -> List[Dict[str, Any]]:
    infos = []
    for ts_name, ts_config in TOOLSETS.items():
        infos.append({
            'id': ts_name,
            'name': ts_config['name'],
            'description': ts_config['description'],
            'trigger_keywords': ts_config['trigger_keywords'],
            'tools': ts_config['tools'],
        })
    return infos


def get_all_profile_info() -> List[Dict[str, Any]]:
    infos = []
    for profile_name, profile_config in TOOLSET_PROFILES.items():
        infos.append({
            'id': profile_name,
            'name': profile_config['name'],
            'description': profile_config['description'],
            'toolsets': profile_config['toolsets'],
        })
    return infos


def _build_toolset_catalog() -> str:
    lines = []
    for ts_name, ts_config in TOOLSETS.items():
        lines.append(f"- {ts_name}: {ts_config['description']}")
    return '\n'.join(lines)


_TOOLSET_CATALOG_CACHE = None


def get_toolset_catalog() -> str:
    global _TOOLSET_CATALOG_CACHE
    if _TOOLSET_CATALOG_CACHE is None:
        _TOOLSET_CATALOG_CACHE = _build_toolset_catalog()
    return _TOOLSET_CATALOG_CACHE


_AI_ROUTING_SYSTEM_PROMPT = """你是一个工具路由器。根据用户输入，判断需要哪些工具集。

可用工具集:
{catalog}

特殊标记:
- task: 多步骤复杂任务(部署环境、配置多个服务等),需要任务跟踪
- doc: 询问面板功能使用方法、操作步骤、配置方式

规则:
1. 返回需要的工具集ID和特殊标记，用逗号分隔
2. 闲聊/问候/通用问题返回 none
3. 只返回ID列表，不要解释

示例:
- "查看cpu使用率" → system
- "重启nginx服务" → service
- "docker容器日志和系统负载" → docker,system
- "你好" → none
- "创建一个网站并配置SSL" → panel_website,website,task
- "怎么创建数据库" → panel_database,doc
- "帮我部署LNMP环境" → system,service,website,task
- "检查服务器有没有漏洞" → vulnerability
- "扫描内核漏洞CVE" → vulnerability
- "帮我做安全检查加固" → security,vulnerability,waf
- "帮我检查服务器安全事件" → security,waf
- "设定每天凌晨2点做安全事件分析并发邮件" → crontab,alert,security,waf,task
- "设置CPU超过90%告警" → alert
- "创建定时任务每天备份数据库" → crontab,task
- "配置邮件通知渠道" → alert,doc
- "查看告警规则列表" → alert
- "设定一个AI定时检查磁盘空间" → crontab
"""

_VALID_TOOLSET_IDS = set(TOOLSETS.keys())


_AI_ROUTING_TIMEOUT = 10


def _do_ai_routing(ai_model, messages):
    return ai_model.chat(
        messages=messages,
        stream=False,
        max_tokens=50,
        temperature=0,
    )


_AI_ROUTING_SPECIAL_FLAGS = {'task', 'doc'}


def ai_match_toolsets(user_input: str, ai_model=None) -> Optional[Dict[str, Any]]:
    if not ai_model:
        return None

    try:
        import time
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        from apps.sysai.provider.base import ChatMessage

        catalog = get_toolset_catalog()
        system_prompt = _AI_ROUTING_SYSTEM_PROMPT.format(catalog=catalog)

        messages = [
            ChatMessage(role='system', content=system_prompt),
            ChatMessage(role='user', content=user_input[:200]),
        ]

        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_ai_routing, ai_model, messages)
            try:
                response = future.result(timeout=_AI_ROUTING_TIMEOUT)
            except FuturesTimeout:
                elapsed = time.monotonic() - t0
                logger.warning(f'[AI路由] 超时(>{_AI_ROUTING_TIMEOUT}s), 降级为关键词匹配')
                return None
        elapsed = time.monotonic() - t0

        if not response or not response.choices:
            logger.info(f'[AI路由] 响应为空, 耗时{elapsed:.1f}s, 降级为关键词匹配')
            return None

        content = response.choices[0].message.content.strip().lower()
        logger.info(f'[AI路由] 用户输入="{user_input[:50]}", AI返回="{content}", 耗时{elapsed:.1f}s')

        if content == 'none' or not content:
            return {'toolsets': [], 'need_task': False, 'need_doc': False}

        matched_toolsets = []
        need_task = False
        need_doc = False

        for part in content.replace('，', ',').replace('、', ',').split(','):
            token = part.strip()
            if token in _VALID_TOOLSET_IDS and token not in matched_toolsets:
                matched_toolsets.append(token)
            elif token == 'task':
                need_task = True
            elif token == 'doc':
                need_doc = True

        if not matched_toolsets and not need_task and not need_doc:
            logger.info(f'[AI路由] AI返回内容无法解析, 降级为关键词匹配')
            return None

        return {'toolsets': matched_toolsets, 'need_task': need_task, 'need_doc': need_doc}

    except Exception as e:
        logger.warning(f'[AI路由] 调用失败, 降级为关键词匹配: {e}')
        return None
