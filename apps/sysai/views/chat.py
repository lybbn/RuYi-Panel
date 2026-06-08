import json
import logging
import os
import queue
import threading
import time
from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, ErrorResponse, DetailResponse
from utils.common import get_parameter_dic
from apps.sysai.models import AIModel, AIChatSession, AIChatMessage, AIToolConfig, AIUsageLog
from apps.sysai.serializers.chat import (
    AIChatSessionSerializer, AIChatMessageSerializer,
    ChatRequestSerializer, ChatStopSerializer,
    AIModelSerializer, AIModelListSerializer, AIToolConfigSerializer
)
from apps.sysai.provider.tools import get_model_from_db
from apps.sysai.tools.base import registry as tool_registry
from apps.sysai.agent.core import Agent
from apps.sysai.agent.specialized import get_agent_class, get_all_agents

_SENTINEL = object()

logger = logging.getLogger(__name__)


def _get_tool_type(tool_name: str) -> str:
    if not tool_name:
        return 'tool'
    if tool_name == 'Skills':
        return 'skill'
    if tool_name == 'web_search':
        return 'web_search'
    if tool_name == 'agent_call':
        return 'agent'
    if tool_name.startswith('mcp_'):
        return 'mcp'
    if tool_name in ('TodoWrite', 'TodoRead'):
        return 'todo'
    if tool_name == 'search_docs':
        return 'docs'
    if tool_name == 'execute_command':
        return 'command'
    if tool_name.startswith('panel_'):
        return 'panel'
    return 'tool'


def _mark_tool_blocks_error(blocks):
    for blk in blocks:
        if blk.get('type') == 'tool' and blk.get('status') in ('calling', 'executing', 'confirming'):
            blk['status'] = 'error'
            blk['result'] = blk.get('result', '') or '工具执行出错'


_agents = {}
_agents_lock = threading.Lock()
_agents_last_access = {}
_AGENT_IDLE_TIMEOUT = 3600

def _cleanup_idle_agents():
    now = time.time()
    with _agents_lock:
        expired = [sid for sid, ts in _agents_last_access.items() if now - ts > _AGENT_IDLE_TIMEOUT]
        for sid in expired:
            agent = _agents.pop(sid, None)
            if agent:
                try:
                    agent.stop(reason='idle_timeout')
                except Exception:
                    pass
            _agents_last_access.pop(sid, None)
        if expired:
            logger.info(f'[AI] 自动清理 {len(expired)} 个空闲Agent')


def _start_async_routing(agent, user_input, ai_model, all_tool_names, disabled_tool_names):
    from apps.sysai.agent.toolsets import ai_match_toolsets, _is_panel_general_question

    def _route():
        try:
            result = ai_match_toolsets(user_input, ai_model=ai_model)
            if result is not None:
                agent._pending_ai_route = result
                ts = result.get('toolsets', [])
                logger.info(f'[AI路由-异步] 结果已缓存, Toolset={ts}, 下轮生效')
            else:
                # 检测通用面板问题，确保文档工具可用
                if _is_panel_general_question(user_input):
                    agent._pending_ai_route = {'toolsets': [], 'need_task': False, 'need_doc': True}
                    logger.info(f'[AI路由-异步] 检测到通用面板问题, 强制加载文档工具')
                else:
                    agent._pending_ai_route = None
        except Exception as e:
            logger.warning(f'[AI路由-异步] 失败: {e}')
            agent._pending_ai_route = None

    t = threading.Thread(target=_route, daemon=True)
    t.start()


def _get_or_create_agent(session_id, model, config=None, user_input='', agent_id=None):
    if len(_agents) > 50:
        _cleanup_idle_agents()
    agent_config = config or {}
    resolve_input = agent_config.pop('_original_user_input', None) or user_input
    with _agents_lock:
        if session_id in _agents:
            agent = _agents[session_id]
            agent.reset_stop()
            _agents_last_access[session_id] = time.time()

            agent_config = config or {}

            agent.require_command_confirm = agent_config.get('require_command_confirm', 'medium_high')
            agent.max_tool_iterations = agent_config.get('max_tool_iterations', 20)
            agent.max_context_messages = agent_config.get('max_context_messages', 30)
            agent.web_search = agent_config.get('web_search', False)
            agent.enable_memory = agent_config.get('enable_memory', False)
            agent.memory_recall_threshold = agent_config.get('memory_recall_threshold', 10)

            smart_mode = agent_config.get('smart_mode', False)
            manual_enabled_tools = agent_config.get('enabled_tools', [])

            if smart_mode and not manual_enabled_tools:
                from apps.sysai.agent.toolsets import match_toolsets_by_keywords, resolve_tools_by_toolsets, get_minimal_tools, ai_match_toolsets, TASK_TOOLS, DOC_TOOLS
                from apps.sysai.models import AIToolConfig
                disabled_tool_names = set(AIToolConfig.objects.filter(is_enabled=False).values_list('name', flat=True))
                all_tool_names = list(tool_registry._tools.keys())

                pending = getattr(agent, '_pending_ai_route', None)
                if pending is not None:
                    ts_names = pending['toolsets']
                    need_task = pending.get('need_task', False)
                    need_doc = pending.get('need_doc', False)
                    smart_tools = resolve_tools_by_toolsets(ts_names) if ts_names else list(get_minimal_tools())
                    if need_task:
                        smart_tools.extend(t for t in TASK_TOOLS if t not in smart_tools)
                    if need_doc:
                        smart_tools.extend(t for t in DOC_TOOLS if t not in smart_tools)
                    agent.enabled_tools = [
                        t for t in smart_tools
                        if t in all_tool_names and t not in disabled_tool_names
                    ]
                    logger.info(f'[Agent重用] AI路由生效: Toolset={ts_names}, task={need_task}, doc={need_doc}, 加载{len(agent.enabled_tools)}个工具')
                    agent._pending_ai_route = None

                ai_model = agent.model if hasattr(agent, 'model') else None
                _start_async_routing(agent, resolve_input, ai_model, all_tool_names, disabled_tool_names)

            elif not smart_mode and not manual_enabled_tools:
                from apps.sysai.models import AIToolConfig
                disabled_tool_names = set(AIToolConfig.objects.filter(is_enabled=False).values_list('name', flat=True))
                all_tool_names = list(tool_registry._tools.keys())

                if 'enabled_tools' in agent_config:
                    agent.enabled_tools = [
                        t for t in agent_config['enabled_tools']
                        if t in all_tool_names and t not in disabled_tool_names
                    ]
                    logger.info(f'[Agent重用] 手动模式(无工具选择): smart_mode=False, enabled_tools={agent_config["enabled_tools"]}, 最终{len(agent.enabled_tools)}个工具')
                else:
                    from apps.sysai.agent.intent_router import resolve_tools
                    logger.info(f'[Agent重用] session={session_id}, agent_id={agent_id}, user_input={resolve_input[:80]}')
                    resolved_tools, _ = resolve_tools(
                        user_input=resolve_input,
                        agent_id=agent_id,
                        smart_mode=False,
                        ai_model=agent.model if hasattr(agent, 'model') else None,
                    )
                    if resolved_tools is not None:
                        before_filter = len(resolved_tools)
                        agent.enabled_tools = [
                            t for t in resolved_tools
                            if t in all_tool_names and t not in disabled_tool_names
                        ]
                        filtered_out = [t for t in resolved_tools if t in disabled_tool_names]
                        if filtered_out:
                            logger.warning(f'[Agent重用] 被disabled_tool_names过滤的工具: {filtered_out}')
                        logger.info(f'[Agent重用] 工具解析完成: 解析{before_filter}个, 过滤{len(filtered_out)}个, 最终{len(agent.enabled_tools)}个, require_confirm={agent.require_command_confirm}')
                    else:
                        agent.enabled_tools = [
                            t for t in all_tool_names if t not in disabled_tool_names
                        ]
                        logger.info(f'[Agent重用] 全量工具模式: {len(agent.enabled_tools)}个工具, require_confirm={agent.require_command_confirm}')

            elif not smart_mode and manual_enabled_tools:
                from apps.sysai.models import AIToolConfig
                disabled_tool_names = set(AIToolConfig.objects.filter(is_enabled=False).values_list('name', flat=True))
                all_tool_names = list(tool_registry._tools.keys())
                agent.enabled_tools = [
                    t for t in manual_enabled_tools
                    if t in all_tool_names and t not in disabled_tool_names
                ]
                logger.info(f'[Agent重用] 手动指定工具模式: smart_mode=False, 加载{len(agent.enabled_tools)}个工具')

            return agent

        ai_model = get_model_from_db(model)
        agent_config = config or {}

        from apps.sysai.models import AIToolConfig
        disabled_tool_names = set(AIToolConfig.objects.filter(is_enabled=False).values_list('name', flat=True))
        all_tool_names = list(tool_registry._tools.keys())

        smart_mode = agent_config.get('smart_mode', False)
        manual_enabled_tools = agent_config.get('enabled_tools', [])

        logger.info(f'[Agent新建] session={session_id}, smart_mode={smart_mode}, agent_id={agent_id}, user_input={resolve_input[:80]}')

        if smart_mode or manual_enabled_tools:
            if manual_enabled_tools:
                agent_config['enabled_tools'] = [
                    t for t in manual_enabled_tools
                    if t in all_tool_names and t not in disabled_tool_names
                ]
                logger.info(f'[Agent新建] 手动指定工具模式: {len(agent_config["enabled_tools"])}个工具')
            else:
                from apps.sysai.agent.toolsets import match_toolsets_by_keywords, resolve_tools_by_toolsets, get_minimal_tools
                ts_names = match_toolsets_by_keywords(resolve_input)
                if ts_names:
                    smart_tools = resolve_tools_by_toolsets(ts_names)
                    agent_config['enabled_tools'] = [
                        t for t in smart_tools
                        if t in all_tool_names and t not in disabled_tool_names
                    ]
                    logger.info(f'[Agent新建] 智能模式(关键词): 匹配Toolset {ts_names}, 加载{len(agent_config["enabled_tools"])}个工具')
                else:
                    agent_config['enabled_tools'] = [
                        t for t in get_minimal_tools()
                        if t in all_tool_names and t not in disabled_tool_names
                    ]
                    logger.info(f'[Agent新建] 智能模式(最小): 无匹配Toolset, 仅加载{len(agent_config["enabled_tools"])}个基础工具')
        else:
            if 'enabled_tools' in agent_config:
                agent_config['enabled_tools'] = [
                    t for t in agent_config['enabled_tools']
                    if t in all_tool_names and t not in disabled_tool_names
                ]
                logger.info(f'[Agent新建] 手动模式(无工具选择): smart_mode=False, enabled_tools={agent_config["enabled_tools"]}, 最终{len(agent_config["enabled_tools"])}个工具')
            else:
                from apps.sysai.agent.intent_router import resolve_tools
                resolved_tools, system_prompt_override = resolve_tools(
                    user_input=resolve_input,
                    agent_id=agent_id,
                    smart_mode=False,
                    ai_model=ai_model,
                )
                if resolved_tools is not None:
                    before_filter = len(resolved_tools)
                    agent_config['enabled_tools'] = [
                        t for t in resolved_tools
                        if t in all_tool_names and t not in disabled_tool_names
                    ]
                    filtered_out = [t for t in resolved_tools if t in disabled_tool_names]
                    if filtered_out:
                        logger.warning(f'[Agent新建] 被disabled_tool_names过滤的工具: {filtered_out}')
                    logger.info(f'[Agent新建] 关键词匹配模式: 解析{before_filter}个, 过滤{len(filtered_out)}个, 最终{len(agent_config["enabled_tools"])}个')
                else:
                    agent_config['enabled_tools'] = [
                        t for t in all_tool_names if t not in disabled_tool_names
                    ]
                    logger.info(f'[Agent新建] 关键词匹配返回None, 全量模式: {len(agent_config["enabled_tools"])}个工具')
                if system_prompt_override:
                    agent_config['system_prompt'] = system_prompt_override

        agent = Agent(
            session_id=str(session_id),
            model=ai_model,
            config=agent_config,
            tool_registry=tool_registry,
        )
        _agents[session_id] = agent
        _agents_last_access[session_id] = time.time()

        if smart_mode and not manual_enabled_tools:
            _start_async_routing(agent, resolve_input, ai_model, all_tool_names, disabled_tool_names)

        return agent


