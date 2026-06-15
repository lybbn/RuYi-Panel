import json
import logging
import platform
import re
import threading
import uuid
from typing import Generator, List, Dict, Any, Optional, Union

from apps.sysai.provider.base import ChatMessage, ChatResponse, ToolDefinition
from apps.sysai.tools.base import AIToolRegistry, _xml_response
from utils.common import repair_json

logger = logging.getLogger(__name__)


def _get_os_info() -> str:
    system = platform.system()
    release = platform.release()
    version = platform.version()
    machine = platform.machine()

    if system == 'Windows':
        return (
            f'**当前服务器操作系统**: Windows {release}\n'
            f'- 版本: {version}\n'
            f'- 架构: {machine}\n'
            f'- **命令规范**: 必须使用Windows命令（如 dir、tasklist、netstat、sc、powershell 等），禁止使用Linux命令（如 ls、ps、grep、systemctl 等）\n'
            f'- 如需执行复杂操作，优先使用 PowerShell 命令\n'
            f'- 路径分隔符使用反斜杠 \\，如 C:\\Users\\...\n'
        )
    elif system == 'Linux':
        return (
            f'**当前服务器操作系统**: Linux {release}\n'
            f'- 架构: {machine}\n'
            f'- **命令规范**: 使用标准Linux命令，注意不同发行版的包管理器差异（apt/yum/dnf）\n'
        )
    elif system == 'Darwin':
        return (
            f'**当前服务器操作系统**: macOS {release}\n'
            f'- 架构: {machine}\n'
            f'- **命令规范**: 使用macOS兼容命令，包管理器为brew\n'
        )
    else:
        return f'**当前服务器操作系统**: {system} {release} ({machine})\n'


SYSTEM_PROMPT_TEMPLATE = """你是如意面板(Ruyi Panel)的专业服务器运维工程师。

{os_info}

═══════════════════════════════════════
核心原则
═══════════════════════════════════════
1. 真实可信：基于工具返回数据，不确定就说不知道，绝不编造
2. 简洁精准：工具返回后直接给结论，不重复啰嗦
3. 面板工具优先：面板能做的不用命令行
4. 安全第一：危险操作需确认，禁止未经授权获取密码

═══════════════════════════════════════
工具优先级（从高到低，必须遵守）
═══════════════════════════════════════
1. 面板专用工具（最优先）
   - 软件管理：panel_shop_install / panel_shop_manage（禁止apt/yum/systemctl）
   - Docker应用：panel_docker_square_install / panel_docker_square_manage（禁止docker run）
   - 网站管理：panel_site_create / panel_site_manage（禁止直接改Nginx配置）
   - 数据库：panel_database_create / panel_database_list（禁止mysql -e）
   - 定时任务：crontab_create / crontab_list（跨平台，禁止crontab -e/schtasks）
   - 漏洞扫描：vuln_scan_kernel / vuln_get_cve_info / vuln_scan_packages
2. 信息收集：search_docs / get_system_info / get_disk_info / get_process_info / read_file
3. 文件写入：write_file（禁止用execute_command的cat/echo/tee/heredoc写文件）
4. 系统操作：execute_command / service_manage
   ⚠️ execute_command每次都会弹出用户确认对话框，严重影响体验，尽量少用
   ⚠️ 以下场景禁止使用execute_command，必须用面板专用工具：
   - 查看容器日志 → docker_container_logs（禁止execute_command执行docker logs）
   - 查看容器详情 → docker_container_inspect（禁止execute_command执行docker inspect）
   - 查看数据库列表 → panel_database_list（禁止execute_command执行mysql -e "SHOW DATABASES"）
   - 创建数据库/用户 → panel_database_create（禁止execute_command执行mysql -e "CREATE DATABASE"）
   - 获取数据库Root密码 → panel_database_root_pass（禁止execute_command读取配置文件）
   - 查看Docker容器列表 → panel_docker_square_list（禁止execute_command执行docker ps）
   - 查看容器环境变量 → docker_container_inspect（禁止execute_command执行docker exec ... env）
5. MCP外部工具：mcp_*
6. 控制工具：TodoWrite / TodoRead / request_user_input / agent_call / Skills

═══════════════════════════════════════
项目部署（部署意图触发专用Agent，此处仅做初步判断）
═══════════════════════════════════════
用户请求"部署xxx"时：
- 容器化应用（WordPress/MySQL等）→ panel_docker_square_catalog 查广场 → panel_docker_square_install 安装
- Git仓库项目 → panel_deploy_project 一键部署 或 panel_runtime_site_create 分步部署
- 密码传默认值（工具自动替换弱密码），服务地址传空或默认值（工具自动解析）
- 禁止手动写Nginx配置，禁止docker run，禁止execute_command生成密码/查网关IP

═══════════════════════════════════════
TodoWrite规则
═══════════════════════════════════════
✅ 多步骤操作时使用，创建后立即执行第一个任务（in_progress）
❌ 知识问答/简单查看时不使用
同一时间只有一个in_progress，完成后立即更新状态

═══════════════════════════════════════
信息收集与交互
═══════════════════════════════════════
- 缺少关键参数（域名/端口/密码等）→ request_user_input 表单收集，不用纯文本提问
- 面板操作问题 → 先 search_docs 查文档，不凭记忆回答
- 运维操作类问题 → 先调用工具收集信息，不直接给方案
- 日常对话/问候/闲聊 → 直接回复，不调用任何工具

═══════════════════════════════════════
工具调用规则
═══════════════════════════════════════
- 必须用function calling，禁止在文本中输出工具调用
- 严格使用工具定义中的参数名（如 search_docs 的参数是 query）
- 工具失败时根据错误调整参数重试，不放弃
- 写入文件必须用 write_file，禁止execute_command写文件

═══════════════════════════════════════
技能系统
═══════════════════════════════════════
- 系统会自动注入匹配的技能指令，按指令执行
- 可用 Skills 工具手动加载/查看技能
- 创建/修改技能用 skill_manage 工具

回答格式：Markdown，代码块标注语言，关键信息加粗
"""

