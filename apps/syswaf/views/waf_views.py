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

import json
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate, TruncHour, TruncDay, TruncMinute
from datetime import datetime, timedelta

def _naive_parse_dt(s):
    """解析ISO格式日期字符串并去除时区信息，兼容SQLite (USE_TZ=False)"""
    if isinstance(s, datetime):
        return s.replace(tzinfo=None)
    s = s.strip().replace('Z', '+00:00')
    return datetime.fromisoformat(s).replace(tzinfo=None)

from utils.viewset import CustomModelViewSet
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from apps.syswaf.models import (
    WafGlobalConfig, WafSiteConfig, WafRuleCategory, WafRule,
    WafIpGroup, WafIpList, WafAttackLog, WafUrlWhitelist,
    WafUrlBlacklist, WafUaList
)
from apps.syswaf.serializers import (
    WafGlobalConfigSerializer, WafGlobalConfigUpdateSerializer,
    WafSiteConfigSerializer, WafSiteConfigUpdateSerializer,
    WafRuleCategorySerializer, WafRuleSerializer, WafRuleCreateUpdateSerializer,
    WafIpGroupSerializer, WafIpListSerializer, WafIpListCreateUpdateSerializer,
    WafAttackLogSerializer, WafUrlWhitelistSerializer, WafDashboardStatsSerializer,
    WafUrlBlacklistSerializer, WafUaListSerializer
)
from apps.syswaf.services import WafConfigSync
from utils.ruyiclass.nginxClass import NginxClient
from utils.ip_util import IPQQwry, GeoIP2Lookup, get_server_location, get_ip_location_with_coords
from utils.common import is_private_ip
from apps.syslogs.logutil import RuyiAddOpLog