def _stop_agent(session_id, reason='user'):
    with _agents_lock:
        if session_id in _agents:
            _agents[session_id].stop(reason=reason)


def _cleanup_agent(session_id):
    import shutil
    with _agents_lock:
        _agents.pop(session_id, None)
        _agents_last_access.pop(session_id, None)

    try:
        from apps.sysai.agent.agent_orchestrator import cleanup_orchestrator
        cleanup_orchestrator(session_id)
    except Exception:
        pass

    _base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data', 'agent')
    for subdir in ('sessions', 'trajectories'):
        target = os.path.join(_base, subdir, session_id)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    import re
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', text))
    other_chars = len(text) - chinese_chars
    tokens = chinese_chars * 1.7 + other_chars / 4.0
    return max(1, int(tokens))


class AIChatSessionViewSet(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        show_archived = request.query_params.get('show_archived', 'false').lower() == 'true'
        if show_archived:
            sessions = AIChatSession.objects.filter(
                user_id=request.user.id, is_archived=True
            ).order_by('-update_at')
        else:
            sessions = AIChatSession.objects.filter(
                user_id=request.user.id, is_archived=False
            ).order_by('-is_pinned', '-update_at')
        serializer = AIChatSessionSerializer(sessions, many=True)
        return SuccessResponse(data=serializer.data, total=sessions.count())

    def post(self, request):
        req_data = get_parameter_dic(request)
        title = req_data.get('title', '新对话')
        model_id = req_data.get('model_id')

        model = None
        if model_id:
            model = AIModel.objects.filter(id=model_id, is_enabled=True).first()
        if not model:
            model = AIModel.objects.filter(is_enabled=True, is_default=True).first()
        if not model:
            model = AIModel.objects.filter(is_enabled=True).first()

        session = AIChatSession.objects.create(
            title=title, model=model, user_id=request.user.id
        )
        serializer = AIChatSessionSerializer(session)
        return DetailResponse(data=serializer.data, msg='会话创建成功')

    def put(self, request):
        req_data = get_parameter_dic(request)
        session_id = req_data.get('session_id')
        if not session_id:
            return ErrorResponse(msg='缺少会话ID')

        session = AIChatSession.objects.filter(id=session_id, user_id=request.user.id).first()
        if not session:
            return ErrorResponse(msg='会话不存在')

        if 'title' in req_data:
            session.title = req_data['title']
        if 'is_pinned' in req_data:
            session.is_pinned = req_data['is_pinned']
        if 'is_archived' in req_data:
            session.is_archived = req_data['is_archived']
        if 'model_id' in req_data:
            model = AIModel.objects.filter(id=req_data['model_id']).first()
            if model:
                session.model = model
        session.save()
        serializer = AIChatSessionSerializer(session)
        return DetailResponse(data=serializer.data, msg='更新成功')

    def delete(self, request):
        req_data = get_parameter_dic(request)
        clear_all = req_data.get('clear_all')
        if clear_all:
            sessions = AIChatSession.objects.filter(user_id=request.user.id)
            for s in sessions:
                _cleanup_agent(str(s.id))
            sessions.delete()
            return DetailResponse(msg='清空成功')

        session_id = req_data.get('session_id')
        if not session_id:
            return ErrorResponse(msg='缺少会话ID')

        session = AIChatSession.objects.filter(id=session_id, user_id=request.user.id).first()
        if not session:
            return ErrorResponse(msg='会话不存在')

        _cleanup_agent(str(session_id))
        session.delete()
        return DetailResponse(msg='删除成功')


class AIChatMessageViewSet(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        req_data = get_parameter_dic(request)
        session_id = req_data.get('session_id')
        if not session_id:
            return ErrorResponse(msg='缺少会话ID')

        session = AIChatSession.objects.filter(id=session_id, user_id=request.user.id).first()
        if not session:
            return ErrorResponse(msg='会话不存在')

        messages = AIChatMessage.objects.filter(session=session).exclude(role='tool').order_by('create_at')
        total_count = messages.count()

        limit = int(req_data.get('limit', 0))
        offset = int(req_data.get('offset', 0))
        before_id = req_data.get('before', '')

        if before_id and limit > 0:
            before_msg = AIChatMessage.objects.filter(id=before_id, session=session).first()
            if before_msg:
                older_messages = AIChatMessage.objects.filter(
                    session=session, create_at__lt=before_msg.create_at
                ).exclude(role='tool').order_by('-create_at')[:limit]
                messages = list(reversed(older_messages))
            else:
                messages = []
        elif limit > 0:
            if offset > 0:
                messages = messages[offset:offset + limit]
            else:
                start = max(0, total_count - limit)
                messages = messages[start:]

        data = []
        for msg in messages:
            item = {
                'id': str(msg.id),
                'role': msg.role,
                'content': msg.content,
                'reasoning_content': msg.reasoning_content,
                'tool_calls': msg.tool_calls,
                'tool_call_id': msg.tool_call_id,
                'tool_name': msg.tool_name,
                'is_stop': msg.is_stop,
                'stop_reason': msg.stop_reason,
                'is_error': msg.is_error,
                'metadata': msg.metadata,
                'create_at': msg.create_at.isoformat() if msg.create_at else '',
            }
            if msg.role == 'user':
                item['problem_text'] = msg.content
                item['answer_text'] = ''
            elif msg.role == 'assistant':
                item['problem_text'] = ''
                item['answer_text'] = msg.content
            data.append(item)

        return SuccessResponse(data=data, total=total_count, limit=limit or total_count)

    def delete(self, request):
        req_data = get_parameter_dic(request)
        message_id = req_data.get('message_id') or req_data.get('id')
        if not message_id:
            return ErrorResponse(msg='缺少消息ID')

        msg = AIChatMessage.objects.filter(id=message_id).first()
        if not msg:
            return ErrorResponse(msg='消息不存在')

        session = msg.session
        if session.user_id != request.user.id:
            return ErrorResponse(msg='无权操作此消息')

        ids_to_delete = [msg.id]

        if msg.role == 'user':
            next_msg = AIChatMessage.objects.filter(
                session=session, create_at__gt=msg.create_at
            ).order_by('create_at').first()
            if next_msg and next_msg.role in ('assistant', 'tool'):
                ids_to_delete.append(next_msg.id)
                if next_msg.role == 'assistant':
                    tool_msgs = AIChatMessage.objects.filter(
                        session=session, role='tool',
                        create_at__gt=msg.create_at, create_at__lt=next_msg.create_at
                    )
                    ids_to_delete.extend([tm.id for tm in tool_msgs])
        elif msg.role == 'assistant':
            tool_msgs = AIChatMessage.objects.filter(
                session=session, role='tool', tool_call_id__in=[
                    tc.get('id', '') for tc in (msg.tool_calls or [])
                    if isinstance(tc, dict)
                ]
            )
            ids_to_delete.extend([tm.id for tm in tool_msgs])
            prev_msg = AIChatMessage.objects.filter(
                session=session, create_at__lt=msg.create_at
            ).order_by('-create_at').first()
            if prev_msg and prev_msg.role == 'user':
                ids_to_delete.append(prev_msg.id)

        AIChatMessage.objects.filter(id__in=ids_to_delete).delete()

        session.message_count = AIChatMessage.objects.filter(session=session).count()
        session.save()

        return DetailResponse(msg='消息删除成功')


class AIChatStreamView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        serializer = ChatRequestSerializer(data=req_data)
        if not serializer.is_valid():
            return ErrorResponse(msg=str(serializer.errors))

        message = serializer.validated_data['message']
        session_id = serializer.validated_data.get('session_id')
        model_id = serializer.validated_data.get('model_id')
        agent_id = serializer.validated_data.get('agent_id')
        stream = serializer.validated_data.get('stream', True)
        re_chat = serializer.validated_data.get('re_chat', False)
        continue_chat = serializer.validated_data.get('continue_chat', False)
        chat_record_id = serializer.validated_data.get('chat_record_id')
        enabled_tools = serializer.validated_data.get('enabled_tools')
        web_search = serializer.validated_data.get('web_search', False)
        smart_mode = serializer.validated_data.get('smart_mode', False)
        attachments = serializer.validated_data.get('attachments')

        if not agent_id:
            import re
            mention_match = re.match(r'@(\S+)\s+', message)
            if mention_match:
                mentioned_name = mention_match.group(1)
                try:
                    from apps.sysai.agent.specialized import AGENT_REGISTRY
                    if mentioned_name in AGENT_REGISTRY:
                        agent_id = mentioned_name
                        message = message[mention_match.end():]
                        logger.info(f'[@智能体] 识别到@{mentioned_name}, 路由到智能体')
                except Exception:
                    pass
                if not agent_id:
                    try:
                        from apps.sysai.agent.skill_agent_manager import skill_agent_manager
                        skill_agent = skill_agent_manager.get(mentioned_name)
                        if skill_agent:
                            agent_id = mentioned_name
                            message = message[mention_match.end():]
                            logger.info(f'[@智能体] 识别到@{mentioned_name}(Skill), 路由到智能体')
                    except Exception:
                        pass

        session = None
        model = None
        is_new_session = False

        if session_id:
            session = AIChatSession.objects.filter(id=session_id, user_id=request.user.id).first()
            if session and session.model:
                model = session.model

        if not model and model_id:
            model = AIModel.objects.filter(id=model_id, is_enabled=True).first()
        if not model:
            model = AIModel.objects.filter(is_enabled=True, is_default=True).first()
        if not model:
            model = AIModel.objects.filter(is_enabled=True).first()
        if not model:
            return ErrorResponse(msg='没有可用的AI模型，请先在设置中配置模型')

        if not session:
            title = message[:30] + ('...' if len(message) > 30 else '')
            session_kwargs = dict(title=title, model=model, user_id=request.user.id)
            if agent_id:
                agent_cls = get_agent_class(agent_id)
                if agent_cls:
                    session_kwargs['title'] = agent_cls.title
                    session_kwargs['agent_id'] = agent_id
            session = AIChatSession.objects.create(**session_kwargs)
            session_id = session.id
            is_new_session = True

        if re_chat and chat_record_id:
            AIChatMessage.objects.filter(
                session=session, id=chat_record_id
            ).delete()

        if continue_chat:
            stopped_msg = None
            if chat_record_id:
                stopped_msg = AIChatMessage.objects.filter(
                    session=session, id=chat_record_id
                ).first()
            if not stopped_msg:
                stopped_msg = AIChatMessage.objects.filter(
                    session=session, role='assistant', is_stop=True
                ).order_by('-create_at').first()
            if stopped_msg:
                stopped_msg_create_at = stopped_msg.create_at
                stopped_msg.is_stop = False
                stopped_msg.stop_reason = ''
                stopped_msg.save()
            else:
                stopped_msg_create_at = None

        original_user_message = None
        if continue_chat and stopped_msg_create_at:
            prev_user_msg = AIChatMessage.objects.filter(
                session=session, role='user', create_at__lt=stopped_msg_create_at
            ).order_by('-create_at').first()
            if prev_user_msg:
                original_user_message = prev_user_msg.content

        if continue_chat:
            user_msg = AIChatMessage.objects.create(
                session=session, role='user', content=message, metadata={'is_continue': True}
            )
        else:
            user_msg = AIChatMessage.objects.create(
                session=session, role='user', content=message
            )

        agent_config = {}
        try:
            from apps.sysai.models import AIModel
            sys_config = AIModel.objects_all.filter(name='__sys_config__').first()
            if sys_config and sys_config.extra_params:
                global_cfg = sys_config.extra_params
                agent_config['max_tool_iterations'] = global_cfg.get('max_turns', 100)
                agent_config['require_command_confirm'] = global_cfg.get('require_command_confirm', 'medium_high')
                agent_config['max_context_messages'] = global_cfg.get('max_context_messages', 30)
                agent_config['web_search'] = global_cfg.get('enable_web_search', False)
            else:
                agent_config['max_tool_iterations'] = 20
                agent_config['require_command_confirm'] = 'medium_high'
                agent_config['max_context_messages'] = 30
                agent_config['web_search'] = False
        except Exception:
            agent_config['max_tool_iterations'] = 20
            agent_config['require_command_confirm'] = 'medium_high'
            agent_config['max_context_messages'] = 30
            agent_config['web_search'] = False

        if smart_mode:
            agent_config['smart_mode'] = True
            agent_config['web_search'] = True
        else:
            agent_config['smart_mode'] = False
            if enabled_tools is not None:
                agent_config['enabled_tools'] = enabled_tools
            if web_search:
                agent_config['web_search'] = True

        if agent_id:
            agent_cls = get_agent_class(agent_id)
            if agent_cls and agent_cls.system_prompt:
                agent_config['system_prompt'] = agent_cls.system_prompt
            try:
                from apps.sysai.agent.skill_agent_manager import skill_agent_manager
                skill_agent = skill_agent_manager.get(agent_id)
                if skill_agent and skill_agent.system_prompt:
                    existing = agent_config.get('system_prompt', '')
                    if existing:
                        agent_config['system_prompt'] = existing + '\n\n' + skill_agent.system_prompt
                    else:
                        agent_config['system_prompt'] = skill_agent.system_prompt
            except Exception:
                pass
        if attachments:
            message = self._process_attachments(message, attachments)

        if original_user_message:
            agent_config['_original_user_input'] = original_user_message

        if stream:
            sync_gen = self._stream_chat_with_agent(session, model, message, agent_config=agent_config, is_new_session=is_new_session)

            async def _async_wrapper():
                def _safe_next(gen):
                    try:
                        return next(gen)
                    except StopIteration:
                        return _SENTINEL

                while True:
                    chunk = await sync_to_async(_safe_next)(sync_gen)
                    if chunk is _SENTINEL:
                        break
                    yield chunk

            response = StreamingHttpResponse(
                _async_wrapper(),
                content_type='text/event-stream; charset=utf-8'
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            response['X-Session-Id'] = str(session_id)
            return response
        else:
            result = self._sync_chat_with_agent(session, model, message, agent_config=agent_config)
            return DetailResponse(data=result)

    def _get_history(self, session):
        MAX_HISTORY_MESSAGES = 100
        messages = AIChatMessage.objects.filter(session=session).order_by('-create_at')[:MAX_HISTORY_MESSAGES]
        messages = reversed(list(messages))
        history = []
        for msg in messages:
            item = {'id': str(msg.id), 'role': msg.role, 'content': msg.content}
            if msg.tool_calls:
                item['tool_calls'] = msg.tool_calls
            if msg.tool_call_id:
                item['tool_call_id'] = msg.tool_call_id
            if msg.tool_name:
                item['name'] = msg.tool_name
            if msg.reasoning_content:
                item['reasoning_content'] = msg.reasoning_content
            history.append(item)
        return history

    def _get_sysai_config(self):
        try:
            config_obj = AIModel.objects_all.filter(name='__sys_config__').first()
            if config_obj and config_obj.extra_params:
                return config_obj.extra_params
        except Exception:
            pass
        return {}

    BINARY_EXTENSIONS = {
        '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
        '.exe', '.dll', '.so', '.o', '.a', '.bin',
        '.pyc', '.pyo',
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.tiff', '.webp', '.svg',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.mp3', '.mp4', '.avi', '.mov', '.mkv', '.flv',
        '.woff', '.woff2', '.eot', '.ttf',
        '.db', '.sqlite', '.sqlite3',
    }

    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

    MAX_FILE_READ_SIZE = 256 * 1024
    MAX_DIR_ENTRIES = 100

    def _process_attachments(self, message: str, attachments: list) -> str:
        from apps.sysai.agent.file_safety import is_read_denied

        context_parts = []

        for att in attachments:
            if not isinstance(att, dict):
                context_parts.append(f'[附件] {att}')
                continue

            att_type = att.get('type', 'file')
            att_name = att.get('name', '')
            att_path = att.get('path', '')
            att_size = att.get('size', 0)

            if att_type == 'server' and att_path:
                if not os.path.exists(att_path):
                    context_parts.append(f'[服务器文件] {att_name} (路径: {att_path}) - 错误: 路径不存在')
                    continue

                denied = is_read_denied(att_path)
                if denied:
                    context_parts.append(f'[服务器文件] {att_name} (路径: {att_path}) - {denied}')
                    continue

                if os.path.isdir(att_path):
                    dir_info = self._read_directory_info(att_path)
                    context_parts.append(
                        f'[服务器目录] {att_name} (路径: {att_path})\n'
                        f'已自动读取目录内容:\n{dir_info}'
                    )
                elif os.path.isfile(att_path):
                    file_info = self._read_file_content(att_path, att_name)
                    context_parts.append(file_info)
                else:
                    context_parts.append(f'[服务器文件] {att_name} (路径: {att_path}) - 错误: 路径类型未知')

            elif att_type == 'folder' and att_path:
                if os.path.exists(att_path) and os.path.isdir(att_path):
                    dir_info = self._read_directory_info(att_path)
                    context_parts.append(
                        f'[目录] {att_name} (路径: {att_path})\n'
                        f'已自动读取目录内容:\n{dir_info}'
                    )
                else:
                    context_parts.append(f'[目录] {att_name} (路径: {att_path}, 大小: {att_size}字节)')

            elif att_type == 'file' and att_path:
                if os.path.exists(att_path) and os.path.isfile(att_path):
                    denied = is_read_denied(att_path)
                    if denied:
                        context_parts.append(f'[文件] {att_name} (路径: {att_path}) - {denied}')
                    else:
                        file_info = self._read_file_content(att_path, att_name)
                        context_parts.append(file_info)
                else:
                    context_parts.append(f'[文件] {att_name} (路径: {att_path}, 大小: {att_size}字节)')

            else:
                size_str = f', 大小: {att_size}字节' if att_size else ''
                path_str = f', 路径: {att_path}' if att_path else ''
                context_parts.append(f'[附件] {att_name}{path_str}{size_str}')

        if context_parts:
            return message + '\n\n' + '\n\n'.join(context_parts)
        return message

    def _read_directory_info(self, dir_path: str) -> str:
        try:
            entries = []
            for entry in os.scandir(dir_path):
                if len(entries) >= self.MAX_DIR_ENTRIES:
                    entries.append('... (目录内容过多，已截断)')
                    break
                try:
                    is_dir = entry.is_dir()
                    stat_info = entry.stat()
                    size_str = '' if is_dir else f' ({self._format_size(stat_info.st_size)})'
                    entries.append(f'{"📁" if is_dir else "📄"} {entry.name}{size_str}')
                except (PermissionError, OSError):
                    entries.append(f'🔒 {entry.name} (权限不足)')
            entries.sort(key=lambda x: (not x.startswith('📁'), x))
            return '\n'.join(entries)
        except PermissionError:
            return f'权限不足，无法访问: {dir_path}'
        except Exception as e:
            return f'读取目录失败: {str(e)}'

    def _read_file_content(self, file_path: str, file_name: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()

        if ext in self.BINARY_EXTENSIONS:
            if ext in self.IMAGE_EXTENSIONS:
                return f'[文件] {file_name} (路径: {file_path}) - 图片文件，AI可通过工具查看'
            return f'[文件] {file_name} (路径: {file_path}) - 二进制文件，无法直接读取文本内容'

        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.MAX_FILE_READ_SIZE:
                return (
                    f'[文件] {file_name} (路径: {file_path}, 大小: {self._format_size(file_size)})\n'
                    f'文件较大，已自动读取前部分内容:\n'
                    f'--- 文件开始 ---\n'
                    f'(文件超过256KB，请使用 read_file 工具分段读取)\n'
                    f'--- 文件结束 ---'
                )

            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            if len(content) > 20000:
                content = content[:20000] + '\n... (内容已截断)'

            return (
                f'[文件] {file_name} (路径: {file_path})\n'
                f'已自动读取文件内容:\n'
                f'--- 文件开始 ---\n'
                f'{content}\n'
                f'--- 文件结束 ---'
            )
        except PermissionError:
            return f'[文件] {file_name} (路径: {file_path}) - 权限不足，无法读取'
        except Exception as e:
            return f'[文件] {file_name} (路径: {file_path}) - 读取失败: {str(e)}'

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f'{size_bytes:.1f} {unit}'
            size_bytes /= 1024
        return f'{size_bytes:.1f} PB'

    def _stream_chat_with_agent(self, session, model, message, agent_config=None, is_new_session=False):
        agent_id = getattr(session, 'agent_id', None) or ''
        agent = _get_or_create_agent(str(session.id), model, config=agent_config, user_input=message, agent_id=agent_id)
        history = self._get_history(session)
        history = history[:-1]

        compact_result = None
        sys_config = self._get_sysai_config()
        from apps.sysai.compressor import ContextCompressor
        compressor = ContextCompressor(sys_config)
        if compressor.should_compress(history):
            try:
                from apps.sysai.provider.tools import get_model_from_db
                llm_model = get_model_from_db(model)
                compact_result = compressor.compress(session, history, llm_model)
                if compact_result.get('compacted'):
                    history = self._get_history(session)
                    history = history[:-1]
            except Exception as e:
                logger.error(f'自动压缩失败: {e}', exc_info=True)

        full_content = ''
        full_reasoning = ''
        assistant_msg = None
        total_usage = {'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0}
        tool_calls_collected = []
        blocks = []
        current_content_block = None
        current_thinking_block = None

        if compact_result and compact_result.get('compacted'):
            compact_info = {
                'type': 'compact',
                'content': '对话上下文已自动压缩，关键信息已保留',
                'compacted_count': compact_result.get('compacted_count', 0),
                'flushed': compact_result.get('flushed', 0),
            }
        else:
            compact_info = None

        tool_executing = False
        tool_confirming = False
        current_tool_name = ''
        current_tool_call_id = ''
        current_confirm_id = ''
        last_status_time = time.time()
        is_compacted = False

        def ensure_assistant_msg():
            nonlocal assistant_msg
            metadata = {'blocks': list(blocks)}
            if is_compacted:
                metadata['compacted'] = True
            if not assistant_msg:
                assistant_msg = AIChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=full_content,
                    reasoning_content=full_reasoning,
                    tool_calls=list(tool_calls_collected),
                    metadata=metadata,
                )
            else:
                assistant_msg.content = full_content
                assistant_msg.reasoning_content = full_reasoning
                assistant_msg.tool_calls = list(tool_calls_collected)
                assistant_msg.metadata = metadata
                assistant_msg.save(update_fields=['content', 'reasoning_content', 'tool_calls', 'metadata'])
            return assistant_msg

        event_queue = queue.Queue()
        agent_error = [None]

        def _on_tool_progress(event_type, tool_name, call_id='', progress=0, message='', data=None):
            event_queue.put(('event', {
                'type': 'tool_progress',
                'event_type': event_type,
                'tool_name': tool_name,
                'call_id': call_id,
                'progress': progress,
                'message': message,
                'data': data or {},
            }))

        agent.set_progress_callback(_on_tool_progress)

        def run_agent():
            try:
                for event in agent.chat(message, history=history):
                    event_queue.put(('event', event))
                event_queue.put(('done', None))
            except Exception as e:
                logger.error(f'Agent线程异常: {e}', exc_info=True)
                agent_error[0] = str(e)
                event_queue.put(('error', None))

        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()

        completed_normally = False
        try:
            if compact_info:
                is_compacted = True
                yield f'data: {json.dumps(compact_info, ensure_ascii=False)}\n\n'

            while True:
                try:
                    msg_type, event = event_queue.get(timeout=0.5)
                except queue.Empty:
                    if tool_executing and time.time() - last_status_time > 2:
                        yield f'data: {json.dumps({"type": "tool_executing", "tool_name": current_tool_name, "call_id": current_tool_call_id}, ensure_ascii=False)}\n\n'
                        last_status_time = time.time()
                    elif tool_confirming and time.time() - last_status_time > 2:
                        yield f'data: {json.dumps({"type": "tool_confirming", "tool_name": current_tool_name, "call_id": current_tool_call_id, "confirm_id": current_confirm_id}, ensure_ascii=False)}\n\n'
                        last_status_time = time.time()
                    else:
                        yield ': heartbeat\n\n'
                    continue

                if msg_type == 'done':
                    break
                elif msg_type == 'error':
                    raise Exception(agent_error[0] or 'Agent执行异常')

                if event['type'] == 'reasoning':
                    full_reasoning += event['content']
                    if current_thinking_block is None:
                        current_thinking_block = {'type': 'thinking', 'content': event['content']}
                        blocks.append(current_thinking_block)
                    else:
                        current_thinking_block['content'] += event['content']
                    yield f'data: {json.dumps({"type": "reasoning", "content": event["content"]}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'content':
                    full_content += event['content']
                    if current_content_block is None:
                        current_content_block = {'type': 'content', 'content': event['content']}
                        blocks.append(current_content_block)
                    else:
                        current_content_block['content'] += event['content']
                    ensure_assistant_msg()
                    yield f'data: {json.dumps({"type": "content", "content": event["content"]}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'tool_call':
                    tool_name = event.get('tool', '') or 'unknown'
                    call_id = event.get('id', '')
                    tool_type = _get_tool_type(tool_name)
                    tool_calls_collected.append({
                        'id': call_id,
                        'type': 'function',
                        'function': {'name': tool_name, 'arguments': '{}'}
                    })
                    current_content_block = None
                    current_thinking_block = None
                    blocks.append({
                        'type': 'tool',
                        'call_id': call_id,
                        'name': tool_name,
                        'tool_type': tool_type,
                        'status': 'calling',
                        'result': '',
                    })
                    ensure_assistant_msg()
                    yield f'data: {json.dumps({"type": "tool_call", "tool_name": tool_name, "call_id": call_id, "tool_type": tool_type}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'tool_executing':
                    tool_name = event.get('tool', '') or 'unknown'
                    call_id = event.get('id', '')
                    arguments = event.get('arguments', {})
                    tool_type = _get_tool_type(tool_name)
                    tool_executing = True
                    current_tool_name = tool_name
                    current_tool_call_id = call_id
                    last_status_time = time.time()
                    for tc in tool_calls_collected:
                        if tc.get('id') == call_id:
                            tc['function']['arguments'] = json.dumps(arguments, ensure_ascii=False)
                            break
                    for blk in blocks:
                        if blk.get('type') == 'tool' and blk.get('call_id') == call_id:
                            blk['status'] = 'executing'
                            blk['arguments'] = arguments
                            blk['tool_type'] = tool_type
                            break
                    ensure_assistant_msg()
                    yield f'data: {json.dumps({"type": "tool_executing", "tool_name": tool_name, "call_id": call_id, "arguments": arguments, "tool_type": tool_type}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'tool_confirm':
                    tool_name = event.get('tool', '') or 'unknown'
                    call_id = event.get('id', '')
                    confirm_id = event.get('confirm_id', '')
                    arguments = event.get('arguments', {})
                    tool_type = _get_tool_type(tool_name)
                    tool_executing = False
                    tool_confirming = True
                    current_tool_name = tool_name
                    current_tool_call_id = call_id
                    current_confirm_id = confirm_id
                    last_status_time = time.time()
                    for blk in blocks:
                        if blk.get('type') == 'tool' and blk.get('call_id') == call_id:
                            blk['status'] = 'confirming'
                            blk['arguments'] = arguments
                            blk['tool_type'] = tool_type
                            break
                    confirm_timeout = event.get('timeout', 600)
                    yield f'data: {json.dumps({"type": "tool_confirm", "tool_name": tool_name, "call_id": call_id, "confirm_id": confirm_id, "arguments": arguments, "tool_type": tool_type, "timeout": confirm_timeout}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'form_request':
                    tool_name = event.get('tool', '') or 'unknown'
                    call_id = event.get('id', '')
                    form_id = event.get('form_id', '')
                    form_title = event.get('title', '')
                    form_fields = event.get('fields', [])
                    tool_type = _get_tool_type(tool_name)
                    tool_executing = False
                    tool_confirming = False
                    for blk in blocks:
                        if blk.get('type') == 'tool' and blk.get('call_id') == call_id:
                            blk['status'] = 'form'
                            blk['form_id'] = form_id
                            blk['form_title'] = form_title
                            blk['form_fields'] = form_fields
                            blk['tool_type'] = tool_type
                            break
                    ensure_assistant_msg()
                    yield f'data: {json.dumps({"type": "form_request", "tool_name": tool_name, "call_id": call_id, "form_id": form_id, "title": form_title, "fields": form_fields, "tool_type": tool_type}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'tool_result':
                    tool_name = event.get('tool', '') or 'unknown'
                    result = event.get('result', '')
                    call_id = event.get('id', '')
                    tool_type = _get_tool_type(tool_name)
                    tool_executing = False
                    tool_confirming = False

                    for tc in tool_calls_collected:
                        if tc.get('id') == call_id:
                            tc['result'] = result
                            break

                    for blk in blocks:
                        if blk.get('type') == 'tool' and blk.get('call_id') == call_id:
                            blk['status'] = 'done' if '<toolcall_status>error</toolcall_status>' not in result else 'error'
                            blk['result'] = result
                            blk['tool_type'] = tool_type
                            break

                    tool_msg_content = result
                    if len(result) > 8000:
                        try:
                            from apps.sysai.tools.base import _smart_truncate
                            tool_msg_content = _smart_truncate(result, 8000)
                        except Exception:
                            tool_msg_content = result[:8000]

                    AIChatMessage.objects.create(
                        session=session,
                        role='tool',
                        content=tool_msg_content,
                        tool_call_id=call_id,
                        tool_name=tool_name,
                    )

                    ensure_assistant_msg()
                    yield f'data: {json.dumps({"type": "tool_result", "tool_name": tool_name, "result": result, "call_id": call_id, "tool_type": tool_type}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'stop':
                    tool_executing = False
                    tool_confirming = False
                    usage = event.get('usage', {})
                    if usage.get('total_tokens') or usage.get('input_tokens') or usage.get('output_tokens'):
                        total_usage['total_tokens'] = usage.get('total_tokens', 0) or total_usage['total_tokens']
                        total_usage['input_tokens'] = usage.get('input_tokens', 0) or total_usage['input_tokens']
                        total_usage['output_tokens'] = usage.get('output_tokens', 0) or total_usage['output_tokens']

                    if agent.is_stopped():
                        stop_reason = agent.get_stop_reason()
                        display_stop_reason = 'user' if stop_reason == 'user' else 'interrupted'
                        if assistant_msg:
                            assistant_msg.is_stop = True
                            if assistant_msg.stop_reason not in ('length', 'limit'):
                                assistant_msg.stop_reason = display_stop_reason
                            assistant_msg.content = full_content
                            assistant_msg.reasoning_content = full_reasoning
                            assistant_msg.tool_calls = tool_calls_collected
                            assistant_msg.metadata = {'blocks': blocks}
                            assistant_msg.save()
                        else:
                            AIChatMessage.objects.create(
                                session=session,
                                role='assistant',
                                content=full_content,
                                reasoning_content=full_reasoning,
                                tool_calls=tool_calls_collected,
                                is_stop=True,
                                stop_reason=display_stop_reason,
                                metadata={'blocks': blocks},
                            )
                    else:
                        ensure_assistant_msg()

                    session.message_count = AIChatMessage.objects.filter(session=session).count()
                    session.save()

                    self._record_usage(session, model, total_usage, content=full_content, user_message=message)

                    need_generate_title = is_new_session and len(message) > 30
                    if not need_generate_title and session:
                        msg_count_before = AIChatMessage.objects.filter(session=session, role='user').count()
                        default_title = message[:30]
                        if msg_count_before <= 1 and len(message) > 30 and session.title == default_title:
                            need_generate_title = True

                    if need_generate_title:
                        try:
                            title_response = full_content or full_reasoning or ''
                            logger.info(f'开始生成会话标题: session={session.id}, msg_len={len(message)}, resp_len={len(title_response)}, has_content={bool(full_content)}, has_reasoning={bool(full_reasoning)}, is_new_session={is_new_session}')
                            from apps.sysai.agent.title_generator import generate_title

                            def _title_callback(sid, title):
                                try:
                                    s = AIChatSession.objects.filter(id=sid).first()
                                    if s:
                                        s.title = title
                                        s.save(update_fields=['title'])
                                        logger.info(f'标题已更新到数据库: session={sid}, title={title}')
                                except Exception as te:
                                    logger.warning(f'标题更新DB失败: {te}')

                            new_title = generate_title(message, title_response, str(session.id), model)
                            if new_title:
                                _title_callback(str(session.id), new_title)
                                yield f'data: {json.dumps({"type": "title_update", "session_id": str(session.id), "title": new_title}, ensure_ascii=False)}\n\n'
                            else:
                                logger.warning(f'标题生成返回空: session={session.id}')
                        except Exception as te:
                            logger.warning(f'标题生成异常: {te}')

                    msg_id = str(assistant_msg.id) if assistant_msg else ''
                    done_data = {"type": "done", "message_id": msg_id, "session_id": str(session.id)}
                    if total_usage.get('total_tokens') or total_usage.get('input_tokens') or total_usage.get('output_tokens'):
                        done_data['usage'] = {
                            'total_tokens': total_usage.get('total_tokens', 0),
                            'input_tokens': total_usage.get('input_tokens', 0),
                            'output_tokens': total_usage.get('output_tokens', 0),
                        }
                    yield f'data: {json.dumps(done_data, ensure_ascii=False)}\n\n'

                    yield 'data: [DONE]\n\n'
                    completed_normally = True
                    return

                elif event['type'] == 'warning':
                    yield f'data: {json.dumps({"type": "warning", "content": event.get("content", "")}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'length_limit':
                    if assistant_msg:
                        assistant_msg.is_stop = True
                        assistant_msg.stop_reason = 'length'
                        assistant_msg.save(update_fields=['is_stop', 'stop_reason'])
                    yield f'data: {json.dumps({"type": "length_limit", "content": event.get("content", "")}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'can_continue':
                    if assistant_msg:
                        assistant_msg.is_stop = True
                        if assistant_msg.stop_reason != 'length':
                            assistant_msg.stop_reason = 'limit'
                        assistant_msg.save(update_fields=['is_stop', 'stop_reason'])
                    yield f'data: {json.dumps({"type": "can_continue", "content": event.get("content", "")}, ensure_ascii=False)}\n\n'

                elif event['type'] == 'error':
                    tool_executing = False
                    tool_confirming = False
                    error_content = event.get('content', '未知错误')
                    _mark_tool_blocks_error(blocks)
                    if not assistant_msg:
                        assistant_msg = AIChatMessage.objects.create(
                            session=session,
                            role='assistant',
                            content=f'抱歉，对话过程中出现了错误：{error_content}',
                            is_error=True,
                            tool_calls=tool_calls_collected,
                            metadata={'blocks': blocks},
                        )
                    else:
                        assistant_msg.is_error = True
                        assistant_msg.content = f'抱歉，对话过程中出现了错误：{error_content}'
                        assistant_msg.tool_calls = tool_calls_collected
                        assistant_msg.metadata = {'blocks': blocks}
                        assistant_msg.save()
                    self._record_usage(session, model, total_usage, is_error=True, content=full_content, user_message=message)
                    yield f'data: {json.dumps({"type": "error", "content": error_content}, ensure_ascii=False)}\n\n'
                    yield 'data: [DONE]\n\n'
                    return

                elif event['type'] == 'meta_info':
                    pass

                elif event['type'] == 'tool_progress':
                    yield f'data: {json.dumps({
                        "type": "tool_progress",
                        "event_type": event.get("event_type", ""),
                        "tool_name": event.get("tool_name", ""),
                        "call_id": event.get("call_id", ""),
                        "progress": event.get("progress", 0),
                        "message": event.get("message", ""),
                        "data": event.get("data", {}),
                    }, ensure_ascii=False)}\n\n'

            if not assistant_msg and (full_content or tool_calls_collected):
                assistant_msg = AIChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=full_content,
                    reasoning_content=full_reasoning,
                    tool_calls=tool_calls_collected,
                    metadata={'blocks': blocks},
                )
                session.message_count = AIChatMessage.objects.filter(session=session).count()
                session.save()

                self._record_usage(session, model, total_usage, content=full_content, user_message=message)

            yield f'data: {json.dumps({"type": "done", "message_id": str(assistant_msg.id) if assistant_msg else "", "session_id": str(session.id)}, ensure_ascii=False)}\n\n'
            yield 'data: [DONE]\n\n'
            completed_normally = True

        except GeneratorExit:
            if not assistant_msg and (full_content or tool_calls_collected):
                assistant_msg = AIChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=full_content,
                    reasoning_content=full_reasoning,
                    tool_calls=tool_calls_collected,
                    is_stop=True,
                    stop_reason='interrupted',
                    metadata={'blocks': blocks},
                )
                session.message_count = AIChatMessage.objects.filter(session=session).count()
                session.save()
            elif assistant_msg:
                assistant_msg.is_stop = True
                assistant_msg.stop_reason = 'interrupted'
                assistant_msg.content = full_content
                assistant_msg.reasoning_content = full_reasoning
                assistant_msg.tool_calls = tool_calls_collected
                assistant_msg.metadata = {'blocks': blocks}
                assistant_msg.save()
            self._record_usage(session, model, total_usage, is_error=False, content=full_content, user_message=message)
        except Exception as e:
            logger.error(f'流式对话异常: {e}', exc_info=True)
            error_msg = f'对话出错: {str(e)}'
            _mark_tool_blocks_error(blocks)
            if not assistant_msg:
                AIChatMessage.objects.create(
                    session=session,
                    role='assistant',
                    content=f'抱歉，对话过程中出现了错误：{error_msg}',
                    is_error=True,
                    tool_calls=tool_calls_collected,
                    metadata={'blocks': blocks},
                )
            else:
                assistant_msg.is_error = True
                assistant_msg.content = f'抱歉，对话过程中出现了错误：{error_msg}'
                assistant_msg.tool_calls = tool_calls_collected
                assistant_msg.metadata = {'blocks': blocks}
                assistant_msg.save()
            self._record_usage(session, model, total_usage, is_error=True, content=full_content, user_message=message)
            yield f'data: {json.dumps({"type": "error", "content": error_msg}, ensure_ascii=False)}\n\n'
            yield 'data: [DONE]\n\n'
        finally:
            if not completed_normally:
                _stop_agent(str(session.id), reason='cleanup')
            _cleanup_agent(str(session.id))
            agent.tool_registry.remove_progress_callback(str(session.id))

    def _record_usage(self, session, model, usage, is_error=False, content='', user_message='', user_id=None):
        try:
            prompt_tokens = usage.get('input_tokens', 0) or 0
            completion_tokens = usage.get('output_tokens', 0) or 0
            total_tokens = usage.get('total_tokens', 0) or 0

            has_provider_data = bool(prompt_tokens or completion_tokens or total_tokens)

            if not has_provider_data:
                if content:
                    completion_tokens = _estimate_tokens(content)
                else:
                    completion_tokens = 0

                prompt_tokens = 0
                if user_message:
                    prompt_tokens += _estimate_tokens(user_message)

                if session:
                    all_msgs = AIChatMessage.objects.filter(
                        session=session
                    ).order_by('create_at')
                    for msg in all_msgs:
                        if msg.content:
                            prompt_tokens += _estimate_tokens(msg.content)
                        if msg.reasoning_content:
                            prompt_tokens += _estimate_tokens(msg.reasoning_content)
                        if msg.tool_calls:
                            prompt_tokens += _estimate_tokens(json.dumps(msg.tool_calls, ensure_ascii=False))

                prompt_tokens += _estimate_tokens(
                    '你是如意面板的AI助手，一个专业的服务器运维专家。你可以帮助用户管理服务器、诊断问题、部署应用、优化性能。'
                )

                if prompt_tokens == 0:
                    prompt_tokens = max(1, int(completion_tokens * 0.5)) if completion_tokens > 0 else 1

                total_tokens = prompt_tokens + completion_tokens
                if total_tokens == 0:
                    total_tokens = 1
                    prompt_tokens = 1
            else:
                if total_tokens == 0:
                    total_tokens = prompt_tokens + completion_tokens

            _user_id = user_id or (session.user_id if session else 0)
            logger.info(
                f'记录AI用量: user={_user_id}, model={model.model_name if model else "unknown"}, '
                f'prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}, '
                f'from_provider={has_provider_data}, is_error={is_error}'
            )

            AIUsageLog.objects.create(
                user_id=_user_id,
                model=model,
                session=session,
                session_title=session.title if session else '',
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                model_name=model.model_name if model else '',
                provider=model.provider if model else '',
            )
        except Exception as e:
            logger.error(f'记录用量失败: {e}', exc_info=True)

    def _sync_chat_with_agent(self, session, model, message, agent_config=None):
        agent_id = getattr(session, 'agent_id', None) or ''
        agent = _get_or_create_agent(str(session.id), model, config=agent_config, user_input=message, agent_id=agent_id)
        history = self._get_history(session)
        history = history[:-1]

        full_content = ''
        full_reasoning = ''
        total_usage = {'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0}
        tool_calls_collected = []
        blocks = []
        current_content_block = None
        current_thinking_block = None
        is_stopped_by_limit = False
        stop_reason_value = ''
        can_continue_content = ''

        try:
            for event in agent.chat(message, history=history):
                if event['type'] == 'content':
                    full_content += event['content']
                    if current_content_block is None:
                        current_content_block = {'type': 'content', 'content': event['content']}
                        blocks.append(current_content_block)
                    else:
                        current_content_block['content'] += event['content']
                elif event['type'] == 'reasoning':
                    full_reasoning += event['content']
                    if current_thinking_block is None:
                        current_thinking_block = {'type': 'thinking', 'content': event['content']}
                        blocks.append(current_thinking_block)
                    else:
                        current_thinking_block['content'] += event['content']
                elif event['type'] == 'tool_call':
                    tool_name = event.get('tool', '') or 'unknown'
                    call_id = event.get('id', '')
                    tool_calls_collected.append({
                        'id': call_id,
                        'type': 'function',
                        'function': {'name': tool_name, 'arguments': '{}'}
                    })
                    current_content_block = None
                    current_thinking_block = None
                    blocks.append({
                        'type': 'tool',
                        'call_id': call_id,
                        'name': tool_name,
                        'status': 'calling',
                        'result': '',
                    })
                elif event['type'] == 'tool_confirm':
                    confirm_id = event.get('confirm_id', '')
                    call_id = event.get('id', '')
                    tool_name = event.get('tool', '') or 'unknown'
                    for blk in blocks:
                        if blk.get('type') == 'tool' and blk.get('call_id') == call_id:
                            blk['status'] = 'executing'
                            break
                    agent.confirm_tool(confirm_id, True)
                elif event['type'] == 'form_request':
                    form_id = event.get('form_id', '')
                    call_id = event.get('id', '')
                    for blk in blocks:
                        if blk.get('type') == 'tool' and blk.get('call_id') == call_id:
                            blk['status'] = 'form'
                            break
                    agent.submit_form(form_id, {'_auto_submitted': True, '_note': '同步模式下自动提交，信息未填写'})
                elif event['type'] == 'tool_executing':
                    tool_name = event.get('tool', '') or 'unknown'
                    call_id = event.get('id', '')
                    arguments = event.get('arguments', {})
                    for tc in tool_calls_collected:
                        if tc.get('id') == call_id:
                            tc['function']['arguments'] = json.dumps(arguments, ensure_ascii=False)
                            break
                    for blk in blocks:
                        if blk.get('type') == 'tool' and blk.get('call_id') == call_id:
                            blk['status'] = 'executing'
                            blk['arguments'] = arguments
                            break
                elif event['type'] == 'tool_result':
                    tool_name = event.get('tool', '') or 'unknown'
                    result = event.get('result', '')
                    call_id = event.get('id', '')

                    for tc in tool_calls_collected:
                        if tc.get('id') == call_id:
                            tc['result'] = result
                            break

                    for blk in blocks:
                        if blk.get('type') == 'tool' and blk.get('call_id') == call_id:
                            blk['status'] = 'done' if '<toolcall_status>error</toolcall_status>' not in result else 'error'
                            blk['result'] = result
                            break

                    tool_msg_content = result
                    if len(result) > 8000:
                        try:
                            from apps.sysai.tools.base import _smart_truncate
                            tool_msg_content = _smart_truncate(result, 8000)
                        except Exception:
                            tool_msg_content = result[:8000]

                    AIChatMessage.objects.create(
                        session=session,
                        role='tool',
                        content=tool_msg_content,
                        tool_call_id=call_id,
                        tool_name=tool_name,
                    )
                elif event['type'] == 'stop':
                    usage = event.get('usage', {})
                    total_usage['total_tokens'] = usage.get('total_tokens', 0) or total_usage['total_tokens']
                    total_usage['input_tokens'] = usage.get('input_tokens', 0) or total_usage['input_tokens']
                    total_usage['output_tokens'] = usage.get('output_tokens', 0) or total_usage['output_tokens']
                    if not is_stopped_by_limit:
                        is_stopped_by_limit = True
                        if stop_reason_value not in ('length', 'limit'):
                            stop_reason_value = 'user'
                    break
                elif event['type'] == 'error':
                    full_content += f'\n\n[错误: {event.get("content", "")}]'
                    _mark_tool_blocks_error(blocks)
                    break
                elif event['type'] == 'warning':
                    pass
                elif event['type'] == 'length_limit':
                    is_stopped_by_limit = True
                    stop_reason_value = 'length'
                    can_continue_content = event.get('content', '')
                elif event['type'] == 'can_continue':
                    is_stopped_by_limit = True
                    if stop_reason_value != 'length':
                        stop_reason_value = 'limit'
                    can_continue_content = event.get('content', '')
                elif event['type'] == 'meta_info':
                    pass

            assistant_msg = AIChatMessage.objects.create(
                session=session,
                role='assistant',
                content=full_content,
                reasoning_content=full_reasoning,
                tool_calls=tool_calls_collected,
                is_stop=is_stopped_by_limit,
                stop_reason=stop_reason_value,
                metadata={'blocks': blocks},
            )
            session.message_count = AIChatMessage.objects.filter(session=session).count()
            session.save()

            self._record_usage(session, model, total_usage, content=full_content, user_message=message)

            return {
                'session_id': str(session.id),
                'message_id': str(assistant_msg.id),
                'content': full_content,
                'reasoning_content': full_reasoning,
            }

        except Exception as e:
            logger.error(f'同步对话异常: {e}', exc_info=True)
            error_msg = f'对话出错: {str(e)}'
            _mark_tool_blocks_error(blocks)
            AIChatMessage.objects.create(
                session=session,
                role='assistant',
                content=f'抱歉，对话过程中出现了错误：{error_msg}',
                is_error=True,
                tool_calls=tool_calls_collected,
                metadata={'blocks': blocks},
            )
            return {
                'session_id': str(session.id),
                'content': f'抱歉，对话过程中出现了错误：{error_msg}',
            }
        finally:
            _stop_agent(str(session.id), reason='cleanup')
            _cleanup_agent(str(session.id))


class AIChatStopView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        serializer = ChatStopSerializer(data=req_data)
        if not serializer.is_valid():
            return ErrorResponse(msg=str(serializer.errors))

        session_id = serializer.validated_data['session_id']
        _stop_agent(str(session_id))

        return DetailResponse(msg='已发送停止信号')


class AIChatConfirmView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        session_id = req_data.get('session_id')
        confirm_id = req_data.get('confirm_id')
        approved = req_data.get('approved', False)
        remember = req_data.get('remember', False)

        if not session_id or not confirm_id:
            return ErrorResponse(msg='缺少必要参数')

        with _agents_lock:
            agent = _agents.get(str(session_id))

        if not agent:
            return ErrorResponse(msg='会话不存在或已结束')

        agent.confirm_tool(confirm_id, bool(approved), remember=bool(remember))
        status_text = '已确认执行' if approved else '已拒绝执行'
        return DetailResponse(msg=status_text)


class AIChatFormSubmitView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        session_id = req_data.get('session_id')
        form_id = req_data.get('form_id')
        form_data = req_data.get('form_data', {})

        if not session_id or not form_id:
            return ErrorResponse(msg='缺少必要参数')

        with _agents_lock:
            agent = _agents.get(str(session_id))

        if not agent:
            return ErrorResponse(msg='会话不存在或已结束')

        agent.submit_form(form_id, form_data)
        return DetailResponse(msg='表单已提交')


class AIModelViewSet(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        models = AIModel.objects.all().order_by('sort_order', '-create_at')
        serializer = AIModelListSerializer(models, many=True)
        return SuccessResponse(data=serializer.data, total=models.count())

    def post(self, request):
        req_data = get_parameter_dic(request)
        serializer = AIModelSerializer(data=req_data)
        if not serializer.is_valid():
            return ErrorResponse(msg=str(serializer.errors))
        serializer.save()
        return DetailResponse(data=serializer.data, msg='模型添加成功')

    def put(self, request):
        req_data = get_parameter_dic(request)
        model_id = req_data.get('model_id') or req_data.get('id')
        if not model_id:
            return ErrorResponse(msg='缺少模型ID')
        instance = AIModel.objects.filter(id=model_id).first()
        if not instance:
            return ErrorResponse(msg='模型不存在')
        serializer = AIModelSerializer(instance, data=req_data, partial=True)
        if not serializer.is_valid():
            return ErrorResponse(msg=str(serializer.errors))
        serializer.save()
        return DetailResponse(data=serializer.data, msg='模型更新成功')

    def delete(self, request):
        req_data = get_parameter_dic(request)
        model_id = req_data.get('model_id') or req_data.get('id')
        if not model_id:
            return ErrorResponse(msg='缺少模型ID')
        instance = AIModel.objects.filter(id=model_id).first()
        if not instance:
            return ErrorResponse(msg='模型不存在')
        instance.delete()
        return DetailResponse(msg='模型删除成功')


class AIToolsView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.sysai.tools.base import registry as tool_registry
        tools_info = tool_registry.get_all_tools_info()

        tool_configs = {}
        for config in AIToolConfig.objects.all():
            tool_configs[config.name] = config

        result = []
        for info in tools_info:
            tool_name = info.get('name', '')
            config = tool_configs.get(tool_name)
            correct_category = info.get('category', 'default')
            if config:
                if config.tool_type != correct_category and correct_category:
                    config.tool_type = correct_category
                    config.save(update_fields=['tool_type'])
                result.append({
                    'id': config.id,
                    'name': config.name,
                    'display_name': config.display_name or info.get('name_cn', ''),
                    'tool_type': correct_category,
                    'description': config.description or info.get('description', ''),
                    'is_enabled': config.is_enabled,
                    'is_dangerous': config.is_dangerous,
                    'require_confirm': config.require_confirm,
                    'sort_order': config.sort_order,
                    'category': correct_category,
                    'name_cn': info.get('name_cn', ''),
                    'risk_level': info.get('risk_level', 'low'),
                })
            else:
                result.append({
                    'name': tool_name,
                    'display_name': info.get('name_cn', '') or tool_name,
                    'tool_type': info.get('category', 'default'),
                    'description': info.get('description', ''),
                    'is_enabled': True,
                    'is_dangerous': False,
                    'require_confirm': False,
                    'sort_order': 0,
                    'category': info.get('category', 'default'),
                    'name_cn': info.get('name_cn', ''),
                    'risk_level': info.get('risk_level', 'low'),
                })

        return DetailResponse(data=result)

    def post(self, request):
        req_data = get_parameter_dic(request)
        serializer = AIToolConfigSerializer(data=req_data)
        if not serializer.is_valid():
            return ErrorResponse(msg=str(serializer.errors))
        serializer.save()
        return DetailResponse(data=serializer.data, msg='工具添加成功')

    def put(self, request):
        req_data = get_parameter_dic(request)
        tool_id = req_data.get('id')
        if not tool_id:
            return ErrorResponse(msg='缺少工具ID')
        instance = AIToolConfig.objects.filter(id=tool_id).first()
        if not instance:
            return ErrorResponse(msg='工具不存在')
        serializer = AIToolConfigSerializer(instance, data=req_data, partial=True)
        if not serializer.is_valid():
            return ErrorResponse(msg=str(serializer.errors))
        serializer.save()
        return DetailResponse(data=serializer.data, msg='工具更新成功')

    def delete(self, request):
        req_data = get_parameter_dic(request)
        tool_id = req_data.get('id')
        if not tool_id:
            return ErrorResponse(msg='缺少工具ID')
        instance = AIToolConfig.objects.filter(id=tool_id).first()
        if not instance:
            return ErrorResponse(msg='工具不存在')
        instance.delete()
        return DetailResponse(msg='工具删除成功')


def _extract_error_message(error):
    try:
        if hasattr(error, 'message') and error.message:
            return str(error.message)
        body = getattr(error, 'body', None)
        if isinstance(body, dict):
            err_info = body.get('error', {})
            if isinstance(err_info, dict):
                return err_info.get('message', str(error))
            return str(err_info) if err_info else str(error)
    except Exception:
        pass
    return str(error)


class AIModelDiscoverView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        base_url = req_data.get('base_url', '').strip().rstrip('/')
        api_key = req_data.get('api_key', '').strip()

        if not base_url or not api_key:
            return ErrorResponse(msg='缺少参数 base_url 或 api_key')

        import openai

        urls_to_try = [base_url]
        if not base_url.endswith('/v1'):
            urls_to_try.append(base_url + '/v1')

        last_error = None
        last_error_detail = None
        for url in urls_to_try:
            try:
                client = openai.OpenAI(api_key=api_key, base_url=url)
                response = client.models.list()
                model_names = [model.id for model in response.data]
                return SuccessResponse(data=model_names)
            except openai.NotFoundError:
                last_error = '接口路径不存在'
                last_error_detail = f'尝试的地址: {url}/models'
                continue
            except openai.AuthenticationError:
                return ErrorResponse(msg='API Key 认证失败，请检查密钥是否正确')
            except openai.PermissionDeniedError:
                return ErrorResponse(msg='没有权限访问该接口，请检查 API Key 权限')
            except openai.RateLimitError as e:
                return ErrorResponse(msg=f'请求频率超限，请稍后重试。详情: {_extract_error_message(e)}')
            except openai.APIConnectionError:
                last_error = f'无法连接到服务器: {url}'
                last_error_detail = f'请检查接口地址是否正确，当前尝试: {url}'
                continue
            except openai.APIStatusError as e:
                error_msg = _extract_error_message(e)
                status_code = e.status_code
                if status_code == 402:
                    return ErrorResponse(msg=f'账户余额不足，请充值后重试。详情: {error_msg}')
                elif status_code == 429:
                    return ErrorResponse(msg=f'请求频率超限，请稍后重试。详情: {error_msg}')
                elif status_code == 400:
                    return ErrorResponse(msg=f'请求参数错误。详情: {error_msg}')
                elif status_code == 403:
                    return ErrorResponse(msg=f'访问被拒绝，请检查权限。详情: {error_msg}')
                elif status_code >= 500:
                    last_error = f'服务端错误(HTTP {status_code})'
                    last_error_detail = error_msg
                    continue
                else:
                    last_error = f'请求失败(HTTP {status_code})'
                    last_error_detail = error_msg
                    continue
            except Exception as e:
                last_error = str(e)
                last_error_detail = str(e)
                continue

        error_msg = '获取模型列表失败'
        if last_error_detail:
            error_msg = f'{error_msg}: {last_error_detail}'
        logger.error(f'获取模型列表失败: {last_error}')
        return ErrorResponse(msg=error_msg)


class AIAgentListView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        agents = get_all_agents()

        try:
            from apps.sysai.agent.skill_agent_manager import skill_agent_manager
            skill_agents = skill_agent_manager.all_as_dict()
            existing_ids = {a['id'] for a in agents}
            for sa in skill_agents:
                if sa['id'] not in existing_ids:
                    agents.append(sa)
        except Exception as e:
            logger.debug(f'加载SkillAgent列表失败: {e}')

        try:
            from apps.sysai.agent.intent_router import get_toolset_info_for_api
            toolset_info = get_toolset_info_for_api()
        except Exception:
            toolset_info = None

        return DetailResponse(data={'agents': agents, 'toolset_info': toolset_info})


class AIAgentAutoCollectView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        agent_id = req_data.get('agent_id', '')

        if not agent_id:
            return ErrorResponse(msg='缺少agent_id')

        agent_cls = get_agent_class(agent_id)
        if not agent_cls:
            try:
                from apps.sysai.agent.skill_agent_manager import skill_agent_manager
                skill_agent = skill_agent_manager.get(agent_id)
                if skill_agent:
                    return SuccessResponse(data={
                        'agent_id': agent_id,
                        'collected': [],
                        'system_prompt': skill_agent.system_prompt,
                    })
            except Exception:
                pass
            return ErrorResponse(msg='未找到指定的Agent')

        agent_instance = agent_cls()
        steps = agent_instance.get_auto_collect_steps()
        if not steps:
            return SuccessResponse(data={
                'agent_id': agent_id,
                'collected': [],
                'system_prompt': agent_instance.system_prompt or '',
            })

        collected = []
        for step in steps:
            tool_name = step.get('tool', '')
            params = step.get('params', {})
            label = step.get('label', tool_name)

            try:
                tool_func = tool_registry.get_tool(tool_name)
                if not tool_func:
                    collected.append({'label': label, 'success': False, 'error': f'工具 {tool_name} 不存在'})
                    continue

                result = tool_func(**params)

                output = ''
                if isinstance(result, dict):
                    output = result.get('output', result.get('result', json.dumps(result, ensure_ascii=False)))
                else:
                    output = str(result)

                collected.append({'label': label, 'success': True, 'output': output[:3000]})
            except Exception as e:
                collected.append({'label': label, 'success': False, 'error': str(e)})

        return SuccessResponse(data={'agent_id': agent_id, 'collected': collected})


class AICustomAgentView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        name = req_data.get('name', '').strip()
        if not name:
            return ErrorResponse(msg='智能体名称不能为空')

        description = req_data.get('description', '')
        category = req_data.get('category', 'custom')
        toolsets = req_data.get('toolsets', [])
        if isinstance(toolsets, str):
            toolsets = [t.strip() for t in toolsets.split(',') if t.strip()]
        tools = req_data.get('tools', [])
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(',') if t.strip()]
        system_prompt = req_data.get('system_prompt', '')
        preset_questions = req_data.get('preset_questions', [])
        if isinstance(preset_questions, str):
            preset_questions = [q.strip() for q in preset_questions.split('|') if q.strip()]

        try:
            from apps.sysai.agent.skill_agent_manager import skill_agent_manager
            result = skill_agent_manager.create_skill(
                name=name,
                description=description,
                category=category,
                toolsets=toolsets,
                tools=tools,
                system_prompt=system_prompt,
                preset_questions=preset_questions,
            )
            return SuccessResponse(data=result)
        except Exception as e:
            return ErrorResponse(msg=f'创建智能体失败: {e}')

    def delete(self, request):
        req_data = get_parameter_dic(request)
        agent_id = req_data.get('agent_id', '').strip()
        if not agent_id:
            return ErrorResponse(msg='缺少agent_id')

        try:
            from apps.sysai.agent.skill_agent_manager import skill_agent_manager
            success = skill_agent_manager.delete_skill(agent_id)
            if success:
                return SuccessResponse(msg='删除成功')
            return ErrorResponse(msg='删除失败，智能体不存在或为内置智能体')
        except Exception as e:
            return ErrorResponse(msg=f'删除智能体失败: {e}')


class AIToolToggleView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        tool_name = req_data.get('tool_name', '')
        is_visible = req_data.get('is_visible', True)

        if not tool_name:
            return ErrorResponse(msg='缺少工具名称')

        from apps.sysai.tools.base import registry as tool_registry
        tool_meta = tool_registry._metadata.get(tool_name, {})
        original_category = tool_meta.get('category', 'custom')
        original_name_cn = tool_meta.get('name_cn', tool_name)

        tool_config, created = AIToolConfig.objects.get_or_create(
            name=tool_name,
            defaults={
                'display_name': original_name_cn or tool_name,
                'tool_type': original_category,
                'is_enabled': is_visible,
            }
        )
        if not created:
            tool_config.is_enabled = is_visible
            tool_config.save()

        return DetailResponse(msg='更新成功')


class AICompactChatView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        req_data = get_parameter_dic(request)
        session_id = req_data.get('session_id')
        if not session_id:
            return ErrorResponse(msg='缺少会话ID')

        session = AIChatSession.objects.filter(id=session_id, user_id=request.user.id).first()
        if not session:
            return ErrorResponse(msg='会话不存在')

        model = session.model or AIModel.objects.filter(is_enabled=True, is_default=True).first()
        if not model:
            return ErrorResponse(msg='没有可用的AI模型')

        try:
            from apps.sysai.provider.tools import get_model_from_db
            from apps.sysai.compressor import ContextCompressor

            llm_model = get_model_from_db(model)
            sys_config = {}
            config_obj = AIModel.objects_all.filter(name='__sys_config__').first()
            if config_obj and config_obj.extra_params:
                sys_config = config_obj.extra_params

            compressor = ContextCompressor(sys_config)
            compressor.enabled = True

            messages = AIChatMessage.objects.filter(session=session).order_by('create_at')
            history = []
            for msg in messages:
                item = {'id': str(msg.id), 'role': msg.role, 'content': msg.content}
                if msg.tool_calls:
                    item['tool_calls'] = msg.tool_calls
                if msg.tool_call_id:
                    item['tool_call_id'] = msg.tool_call_id
                if msg.tool_name:
                    item['name'] = msg.tool_name
                history.append(item)

            assistant_count = sum(1 for m in history if m.get('role') == 'assistant' and m.get('content'))
            if assistant_count < 3:
                return DetailResponse(msg='对话轮次较少，无需压缩')

            result = compressor.compress(session, history, llm_model)
            if result.get('compacted'):
                return DetailResponse(
                    msg='上下文压缩成功',
                    data={
                        'compacted_count': result.get('compacted_count', 0),
                        'flushed': result.get('flushed', 0),
                        'tokens_before': result.get('tokens_before', 0),
                        'tokens_after': result.get('tokens_after', 0),
                    }
                )
            else:
                return DetailResponse(msg='对话内容较少，无需压缩')
        except Exception as e:
            logger.error(f'上下文压缩失败: {e}', exc_info=True)
            return ErrorResponse(msg=f'压缩失败: {str(e)}')


class AIFileUploadView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from utils.common import GetDataPath
        upload_dir = os.path.join(GetDataPath(), 'ai_attachments')
        os.makedirs(upload_dir, exist_ok=True)

        files = request.FILES.getlist('files')
        if not files:
            return ErrorResponse(msg='没有上传文件')

        relative_paths = request.POST.getlist('relative_paths')

        uploaded = []
        for idx, f in enumerate(files):
            if relative_paths and idx < len(relative_paths) and relative_paths[idx]:
                rel_path = relative_paths[idx]
                file_path = os.path.join(upload_dir, rel_path)
                file_dir = os.path.dirname(file_path)
                os.makedirs(file_dir, exist_ok=True)
            else:
                file_path = os.path.join(upload_dir, f.name)

            with open(file_path, 'wb') as dest:
                for chunk in f.chunks():
                    dest.write(chunk)
            uploaded.append({
                'name': f.name,
                'path': file_path,
                'size': f.size,
            })

        return DetailResponse(data=uploaded, msg='上传成功')


class AIServerFileBrowseView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        req_data = get_parameter_dic(request)
        dir_path = req_data.get('path', '/')
        if not os.path.isdir(dir_path):
            return ErrorResponse(msg='目录不存在')

        items = []
        try:
            for entry in os.scandir(dir_path):
                try:
                    is_dir = entry.is_dir()
                    stat = entry.stat()
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'is_dir': is_dir,
                        'size': stat.st_size if not is_dir else 0,
                        'modify_time': stat.st_mtime,
                    })
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            return ErrorResponse(msg='无权限访问该目录')

        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return SuccessResponse(data=items, msg='获取成功')


