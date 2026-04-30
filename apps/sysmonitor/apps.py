#!/bin/python
#coding: utf-8
from django.apps import AppConfig


class SysmonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sysmonitor'
    verbose_name = "系统监控"
    app_label = 'sysmonitor'

