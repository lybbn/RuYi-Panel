import os
import json
import time
import uuid
from utils.common import ReadFile, WriteFile, current_os, GetRuyiSetupPath, GetPanelPath
from apps.sysbak.backup_engine.base import BaseBackupModule


class CrontabBackupModule(BaseBackupModule):
    """计划任务备份模块 - 使用 APScheduler 管理"""

    def get_data_list(self):
        from apps.systask.models import CrontabTask
        tasks = CrontabTask.objects.filter(is_sys=False).order_by('-id')
        result = []
        for t in tasks:
            result.append({
                'id': t.id,
                'name': t.name,
                'period_type': t.get_period_type_display(),
                'type': t.get_type_display(),
            })
        return result

    def backup(self, item_ids=None):
        from apps.systask.models import CrontabTask

        results = {}
        tasks = CrontabTask.objects.filter(id__in=item_ids) if item_ids else CrontabTask.objects.filter(is_sys=False)

        crontab_dir = os.path.join(self.backup_dir, 'crontab')
        os.makedirs(crontab_dir, exist_ok=True)

        tasks_data = []
        for task in tasks:
            try:
                self.report_progress('crontab', task.id, 1, f'正在备份计划任务: {task.name}')
                task_data = {
                    'id': task.id,
                    'name': task.name,
                    'is_sys': task.is_sys,
                    'status': task.status,
                    'period_type': task.period_type,
                    'year': task.year,
                    'month': task.month,
                    'week': task.week,
                    'day': task.day,
                    'hour': task.hour,
                    'minute': task.minute,
                    'second': task.second,
                    'type': task.type,
                    'shell_body': task.shell_body,
                    'database': task.database,
                    'website': task.website,
                    'dir': task.dir,
                    'exclude_rules': task.exclude_rules,
                    'db_type': task.db_type,
                    'backup_to': task.backup_to,
                    'saveNums': task.saveNums,
                    'url': task.url,
                    'ai_prompt': task.ai_prompt,
                    'ai_deliver': task.ai_deliver,
                    'ai_silent': task.ai_silent,
                    'ai_context_from': task.ai_context_from,
                    'ai_timeout': task.ai_timeout,
                    'run_at': str(task.run_at) if task.run_at else None,
                    'job_id': task.job_id,
                }
                tasks_data.append(task_data)
                results[task.id] = {'status': 2, 'error_msg': ''}
            except Exception as e:
                self.report_progress('crontab', task.id, 3, f'备份计划任务失败: {task.name} - {str(e)}')
                results[task.id] = {'status': 3, 'error_msg': str(e)}

        WriteFile(os.path.join(crontab_dir, 'crontab_tasks.json'), json.dumps(tasks_data, default=str))
        self.log(f'备份计划任务完成，共 {len(tasks_data)} 个')
        return results

    def restore(self, backup_dir, items_config, conflict_strategy='skip'):
        from apps.systask.models import CrontabTask
        from apps.systask.scheduler import scheduler
        from apps.systask.tasks import resolvingCron, cronTask

        tasks_file = os.path.join(backup_dir, 'crontab', 'crontab_tasks.json')
        if not os.path.exists(tasks_file):
            self.log('未找到计划任务备份文件')
            return

        tasks_data = json.loads(ReadFile(tasks_file))
        existing_names = set(CrontabTask.objects.values_list('name', flat=True))

        for task_data in tasks_data:
            name = task_data.get('name', '')
            is_sys = task_data.get('is_sys', False)

            # 跳过系统任务
            if is_sys:
                continue

            if name in existing_names:
                if conflict_strategy == 'skip':
                    self.log(f'跳过已存在的计划任务: {name}')
                    continue
                elif conflict_strategy == 'overwrite':
                    old_task = CrontabTask.objects.filter(name=name).first()
                    if old_task:
                        try:
                            if old_task.job_id:
                                scheduler.remove_job(old_task.job_id)
                        except Exception:
                            pass
                        old_task.delete()
                elif conflict_strategy == 'rename':
                    name = f"{name}_restored_{int(time.time())}"

            self.report_progress('crontab', task_data.get('id', ''), 1, f'正在还原计划任务: {name}')
            self.log(f'还原计划任务: {name}')

            try:
                # 跨平台适配 shell_body
                shell_body = task_data.get('shell_body', '')
                source_os = self._detect_source_os(backup_dir)
                shell_body = self._adapt_shell_body(shell_body, source_os)

                # 生成新的job_id
                new_job_id = str(uuid.uuid4().hex)

                # 构建reqData供cronTask使用
                reqData = {
                    'name': name,
                    'type': task_data.get('type', 0),
                    'shell_body': shell_body,
                    'database': task_data.get('database', ''),
                    'website': task_data.get('website', ''),
                    'dir': task_data.get('dir', ''),
                    'exclude_rules': task_data.get('exclude_rules', ''),
                    'url': task_data.get('url', ''),
                    'db_type': task_data.get('db_type', 0),
                    'backup_to': task_data.get('backup_to', 0),
                    'saveNums': task_data.get('saveNums', 3),
                    'ai_prompt': task_data.get('ai_prompt', ''),
                    'ai_deliver': task_data.get('ai_deliver', 'none'),
                    'ai_silent': task_data.get('ai_silent', False),
                    'ai_context_from': task_data.get('ai_context_from', ''),
                    'ai_timeout': task_data.get('ai_timeout', 300),
                    'run_at': task_data.get('run_at', ''),
                }

                period_type = task_data['period_type']
                django_job = None

                # 使用 scheduler 添加调度任务
                try:
                    if period_type == 9:  # 一次性任务
                        from apscheduler.triggers.date import DateTrigger
                        from pytz import timezone as pytz_tz
                        from django.conf import settings as django_settings

                        run_at = task_data.get('run_at', '')
                        if run_at:
                            import datetime
                            run_at_dt = datetime.datetime.strptime(str(run_at).strip(), '%Y-%m-%d %H:%M:%S')
                            run_at_dt = pytz_tz(django_settings.TIME_ZONE).localize(run_at_dt)
                            django_job = scheduler.add_job(
                                cronTask, 'date', id=new_job_id,
                                run_date=run_at_dt,
                                args=[reqData, new_job_id],
                                max_instances=1, replace_existing=True,
                                misfire_grace_time=3600, coalesce=True,
                            )
                    else:
                        cron_params = {
                            'period_type': period_type,
                            'year': task_data.get('year', 0),
                            'month': task_data.get('month', 0),
                            'week': task_data.get('week', 0),
                            'day': task_data.get('day', 0),
                            'hour': task_data.get('hour', 0),
                            'minute': task_data.get('minute', 0),
                            'second': task_data.get('second', 0),
                        }
                        cron_res = resolvingCron(cron_params)

                        if period_type in [1, 2, 3, 4]:  # 每天/每周/每月/每小时
                            django_job = scheduler.add_job(
                                cronTask, 'cron', id=new_job_id,
                                second=cron_res.get("second", "*"),
                                minute=cron_res.get("minute", "*"),
                                hour=cron_res.get("hour", "*"),
                                day=cron_res.get("day", "*"),
                                month=cron_res.get("month", "*"),
                                week=cron_res.get("week", "*"),
                                year=cron_res.get("year", "*"),
                                args=[reqData, new_job_id],
                                max_instances=1, replace_existing=True,
                                misfire_grace_time=1, coalesce=True,
                            )
                        elif period_type in [5, 6, 7, 8]:  # 间隔任务
                            from apscheduler.triggers.interval import IntervalTrigger
                            trigger_kwargs = {}
                            if period_type == 5:
                                trigger_kwargs = {'days': int(task_data.get('day', 0) or 0)}
                            elif period_type == 6:
                                trigger_kwargs = {'hours': int(task_data.get('hour', 0) or 0)}
                            elif period_type == 7:
                                trigger_kwargs = {'minutes': int(task_data.get('minute', 0) or 0)}
                            elif period_type == 8:
                                trigger_kwargs = {'seconds': int(task_data.get('second', 0) or 0)}

                            if any(trigger_kwargs.values()):
                                trigger = IntervalTrigger(**trigger_kwargs)
                                django_job = scheduler.add_job(
                                    cronTask, trigger, id=new_job_id,
                                    args=[reqData, new_job_id],
                                    max_instances=1, replace_existing=True,
                                    misfire_grace_time=1, coalesce=True,
                                )
                except Exception as e:
                    self.log(f'调度器添加任务失败: {str(e)}')

                # 创建数据库记录
                CrontabTask.objects.create(
                    name=name,
                    is_sys=False,
                    status=task_data.get('status', True),
                    period_type=period_type,
                    year=task_data.get('year', 0),
                    month=task_data.get('month', 0),
                    week=task_data.get('week', 0),
                    day=task_data.get('day', 0),
                    hour=task_data.get('hour', 0),
                    minute=task_data.get('minute', 0),
                    second=task_data.get('second', 0),
                    type=task_data.get('type', 0),
                    shell_body=shell_body,
                    database=task_data.get('database', ''),
                    website=task_data.get('website', ''),
                    dir=task_data.get('dir', ''),
                    exclude_rules=task_data.get('exclude_rules', ''),
                    url=task_data.get('url', ''),
                    db_type=task_data.get('db_type', 0),
                    backup_to=task_data.get('backup_to', 0),
                    saveNums=task_data.get('saveNums', 3),
                    ai_prompt=task_data.get('ai_prompt', ''),
                    ai_deliver=task_data.get('ai_deliver', 'none'),
                    ai_silent=task_data.get('ai_silent', False),
                    ai_context_from=task_data.get('ai_context_from', ''),
                    ai_timeout=task_data.get('ai_timeout', 300),
                    run_at=task_data.get('run_at', None),
                    job_id=new_job_id,
                )

                self.report_progress('crontab', task_data.get('id', ''), 2, f'计划任务还原完成: {name}')
                self.log(f'计划任务还原完成: {name}')
            except Exception as e:
                self.report_progress('crontab', task_data.get('id', ''), 3, f'计划任务还原失败: {name} - {str(e)}')
                self.log(f'计划任务还原失败: {name} - {str(e)}')

    def _detect_source_os(self, backup_dir):
        """检测备份来源平台"""
        metadata_file = os.path.join(backup_dir, 'metadata.json')
        if os.path.exists(metadata_file):
            try:
                metadata = json.loads(ReadFile(metadata_file))
                return metadata.get('platform', {}).get('os', 'linux')
            except Exception:
                pass
        return 'linux'

    def _adapt_shell_body(self, shell_body, source_os):
        """跨平台适配 shell_body"""
        if source_os == current_os or not shell_body:
            return shell_body

        import re
        manage_match = re.search(r'(manage\.py\s+\S+.*)', shell_body)
        if not manage_match:
            return shell_body

        manage_cmd = manage_match.group(1)

        if current_os == 'windows':
            setup_path = GetRuyiSetupPath()
            return f'cd /d "{setup_path}"\npython {manage_cmd}'
        else:
            panel_path = GetPanelPath()
            return f'cd "{panel_path}" && /usr/local/ruyi/python/bin/python3 {manage_cmd}'
