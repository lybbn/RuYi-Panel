import json
import logging
from typing import Dict, Any, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    AGENT_CONTROL = 'agent_control'
    INFORMATION_GATHER = 'information_gather'
    PANEL_OPERATION = 'panel_operation'
    SYSTEM_OPERATION = 'system_operation'
    MCP_EXTERNAL = 'mcp_external'
    SKILL = 'skill'


TOOL_CATEGORIES: Dict[str, ToolCategory] = {
    'TodoRead': ToolCategory.AGENT_CONTROL,
    'TodoWrite': ToolCategory.AGENT_CONTROL,
    'request_user_input': ToolCategory.AGENT_CONTROL,
    'agent_call': ToolCategory.AGENT_CONTROL,
    'Skills': ToolCategory.SKILL,
    'search_docs': ToolCategory.INFORMATION_GATHER,
    'list_docs': ToolCategory.INFORMATION_GATHER,
    'read_file': ToolCategory.INFORMATION_GATHER,
    'list_directory': ToolCategory.INFORMATION_GATHER,
    'search_in_file': ToolCategory.INFORMATION_GATHER,
    'web_search': ToolCategory.INFORMATION_GATHER,
    'get_system_info': ToolCategory.INFORMATION_GATHER,
    'get_cpu_info': ToolCategory.INFORMATION_GATHER,
    'get_memory_info': ToolCategory.INFORMATION_GATHER,
    'get_disk_info': ToolCategory.INFORMATION_GATHER,
    'get_network_info': ToolCategory.INFORMATION_GATHER,
    'get_process_list': ToolCategory.INFORMATION_GATHER,
    'get_system_logs': ToolCategory.INFORMATION_GATHER,
    'get_service_status': ToolCategory.INFORMATION_GATHER,
    'list_services': ToolCategory.INFORMATION_GATHER,
    'get_service_logs': ToolCategory.INFORMATION_GATHER,
    'docker_list_containers': ToolCategory.INFORMATION_GATHER,
    'docker_container_info': ToolCategory.INFORMATION_GATHER,
    'docker_container_logs': ToolCategory.INFORMATION_GATHER,
    'docker_list_images': ToolCategory.INFORMATION_GATHER,
    'docker_stats': ToolCategory.INFORMATION_GATHER,
    'mysql_status': ToolCategory.INFORMATION_GATHER,
    'redis_status': ToolCategory.INFORMATION_GATHER,
    'list_websites': ToolCategory.INFORMATION_GATHER,
    'get_website_config': ToolCategory.INFORMATION_GATHER,
    'check_website_status': ToolCategory.INFORMATION_GATHER,
    'get_nginx_status': ToolCategory.INFORMATION_GATHER,
    'get_firewall_status': ToolCategory.INFORMATION_GATHER,
    'get_ssh_config': ToolCategory.INFORMATION_GATHER,
    'get_login_history': ToolCategory.INFORMATION_GATHER,
    'get_open_ports': ToolCategory.INFORMATION_GATHER,
    'get_security_updates': ToolCategory.INFORMATION_GATHER,
    'panel_shop_list': ToolCategory.INFORMATION_GATHER,
    'panel_shop_task_status': ToolCategory.INFORMATION_GATHER,
    'panel_docker_square_list': ToolCategory.INFORMATION_GATHER,
    'panel_docker_square_catalog': ToolCategory.INFORMATION_GATHER,
    'panel_site_list': ToolCategory.INFORMATION_GATHER,
    'panel_database_list': ToolCategory.INFORMATION_GATHER,
    'panel_database_root_pass': ToolCategory.INFORMATION_GATHER,
    'crontab_list': ToolCategory.INFORMATION_GATHER,
    'crontab_logs': ToolCategory.INFORMATION_GATHER,
    'execute_command': ToolCategory.SYSTEM_OPERATION,
    'manage_service': ToolCategory.SYSTEM_OPERATION,
    'docker_manage_container': ToolCategory.SYSTEM_OPERATION,
    'mysql_execute': ToolCategory.SYSTEM_OPERATION,
    'mysql_list_databases': ToolCategory.INFORMATION_GATHER,
    'redis_execute': ToolCategory.SYSTEM_OPERATION,
    'reload_nginx': ToolCategory.SYSTEM_OPERATION,
    'restart_nginx': ToolCategory.SYSTEM_OPERATION,
    'manage_firewall_rule': ToolCategory.SYSTEM_OPERATION,
    'write_file': ToolCategory.SYSTEM_OPERATION,
    'search_files': ToolCategory.INFORMATION_GATHER,
    'panel_shop_install': ToolCategory.PANEL_OPERATION,
    'panel_shop_manage': ToolCategory.PANEL_OPERATION,
    'panel_docker_square_install': ToolCategory.PANEL_OPERATION,
    'panel_docker_square_manage': ToolCategory.PANEL_OPERATION,
    'panel_site_create': ToolCategory.PANEL_OPERATION,
    'panel_site_manage': ToolCategory.PANEL_OPERATION,
    'panel_site_domains': ToolCategory.PANEL_OPERATION,
    'panel_database_create': ToolCategory.PANEL_OPERATION,
    'panel_database_delete': ToolCategory.PANEL_OPERATION,
    'panel_database_reset_pass': ToolCategory.PANEL_OPERATION,
    'crontab_create': ToolCategory.PANEL_OPERATION,
    'crontab_delete': ToolCategory.PANEL_OPERATION,
    'crontab_toggle': ToolCategory.PANEL_OPERATION,
    'crontab_run': ToolCategory.PANEL_OPERATION,
    'vuln_scan_kernel': ToolCategory.INFORMATION_GATHER,
    'vuln_get_cve_info': ToolCategory.INFORMATION_GATHER,
    'vuln_scan_packages': ToolCategory.INFORMATION_GATHER,
}

