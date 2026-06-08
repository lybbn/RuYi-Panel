from .dnspod import DnspodProvider
from .aliyun import AliyunProvider
from .tencentcloud import TencentCloudProvider
from .huaweicloud import HuaweiCloudProvider
from .cloudflare import CloudflareProvider
from .west import WestProvider
from .aws import AwsProvider
from .volcengine import VolcengineProvider

PROVIDER_MAP = {
    'dnspod': DnspodProvider,
    'aliyun': AliyunProvider,
    'tencentcloud': TencentCloudProvider,
    'huaweicloud': HuaweiCloudProvider,
    'cloudflare': CloudflareProvider,
    'west': WestProvider,
    'aws': AwsProvider,
    'volcengine': VolcengineProvider,
}

PROVIDER_PARAMS = {
    'dnspod': {'name': 'DNSPod', 'id': 'DNSPod', 'params': ['ID', 'Token']},
    'aliyun': {'name': '阿里云', 'id': 'AliyunDns', 'params': ['AccessKey', 'SecretKey']},
    'tencentcloud': {'name': '腾讯云', 'id': 'TencentCloudDns', 'params': ['secret_id', 'secret_key']},
    'huaweicloud': {'name': '华为云', 'id': 'HuaweiCloudDns', 'params': ['AccessKey', 'SecretKey', 'project_id']},
    'cloudflare': {
        'name': 'CloudFlare',
        'id': 'CloudFlareDns',
        'params': ['API Token'],
        'auth_modes': [
            {'key': 'api_token', 'label': 'API Token', 'params': ['API Token']},
            {'key': 'global_key', 'label': 'E-Mail + API Key', 'params': ['E-Mail', 'API Key']},
        ],
    },
    'west': {'name': '西部数码', 'id': 'WestDns', 'params': ['user_name', 'api_password']},
    'aws': {'name': 'AWS', 'id': 'AwsDns', 'params': ['AccessKey', 'SecretKey', 'region']},
    'volcengine': {'name': '火山引擎', 'id': 'VolcengineCloudDns', 'params': ['AccessKey', 'SecretKey']},
}


PROVIDER_LINES = {
    'dnspod': [
        {'value': '默认', 'label': '默认'},
        {'value': '电信', 'label': '电信'},
        {'value': '联通', 'label': '联通'},
        {'value': '移动', 'label': '移动'},
        {'value': '教育网', 'label': '教育网'},
        {'value': '铁通', 'label': '铁通'},
        {'value': '搜索', 'label': '搜索引擎'},
        {'value': '境外', 'label': '境外'},
    ],
    'aliyun': [
        {'value': 'default', 'label': '默认'},
        {'value': 'telecom', 'label': '电信'},
        {'value': 'unicom', 'label': '联通'},
        {'value': 'mobile', 'label': '移动'},
        {'value': 'edu', 'label': '教育网'},
        {'value': 'oversea', 'label': '境外'},
    ],
    'tencentcloud': [
        {'value': '默认', 'label': '默认'},
        {'value': '电信', 'label': '电信'},
        {'value': '联通', 'label': '联通'},
        {'value': '移动', 'label': '移动'},
        {'value': '教育网', 'label': '教育网'},
        {'value': '境外', 'label': '境外'},
    ],
    'huaweicloud': [
        {'value': 'default_view', 'label': '默认'},
        {'value': 'Dianxin', 'label': '电信'},
        {'value': 'Liantong', 'label': '联通'},
        {'value': 'Yidong', 'label': '移动'},
        {'value': 'Jiaoyuwang', 'label': '教育网'},
        {'value': 'Tietong', 'label': '铁通'},
    ],
    'cloudflare': [
        {'value': 'DNS only', 'label': 'DNS only'},
        {'value': 'Proxied', 'label': 'Proxied'},
    ],
    'west': [
        {'value': '默认', 'label': '默认'},
    ],
    'aws': [
        {'value': '默认', 'label': '默认'},
    ],
    'volcengine': [
        {'value': '默认', 'label': '默认'},
    ],
}

