# -*- coding: utf-8 -*-

"""
@Remark: 日志路由
"""
from django.urls import path, re_path
from rest_framework import routers

from apps.syslogs.logViews import RYOPLogsManageView

system_url = routers.SimpleRouter()
# system_url.register(r'terminal', TerminalServerViewSet)

urlpatterns = [
    path('opLog/', RYOPLogsManageView.as_view(), name='操作日志'),
]
urlpatterns += system_url.urls
