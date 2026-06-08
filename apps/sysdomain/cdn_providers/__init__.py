from .base import CdnProviderBase
from .cloudflare import CloudflareCdnProvider
from .aliyun import AliyunCdnProvider
from .tencentcloud import TencentCloudCdnProvider
from .huaweicloud import HuaweiCloudCdnProvider
from .volcengine import VolcengineCdnProvider
from .aws import AwsCloudFrontProvider
from .factory import get_cdn_provider, get_cdn_provider_info, get_all_cdn_providers
