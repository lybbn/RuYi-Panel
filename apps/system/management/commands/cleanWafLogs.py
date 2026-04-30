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

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.syswaf.models import WafGlobalConfig, WafAttackLog


class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-01-01
    @name:清理WAF攻击日志命令: python manage.py cleanWafLogs
    @使用场景：定时清理过期的WAF攻击日志
    """
    
    help = '清理过期的WAF攻击日志'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='保留天数，不指定则使用全局配置',
        )
    
    def handle(self, *args, **options):
        days = options.get('days')
        
        if days is None:
            try:
                config = WafGlobalConfig.get_instance()
                days = config.log_retention_days
            except:
                days = 30
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count, _ = WafAttackLog.objects.filter(
            create_at__lt=cutoff_date
        ).delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'成功清理 {deleted_count} 条 {days} 天前的WAF攻击日志'
            )
        )
