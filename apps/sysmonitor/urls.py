# -*- coding: utf-8 -*-

"""
@Remark: 监控路由
"""
from django.urls import path

from apps.sysmonitor.views import (
    MonitorConfigView, MonitorClearLogsView, MonitorHistoryDataView,
    MonitorCollectDataView, MonitorDevicesView
)

urlpatterns = [
    path('config/', MonitorConfigView.as_view(), name='监控配置'),
    path('clearLogs/', MonitorClearLogsView.as_view(), name='清空监控日志'),
    path('history/', MonitorHistoryDataView.as_view(), name='监控历史数据'),
    path('collect/', MonitorCollectDataView.as_view(), name='采集监控数据'),
    path('devices/', MonitorDevicesView.as_view(), name='获取网卡磁盘列表'),
]
