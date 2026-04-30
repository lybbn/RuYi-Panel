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
# SSL证书检查命令
# 用于定时任务检查SSL证书过期
# ------------------------------

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruyi.settings')
django.setup()

import logging
from django.core.management.base import BaseCommand
from apps.sysalert.tasks import check_ssl_expire

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-09-21
    @EditData:2024-09-21
    @Email:1042594286@qq.com
    @name:SSL证书检查命令: python manage.py checkSSL
    @使用场景：定时检查SSL证书过期情况
    """

    def handle(self, *args, **options):
        print("开始检查SSL证书过期情况...")
        try:
            check_ssl_expire()
            print("SSL证书检查完成")
        except Exception as e:
            print(f"SSL证书检查失败: {e}")
            logger.error(f"SSL证书检查失败: {e}")