EXECUTION_PHASES = [
    'collect_info',
    'plan',
    'execute',
    'verify',
]


class ToolCallGuidance:
    """
    Inspired by hermes-agent's TOOL_USE_ENFORCEMENT_GUIDANCE and
    act_dont_ask principle. Generates contextual guidance for each
    agent loop iteration based on current state.
    """

    @staticmethod
    def get_phase_guidance(
        iteration: int,
        has_todos: bool,
        pending_todos: int,
        in_progress_todos: int,
        tools_called: List[str],
        user_intent: str,
    ) -> str:
        parts = []

        if iteration == 1:
            parts.append(ToolCallGuidance._first_turn_guidance(user_intent))
        elif has_todos and in_progress_todos > 0:
            parts.append(ToolCallGuidance._todo_progress_guidance(pending_todos, in_progress_todos))
        elif has_todos and pending_todos > 0 and in_progress_todos == 0:
            parts.append(ToolCallGuidance._todo_start_next_guidance(pending_todos))

        if iteration > 1:
            info_tools_called = sum(
                1 for t in tools_called
                if TOOL_CATEGORIES.get(t) == ToolCategory.INFORMATION_GATHER
            )
            action_tools_called = sum(
                1 for t in tools_called
                if TOOL_CATEGORIES.get(t) in (ToolCategory.PANEL_OPERATION, ToolCategory.SYSTEM_OPERATION)
            )
            if info_tools_called > 5 and action_tools_called == 0 and not has_todos:
                parts.append(
                    '\n<system-reminder>你已收集了大量信息但尚未采取行动。'
                    '请基于已收集的信息开始执行操作或给出结论，不要继续收集信息。</system-reminder>'
                )

        return '\n'.join(parts) if parts else ''

    @staticmethod
    def _first_turn_guidance(user_intent: str) -> str:
        intent_lower = (user_intent or '').lower()

        is_question = any(
            kw in intent_lower
            for kw in ['怎么', '如何', '什么是', '为什么', '能不能', '是否', '怎样', '方法', '教程', '文档']
        )
        is_action = any(
            kw in intent_lower
            for kw in ['帮我', '安装', '部署', '创建', '删除', '修改', '配置', '启动', '停止', '重启', '执行', '修复', '优化']
        )

        if is_question and not is_action:
            return (
                '\n<system-reminder>用户在询问方法/知识类问题。'
                '优先调用 search_docs 搜索面板文档来回答，'
                '不要调用 TodoWrite 创建任务列表，'
                '不要调用 execute_command 执行操作。'
                '直接用文字回答即可。</system-reminder>'
            )

        if is_action:
            return (
                '\n<system-reminder>用户要求执行操作。'
                '如果操作需要多个步骤，先调用 TodoWrite 创建任务列表并立即开始执行第一个任务。'
                '如果缺少关键信息（路径、端口、版本等），先调用 request_user_input 收集信息。'
                '不要只列计划不执行。</system-reminder>'
            )

        return ''

    @staticmethod
    def _todo_progress_guidance(pending: int, in_progress: int) -> str:
        return (
            f'\n<system-reminder>任务进度: {in_progress}个进行中, {pending}个待处理。'
            f'请继续执行当前进行中的任务，完成后立即调用 TodoWrite 更新状态为completed，'
            f'然后将下一个pending任务更新为in_progress并开始执行。'
            f'不要跳过任务，不要同时标记多个任务为in_progress。</system-reminder>'
        )

    @staticmethod
    def _todo_start_next_guidance(pending: int) -> str:
        return (
            f'\n<system-reminder>还有{pending}个待处理任务但没有进行中的任务。'
            f'请立即调用 TodoWrite 将下一个pending任务更新为in_progress，'
            f'然后开始执行该任务。不要停留在计划阶段。</system-reminder>'
        )


