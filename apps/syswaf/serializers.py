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

from rest_framework import serializers
from utils.serializers import CustomModelSerializer
from apps.syswaf.models import (
    WafGlobalConfig, WafSiteConfig, WafRuleCategory, WafRule,
    WafIpGroup, WafIpList, WafAttackLog, WafUrlWhitelist,
    WafUrlBlacklist, WafUaList
)
import json
from apps.syswaf.models import WafIpList, WafUrlWhitelist, WafUrlBlacklist, WafUaList


class WafGlobalConfigSerializer(CustomModelSerializer):
    cc_config = serializers.SerializerMethodField()
    request_limit_config = serializers.SerializerMethodField()
    geo_config = serializers.SerializerMethodField()
    cdn_config = serializers.SerializerMethodField()
    rule_config = serializers.SerializerMethodField()
    access_control_config = serializers.SerializerMethodField()
    block_page_config = serializers.SerializerMethodField()
    
    class Meta:
        model = WafGlobalConfig
        fields = '__all__'
    
    def get_cc_config(self, obj):
        return obj.get_config('cc_config')
    
    def get_request_limit_config(self, obj):
        return obj.get_config('request_limit_config')
    
    def get_geo_config(self, obj):
        return obj.get_config('geo_config')
    
    def get_cdn_config(self, obj):
        return obj.get_config('cdn_config')
    
    def get_rule_config(self, obj):
        return obj.get_config('rule_config')
    
    def get_block_page_config(self, obj):
        return obj.get_config('block_page_config')
    
    def get_access_control_config(self, obj):
        def get_list_global_switch(model_class, list_type=None):
            query = {'site_id': None}
            if list_type:
                query['list_type'] = list_type
            instance = model_class.objects.filter(**query).first()
            return instance.enabled if instance else True
        
        return {
            'ip_whitelist_enabled': get_list_global_switch(WafIpList, 'whitelist'),
            'ip_blacklist_enabled': get_list_global_switch(WafIpList, 'blacklist'),
            'url_whitelist_enabled': get_list_global_switch(WafUrlWhitelist),
            'url_blacklist_enabled': get_list_global_switch(WafUrlBlacklist),
            'ua_whitelist_enabled': get_list_global_switch(WafUaList, 'whitelist'),
            'ua_blacklist_enabled': get_list_global_switch(WafUaList, 'blacklist'),
        }


class WafGlobalConfigUpdateSerializer(CustomModelSerializer):
    cc_config = serializers.DictField(required=False, default=dict)
    request_limit_config = serializers.DictField(required=False, default=dict)
    geo_config = serializers.DictField(required=False, default=dict)
    cdn_config = serializers.DictField(required=False, default=dict)
    rule_config = serializers.DictField(required=False, default=dict)
    
    class Meta:
        model = WafGlobalConfig
        fields = '__all__'
    
    def update(self, instance, validated_data):
        config_fields = [
            'cc_config',
            'request_limit_config', 'geo_config',
            'cdn_config', 'rule_config'
        ]
        for field in config_fields:
            if field in validated_data:
                instance.set_config(field, validated_data.pop(field))
        return super().update(instance, validated_data)


