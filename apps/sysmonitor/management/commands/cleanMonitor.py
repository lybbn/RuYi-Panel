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
# 清理过期监控数据命令
# ------------------------------

from django.core.management.base import BaseCommand
from apps.sysmonitor.views import MonitorDataCollector
from apps.sysmonitor.models import MonitorConfig

class Command(BaseCommand):
    help = '清理过期监控数据'

    def handle(self, *args, **options):
        try:
            config = MonitorConfig.objects.first()
            if not config:
                print("未找到监控配置")
                return
            
            days = config.log_save_days
            MonitorDataCollector.clean_old_data(days)
            print(f"成功清理 {days} 天前的监控数据")
            
        except Exception as e:
           print(f"清理监控数据失败: {e}")