class AgentOrchestrator:
    """
    Unified tool dispatch orchestrator.

    Inspired by hermes-agent's HermesAgentLoop, this class manages:
    1. Tool call ordering and priority
    2. Todo lifecycle enforcement
    3. request_user_input / agent_call dispatch
    4. MCP tool routing
    5. Stuck detection and recovery guidance
    """

    AGENT_CONTROL_TOOLS = {'TodoRead', 'TodoWrite', 'request_user_input', 'agent_call', 'Skills'}
    FORM_TOOLS = {'request_user_input'}
    TODO_TOOLS = {'TodoRead', 'TodoWrite'}

    def __init__(self, session_id: str, agent):
        self.session_id = session_id
        self.agent = agent
        self._tools_called_this_session: List[str] = []
        self._current_phase = 'collect_info'
        self._iterations_since_last_todo_update = 0
        self._iterations_since_last_action = 0
        self._last_todo_state_hash = ''
        self._consecutive_info_gather_count = 0

    def record_tool_call(self, tool_name: str):
        self._tools_called_this_session.append(tool_name)
        self._update_phase(tool_name)

        category = TOOL_CATEGORIES.get(tool_name)
        if category == ToolCategory.INFORMATION_GATHER:
            self._consecutive_info_gather_count += 1
        else:
            self._consecutive_info_gather_count = 0

        if tool_name in self.TODO_TOOLS:
            self._iterations_since_last_todo_update = 0
        else:
            self._iterations_since_last_todo_update += 1

        if category in (ToolCategory.PANEL_OPERATION, ToolCategory.SYSTEM_OPERATION):
            self._iterations_since_last_action = 0
        else:
            self._iterations_since_last_action += 1

    def _update_phase(self, tool_name: str):
        category = TOOL_CATEGORIES.get(tool_name)
        if category == ToolCategory.INFORMATION_GATHER:
            if self._current_phase == 'collect_info':
                pass
        elif category in (ToolCategory.PANEL_OPERATION, ToolCategory.SYSTEM_OPERATION):
            self._current_phase = 'execute'
        elif tool_name in ('TodoWrite', 'TodoRead'):
            self._current_phase = 'plan'
        elif category == ToolCategory.AGENT_CONTROL:
            pass

    def get_iteration_guidance(self, iteration: int, user_intent: str) -> str:
        from apps.sysai.tools.agent_tools import TodoManager

        manager = TodoManager(self.session_id)
        todos = manager.get_todos()
        has_todos = len(todos) > 0
        pending = len([t for t in todos if t.status == 'pending'])
        in_progress = len([t for t in todos if t.status == 'in_progress'])

        guidance = ToolCallGuidance.get_phase_guidance(
            iteration=iteration,
            has_todos=has_todos,
            pending_todos=pending,
            in_progress_todos=in_progress,
            tools_called=self._tools_called_this_session,
            user_intent=user_intent,
        )

        stuck_guidance = self._get_stuck_guidance(has_todos, pending, in_progress)
        if stuck_guidance:
            if guidance:
                guidance += '\n' + stuck_guidance
            else:
                guidance = stuck_guidance

        return guidance

    def _get_stuck_guidance(self, has_todos: bool, pending: int, in_progress: int) -> str:
        parts = []

        if self._consecutive_info_gather_count >= 5:
            parts.append(
                '<system-reminder>警告：你已经连续5轮只收集信息而没有执行任何操作。'
                '请立即停止收集信息，基于已有信息开始执行操作或给出结论。'
                '如果信息已经足够，不要再调用信息收集工具。</system-reminder>'
            )

        if has_todos and self._iterations_since_last_todo_update >= 3:
            parts.append(
                '<system-reminder>警告：你已经3轮没有更新Todo状态了。'
                '请立即调用 TodoRead 查看当前任务状态，然后调用 TodoWrite 更新进度。'
                '如果有任务已完成但未标记，请立即标记为completed。</system-reminder>'
            )

        if has_todos and in_progress == 0 and pending > 0 and self._iterations_since_last_action >= 2:
            parts.append(
                f'<system-reminder>还有{pending}个待处理任务但没有进行中的任务，'
                f'且已经{self._iterations_since_last_action}轮没有执行操作。'
                '请立即调用 TodoWrite 将下一个pending任务设为in_progress并开始执行。</system-reminder>'
            )

        if not has_todos and self._iterations_since_last_action >= 4 and self._consecutive_info_gather_count >= 3:
            parts.append(
                '<system-reminder>你已经收集了多轮信息但既没有创建任务也没有执行操作。'
                '请基于已收集的信息直接给出结论或建议，不要再继续收集信息。</system-reminder>'
            )

        return '\n'.join(parts) if parts else ''

    def should_intercept_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Pre-process tool calls before execution.

        Returns None to proceed with normal execution,
        or a dict with 'action' and 'content' to override.
        """
        if tool_name == 'TodoRead':
            return self._handle_todo_read(arguments)

        if tool_name == 'TodoWrite':
            return self._handle_todo_write(arguments)

        if tool_name == 'agent_call':
            return self._handle_agent_call(arguments)

        return None

    def _handle_todo_read(self, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    def _handle_todo_write(self, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        todos_data = arguments.get('todos', [])
        if not isinstance(todos_data, list) or not todos_data:
            return None

        in_progress_count = sum(
            1 for t in todos_data
            if isinstance(t, dict) and t.get('status') == 'in_progress'
        )
        if in_progress_count > 1:
            for t in todos_data:
                if isinstance(t, dict) and t.get('status') == 'in_progress':
                    t['status'] = 'pending'

            first_pending = None
            for t in todos_data:
                if isinstance(t, dict) and t.get('status') == 'pending':
                    first_pending = t
                    break

            if first_pending is not None:
                first_pending['status'] = 'in_progress'

            arguments['todos'] = todos_data

        return None

    def _handle_agent_call(self, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        agent_name = arguments.get('agent_name', '')
        task = arguments.get('task', '')

        if not agent_name:
            return None

        auto_collect_steps = self._get_agent_auto_collect(agent_name)
        if auto_collect_steps:
            arguments['_auto_collect_steps'] = auto_collect_steps
            arguments['_task'] = task

        return None

    def _get_agent_auto_collect(self, agent_name: str) -> List[Dict[str, Any]]:
        try:
            from apps.sysai.agent.specialized import AGENT_REGISTRY, get_agent_class
            agent_cls = AGENT_REGISTRY.get(agent_name) or get_agent_class(agent_name)
            if agent_cls:
                instance = agent_cls()
                return instance.get_auto_collect_steps()
        except Exception:
            pass
        return []

    def post_process_tool_result(self, tool_name: str, arguments: Dict[str, Any], result: str) -> str:
        """
        Post-process tool results to inject guidance.

        Inspired by hermes-agent's enforce_turn_budget and
        tool result enhancement patterns.
        """
        if tool_name == 'TodoWrite':
            return self._enhance_todo_write_result(result)

        if tool_name == 'agent_call':
            return self._enhance_agent_call_result(arguments, result)

        if tool_name == 'request_user_input':
            return result

        return result

    def _enhance_todo_write_result(self, result: str) -> str:
        from apps.sysai.tools.agent_tools import TodoManager
        manager = TodoManager(self.session_id)
        todos = manager.get_todos()

        in_progress = [t for t in todos if t.status == 'in_progress']
        pending = [t for t in todos if t.status == 'pending']
        completed = [t for t in todos if t.status == 'completed']

        guidance_parts = []

        if in_progress:
            current = in_progress[0]
            guidance_parts.append(
                f'\n\n[任务指引] 当前执行中: "{current.content}" (id={current.id})。'
                f'请立即调用相应工具执行此任务，完成后调用 TodoWrite 将其状态更新为completed。'
            )
        elif pending:
            next_task = pending[0]
            guidance_parts.append(
                f'\n\n[任务指引] 无进行中任务，下一个待执行: "{next_task.content}" (id={next_task.id})。'
                f'请调用 TodoWrite 将此任务更新为in_progress，然后立即执行。'
            )
        elif completed and len(completed) == len(todos):
            guidance_parts.append(
                '\n\n[任务指引] 所有任务已完成。请向用户汇报最终结果。'
            )

        if guidance_parts:
            result += ''.join(guidance_parts)

        return result

    def _enhance_agent_call_result(self, arguments: Dict[str, Any], result: str) -> str:
        agent_name = arguments.get('agent_name', '')
        task = arguments.get('task', '')

        if not agent_name or not task:
            return result

        enhancement = (
            '\n\n[智能体调用指引] 你已获取专家建议。现在请：\n'
            '1. 基于专家建议，制定具体执行步骤\n'
            '2. 如果是复杂任务，调用 TodoWrite 创建任务列表\n'
            '3. 立即开始执行第一个步骤\n'
            '不要只是转述专家建议，要付诸行动。'
        )

        return result + enhancement


orchestrator_registry: Dict[str, AgentOrchestrator] = {}


def get_or_create_orchestrator(session_id: str, agent=None) -> AgentOrchestrator:
    if session_id not in orchestrator_registry:
        orchestrator_registry[session_id] = AgentOrchestrator(session_id, agent)
    elif agent and orchestrator_registry[session_id].agent is None:
        orchestrator_registry[session_id].agent = agent
    return orchestrator_registry[session_id]


def cleanup_orchestrator(session_id: str):
    orchestrator_registry.pop(session_id, None)
