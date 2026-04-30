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

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.syswaf.views.waf_views import (
    WafGlobalConfigViewSet, WafSiteConfigViewSet, WafRuleCategoryViewSet,
    WafRuleViewSet, WafIpGroupViewSet, WafIpListViewSet,
    WafAttackLogViewSet, WafUrlWhitelistViewSet, WafUrlBlacklistViewSet,
    WafUaListViewSet, WafDashboardView, WafInternalApiView
)

router = DefaultRouter()
router.register(r'global-config', WafGlobalConfigViewSet, basename='waf-global-config')
router.register(r'site-config', WafSiteConfigViewSet, basename='waf-site-config')
router.register(r'rule-categories', WafRuleCategoryViewSet, basename='waf-rule-category')
router.register(r'rules', WafRuleViewSet, basename='waf-rule')
router.register(r'ip-groups', WafIpGroupViewSet, basename='waf-ip-group')
router.register(r'ip-list', WafIpListViewSet, basename='waf-ip-list')
router.register(r'attack-logs', WafAttackLogViewSet, basename='waf-attack-log')
router.register(r'url-whitelist', WafUrlWhitelistViewSet, basename='waf-url-whitelist')
router.register(r'url-blacklist', WafUrlBlacklistViewSet, basename='waf-url-blacklist')
router.register(r'ua-list', WafUaListViewSet, basename='waf-ua-list')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', WafDashboardView.as_view(), name='waf-dashboard'),
    path('internal/', WafInternalApiView.as_view(), name='waf-internal'),
]
