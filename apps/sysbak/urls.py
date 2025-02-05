# -*- coding: utf-8 -*-

"""
@Remark: 日志路由
"""
from django.urls import path, re_path
from rest_framework import routers

from apps.sysbak.bakViews import RuyiBackupManageView

system_url = routers.SimpleRouter()
# system_url.register(r'backup', RuyiBackupManageView)

urlpatterns = [
    path('backup/', RuyiBackupManageView.as_view(), name='备份'),
]
urlpatterns += system_url.urls
