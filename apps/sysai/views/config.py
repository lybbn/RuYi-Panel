import json
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from utils.common import get_parameter_dic
from apps.sysai.models import AIModel, AIChatSession, AIChatMessage, AIUsageLog

logger = logging.getLogger(__name__)

AI_CONFIG_KEY = 'sysai_global_config'

_DEFAULT_CONFIG = {
    'system_prompt': '',
    'max_turns': 100,
    'max_context_messages': 20,
    'enable_web_search': False,
    'web_search_provider': '',
    'web_search_api_key': '',
    'web_search_api_url': '',
    'enable_context_compress': True,
    'context_compress_threshold': 10000,
    'compress_preserve_rounds': 5,
    'enable_memory_flush': True,
    'enable_memory': False,
    'memory_recall_threshold': 10,
    'require_command_confirm': 'medium_high',
    'show_assistant': True,
}


class AIConfigView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.sysai.models import AIModel
        try:
            config_obj = AIModel.objects_all.filter(name='__sys_config__').first()
            if config_obj and config_obj.extra_params:
                config = {**_DEFAULT_CONFIG, **config_obj.extra_params}
            else:
                config = {**_DEFAULT_CONFIG}
        except Exception:
            config = {**_DEFAULT_CONFIG}
        return SuccessResponse(data=config)

    def post(self, request):
        req_data = get_parameter_dic(request)
        try:
            config_obj, _ = AIModel.objects_all.get_or_create(
                name='__sys_config__',
                defaults={
                    'model_name': '__sys_config__',
                    'provider': 'custom',
                    'extra_params': {},
                }
            )
            config_obj.extra_params = req_data
            config_obj.save()
            return DetailResponse(msg='配置保存成功')
        except Exception as e:
            logger.error(f'保存AI配置失败: {e}', exc_info=True)
            return ErrorResponse(msg=f'保存配置失败: {str(e)}')


class AIUsageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        req_data = get_parameter_dic(request)
        time_range = req_data.get('time_range', 'week')

        now = timezone.now()
        if time_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == 'week':
            start_date = now - timedelta(days=7)
        elif time_range == 'month':
            start_date = now - timedelta(days=30)
        else:
            start_date = None

        queryset = AIUsageLog.objects.filter(user_id=request.user.id)
        if start_date:
            queryset = queryset.filter(create_at__gte=start_date)

        summary = queryset.aggregate(
            total_requests=Count('id'),
            total_input_tokens=Sum('prompt_tokens'),
            total_output_tokens=Sum('completion_tokens'),
        )

        session_tool_counts = {}
        if start_date:
            tool_msgs = AIChatMessage.objects.filter(
                role='tool',
                session__in=queryset.values_list('session', flat=True),
                create_at__gte=start_date,
            ).values('session').annotate(tc=Count('id'))
        else:
            tool_msgs = AIChatMessage.objects.filter(
                role='tool',
                session__in=queryset.values_list('session', flat=True),
            ).values('session').annotate(tc=Count('id'))
        for item in tool_msgs:
            if item['session']:
                session_tool_counts[item['session']] = item['tc']

        by_model = queryset.values('model_name', 'provider').annotate(
            request_count=Count('id'),
            input_tokens=Sum('prompt_tokens'),
            output_tokens=Sum('completion_tokens'),
            total_tokens=Sum('total_tokens'),
        ).order_by('-total_tokens')

        by_model_list = []
        for item in by_model:
            model_sessions = queryset.filter(
                model_name=item['model_name'],
                provider=item['provider'],
            ).values_list('session_id', flat=True)
            tc = sum(session_tool_counts.get(sid, 0) for sid in model_sessions if sid)
            by_model_list.append({
                'model_name': item['model_name'],
                'provider': item['provider'],
                'request_count': item['request_count'],
                'input_tokens': item['input_tokens'] or 0,
                'output_tokens': item['output_tokens'] or 0,
                'total_tokens': item['total_tokens'] or 0,
                'tool_calls': tc,
            })

        from django.db.models.functions import TruncDate
        daily_stats = queryset.annotate(
            date=TruncDate('create_at')
        ).values('date').annotate(
            request_count=Count('id'),
            input_tokens=Sum('prompt_tokens'),
            output_tokens=Sum('completion_tokens'),
            total_tokens=Sum('total_tokens'),
        ).order_by('date')

        recent_logs = queryset.select_related('model', 'session').order_by('-create_at')[:50]
        logs_data = []
        for log in recent_logs:
            has_error = False
            tool_calls_count = 0
            if log.session:
                last_msg = AIChatMessage.objects.filter(
                    session=log.session, role='assistant'
                ).order_by('-create_at').first()
                if last_msg and last_msg.is_error:
                    has_error = True
                tool_calls_count = session_tool_counts.get(log.session.id, 0)

            logs_data.append({
                'id': str(log.id),
                'create_datetime': log.create_at.strftime('%Y-%m-%d %H:%M:%S'),
                'model_name': log.model_name,
                'provider': log.provider,
                'input_tokens': log.prompt_tokens,
                'output_tokens': log.completion_tokens,
                'total_tokens': log.total_tokens,
                'tool_calls_count': tool_calls_count,
                'is_error': has_error,
                'session_id': str(log.session.id) if log.session else '',
                'session_title': log.session_title or '',
            })

        return DetailResponse(data={
            'summary': {
                'total_requests': summary['total_requests'] or 0,
                'total_input_tokens': summary['total_input_tokens'] or 0,
                'total_output_tokens': summary['total_output_tokens'] or 0,
            },
            'by_model': by_model_list,
            'daily_stats': [
                {
                    'date': item['date'].strftime('%Y-%m-%d') if item['date'] else '',
                    'request_count': item['request_count'],
                    'input_tokens': item['input_tokens'] or 0,
                    'output_tokens': item['output_tokens'] or 0,
                    'total_tokens': item['total_tokens'] or 0,
                }
                for item in daily_stats
            ],
            'recent_logs': logs_data,
        })


