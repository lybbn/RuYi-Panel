from .base import CdnProviderBase
from .cloudflare import CloudflareCdnProvider
from .aliyun import AliyunCdnProvider
from .tencentcloud import TencentCloudCdnProvider
from .huaweicloud import HuaweiCloudCdnProvider
from .volcengine import VolcengineCdnProvider
from .aws import AwsCloudFrontProvider

# CDN厂商注册表
# key: 与DnsAccount.provider一致，方便通过DNS账号关联CDN
CDN_PROVIDER_REGISTRY = {
    'cloudflare': {
        'name': 'Cloudflare',
        'provider_class': CloudflareCdnProvider,
        'supports_purge_url': True,
        'supports_purge_all': True,
        'supports_purge_tag': True,
        'supports_preload': False,
        'supports_quota': False,
    },
    'aliyun': {
        'name': '阿里云CDN',
        'provider_class': AliyunCdnProvider,
        'supports_purge_url': True,
        'supports_purge_all': True,
        'supports_purge_tag': False,
        'supports_preload': True,
        'supports_quota': True,
    },
    'tencentcloud': {
        'name': '腾讯云CDN',
        'provider_class': TencentCloudCdnProvider,
        'supports_purge_url': True,
        'supports_purge_all': True,
        'supports_purge_tag': False,
        'supports_preload': True,
        'supports_quota': True,
    },
    'huaweicloud': {
        'name': '华为云CDN',
        'provider_class': HuaweiCloudCdnProvider,
        'supports_purge_url': True,
        'supports_purge_all': True,
        'supports_purge_tag': False,
        'supports_preload': True,
        'supports_quota': True,
    },
    'volcengine': {
        'name': '火山引擎CDN',
        'provider_class': VolcengineCdnProvider,
        'supports_purge_url': True,
        'supports_purge_all': True,
        'supports_purge_tag': False,
        'supports_preload': True,
        'supports_quota': True,
    },
    'aws': {
        'name': 'AWS CloudFront',
        'provider_class': AwsCloudFrontProvider,
        'supports_purge_url': True,
        'supports_purge_all': True,
        'supports_purge_tag': False,
        'supports_preload': False,
        'supports_quota': False,
    },
}


def get_cdn_provider(dns_account, zone_id=None, domain_name=None):
    """根据DNS账号获取CDN管理实例"""
    provider_key = dns_account.provider
    registry = CDN_PROVIDER_REGISTRY.get(provider_key)
    if not registry:
        return None
    provider_class = registry['provider_class']
    return provider_class(dns_account.credentials, zone_id=zone_id, domain_name=domain_name)


def get_cdn_provider_info(provider_key):
    """获取CDN厂商支持的功能信息"""
    registry = CDN_PROVIDER_REGISTRY.get(provider_key)
    if not registry:
        return None
    return {
        'provider': provider_key,
        'name': registry['name'],
        'supports_purge_url': registry['supports_purge_url'],
        'supports_purge_all': registry['supports_purge_all'],
        'supports_purge_tag': registry['supports_purge_tag'],
        'supports_preload': registry['supports_preload'],
        'supports_quota': registry['supports_quota'],
    }


def get_all_cdn_providers():
    """获取所有CDN厂商信息"""
    result = []
    for key, info in CDN_PROVIDER_REGISTRY.items():
        result.append({
            'provider': key,
            'name': info['name'],
            'supports_purge_url': info['supports_purge_url'],
            'supports_purge_all': info['supports_purge_all'],
            'supports_purge_tag': info['supports_purge_tag'],
            'supports_preload': info['supports_preload'],
            'supports_quota': info['supports_quota'],
        })
    return result
