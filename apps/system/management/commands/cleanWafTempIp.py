#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Copyright (c) 如意面板 All rights reserved.
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.syswaf.models import WafIpList, WafGlobalConfig


class Command(BaseCommand):
    """
    清理过期的WAF临时封禁IP: python manage.py cleanWafTempIp
    定时清理已过期超过指定天数的临时封禁IP记录（过期后已自动标记为禁用）
    """

    help = '清理过期的WAF临时封禁IP记录'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='清理过期超过多少天的临时封禁IP记录，不指定则使用全局配置',
        )

    def handle(self, *args, **options):
        days = options.get('days')

        if days is None:
            try:
                config = WafGlobalConfig.get_instance()
                days = config.ip_list_retention_days
            except Exception:
                days = 1

        # 先将已过期但仍为enabled的临时封禁IP标记为禁用
        disabled_count = WafIpList.objects.filter(
            list_type='temp',
            expire_at__isnull=False,
            expire_at__lt=timezone.now(),
            enabled=True
        ).update(enabled=False)

        # days=0 表示永久保留，只标记禁用不删除
        if days == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'已禁用 {disabled_count} 条过期临时封禁IP，'
                    f'过期IP名单保留天数设为0，不执行删除'
                )
            )
            return

        cutoff_date = timezone.now() - timedelta(days=days)

        # 删除过期超过指定天数的临时封禁IP记录
        deleted_count, _ = WafIpList.objects.filter(
            list_type='temp',
            expire_at__isnull=False,
            expire_at__lt=cutoff_date
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'已禁用 {disabled_count} 条过期临时封禁IP，'
                f'清理 {deleted_count} 条过期超过{days}天的临时封禁IP记录'
            )
        )
