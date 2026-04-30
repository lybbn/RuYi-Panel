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

# ------------------------------
# 管理监控定时任务命令
# ------------------------------

from django.core.management.base import BaseCommand
from apps.sysmonitor.tasks import (
    register_monitor_task, remove_monitor_task, 
    toggle_monitor_task, get_monitor_config
)

class Command(BaseCommand):
    help = '管理监控数据采集定时任务'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['register', 'remove', 'enable', 'disable', 'status'],
            default='register',
            help='操作类型: register-注册, remove-移除, enable-启用, disable-禁用, status-查看状态'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'register':
            register_monitor_task()
            self.stdout.write(self.style.SUCCESS('监控数据采集任务注册成功'))
            
        elif action == 'remove':
            remove_monitor_task()
            self.stdout.write(self.style.SUCCESS('监控数据采集任务已移除'))
            
        elif action == 'enable':
            toggle_monitor_task(True)
            self.stdout.write(self.style.SUCCESS('监控数据采集任务已启用'))
            
        elif action == 'disable':
            toggle_monitor_task(False)
            self.stdout.write(self.style.SUCCESS('监控数据采集任务已禁用'))
            
        elif action == 'status':
            from apps.systask.scheduler import scheduler
            from apps.sysmonitor.tasks import MONITOR_COLLECT_JOB_ID
            
            job = scheduler.get_job(MONITOR_COLLECT_JOB_ID)
            config = get_monitor_config()
            
            self.stdout.write('========== 监控任务状态 ==========')
            
            if config:
                self.stdout.write(f"监控开关: {'开启' if config.is_enabled else '关闭'}")
                self.stdout.write(f"采集间隔: {config.collect_interval}秒")
                self.stdout.write(f"日志保留: {config.log_save_days}天")
            else:
                self.stdout.write(self.style.WARNING("未找到监控配置"))
            
            if job:
                self.stdout.write(self.style.SUCCESS(f"定时任务: 运行中"))
                self.stdout.write(f"下次执行: {job.next_run_time}")
            else:
                self.stdout.write(self.style.WARNING("定时任务: 未运行"))
