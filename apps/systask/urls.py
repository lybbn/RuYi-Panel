# -*- coding: utf-8 -*-

"""
@Remark: 定时任务路由
"""
from django.urls import path, re_path
from rest_framework import routers

from apps.systask.views.crontab_task import CrontabTaskViewSet,GetDjangoJobExecutionView
from apps.systask.views.systaskcenter import RYSystemTaskCenterView

system_url = routers.SimpleRouter()
system_url.register(r'contab', CrontabTaskViewSet)

urlpatterns = [
    path('contab/status/<str:pk>/', CrontabTaskViewSet.as_view({'put': 'status'}), name='停止/启动任务'),
    path('contab/runtask/<str:pk>/', CrontabTaskViewSet.as_view({'put': 'runtask'}), name='立即执行任务'),
    path('contab/logs/', GetDjangoJobExecutionView.as_view(), name='日志'),
    path('contab/delLogs/', CrontabTaskViewSet.as_view({'post': 'deleteLogs'}), name='清空任务日志'),
    path('contab/runlogs/', CrontabTaskViewSet.as_view({'get': 'run_logs'}), name='获取执行日志'),
    path('systaskcenter/', RYSystemTaskCenterView.as_view(), name='获取系统任务中心'),
]
urlpatterns += system_url.urls
