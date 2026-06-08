import logging

logger = logging.getLogger(__name__)


class CdnProviderBase:
    """CDN缓存管理基类"""

    provider_name = ""
    provider_display = ""

    # 各厂商支持的CDN功能
    supports_purge_url = False       # 按URL刷新
    supports_purge_all = False       # 全量刷新
    supports_purge_tag = False       # 按标签刷新（Cache-Tag）
    supports_preload = False         # 预热
    supports_quota = False           # 查询刷新配额

    def __init__(self, credentials):
        self.credentials = credentials

    def purge_urls(self, urls):
        """按URL刷新缓存"""
        raise NotImplementedError

    def purge_all(self):
        """全量刷新缓存"""
        raise NotImplementedError

    def purge_tags(self, tags):
        """按Cache-Tag刷新缓存"""
        raise NotImplementedError

    def preload_urls(self, urls):
        """预热URL"""
        raise NotImplementedError

    def get_purge_quota(self):
        """查询刷新配额"""
        raise NotImplementedError

    def get_cache_rules(self):
        """获取缓存规则列表"""
        raise NotImplementedError
