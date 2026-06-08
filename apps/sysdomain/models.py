from django.db import models
from utils.models import table_prefix, BaseModel


class DnsAccount(BaseModel):
    PROVIDER_CHOICES = (
        ('dnspod', 'DNSPod'),
        ('aliyun', '阿里云'),
        ('tencentcloud', '腾讯云'),
        ('huaweicloud', '华为云'),
        ('cloudflare', 'CloudFlare'),
        ('west', '西部数码'),
        ('aws', 'AWS'),
        ('volcengine', '火山引擎'),
    )

    name = models.CharField(max_length=100, verbose_name='账号名称')
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, verbose_name='DNS服务商')
    credentials = models.JSONField(verbose_name='认证凭据', default=dict)
    remark = models.CharField(max_length=255, verbose_name='备注', null=True, blank=True)

    class Meta:
        db_table = table_prefix + "dns_account"
        verbose_name = 'DNS账号'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysdomain"

    def __str__(self):
        return f"{self.name}({self.get_provider_display()})"


class DomainHosting(BaseModel):
    dns_account = models.ForeignKey(
        DnsAccount, on_delete=models.CASCADE, verbose_name='DNS账号',
        db_constraint=False, null=True, blank=True
    )
    domain = models.CharField(max_length=255, verbose_name='域名', db_index=True)
    domain_id = models.CharField(max_length=100, verbose_name='远程域名ID', null=True, blank=True)
    remark = models.CharField(max_length=255, verbose_name='备注', null=True, blank=True)
    record_count = models.IntegerField(verbose_name='解析记录数', default=0)

    class Meta:
        db_table = table_prefix + "domain_hosting"
        verbose_name = '域名托管'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysdomain"

    def __str__(self):
        return self.domain