class WafGlobalConfigViewSet(CustomModelViewSet):
    queryset = WafGlobalConfig.objects.all()
    serializer_class = WafGlobalConfigSerializer
    update_serializer_class = WafGlobalConfigUpdateSerializer
    
    def get_object(self):
        return WafGlobalConfig.get_instance()
    
    def list(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        return DetailResponse(data=data, msg="获取成功")
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, request=request, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        sync = WafConfigSync()
        sync.sync_global_config()
        RuyiAddOpLog(request, msg="【WAF防护】-【全局配置】-【更新】", module="wafmg")
        return DetailResponse(data=serializer.data, msg="更新成功")
    
    @action(methods=['POST'], detail=False)
    def set_status(self, request):
        status = request.data.get('status')
        if status not in ['off', 'observe', 'protect']:
            return ErrorResponse(msg="无效的状态")
        instance = self.get_object()
        old_status = instance.waf_status
        
        instance.waf_status = status
        instance.save()
        sync = WafConfigSync()
        sync.sync_global_config()
        status_display = {'off': '关闭', 'observe': '观察模式', 'protect': '防护模式'}
        RuyiAddOpLog(request, msg=f"【WAF防护】-【全局状态】切换为{status_display.get(status, status)}", module="wafmg")
        return DetailResponse(msg=f"WAF已切换为{status_display.get(status, status)}")
    
    @action(methods=['POST'], detail=False)
    def save_cc_config(self, request):
        instance = self.get_object()
        cc_config = request.data.get('cc_config', {})
        instance.set_config('cc_config', cc_config)
        instance.save()
        sync = WafConfigSync()
        sync.sync_global_config()
        RuyiAddOpLog(request, msg="【WAF防护】-【CC防护配置】保存", module="wafmg")
        return DetailResponse(msg="CC防护配置保存成功")
    
    @action(methods=['POST'], detail=False)
    def save_request_limit_config(self, request):
        instance = self.get_object()
        request_limit_config = request.data.get('request_limit_config', {})
        instance.set_config('request_limit_config', request_limit_config)
        instance.save()
        sync = WafConfigSync()
        sync.sync_global_config()
        RuyiAddOpLog(request, msg="【WAF防护】-【HTTP请求过滤配置】保存", module="wafmg")
        return DetailResponse(msg="HTTP请求过滤配置保存成功")
    
    @action(methods=['POST'], detail=False)
    def save_geo_config(self, request):
        instance = self.get_object()
        geo_config = request.data.get('geo_config', {})
        instance.set_config('geo_config', geo_config)
        instance.save()
        sync = WafConfigSync()
        sync.sync_global_config()
        RuyiAddOpLog(request, msg="【WAF防护】-【地域限制配置】保存", module="wafmg")
        return DetailResponse(msg="地域限制配置保存成功")
    
    @action(methods=['POST'], detail=False)
    def save_cdn_config(self, request):
        instance = self.get_object()
        cdn_config = request.data.get('cdn_config', {})
        instance.set_config('cdn_config', cdn_config)
        instance.save()
        sync = WafConfigSync()
        sync.sync_global_config()
        RuyiAddOpLog(request, msg="【WAF防护】-【CDN兼容配置】保存", module="wafmg")
        return DetailResponse(msg="CDN兼容配置保存成功")
    
    @action(methods=['POST'], detail=False)
    def save_rule_config(self, request):
        instance = self.get_object()
        rule_config = request.data.get('rule_config', {})
        instance.set_config('rule_config', rule_config)
        instance.save()
        sync = WafConfigSync()
        sync.sync_global_config()
        RuyiAddOpLog(request, msg="【WAF防护】-【攻击防护规则配置】保存", module="wafmg")
        return DetailResponse(msg="攻击防护规则配置保存成功")
    
    @action(methods=['POST'], detail=False)
    def save_block_page_config(self, request):
        instance = self.get_object()
        block_page_config = request.data.get('block_page_config', {})
        instance.set_config('block_page_config', block_page_config)
        instance.save()
        sync = WafConfigSync()
        sync.sync_global_config()
        RuyiAddOpLog(request, msg="【WAF防护】-【拦截页面配置】保存", module="wafmg")
        return DetailResponse(msg="拦截页面配置保存成功")

    @action(methods=['POST'], detail=False)
    def save_data_retention_config(self, request):
        instance = self.get_object()
        log_retention_days = request.data.get('log_retention_days')
        ip_list_retention_days = request.data.get('ip_list_retention_days')
        if log_retention_days is not None:
            instance.log_retention_days = int(log_retention_days)
        if ip_list_retention_days is not None:
            instance.ip_list_retention_days = int(ip_list_retention_days)
        instance.save()
        RuyiAddOpLog(request, msg="【WAF防护】-【数据清理配置】保存", module="wafmg")
        return DetailResponse(msg="数据清理配置保存成功")
    
    @action(methods=['GET'], detail=False)
    def get_all_lists(self, request):
        def format_datetime(dt):
            if dt:
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            return ''
        
        ip_white = list(WafIpList.objects.filter(site_id=None, list_type='whitelist').values('id', 'ip', 'remark', 'create_at'))
        for item in ip_white:
            item['create_at'] = format_datetime(item.get('create_at'))
        
        ip_black = list(WafIpList.objects.filter(site_id=None, list_type='blacklist').values('id', 'ip', 'remark', 'create_at'))
        for item in ip_black:
            item['create_at'] = format_datetime(item.get('create_at'))
        
        url_white = list(WafUrlWhitelist.objects.filter(site_id=None).values('id', 'url', 'remark', 'create_at'))
        for item in url_white:
            item['create_at'] = format_datetime(item.get('create_at'))
        
        url_black = list(WafUrlBlacklist.objects.filter(site_id=None).values('id', 'url', 'remark', 'create_at'))
        for item in url_black:
            item['create_at'] = format_datetime(item.get('create_at'))
        
        ua_white = list(WafUaList.objects.filter(site_id=None, list_type='whitelist').values('id', 'keyword', 'remark', 'create_at'))
        for item in ua_white:
            item['create_at'] = format_datetime(item.get('create_at'))
        
        ua_black = list(WafUaList.objects.filter(site_id=None, list_type='blacklist').values('id', 'keyword', 'remark', 'create_at'))
        for item in ua_black:
            item['create_at'] = format_datetime(item.get('create_at'))
        
        return DetailResponse(data={
            'ip_whitelist': ip_white,
            'ip_blacklist': ip_black,
            'url_whitelist': url_white,
            'url_blacklist': url_black,
            'ua_whitelist': ua_white,
            'ua_blacklist': ua_black,
        }, msg="获取成功")


class WafSiteConfigViewSet(CustomModelViewSet):
    queryset = WafSiteConfig.objects.all()
    serializer_class = WafSiteConfigSerializer
    update_serializer_class = WafSiteConfigUpdateSerializer
    filterset_fields = ('site_id',)
    
    def get_queryset(self):
        from apps.system.models import Sites
        all_sites = Sites.objects.filter(type=0)
        for site in all_sites:
            WafSiteConfig.objects.get_or_create(
                site_id=site.id,
                defaults={'site_name': site.name}
            )
        queryset = super().get_queryset()
        site_id = self.request.query_params.get('site_id')
        if site_id:
            queryset = queryset.filter(site_id=site_id)
        return queryset
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, request=request)
        serializer.is_valid(raise_exception=True)
        
        self.perform_create(serializer)
        
        if serializer.data.get('waf_status') != 'off' and serializer.data.get('site_id'):
            from apps.system.models import Sites
            site = Sites.objects.filter(id=serializer.data['site_id']).first()
            if site:
                nginx = NginxClient(siteName=site.name)
                ok, msg = nginx.set_site_waf(enabled=True, site_id=serializer.data['site_id'])
                if not ok:
                    return ErrorResponse(msg=f"WAF配置失败：{msg}")
        
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】新增站点WAF", module="wafmg")
        return DetailResponse(data=serializer.data, msg="新增成功")
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_status = instance.waf_status
        
        serializer = self.get_serializer(instance, data=request.data, request=request, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        new_status = instance.waf_status
        old_enabled = old_status != 'off'
        new_enabled = new_status != 'off'
        if old_enabled != new_enabled:
            site = instance.site
            if site:
                nginx = NginxClient(siteName=site.name)
                ok, msg = nginx.set_site_waf(enabled=new_enabled, site_id=instance.site_id)
                if not ok:
                    return ErrorResponse(msg=f"WAF配置失败：{msg}")
        
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】更新 {instance.site_name or ''}", module="wafmg")
        return DetailResponse(data=serializer.data, msg="更新成功")
    
    @action(methods=['POST'], detail=True)
    def set_status(self, request, pk=None):
        status = request.data.get('status')
        if status not in ['off', 'observe', 'protect']:
            return ErrorResponse(msg="无效的状态")
        instance = self.get_object()
        old_status = instance.waf_status
        
        instance.waf_status = status
        instance.save()
        
        old_enabled = old_status != 'off'
        new_enabled = status != 'off'
        if old_enabled != new_enabled:
            site = instance.site
            if site:
                nginx = NginxClient(siteName=site.name)
                ok, msg = nginx.set_site_waf(enabled=new_enabled, site_id=instance.site_id)
                if not ok:
                    instance.waf_status = old_status
                    instance.save()
                    return ErrorResponse(msg=f"WAF配置失败：{msg}")
        
        status_display = {'off': '关闭', 'observe': '观察模式', 'protect': '防护模式'}
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点WAF】{instance.site_name or ''} 切换为{status_display.get(status, status)}", module="wafmg")
        return DetailResponse(msg=f"站点WAF已切换为{status_display.get(status, status)}")
    
    @action(methods=['POST'], detail=True)
    def reset_stats(self, request, pk=None):
        instance = self.get_object()
        instance.stats_blocked_today = 0
        instance.stats_blocked_total = 0
        instance.save()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】{instance.site_name or ''} 重置统计数据", module="wafmg")
        return DetailResponse(msg="统计数据已重置")
    
    @action(methods=['POST'], detail=False)
    def batch_update(self, request):
        ids = request.data.get('ids', [])
        updates = request.data.get('updates', {})
        if not ids or not updates:
            return ErrorResponse(msg="参数错误")
        WafSiteConfig.objects.filter(id__in=ids).update(**updates)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】批量更新{len(ids)}个站点", module="wafmg")
        return DetailResponse(msg=f"已批量更新{len(ids)}个站点配置")
    
    @action(methods=['POST'], detail=True)
    def save_basic(self, request, pk=None):
        instance = self.get_object()
        status = request.data.get('waf_status')
        if status and status in ['off', 'observe', 'protect']:
            instance.waf_status = status
        instance.save()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】{instance.site_name or ''} 保存基础配置", module="wafmg")
        return DetailResponse(msg="基础配置保存成功")

    @action(methods=['POST'], detail=True)
    def save_cdn(self, request, pk=None):
        instance = self.get_object()
        instance.cdn_enabled = request.data.get('cdn_enabled', False)
        instance.cdn_provider = request.data.get('cdn_provider', 'auto')
        if 'cdn_headers' in request.data:
            instance.cdn_headers = json.dumps(request.data['cdn_headers'], ensure_ascii=False)
        if 'cdn_ip_groups' in request.data:
            instance.cdn_ip_groups = json.dumps(request.data['cdn_ip_groups'], ensure_ascii=False)
        if 'cdn_ip_position' in request.data:
            instance.cdn_ip_position = request.data['cdn_ip_position']
        instance.save()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】{instance.site_name or ''} 保存CDN配置", module="wafmg")
        return DetailResponse(msg="CDN配置保存成功")

    @action(methods=['POST'], detail=True)
    def save_cc(self, request, pk=None):
        instance = self.get_object()
        instance.inherit_cc = request.data.get('inherit_cc', True)
        if not instance.inherit_cc and 'cc_config' in request.data:
            instance.set_config('cc_config', request.data['cc_config'])
        instance.save()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】{instance.site_name or ''} 保存CC防护配置", module="wafmg")
        return DetailResponse(msg="CC防护配置保存成功")

    @action(methods=['POST'], detail=True)
    def save_geo(self, request, pk=None):
        instance = self.get_object()
        instance.inherit_geo = request.data.get('inherit_geo', True)
        if not instance.inherit_geo and 'geo_config' in request.data:
            instance.set_config('geo_config', request.data['geo_config'])
        instance.save()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】{instance.site_name or ''} 保存地域限制配置", module="wafmg")
        return DetailResponse(msg="地域限制配置保存成功")

    @action(methods=['POST'], detail=True)
    def save_rule(self, request, pk=None):
        instance = self.get_object()
        instance.inherit_rule = request.data.get('inherit_rule', True)
        if not instance.inherit_rule and 'rule_config' in request.data:
            instance.set_config('rule_config', request.data['rule_config'])
        instance.save()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】{instance.site_name or ''} 保存规则配置", module="wafmg")
        return DetailResponse(msg="规则配置保存成功")

    @action(methods=['POST'], detail=True)
    def save_request_limit(self, request, pk=None):
        instance = self.get_object()
        instance.inherit_request_limit = request.data.get('inherit_request_limit', True)
        if not instance.inherit_request_limit and 'request_limit_config' in request.data:
            instance.set_config('request_limit_config', request.data['request_limit_config'])
        instance.save()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】{instance.site_name or ''} 保存请求限制配置", module="wafmg")
        return DetailResponse(msg="请求限制配置保存成功")

    @action(methods=['POST'], detail=True)
    def toggle_inherit(self, request, pk=None):
        """
        切换单个配置项的继承状态
        request.data: {'config_type': 'cc|tolerance|error_limit|geo|rule|request_limit'}
        """
        instance = self.get_object()
        config_type = request.data.get('config_type')
        if not config_type:
            return ErrorResponse(msg="缺少config_type参数")

        inherit_field = f'inherit_{config_type}'
        if not hasattr(instance, inherit_field):
            return ErrorResponse(msg="无效的config_type")

        current_value = getattr(instance, inherit_field)
        setattr(instance, inherit_field, not current_value)
        instance.save()

        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】{instance.site_name or ''} 切换{config_type}为{'继承全局' if not current_value else '独立配置'}", module="wafmg")
        return DetailResponse(data={
            'inherit_status': not current_value,
            'config_type': config_type
        }, msg=f"已切换为{'继承全局' if not current_value else '独立配置'}")
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object_list()
        for item in instance:
            site = item.site
            if site:
                nginx = NginxClient(siteName=site.name)
                nginx.set_site_waf(enabled=False, site_id=item.site_id)
        self.perform_destroy(instance)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【站点配置】删除", module="wafmg")
        return DetailResponse(data=[], msg="删除成功")


class WafRuleCategoryViewSet(CustomModelViewSet):
    queryset = WafRuleCategory.objects.all()
    serializer_class = WafRuleCategorySerializer
    filterset_fields = ('code',)
    ordering_fields = ('sort', 'id')
    pagination_class = None

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True, request=request)
        return DetailResponse(data=serializer.data, msg="获取成功")


