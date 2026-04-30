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

from django.db import models
from utils.models import table_prefix, BaseModel
import json


class WafGlobalConfig(BaseModel):
    """
    WAF全局配置（单例模式）
    """
    WAF_STATUS_CHOICES = (
        ('off', '关闭'),
        ('observe', '观察模式'),
        ('protect', '防护模式'),
    )
    
    id = models.IntegerField(primary_key=True, default=1, verbose_name='主键')
    waf_status = models.CharField(max_length=20, choices=WAF_STATUS_CHOICES, default='off', verbose_name='WAF状态')
    
    cc_config = models.TextField(verbose_name='CC防护配置', default='{}')
    request_limit_config = models.TextField(verbose_name='请求限制配置', default='{}')
    geo_config = models.TextField(verbose_name='地域限制配置', default='{}')
    cdn_config = models.TextField(verbose_name='CDN兼容配置', default='{}')
    rule_config = models.TextField(verbose_name='规则开关配置', default='{}')
    block_page_config = models.TextField(verbose_name='拦截页面配置', default='{}')
    
    log_retention_days = models.IntegerField(default=30, verbose_name='日志保留天数')
    
    class Meta:
        db_table = table_prefix + "waf_global_config"
        verbose_name = 'WAF全局配置'
        verbose_name_plural = verbose_name
        app_label = "syswaf"
    
    def get_config(self, field_name):
        try:
            config = json.loads(getattr(self, field_name))
            if not config:
                return self._get_default_config(field_name)
            return config
        except:
            return self._get_default_config(field_name)
    
    def _get_default_config(self, field_name):
        defaults = {
            'cc_config': {
                'frequency': {'requestType': 'url_no_param', 'period': 60, 'frequency': 180, 'blockTime': 300, 'enabled': False},
                'tolerance': {'period': 600, 'threshold': 10, 'blockTime': 3600, 'enabled': False},
                'error_limit': {'period': 60, 'threshold': 10, 'blockTime': 300, 'enabled': False}
            },
            'request_limit_config': {'enabled': False, 'allowedMethods': ['GET', 'POST', 'HEAD'], 'blockEmptyUA': True, 'blockEmptyReferer': False, 'blockEmptyHost': True, 'maxBodySize': 10485760, 'maxUrlLength': 2048, 'maxHeaderSize': 8192},
            'geo_config': {'enabled': False, 'mode': 'whitelist', 'ip_groups': []},
            'cdn_config': {'enabled': False, 'provider': 'auto', 'realIpHeaders': [], 'ipRanges': ''},
            'rule_config': {'sql': {'mode': 2}, 'xss': {'mode': 2}, 'command': {'mode': 2}, 'sensitive_file': {'mode': 2}, 'scanner': {'mode': 2}, 'bot': {'mode': 2}, 'path': {'mode': 2}},
            'block_page_config': {'show_detail': False, 'custom_page': ''}
        }
        return defaults.get(field_name, {})
    
    def set_config(self, field_name, config_dict):
        setattr(self, field_name, json.dumps(config_dict, ensure_ascii=False))
    
    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class WafSiteConfig(BaseModel):
    """
    站点WAF配置
    设计说明：
    1. 每个配置项都有对应的继承标记字段（inherit_xxx）
    2. 当继承标记为True时，使用全局配置
    3. 当继承标记为False时，使用站点自定义配置
    4. get_effective_config 方法返回最终生效的配置
    """
    WAF_STATUS_CHOICES = (
        ('off', '关闭'),
        ('observe', '观察模式'),
        ('protect', '防护模式'),
    )

    site_id = models.IntegerField(unique=True, default=0, verbose_name='站点ID')
    site_name = models.CharField(max_length=255, default='', verbose_name='站点名称')

    waf_status = models.CharField(max_length=20, choices=WAF_STATUS_CHOICES, default='off', verbose_name='WAF状态')

    inherit_cc = models.BooleanField(default=True, verbose_name='继承CC防护配置')
    cc_config = models.TextField(verbose_name='CC防护配置', default='{}')

    inherit_geo = models.BooleanField(default=True, verbose_name='继承地域限制配置')
    geo_config = models.TextField(verbose_name='地域限制配置', default='{}')

    cdn_enabled = models.BooleanField(default=False, verbose_name='CDN兼容开关')
    cdn_provider = models.CharField(max_length=50, default='auto', verbose_name='CDN服务商')
    cdn_headers = models.TextField(verbose_name='CDN获取IP头', default='[]')
    cdn_ip_groups = models.TextField(verbose_name='CDN回源IP组', default='[]', help_text='IP组ID列表')
    cdn_ip_position = models.CharField(max_length=10, default='last', verbose_name='CDN真实IP位置', help_text='从X-Forwarded-For中获取IP的位置：last取最后一个，first取第一个')

    inherit_rule = models.BooleanField(default=True, verbose_name='继承规则配置')
    rule_config = models.TextField(verbose_name='规则开关配置', default='{}')

    inherit_request_limit = models.BooleanField(default=True, verbose_name='继承请求限制配置')
    request_limit_config = models.TextField(verbose_name='请求限制配置', default='{}')

    stats_blocked_today = models.IntegerField(default=0, verbose_name='今日拦截数')
    stats_blocked_total = models.IntegerField(default=0, verbose_name='总拦截数')

    class Meta:
        db_table = table_prefix + "waf_site_config"
        verbose_name = '站点WAF配置'
        verbose_name_plural = verbose_name
        app_label = "syswaf"

    def get_config(self, field_name):
        try:
            config = json.loads(getattr(self, field_name))
            if not config:
                return self._get_default_config(field_name)
            return config
        except:
            return self._get_default_config(field_name)
    
    def _get_default_config(self, field_name):
        defaults = {
            'cc_config': {
                'frequency': {'requestType': 'url_no_param', 'period': 60, 'frequency': 180, 'blockTime': 300, 'enabled': False},
                'tolerance': {'period': 600, 'threshold': 10, 'blockTime': 3600, 'enabled': False},
                'error_limit': {'period': 60, 'threshold': 10, 'blockTime': 300, 'enabled': False}
            },
            'request_limit_config': {'enabled': False, 'allowedMethods': ['GET', 'POST', 'HEAD'], 'blockEmptyUA': True, 'blockEmptyReferer': False, 'blockEmptyHost': True, 'maxBodySize': 10485760, 'maxUrlLength': 2048, 'maxHeaderSize': 8192},
            'geo_config': {'enabled': False, 'mode': 'whitelist', 'ip_groups': []},
            'rule_config': {'sql': {'mode': 2}, 'xss': {'mode': 2}, 'command': {'mode': 2}, 'sensitive_file': {'mode': 2}, 'scanner': {'mode': 2}, 'bot': {'mode': 2}, 'path': {'mode': 2}}
        }
        return defaults.get(field_name, {})

    def set_config(self, field_name, config_dict):
        setattr(self, field_name, json.dumps(config_dict, ensure_ascii=False))

    def get_effective_config(self, config_name):
        """
        获取最终生效的配置
        config_name: cc, geo, cdn, rule, request_limit
        返回: (config_dict, is_inherited)
        """
        inherit_field = f'inherit_{config_name}'
        config_field = f'{config_name}_config'

        is_inherited = getattr(self, inherit_field, True)

        if is_inherited:
            global_config = WafGlobalConfig.get_instance()
            return global_config.get_config(config_field), True
        else:
            return self.get_config(config_field), False

    def get_all_effective_configs(self):
        """
        获取所有最终生效的配置
        """
        result = {}
        inherit_status = {}

        for config_name in ['cc', 'geo', 'rule', 'request_limit']:
            config, is_inherited = self.get_effective_config(config_name)
            if config_name == 'request_limit':
                result['request_limit_config'] = config
            else:
                result[f'{config_name}_config'] = config
            inherit_status[config_name] = is_inherited

        result['cdn_config'] = {
            'enabled': self.cdn_enabled,
            'provider': self.cdn_provider,
            'headers': json.loads(self.cdn_headers) if self.cdn_headers else [],
            'ip_groups': json.loads(self.cdn_ip_groups) if self.cdn_ip_groups else [],
            'ip_position': self.cdn_ip_position or 'last'
        }

        result['inherit_status'] = inherit_status
        return result

    def get_cdn_ip_list(self):
        """
        获取CDN回源IP列表（从IP组中获取）
        """
        ip_groups = json.loads(self.cdn_ip_groups) if self.cdn_ip_groups else []
        if not ip_groups:
            return []
        
        ip_list = []
        for group_id in ip_groups:
            try:
                group = WafIpGroup.objects.get(id=group_id)
                ip_list.extend(group.get_ip_list())
            except WafIpGroup.DoesNotExist:
                pass
        return ip_list

    @property
    def site(self):
        from apps.system.models import Sites
        return Sites.objects.filter(id=self.site_id).first()


