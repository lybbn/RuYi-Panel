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
from .views import (
    SyscheckScanView, SyscheckProgressView, SyscheckResultView,
    SyscheckSummaryView, SyscheckIgnoreView, SyscheckRecheckView,
)

urlpatterns = [
    path('scan/', SyscheckScanView.as_view(), name='syscheck_scan'),
    path('progress/', SyscheckProgressView.as_view(), name='syscheck_progress'),
    path('result/', SyscheckResultView.as_view(), name='syscheck_result'),
    path('summary/', SyscheckSummaryView.as_view(), name='syscheck_summary'),
    path('ignore/', SyscheckIgnoreView.as_view(), name='syscheck_ignore'),
    path('recheck/', SyscheckRecheckView.as_view(), name='syscheck_recheck'),
]