class WafRuleViewSet(CustomModelViewSet):
    queryset = WafRule.objects.all().select_related('category')
    serializer_class = WafRuleSerializer
    create_serializer_class = WafRuleCreateUpdateSerializer
    update_serializer_class = WafRuleCreateUpdateSerializer
    filterset_fields = ('severity', 'enabled', 'is_builtin')
    search_fields = ('name', 'rule_id', 'description')
    ordering_fields = ('severity', 'trigger_count', 'create_at')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__code=category)
        return queryset
    
    def destroy(self, request, pk=None):
        instance = self.get_object()
        if instance.is_builtin:
            return ErrorResponse(msg="内置规则不允许删除")
        rule_name = instance.name
        result = super().destroy(request, pk)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【规则】删除 {rule_name}", module="wafmg")
        return result
    
    def create(self, request, *args, **kwargs):
        result = super().create(request, *args, **kwargs)
        RuyiAddOpLog(request, msg="【WAF防护】-【规则】新增", module="wafmg")
        return result

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        rule_name = instance.name
        result = super().update(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【规则】更新 {rule_name}", module="wafmg")
        return result
    
    @action(methods=['POST'], detail=True)
    def toggle(self, request, pk=None):
        instance = self.get_object()
        instance.enabled = not instance.enabled
        instance.save()
        status_text = "启用" if instance.enabled else "禁用"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【规则】{instance.name} {status_text}", module="wafmg")
        return DetailResponse(msg=f"规则已{status_text}")
    
    @action(methods=['POST'], detail=False)
    def batch_toggle(self, request):
        ids = request.data.get('ids', [])
        enabled = request.data.get('enabled', True)
        WafRule.objects.filter(id__in=ids).update(enabled=enabled)
        status_text = "启用" if enabled else "禁用"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【规则】批量{status_text}{len(ids)}条规则", module="wafmg")
        return DetailResponse(msg=f"已批量{status_text}{len(ids)}条规则")
    
    @action(methods=['POST'], detail=False)
    def batch_set_mode(self, request):
        ids = request.data.get('ids', [])
        mode = request.data.get('mode', 'block')
        if mode not in ['block', 'log', 'captcha']:
            return ErrorResponse(msg="无效的防护模式")
        WafRule.objects.filter(id__in=ids).update(mode=mode)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【规则】批量修改{len(ids)}条规则防护模式为{mode}", module="wafmg")
        return DetailResponse(msg=f"已批量修改{len(ids)}条规则的防护模式")
    
    @action(methods=['GET'], detail=False)
    def stats(self, request):
        total = WafRule.objects.count()
        enabled = WafRule.objects.filter(enabled=True).count()
        by_severity = WafRule.objects.values('severity').annotate(count=Count('id'))
        by_category = WafRule.objects.values('category__name', 'category__code').annotate(count=Count('id'))
        return DetailResponse(data={
            'total': total,
            'enabled': enabled,
            'disabled': total - enabled,
            'by_severity': list(by_severity),
            'by_category': list(by_category),
        })
    
    @action(methods=['POST'], detail=False)
    def update_from_cloud(self, request):
        """
        从云端更新WAF规则
        """
        try:
            # 调用init_waf_data强制更新规则
            from apps.syswaf.init_data import init_waf_data
            categories, rules, config, ip_group, from_remote, rules_updated = init_waf_data(force=True)
            
            source_text = "云端" if from_remote else "本地"
            
            RuyiAddOpLog(request, msg=f"【WAF防护】-【规则】从{source_text}更新规则", module="wafmg")
            return DetailResponse(data={
                'categories': categories,
                'rules': rules,
                'config': config,
                'ip_group': ip_group,
                'from_remote': from_remote
            }, msg=f"规则更新成功：从{source_text}新增{categories}个分类，{rules}条规则")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"从云端更新WAF规则失败: {e}")
            return ErrorResponse(msg=f"规则更新失败: {str(e)}")