class WafRuleCategory(BaseModel):
    """
    规则分类
    """
    name = models.CharField(max_length=50, verbose_name='分类名称')
    code = models.CharField(max_length=30, unique=True, verbose_name='分类代码')
    icon = models.CharField(max_length=50, default='Warning', verbose_name='图标名称')
    color = models.CharField(max_length=20, default='#909399', verbose_name='颜色值')
    sort = models.IntegerField(default=0, verbose_name='排序')
    description = models.TextField(verbose_name='描述', default='')
    
    class Meta:
        db_table = table_prefix + "waf_rule_category"
        verbose_name = '规则分类'
        verbose_name_plural = verbose_name
        ordering = ('sort',)
        app_label = "syswaf"


class WafRule(BaseModel):
    """
    防护规则
    """
    SEVERITY_CHOICES = (
        ('critical', '严重'),
        ('high', '高危'),
        ('medium', '中危'),
        ('low', '低危'),
    )
    
    name = models.CharField(max_length=100, verbose_name='规则名称')
    rule_id = models.CharField(max_length=50, unique=True, verbose_name='规则ID')
    category = models.ForeignKey(WafRuleCategory, on_delete=models.CASCADE, related_name='rules', verbose_name='所属分类')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium', verbose_name='危险等级')
    
    pattern = models.TextField(verbose_name='匹配规则（正则表达式）')
    targets = models.TextField(verbose_name='匹配目标', default='["url", "post"]')
    
    description = models.TextField(verbose_name='规则描述', default='')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    is_builtin = models.BooleanField(default=True, verbose_name='是否内置规则')
    
    trigger_count = models.IntegerField(default=0, verbose_name='触发次数')
    
    class Meta:
        db_table = table_prefix + "waf_rule"
        verbose_name = '防护规则'
        verbose_name_plural = verbose_name
        ordering = ('-severity', 'category', 'id')
        app_label = "syswaf"
    
    def get_targets(self):
        try:
            return json.loads(self.targets)
        except:
            return []


