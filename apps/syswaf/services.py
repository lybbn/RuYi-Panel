#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# | Author: lybbn
# +-------------------------------------------------------------------

import os
import json
import shutil
from django.conf import settings
from apps.syswaf.models import (
    WafGlobalConfig, WafSiteConfig, WafRule, 
    WafIpList, WafUrlWhitelist, WafUrlBlacklist, WafUaList,
    WafRuleCategory, WafIpGroup
)


class WafConfigSync:
    """
    WAF配置同步服务
    将数据库中的WAF配置同步到Nginx配置文件和Lua脚本所需的JSON配置
    """
    
    def __init__(self):
        self.data_dir = settings.RUYI_DATA_BASE_PATH
        self.waf_config_dir = settings.RUYI_WAF_DATA_PATH
        self.lua_dir = settings.RUYI_WAF_LUA_PATH
        self.ensure_dirs()
    
    def ensure_dirs(self):
        dirs = [
            self.waf_config_dir,
            os.path.join(self.waf_config_dir, 'rules'),
            os.path.join(self.waf_config_dir, 'ip'),
            os.path.join(self.waf_config_dir, 'sites'),
        ]
        for d in dirs:
            if not os.path.exists(d):
                os.makedirs(d)
        
        token_file = os.path.join(self.waf_config_dir, 'internal_token.ry')
        if not os.path.exists(token_file):
            from utils.common import GetRandomSet
            token = GetRandomSet(32)
            with open(token_file, 'w') as f:
                f.write(token)
    
    def _get_list_global_switch(self, model_class, list_type=None, site_id=None):
        """
        获取列表的全局开关状态
        """
        try:
            filters = {'remark': '__GLOBAL_SWITCH__', 'site_id': site_id}
            if list_type:
                filters['list_type'] = list_type
            switch = model_class.objects.get(**filters)
            return switch.enabled
        except model_class.DoesNotExist:
            return True
    
    def _get_ip_list_from_groups(self, ip_group_ids):
        """
        从IP组获取IP列表
        返回格式: ['1.0.1.0/24', '1.0.2.0/23', ...]
        """
        if not ip_group_ids:
            return []
        
        ip_list = []
        for group_id in ip_group_ids:
            try:
                group = WafIpGroup.objects.get(id=group_id)
                ip_list.extend(group.get_ip_list())
            except WafIpGroup.DoesNotExist:
                pass
        return ip_list
    
    def _build_ip_ranges_for_lua(self, ip_list):
        """
        构建Lua使用的IP范围数据结构
        将CIDR转换为数值范围，便于二分查找
        """
        ranges = []
        for cidr in ip_list:
            try:
                if '/' in cidr:
                    ip, prefix = cidr.split('/')
                    prefix = int(prefix)
                    parts = [int(p) for p in ip.split('.')]
                    if len(parts) != 4:
                        continue
                    ip_num = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
                    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
                    ip_start = ip_num & mask
                    ip_end = ip_start | (~mask & 0xFFFFFFFF)
                    ranges.append({
                        'start': ip_start,
                        'end': ip_end
                    })
            except:
                continue
        ranges.sort(key=lambda x: x['start'])
        return ranges
    
    def _ensure_waf_config_files_exist(self):
        """
        确保所有WAF配置文件存在，如果不存在则创建空文件
        """
        files_to_check = [
            'rules.json',
            'ip_whitelist.json',
            'ip_blacklist.json',
            'url_whitelist.json',
            'url_blacklist.json',
            'ua_whitelist.json',
            'ua_blacklist.json',
            'site_ip_whitelist.json',
            'site_ip_blacklist.json',
            'ip_groups.json',
        ]
        
        default_contents = {
            'rules.json': {'rules': []},
            'ip_whitelist.json': {'ips': [], 'ranges': []},
            'ip_blacklist.json': {'ips': [], 'ranges': []},
            'url_whitelist.json': {'urls': []},
            'url_blacklist.json': {'urls': []},
            'ua_whitelist.json': {'ua_patterns': []},
            'ua_blacklist.json': {'ua_patterns': []},
            'site_ip_whitelist.json': {'sites': {}},
            'site_ip_blacklist.json': {'sites': {}},
            'ip_groups.json': {'groups': {}},
        }
        
        for filename in files_to_check:
            filepath = os.path.join(self.waf_config_dir, filename)
            if not os.path.exists(filepath):
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(default_contents.get(filename, {}), f, ensure_ascii=False, indent=2)
                except Exception:
                    # 记录错误但不中断流程
                    pass
    
    def sync_global_config(self):
        """
        同步全局WAF配置 - 生成Lua脚本所需的config.json
        同时更新Nginx主配置文件中的WAF开关状态
        """
        try:
            config = WafGlobalConfig.get_instance()
            
            geo_config = config.get_config('geo_config') or {}
            
            block_page_config = config.get_config('block_page_config') or {}
            
            config_data = {
                'waf_status': config.waf_status,
                'cc_config': config.get_config('cc_config') or {},
                'request_limit_config': config.get_config('request_limit_config') or {},
                'geo_config': {
                    'enabled': geo_config.get('enabled', False),
                    'mode': geo_config.get('mode', 'whitelist'),
                    'ip_groups': geo_config.get('ip_groups', []),
                },
                'cdn_config': config.get_config('cdn_config') or {},
                'rule_config': config.get_config('rule_config') or {},
                'block_page_config': {
                    'show_detail': block_page_config.get('show_detail', True),
                    'custom_page': block_page_config.get('custom_page', '')
                },
                'log_retention_days': config.log_retention_days,
                'access_control': {
                    'ip_whitelist_enabled': self._get_list_global_switch(WafIpList, 'whitelist'),
                    'ip_blacklist_enabled': self._get_list_global_switch(WafIpList, 'blacklist'),
                    'url_whitelist_enabled': self._get_list_global_switch(WafUrlWhitelist),
                    'url_blacklist_enabled': self._get_list_global_switch(WafUrlBlacklist),
                    'ua_whitelist_enabled': self._get_list_global_switch(WafUaList, 'whitelist'),
                    'ua_blacklist_enabled': self._get_list_global_switch(WafUaList, 'blacklist'),
                }
            }
            
            config_file = os.path.join(self.waf_config_dir, 'config.json')
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            # 确保所有WAF配置文件存在
            self._ensure_waf_config_files_exist()
            
            # 确保nginx_waf.conf文件存在，并更新Nginx主配置
            nginx_waf_conf = os.path.join(self.waf_config_dir, 'nginx_waf.conf')
            if not os.path.exists(nginx_waf_conf):
                # 文件不存在，生成完整配置
                self.generate_nginx_waf_config()
            else:
                # 文件已存在，只更新Nginx主配置文件中的WAF开关状态
                self._update_nginx_main_config(config.waf_status)
            
            # 如果WAF处于启用状态（非off），同步所有配置数据
            if config.waf_status != 'off':
                self.sync_rules()
                self.sync_ip_list()
                self.sync_url_lists()
                self.sync_ua_list()
                self.sync_ip_groups()
                self.sync_site_config()
            
            return True, "全局配置同步成功"
        except Exception as e:
            return False, f"全局配置同步失败: {str(e)}"
    
    def sync_site_config(self, site_id=None):
        """
        同步站点WAF配置 - 实现继承机制
        """
        try:
            global_config = WafGlobalConfig.get_instance()
            
            if site_id:
                site_config_file = os.path.join(self.waf_config_dir, 'sites', f'site_{site_id}.json')
                if not WafSiteConfig.objects.filter(site_id=site_id).exists():
                    if os.path.exists(site_config_file):
                        os.remove(site_config_file)
                    return True, f"站点{site_id}配置已删除"
                configs = WafSiteConfig.objects.filter(site_id=site_id)
            else:
                configs = WafSiteConfig.objects.all()
            
            count = 0
            for site_config in configs:
                effective_configs = site_config.get_all_effective_configs()
                
                geo_config = effective_configs.get('geo_config', {})
                
                config_data = {
                    'site_id': site_config.site_id,
                    'site_name': site_config.site_name,
                    'waf_status': site_config.waf_status,
                    'cc_config': effective_configs.get('cc_config', {}),
                    'geo_config': {
                        'enabled': geo_config.get('enabled', False),
                        'mode': geo_config.get('mode', 'whitelist'),
                        'ip_groups': geo_config.get('ip_groups', []),
                    },
                    'request_limit_config': effective_configs.get('request_limit_config', {}),
                    'rule_config': effective_configs.get('rule_config', {}),
                    'cdn_config': {
                        'enabled': site_config.cdn_enabled,
                        'provider': site_config.cdn_provider,
                        'headers': json.loads(site_config.cdn_headers) if site_config.cdn_headers else [],
                        'ip_groups': json.loads(site_config.cdn_ip_groups) if site_config.cdn_ip_groups else [],
                        'ip_position': site_config.cdn_ip_position or 'last',
                    },
                    'inherit_status': effective_configs.get('inherit_status', {}),
                }
                
                config_file = os.path.join(self.waf_config_dir, 'sites', f'site_{site_config.site_id}.json')
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                count += 1
            
            return True, f"站点配置同步成功，共{count}个站点"
        except Exception as e:
            return False, f"站点配置同步失败: {str(e)}"
    
    def sync_rules(self):
        """
        同步防护规则 - 生成Lua脚本所需的rules.json
        所有规则（内置+自定义）统一管理
        """
        try:
            rules = WafRule.objects.all().select_related('category')
            rules_data = {
                'version': '1.0',
                'update_time': '',
                'rules': []
            }
            
            for rule in rules:
                rule_data = {
                    'id': rule.id,
                    'rule_id': rule.rule_id,
                    'name': rule.name,
                    'category': rule.category.code if rule.category else 'other',
                    'category_name': rule.category.name if rule.category else '其他',
                    'severity': rule.severity,
                    'pattern': rule.pattern,
                    'targets': rule.get_targets() if hasattr(rule, 'get_targets') else [],
                    'description': rule.description,
                    'enabled': rule.enabled,
                    'is_builtin': rule.is_builtin,
                }
                rules_data['rules'].append(rule_data)
            
            rules_file = os.path.join(self.waf_config_dir, 'rules.json')
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules_data, f, ensure_ascii=False, indent=2)
            
            return True, f"规则同步成功，共{len(rules_data['rules'])}条规则"
        except Exception as e:
            return False, f"规则同步失败: {str(e)}"
    
    def sync_ip_list(self):
        """
        同步IP黑白名单
        """
        try:
            global_whitelist = WafIpList.objects.filter(
                list_type='whitelist', 
                enabled=True, 
                site_id__isnull=True
            ).exclude(remark='__GLOBAL_SWITCH__')
            
            global_blacklist = WafIpList.objects.filter(
                list_type='blacklist', 
                enabled=True, 
                site_id__isnull=True
            ).exclude(remark='__GLOBAL_SWITCH__')
            
            site_whitelist = WafIpList.objects.filter(
                list_type='whitelist', 
                enabled=True
            ).exclude(site_id__isnull=True).exclude(remark='__GLOBAL_SWITCH__')
            
            site_blacklist = WafIpList.objects.filter(
                list_type='blacklist', 
                enabled=True
            ).exclude(site_id__isnull=True).exclude(remark='__GLOBAL_SWITCH__')
            
            whitelist_data = {
                'version': '1.0',
                'update_time': '',
                'enabled': self._get_list_global_switch(WafIpList, 'whitelist'),
                'ips': []
            }
            for ip in global_whitelist:
                whitelist_data['ips'].append({
                    'ip': ip.ip,
                    'cidr': ip.cidr if hasattr(ip, 'cidr') else '',
                    'remark': ip.remark or '',
                })
            
            blacklist_data = {
                'version': '1.0',
                'update_time': '',
                'enabled': self._get_list_global_switch(WafIpList, 'blacklist'),
                'ips': []
            }
            for ip in global_blacklist:
                blacklist_data['ips'].append({
                    'ip': ip.ip,
                    'cidr': ip.cidr if hasattr(ip, 'cidr') else '',
                    'remark': ip.remark or '黑名单IP',
                    'expire_at': ip.expire_at.isoformat() if hasattr(ip, 'expire_at') and ip.expire_at else None,
                })
            
            whitelist_file = os.path.join(self.waf_config_dir, 'ip_whitelist.json')
            with open(whitelist_file, 'w', encoding='utf-8') as f:
                json.dump(whitelist_data, f, ensure_ascii=False, indent=2)
            
            blacklist_file = os.path.join(self.waf_config_dir, 'ip_blacklist.json')
            with open(blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(blacklist_data, f, ensure_ascii=False, indent=2)
            
            site_whitelist_data = {}
            for ip in site_whitelist:
                site_id = ip.site_id
                if site_id not in site_whitelist_data:
                    site_whitelist_data[site_id] = {
                        'site_id': site_id,
                        'ips': []
                    }
                site_whitelist_data[site_id]['ips'].append({
                    'ip': ip.ip,
                    'cidr': ip.cidr if hasattr(ip, 'cidr') else '',
                    'remark': ip.remark or '',
                })
            
            site_blacklist_data = {}
            for ip in site_blacklist:
                site_id = ip.site_id
                if site_id not in site_blacklist_data:
                    site_blacklist_data[site_id] = {
                        'site_id': site_id,
                        'ips': []
                    }
                site_blacklist_data[site_id]['ips'].append({
                    'ip': ip.ip,
                    'cidr': ip.cidr if hasattr(ip, 'cidr') else '',
                    'remark': ip.remark or '站点黑名单IP',
                    'expire_at': ip.expire_at.isoformat() if hasattr(ip, 'expire_at') and ip.expire_at else None,
                })
            
            site_whitelist_file = os.path.join(self.waf_config_dir, 'site_ip_whitelist.json')
            with open(site_whitelist_file, 'w', encoding='utf-8') as f:
                json.dump(site_whitelist_data, f, ensure_ascii=False, indent=2)
            
            site_blacklist_file = os.path.join(self.waf_config_dir, 'site_ip_blacklist.json')
            with open(site_blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(site_blacklist_data, f, ensure_ascii=False, indent=2)
            
            return True, f"IP名单同步成功，全局白名单{len(whitelist_data['ips'])}条，全局黑名单{len(blacklist_data['ips'])}条"
        except Exception as e:
            return False, f"IP名单同步失败: {str(e)}"
    
    def sync_url_lists(self):
        """
        同步URL白名单和黑名单
        """
        try:
            url_whitelist = WafUrlWhitelist.objects.filter(
                enabled=True, 
                site_id__isnull=True
            ).exclude(remark='__GLOBAL_SWITCH__')
            
            url_blacklist = WafUrlBlacklist.objects.filter(
                enabled=True, 
                site_id__isnull=True
            ).exclude(remark='__GLOBAL_SWITCH__')
            
            whitelist_data = {
                'version': '1.0',
                'update_time': '',
                'enabled': self._get_list_global_switch(WafUrlWhitelist),
                'urls': []
            }
            for item in url_whitelist:
                whitelist_data['urls'].append({
                    'id': item.id,
                    'url': item.url,
                    'match_type': item.match_type,
                    'remark': item.remark or '',
                })
            
            blacklist_data = {
                'version': '1.0',
                'update_time': '',
                'enabled': self._get_list_global_switch(WafUrlBlacklist),
                'urls': []
            }
            for item in url_blacklist:
                blacklist_data['urls'].append({
                    'id': item.id,
                    'url': item.url,
                    'match_type': item.match_type,
                    'response_code': item.response_code if hasattr(item, 'response_code') else 403,
                    'remark': item.remark or '',
                })
            
            whitelist_file = os.path.join(self.waf_config_dir, 'url_whitelist.json')
            with open(whitelist_file, 'w', encoding='utf-8') as f:
                json.dump(whitelist_data, f, ensure_ascii=False, indent=2)
            
            blacklist_file = os.path.join(self.waf_config_dir, 'url_blacklist.json')
            with open(blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(blacklist_data, f, ensure_ascii=False, indent=2)
            
            return True, f"URL名单同步成功，白名单{len(whitelist_data['urls'])}条，黑名单{len(blacklist_data['urls'])}条"
        except Exception as e:
            return False, f"URL名单同步失败: {str(e)}"
    
    def sync_ua_list(self):
        """
        同步UA白名单和黑名单
        """
        try:
            ua_whitelist = WafUaList.objects.filter(
                list_type='whitelist', 
                enabled=True, 
                site_id__isnull=True
            ).exclude(remark='__GLOBAL_SWITCH__')
            
            ua_blacklist = WafUaList.objects.filter(
                list_type='blacklist', 
                enabled=True, 
                site_id__isnull=True
            ).exclude(remark='__GLOBAL_SWITCH__')
            
            whitelist_data = {
                'version': '1.0',
                'update_time': '',
                'enabled': self._get_list_global_switch(WafUaList, 'whitelist'),
                'keywords': []
            }
            for item in ua_whitelist:
                whitelist_data['keywords'].append({
                    'id': item.id,
                    'keyword': item.keyword,
                    'remark': item.remark or '',
                })
            
            blacklist_data = {
                'version': '1.0',
                'update_time': '',
                'enabled': self._get_list_global_switch(WafUaList, 'blacklist'),
                'keywords': []
            }
            for item in ua_blacklist:
                blacklist_data['keywords'].append({
                    'id': item.id,
                    'keyword': item.keyword,
                    'remark': item.remark or '',
                })
            
            whitelist_file = os.path.join(self.waf_config_dir, 'ua_whitelist.json')
            with open(whitelist_file, 'w', encoding='utf-8') as f:
                json.dump(whitelist_data, f, ensure_ascii=False, indent=2)
            
            blacklist_file = os.path.join(self.waf_config_dir, 'ua_blacklist.json')
            with open(blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(blacklist_data, f, ensure_ascii=False, indent=2)
            
            return True, f"UA名单同步成功，白名单{len(whitelist_data['keywords'])}条，黑名单{len(blacklist_data['keywords'])}条"
        except Exception as e:
            return False, f"UA名单同步失败: {str(e)}"
    
    def sync_ip_groups(self):
        """
        同步IP组 - 生成Lua脚本所需的ip_groups.json
        包含IP列表和预计算的IP范围，便于Lua快速匹配
        """
        try:
            groups = WafIpGroup.objects.all()
            groups_data = {
                'version': '1.0',
                'update_time': '',
                'groups': {}
            }
            
            for group in groups:
                ips = group.get_ip_list()
                ip_ranges = self._build_ip_ranges_for_lua(ips)
                groups_data['groups'][str(group.id)] = {
                    'id': group.id,
                    'name': group.name,
                    'ips': ips,
                    'ip_ranges': ip_ranges,
                }
            
            groups_file = os.path.join(self.waf_config_dir, 'ip_groups.json')
            with open(groups_file, 'w', encoding='utf-8') as f:
                json.dump(groups_data, f, ensure_ascii=False, indent=2)
            
            return True, f"IP组同步成功，共{len(groups_data['groups'])}个组"
        except Exception as e:
            return False, f"IP组同步失败: {str(e)}"
    
    def generate_nginx_waf_config(self):
        """
        生成Nginx WAF配置片段
        """
        try:
            config = WafGlobalConfig.get_instance()
            
            status_map = {'off': '关闭', 'observe': '观察模式', 'protect': '防护模式'}
            status_display = status_map.get(config.waf_status, '关闭')
            
            waf_data_path = self.waf_config_dir.replace('\\', '/')
            lua_path = self.lua_dir.replace('\\', '/')
            
            nginx_config = f'''# WAF Configuration - Generated by Ruyi Panel
# WAF Status: {config.waf_status} ({status_display})

# Lua Shared Dictionary
lua_shared_dict waf_cache 10m;
lua_shared_dict waf_attack_log 10m;

# Lua Package Path
lua_package_path "{lua_path}/?.lua;;";

# WAF Init
init_by_lua_block {{
    local waf_check = require("waf_check")
}}

init_worker_by_lua_block {{
    package.loaded.waf_data_path = "{waf_data_path}"
    local waf_init = require("waf_init")
    waf_init.init_worker()
}}

# WAF Access Check (include this in server block)
# access_by_lua_block {{
#     local waf_check = require("waf_check")
#     waf_check.check()
# }}
'''
            
            config_file = os.path.join(self.waf_config_dir, 'nginx_waf.conf')
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(nginx_config)
            
            self._update_nginx_main_config(config.waf_status)
            
            return True, "Nginx WAF配置生成成功"
        except Exception as e:
            return False, f"Nginx WAF配置生成失败: {str(e)}"
    
    def _update_nginx_main_config(self, waf_status):
        """
        更新nginx主配置文件中的WAF配置
        """
        try:
            from utils.common import ReadFile, WriteFile
            from utils.install.nginx import get_nginx_path_info
            
            soft_paths = get_nginx_path_info()
            nginx_conf_path = soft_paths['abspath_conf_path']
            
            if not os.path.exists(nginx_conf_path):
                return False, "nginx.conf 不存在"
            
            content = ReadFile(nginx_conf_path)
            if content is None:
                return False, "读取 nginx.conf 失败"
            
            waf_include_line = f"include {self.waf_config_dir.replace(chr(92), '/')}/nginx_waf.conf;"
            marker = "#ruyi_waf_line please do not delete"
            
            if waf_status == 'off':
                new_content = content.replace(f"{marker}\n    {waf_include_line}\n", f"{marker}\n")
                new_content = new_content.replace(f"{marker}\n{waf_include_line}\n", f"{marker}\n")
            else:
                if waf_include_line in content:
                    new_content = content
                else:
                    if marker in content:
                        new_content = content.replace(
                            marker,
                            f"{marker}\n    {waf_include_line}"
                        )
                    else:
                        http_block_end = content.rfind('}')
                        if http_block_end > 0:
                            new_content = content[:http_block_end] + \
                                f"\n    {marker}\n    {waf_include_line}\n" + \
                                content[http_block_end:]
                        else:
                            return False, "nginx.conf 格式错误"
            
            if new_content != content:
                WriteFile(nginx_conf_path, new_content)
            
            return True, "nginx.conf 更新成功"
        except Exception as e:
            return False, f"更新 nginx.conf 失败: {str(e)}"
    
    def copy_lua_scripts(self):
        """
        复制Lua脚本到data目录
        """
        try:
            dest_lua_dir = os.path.join(self.waf_config_dir, 'lua')
            if not os.path.exists(dest_lua_dir):
                os.makedirs(dest_lua_dir)
            
            lua_files = ['waf_utils.lua', 'waf_init.lua', 'waf_check.lua', 'waf_cc.lua', 'waf_rules.lua']
            
            for lua_file in lua_files:
                src = os.path.join(self.lua_dir, lua_file)
                dst = os.path.join(dest_lua_dir, lua_file)
                if os.path.exists(src):
                    shutil.copy2(src, dst)
            
            return True, f"Lua脚本复制成功，共{len(lua_files)}个文件"
        except Exception as e:
            return False, f"Lua脚本复制失败: {str(e)}"
    
    def sync_all(self):
        """
        同步所有WAF配置
        """
        results = []
        
        success, msg = self.sync_global_config()
        results.append(('全局配置', success, msg))
        
        success, msg = self.sync_site_config()
        results.append(('站点配置', success, msg))
        
        success, msg = self.sync_rules()
        results.append(('防护规则', success, msg))
        
        success, msg = self.sync_ip_list()
        results.append(('IP名单', success, msg))
        
        success, msg = self.sync_url_lists()
        results.append(('URL名单', success, msg))
        
        success, msg = self.sync_ua_list()
        results.append(('UA名单', success, msg))
        
        success, msg = self.sync_ip_groups()
        results.append(('IP组', success, msg))
        
        success, msg = self.generate_nginx_waf_config()
        results.append(('Nginx配置', success, msg))
        
        success, msg = self.copy_lua_scripts()
        results.append(('Lua脚本', success, msg))
        
        return results


def sync_waf_config(site_id=None):
    """
    同步WAF配置的便捷函数
    """
    syncer = WafConfigSync()
    if site_id:
        return syncer.sync_site_config(site_id)
    return syncer.sync_all()


def get_waf_status():
    """
    获取WAF状态
    """
    try:
        config = WafGlobalConfig.get_instance()
        status_map = {'off': '关闭', 'observe': '观察模式', 'protect': '防护模式'}
        return {
            'status': config.waf_status,
            'status_display': status_map.get(config.waf_status, '关闭'),
        }
    except Exception:
        return {
            'status': 'off',
            'status_display': '关闭',
        }