TOOLSET_SUPPLEMENT_PROMPTS = {
    'vulnerability': """
### 漏洞检测补充规则
- 内核漏洞扫描 → vuln_scan_kernel（禁止execute_command手动检测）
- CVE详情查询 → vuln_get_cve_info（禁止凭记忆编造CVE信息）
- 软件包安全更新 → vuln_scan_packages（优先于get_security_updates）
- risk_level由代码确定性判断，AI不得修改结论：
  safe=安全 / caution=注意(低风险) / notice=注意(建议升级) / warning=存在风险 / dangerous=危险
""",
    'crontab': """
### 定时任务补充规则
- crontab_*系列工具同时支持Windows和Linux，底层自动适配
- 绝对禁止用execute_command执行crontab -l/-e/-r或schtasks等系统命令
""",
    'panel_shop': """
### 应用商店补充规则
- 安装软件前必须先查询知识库：search_docs(query="AI安装指南")
- 安装软件 → panel_shop_install（禁止apt/yum install/dnf install）
- 管理软件 → panel_shop_manage（禁止systemctl start/stop/restart）
- 查看进度 → panel_shop_task_status
⛔ 绝对禁止使用execute_command执行以下命令：
  - apt-get install / apt install
  - yum install / dnf install
  - apt update / apt-get update
  - yum update / dnf update
  - 任何系统包管理器安装/更新命令
安装失败时，重试panel_shop_install，不要尝试用系统命令修复！
""",
    'panel_docker': """
### Docker广场补充规则
- 安装前必须查询知识库：search_docs(query="AI安装指南")
- 查看已部署应用 → panel_docker_square_list（优先于docker_list_containers）
- 查看可安装应用 → panel_docker_square_catalog（安装前必须先查目录）
- 安装Docker应用 → panel_docker_square_install（禁止docker run）
- 管理Docker应用 → panel_docker_square_manage
⛔ 重要规则（详细说明见知识库）：
  1. panel_service_type必须传【实例名称】如"my-mysql"，不是应用名称"mysql"
  2. 服务地址不要手动指定，系统自动填充
  3. 密码传默认值，工具自动替换弱密码
- 依赖服务未安装 → 必须询问用户选择：容器广场(推荐) or Docker原生
- 广场中不存在该应用 → 告知用户并询问是否用Docker原生方式
""",
    'panel_site': """
### 网站管理补充规则
- 查看网站 → panel_site_list（禁止扫描Nginx配置）
- 创建网站 → panel_site_create（禁止直接修改Nginx配置）
- 管理网站 → panel_site_manage / panel_site_domains
- 部署项目 → panel_deploy_project（一键部署，优先使用）
- 创建运行时站点 → panel_runtime_site_create（Python/Node/Go/PHP项目）
- 反向代理 → panel_site_proxy（禁止手动写Nginx代理配置）
- SSL证书 → panel_site_ssl（禁止手动配置SSL）
- 部署Git项目流程：panel_deploy_project 或 panel_runtime_site_create + panel_site_create + panel_site_proxy + panel_site_ssl
""",
    'panel_deploy': """
### 智能部署补充规则（最高优先级）
⛔ 第一步：查询安装指南知识库
  search_docs(query="AI安装指南") 或 search_docs(query="Docker广场安装")

⛔ 红线：
  R1. 第一个工具调用必须是 TodoWrite
  R2. 必须调用 panel_environment_probe 探测环境
  R3. 部署完成后必须调用 panel_deploy_verify 验证服务
  R4. 密码传默认值（工具自动替换弱密码），禁止手动生成或传弱密码
  R5. 服务地址传空或默认值（工具自动解析），禁止手动设置172.x.x.1等网关IP
  R6. 禁止execute_command生成密码/查网关IP/查容器端口（工具已内置）
  R7. 尽量减少execute_command调用（每次弹确认框，严重影响体验）
  R8. 部署成功后必须执行部署后配置，禁止只文字推荐就结束对话
  R9. 如果应用依赖数据库，部署后必须检查数据库是否已创建
  R10. panel_deploy_verify返回success=false时，禁止标记任务为completed
- Nginx安装必须用panel_shop_install("nginx")，禁止execute_command
- 验证失败时的排查顺序：1.检查依赖服务 2.检查数据库 3.查看容器日志 4.等待后重试
""",
    'panel_database': """
### 数据库管理补充规则
- 查看数据库 → panel_database_list（禁止mysql -e）
- 创建数据库 → panel_database_create（禁止SQL创建）
- 获取Root密码 → panel_database_root_pass
""",
}