PROVIDER_TTL = {
    'dnspod': [
        {'value': 60, 'label': '1 分钟'},
        {'value': 120, 'label': '2 分钟'},
        {'value': 300, 'label': '5 分钟'},
        {'value': 600, 'label': '10 分钟'},
        {'value': 1800, 'label': '30 分钟'},
        {'value': 3600, 'label': '1 小时'},
        {'value': 21600, 'label': '6 小时'},
        {'value': 43200, 'label': '12 小时'},
        {'value': 86400, 'label': '1 天'},
    ],
    'aliyun': [
        {'value': 60, 'label': '1 分钟'},
        {'value': 120, 'label': '2 分钟'},
        {'value': 300, 'label': '5 分钟'},
        {'value': 600, 'label': '10 分钟'},
        {'value': 1800, 'label': '30 分钟'},
        {'value': 3600, 'label': '1 小时'},
        {'value': 21600, 'label': '6 小时'},
        {'value': 43200, 'label': '12 小时'},
        {'value': 86400, 'label': '1 天'},
        {'value': 604800, 'label': '7 天'},
    ],
    'tencentcloud': [
        {'value': 60, 'label': '1 分钟'},
        {'value': 120, 'label': '2 分钟'},
        {'value': 300, 'label': '5 分钟'},
        {'value': 600, 'label': '10 分钟'},
        {'value': 1800, 'label': '30 分钟'},
        {'value': 3600, 'label': '1 小时'},
        {'value': 21600, 'label': '6 小时'},
        {'value': 43200, 'label': '12 小时'},
        {'value': 86400, 'label': '1 天'},
    ],
    'huaweicloud': [
        {'value': 300, 'label': '5 分钟'},
        {'value': 600, 'label': '10 分钟'},
        {'value': 1800, 'label': '30 分钟'},
        {'value': 3600, 'label': '1 小时'},
        {'value': 21600, 'label': '6 小时'},
        {'value': 43200, 'label': '12 小时'},
        {'value': 86400, 'label': '1 天'},
    ],
    'cloudflare': [
        {'value': 1, 'label': 'Auto'},
        {'value': 60, 'label': '1 分钟'},
        {'value': 120, 'label': '2 分钟'},
        {'value': 300, 'label': '5 分钟'},
        {'value': 600, 'label': '10 分钟'},
        {'value': 1800, 'label': '30 分钟'},
        {'value': 3600, 'label': '1 小时'},
        {'value': 21600, 'label': '6 小时'},
        {'value': 43200, 'label': '12 小时'},
        {'value': 86400, 'label': '1 天'},
    ],
    'west': [
        {'value': 600, 'label': '10 分钟'},
        {'value': 1800, 'label': '30 分钟'},
        {'value': 3600, 'label': '1 小时'},
        {'value': 21600, 'label': '6 小时'},
        {'value': 43200, 'label': '12 小时'},
        {'value': 86400, 'label': '1 天'},
    ],
    'aws': [
        {'value': 60, 'label': '1 分钟'},
        {'value': 120, 'label': '2 分钟'},
        {'value': 300, 'label': '5 分钟'},
        {'value': 600, 'label': '10 分钟'},
        {'value': 1800, 'label': '30 分钟'},
        {'value': 3600, 'label': '1 小时'},
        {'value': 21600, 'label': '6 小时'},
        {'value': 43200, 'label': '12 小时'},
        {'value': 86400, 'label': '1 天'},
    ],
    'volcengine': [
        {'value': 600, 'label': '10 分钟'},
        {'value': 1800, 'label': '30 分钟'},
        {'value': 3600, 'label': '1 小时'},
        {'value': 21600, 'label': '6 小时'},
        {'value': 43200, 'label': '12 小时'},
        {'value': 86400, 'label': '1 天'},
    ],
}


def get_provider(provider_key, credentials):
    provider_cls = PROVIDER_MAP.get(provider_key)
    if not provider_cls:
        raise ValueError("Unsupported DNS provider: {}".format(provider_key))
    return provider_cls(credentials)


def get_provider_params():
    result = []
    for key, info in PROVIDER_PARAMS.items():
        item = {
            'name': info['name'],
            'id': info['id'],
            'key': key,
            'params': info['params'],
        }
        if 'auth_modes' in info:
            item['auth_modes'] = info['auth_modes']
        result.append(item)
    return result


def get_provider_line_ttl(provider_key):
    return {
        'lines': PROVIDER_LINES.get(provider_key, [{'value': '默认', 'label': '默认'}]),
        'ttl': PROVIDER_TTL.get(provider_key, [{'value': 600, 'label': '10 分钟'}]),
    }
