# -*- coding: utf-8 -*-

"""
@Remark: 备份路由
"""
from django.urls import path, re_path
from rest_framework import routers

from apps.sysbak.bakViews import RuyiBackupManageView
from apps.sysbak.panelBackupViews import PanelBackupManageView, BackupScheduleManageView

system_url = routers.SimpleRouter()

urlpatterns = [
    path('backup/', RuyiBackupManageView.as_view(), name='备份'),
    path('panel_backup/', PanelBackupManageView.as_view(), name='面板备份还原'),
    path('backup_schedule/', BackupScheduleManageView.as_view(), name='备份计划'),
]
urlpatterns += system_url.urls
