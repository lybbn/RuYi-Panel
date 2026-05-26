import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

IDEMPOTENT_TOOL_NAMES = frozenset({
    'panel_shop_list', 'panel_shop_task_status',
    'panel_site_list', 'panel_site_detail',
    'panel_database_list', 'panel_database_root_pass',
    'panel_docker_square_list', 'panel_docker_square_catalog',
    'docker_list_containers', 'docker_container_info', 'docker_container_logs',
    'docker_list_images', 'docker_search_images',
    'get_system_info', 'get_system_resource', 'get_system_logs',
    'get_network_info', 'get_disk_info', 'get_process_info',
    'check_website_status', 'read_website_config',
    'file_read', 'search_docs',
    'panel_cron_list', 'panel_firewall_status',
    'panel_ssl_list',
})

MUTATING_TOOL_NAMES = frozenset({
    'execute_command', 'file_write', 'file_delete',
    'panel_shop_install', 'panel_shop_manage',
    'panel_site_create', 'panel_site_manage', 'panel_site_domains',
    'panel_database_create', 'panel_database_delete', 'panel_database_reset_pass',
    'panel_docker_square_install', 'panel_docker_square_manage',
    'docker_manage_container', 'docker_pull_image', 'docker_remove_image',
    'service_manage', 'firewall_manage',
    'panel_cron_create', 'panel_cron_manage',
})


@dataclass(frozen=True)
class ToolGuardrailConfig:
    exact_failure_warn_after: int = 2
    exact_failure_block_after: int = 4
    same_tool_failure_warn_after: int = 3
    same_tool_failure_halt_after: int = 6
    no_progress_warn_after: int = 2
    no_progress_block_after: int = 4
    idempotent_tools: frozenset = field(default_factory=lambda: IDEMPOTENT_TOOL_NAMES)
    mutating_tools: frozenset = field(default_factory=lambda: MUTATING_TOOL_NAMES)


@dataclass(frozen=True)
class ToolCallSignature:
    tool_name: str
    args_hash: str

    @classmethod
    def from_call(cls, tool_name: str, args: Mapping[str, Any]) -> 'ToolCallSignature':
        canonical = _canonical_args(args)
        return cls(tool_name=tool_name, args_hash=_sha256(canonical))


@dataclass
class GuardrailDecision:
    action: str = 'allow'
    code: str = 'allow'
    message: str = ''
    tool_name: str = ''
    count: int = 0
    signature: Optional[ToolCallSignature] = None

    @property
    def allows_execution(self) -> bool:
        return self.action in ('allow', 'warn')

    @property
    def should_halt(self) -> bool:
        return self.action in ('block', 'halt')


