#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Copyright (c) 如意面板 All rights reserved.
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------

"""
计划任务系统初始数据配置
"""

import platform
from django.conf import settings


def get_default_crontab_tasks():
    """
    获取默认计划任务配置
    根据操作系统返回对应的 shell 命令
    """
    root_path = settings.BASE_DIR
    plat = platform.system().lower()
    
    if plat == 'windows':
        shell_body1 = f"cd {root_path}\npython manage.py checkSitesEnd"
        shell_body2 = f"cd {root_path}\npython manage.py renewSSL"
        shell_body3 = f"cd {root_path}\npython manage.py cleanMonitor"
        shell_body4 = f"cd {root_path}\npython manage.py cleanWafLogs"
    else:
        shell_body1 = f"cd {root_path}\n/usr/local/ruyi/python/bin/python3 manage.py checkSitesEnd"
        shell_body2 = f"cd {root_path}\n/usr/local/ruyi/python/bin/python3 manage.py renewSSL"
        shell_body3 = f"cd {root_path}\n/usr/local/ruyi/python/bin/python3 manage.py cleanMonitor"
        shell_body4 = f"cd {root_path}\n/usr/local/ruyi/python/bin/python3 manage.py cleanWafLogs"
    
    return [
        {
            "id": 1,
            "job_id": "sys_job_check_sites_end_001",
            "name": "检查网站过期",
            "is_sys": 0,
            "status": 1,
            "period_type": 1,
            "year": 0,
            "month": 0,
            "week": 0,
            "day": 0,
            "hour": 1,
            "minute": 10,
            "second": 0,
            "shell_body": shell_body1,
        },
        {
            "id": 2,
            "job_id": "sys_job_check_letsencrypt_001",
            "name": "续签Let's Encrypt证书",
            "is_sys": 0,
            "status": 1,
            "period_type": 1,
            "year": 0,
            "month": 0,
            "week": 0,
            "day": 0,
            "hour": 1,
            "minute": 30,
            "second": 0,
            "shell_body": shell_body2,
        },
        {
            "id": 3,
            "job_id": "sys_job_clean_monitor_001",
            "name": "清理过期监控数据",
            "is_sys": 0,
            "status": 1,
            "period_type": 1,
            "year": 0,
            "month": 0,
            "week": 0,
            "day": 0,
            "hour": 2,
            "minute": 30,
            "second": 0,
            "shell_body": shell_body3,
        },
        {
            "id": 4,
            "job_id": "sys_job_clean_waf_logs_001",
            "name": "清理WAF攻击日志",
            "is_sys": 0,
            "status": 1,
            "period_type": 1,
            "year": 0,
            "month": 0,
            "week": 0,
            "day": 0,
            "hour": 3,
            "minute": 0,
            "second": 0,
            "shell_body": shell_body4,
        },
    ]


def init_crontab_tasks(force=False):
    """
    初始化计划任务
    
    Args:
        force: 是否强制重新初始化（删除已有数据）
    
    Returns:
        tuple: (created_count, skipped_count)
    """
    from django_apscheduler.jobstores import DjangoJobStore
    from apps.systask.models import CrontabTask
    from apps.systask.scheduler import scheduler
    from apps.systask.tasks import cronTask

    if 'default' not in scheduler._jobstores:
        scheduler.add_jobstore(DjangoJobStore(), 'default')
    
    if not scheduler.running:
        scheduler.start()
    
    data = get_default_crontab_tasks()
    
    if force:
        CrontabTask.objects.filter(id__in=[ele.get('id') for ele in data]).delete()
    
    created_count = 0
    skipped_count = 0
    
    for task_data in data:
        task_id = task_data.get("id")
        job_id = task_data.get("job_id")
        shell_body = task_data.get("shell_body")
        
        # 使用 get_or_create，存在则跳过，不存在则创建
        obj, created = CrontabTask.objects.get_or_create(
            id=task_id,
            defaults=task_data
        )
        
        if created or force:
            # 注册定时任务到调度器
            req_data = {"type": 0, "name": task_data.get("name"), "shell_body": shell_body}
            
            # 构建 cron 参数，只传递非 None 的值
            cron_kwargs = {
                'second': task_data.get("second", 0) or 0,
                'minute': task_data.get("minute", 0) or 0,
                'hour': task_data.get("hour", 0) or 0,
                'day': task_data.get("day") if task_data.get("day") not in [None, 0] else '*',
                'month': task_data.get("month") if task_data.get("month") not in [None, 0] else '*',
                'week': task_data.get("week") if task_data.get("week") not in [None, 0] else '*',
            }
            
            scheduler.add_job(
                cronTask,
                'cron',
                id=job_id,
                args=[req_data, job_id],
                max_instances=1,
                replace_existing=True,
                misfire_grace_time=1,
                coalesce=True,
                **cron_kwargs
            )
            created_count += 1
        else:
            skipped_count += 1
    
    return created_count, skipped_count