class WafSiteConfigSerializer(CustomModelSerializer):
    cc_config = serializers.SerializerMethodField()
    geo_config = serializers.SerializerMethodField()
    cdn_config = serializers.SerializerMethodField()
    rule_config = serializers.SerializerMethodField()
    request_limit_config = serializers.SerializerMethodField()
    cdn_headers_list = serializers.SerializerMethodField()
    inherit_status = serializers.SerializerMethodField()
    global_config = serializers.SerializerMethodField()
    stats_blocked_today = serializers.SerializerMethodField()

    class Meta:
        model = WafSiteConfig
        fields = '__all__'
        read_only_fields = ('site_name',)

    def get_stats_blocked_today(self, obj):
        from django.utils import timezone
        from datetime import datetime
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return WafAttackLog.objects.filter(
            site_id=obj.site_id,
            create_at__gte=today,
            action_taken='block'
        ).count()

    def get_cc_config(self, obj):
        return obj.get_config('cc_config')

    def get_geo_config(self, obj):
        return obj.get_config('geo_config')

    def get_cdn_config(self, obj):
        return {
            'enabled': obj.cdn_enabled,
            'provider': obj.cdn_provider,
            'realIpHeaders': json.loads(obj.cdn_headers) if obj.cdn_headers else [],
            'ipGroups': json.loads(obj.cdn_ip_groups) if obj.cdn_ip_groups else [],
            'ipPosition': obj.cdn_ip_position or 'last'
        }

    def get_rule_config(self, obj):
        return obj.get_config('rule_config')

    def get_request_limit_config(self, obj):
        return obj.get_config('request_limit_config')

    def get_cdn_headers_list(self, obj):
        try:
            return json.loads(obj.cdn_headers)
        except:
            return []

    def get_inherit_status(self, obj):
        return {
            'cc': obj.inherit_cc,
            'geo': obj.inherit_geo,
            'rule': obj.inherit_rule,
            'request_limit': obj.inherit_request_limit
        }

    def get_global_config(self, obj):
        global_config = WafGlobalConfig.get_instance()
        return {
            'cc_config': global_config.get_config('cc_config'),
            'geo_config': global_config.get_config('geo_config'),
            'rule_config': global_config.get_config('rule_config'),
            'request_limit_config': global_config.get_config('request_limit_config')
        }


class WafSiteConfigUpdateSerializer(CustomModelSerializer):
    cc_config = serializers.DictField(required=False, default=dict)
    geo_config = serializers.DictField(required=False, default=dict)
    rule_config = serializers.DictField(required=False, default=dict)
    request_limit_config = serializers.DictField(required=False, default=dict)
    cdn_headers = serializers.ListField(required=False, default=list)

    class Meta:
        model = WafSiteConfig
        fields = '__all__'
        read_only_fields = ('site_id', 'site_name')

    def update(self, instance, validated_data):
        if 'cdn_headers' in validated_data:
            validated_data['cdn_headers'] = json.dumps(validated_data.pop('cdn_headers'), ensure_ascii=False)

        dict_fields = ['cc_config', 'geo_config', 'rule_config', 'request_limit_config']
        for field in dict_fields:
            if field in validated_data:
                instance.set_config(field, validated_data.pop(field))

        return super().update(instance, validated_data)


class WafRuleCategorySerializer(CustomModelSerializer):
    rule_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WafRuleCategory
        fields = '__all__'
    
    def get_rule_count(self, obj):
        return obj.rules.count()


