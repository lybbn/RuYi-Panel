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

from django.apps import AppConfig

class SysalertConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sysalert'
    verbose_name = '告警系统'