class AIMCPStatusView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from apps.sysai.mcp import mcp_client_manager
            servers = mcp_client_manager.get_server_status()
            tools = mcp_client_manager.get_openai_tools()
            return DetailResponse(data={
                'servers': servers,
                'tools_count': len(tools),
            })
        except Exception as e:
            return ErrorResponse(msg=f'获取MCP状态失败: {e}')

    def post(self, request):
        req_data = get_parameter_dic(request)
        action = req_data.get('action', '')

        try:
            from apps.sysai.mcp import mcp_client_manager

            if action == 'reload':
                mcp_client_manager.reload()
                return SuccessResponse(msg='MCP配置已重新加载')
            elif action == 'connect':
                server_name = req_data.get('server_name', '')
                if not server_name:
                    return ErrorResponse(msg='缺少server_name')
                success = mcp_client_manager.connect_server(server_name)
                if success:
                    return SuccessResponse(msg=f'MCP Server [{server_name}] 连接成功')
                else:
                    return ErrorResponse(msg=f'MCP Server [{server_name}] 连接失败')
            elif action == 'add_server':
                server_data = req_data.get('server_data', {})
                if not server_data or not server_data.get('name'):
                    return ErrorResponse(msg='缺少server_data或name')
                success = mcp_client_manager.add_server(server_data)
                if success:
                    return SuccessResponse(msg=f'MCP Server [{server_data["name"]}] 添加成功')
                else:
                    return ErrorResponse(msg='添加MCP Server失败')
            elif action == 'remove_server':
                server_name = req_data.get('server_name', '')
                if not server_name:
                    return ErrorResponse(msg='缺少server_name')
                success = mcp_client_manager.remove_server(server_name)
                if success:
                    return SuccessResponse(msg=f'MCP Server [{server_name}] 已删除')
                else:
                    return ErrorResponse(msg=f'MCP Server [{server_name}] 不存在')
            else:
                return ErrorResponse(msg='不支持的操作')
        except Exception as e:
            return ErrorResponse(msg=f'MCP操作失败: {e}')


class AIToolsetInfoView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from apps.sysai.agent.intent_router import get_toolset_info_for_api
            info = get_toolset_info_for_api()
            return SuccessResponse(data=info)
        except Exception as e:
            return ErrorResponse(msg=f'获取Toolset信息失败: {e}')
