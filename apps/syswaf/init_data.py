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
import logging
import requests
from apps.syswaf.models import WafGlobalConfig, WafRuleCategory, WafRule

logger = logging.getLogger(__name__)

# 远程规则下载地址
REMOTE_RULES_URL = "http://download.lybbn.cn/ruyi/install/common/waf/waf_rules.json"


def download_remote_rules(save_to_local=True):
    """
    从远程服务器下载最新规则
    
    Args:
        save_to_local: 是否保存到本地文件，默认为True
    
    Returns:
        dict: 包含categories和rules的字典，下载失败返回None
    """
    try:
        logger.info(f"正在从远程下载WAF规则: {REMOTE_RULES_URL}")
        response = requests.get(REMOTE_RULES_URL, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"远程规则下载成功")
        
        # 保存到本地文件
        if save_to_local and data:
            try:
                with open(LOCAL_RULES_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"远程规则已保存到本地文件: {LOCAL_RULES_FILE}")
            except Exception as e:
                logger.warning(f"保存远程规则到本地文件失败: {e}")
        
        return data
    except requests.exceptions.RequestException as e:
        logger.warning(f"从远程下载规则失败: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"解析远程规则JSON失败: {e}")
        return None
    except Exception as e:
        logger.warning(f"下载远程规则时发生错误: {e}")
        return None


import os

# 本地规则文件路径
LOCAL_RULES_FILE = os.path.join(os.path.dirname(__file__), 'data', 'waf_rules.json')


def load_local_rules():
    """
    从本地JSON文件加载规则数据
    
    Returns:
        dict: 包含categories和rules的字典，加载失败返回None
    """
    try:
        if os.path.exists(LOCAL_RULES_FILE):
            with open(LOCAL_RULES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"从本地文件加载规则成功: {LOCAL_RULES_FILE}")
                return data
        else:
            logger.warning(f"本地规则文件不存在: {LOCAL_RULES_FILE}")
            return None
    except Exception as e:
        logger.error(f"加载本地规则文件失败: {e}")
        return None


def get_default_rule_categories():
    """
    获取默认规则分类，从本地JSON文件读取
    
    Returns:
        list: 规则分类列表，加载失败返回None
    """
    data = load_local_rules()
    if data and data.get('categories'):
        return data['categories']
    
    logger.error("加载本地规则分类失败，waf_rules.json文件可能不存在或损坏")
    return None


def get_default_rules():
    """
    获取默认规则，从本地JSON文件读取
    
    Returns:
        list: 规则列表，加载失败返回None
    """
    data = load_local_rules()
    if data and data.get('rules'):
        rules = data['rules']
        # 确保targets字段是JSON字符串格式
        for rule in rules:
            if isinstance(rule.get('targets'), list):
                rule['targets'] = json.dumps(rule['targets'])
        return rules
    
    logger.error("加载本地规则失败，waf_rules.json文件可能不存在或损坏")
    return None


def get_default_global_config():
    return {
        'id': 1,
        'waf_status': 'off',
        'cc_config': json.dumps({
            'frequency': {'requestType': 'url_no_param', 'period': 60, 'frequency': 180, 'blockTime': 300, 'enabled': False},
            'tolerance': {'period': 600, 'threshold': 10, 'blockTime': 3600, 'enabled': False},
            'error_limit': {'period': 60, 'threshold': 10, 'blockTime': 300, 'enabled': False}
        }),
        'request_limit_config': json.dumps({
            'enabled': False,
            'allowedMethods': ['GET', 'POST', 'HEAD'],
            'blockEmptyUA': True,
            'blockEmptyReferer': False,
            'blockEmptyHost': True,
            'maxBodySize': 10485760,
            'maxUrlLength': 2048,
            'maxHeaderSize': 8192
        }),
        'geo_config': json.dumps({
            'enabled': False,
            'mode': 'whitelist',
            'ip_groups': [],
        }),
        'cdn_config': json.dumps({
            'enabled': False,
            'provider': 'auto',
            'realIpHeaders': [],
            'ipRanges': ''
        }),
        'rule_config': json.dumps({
            'sql': {'mode': 2},
            'xss': {'mode': 2},
            'command': {'mode': 2},
            'file_include': {'mode': 2},
            'sensitive_file': {'mode': 2},
            'scanner': {'mode': 2},
            'bot': {'mode': 2}
        }),
        'log_retention_days': 30,
    }


def init_waf_data(force=False):
    """
    初始化WAF数据
    
    Args:
        force: 是否强制重新初始化，为True时会尝试从远程下载最新规则
    
    Returns:
        tuple: (categories_created, rules_created, config_created, ip_group_created, from_remote)
    """
    from django.db.models.signals import post_save, post_delete
    from apps.syswaf import signals as waf_signals
    
    categories_created = 0
    rules_created = 0
    config_created = False
    ip_group_created = False
    from_remote = False
    
    post_save.disconnect(waf_signals.on_rule_change, sender='syswaf.WafRule')
    post_delete.disconnect(waf_signals.on_rule_change, sender='syswaf.WafRule')
    post_save.disconnect(waf_signals.on_ip_group_change, sender='syswaf.WafIpGroup')
    post_save.disconnect(waf_signals.on_global_config_save, sender='syswaf.WafGlobalConfig')
    
    try:
        if force:
            WafRule.objects.all().delete()
            WafRuleCategory.objects.all().delete()
        
        # 如果是强制更新，尝试从远程下载规则
        remote_data = None
        if force:
            remote_data = download_remote_rules()
        
        if remote_data and remote_data.get('categories') and remote_data.get('rules'):
            # 使用远程下载的规则
            from_remote = True
            logger.info("使用远程下载的规则数据")
            
            categories_data = remote_data['categories']
            rules_data = remote_data['rules']
            
            # 将规则中的targets从字符串转为JSON字符串格式（如果已经是字符串则保持不变）
            for rule in rules_data:
                if isinstance(rule.get('targets'), list):
                    rule['targets'] = json.dumps(rule['targets'])
        else:
            # 使用本地默认规则
            if force:
                logger.info("远程规则下载失败，使用本地默认规则")
            categories_data = get_default_rule_categories()
            rules_data = get_default_rules()
            
            # 检查本地规则是否加载成功
            if categories_data is None or rules_data is None:
                logger.error("WAF规则加载失败，无法初始化WAF数据。请检查waf_rules.json文件是否存在且格式正确。")
                return (0, 0, False, False, False)
        
        for cat_data in categories_data:
            _, created = WafRuleCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults=cat_data
            )
            if created:
                categories_created += 1
        
        for rule_data in rules_data:
            _, created = WafRule.objects.get_or_create(
                rule_id=rule_data['rule_id'],
                defaults=rule_data
            )
            if created:
                rules_created += 1
        
        china_ip_group, ip_group_created = init_china_ip_group()
        
        config_data = get_default_global_config()
        if china_ip_group and china_ip_group.id:
            geo_config = json.loads(config_data['geo_config'])
            geo_config['ip_groups'] = [china_ip_group.id]
            config_data['geo_config'] = json.dumps(geo_config, ensure_ascii=False)
        
        _, config_created = WafGlobalConfig.objects.get_or_create(
            id=1,
            defaults=config_data
        )
    finally:
        post_save.connect(waf_signals.on_rule_change, sender='syswaf.WafRule')
        post_delete.connect(waf_signals.on_rule_change, sender='syswaf.WafRule')
        post_save.connect(waf_signals.on_ip_group_change, sender='syswaf.WafIpGroup')
        post_save.connect(waf_signals.on_global_config_save, sender='syswaf.WafGlobalConfig')
        
        # 强制更新后手动触发配置同步，使规则立即生效
        if force and (categories_created > 0 or rules_created > 0):
            try:
                from apps.syswaf.services import WafConfigSync
                syncer = WafConfigSync()
                syncer.sync_rules()
                
                # 重载Nginx使配置生效
                from utils.install.nginx import Reload_Nginx, is_nginx_running
                from utils.common import current_os
                is_windows = current_os == "windows"
                if is_nginx_running(is_windows=is_windows, simple_check=True):
                    Reload_Nginx(is_windows=is_windows)
            except Exception as e:
                logger.error(f"WAF规则同步失败: {e}")
    
    return categories_created, rules_created, config_created, ip_group_created, from_remote


def get_china_ip_ranges():
    import os
    
    data_file = os.path.join(os.path.dirname(__file__), 'data', 'china_ip_ranges.txt')
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return content
    
    return ""


def get_china_ip_group():
    return {
        'name': '中国大陆IP段',
        'ip_content': get_china_ip_ranges()
    }


def init_china_ip_group():
    from apps.syswaf.models import WafIpGroup
    
    group_data = get_china_ip_group()
    group, created = WafIpGroup.objects.get_or_create(
        name=group_data['name'],
        defaults=group_data
    )
    return group, created
