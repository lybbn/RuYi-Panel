DNS_PROVIDER_CONFIGS = [
    {
        "name": "DNSPod",
        "key": "dnspod",
        "params": ["ID", "Token"],
    },
    {
        "name": "阿里云",
        "key": "aliyun",
        "params": ["AccessKey", "SecretKey"],
    },
    {
        "name": "腾讯云",
        "key": "tencentcloud",
        "params": ["secret_id", "secret_key"],
    },
    {
        "name": "华为云",
        "key": "huaweicloud",
        "params": ["AccessKey", "SecretKey", "project_id"],
    },
    {
        "name": "CloudFlare",
        "key": "cloudflare",
        "params": ["API Token"],
    },
    {
        "name": "西部数码",
        "key": "west",
        "params": ["user_name", "api_password"],
    },
    {
        "name": "AWS",
        "key": "aws",
        "params": ["AccessKey", "SecretKey", "region"],
    },
    {
        "name": "火山引擎",
        "key": "volcengine",
        "params": ["AccessKey", "SecretKey"],
    },
]


def init_domain_data(force=False):
    from apps.sysdomain.models import DnsAccount, DomainHosting
    if force:
        DomainHosting.objects.all().delete()
        DnsAccount.objects.all().delete()
    return 0, 0
