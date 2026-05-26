import json
import logging
from apps.sysai.tools.base import register_tool

logger = logging.getLogger(__name__)


@register_tool(id='alert_list', category='panel', name_cn='告警任务列表', risk_level='low')
def alert_list(is_enabled: bool = None):
    """获取告警任务列表。当用户需要查看、管理告警规则时使用此工具。可按启用状态过滤。"""
    try:
        from apps.sysalert.models import AlertTask

        queryset = AlertTask.objects.all().order_by('-id')
        if is_enabled is not None:
            queryset = queryset.filter(is_enabled=is_enabled)

        tasks = []
        for task in queryset[:50]:
            item = {
                'id': task.id,
                'name': task.name,
                'task_type': task.get_task_type_display(),
                'task_type_code': task.task_type,
                'is_enabled': task.is_enabled,
                'is_alerting': task.is_alerting,
                'silence_minutes': task.silence_minutes,
                'push_count': task.push_count,
                'last_trigger': task.last_trigger.strftime('%Y-%m-%d %H:%M:%S') if task.last_trigger else '',
                'channels': task.channels or '',
                'create_at': task.create_at.strftime('%Y-%m-%d %H:%M:%S') if task.create_at else '',
            }
            tasks.append(item)

        return json.dumps({
            'total': AlertTask.objects.count(),
            'showing': len(tasks),
            'tasks': tasks,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'获取告警任务列表失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>获取告警任务列表失败: {str(e)}'


@register_tool(id='alert_create', category='panel', name_cn='创建告警任务', risk_level='high')
def alert_create(
    name: str,
    task_type: str,
    threshold: int = 80,
    duration: int = 5,
    channels: str = '',
    silence_minutes: int = 30,
    push_count: int = 10,
    check_interval: int = 300,
    urls: str = '',
    days_before: int = 15,
    slow_threshold: int = 5,
    timeout: int = 10,
):
    """创建一个告警任务。当用户需要设置系统资源监控告警、网站监控告警、SSL证书过期告警等时使用此工具。

    参数说明:
    - name: 告警任务名称
    - task_type: 告警类型，可选值:
      - cpu_usage: CPU使用率告警
      - mem_usage: 内存使用率告警
      - disk_usage: 磁盘使用率告警
      - disk_io: 磁盘IO告警
      - network_io: 网络流量告警
      - load_avg: 系统负载告警
      - ssl_expire: SSL证书过期告警
      - site_down: 网站宕机告警
      - site_slow: 网站响应慢告警
      - cron_fail: 定时任务失败告警
    - threshold: 告警阈值百分比（默认80），适用于cpu_usage/mem_usage/disk_usage/disk_io/network_io/load_avg
    - duration: 持续时间分钟数（默认5），指标持续超过阈值多少分钟才告警
    - channels: 通知渠道ID列表，逗号分隔（如 "1,2,3"）。先使用 notify_channel_list 查看可用渠道
    - silence_minutes: 静默时间分钟数（默认30），同一告警在静默期内不重复通知
    - push_count: 每日推送上限（默认10），0表示不限制
    - check_interval: 检查间隔秒数（默认300），仅网站类告警可配置
    - urls: 监控URL列表，逗号分隔（仅site_down/site_slow类型需要）
    - days_before: 提前几天告警（默认15，仅ssl_expire类型）
    - slow_threshold: 响应慢阈值秒数（默认5，仅site_slow类型）
    - timeout: URL请求超时秒数（默认10，仅网站类告警）

    示例:
    - CPU超过90%告警: task_type="cpu_usage", threshold=90, channels="1"
    - 磁盘超过85%告警: task_type="disk_usage", threshold=85
    - SSL证书15天内过期告警: task_type="ssl_expire", days_before=15
    - 网站宕机告警: task_type="site_down", urls="https://example.com,https://api.example.com"
    """
    try:
        from apps.sysalert.models import AlertTask

        valid_types = [choice[0] for choice in AlertTask.TYPE_CHOICES]
        if task_type not in valid_types:
            return f'<toolcall_status>error</toolcall_status>不支持的告警类型: {task_type}，可选: {", ".join(valid_types)}'

        config = {}
        if task_type in ['cpu_usage', 'mem_usage', 'disk_usage', 'disk_io', 'network_io', 'load_avg']:
            config['threshold'] = threshold
            config['duration'] = duration
        elif task_type == 'ssl_expire':
            config['days_before'] = days_before
        elif task_type in ['site_down', 'site_slow']:
            if not urls:
                return '<toolcall_status>error</toolcall_status>网站类告警必须提供urls参数'
            config['urls'] = [u.strip() for u in urls.split(',') if u.strip()]
            config['timeout'] = timeout
            if task_type == 'site_slow':
                config['slow_threshold'] = slow_threshold

        task = AlertTask.objects.create(
            name=name,
            task_type=task_type,
            config=json.dumps(config, ensure_ascii=False),
            channels=channels,
            is_enabled=True,
            silence_minutes=silence_minutes,
            push_count=push_count,
            check_interval=check_interval,
        )

        return json.dumps({
            'id': task.id,
            'name': name,
            'task_type': task.get_task_type_display(),
            'config': config,
            'channels': channels,
            'message': f'告警任务"{name}"创建成功',
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'创建告警任务失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>创建告警任务失败: {str(e)}'


@register_tool(id='alert_toggle', category='panel', name_cn='启停告警任务', risk_level='medium')
def alert_toggle(task_id: int, is_enabled: bool = True):
    """启用或停用告警任务。当用户需要暂停或恢复告警监控时使用此工具。"""
    try:
        from apps.sysalert.models import AlertTask

        task = AlertTask.objects.filter(id=task_id).first()
        if not task:
            return '<toolcall_status>error</toolcall_status>告警任务不存在'

        task.is_enabled = is_enabled
        task.save(update_fields=['is_enabled', 'update_at'])

        status_text = '已启用' if is_enabled else '已停用'
        return json.dumps({
            'id': task.id,
            'name': task.name,
            'is_enabled': is_enabled,
            'message': f'告警任务"{task.name}"{status_text}',
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'启停告警任务失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>启停告警任务失败: {str(e)}'


@register_tool(id='alert_delete', category='panel', name_cn='删除告警任务', risk_level='high')
def alert_delete(task_id: int):
    """删除指定的告警任务。"""
    try:
        from apps.sysalert.models import AlertTask

        task = AlertTask.objects.filter(id=task_id).first()
        if not task:
            return '<toolcall_status>error</toolcall_status>告警任务不存在'

        task_name = task.name
        task.delete()

        return json.dumps({
            'id': task_id,
            'name': task_name,
            'message': f'告警任务"{task_name}"已删除',
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'删除告警任务失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>删除告警任务失败: {str(e)}'


@register_tool(id='alert_test', category='panel', name_cn='测试告警通知', risk_level='medium')
def alert_test(task_id: int):
    """测试告警任务的通知渠道是否正常。发送一条测试消息到该告警任务配置的所有通知渠道。"""
    try:
        from apps.sysalert.models import AlertTask, AlertNotifyConfig
        from apps.sysalert.notify import AlertNotifier

        task = AlertTask.objects.filter(id=task_id).first()
        if not task:
            return '<toolcall_status>error</toolcall_status>告警任务不存在'

        channel_ids = task.get_channel_ids()
        if not channel_ids:
            return '<toolcall_status>error</toolcall_status>该告警任务未配置通知渠道，请先配置通知渠道'

        configs = AlertNotifyConfig.objects.filter(id__in=channel_ids)
        if not configs.exists():
            return '<toolcall_status>error</toolcall_status>未找到对应的通知渠道配置'

        title = f'告警测试 - {task.name}'
        content = f'这是一条测试消息，用于验证告警任务"{task.name}"的通知渠道是否正常。\n发送时间: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

        results = []
        for cfg in configs:
            success, msg = AlertNotifier.send(cfg, title, content)
            results.append({
                'channel': f'{cfg.channel_type}({cfg.name})',
                'success': success,
                'message': msg,
            })

        success_count = sum(1 for r in results if r['success'])
        return json.dumps({
            'task_name': task.name,
            'total_channels': len(results),
            'success_count': success_count,
            'results': results,
            'message': f'测试完成: {success_count}/{len(results)} 个渠道发送成功',
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'测试告警通知失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>测试告警通知失败: {str(e)}'


@register_tool(id='notify_channel_list', category='panel', name_cn='通知渠道列表', risk_level='low')
def notify_channel_list(is_enabled: bool = None):
    """获取告警通知渠道列表。当用户需要查看可用的通知渠道（邮件、钉钉、飞书等）时使用此工具。创建告警任务时需要用到渠道ID。"""
    try:
        from apps.sysalert.models import AlertNotifyConfig

        queryset = AlertNotifyConfig.objects.all().order_by('-id')
        if is_enabled is not None:
            queryset = queryset.filter(is_enabled=is_enabled)

        channels = []
        for cfg in queryset:
            channels.append({
                'id': cfg.id,
                'name': cfg.name,
                'channel_type': cfg.get_channel_type_display(),
                'channel_type_code': cfg.channel_type,
                'is_enabled': cfg.is_enabled,
                'daily_limit': cfg.daily_limit,
                'send_time_range': f'{cfg.send_start_time.strftime("%H:%M")}-{cfg.send_end_time.strftime("%H:%M")}',
            })

        return json.dumps({
            'total': AlertNotifyConfig.objects.count(),
            'showing': len(channels),
            'channels': channels,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'获取通知渠道列表失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>获取通知渠道列表失败: {str(e)}'


@register_tool(id='notify_channel_test', category='panel', name_cn='测试通知渠道', risk_level='medium')
def notify_channel_test(channel_id: int):
    """测试指定通知渠道是否正常。发送一条测试消息到该渠道，验证配置是否正确。"""
    try:
        from apps.sysalert.models import AlertNotifyConfig
        from apps.sysalert.notify import AlertNotifier

        config = AlertNotifyConfig.objects.filter(id=channel_id).first()
        if not config:
            return '<toolcall_status>error</toolcall_status>通知渠道不存在'

        title = '如意面板 - 通知渠道测试'
        content = f'这是一条测试消息，用于验证"{config.name}"({config.get_channel_type_display()})渠道配置是否正常。\n发送时间: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

        success, msg = AlertNotifier.send(config, title, content)

        return json.dumps({
            'channel_id': channel_id,
            'channel_name': config.name,
            'channel_type': config.get_channel_type_display(),
            'success': success,
            'message': msg,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'测试通知渠道失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>测试通知渠道失败: {str(e)}'