class WafRuleSerializer(CustomModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    targets_list = serializers.SerializerMethodField()
    
    class Meta:
        model = WafRule
        fields = '__all__'
    
    def get_targets_list(self, obj):
        return obj.get_targets()


class WafRuleCreateUpdateSerializer(CustomModelSerializer):
    targets = serializers.ListField(required=False, default=list)
    category = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = WafRule
        fields = '__all__'
        extra_kwargs = {
            'rule_id': {'required': False},
            'name': {'required': False},
            'pattern': {'required': False},
            'severity': {'required': False},
            'category': {'required': False},
            'targets': {'required': False},
            'match_type': {'required': False},
            'action': {'required': False},
        }
    
    def validate_category(self, value):
        if isinstance(value, int):
            try:
                return WafRuleCategory.objects.get(pk=value)
            except WafRuleCategory.DoesNotExist:
                raise serializers.ValidationError('分类不存在')
        try:
            return WafRuleCategory.objects.get(code=value)
        except WafRuleCategory.DoesNotExist:
            raise serializers.ValidationError(f'分类不存在: {value}')
    
    def validate_targets(self, value):
        valid_targets = ['url', 'post', 'header', 'cookie', 'ua']
        for target in value:
            if target not in valid_targets:
                raise serializers.ValidationError(f'无效的匹配目标: {target}')
        return json.dumps(value, ensure_ascii=False)


class WafIpGroupSerializer(CustomModelSerializer):
    ip_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WafIpGroup
        fields = '__all__'
    
    def get_ip_count(self, obj):
        return obj.ip_count
    
    def validate_ip_content(self, value):
        if not value:
            return value
        
        import ipaddress
        lines = [line.strip() for line in value.split('\n') if line.strip()]
        errors = []
        
        for i, line in enumerate(lines, 1):
            try:
                if '/' in line:
                    ipaddress.ip_network(line, strict=False)
                else:
                    ipaddress.ip_address(line)
            except ValueError:
                errors.append(f'第{i}行: "{line}" 不是有效的IP地址或CIDR格式')
        
        if errors:
            raise serializers.ValidationError('\n'.join(errors))
        
        return value


class WafIpListSerializer(CustomModelSerializer):
    entry_type_display = serializers.CharField(source='get_entry_type_display', read_only=True)
    list_type_display = serializers.CharField(source='get_list_type_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    ip_version_display = serializers.CharField(source='get_ip_version_display', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    class Meta:
        model = WafIpList
        fields = '__all__'


class WafIpListCreateUpdateSerializer(CustomModelSerializer):
    group = serializers.PrimaryKeyRelatedField(
        queryset=WafIpGroup.objects.all(),
        required=False,
        allow_null=True
    )
    remark = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    
    class Meta:
        model = WafIpList
        fields = '__all__'
    
    def validate(self, data):
        if self.instance and set(data.keys()) == {'enabled'}:
            return data
        
        entry_type = data.get('entry_type', self.instance.entry_type if self.instance else 'single')
        ip = data.get('ip', self.instance.ip if self.instance else '')
        group = data.get('group', self.instance.group if self.instance else None)
        ip_version = data.get('ip_version', self.instance.ip_version if self.instance else 'ipv4')
        
        if entry_type == 'group':
            if not group:
                raise serializers.ValidationError({'group': '选择IP组类型时必须选择一个分组'})
            data['ip'] = ''
            data['ip_version'] = 'ipv4'
        elif entry_type in ('single', 'cidr'):
            if not ip:
                raise serializers.ValidationError({'ip': '请输入IP地址'})
            
            import ipaddress
            try:
                if entry_type == 'single':
                    ip_obj = ipaddress.ip_address(ip)
                    detected_version = 'ipv6' if ip_obj.version == 6 else 'ipv4'
                else:
                    if '/' not in ip:
                        raise serializers.ValidationError({'ip': 'CIDR格式必须包含前缀长度，如 192.168.1.0/24'})
                    network = ipaddress.ip_network(ip, strict=False)
                    detected_version = 'ipv6' if network.version == 6 else 'ipv4'
                    if ip_version == 'ipv4' and network.version == 6:
                        raise serializers.ValidationError({'ip': 'IP版本与所选版本不一致，请选择IPv6'})
                    if ip_version == 'ipv6' and network.version == 4:
                        raise serializers.ValidationError({'ip': 'IP版本与所选版本不一致，请选择IPv4'})
                
                if ip_version != detected_version:
                    data['ip_version'] = detected_version
            except ValueError as e:
                raise serializers.ValidationError({'ip': f'无效的IP地址格式: {str(e)}'})
        
        return data


class WafAttackLogSerializer(CustomModelSerializer):
    action_taken_display = serializers.CharField(source='get_action_taken_display', read_only=True)
    site_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = WafAttackLog
        fields = '__all__'
    
    def get_site_name(self, obj):
        """获取站点名称"""
        if obj.site_id:
            from apps.system.models import Sites
            try:
                site = Sites.objects.filter(id=obj.site_id).first()
                return site.name if site else None
            except:
                return None
        return None


class WafUrlWhitelistSerializer(CustomModelSerializer):
    match_type_display = serializers.CharField(source='get_match_type_display', read_only=True)
    
    class Meta:
        model = WafUrlWhitelist
        fields = '__all__'


class WafUrlBlacklistSerializer(CustomModelSerializer):
    match_type_display = serializers.CharField(source='get_match_type_display', read_only=True)
    
    class Meta:
        model = WafUrlBlacklist
        fields = '__all__'


class WafUaListSerializer(CustomModelSerializer):
    list_type_display = serializers.CharField(source='get_list_type_display', read_only=True)
    
    class Meta:
        model = WafUaList
        fields = '__all__'


class WafDashboardStatsSerializer(serializers.Serializer):
    total_blocked_today = serializers.IntegerField()
    total_blocked_week = serializers.IntegerField()
    total_blocked_month = serializers.IntegerField()
    total_blocked = serializers.IntegerField()
    attack_types = serializers.ListField()
    top_ips = serializers.ListField()
    top_urls = serializers.ListField()
    trend_data = serializers.ListField()