class WafIpGroupViewSet(CustomModelViewSet):
    queryset = WafIpGroup.objects.all()
    serializer_class = WafIpGroupSerializer
    search_fields = ('name',)
    ordering_fields = ('create_at',)
    
    def create(self, request, *args, **kwargs):
        result = super().create(request, *args, **kwargs)
        RuyiAddOpLog(request, msg="【WAF防护】-【IP分组】新增", module="wafmg")
        return result

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name
        result = super().update(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP分组】更新 {name}", module="wafmg")
        return result

    def destroy(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        if not pk:
            return DetailResponse(data=[], msg="删除成功")
        
        try:
            instance = self.get_queryset().get(pk=pk)
            WafIpList.objects.filter(group=instance).update(group=None)
            instance.delete()
            RuyiAddOpLog(request, msg=f"【WAF防护】-【IP分组】删除 {instance.name}", module="wafmg")
            return DetailResponse(data=[], msg="删除成功")
        except WafIpGroup.DoesNotExist:
            return DetailResponse(data=[], msg="分组不存在")


class WafIpListViewSet(CustomModelViewSet):
    queryset = WafIpList.objects.all()
    serializer_class = WafIpListSerializer
    create_serializer_class = WafIpListCreateUpdateSerializer
    update_serializer_class = WafIpListCreateUpdateSerializer
    filterset_fields = ('list_type', 'entry_type', 'source', 'enabled', 'site_id', 'ip_version')
    search_fields = ('ip', 'remark', 'location')
    ordering_fields = ('create_at', 'trigger_count')

    def get_queryset(self):
        from django.utils import timezone
        # 自动将已过期的临时封禁IP标记为禁用（保留记录便于审计）
        WafIpList.objects.filter(
            list_type='temp',
            expire_at__isnull=False,
            expire_at__lt=timezone.now(),
            enabled=True
        ).update(enabled=False)
        return super().get_queryset()
    
    def create(self, request, *args, **kwargs):
        ip = request.data.get('ip')
        list_type = request.data.get('list_type', 'blacklist')
        
        if ip and list_type in ['blacklist', 'whitelist']:
            exists = WafIpList.objects.filter(ip=ip, list_type=list_type).exists()
            if exists:
                return ErrorResponse(msg=f"IP {ip} 已在{('黑名单' if list_type == 'blacklist' else '白名单')}中")
        
        result = super().create(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP名单】新增 {ip or ''}", module="wafmg")
        return result
    
    def perform_create(self, serializer):
        ip = serializer.validated_data.get('ip')
        location = self._get_ip_location(ip)
        serializer.save(location=location)
    
    def perform_update(self, serializer):
        ip = serializer.validated_data.get('ip')
        if ip:
            location = self._get_ip_location(ip)
            serializer.save(location=location)
        else:
            serializer.save()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        ip_addr = instance.ip
        result = super().update(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP名单】更新 {ip_addr}", module="wafmg")
        return result

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        ip_addr = instance.ip
        result = super().destroy(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP名单】删除 {ip_addr}", module="wafmg")
        return result
    
    def _get_ip_location(self, ip):
        if not ip:
            return ''
        try:
            clean_ip = ip.split('/')[0].strip()
        except:
            return ''
        if not clean_ip:
            return ''
        try:
            if is_private_ip(clean_ip):
                return '局域网IP'
        except:
            pass
        # 优先使用 GeoIP2（和攻击日志一致，支持IPv4/IPv6，返回结构化数据）
        try:
            geo_data = GeoIP2Lookup.lookup(clean_ip)
            if geo_data and geo_data.get('location'):
                return geo_data['location']
        except:
            pass
        # 回退到 QQwry
        try:
            results = IPQQwry.get_local_ips_area([clean_ip])
            if results and results[0]:
                return results[0]
        except:
            pass
        return ''
    
    @action(methods=['POST'], detail=False)
    def batch_import(self, request):
        ips = request.data.get('ips', [])
        list_type = request.data.get('list_type', 'blacklist')
        remark = request.data.get('remark', '批量导入')
        group_id = request.data.get('group')
        
        created_count = 0
        for ip in ips:
            ip = ip.strip()
            if not ip:
                continue
            location = self._get_ip_location(ip)
            _, created = WafIpList.objects.get_or_create(
                ip=ip,
                list_type=list_type,
                defaults={
                    'remark': remark,
                    'source': 'import',
                    'location': location,
                    'group_id': group_id
                }
            )
            if created:
                created_count += 1
        
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP名单】批量导入{created_count}条IP到{'黑名单' if list_type == 'blacklist' else '白名单'}", module="wafmg")
        return DetailResponse(msg=f"成功导入{created_count}条IP")
    
    @action(methods=['POST'], detail=False)
    def batch_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return ErrorResponse(msg="请选择要删除的IP")
        
        deleted_count = WafIpList.objects.filter(id__in=ids).count()
        WafIpList.objects.filter(id__in=ids).delete()
        
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP名单】批量删除{deleted_count}条IP", module="wafmg")
        return DetailResponse(msg=f"成功删除{deleted_count}条IP")

    @action(methods=['POST'], detail=False)
    def refresh_location(self, request):
        """批量刷新IP归属地（刷新location为空的记录，或全部刷新）"""
        refresh_all = request.data.get('refresh_all', False)
        if refresh_all:
            ip_list = WafIpList.objects.exclude(entry_type='group').exclude(ip='')
        else:
            ip_list = WafIpList.objects.filter(location='').exclude(entry_type='group').exclude(ip='')
        
        updated = 0
        for item in ip_list:
            location = self._get_ip_location(item.ip)
            if location:
                item.location = location
                item.save(update_fields=['location'])
                updated += 1
        
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP名单】刷新归属地{updated}条", module="wafmg")
        return DetailResponse(data={'updated': updated}, msg=f"已刷新{updated}条IP归属地")
    
    @action(methods=['POST'], detail=True)
    def toggle(self, request, pk=None):
        instance = self.get_object()
        instance.enabled = not instance.enabled
        instance.save()
        status_text = "启用" if instance.enabled else "禁用"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP名单】{instance.ip} {status_text}", module="wafmg")
        return DetailResponse(msg=f"IP已{status_text}")
    
    @action(methods=['POST'], detail=False)
    def toggle_global_switch(self, request):
        list_type = request.data.get('list_type')
        if not list_type:
            return ErrorResponse(msg="缺少list_type参数")
        
        switch, _ = WafIpList.objects.get_or_create(
            list_type=list_type,
            remark='__GLOBAL_SWITCH__',
            site_id=None,
            defaults={'ip': '', 'enabled': True, 'source': 'manual'}
        )
        switch.enabled = not switch.enabled
        switch.save()
        status_text = "开启" if switch.enabled else "关闭"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【IP名单】{'黑名单' if list_type == 'blacklist' else '白名单'} 全局{status_text}", module="wafmg")
        return DetailResponse(data={'enabled': switch.enabled}, msg=f"已{status_text}")
    
    @action(methods=['GET'], detail=False)
    def get_global_switch(self, request):
        list_type = request.query_params.get('list_type')
        if not list_type:
            return ErrorResponse(msg="缺少list_type参数")
        
        try:
            switch = WafIpList.objects.get(
                list_type=list_type,
                remark='__GLOBAL_SWITCH__',
                site_id=None
            )
            return DetailResponse(data={'enabled': switch.enabled})
        except WafIpList.DoesNotExist:
            return DetailResponse(data={'enabled': True})


class WafAttackLogViewSet(CustomModelViewSet):
    queryset = WafAttackLog.objects.all()
    serializer_class = WafAttackLogSerializer
    filterset_fields = ('site_id', 'attack_type', 'action_taken', 'src_ip', 'is_false_positive', 'dst_url')
    search_fields = ('src_ip', 'dst_url', 'attack_type')
    ordering_fields = ('create_at', 'severity')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # 支持前端全局时间选择器传入的 start_time/end_time
        start_time = self.request.query_params.get('start_time')
        end_time = self.request.query_params.get('end_time')
        # 兼容旧参数名
        if not start_time:
            start_time = self.request.query_params.get('start_date')
        if not end_time:
            end_time = self.request.query_params.get('end_date')
        if start_time:
            try:
                queryset = queryset.filter(create_at__gte=_naive_parse_dt(start_time))
            except Exception:
                queryset = queryset.filter(create_at__gte=start_time)
        if end_time:
            try:
                queryset = queryset.filter(create_at__lte=_naive_parse_dt(end_time))
            except Exception:
                queryset = queryset.filter(create_at__lte=end_time)
        # 支持逗号分隔的 severity 过滤（如 critical,high）
        severity = self.request.query_params.get('severity')
        if severity and ',' in severity:
            severity_list = [s.strip() for s in severity.split(',') if s.strip()]
            queryset = queryset.filter(severity__in=severity_list)
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        ip_today_count = WafAttackLog.objects.filter(
            src_ip=instance.src_ip,
            create_at__gte=today_start
        ).count()
        
        ip_total_count = WafAttackLog.objects.filter(src_ip=instance.src_ip).count()
        
        confidence = self._calculate_confidence(instance)
        
        data['ip_today_attacks'] = ip_today_count
        data['ip_total_attacks'] = ip_total_count
        data['confidence'] = confidence
        
        return DetailResponse(data=data)
    
    def _calculate_confidence(self, log):
        base_confidence = 70
        severity_scores = {'critical': 25, 'high': 20, 'medium': 10, 'low': 5}
        base_confidence += severity_scores.get(log.severity, 10)
        if log.matched_pattern:
            base_confidence += 10
        if log.attack_type in ['sql_injection', 'xss', 'command_injection']:
            base_confidence += 5
        return min(base_confidence, 100)
    
    @action(methods=['GET'], detail=False)
    def stats(self, request):
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        
        if start_time and end_time:
            try:
                filter_start = _naive_parse_dt(start_time)
                filter_end = _naive_parse_dt(end_time)
            except Exception:
                today = datetime.now().date()
                filter_start = datetime.combine(today, datetime.min.time())
                filter_end = datetime.now()
        else:
            today = datetime.now().date()
            filter_start = datetime.combine(today, datetime.min.time())
            filter_end = datetime.now()
        
        base_qs = WafAttackLog.objects.filter(create_at__gte=filter_start, create_at__lte=filter_end)
        
        today_count = base_qs.count()
        today_blocked = base_qs.filter(action_taken='block').count()
        today_high_risk = base_qs.filter(severity__in=['critical', 'high']).count()
        unique_attackers = base_qs.values('src_ip').distinct().count()
        
        week_count = WafAttackLog.objects.filter(
            create_at__gte=filter_start - timedelta(days=7)
        ).count()
        month_count = WafAttackLog.objects.filter(
            create_at__gte=filter_start - timedelta(days=30)
        ).count()
        
        by_type = base_qs.values('attack_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        by_severity = base_qs.values('severity').annotate(
            count=Count('id')
        )
        
        top_ips = base_qs.values('src_ip', 'src_location').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return DetailResponse(data={
            'today_count': today_count,
            'today_blocked': today_blocked,
            'today_high_risk': today_high_risk,
            'unique_attackers': unique_attackers,
            'week_count': week_count,
            'month_count': month_count,
            'by_type': list(by_type),
            'by_severity': list(by_severity),
            'top_ips': list(top_ips),
        })
    
    @action(methods=['GET'], detail=False)
    def trend(self, request):
        period = request.query_params.get('period', '24h')
        start_time_param = request.query_params.get('start_time')
        end_time_param = request.query_params.get('end_time')
        
        # 如果传入了时间范围参数，优先使用
        if start_time_param and end_time_param:
            try:
                filter_start = _naive_parse_dt(start_time_param)
                filter_end = _naive_parse_dt(end_time_param)
            except Exception:
                filter_start = datetime.now() - timedelta(hours=24)
                filter_end = datetime.now()
            
            if period in ('1h', '24h'):
                trend_data = WafAttackLog.objects.filter(
                    create_at__gte=filter_start,
                    create_at__lte=filter_end
                ).annotate(
                    time=TruncMinute('create_at')
                ).values('time').annotate(
                    count=Count('id'),
                    blocked=Count('id', filter=Q(action_taken='block'))
                ).order_by('time')
                for item in trend_data:
                    if item.get('time'):
                        item['time'] = item['time'].isoformat()
            else:
                trend_data = WafAttackLog.objects.filter(
                    create_at__gte=filter_start,
                    create_at__lte=filter_end
                ).annotate(
                    date=TruncDate('create_at')
                ).values('date').annotate(
                    count=Count('id'),
                    blocked=Count('id', filter=Q(action_taken='block'))
                ).order_by('date')
                for item in trend_data:
                    if item.get('date'):
                        item['date'] = item['date'].isoformat()
            
            return DetailResponse(data=list(trend_data))
        
        # 兼容旧的 period 参数
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        if period == 'all':
            # 全部数据，按天聚合
            trend_data = WafAttackLog.objects.annotate(
                date=TruncDate('create_at')
            ).values('date').annotate(
                count=Count('id'),
                blocked=Count('id', filter=Q(action_taken='block'))
            ).order_by('date')
            for item in trend_data:
                if item.get('date'):
                    item['date'] = item['date'].isoformat()
        elif period == '24h':
            start_time = datetime.now() - timedelta(hours=24)
            trend_data = WafAttackLog.objects.filter(
                create_at__gte=start_time
            ).annotate(
                time=TruncMinute('create_at')
            ).values('time').annotate(
                count=Count('id'),
                blocked=Count('id', filter=Q(action_taken='block'))
            ).order_by('time')
            for item in trend_data:
                if item.get('time'):
                    item['time'] = item['time'].isoformat()
        else:
            days = int(request.query_params.get('days', 7))
            start_date = today - timedelta(days=days)
            trend_data = WafAttackLog.objects.filter(
                create_at__date__gte=start_date,
                create_at__date__lte=today
            ).annotate(
                date=TruncDate('create_at')
            ).values('date').annotate(
                count=Count('id'),
                blocked=Count('id', filter=Q(action_taken='block'))
            ).order_by('date')
            for item in trend_data:
                if item.get('date'):
                    item['date'] = item['date'].isoformat()
        
        return DetailResponse(data=list(trend_data))
    
    @action(methods=['GET'], detail=False)
    def ip_stats(self, request):
        ip = request.query_params.get('ip')
        if not ip:
            return ErrorResponse(msg="IP地址不能为空")
        
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        today_attacks = WafAttackLog.objects.filter(
            src_ip=ip,
            create_at__gte=today_start
        ).count()
        
        total_attacks = WafAttackLog.objects.filter(src_ip=ip).count()
        
        first_seen = WafAttackLog.objects.filter(src_ip=ip).order_by('create_at').first()
        last_seen = WafAttackLog.objects.filter(src_ip=ip).order_by('-create_at').first()
        
        attack_types = WafAttackLog.objects.filter(src_ip=ip).values('attack_type').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # 查询IP归属地
        ip_qqwry = IPQQwry()
        location = ip_qqwry.lookup(ip)
        
        # 解析归属地信息
        location_parts = location.split('–') if location else ['', '']
        country = location_parts[0] if len(location_parts) > 0 else '未知'
        province = location_parts[1] if len(location_parts) > 1 else '未知'
        city = location_parts[2] if len(location_parts) > 2 else '未知'
        
        # 格式化归属地显示
        if country and province and city and city != '未知':
            location_str = f"{country} {province} {city}"
        elif country and province and province != '未知':
            location_str = f"{country} {province}"
        elif country and country != '未知':
            location_str = country
        else:
            location_str = '未知'
        
        return DetailResponse(data={
            'ip': ip,
            'today_attacks': today_attacks,
            'total_attacks': total_attacks,
            'first_seen': first_seen.create_at if first_seen else None,
            'last_seen': last_seen.create_at if last_seen else None,
            'attack_types': list(attack_types),
            'location': location_str,
            'country': country,
            'province': province,
            'city': city,
            'isp': '未知',  # qqwry库可能不包含运营商信息
            'is_blacklisted': WafIpList.objects.filter(ip=ip, list_type='blacklist').exists(),
            'is_whitelisted': WafIpList.objects.filter(ip=ip, list_type='whitelist').exists(),
        })
    
    @action(methods=['POST'], detail=False)
    def clear_logs(self, request):
        deleted_count, _ = WafAttackLog.objects.all().delete()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【攻击日志】清空{deleted_count}条记录", module="wafmg")
        return DetailResponse(data={'deleted_count': deleted_count}, msg=f"已清空 {deleted_count} 条攻击日志")

    @action(methods=['POST'], detail=True)
    def mark_false_positive(self, request, pk=None):
        """标记为误报，可选同时加白"""
        instance = self.get_object()
        reason = request.data.get('reason', '')
        add_whitelist = request.data.get('add_whitelist', False)
        whitelist_type = request.data.get('whitelist_type', 'url')  # url 或 ip

        instance.is_false_positive = True
        instance.false_positive_reason = reason
        instance.false_positive_at = datetime.now()
        instance.false_positive_by = request.user.username if hasattr(request, 'user') and request.user else 'system'
        instance.save()

        whitelist_info = ''
        if add_whitelist:
            if whitelist_type == 'url':
                url = instance.dst_url
                # 提取路径部分（去掉查询参数）
                path = url.split('?')[0] if url else ''
                WafUrlWhitelist.objects.create(
                    url=path,
                    match_type='prefix',
                    remark=f'误报自动加白 - {instance.attack_type} - {reason}',
                    enabled=True
                )
                whitelist_info = f'，已将 {path} 加入URL白名单'
            elif whitelist_type == 'ip':
                WafIpList.objects.create(
                    ip=instance.src_ip,
                    list_type='whitelist',
                    remark=f'误报自动加白 - {reason}',
                    source='auto'
                )
                whitelist_info = f'，已将 {instance.src_ip} 加入IP白名单'

        RuyiAddOpLog(request, msg=f"【WAF防护】-【攻击日志】标记误报 ID:{instance.id}{whitelist_info}", module="wafmg")
        return DetailResponse(msg=f'已标记为误报{whitelist_info}')

    @action(methods=['POST'], detail=True)
    def unmark_false_positive(self, request, pk=None):
        """取消误报标记"""
        instance = self.get_object()
        instance.is_false_positive = False
        instance.false_positive_reason = ''
        instance.false_positive_at = None
        instance.false_positive_by = ''
        instance.save()
        RuyiAddOpLog(request, msg=f"【WAF防护】-【攻击日志】取消误报标记 ID:{instance.id}", module="wafmg")
        return DetailResponse(msg='已取消误报标记')

    @action(methods=['GET'], detail=False)
    def top_stats(self, request):
        """攻击TOP统计：攻击类型TOP5 + 攻击IP TOP5 + 被攻击URL TOP5"""
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        
        if start_time and end_time:
            try:
                filter_start = _naive_parse_dt(start_time)
                filter_end = _naive_parse_dt(end_time)
            except Exception:
                today = datetime.now().date()
                filter_start = datetime.combine(today, datetime.min.time())
                filter_end = datetime.now()
        else:
            today = datetime.now().date()
            filter_start = datetime.combine(today, datetime.min.time())
            filter_end = datetime.now()
        
        base_qs = WafAttackLog.objects.filter(
            create_at__gte=filter_start,
            create_at__lte=filter_end,
            is_false_positive=False
        )

        top_attack_types = list(base_qs.values('attack_type').annotate(
            count=Count('id')
        ).order_by('-count')[:5])

        top_ips = list(base_qs.values('src_ip', 'src_location').annotate(
            count=Count('id')
        ).order_by('-count')[:5])

        top_urls = list(base_qs.values('dst_url').annotate(
            count=Count('id')
        ).order_by('-count')[:5])

        return DetailResponse(data={
            'top_attack_types': top_attack_types,
            'top_ips': top_ips,
            'top_urls': top_urls,
        })


class WafUrlWhitelistViewSet(CustomModelViewSet):
    queryset = WafUrlWhitelist.objects.all()
    serializer_class = WafUrlWhitelistSerializer
    filterset_fields = ('site_id', 'match_type', 'enabled')
    search_fields = ('url', 'remark')

    def create(self, request, *args, **kwargs):
        result = super().create(request, *args, **kwargs)
        RuyiAddOpLog(request, msg="【WAF防护】-【URL白名单】新增", module="wafmg")
        return result

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        url = instance.url
        result = super().update(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【URL白名单】更新 {url}", module="wafmg")
        return result

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        url = instance.url
        result = super().destroy(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【URL白名单】删除 {url}", module="wafmg")
        return result
    
    @action(methods=['POST'], detail=True)
    def toggle(self, request, pk=None):
        instance = self.get_object()
        instance.enabled = not instance.enabled
        instance.save()
        status_text = "启用" if instance.enabled else "禁用"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【URL白名单】{instance.url} {status_text}", module="wafmg")
        return DetailResponse(msg=f"URL白名单已{status_text}")
    
    @action(methods=['POST'], detail=False)
    def toggle_global_switch(self, request):
        switch, _ = WafUrlWhitelist.objects.get_or_create(
            remark='__GLOBAL_SWITCH__',
            site_id=None,
            defaults={'url': '', 'enabled': True}
        )
        switch.enabled = not switch.enabled
        switch.save()
        status_text = "开启" if switch.enabled else "关闭"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【URL白名单】全局{status_text}", module="wafmg")
        return DetailResponse(data={'enabled': switch.enabled}, msg=f"已{status_text}")
    
    @action(methods=['GET'], detail=False)
    def get_global_switch(self, request):
        try:
            switch = WafUrlWhitelist.objects.get(remark='__GLOBAL_SWITCH__', site_id=None)
            return DetailResponse(data={'enabled': switch.enabled})
        except WafUrlWhitelist.DoesNotExist:
            return DetailResponse(data={'enabled': True})


class WafUrlBlacklistViewSet(CustomModelViewSet):
    queryset = WafUrlBlacklist.objects.all()
    serializer_class = WafUrlBlacklistSerializer
    filterset_fields = ('site_id', 'match_type', 'enabled')
    search_fields = ('url', 'remark')

    def create(self, request, *args, **kwargs):
        result = super().create(request, *args, **kwargs)
        RuyiAddOpLog(request, msg="【WAF防护】-【URL黑名单】新增", module="wafmg")
        return result

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        url = instance.url
        result = super().update(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【URL黑名单】更新 {url}", module="wafmg")
        return result

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        url = instance.url
        result = super().destroy(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【URL黑名单】删除 {url}", module="wafmg")
        return result
    
    @action(methods=['POST'], detail=True)
    def toggle(self, request, pk=None):
        instance = self.get_object()
        instance.enabled = not instance.enabled
        instance.save()
        status_text = "启用" if instance.enabled else "禁用"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【URL黑名单】{instance.url} {status_text}", module="wafmg")
        return DetailResponse(msg=f"URL黑名单已{status_text}")
    
    @action(methods=['POST'], detail=False)
    def toggle_global_switch(self, request):
        switch, _ = WafUrlBlacklist.objects.get_or_create(
            remark='__GLOBAL_SWITCH__',
            site_id=None,
            defaults={'url': '', 'enabled': True}
        )
        switch.enabled = not switch.enabled
        switch.save()
        status_text = "开启" if switch.enabled else "关闭"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【URL黑名单】全局{status_text}", module="wafmg")
        return DetailResponse(data={'enabled': switch.enabled}, msg=f"已{status_text}")
    
    @action(methods=['GET'], detail=False)
    def get_global_switch(self, request):
        try:
            switch = WafUrlBlacklist.objects.get(remark='__GLOBAL_SWITCH__', site_id=None)
            return DetailResponse(data={'enabled': switch.enabled})
        except WafUrlBlacklist.DoesNotExist:
            return DetailResponse(data={'enabled': True})


class WafUaListViewSet(CustomModelViewSet):
    queryset = WafUaList.objects.all()
    serializer_class = WafUaListSerializer
    filterset_fields = ('list_type', 'site_id', 'enabled')
    search_fields = ('keyword', 'remark')

    def create(self, request, *args, **kwargs):
        result = super().create(request, *args, **kwargs)
        RuyiAddOpLog(request, msg="【WAF防护】-【UA名单】新增", module="wafmg")
        return result

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        keyword = instance.keyword
        result = super().update(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【UA名单】更新 {keyword}", module="wafmg")
        return result

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        keyword = instance.keyword
        result = super().destroy(request, *args, **kwargs)
        RuyiAddOpLog(request, msg=f"【WAF防护】-【UA名单】删除 {keyword}", module="wafmg")
        return result
    
    @action(methods=['POST'], detail=True)
    def toggle(self, request, pk=None):
        instance = self.get_object()
        instance.enabled = not instance.enabled
        instance.save()
        status_text = "启用" if instance.enabled else "禁用"
        RuyiAddOpLog(request, msg=f"【WAF防护】-【UA名单】{instance.keyword} {status_text}", module="wafmg")
        return DetailResponse(msg=f"UA名单已{status_text}")
    
    @action(methods=['POST'], detail=False)
    def toggle_global_switch(self, request):
        list_type = request.data.get('list_type')
        if not list_type:
            return ErrorResponse(msg="缺少list_type参数")
        
        switch, _ = WafUaList.objects.get_or_create(
            list_type=list_type,
            remark='__GLOBAL_SWITCH__',
            site_id=None,
            defaults={'keyword': '', 'enabled': True}
        )
        switch.enabled = not switch.enabled
        switch.save()
        status_text = "开启" if switch.enabled else "关闭"
        type_display = 'UA白名单' if list_type == 'whitelist' else 'UA黑名单'
        RuyiAddOpLog(request, msg=f"【WAF防护】-【{type_display}】全局{status_text}", module="wafmg")
        return DetailResponse(data={'enabled': switch.enabled}, msg=f"已{status_text}")
    
    @action(methods=['GET'], detail=False)
    def get_global_switch(self, request):
        list_type = request.query_params.get('list_type')
        if not list_type:
            return ErrorResponse(msg="缺少list_type参数")
        
        try:
            switch = WafUaList.objects.get(
                list_type=list_type,
                remark='__GLOBAL_SWITCH__',
                site_id=None
            )
            return DetailResponse(data={'enabled': switch.enabled})
        except WafUaList.DoesNotExist:
            return DetailResponse(data={'enabled': True})


class WafDashboardView(CustomAPIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        yesterday_start = today_start - timedelta(days=1)
        time_range = request.query_params.get('time_range', '24h')
        
        if time_range == '24h':
            start_time = today_start - timedelta(hours=24)
        elif time_range == '7d':
            start_time = today_start - timedelta(days=7)
        elif time_range == '30d':
            start_time = today_start - timedelta(days=30)
        else:
            start_time = today_start - timedelta(hours=24)
        
        today_attacks = WafAttackLog.objects.filter(create_at__gte=today_start).count()
        today_blocked = WafAttackLog.objects.filter(
            create_at__gte=today_start,
            action_taken='block'
        ).count()
        
        yesterday_attacks = WafAttackLog.objects.filter(
            create_at__gte=yesterday_start,
            create_at__lt=today_start
        ).count()
        
        week_blocked = WafAttackLog.objects.filter(
            create_at__gte=today_start - timedelta(days=7),
            action_taken='block'
        ).count()
        
        month_blocked = WafAttackLog.objects.filter(
            create_at__gte=today_start - timedelta(days=30),
            action_taken='block'
        ).count()
        
        total_blocked = WafAttackLog.objects.filter(action_taken='block').count()
        total_attacks = WafAttackLog.objects.count()
        
        unique_attackers_today = WafAttackLog.objects.filter(
            create_at__gte=today_start
        ).values('src_ip').distinct().count()
        
        unique_attackers_total = WafAttackLog.objects.values('src_ip').distinct().count()
        
        attack_types = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('attack_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10])
        
        severity_breakdown = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('severity').annotate(
            count=Count('id')
        ).order_by('-count'))
        
        top_ips = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('src_ip', 'src_location').annotate(
            count=Count('id')
        ).order_by('-count')[:10])
        
        top_urls = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).values('dst_url').annotate(
            count=Count('id')
        ).order_by('-count')[:10])
        
        if time_range == '24h':
            trend_data = list(WafAttackLog.objects.filter(
                create_at__gte=start_time
            ).annotate(
                hour=TruncMinute('create_at')
            ).values('hour').annotate(
                count=Count('id'),
                blocked=Count('id', filter=Q(action_taken='block'))
            ).order_by('hour'))
            for item in trend_data:
                if item.get('hour'):
                    item['hour'] = item['hour'].isoformat()
        else:
            trend_data = list(WafAttackLog.objects.filter(
                create_at__gte=start_time
            ).annotate(
                day=TruncDay('create_at')
            ).values('day').annotate(
                count=Count('id'),
                blocked=Count('id', filter=Q(action_taken='block'))
            ).order_by('day'))
            for item in trend_data:
                if item.get('day'):
                    item['day'] = item['day'].isoformat()
        
        ip_stats = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).exclude(src_ip='').exclude(src_ip__isnull=True).values('src_ip').annotate(
            count=Count('id')
        ).order_by('-count')[:50])
        
        country_stats = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).exclude(src_country='').exclude(src_country__isnull=True).values('src_country').annotate(
            count=Count('id')
        ).order_by('-count')[:20])
        
        country_coords = {}
        for stat in country_stats:
            country = stat['src_country']
            sample_log = WafAttackLog.objects.filter(
                create_at__gte=start_time, 
                src_country=country
            ).exclude(src_latitude__isnull=True).exclude(src_longitude__isnull=True).first()
            if sample_log:
                country_coords[country] = [sample_log.src_longitude, sample_log.src_latitude]
        
        location_stats_country = []
        for stat in country_stats:
            country = stat['src_country']
            location_stats_country.append({
                'name': country,
                'count': stat['count'],
                'coords': country_coords.get(country)
            })
        
        province_stats = list(WafAttackLog.objects.filter(
            create_at__gte=start_time,
            src_country='中国'
        ).exclude(src_province='').exclude(src_province__isnull=True).values('src_province').annotate(
            count=Count('id')
        ).order_by('-count')[:20])
        
        province_coords = {}
        for stat in province_stats:
            province = stat['src_province']
            sample_log = WafAttackLog.objects.filter(
                create_at__gte=start_time,
                src_country='中国',
                src_province=province
            ).exclude(src_latitude__isnull=True).exclude(src_longitude__isnull=True).first()
            if sample_log:
                province_coords[province] = [sample_log.src_longitude, sample_log.src_latitude]
        
        location_stats_province = []
        for stat in province_stats:
            province = stat['src_province']
            location_stats_province.append({
                'name': province,
                'count': stat['count'],
                'coords': province_coords.get(province)
            })
        
        recent_attacks = list(WafAttackLog.objects.filter(
            create_at__gte=start_time
        ).order_by('-create_at')[:20].values(
            'id', 'attack_type', 'src_ip', 'src_location', 'src_latitude', 'src_longitude', 'dst_url', 
            'action_taken', 'create_at', 'severity'
        ))
        
        waf_config = WafGlobalConfig.get_instance()
        
        server_location = get_server_location()
        
        trend_percent = round(((today_attacks - yesterday_attacks) / yesterday_attacks * 100), 1) if yesterday_attacks > 0 else 0
        
        return DetailResponse(data={
            'stats': {
                'today_attacks': today_attacks,
                'today_blocked': today_blocked,
                'yesterday_attacks': yesterday_attacks,
                'week_blocked': week_blocked,
                'month_blocked': month_blocked,
                'total_blocked': total_blocked,
                'total_attacks': total_attacks,
                'unique_attackers_today': unique_attackers_today,
                'unique_attackers_total': unique_attackers_total,
                'trend_percent': trend_percent,
            },
            'waf_status': waf_config.waf_status,
            'alert_enabled': waf_config.alert_enabled,
            'attack_types': attack_types,
            'severity_breakdown': severity_breakdown,
            'top_ips': top_ips,
            'top_urls': top_urls,
            'trend_data': trend_data,
            'location_stats_country': location_stats_country,
            'location_stats_province': location_stats_province,
            'server_location': server_location,
            'recent_attacks': recent_attacks,
        })


class WafInternalApiView(CustomAPIView):
    """
    WAF 内部接口：处理日志记录和 CC 攻击自动封禁
    仅供 Lua 脚本调用，需要验证 IP 和 Token
    """
    permission_classes = []
    throttle_classes = []
    check_security_path = False
    authentication_classes = []
    
    ALLOWED_IPS = {'127.0.0.1', '::1'}
    MAX_LOGS_PER_REQUEST = 999
    
    def _verify_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR', '')
        return client_ip in self.ALLOWED_IPS, client_ip
    
    def _verify_token(self, request):
        token = request.headers.get('X-WAF-Token', '')
        if not token:
            return False
        from django.conf import settings
        import os
        import hmac
        token_file = os.path.join(settings.RUYI_DATA_BASE_PATH, 'waf', 'internal_token.ry')
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                expected_token = f.read().strip()
            return hmac.compare_digest(token, expected_token)
        return False
    
    def post(self, request):
        ip_ok, client_ip = self._verify_ip(request)
        if not ip_ok:
            return ErrorResponse(msg="Access denied", status=403)
        
        if not self._verify_token(request):
            return ErrorResponse(msg="Invalid token", status=403)
        
        action = request.query_params.get('action', 'log')
        
        if action == 'ip_blacklist':
            return self._handle_ip_blacklist(request)
        else:
            return self._handle_log(request)
    
    def _handle_log(self, request):
        """处理日志记录"""
        data = request.data
        if isinstance(data, list):
            logs = data[:self.MAX_LOGS_PER_REQUEST]
        else:
            logs = [data]
        
        if not logs:
            return ErrorResponse(msg="No data", status=400)
        
        created_count = 0
        for log_data in logs:
            try:
                src_ip = str(log_data.get('src_ip', ''))[:45]
                src_location = str(log_data.get('src_location', ''))[:200]
                src_country = ''
                src_province = ''
                src_city = ''
                src_latitude = None
                src_longitude = None
                if not src_location and src_ip:
                    try:
                        if is_private_ip(src_ip):
                            src_location = "局域网IP"
                        else:
                            geo_data = GeoIP2Lookup.lookup(src_ip)
                            src_location = geo_data['location'] or ''
                            src_country = geo_data['country'] or ''
                            src_province = geo_data['province'] or ''
                            src_city = geo_data['city'] or ''
                            src_latitude = geo_data['latitude']
                            src_longitude = geo_data['longitude']
                    except Exception as e:
                        import logging
                        logger = logging.getLogger('syswaf')
                        logger.warning(f"IP location lookup failed for {src_ip}: {e}")
                
                attack_log = WafAttackLog.objects.create(
                    site_id=log_data.get('site_id'),
                    rule_id=log_data.get('rule_id'),
                    attack_type=str(log_data.get('attack_type', 'unknown'))[:50],
                    severity=str(log_data.get('severity', 'medium'))[:20],
                    src_ip=src_ip,
                    src_location=str(src_location)[:200],
                    src_country=src_country[:50],
                    src_province=src_province[:50],
                    src_city=src_city[:50],
                    src_latitude=src_latitude,
                    src_longitude=src_longitude,
                    dst_domain=str(log_data.get('dst_host', ''))[:255],
                    dst_url=str(log_data.get('dst_url', ''))[:2000],
                    request_method=str(log_data.get('request_method', 'GET'))[:10],
                    request_data=str(log_data.get('raw_request', ''))[:65535],
                    matched_pattern=str(log_data.get('matched_pattern', '') or log_data.get('rule_name', ''))[:255],
                    action_taken=str(log_data.get('action_taken', 'log'))[:20],
                    user_agent=str(log_data.get('user_agent', ''))[:500],
                    headers=str(log_data.get('headers', '{}'))[:65535],
                    request_id=str(log_data.get('request_id', ''))[:100],
                )
                created_count += 1
            except Exception as e:
                import logging
                logger = logging.getLogger('syswaf')
                logger.error(f"Failed to create WAF attack log: {e}")
        
        return SuccessResponse(data={'created': created_count}, msg=f"成功记录{created_count}条日志")
    
    def _handle_ip_blacklist(self, request):
        """处理 IP 黑名单添加"""
        ip = request.data.get('ip')
        list_type = request.data.get('list_type', 'blacklist')
        remark = request.data.get('remark', 'CC 攻击自动拉黑')
        expire_at = request.data.get('expire_at')
        enabled = request.data.get('enabled', True)
        
        if not ip:
            return ErrorResponse(msg="IP 地址不能为空", status=400)
        
        if list_type not in ['blacklist', 'whitelist', 'temp']:
            return ErrorResponse(msg="无效的名单类型", status=400)
        
        # 有过期时间的黑名单自动设为临时封禁
        if list_type == 'blacklist' and expire_at:
            list_type = 'temp'
        
        try:
            from apps.syswaf.models import WafIpList
            
            # 检查是否已存在
            exists = WafIpList.objects.filter(ip=ip, list_type=list_type).exists()
            if exists:
                # 更新过期时间和备注
                WafIpList.objects.filter(ip=ip, list_type=list_type).update(
                    expire_at=expire_at,
                    remark=remark,
                    enabled=enabled,
                    source='auto'
                )
                return DetailResponse(msg=f"IP {ip} 已更新到{('黑名单' if list_type == 'blacklist' else '白名单')}")
            else:
                # 创建新记录
                WafIpList.objects.create(
                    ip=ip,
                    list_type=list_type,
                    remark=remark,
                    expire_at=expire_at,
                    enabled=enabled,
                    source='auto',
                    entry_type='ip'
                )
                return DetailResponse(msg=f"IP {ip} 已添加到{('黑名单' if list_type == 'blacklist' else '白名单')}")
        except Exception as e:
            return ErrorResponse(msg=f"添加失败：{str(e)}", status=500)
