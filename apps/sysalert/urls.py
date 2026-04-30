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

from django.urls import path
from . import views

urlpatterns = [
    # 通知渠道
    path('notify-config/', views.AlertNotifyConfigListView.as_view(), name='alert_notify_config_list'),
    path('notify-config/<int:pk>/', views.AlertNotifyConfigDetailView.as_view(), name='alert_notify_config_detail'),
    path('notify-config/<int:pk>/test/', views.AlertNotifyConfigTestView.as_view(), name='alert_notify_config_test'),
    path('notify-config/<int:pk>/toggle/', views.AlertNotifyConfigToggleView.as_view(), name='alert_notify_config_toggle'),
    
    # 告警任务
    path('task/', views.AlertTaskListView.as_view(), name='alert_task_list'),
    path('task/<int:pk>/', views.AlertTaskDetailView.as_view(), name='alert_task_detail'),
    path('task/<int:pk>/toggle/', views.AlertTaskToggleView.as_view(), name='alert_task_toggle'),
    
    # 告警日志
    path('log/', views.AlertLogListView.as_view(), name='alert_log_list'),
    path('log/<int:pk>/', views.AlertLogDetailView.as_view(), name='alert_log_detail'),
    path('log/clear/', views.AlertLogClearView.as_view(), name='alert_log_clear'),
    
    # 其他
    path('task-types/', views.AlertTaskTypeListView.as_view(), name='alert_task_types'),
    path('channel-types/', views.AlertChannelTypeListView.as_view(), name='alert_channel_types'),
    path('dashboard-stats/', views.AlertDashboardStatsView.as_view(), name='alert_dashboard_stats'),
]