class WafIpGroup(BaseModel):
    """
    IP分组
    """
    name = models.CharField(max_length=100, verbose_name='分组名称')
    ip_content = models.TextField(verbose_name='IP内容', default='', help_text='每行一个IP或CIDR')
    
    class Meta:
        db_table = table_prefix + "waf_ip_group"
        verbose_name = 'IP分组'
        verbose_name_plural = verbose_name
        app_label = "syswaf"
    
    def get_ip_list(self):
        return [line.strip() for line in self.ip_content.split('\n') if line.strip()]
    
    @property
    def ip_count(self):
        return len(self.get_ip_list())


class WafIpList(BaseModel):
    """
    IP黑白名单
    """
    ENTRY_TYPE_CHOICES = (
        ('single', '单IP'),
        ('group', 'IP组'),
        ('cidr', 'IP段'),
    )
    LIST_TYPE_CHOICES = (
        ('whitelist', '白名单'),
        ('blacklist', '黑名单'),
        ('temp', '临时封禁'),
    )
    IP_VERSION_CHOICES = (
        ('ipv4', 'IPv4'),
        ('ipv6', 'IPv6'),
    )
    SOURCE_CHOICES = (
        ('manual', '手动添加'),
        ('auto', '自动封禁'),
        ('rule', '规则触发'),
        ('import', '批量导入'),
    )
    
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default='single', verbose_name='条目类型')
    ip = models.CharField(max_length=100, verbose_name='IP地址', blank=True, default='', help_text='单IP或CIDR格式')
    ip_version = models.CharField(max_length=10, choices=IP_VERSION_CHOICES, default='ipv4', verbose_name='IP版本')
    list_type = models.CharField(max_length=20, choices=LIST_TYPE_CHOICES, default='blacklist', verbose_name='名单类型')
    group = models.ForeignKey('WafIpGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='ips', verbose_name='所属分组')
    
    remark = models.CharField(max_length=255, verbose_name='备注', default='')
    expire_at = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual', verbose_name='来源')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    
    location = models.CharField(max_length=100, verbose_name='IP归属地', default='')
    trigger_count = models.IntegerField(default=0, verbose_name='触发次数')
    
    site_id = models.IntegerField(null=True, blank=True, verbose_name='关联站点ID（空为全局）')
    
    class Meta:
        db_table = table_prefix + "waf_ip_list"
        verbose_name = 'IP名单'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "syswaf"


class WafAttackLog(BaseModel):
    """
    攻击日志（独立数据库 waf_logs）
    """
    ACTION_CHOICES = (
        ('block', '拦截'),
        ('log', '记录'),
        ('captcha', '人机验证'),
    )
    
    site_id = models.IntegerField(null=True, verbose_name='关联站点ID')
    rule_id = models.CharField(max_length=50, null=True, verbose_name='触发的规则ID')
    
    attack_type = models.CharField(max_length=50, verbose_name='攻击类型')
    severity = models.CharField(max_length=20, verbose_name='危险等级')
    
    src_ip = models.CharField(max_length=50, verbose_name='攻击源IP')
    src_location = models.CharField(max_length=100, verbose_name='IP归属地', default='')
    src_country = models.CharField(max_length=50, verbose_name='国家', default='')
    src_province = models.CharField(max_length=50, verbose_name='省份', default='')
    src_city = models.CharField(max_length=50, verbose_name='城市', default='')
    src_latitude = models.FloatField(null=True, blank=True, verbose_name='IP纬度')
    src_longitude = models.FloatField(null=True, blank=True, verbose_name='IP经度')
    
    dst_domain = models.CharField(max_length=255, verbose_name='目标域名', default='')
    dst_url = models.TextField(verbose_name='目标URL')
    
    request_method = models.CharField(max_length=10, verbose_name='请求方法')
    request_data = models.TextField(verbose_name='请求数据', default='')
    matched_pattern = models.TextField(verbose_name='匹配规则', default='')
    
    action_taken = models.CharField(max_length=20, choices=ACTION_CHOICES, default='block', verbose_name='处理动作')
    
    user_agent = models.TextField(verbose_name='User-Agent', default='')
    headers = models.TextField(verbose_name='请求头', default='{}')
    
    request_id = models.CharField(max_length=50, verbose_name='请求ID', default='')
    
    class Meta:
        db_table = table_prefix + "waf_attack_log"
        verbose_name = '攻击日志'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "syswaf"


class WafUrlWhitelist(BaseModel):
    """
    URL白名单
    """
    MATCH_TYPE_CHOICES = (
        ('exact', '精确匹配'),
        ('prefix', '前缀匹配'),
        ('regex', '正则匹配'),
    )
    
    url = models.CharField(max_length=255, verbose_name='URL路径')
    match_type = models.CharField(max_length=20, choices=MATCH_TYPE_CHOICES, default='prefix', verbose_name='匹配类型')
    site_id = models.IntegerField(null=True, blank=True, verbose_name='关联站点ID（空为全局）')
    remark = models.CharField(max_length=255, verbose_name='备注', default='')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = table_prefix + "waf_url_whitelist"
        verbose_name = 'URL白名单'
        verbose_name_plural = verbose_name
        app_label = "syswaf"


class WafUrlBlacklist(BaseModel):
    """
    URL黑名单
    """
    MATCH_TYPE_CHOICES = (
        ('exact', '精确匹配'),
        ('prefix', '前缀匹配'),
        ('regex', '正则匹配'),
    )
    
    url = models.CharField(max_length=255, verbose_name='URL路径')
    match_type = models.CharField(max_length=20, choices=MATCH_TYPE_CHOICES, default='prefix', verbose_name='匹配类型')
    site_id = models.IntegerField(null=True, blank=True, verbose_name='关联站点ID（空为全局）')
    response_code = models.IntegerField(default=403, verbose_name='响应状态码')
    remark = models.CharField(max_length=255, verbose_name='备注', default='')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = table_prefix + "waf_url_blacklist"
        verbose_name = 'URL黑名单'
        verbose_name_plural = verbose_name
        app_label = "syswaf"


class WafUaList(BaseModel):
    """
    User-Agent黑白名单
    """
    LIST_TYPE_CHOICES = (
        ('whitelist', '白名单'),
        ('blacklist', '黑名单'),
    )
    
    keyword = models.CharField(max_length=255, verbose_name='UA关键词')
    list_type = models.CharField(max_length=20, choices=LIST_TYPE_CHOICES, default='blacklist', verbose_name='名单类型')
    site_id = models.IntegerField(null=True, blank=True, verbose_name='关联站点ID（空为全局）')
    remark = models.CharField(max_length=255, verbose_name='备注', default='')
    enabled = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = table_prefix + "waf_ua_list"
        verbose_name = 'UA名单'
        verbose_name_plural = verbose_name
        app_label = "syswaf"