class AIUsageResetView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        deleted_count, _ = AIUsageLog.objects.filter(user_id=request.user.id).delete()
        return DetailResponse(data={'deleted_count': deleted_count}, msg='用量统计已清空')


class AIUsageExportView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        req_data = get_parameter_dic(request)
        time_range = req_data.get('time_range', 'week')

        now = timezone.now()
        if time_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == 'week':
            start_date = now - timedelta(days=7)
        elif time_range == 'month':
            start_date = now - timedelta(days=30)
        else:
            start_date = None

        queryset = AIUsageLog.objects.filter(user_id=request.user.id)
        if start_date:
            queryset = queryset.filter(create_at__gte=start_date)

        logs = queryset.order_by('-create_at')
        data = []
        for log in logs:
            data.append({
                'date': log.create_at.strftime('%Y-%m-%d %H:%M:%S'),
                'model': log.model_name,
                'provider': log.provider,
                'input_tokens': log.prompt_tokens,
                'output_tokens': log.completion_tokens,
                'total_tokens': log.total_tokens,
                'cost': float(log.cost),
            })

        return DetailResponse(data=data)


class AIChatExportView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        req_data = get_parameter_dic(request)
        session_id = req_data.get('session_id')
        if not session_id:
            return ErrorResponse(msg='缺少会话ID')

        session = AIChatSession.objects.filter(id=session_id, user_id=request.user.id).first()
        if not session:
            return ErrorResponse(msg='会话不存在')

        messages = AIChatMessage.objects.filter(session=session).order_by('create_at')
        export_data = {
            'session': {
                'id': str(session.id),
                'title': session.title,
                'created_at': session.create_at.isoformat() if session.create_at else '',
                'model': session.model.name if session.model else '',
            },
            'messages': [],
        }

        for msg in messages:
            item = {
                'role': msg.role,
                'content': msg.content,
                'created_at': msg.create_at.isoformat() if msg.create_at else '',
            }
            if msg.reasoning_content:
                item['reasoning'] = msg.reasoning_content
            if msg.tool_calls:
                item['tool_calls'] = msg.tool_calls
            if msg.tool_name:
                item['tool_name'] = msg.tool_name
            export_data['messages'].append(item)

        return SuccessResponse(data=export_data)


class AICuratorView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.sysai.agent.curator import skill_curator
        try:
            status = skill_curator.get_curator_status()
            return DetailResponse(data=status)
        except Exception as e:
            logger.error(f'获取curator状态失败: {e}', exc_info=True)
            return ErrorResponse(msg=f'获取状态失败: {str(e)}')

    def post(self, request):
        from apps.sysai.agent.curator import skill_curator
        req_data = get_parameter_dic(request)
        action = req_data.get('action', 'maintenance')

        try:
            if action == 'maintenance':
                dry_run = req_data.get('dry_run', False)
                result = skill_curator.run_maintenance(dry_run=dry_run)
                return DetailResponse(data=result, msg='维护完成')
            elif action == 'prune':
                dry_run = req_data.get('dry_run', False)
                pruned = skill_curator.prune_stale_skills(dry_run=dry_run)
                return DetailResponse(data={'pruned': pruned}, msg=f'清理{len(pruned)}个技能')
            elif action == 'evolve':
                evolved = skill_curator.auto_evolve()
                return DetailResponse(data={'evolved': evolved}, msg=f'进化{len(evolved)}个技能')
            elif action == 'validate':
                from apps.sysai.agent.curator import skill_curator
                skill_name = req_data.get('skill_name', '')
                if not skill_name:
                    return ErrorResponse(msg='缺少技能名称')
                result = skill_curator.validate_skill(skill_name)
                return DetailResponse(data=result)
            else:
                return ErrorResponse(msg=f'未知操作: {action}')
        except Exception as e:
            logger.error(f'curator操作失败: {e}', exc_info=True)
            return ErrorResponse(msg=f'操作失败: {str(e)}')
