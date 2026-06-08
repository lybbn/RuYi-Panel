import os
import json
import platform
from django.conf import settings


RCLONE_PROVIDER_MAP = {
    'aliyun_oss': {'type': 's3', 'provider': 'Alibaba'},
    'tencent_cos': {'type': 's3', 'provider': 'TencentCOS'},
    'huawei_obs': {'type': 's3', 'provider': 'HuaweiOBS'},
    'baidu_bos': {'type': 's3', 'provider': 'BaiduBOS'},
    'jd_oss': {'type': 's3', 'provider': 'JDOS'},
    'ks_ks3': {'type': 's3', 'provider': 'KsyunKS3'},
    'ctyun_zos': {'type': 's3', 'provider': 'CTYunOOS'},
    'cloudflare_r2': {'type': 's3', 'provider': 'Cloudflare'},
    'google_gcs': {'type': 's3', 'provider': 'GCS'},
    'minio': {'type': 's3', 'provider': 'Minio'},
    'qiniu_kodo': {'type': 's3', 'provider': 'Qiniu'},
    'webdav': {'type': 'webdav', 'provider': None},
    'onedrive': {'type': 'onedrive', 'provider': None},
}


def get_rclone_config_path():
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    config_dir = os.path.join(data_dir, 'rclone')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'rclone.conf')


def generate_rclone_config(account):
    rclone_info = RCLONE_PROVIDER_MAP.get(account.provider)
    if not rclone_info:
        return None

    section_name = "cloud_{}".format(account.id)
    rclone_type = rclone_info['type']
    rclone_provider = rclone_info.get('provider')

    config = {
        'type': rclone_type,
        'env_auth': 'false',
        'access_key_id': account.access_key,
        'secret_access_key': account.secret_key,
    }

    if rclone_provider:
        config['provider'] = rclone_provider

    if account.endpoint:
        config['endpoint'] = account.endpoint

    if account.region:
        config['region'] = account.region

    if rclone_type == 's3':
        from apps.syscloud.cloud_providers.factory import PROVIDER_REGISTRY
        provider_info = PROVIDER_REGISTRY.get(account.provider, {})
        if provider_info.get('s3_path_style'):
            config['force_path_style'] = 'true'

    if rclone_type == 'webdav':
        config['url'] = account.endpoint
        config['user'] = account.access_key
        config['pass'] = account.secret_key

    if rclone_type == 'onedrive':
        extra = {}
        try:
            extra = json.loads(account.extra_config) if account.extra_config else {}
        except (json.JSONDecodeError, TypeError):
            pass
        config['client_id'] = account.access_key
        config['client_secret'] = account.secret_key
        config['token'] = extra.get('rclone_token', '')

    return section_name, config


def write_rclone_conf(accounts=None):
    from apps.syscloud.models import CloudStorageAccount

    if accounts is None:
        accounts = CloudStorageAccount.objects.all()

    config_path = get_rclone_config_path()
    lines = []

    for account in accounts:
        result = generate_rclone_config(account)
        if not result:
            continue
        section_name, config = result
        lines.append("[{}]".format(section_name))
        for key, value in config.items():
            lines.append("{} = {}".format(key, value))
        lines.append("")

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return config_path
