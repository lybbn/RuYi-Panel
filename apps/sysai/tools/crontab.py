import json
import logging
from datetime import datetime, timedelta
from apps.sysai.tools.base import register_tool, AIToolRegistry

logger = logging.getLogger(__name__)


@register_tool(id='crontab_list', category='panel', name_cn='定时任务列表', risk_level='low')
def crontab_list(status: int = None):
    """获取服务器定时任务列表。当用户需要查看、管理计划任务/定时任务/cron任务时使用此工具。可按状态过滤：1=启用, 0=停用, 不传则返回全部。"""
    try:
        from apps.systask.models import CrontabTask
        from django_apscheduler.models import DjangoJobExecution

        queryset = CrontabTask.objects.all().order_by('-create_at')
        if status is not None:
            queryset = queryset.filter(status=status)

        tasks = []
        for task in queryset[:50]:
            next_run = ''
            try:
                if task.job:
                    next_run = task.job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if task.job.next_run_time else ''
            except Exception:
                pass

            last_run = ''
            last_status = ''
            try:
                last_execution = DjangoJobExecution.objects.filter(job=task.job).order_by('-run_time').first()
                if last_execution:
                    last_run = last_execution.run_time.strftime('%Y-%m-%d %H:%M:%S')
                    last_status = '成功' if last_execution.status == 'Executed' else ('失败' if last_execution.status == 'Error!' else last_execution.status)
            except Exception:
                pass

            period_map = {0: '自定义', 1: '每天', 2: '每周', 3: '每月', 4: '每小时', 5: '每隔N天', 6: '每隔N时', 7: '每隔N分', 8: '每隔N秒', 9: '一次性'}
            type_map = {0: 'Shell脚本', 1: '备份数据库', 2: '备份网站', 3: '备份目录', 4: '访问URL', 5: 'AI任务'}

            item = {
                'id': task.id,
                'name': task.name,
                'type': type_map.get(task.type, f'类型{task.type}'),
                'period_type': period_map.get(task.period_type, f'周期{task.period_type}'),
                'status': '启用' if task.status else '停用',
                'is_sys': task.is_sys,
                'shell_body': (task.shell_body or '')[:200],
                'next_run_time': next_run,
                'last_run_time': last_run,
                'last_run_status': last_status,
                'create_at': task.create_at.strftime('%Y-%m-%d %H:%M:%S') if task.create_at else '',
            }

            if task.type == 5:
                item['ai_prompt'] = (task.ai_prompt or '')[:200]
                item['ai_deliver'] = task.ai_deliver or 'none'
                item['ai_silent'] = task.ai_silent
                item['ai_context_from'] = task.ai_context_from
                item['ai_last_result'] = (task.ai_last_result or '')[:200]

            tasks.append(item)

        return json.dumps({
            'total': CrontabTask.objects.count(),
            'showing': len(tasks),
            'tasks': tasks,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'获取定时任务列表失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>获取定时任务列表失败: {str(e)}'


@register_tool(id='crontab_create', category='panel', name_cn='创建定时任务', risk_level='high')
def crontab_create(
    name: str,
    shell_body: str,
    period_type: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    day: int = 0,
    week: int = 0,
    month: int = 0,
):
    """创建一个新的定时任务。当用户需要设置定时执行脚本、定期备份、周期性运维操作、定时访问URL时使用此工具。**此工具跨平台支持Windows和Linux，禁止用execute_command执行schtasks/crontab等系统命令来创建定时任务。**

    参数说明:
    - name: 任务名称
    - shell_body: 要执行的脚本或命令内容（支持Shell、PowerShell、curl、wget等，跨平台通用）
    - period_type: 周期类型 (1=每天, 2=每周, 3=每月, 4=每小时, 5=每隔N天, 6=每隔N时, 7=每隔N分, 8=每隔N秒)
    - hour: 小时 (0-23)
    - minute: 分钟 (0-59)
    - second: 秒 (0-59, 仅period_type=8时有效)
    - day: 天 (period_type=5时为间隔天数, period_type=3时为每月几号)
    - week: 星期几 (1-7, 仅period_type=2时有效)
    - month: 月份 (仅period_type=3时有效)

    示例:
    - 每天凌晨3点执行: period_type=1, hour=3, minute=0
    - 每周一凌晨2点执行: period_type=2, week=1, hour=2, minute=0
    - 每月1号凌晨4点执行: period_type=3, day=1, hour=4, minute=0
    - 每隔30分钟执行: period_type=7, minute=30
    - 定时访问URL: shell_body="curl -s https://example.com" 或 "powershell Invoke-WebRequest -Uri 'https://example.com' -UseBasicParsing"
    """
    try:
        from apps.systask.models import CrontabTask
        from apps.systask.tasks import resolvingCron, cronTask
        from apps.systask.scheduler import scheduler
        import uuid

        if not name or not shell_body:
            return '<toolcall_status>error</toolcall_status>任务名称和脚本内容不能为空'

        job_id = str(uuid.uuid4().hex)
        req_data = {
            'name': name,
            'shell_body': shell_body,
            'type': 0,
            'period_type': period_type,
            'hour': hour,
            'minute': minute,
            'second': second,
            'day': day,
            'week': week,
            'month': month,
            'year': 0,
        }

        cron_res = resolvingCron(req_data)
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        if period_type in [1, 2, 3, 4]:
            cron_kwargs = {}
            if cron_res.get('second') and cron_res['second'] != '*':
                cron_kwargs['second'] = int(cron_res['second'])
            if cron_res.get('minute') and cron_res['minute'] != '*':
                cron_kwargs['minute'] = int(cron_res['minute'])
            if cron_res.get('hour') and cron_res['hour'] != '*':
                cron_kwargs['hour'] = int(cron_res['hour'])
            if cron_res.get('day') and cron_res['day'] != '*':
                cron_kwargs['day'] = int(cron_res['day'])
            if cron_res.get('month') and cron_res['month'] != '*':
                cron_kwargs['month'] = int(cron_res['month'])
            if cron_res.get('week') and cron_res['week'] != '*':
                cron_kwargs['week'] = int(cron_res['week'])

            django_job = scheduler.add_job(
                cronTask, 'cron', id=job_id,
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
                args=[req_data, job_id],
                **cron_kwargs,
            )
        elif period_type == 5:
            django_job = scheduler.add_job(
                cronTask, 'interval', id=job_id,
                days=int(day) if day else 0,
                hours=int(hour) if hour else 0,
                minutes=int(minute) if minute else 0,
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
            )
        elif period_type == 6:
            django_job = scheduler.add_job(
                cronTask, 'interval', id=job_id,
                hours=int(hour) if hour else 0,
                minutes=int(minute) if minute else 0,
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
            )
        elif period_type == 7:
            django_job = scheduler.add_job(
                cronTask, 'interval', id=job_id,
                minutes=int(minute),
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
            )
        elif period_type == 8:
            django_job = scheduler.add_job(
                cronTask, 'interval', id=job_id,
                seconds=int(second),
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
            )
        else:
            return '<toolcall_status>error</toolcall_status>不支持的周期类型'

        req_data['job'] = django_job.id
        task = CrontabTask.objects.create(
            name=name,
            type=0,
            period_type=period_type,
            hour=hour,
            minute=minute,
            second=second,
            day=day,
            week=week,
            month=month,
            year=0,
            shell_body=shell_body,
            job_id=django_job.id,
        )

        return json.dumps({
            'task_id': task.id,
            'name': name,
            'job_id': job_id,
            'message': f'定时任务"{name}"创建成功',
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'创建定时任务失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>创建定时任务失败: {str(e)}'


@register_tool(id='crontab_create_ai', category='panel', name_cn='创建AI定时任务', risk_level='high')
def crontab_create_ai(
    name: str,
    ai_prompt: str,
    period_type: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    day: int = 0,
    week: int = 0,
    month: int = 0,
    ai_deliver: str = 'none',
    ai_silent: bool = True,
    ai_context_from: str = '',
    ai_timeout: int = 300,
    run_at: str = '',
):
    """创建一个AI定时任务。AI将在指定时间自动执行提示词描述的任务，并可将结果投递到通知渠道。**这是AI增强型定时任务，AI会自主分析、调用工具并完成任务，无需编写脚本。**

    参数说明:
    - name: 任务名称
    - ai_prompt: AI任务提示词，描述AI需要完成的工作。例如："检查磁盘使用率，如果超过80%则报告具体哪些分区空间不足"
    - period_type: 周期类型 (1=每天, 2=每周, 3=每月, 4=每小时, 5=每隔N天, 6=每隔N时, 7=每隔N分, 9=一次性)
    - hour/minute/second/day/week/month: 同crontab_create
    - ai_deliver: 结果投递渠道，逗号分隔多个。可选: none=不投递, all=所有已启用渠道, email=邮件, dingtalk=钉钉, feishu=飞书, wechat=企业微信, webhook=Webhook。例如: "dingtalk,email"
    - ai_silent: 静默模式，默认True。AI返回[SILENT]时不投递通知（一切正常时不打扰）
    - ai_context_from: 上游任务ID，从指定任务的最近执行结果获取上下文（任务链）
    - ai_timeout: AI执行超时时间(秒)，默认300秒
    - run_at: 一次性执行时间，格式: "2026-01-15 09:00"（仅period_type=9时有效）

    示例:
    - 每天早上9点AI检查系统健康: ai_prompt="检查CPU、内存、磁盘使用率，如果任何指标超过80%则报告异常，否则返回[SILENT]", period_type=1, hour=9, ai_deliver="dingtalk", ai_silent=True
    - 每小时AI监控网站: ai_prompt="检查Nginx是否运行，访问https://example.com确认可访问，异常时报告详情", period_type=4, minute=0, ai_deliver="all", ai_silent=True
    - 30分钟后一次性提醒: ai_prompt="提醒我检查数据库备份是否完成", period_type=9, run_at="2026-01-15 14:30", ai_deliver="email"
    - 任务链 - 分析上游任务结果: ai_prompt="根据上游磁盘检查结果，给出具体的清理建议", ai_context_from="5", period_type=1, hour=10, ai_deliver="feishu"
    """
    try:
        from apps.systask.models import CrontabTask
        from apps.systask.tasks import resolvingCron, cronTask
        from apps.systask.scheduler import scheduler
        import uuid

        if not name or not ai_prompt:
            return '<toolcall_status>error</toolcall_status>任务名称和AI提示词不能为空'

        if ai_context_from:
            upstream = CrontabTask.objects.filter(id=ai_context_from).first()
            if not upstream:
                return f'<toolcall_status>error</toolcall_status>上游任务ID {ai_context_from} 不存在，请先使用 crontab_list 查看可用任务'

        job_id = str(uuid.uuid4().hex)
        req_data = {
            'name': name,
            'type': 5,
            'period_type': period_type,
            'hour': hour,
            'minute': minute,
            'second': second,
            'day': day,
            'week': week,
            'month': month,
            'year': 0,
            'ai_prompt': ai_prompt,
            'ai_deliver': ai_deliver,
            'ai_silent': ai_silent,
            'ai_context_from': ai_context_from,
            'ai_timeout': ai_timeout,
        }

        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.date import DateTrigger

        django_job = None

        if period_type == 9:
            if not run_at:
                return '<toolcall_status>error</toolcall_status>一次性任务必须指定run_at参数（格式: "2026-01-15 09:00"）'
            try:
                for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y-%m-%d'):
                    try:
                        run_at_dt = datetime.strptime(run_at.strip(), fmt)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError('格式不匹配')
                from django.conf import settings
                from pytz import timezone as pytz_tz
                run_at_dt = pytz_tz(settings.TIME_ZONE).localize(run_at_dt)
            except Exception:
                return f'<toolcall_status>error</toolcall_status>无法解析时间: {run_at}，请使用格式 "2026-01-15 09:00"'
            if run_at_dt <= datetime.now(run_at_dt.tzinfo):
                return '<toolcall_status>error</toolcall_status>一次性执行时间必须在当前时间之后'
            django_job = scheduler.add_job(
                cronTask, 'date', id=job_id,
                run_date=run_at_dt,
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=3600, coalesce=True,
            )
            req_data['run_at'] = run_at
        elif period_type in [1, 2, 3, 4]:
            cron_res = resolvingCron(req_data)
            cron_kwargs = {}
            if cron_res.get('second') and cron_res['second'] != '*':
                cron_kwargs['second'] = int(cron_res['second'])
            if cron_res.get('minute') and cron_res['minute'] != '*':
                cron_kwargs['minute'] = int(cron_res['minute'])
            if cron_res.get('hour') and cron_res['hour'] != '*':
                cron_kwargs['hour'] = int(cron_res['hour'])
            if cron_res.get('day') and cron_res['day'] != '*':
                cron_kwargs['day'] = int(cron_res['day'])
            if cron_res.get('month') and cron_res['month'] != '*':
                cron_kwargs['month'] = int(cron_res['month'])
            if cron_res.get('week') and cron_res['week'] != '*':
                cron_kwargs['week'] = int(cron_res['week'])
            django_job = scheduler.add_job(
                cronTask, 'cron', id=job_id,
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
                args=[req_data, job_id],
                **cron_kwargs,
            )
        elif period_type == 5:
            django_job = scheduler.add_job(
                cronTask, 'interval', id=job_id,
                days=int(day) if day else 0,
                hours=int(hour) if hour else 0,
                minutes=int(minute) if minute else 0,
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
            )
        elif period_type == 6:
            django_job = scheduler.add_job(
                cronTask, 'interval', id=job_id,
                hours=int(hour) if hour else 0,
                minutes=int(minute) if minute else 0,
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
            )
        elif period_type == 7:
            django_job = scheduler.add_job(
                cronTask, 'interval', id=job_id,
                minutes=int(minute),
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
            )
        elif period_type == 8:
            django_job = scheduler.add_job(
                cronTask, 'interval', id=job_id,
                seconds=int(second),
                args=[req_data, job_id],
                max_instances=1, replace_existing=True,
                misfire_grace_time=1, coalesce=True,
            )
        else:
            return '<toolcall_status>error</toolcall_status>不支持的周期类型'

        req_data['job'] = django_job.id

        task_kwargs = dict(
            name=name,
            type=5,
            period_type=period_type,
            hour=hour,
            minute=minute,
            second=second,
            day=day,
            week=week,
            month=month,
            year=0,
            shell_body='',
            job_id=django_job.id,
            ai_prompt=ai_prompt,
            ai_deliver=ai_deliver,
            ai_silent=ai_silent,
            ai_timeout=ai_timeout,
        )
        if ai_context_from:
            task_kwargs['ai_context_from'] = ai_context_from
        if period_type == 9 and run_at:
            task_kwargs['run_at'] = run_at

        task = CrontabTask.objects.create(**task_kwargs)

        result = {
            'task_id': task.id,
            'name': name,
            'job_id': job_id,
            'type': 'AI任务',
            'ai_deliver': ai_deliver,
            'ai_silent': ai_silent,
            'message': f'AI定时任务"{name}"创建成功',
        }
        if ai_context_from:
            result['ai_context_from'] = ai_context_from
            result['message'] += f'（关联上游任务ID: {ai_context_from}）'

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f'创建AI定时任务失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>创建AI定时任务失败: {str(e)}'


@register_tool(id='crontab_delete', category='panel', name_cn='删除定时任务', risk_level='high')
def crontab_delete(task_id: int):
    """删除指定的定时任务。当用户需要移除不再需要的计划任务时使用此工具。需要提供任务ID。"""
    try:
        from apps.systask.models import CrontabTask
        from apps.systask.tasks import pause_task, remove_task
        from apps.systask.tasklogger import deleteTaskLogs

        task = CrontabTask.objects.filter(id=task_id).first()
        if not task:
            return '<toolcall_status>error</toolcall_status>任务不存在'

        task_name = task.name
        job_id = task.job_id

        try:
            pause_task(job_id)
            remove_task(job_id)
            deleteTaskLogs(job_id)
        except Exception:
            pass

        task.delete()

        return json.dumps({
            'task_id': task_id,
            'name': task_name,
            'message': f'定时任务"{task_name}"已删除',
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'删除定时任务失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>删除定时任务失败: {str(e)}'


@register_tool(id='crontab_toggle', category='panel', name_cn='启停定时任务', risk_level='medium')
def crontab_toggle(task_id: int, status: int = 1):
    """启用或停用定时任务。status=1启用, status=0停用。当用户需要暂停或恢复定时任务时使用此工具。"""
    try:
        from apps.systask.models import CrontabTask
        from apps.systask.tasks import pause_task, resume_task

        task = CrontabTask.objects.filter(id=task_id).first()
        if not task:
            return '<toolcall_status>error</toolcall_status>任务不存在'

        job_id = task.job_id

        if status == 0:
            pause_task(job_id)
            task.status = False
            task.save()
            return json.dumps({
                'task_id': task_id,
                'name': task.name,
                'status': '已停用',
                'message': f'定时任务"{task.name}"已停用',
            }, ensure_ascii=False)
        else:
            resume_task(job_id)
            task.status = True
            task.save()
            return json.dumps({
                'task_id': task_id,
                'name': task.name,
                'status': '已启用',
                'message': f'定时任务"{task.name}"已启用',
            }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'启停定时任务失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>启停定时任务失败: {str(e)}'


@register_tool(id='crontab_run', category='panel', name_cn='立即执行定时任务', risk_level='medium')
def crontab_run(task_id: int):
    """立即执行一次指定的定时任务，不影响原有调度计划。当用户需要手动触发定时任务执行时使用此工具。"""
    try:
        from apps.systask.models import CrontabTask
        from apps.systask.tasks import run_task
        from apps.systask.views.crontab_task import CrontabTasksSerializer

        task = CrontabTask.objects.filter(id=task_id).first()
        if not task:
            return '<toolcall_status>error</toolcall_status>任务不存在'

        registry = AIToolRegistry()
        registry.emit_progress('crontab_run', 'tool.log', 0, f'Triggering task: {task.name}')

        serializer = CrontabTasksSerializer(instance=task)
        run_task(serializer.data, task.job_id)

        registry.emit_progress('crontab_run', 'tool.log', 0, 'Task triggered successfully')

        return json.dumps({
            'task_id': task_id,
            'name': task.name,
            'message': f'定时任务"{task.name}"已触发执行',
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'执行定时任务失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>执行定时任务失败: {str(e)}'


@register_tool(id='crontab_logs', category='panel', name_cn='定时任务日志', risk_level='low')
def crontab_logs(task_id: int = None, lines: int = 100):
    """获取定时任务的执行日志。当用户需要查看定时任务的运行结果、排查任务执行问题时使用此工具。不传task_id则返回所有任务的最近执行记录。"""
    try:
        from django_apscheduler.models import DjangoJobExecution
        from apps.systask.models import CrontabTask

        queryset = DjangoJobExecution.objects.all().order_by('-run_time')

        if task_id:
            task = CrontabTask.objects.filter(id=task_id).first()
            if task:
                queryset = queryset.filter(job_id=task.job_id)
            else:
                return '<toolcall_status>error</toolcall_status>任务不存在'

        executions = queryset[:lines]
        logs = []
        for exe in executions:
            task_name = ''
            try:
                ct = CrontabTask.objects.filter(job_id=exe.job_id).first()
                if ct:
                    task_name = ct.name
            except Exception:
                pass

            status_map = {
                'Executed': '成功',
                'Error!': '失败',
                'Missed!': '过期',
                'Started execution': '开始',
                'Max instances!': '过载',
            }

            logs.append({
                'task_name': task_name,
                'job_id': exe.job_id,
                'run_time': exe.run_time.strftime('%Y-%m-%d %H:%M:%S') if exe.run_time else '',
                'duration': str(exe.duration) if exe.duration else '',
                'status': status_map.get(exe.status, exe.status),
                'exception': str(exe.exception) if exe.exception else '',
            })

        return json.dumps({
            'total': queryset.count(),
            'showing': len(logs),
            'logs': logs,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f'获取定时任务日志失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>获取定时任务日志失败: {str(e)}'


@register_tool(id='crontab_ai_result', category='panel', name_cn='AI任务最近结果', risk_level='low')
def crontab_ai_result(task_id: int):
    """获取AI定时任务的最近一次执行结果。当用户需要查看AI定时任务的执行输出、分析结果时使用此工具。"""
    try:
        from apps.systask.models import CrontabTask

        task = CrontabTask.objects.filter(id=task_id).first()
        if not task:
            return '<toolcall_status>error</toolcall_status>任务不存在'

        if task.type != 5:
            return '<toolcall_status>error</toolcall_status>该任务不是AI任务类型'

        result = {
            'task_id': task.id,
            'name': task.name,
            'ai_prompt': task.ai_prompt or '',
            'ai_deliver': task.ai_deliver or 'none',
            'ai_silent': task.ai_silent,
            'ai_context_from': task.ai_context_from or '',
            'ai_last_result': task.ai_last_result or '暂无执行结果',
        }

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f'获取AI任务结果失败: {e}', exc_info=True)
        return f'<toolcall_status>error</toolcall_status>获取AI任务结果失败: {str(e)}'