class ToolCallGuardrailController:
    def __init__(self, config: ToolGuardrailConfig = None):
        self.config = config or ToolGuardrailConfig()
        self.reset()

    def reset(self):
        self._exact_failure_counts: Dict[ToolCallSignature, int] = {}
        self._same_tool_failure_counts: Dict[str, int] = {}
        self._no_progress: Dict[ToolCallSignature, tuple] = {}
        self._halt_decision: Optional[GuardrailDecision] = None

    @property
    def halt_decision(self) -> Optional[GuardrailDecision]:
        return self._halt_decision

    def before_call(self, tool_name: str, args: Dict[str, Any]) -> GuardrailDecision:
        signature = ToolCallSignature.from_call(tool_name, args or {})

        exact_count = self._exact_failure_counts.get(signature, 0)
        if exact_count >= self.config.exact_failure_block_after:
            decision = GuardrailDecision(
                action='block',
                code='repeated_exact_failure',
                message=(
                    f'工具 {tool_name} 使用相同参数已失败 {exact_count} 次，'
                    '请更换策略或参数，不要重复调用。'
                ),
                tool_name=tool_name,
                count=exact_count,
                signature=signature,
            )
            self._halt_decision = decision
            return decision

        if self._is_idempotent(tool_name):
            record = self._no_progress.get(signature)
            if record is not None:
                _result_hash, repeat_count = record
                if repeat_count >= self.config.no_progress_block_after:
                    decision = GuardrailDecision(
                        action='block',
                        code='idempotent_no_progress',
                        message=(
                            f'只读工具 {tool_name} 已返回相同结果 {repeat_count} 次，'
                            '请使用已有结果或更换查询方式，不要重复调用。'
                        ),
                        tool_name=tool_name,
                        count=repeat_count,
                        signature=signature,
                    )
                    self._halt_decision = decision
                    return decision

        same_count = self._same_tool_failure_counts.get(tool_name, 0)
        if same_count >= self.config.same_tool_failure_halt_after:
            decision = GuardrailDecision(
                action='halt',
                code='same_tool_failure_halt',
                message=(
                    f'工具 {tool_name} 本轮已失败 {same_count} 次，'
                    '请停止重试此工具，改用其他方式解决问题。'
                ),
                tool_name=tool_name,
                count=same_count,
                signature=signature,
            )
            self._halt_decision = decision
            return decision

        return GuardrailDecision(tool_name=tool_name, signature=signature)

    def after_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: str,
        *,
        failed: bool = False,
    ) -> GuardrailDecision:
        signature = ToolCallSignature.from_call(tool_name, args or {})

        if failed:
            exact_count = self._exact_failure_counts.get(signature, 0) + 1
            self._exact_failure_counts[signature] = exact_count
            self._no_progress.pop(signature, None)

            same_count = self._same_tool_failure_counts.get(tool_name, 0) + 1
            self._same_tool_failure_counts[tool_name] = same_count

            if same_count >= self.config.same_tool_failure_halt_after:
                decision = GuardrailDecision(
                    action='halt',
                    code='same_tool_failure_halt',
                    message=(
                        f'工具 {tool_name} 本轮已失败 {same_count} 次，'
                        '请停止重试此工具，改用其他方式解决问题。'
                    ),
                    tool_name=tool_name,
                    count=same_count,
                    signature=signature,
                )
                self._halt_decision = decision
                return decision

            if exact_count >= self.config.exact_failure_warn_after:
                return GuardrailDecision(
                    action='warn',
                    code='repeated_exact_failure_warning',
                    message=(
                        f'工具 {tool_name} 使用相同参数已失败 {exact_count} 次，'
                        '看起来进入了循环，请检查错误信息并更换策略。'
                    ),
                    tool_name=tool_name,
                    count=exact_count,
                    signature=signature,
                )

            if same_count >= self.config.same_tool_failure_warn_after:
                return GuardrailDecision(
                    action='warn',
                    code='same_tool_failure_warning',
                    message=(
                        f'工具 {tool_name} 本轮已失败 {same_count} 次，'
                        '请考虑更换方式解决问题。'
                    ),
                    tool_name=tool_name,
                    count=same_count,
                    signature=signature,
                )

            return GuardrailDecision(tool_name=tool_name, count=exact_count, signature=signature)

        self._exact_failure_counts.pop(signature, None)
        self._same_tool_failure_counts.pop(tool_name, None)

        if not self._is_idempotent(tool_name):
            self._no_progress.pop(signature, None)
            return GuardrailDecision(tool_name=tool_name, signature=signature)

        result_hash = _sha256(result or '')
        previous = self._no_progress.get(signature)
        repeat_count = 1
        if previous is not None and previous[0] == result_hash:
            repeat_count = previous[1] + 1
        self._no_progress[signature] = (result_hash, repeat_count)

        if repeat_count >= self.config.no_progress_warn_after:
            return GuardrailDecision(
                action='warn',
                code='idempotent_no_progress_warning',
                message=(
                    f'只读工具 {tool_name} 已返回相同结果 {repeat_count} 次，'
                    '请使用已有结果，不要重复调用。'
                ),
                tool_name=tool_name,
                count=repeat_count,
                signature=signature,
            )

        return GuardrailDecision(tool_name=tool_name, count=repeat_count, signature=signature)

    def _is_idempotent(self, tool_name: str) -> bool:
        if tool_name in self.config.mutating_tools:
            return False
        return tool_name in self.config.idempotent_tools


def append_guardrail_guidance(result: str, decision: GuardrailDecision) -> str:
    if decision.action not in ('warn', 'halt', 'block') or not decision.message:
        return result
    label = '工具循环阻断' if decision.action in ('halt', 'block') else '工具循环警告'
    return (result or '') + f'\n\n[{label}: {decision.message}]'


def _canonical_args(args: Mapping[str, Any]) -> str:
    if not isinstance(args, Mapping):
        return str(args)
    return json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()
