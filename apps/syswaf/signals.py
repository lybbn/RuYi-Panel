#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Copyright (c) 如意面板 All rights reserved.
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.conf import settings
import threading
import logging

logger = logging.getLogger(__name__)

_sync_lock = threading.Lock()


def _async_sync_waf_config(site_id=None, sync_type='all'):
    """
    异步同步WAF配置，避免阻塞请求
    """
    def _do_sync():
        try:
            from apps.syswaf.services import WafConfigSync
            syncer = WafConfigSync()
            
            if sync_type == 'global':
                syncer.sync_global_config()
            elif sync_type == 'site' and site_id:
                syncer.sync_site_config(site_id)
            elif sync_type == 'rules':
                syncer.sync_rules()
            elif sync_type == 'ip_list':
                syncer.sync_ip_list()
            elif sync_type == 'url_list':
                syncer.sync_url_lists()
            elif sync_type == 'ua_list':
                syncer.sync_ua_list()
            elif sync_type == 'ip_groups':
                syncer.sync_ip_groups()
            else:
                syncer.sync_all()
            
            _reload_nginx()
            
            logger.info(f"WAF配置同步完成: sync_type={sync_type}, site_id={site_id}")
        except Exception as e:
            logger.error(f"WAF配置同步失败: {e}")
    
    thread = threading.Thread(target=_do_sync, daemon=True)
    thread.start()


def _reload_nginx():
    """
    重载 Nginx 配置以清除 Lua 缓存
    """
    try:
        from utils.install.nginx import Reload_Nginx, is_nginx_running
        from utils.common import current_os
        
        is_windows = current_os == "windows"
        
        if is_nginx_running(is_windows=is_windows, simple_check=True):
            Reload_Nginx(is_windows=is_windows)
            logger.info("Nginx 配置已重载")
        else:
            logger.info("Nginx 未运行，跳过重载")
    except Exception as e:
        logger.warning(f"Nginx 重载失败: {e}")


@receiver(post_save, sender='syswaf.WafGlobalConfig')
def on_global_config_save(sender, instance, created, **kwargs):
    """
    全局配置保存后自动同步
    """
    _async_sync_waf_config(sync_type='global')


@receiver(post_save, sender='syswaf.WafSiteConfig')
def on_site_config_save(sender, instance, created, **kwargs):
    """
    站点配置保存后自动同步
    """
    _async_sync_waf_config(site_id=instance.site_id, sync_type='site')


@receiver(post_delete, sender='syswaf.WafSiteConfig')
def on_site_config_delete(sender, instance, **kwargs):
    """
    站点配置删除后自动同步（清理对应配置文件）
    """
    import os
    try:
        from django.conf import settings
        config_file = os.path.join(
            settings.RUYI_WAF_DATA_PATH, 
            'sites', 
            f'site_{instance.site_id}.json'
        )
        if os.path.exists(config_file):
            os.remove(config_file)
    except Exception as e:
        logger.error(f"删除站点配置文件失败: {e}")
    
    _async_sync_waf_config(sync_type='site')


@receiver(post_save, sender='syswaf.WafRule')
@receiver(post_delete, sender='syswaf.WafRule')
def on_rule_change(sender, instance, **kwargs):
    """
    规则变更后自动同步
    """
    _async_sync_waf_config(sync_type='rules')


@receiver(post_save, sender='syswaf.WafIpList')
@receiver(post_delete, sender='syswaf.WafIpList')
def on_ip_list_change(sender, instance, **kwargs):
    """
    IP名单变更后自动同步
    """
    _async_sync_waf_config(sync_type='ip_list')


@receiver(post_save, sender='syswaf.WafIpGroup')
@receiver(post_delete, sender='syswaf.WafIpGroup')
def on_ip_group_change(sender, instance, **kwargs):
    """
    IP组变更后自动同步
    只需同步 ip_groups.json，Lua运行时动态读取IP数据
    """
    _async_sync_waf_config(sync_type='ip_groups')


@receiver(post_save, sender='syswaf.WafUrlWhitelist')
@receiver(post_delete, sender='syswaf.WafUrlWhitelist')
@receiver(post_save, sender='syswaf.WafUrlBlacklist')
@receiver(post_delete, sender='syswaf.WafUrlBlacklist')
def on_url_list_change(sender, instance, **kwargs):
    """
    URL名单变更后自动同步
    """
    _async_sync_waf_config(sync_type='url_list')


@receiver(post_save, sender='syswaf.WafUaList')
@receiver(post_delete, sender='syswaf.WafUaList')
def on_ua_list_change(sender, instance, **kwargs):
    """
    UA名单变更后自动同步
    """
    _async_sync_waf_config(sync_type='ua_list')