class Agent:
    def __init__(
        self,
        session_id: str,
        model: Any,
        config: Dict[str, Any] = None,
        tool_registry: AIToolRegistry = None,
    ):
        self.session_id = session_id
        self.model = model
        self.config = config or {}
        self.tool_registry = tool_registry or AIToolRegistry()

        os_info = _get_os_info()
        base_prompt = SYSTEM_PROMPT_TEMPLATE.replace('{os_info}', os_info)
        custom_prompt = self.config.get('system_prompt', '').strip()
        if custom_prompt and custom_prompt not in (
            '',
            '你是如意面板的AI助手，一个专业的服务器运维专家。你可以帮助用户管理服务器、诊断问题、部署应用、优化性能。在执行危险操作前，请先向用户确认。',
        ):
            base_prompt += f'\n\n### 用户自定义指令\n{custom_prompt}'
        self.system_prompt = base_prompt
        self.max_tool_iterations = self.config.get('max_tool_iterations', 20)
        logger.info(f'[Agent新建] max_tool_iterations={self.max_tool_iterations}, config={self.config.get("max_tool_iterations", "未设置")}')
        self.enabled_tools = self.config.get('enabled_tools', None)

        if self.enabled_tools:
            from apps.sysai.agent.toolsets import TOOLSETS
            active_toolsets = []
            for ts_name, ts_info in TOOLSETS.items():
                ts_tools = ts_info.get('tools', [])
                if any(t in self.enabled_tools for t in ts_tools):
                    active_toolsets.append(ts_name)
            for ts_name in active_toolsets:
                supplement = TOOLSET_SUPPLEMENT_PROMPTS.get(ts_name, '').strip()
                if supplement:
                    self.system_prompt += '\n\n' + supplement
        self.temperature = self.config.get('temperature', 0.7)
        self.top_p = self.config.get('top_p', 1.0)
        self.require_command_confirm = self.config.get('require_command_confirm', 'medium_high')
        self.max_context_messages = self.config.get('max_context_messages', 30)
        self.enable_memory = self.config.get('enable_memory', False)
        self.memory_recall_threshold = self.config.get('memory_recall_threshold', 10)
        self.web_search = self.config.get('web_search', False)

        if self.web_search:
            try:
                from apps.sysai.tools.web_search import _is_web_search_available
                if _is_web_search_available():
                    self.system_prompt += '\n\n### 网络搜索\n你拥有网络搜索能力，可以使用 web_search 工具搜索互联网获取最新信息。当需要查找最新资讯、技术文档、解决方案时，请主动使用搜索工具。'
                else:
                    self.web_search = False
            except Exception:
                self.web_search = False

        self._memory_store = None
        self._stop_flag = False
        self._stop_reason = ''
        self._confirm_events = {}
        self._confirm_results = {}
        self._confirm_lock = threading.Lock()
        self._remembered_approvals = {}  # {tool_name: bool} session级"记住选择"缓存
        self._form_events = {}
        self._form_results = {}
        self._form_lock = threading.Lock()
        self._progress_callback = None

        from apps.sysai.agent.tool_guardrails import ToolCallGuardrailController
        self._guardrail = ToolCallGuardrailController()

        from apps.sysai.agent.agent_orchestrator import get_or_create_orchestrator
        self._orchestrator = get_or_create_orchestrator(self.session_id, self)

    def stop(self, reason='user'):
        self._stop_flag = True
        self._stop_reason = reason
        with self._confirm_lock:
            for event in self._confirm_events.values():
                event.set()
        with self._form_lock:
            for event in self._form_events.values():
                event.set()

    def is_stopped(self):
        return self._stop_flag

    def get_stop_reason(self):
        return self._stop_reason

    def reset_stop(self):
        self._stop_flag = False
        self._stop_reason = ''

    def cancel_current_command(self):
        self._stop_flag = True
        self._stop_reason = 'command_cancelled'
        with self._confirm_lock:
            for event in self._confirm_events.values():
                event.set()
        with self._form_lock:
            for event in self._form_events.values():
                event.set()
        logger.info(f'Agent命令取消: session={self.session_id}')

    def set_progress_callback(self, callback):
        self._progress_callback = callback
        self.tool_registry.set_progress_callback(callback, session_id=self.session_id)

    def _emit_progress(self, event_type: str, tool_name: str, call_id: str = '',
                       progress: int = 0, message: str = '', data: Dict[str, Any] = None):
        if self._progress_callback:
            try:
                self._progress_callback(event_type, tool_name, call_id, progress, message, data)
            except Exception as e:
                logger.debug(f'进度回调异常: {e}')

    def confirm_tool(self, confirm_id: str, approved: bool, remember: bool = False):
        with self._confirm_lock:
            self._confirm_results[confirm_id] = approved
            # 记住选择：从 confirm_id 提取 tool_name
            # confirm_id 格式: confirm_{func_name}::{call_id}
            if remember and '::' in confirm_id:
                tool_name = confirm_id.split('::')[0][len('confirm_'):]
                self._remembered_approvals[tool_name] = approved
            event = self._confirm_events.get(confirm_id)
        if event:
            event.set()

    def _wait_for_confirm(self, confirm_id: str, timeout: float = 600) -> bool:
        event = threading.Event()
        with self._confirm_lock:
            self._confirm_events[confirm_id] = event
        check_interval = 0.5
        elapsed = 0.0
        while elapsed < timeout:
            if self._stop_flag:
                with self._confirm_lock:
                    self._confirm_events.pop(confirm_id, None)
                return False
            if event.wait(timeout=check_interval):
                break
            elapsed += check_interval
        with self._confirm_lock:
            self._confirm_events.pop(confirm_id, None)
        if elapsed >= timeout and not event.is_set():
            return False
        with self._confirm_lock:
            return self._confirm_results.pop(confirm_id, False)

    def submit_form(self, form_id: str, data: dict):
        with self._form_lock:
            self._form_results[form_id] = data
            event = self._form_events.get(form_id)
        if event:
            event.set()

    def _wait_for_form(self, form_id: str, timeout: float = 1800) -> dict:
        event = threading.Event()
        with self._form_lock:
            self._form_events[form_id] = event
        check_interval = 0.5
        elapsed = 0.0
        while elapsed < timeout:
            if self._stop_flag:
                with self._form_lock:
                    self._form_events.pop(form_id, None)
                return None
            if event.wait(timeout=check_interval):
                break
            elapsed += check_interval
        with self._form_lock:
            self._form_events.pop(form_id, None)
        if elapsed >= timeout and not event.is_set():
            return None
        with self._form_lock:
            return self._form_results.pop(form_id, None)

    def _save_trajectory(self, messages: list, iteration: int, reason: str = 'interrupted'):
        try:
            import os
            import json
            from datetime import datetime

            trajectory_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                'data', 'agent', 'trajectories', self.session_id
            )
            os.makedirs(trajectory_dir, exist_ok=True)

            safe_messages = []
            for m in messages[-50:]:
                safe_m = {'role': m.get('role', '')}
                if m.get('content'):
                    safe_m['content'] = str(m.get('content', ''))[:5000]
                if m.get('tool_calls'):
                    safe_m['tool_calls'] = [
                        {
                            'id': tc.get('id', ''),
                            'function': {
                                'name': tc.get('function', {}).get('name', ''),
                                'arguments': str(tc.get('function', {}).get('arguments', ''))[:2000],
                            }
                        }
                        for tc in m['tool_calls']
                    ]
                if m.get('tool_call_id'):
                    safe_m['tool_call_id'] = m['tool_call_id']
                safe_messages.append(safe_m)

            trajectory = {
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'reason': reason,
                'iteration': iteration,
                'message_count': len(safe_messages),
                'messages': safe_messages,
            }

            filepath = os.path.join(trajectory_dir, f'trajectory_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(trajectory, f, ensure_ascii=False, indent=2)

            logger.info(f'轨迹已保存: {filepath}, reason={reason}, iteration={iteration}')
        except Exception as e:
            logger.warning(f'保存轨迹失败: {e}')

    def get_last_trajectory_summary(self) -> str:
        try:
            import os
            import json
            import glob

            trajectory_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                'data', 'agent', 'trajectories', self.session_id
            )

            if not os.path.exists(trajectory_dir):
                return ''

            files = sorted(glob.glob(os.path.join(trajectory_dir, 'trajectory_*.json')), reverse=True)
            if not files:
                return ''

            with open(files[0], 'r', encoding='utf-8') as f:
                trajectory = json.load(f)

            summary_parts = [
                f'[会话恢复] 上次会话因 "{trajectory.get("reason", "未知")}" 中断，'
                f'已执行 {trajectory.get("iteration", 0)} 轮对话。'
            ]

            messages = trajectory.get('messages', [])
            tool_calls = [m for m in messages if m.get('role') == 'assistant' and m.get('tool_calls')]
            if tool_calls:
                last_tools = []
                for tc in tool_calls[-1].get('tool_calls', [])[-3:]:
                    last_tools.append(tc.get('function', {}).get('name', ''))
                if last_tools:
                    summary_parts.append(f'最后调用的工具: {", ".join(last_tools)}')

            tool_results = [m for m in messages if m.get('role') == 'tool']
            if tool_results:
                summary_parts.append(f'已获取 {len(tool_results)} 个工具结果。')

            return '\n'.join(summary_parts)
        except Exception as e:
            logger.warning(f'读取轨迹失败: {e}')
            return ''

    def _get_memory_store(self):
        if self._memory_store is not None:
            return self._memory_store

        if not self.enable_memory:
            from apps.sysai.memory.noop import NoOpMemoryStore
            self._memory_store = NoOpMemoryStore()
            return self._memory_store

        try:
            from apps.sysai.memory.embedding import EmbeddingProvider
            from apps.sysai.memory.local_store import LocalVectorMemoryStore

            sys_config = {}
            try:
                from apps.sysai.models import AIModel
                config_obj = AIModel.get_sys_config()
                if config_obj.extra_params:
                    sys_config = config_obj.extra_params
            except Exception:
                pass

            embedding_provider = EmbeddingProvider(sys_config)
            self._memory_store = LocalVectorMemoryStore(embedding_provider)
        except Exception as e:
            logger.warning(f'记忆系统初始化失败，降级为NoOp: {e}')
            from apps.sysai.memory.noop import NoOpMemoryStore
            self._memory_store = NoOpMemoryStore()

        return self._memory_store

    def _recall_memory(self, user_message: str, history: list) -> str:
        user_assistant_count = sum(
            1 for m in history if m.get('role') in ('user', 'assistant')
        )
        if user_assistant_count < self.memory_recall_threshold:
            return ''

        store = self._get_memory_store()
        if not store.is_available():
            return ''

        try:
            results = store.search(self.session_id, user_message, top_k=3, threshold=0.4)
            if not results:
                return ''

            parts = []
            for r in results:
                source_label = r.get('source', 'memory')
                if source_label == 'flush':
                    parts.append(f'[历史事实] {r["text"]}')
                else:
                    parts.append(f'[历史对话] {r["text"]}')

            return '\n'.join(parts)
        except Exception as e:
            logger.warning(f'记忆召回失败: {e}')
            return ''

    def _extract_text_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        if not content:
            return []

        extracted = []
        if re.search(r'<longcat_tool_call>.*?</longcat_tool_call>', content, re.DOTALL):
            logger.warning('检测到 longcat_tool_call 文本输出，已忽略该文本兜底工具调用，仅保留正文清洗')

        patterns = [
            r'```(?:json)?\s*\n?\s*(\{[^`]*?"name"\s*:\s*"(\w+)"[^`]*?"arguments"\s*:\s*(\{[^`]*?\})[^`]*?\})\s*\n?\s*```',
            r'"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*(\{[^}]*\})',
            r'(\w+)\s*\(\s*(\{[^}]*\})\s*\)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        tool_name = groups[1]
                        args_str = groups[2]
                    elif len(groups) == 2:
                        tool_name = groups[0]
                        args_str = groups[1]
                    else:
                        continue

                    if tool_name in self.tool_registry._tools:
                        args = repair_json(args_str)

                        if args is not None:
                            extracted.append({
                                'id': f'call_text_{uuid.uuid4().hex[:8]}',
                                'type': 'function',
                                'function': {
                                    'name': tool_name,
                                    'arguments': json.dumps(args, ensure_ascii=False),
                                }
                            })
                            logger.info(f'从文本中提取到工具调用: {tool_name}, args={args}')
                        else:
                            logger.warning(f'从文本中提取到工具名 {tool_name} 但参数解析失败: {args_str[:200]}')
                except Exception as e:
                    logger.debug(f'文本工具调用提取失败: {e}')

        if not extracted:
            args_pattern = r'arguments"\s*:\s*\{\s*"(\w+)"\s*:\s*"([^"]*)"'
            args_matches = re.findall(args_pattern, content)
            if args_matches:
                args_dict = {}
                for key, value in args_matches:
                    args_dict[key] = value

                context_keywords = {
                    'search_docs': ['文档', '搜索', '查询', '部署', '安装', '配置', '创建', 'SSL', 'Docker', 'PHP', '网站', '数据库'],
                    'execute_command': ['命令', '执行', '运行', '查看', '检查', '状态'],
                    'get_system_info': ['系统', 'CPU', '内存', '磁盘'],
                    'panel_site_list': ['网站', '站点', '域名'],
                    'panel_shop_list': ['软件', '应用', '安装'],
                    'panel_docker_square_list': ['Docker', '容器'],
                    'crontab_list': ['定时任务', '计划任务', 'cron', 'crontab', '定时'],
                }

                best_tool = None
                best_score = 0
                for tool_name, keywords in context_keywords.items():
                    if tool_name not in self.tool_registry._tools:
                        continue
                    score = sum(1 for kw in keywords if kw in content)
                    if score > best_score:
                        best_score = score
                        best_tool = tool_name

                if best_tool and args_dict:
                    extracted.append({
                        'id': f'call_text_{uuid.uuid4().hex[:8]}',
                        'type': 'function',
                        'function': {
                            'name': best_tool,
                            'arguments': json.dumps(args_dict, ensure_ascii=False),
                        }
                    })
                    logger.info(f'从残缺文本中推断工具调用: {best_tool}, args={args_dict}')

        return extracted

    def _clean_tool_leakage_from_content(self, content: str) -> str:
        if not content:
            return content

        cleaned = re.sub(
            r'<longcat_tool_call>.*?</longcat_tool_call>',
            '', content, flags=re.DOTALL
        )
        cleaned = re.sub(
            r'<tool_call>.*?</tool_call>',
            '', cleaned, flags=re.DOTALL
        )
        cleaned = re.sub(
            r'<tool>\s*<tool_name>.*?</tool_name>.*?</tool>',
            '', cleaned, flags=re.DOTALL
        )
        cleaned = re.sub(
            r'"arguments"\s*:\s*\{[^}]*"\}\s*',
            '', cleaned
        )
        cleaned = re.sub(
            r'arguments"\s*:\s*\{[^}]*\}',
            '', cleaned
        )
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = cleaned.strip()

        return cleaned

    def _match_skill_intent(self, user_input: str, skill) -> bool:
        if not user_input or not skill:
            return False

        user_lower = user_input.lower()

        name_lower = skill.name.lower().replace('-', ' ').replace('_', ' ')
        if name_lower in user_lower:
            return True

        desc_lower = (skill.description or '').lower()
        desc_keywords = [w for w in desc_lower.split() if len(w) > 1]
        match_count = sum(1 for kw in desc_keywords if kw in user_lower)
        if match_count >= 2:
            return True

        meta_keywords = (skill.metadata or {}).get('trigger_keywords', '')
        if meta_keywords:
            keywords = [kw.strip() for kw in meta_keywords.split(',') if kw.strip()]
            if any(kw.lower() in user_lower for kw in keywords):
                return True

        meta_platforms = (skill.metadata or {}).get('platforms', '')
        if meta_platforms:
            import platform as _pf
            current_os = _pf.system().lower()
            if current_os == 'darwin':
                current_os = 'macos'
            allowed_platforms = [p.strip().lower() for p in meta_platforms.split(',') if p.strip()]
            if allowed_platforms and current_os not in allowed_platforms:
                return False

        _builtin_trigger_keywords = {
            'skill-creator': ['创建技能', '新建技能', '写技能', '制作技能', '开发技能', 'skill'],
            'server-inspection': ['巡检', '检查服务器', '服务器状态', '健康检查'],
            'docker-deploy': ['docker部署', '容器部署', 'docker compose', '容器化'],
            'nginx-config': ['nginx配置', '网站配置', '反向代理', 'ssl配置'],
            'database-backup': ['数据库备份', '备份数据库', '数据导出', 'mysqldump'],
            'log-analysis': ['日志分析', '查看日志', '日志排查', '错误日志'],
            'firewall-setup': ['防火墙', '端口开放', '安全组', 'iptables', 'firewalld'],
            'ssl-certificate': ['ssl证书', 'https', '证书续期', 'letsencrypt'],
            'process-monitor': ['进程监控', 'cpu占用', '内存占用', '性能监控'],
            'cron-job': ['定时任务', 'crontab', '计划任务', '自动执行'],
        }

        if not meta_keywords:
            keywords = _builtin_trigger_keywords.get(skill.name, [])
            if any(kw in user_lower for kw in keywords):
                return True

        return False

    def _inject_skills_to_prompt(self, user_input: str) -> str:
        if not user_input:
            return ''

        try:
            from apps.sysai.skills import skill_manager
        except Exception:
            return ''

        enabled_skills = skill_manager.all_enabled()
        if not enabled_skills:
            return ''

        matched_skills = []
        for skill in enabled_skills:
            if self._match_skill_intent(user_input, skill):
                matched_skills.append(skill)

        if not matched_skills:
            return ''

        parts = []
        for skill in matched_skills[:3]:
            skill_content = skill.content.strip()
            if len(skill_content) > 3000:
                skill_content = skill_content[:3000] + '\n...[技能指令已截断，如需完整指令请使用 Skills 工具加载]...'
            parts.append(
                f'\n### 已激活技能: {skill.name}\n'
                f'以下为该技能的专业指令，请严格遵循：\n\n'
                f'{skill_content}\n'
            )

        if len(matched_skills) > 3:
            parts.append(f'\n(共匹配到 {len(matched_skills)} 个技能，仅注入前3个最相关的)\n')

        return '\n'.join(parts)

    def _build_messages(
        self,
        history: List[Dict[str, Any]],
        user_message: str,
        context_str: str = '',
    ) -> List[Dict[str, Any]]:
        messages = []

        system_content = self.system_prompt
        if context_str:
            system_content += f'\n\n[历史上下文]:\n{context_str}'

        memory_context = self._recall_memory(user_message, history)
        if memory_context:
            system_content += f'\n\n[相关记忆]:\n{memory_context}'

        try:
            from apps.sysai.memory.fact_cache import get_facts_summary
            facts_summary = get_facts_summary()
            if facts_summary:
                system_content += f'\n\n{facts_summary}\n注意：以上为之前会话已确认的事实，如果本次工具返回的结果与事实矛盾，以本次工具返回的最新结果为准，但需向用户说明变化。'
        except Exception:
            pass

        skill_context = self._inject_skills_to_prompt(user_message)
        if skill_context:
            system_content += skill_context

        messages.append({'role': 'system', 'content': system_content})

        raw_messages = []
        for msg in history:
            m = {'role': msg.get('role', 'user'), 'content': msg.get('content', '')}
            if msg.get('tool_calls'):
                m['tool_calls'] = msg['tool_calls']
            if msg.get('tool_call_id'):
                m['tool_call_id'] = msg['tool_call_id']
            if msg.get('name'):
                m['name'] = msg['name']
            # reasoning_content 仅用于前端展示思考过程，不放入API请求消息
            raw_messages.append(m)

        for m in raw_messages:
            if m['role'] == 'tool' and len(m.get('content', '')) > 10000:
                content = m['content']
                try:
                    from apps.sysai.tools.base import _smart_truncate
                    m['content'] = _smart_truncate(content, 10000)
                except Exception:
                    head = content[:7000]
                    tail = content[-2500:]
                    total = len(content)
                    m['content'] = f'{head}\n\n...[工具结果已裁剪，原始{total}字符]...\n\n{tail}'

        if len(raw_messages) > self.max_context_messages:
            truncated = raw_messages[-self.max_context_messages:]
            first_msg = truncated[0] if truncated else None
            if first_msg and first_msg['role'] == 'tool':
                start_idx = len(raw_messages) - self.max_context_messages
                for i in range(start_idx, -1, -1):
                    if raw_messages[i]['role'] == 'user':
                        start_idx = i
                        break
                truncated = raw_messages[start_idx:]
                if len(truncated) > self.max_context_messages:
                    truncated = truncated[-self.max_context_messages:]
            raw_messages = truncated

        known_tool_call_ids = set()
        for m in raw_messages:
            if m['role'] == 'assistant' and m.get('tool_calls'):
                for tc in m['tool_calls']:
                    if tc.get('id'):
                        known_tool_call_ids.add(tc['id'])

        for m in raw_messages:
            if m['role'] == 'tool':
                if not m.get('tool_call_id'):
                    continue
                if m['tool_call_id'] in known_tool_call_ids:
                    messages.append(m)
                    continue
                last_assistant = None
                for prev in reversed(messages):
                    if prev['role'] == 'assistant':
                        last_assistant = prev
                        break
                if not last_assistant:
                    continue
                if not last_assistant.get('tool_calls'):
                    last_assistant['tool_calls'] = []
                existing_ids = {tc['id'] for tc in last_assistant['tool_calls']}
                if m['tool_call_id'] not in existing_ids:
                    last_assistant['tool_calls'].append({
                        'id': m['tool_call_id'],
                        'type': 'function',
                        'function': {'name': m.get('name', 'unknown'), 'arguments': '{}'}
                    })
                known_tool_call_ids.add(m['tool_call_id'])
                messages.append(m)
            else:
                messages.append(m)

        messages.append({'role': 'user', 'content': user_message})

        return messages

    def _get_tools(self) -> Optional[List[Dict[str, Any]]]:
        if not self.tool_registry._tools:
            return None

        if self.enabled_tools is not None:
            if self.enabled_tools:
                tools = self.tool_registry.get_openai_tools(enabled_ids=self.enabled_tools)
            else:
                tools = []
        else:
            tools = self.tool_registry.get_openai_tools()

        if not tools:
            tools = []

        if self.web_search:
            web_search_tool = self.tool_registry.get_openai_tools(enabled_ids=['web_search'])
            if web_search_tool:
                existing_names = {t['function']['name'] for t in tools}
                for t in web_search_tool:
                    if t['function']['name'] not in existing_names:
                        tools.append(t)

        try:
            from apps.sysai.mcp import mcp_client_manager
            mcp_tools = mcp_client_manager.get_openai_tools()
            if mcp_tools:
                tools.extend(mcp_tools)
        except Exception as e:
            logger.debug(f'获取MCP工具失败: {e}')

        if not tools:
            return None

        return tools

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if tool_name.startswith('mcp_'):
            return self._execute_mcp_tool(tool_name, arguments)

        arguments['session_id'] = self.session_id
        progress_args = {k: v for k, v in arguments.items() if k != 'session_id'}
        self._emit_progress('tool.started', tool_name, data={'arguments': progress_args})
        result = self.tool_registry.execute(tool_name, arguments)
        if len(result) > 50000:
            try:
                from apps.sysai.tools.base import _smart_truncate
                inner = result
                result = _smart_truncate(inner, 50000)
            except Exception:
                head = result[:35000]
                tail = result[-12500:]
                total = len(result)
                result = f'{head}\n\n...[内容已截断，共{total}字符]...\n\n{tail}'

        self._emit_progress('tool.completed', tool_name, data={'success': '<toolcall_status>error</toolcall_status>' not in result})
        return result

    def _execute_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        try:
            from apps.sysai.mcp import mcp_client_manager
            result = mcp_client_manager.call_tool(tool_name, arguments)
            if len(result) > 50000:
                try:
                    from apps.sysai.tools.base import _smart_truncate
                    result = _smart_truncate(result, 50000)
                except Exception:
                    head = result[:35000]
                    tail = result[-12500:]
                    total = len(result)
                    result = f'{head}\n\n...[内容已截断，共{total}字符]...\n\n{tail}'
            return _xml_response(tool_name, 'done', result)
        except Exception as e:
            logger.error(f'MCP工具执行失败 [{tool_name}]: {e}')
            return _xml_response(tool_name, 'error', f'MCP工具执行失败: {str(e)}')

    def chat(
        self,
        user_input: str,
        history: List[Dict[str, Any]] = None,
        context_str: str = '',
    ) -> Generator[Dict[str, Any], None, None]:
        try:
            user_msg_id = str(uuid.uuid4())
            ai_msg_id = str(uuid.uuid4())

            yield {
                'type': 'meta_info',
                'user_msg_id': user_msg_id,
                'ai_msg_id': ai_msg_id,
            }

            messages = self._build_messages(history or [], user_input, context_str)

            is_continue = user_input.strip().lower() in ('继续', 'continue', 'go on', 'next')
            if not is_continue:
                _continue_keywords = ('继续完成', '继续生成', '继续执行', '请继续', '接着', '继续之前', '从上次中断')
                input_lower = user_input.strip().lower()
                is_continue = any(kw in input_lower for kw in _continue_keywords)
            if is_continue:
                trajectory_summary = self.get_last_trajectory_summary()
                if trajectory_summary:
                    messages.append({
                        'role': 'system',
                        'content': trajectory_summary + '\n请基于以上信息继续执行未完成的任务。',
                    })
                    logger.info(f'注入轨迹恢复上下文: {trajectory_summary[:200]}')

            tools = self._get_tools()

            iteration_count = 0
            full_response_content = ''
            full_reasoning_content = ''
            total_usage = {
                'total_tokens': 0,
                'input_tokens': 0,
                'output_tokens': 0,
            }
            consecutive_tool_failures = 0
            max_consecutive_failures = 3
            empty_response_retries = 0
            max_empty_response_retries = 1

            while iteration_count < self.max_tool_iterations:
                iteration_usage = {
                    'total_tokens': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                }

                if self.is_stopped():
                    stop_r = self.get_stop_reason()
                    logger.info(f'Agent在迭代开始时被停止: iteration={iteration_count}, stop_reason={stop_r}')
                    self._save_trajectory(messages, iteration_count, f'stopped:{stop_r}')
                    yield {
                        'type': 'stop',
                        'content': '生成已停止',
                        'usage': total_usage,
                    }
                    return

                iteration_count += 1

                if iteration_count > 1:
                    remaining = self.max_tool_iterations - iteration_count + 1
                    iter_msg = f'\n<system-reminder>操作轮次: {iteration_count}/{self.max_tool_iterations}. '
                    if remaining <= 2:
                        iter_msg += '警告: 即将到达工具执行上限，如果任务未完成请停止并告知用户。'

                    orchestrator_guidance = self._orchestrator.get_iteration_guidance(
                        iteration=iteration_count,
                        user_intent=user_input,
                    )
                    if orchestrator_guidance:
                        iter_msg += orchestrator_guidance

                    iter_msg += '</system-reminder>'
                    request_messages = list(messages)
                    request_messages.append({'role': 'system', 'content': iter_msg})
                else:
                    request_messages = messages

                tool_call_chunks = {}
                reported_tool_indices = set()
                tc_id_to_idx = {}
                current_response_content = ''
                current_reasoning_content = ''
                last_finish_reason = ''

                api_retry_count = 0
                max_api_retries = 2

                while api_retry_count <= max_api_retries:
                    try:
                        for chunk in self.model.chat_stream(request_messages, tools):
                            if self.is_stopped():
                                stop_r = self.get_stop_reason()
                                logger.info(f'Agent在流式处理中被停止: iteration={iteration_count}, stop_reason={stop_r}')
                                self._save_trajectory(messages, iteration_count, f'stopped_during_stream:{stop_r}')
                                yield {
                                    'type': 'stop',
                                    'content': '生成已停止',
                                    'usage': total_usage,
                                    'message_id': ai_msg_id,
                                    'full_response': full_response_content,
                                }
                                return

                            if chunk.reasoning_content and not chunk.finish_reason:
                                current_reasoning_content += chunk.reasoning_content
                                full_reasoning_content += chunk.reasoning_content
                                yield {
                                    'type': 'reasoning',
                                    'content': chunk.reasoning_content,
                                }

                            if chunk.content and not chunk.finish_reason:
                                current_response_content += chunk.content
                                full_response_content += chunk.content
                                yield {
                                    'type': 'content',
                                    'content': chunk.content,
                                }

                            if chunk.finish_reason:
                                last_finish_reason = chunk.finish_reason
                                if chunk.content and not current_response_content:
                                    current_response_content = chunk.content
                                    full_response_content += chunk.content
                                    yield {
                                        'type': 'content',
                                        'content': chunk.content,
                                    }
                                if chunk.reasoning_content and not current_reasoning_content:
                                    current_reasoning_content = chunk.reasoning_content
                                    full_reasoning_content += chunk.reasoning_content
                                    yield {
                                        'type': 'reasoning',
                                        'content': chunk.reasoning_content,
                                    }

                            if chunk.tool_calls:
                                for tc in chunk.tool_calls:
                                    tc_id = tc.get('id', '')
                                    tc_index = tc.get('index', 0)
                                    tc_name = tc.get('function', {}).get('name', '')
                                    tc_args = tc.get('function', {}).get('arguments', '')
                                    logger.debug(f'收到tool_call chunk: id={tc_id}, idx={tc_index}, name={tc_name}, args_len={len(tc_args)}, finish={chunk.finish_reason}')

                                    if tc_id and tc_id in tc_id_to_idx:
                                        target_idx = tc_id_to_idx[tc_id]
                                    elif tc_index not in tool_call_chunks:
                                        target_idx = tc_index
                                        if tc_id:
                                            tc_id_to_idx[tc_id] = target_idx
                                    elif tc_id and tool_call_chunks[tc_index].get('id') == tc_id:
                                        target_idx = tc_index
                                    elif not tc_id and tc_index in tool_call_chunks:
                                        target_idx = tc_index
                                    else:
                                        target_idx = max(tool_call_chunks.keys()) + 1 if tool_call_chunks else 0
                                        if tc_id:
                                            tc_id_to_idx[tc_id] = target_idx

                                    if target_idx not in tool_call_chunks:
                                        tool_call_chunks[target_idx] = {
                                            'id': tc_id or f'call_auto_{target_idx}_{uuid.uuid4().hex[:8]}',
                                            'type': 'function',
                                            'function': {'name': '', 'arguments': ''},
                                        }

                                    if tc_id and not tool_call_chunks[target_idx]['id']:
                                        tool_call_chunks[target_idx]['id'] = tc_id

                                    tc_func_name = tc.get('function', {}).get('name', '')
                                    tc_func_args = tc.get('function', {}).get('arguments', '')

                                    if tc_func_name:
                                        if tool_call_chunks[target_idx]['function']['name']:
                                            tool_call_chunks[target_idx]['function']['name'] += tc_func_name
                                        else:
                                            tool_call_chunks[target_idx]['function']['name'] = tc_func_name
                                        tool_name = tool_call_chunks[target_idx]['function']['name']
                                        if target_idx not in reported_tool_indices and tool_name:
                                            reported_tool_indices.add(target_idx)
                                            yield {
                                                'type': 'tool_call',
                                                'tool': tool_name,
                                                'id': tool_call_chunks[target_idx]['id'],
                                            }
                                    if tc_func_args:
                                        tool_call_chunks[target_idx]['function']['arguments'] += tc_func_args

                            if chunk.usage:
                                iteration_usage['total_tokens'] = chunk.usage.get('total_tokens', 0)
                                iteration_usage['input_tokens'] = chunk.usage.get('prompt_tokens', 0)
                                iteration_usage['output_tokens'] = chunk.usage.get('completion_tokens', 0)

                        break
                    except Exception as stream_err:
                        from apps.sysai.agent.error_classifier import classify_api_error, should_retry_after_error
                        classification = classify_api_error(stream_err)
                        logger.warning(f'API流式调用异常: category={classification.category}, strategy={classification.strategy}, error={stream_err}')

                        if classification.category == 'context_overflow':
                            from apps.sysai.compressor.context_compressor import ContextCompressor
                            try:
                                messages = ContextCompressor.prune_tool_results(messages, 3000)
                                logger.info('上下文溢出，已压缩工具结果，准备重试')
                                yield {
                                    'type': 'warning',
                                    'content': classification.message,
                                }
                                api_retry_count += 1
                                continue
                            except Exception:
                                pass

                        retry_delay = should_retry_after_error(stream_err, api_retry_count, max_api_retries)
                        if retry_delay is not None:
                            logger.info(f'API错误可恢复，{retry_delay}秒后重试 (attempt={api_retry_count+1}/{max_api_retries})')
                            yield {
                                'type': 'warning',
                                'content': classification.message,
                            }
                            import time
                            time.sleep(retry_delay)
                            api_retry_count += 1
                            continue
                        else:
                            logger.error(f'API错误不可恢复: {classification.category}')
                            raise

                total_usage['total_tokens'] += iteration_usage['total_tokens']
                total_usage['input_tokens'] += iteration_usage['input_tokens']
                total_usage['output_tokens'] += iteration_usage['output_tokens']

                if hasattr(self.model, '_tool_fallback_warning') and self.model._tool_fallback_warning:
                    yield {
                        'type': 'warning',
                        'content': self.model._tool_fallback_warning,
                    }
                    self.model._tool_fallback_warning = None

                if last_finish_reason == 'length':
                    logger.warning(f'模型输出达到max_tokens限制被截断, content_len={len(current_response_content)}, tool_calls={len(tool_call_chunks)}')

                    if tool_call_chunks:
                        incomplete_indices = []
                        for idx in sorted(tool_call_chunks.keys()):
                            tc = tool_call_chunks[idx]
                            if not tc['function']['name'] and not tc['function']['arguments']:
                                incomplete_indices.append(idx)
                                logger.warning(f'删除空的截断工具调用: idx={idx}')
                                continue
                            if tc['function']['name'] and tc['function']['arguments']:
                                if repair_json(tc['function']['arguments']) is None:
                                    logger.warning(f'截断的工具调用参数JSON不完整: idx={idx}, tool={tc["function"]["name"]}, args={tc["function"]["arguments"][:200]}')
                                    incomplete_indices.append(idx)
                        for idx in incomplete_indices:
                            del tool_call_chunks[idx]

                    if not tool_call_chunks:
                        text_tool_calls = self._extract_text_tool_calls(current_response_content)
                        if text_tool_calls:
                            logger.info(f'从截断文本中提取到 {len(text_tool_calls)} 个工具调用')
                            for i, tc in enumerate(text_tool_calls):
                                tool_call_chunks[i] = tc
                                yield {
                                    'type': 'tool_call',
                                    'tool': tc['function']['name'],
                                    'id': tc['id'],
                                }
                            tool_name_in_text = text_tool_calls[0]['function']['name']
                            clean_patterns = [
                                r'(?:```json\s*\n?\s*)?\{[^}]*?"name"\s*:\s*"' + re.escape(tool_name_in_text) + r'".*?(?:```)?',
                                r'"name"\s*:\s*"' + re.escape(tool_name_in_text) + r'".*?"arguments"\s*:\s*\{[^}]*\}\s*\}?\s*}?',
                                r'"arguments"\s*:\s*\{[^}]*\}\s*\}?',
                            ]
                            clean_content = current_response_content
                            for cp in clean_patterns:
                                clean_content = re.sub(cp, '', clean_content, flags=re.DOTALL).strip()
                            clean_content = self._clean_tool_leakage_from_content(clean_content)
                            if clean_content:
                                current_response_content = clean_content
                                full_response_content = full_response_content[:full_response_content.rfind(current_response_content) + len(current_response_content)] if current_response_content in full_response_content else full_response_content

                    if not tool_call_chunks:
                        yield {
                            'type': 'length_limit',
                            'content': '模型输出已达到Token限制，回复可能不完整。',
                        }
                        yield {
                            'type': 'can_continue',
                            'content': '模型输出达到Token限制被截断，请输入"继续"获取完整回复。',
                        }
                        yield {
                            'type': 'stop',
                            'usage': total_usage,
                            'message_id': ai_msg_id,
                            'full_response': full_response_content,
                        }
                        break

                if not tool_call_chunks:
                    text_tool_calls = self._extract_text_tool_calls(current_response_content)
                    if text_tool_calls:
                        logger.info(f'从文本中提取到 {len(text_tool_calls)} 个工具调用，模型可能不支持function calling')
                        for i, tc in enumerate(text_tool_calls):
                            tool_call_chunks[i] = tc
                            yield {
                                'type': 'tool_call',
                                'tool': tc['function']['name'],
                                'id': tc['id'],
                            }
                        tool_name_in_text = text_tool_calls[0]['function']['name']
                        clean_patterns = [
                            r'(?:```json\s*\n?\s*)?\{[^}]*?"name"\s*:\s*"' + re.escape(tool_name_in_text) + r'".*?(?:```)?',
                            r'"name"\s*:\s*"' + re.escape(tool_name_in_text) + r'".*?"arguments"\s*:\s*\{[^}]*\}\s*\}?\s*}?',
                            r'"arguments"\s*:\s*\{[^}]*\}\s*\}?',
                        ]
                        clean_content = current_response_content
                        for cp in clean_patterns:
                            clean_content = re.sub(cp, '', clean_content, flags=re.DOTALL).strip()
                        clean_content = self._clean_tool_leakage_from_content(clean_content)
                        if clean_content:
                            current_response_content = clean_content
                            full_response_content = full_response_content[:full_response_content.rfind(current_response_content) + len(current_response_content)] if current_response_content in full_response_content else full_response_content
                    else:
                        if not current_response_content and current_reasoning_content and empty_response_retries < max_empty_response_retries:
                            empty_response_retries += 1
                            logger.warning(f'模型返回空内容但有思考过程(iteration={iteration_count}), 重试({empty_response_retries}/{max_empty_response_retries})')
                            messages.append({
                                'role': 'assistant',
                                'content': '',
                                'reasoning_content': current_reasoning_content,
                            })
                            messages.append({
                                'role': 'user',
                                'content': '请基于你的思考过程，直接给出最终回答。不要再次调用工具。',
                            })
                            current_response_content = ''
                            current_reasoning_content = ''
                            continue
                        if not current_response_content and current_reasoning_content:
                            logger.warning(f'模型返回空内容重试后仍为空(iteration={iteration_count}), 使用思考过程作为回复')
                            current_response_content = current_reasoning_content
                            full_response_content += current_response_content
                            yield {
                                'type': 'content',
                                'content': current_response_content,
                            }
                        yield {
                            'type': 'stop',
                            'usage': total_usage,
                            'message_id': ai_msg_id,
                        }
                        break

                assistant_tool_calls = []
                for idx in sorted(tool_call_chunks.keys()):
                    tc = tool_call_chunks[idx]
                    # 修复畸形的 tool_call arguments，确保发送给 API 的是合法 JSON
                    tc_args = tc['function']['arguments']
                    if tc_args:
                        repaired = repair_json(tc_args)
                        if repaired is not None:
                            tc_args = json.dumps(repaired, ensure_ascii=False)
                        else:
                            tc_args = '{}'
                    else:
                        tc_args = '{}'
                    assistant_tool_calls.append({
                        'id': tc['id'],
                        'type': 'function',
                        'function': {
                            'name': tc['function']['name'],
                            'arguments': tc_args,
                        },
                    })

                messages.append({
                    'role': 'assistant',
                    'content': current_response_content,
                    'tool_calls': assistant_tool_calls,
                    'reasoning_content': current_reasoning_content,
                })

                for tc in assistant_tool_calls:
                    func_name = tc['function']['name']
                    args_str = tc['function']['arguments']
                    call_id = tc['id']

                    logger.info(f'工具调用: {func_name}, args={args_str[:500] if args_str else "(empty)"}')

                    if not func_name:
                        logger.warning(f'工具调用缺少函数名, call_id={call_id}, 跳过执行')
                        messages.append({
                            'role': 'tool',
                            'tool_call_id': call_id,
                            'content': '错误：工具调用缺少函数名，无法执行。请跳过此工具，基于已有信息继续回答用户问题。',
                        })
                        consecutive_tool_failures += 1
                        if consecutive_tool_failures >= max_consecutive_failures:
                            yield {
                                'type': 'warning',
                                'content': '工具调用连续失败，已告知AI跳过失败工具',
                            }
                            messages.append({
                                'role': 'system',
                                'content': '系统提示：多个工具调用连续失败，请不要再尝试调用工具，直接基于已获取的信息为用户总结回答。如果信息不足，请如实告知用户。',
                            })
                            consecutive_tool_failures = 0
                        continue

                    arguments = repair_json(args_str)
                    if arguments is not None:
                        logger.info(f'工具 {func_name} 参数解析成功')
                    
                    if arguments is None and args_str:
                        messages.append({
                            'role': 'tool',
                            'tool_call_id': call_id,
                            'content': f'错误：工具 {func_name} 的参数JSON解析失败，原始参数: {args_str[:200]}。请检查参数格式后重新调用，使用正确的JSON格式。',
                        })
                        yield {
                            'type': 'tool_result',
                            'tool': func_name,
                            'result': f'参数JSON解析失败',
                            'id': call_id,
                        }
                        consecutive_tool_failures += 1
                        if consecutive_tool_failures >= max_consecutive_failures:
                            yield {
                                'type': 'warning',
                                'content': '工具调用连续失败，已告知AI跳过失败工具',
                            }
                            messages.append({
                                'role': 'system',
                                'content': '系统提示：多个工具调用连续失败，请不要再尝试调用工具，直接基于已获取的信息为用户总结回答。如果信息不足，请如实告知用户。',
                            })
                            consecutive_tool_failures = 0
                        continue

                    if func_name == 'request_user_input':
                        form_id = f"form_{call_id}"
                        form_title = arguments.get('title', '请填写以下信息')
                        form_fields = arguments.get('fields', [])
                        if isinstance(form_fields, str):
                            try:
                                form_fields = json.loads(form_fields)
                            except json.JSONDecodeError:
                                form_fields = []
                        yield {
                            'type': 'form_request',
                            'tool': func_name,
                            'id': call_id,
                            'form_id': form_id,
                            'title': form_title,
                            'fields': form_fields,
                        }
                        form_data = self._wait_for_form(form_id, timeout=1800)
                        if form_data is None:
                            messages.append({
                                'role': 'tool',
                                'tool_call_id': call_id,
                                'content': '用户取消了表单填写或等待超时。请基于已有信息继续回答，或告知用户需要这些信息才能继续。',
                            })
                            yield {
                                'type': 'tool_result',
                                'tool': func_name,
                                'result': '用户取消了表单填写',
                                'id': call_id,
                            }
                            continue
                        form_result = json.dumps(form_data, ensure_ascii=False)
                        messages.append({
                            'role': 'tool',
                            'tool_call_id': call_id,
                            'content': f'用户提交的表单数据:\n{form_result}',
                        })
                        yield {
                            'type': 'tool_result',
                            'tool': func_name,
                            'result': f'用户提交的表单数据:\n{form_result}',
                            'id': call_id,
                        }
                        continue

                    yield {
                        'type': 'tool_executing',
                        'tool': func_name,
                        'id': call_id,
                        'arguments': arguments,
                    }

                    guardrail_decision = self._guardrail.before_call(func_name, arguments)
                    if not guardrail_decision.allows_execution:
                        from apps.sysai.agent.tool_guardrails import append_guardrail_guidance
                        blocked_msg = guardrail_decision.message
                        logger.warning(f'工具护栏阻断: {func_name}, reason={guardrail_decision.code}, count={guardrail_decision.count}')
                        messages.append({
                            'role': 'tool',
                            'tool_call_id': call_id,
                            'content': blocked_msg,
                        })
                        yield {
                            'type': 'tool_result',
                            'tool': func_name,
                            'result': blocked_msg[:2000],
                            'id': call_id,
                        }
                        continue

                    # 保存before_call的warn决策，工具执行后附加到结果中
                    _before_warn_decision = guardrail_decision if guardrail_decision.action == 'warn' else None

                    need_confirm = False
                    tool_risk_level = 'low'
                    try:
                        from apps.sysai.tools.base import AIToolRegistry
                        registry = AIToolRegistry()
                        meta = registry.get_metadata(func_name)
                        if meta:
                            tool_risk_level = meta.get('risk_level', 'low')
                    except Exception:
                        pass

                    try:
                        from apps.sysai.models import AIToolConfig
                        tool_config = AIToolConfig.objects.filter(name=func_name).first()
                        if tool_config and tool_config.require_confirm:
                            need_confirm = True
                    except Exception:
                        pass

                    confirm_level = self.require_command_confirm
                    if isinstance(confirm_level, bool):
                        confirm_level = 'medium_high' if confirm_level else 'none'

                    if not need_confirm and confirm_level != 'none':
                        if confirm_level == 'high' and tool_risk_level in ('high', 'dangerous'):
                            need_confirm = True
                        elif confirm_level == 'medium_high' and tool_risk_level in ('medium', 'high', 'dangerous'):
                            need_confirm = True

                    if need_confirm:
                        # 检查"记住选择"缓存：同一会话内已记住批准的工具不再弹窗
                        if func_name in self._remembered_approvals:
                            if self._remembered_approvals[func_name]:
                                logger.info(f'工具 {func_name} 已记住批准，跳过确认')
                                need_confirm = False
                            else:
                                logger.info(f'工具 {func_name} 已记住拒绝，跳过执行')
                                messages.append({
                                    'role': 'tool',
                                    'tool_call_id': call_id,
                                    'content': '操作已被用户取消（记住选择）。请告知用户此操作未执行。',
                                })
                                yield {
                                    'type': 'tool_result',
                                    'tool': func_name,
                                    'result': '操作已被用户取消（记住选择）',
                                    'id': call_id,
                                }
                                continue

                    if need_confirm:
                        confirm_id = f"confirm_{func_name}::{call_id}"
                        _confirm_timeout = 600
                        _confirm_timeout_backend = _confirm_timeout + 60
                        yield {
                            'type': 'tool_confirm',
                            'tool': func_name,
                            'id': call_id,
                            'confirm_id': confirm_id,
                            'arguments': arguments,
                            'timeout': _confirm_timeout,
                        }
                        approved = self._wait_for_confirm(confirm_id, timeout=_confirm_timeout_backend)
                        if not approved:
                            logger.info(f'工具 {func_name} 被用户拒绝执行')
                            messages.append({
                                'role': 'tool',
                                'tool_call_id': call_id,
                                'content': '操作已被用户取消。请立即调用TodoWrite将当前正在执行的任务状态更新为pending或删除该任务，然后告知用户此操作未执行，并询问是否需要其他帮助。不要再尝试执行被取消的操作。',
                            })
                            yield {
                                'type': 'tool_result',
                                'tool': func_name,
                                'result': '操作已被用户取消',
                                'id': call_id,
                            }
                            continue

                    tool_result = self._execute_tool(func_name, arguments)

                    self._orchestrator.record_tool_call(func_name)
                    tool_result = self._orchestrator.post_process_tool_result(
                        func_name, arguments, tool_result,
                    )

                    tool_failed = '<toolcall_status>error</toolcall_status>' in tool_result
                    from apps.sysai.agent.tool_guardrails import append_guardrail_guidance
                    guardrail_after = self._guardrail.after_call(
                        func_name, arguments, tool_result, failed=tool_failed,
                    )
                    if guardrail_after.action in ('warn', 'halt', 'block'):
                        tool_result = append_guardrail_guidance(tool_result, guardrail_after)
                        if guardrail_after.action in ('halt', 'block'):
                            logger.warning(f'工具护栏终止: {func_name}, reason={guardrail_after.code}')

                    # 附加before_call的warn决策（如execute_command重定向提示）
                    if _before_warn_decision is not None:
                        tool_result = append_guardrail_guidance(tool_result, _before_warn_decision)

                    if tool_failed:
                        consecutive_tool_failures += 1
                        if consecutive_tool_failures >= max_consecutive_failures:
                            yield {
                                'type': 'warning',
                                'content': f'工具 {func_name} 连续执行失败{consecutive_tool_failures}次，已告知AI跳过',
                            }
                            tool_result += '\n\n系统提示：此工具连续执行失败，请不要再尝试调用此工具。请跳过此工具，基于已有信息继续回答用户问题，或如实告知用户该工具暂不可用。'
                            messages.append({
                                'role': 'system',
                                'content': f'系统提示：工具 {func_name} 连续执行失败，请不要再尝试调用此工具，直接基于已获取的信息为用户总结回答。如果信息不足，请如实告知用户。',
                            })
                            consecutive_tool_failures = 0
                    else:
                        consecutive_tool_failures = 0

                    context_result = tool_result
                    if len(tool_result) > 8000:
                        try:
                            from apps.sysai.tools.base import _smart_truncate
                            context_result = _smart_truncate(tool_result, 8000)
                        except Exception:
                            context_result = tool_result[:8000]

                    yield {
                        'type': 'tool_result',
                        'tool': func_name,
                        'result': tool_result,
                        'id': call_id,
                    }

                    messages.append({
                        'role': 'tool',
                        'tool_call_id': call_id,
                        'content': context_result,
                    })

                if self.is_stopped():
                    stop_r = self.get_stop_reason()
                    logger.info(f'Agent在工具执行后被停止: iteration={iteration_count}, stop_reason={stop_r}')
                    self._save_trajectory(messages, iteration_count, f'stopped_after_tool:{stop_r}')
                    yield {
                        'type': 'stop',
                        'content': '生成已停止',
                        'usage': total_usage,
                        'message_id': ai_msg_id,
                        'full_response': full_response_content,
                    }
                    return

            if iteration_count >= self.max_tool_iterations:
                self._stop_flag = True
                self._save_trajectory(messages, iteration_count, 'max_iterations')
                yield {
                    'type': 'can_continue',
                    'content': f'模型工具调用轮次已达上限（{iteration_count}/{self.max_tool_iterations}），点击"继续生成"可继续执行。',
                }
                yield {
                    'type': 'stop',
                    'usage': total_usage,
                    'message_id': ai_msg_id,
                    'full_response': full_response_content,
                }

        except Exception as e:
            logger.error(f'Agent chat error: {e}', exc_info=True)
            try:
                self._save_trajectory(messages, iteration_count, f'error_{type(e).__name__}')
            except Exception:
                pass
            yield {
                'type': 'error',
                'content': f'对话出错: {str(e)}',
            }
        finally:
            pass
