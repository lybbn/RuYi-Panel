from django.db import models
from utils.models import table_prefix, BaseModel


class CloudStorageAccount(BaseModel):
    PROVIDER_CHOICES = (
        ('aliyun_oss', '阿里云 OSS'),
        ('tencent_cos', '腾讯云 COS'),
        ('huawei_obs', '华为云 OBS'),
        ('baidu_bos', '百度云 BOS'),
        ('jd_oss', '京东云 OSS'),
        ('ks_ks3', '金山云 KS3'),
        ('ctyun_zos', '天翼云 ZOS'),
        ('qiniu_kodo', '七牛云 Kodo'),
        ('cloudflare_r2', 'Cloudflare R2'),
        ('google_gcs', '谷歌云存储'),
        ('minio', 'MinIO'),
        ('webdav', 'WebDAV'),
        ('onedrive', 'OneDrive'),
    )
    PROTOCOL_CHOICES = (
        ('s3', 'S3协议'),
        ('native', '原生SDK'),
        ('webdav', 'WebDAV协议'),
        ('onedrive', 'OneDrive API'),
    )
    name = models.CharField(max_length=128, verbose_name='账号名称')
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, verbose_name='云厂商')
    protocol = models.CharField(max_length=16, choices=PROTOCOL_CHOICES, default='s3', verbose_name='协议类型')
    access_key = models.CharField(max_length=256, verbose_name='AccessKey')
    secret_key = models.CharField(max_length=512, verbose_name='SecretKey')
    endpoint = models.CharField(max_length=256, blank=True, default='', verbose_name='Endpoint')
    region = models.CharField(max_length=64, blank=True, default='', verbose_name='地域')
    bucket = models.CharField(max_length=128, blank=True, default='', verbose_name='存储桶')
    backup_path = models.CharField(max_length=256, default='/ruyi_backup/', verbose_name='云端路径')
    extra_config = models.TextField(blank=True, default='{}', verbose_name='扩展配置JSON')
    is_default = models.BooleanField(default=False, verbose_name='默认备份账号')
    status = models.SmallIntegerField(default=0, verbose_name='状态')
    last_test_time = models.DateTimeField(null=True, blank=True, verbose_name='最后测试时间')
    sdk_installed = models.BooleanField(default=False, verbose_name='SDK已安装')
    remark = models.TextField(blank=True, default='', verbose_name='备注')
    storage_quota = models.BigIntegerField(default=0, verbose_name='存储配额(字节)', help_text='手动设置的存储配额，0表示不限')

    class Meta:
        db_table = table_prefix + "cloud_account"
        verbose_name = "云存储账号"
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "syscloud"

    def __str__(self):
        return f"{self.name}({self.get_provider_display()})"


class CloudMountRecord(BaseModel):
    MOUNT_STATUS_CHOICES = (
        (0, '未挂载'),
        (1, '已挂载'),
        (2, '挂载异常'),
    )
    account = models.ForeignKey(
        CloudStorageAccount, on_delete=models.CASCADE,
        related_name='mount_records', verbose_name='云存储账号'
    )
    mount_path = models.CharField(max_length=512, verbose_name='本地挂载路径')
    mount_status = models.SmallIntegerField(
        choices=MOUNT_STATUS_CHOICES, default=0, verbose_name='挂载状态'
    )
    mount_options = models.TextField(blank=True, default='', verbose_name='挂载选项')
    auto_mount = models.BooleanField(default=False, verbose_name='开机自动挂载')

    class Meta:
        db_table = table_prefix + "cloud_mount"
        verbose_name = "云存储挂载记录"
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "syscloud"

    def __str__(self):
        return f"{self.account.name} -> {self.mount_path}"


class CloudSdkRecord(BaseModel):
    SDK_CHOICES = (
        ('boto3', 'boto3 (S3兼容客户端)'),
        ('oss2', 'oss2 (阿里云OSS)'),
        ('cos-python-sdk-v5', 'cos-sdk (腾讯云COS)'),
        ('qiniu', 'qiniu (七牛云)'),
        ('minio', 'minio (MinIO)'),
        ('webdavclient3', 'webdavclient3 (WebDAV)'),
        ('msal', 'msal (OneDrive)'),
        ('rclone', 'rclone (云存储挂载工具)'),
    )
    INSTALL_STATUS_CHOICES = (
        (0, '未安装'),
        (1, '已安装'),
        (2, '安装中'),
        (3, '安装失败'),
    )
    sdk_name = models.CharField(max_length=64, choices=SDK_CHOICES, verbose_name='SDK包名')
    sdk_version = models.CharField(max_length=32, blank=True, default='', verbose_name='已安装版本')
    install_status = models.SmallIntegerField(
        choices=INSTALL_STATUS_CHOICES, default=0, verbose_name='安装状态'
    )
    install_time = models.DateTimeField(null=True, blank=True, verbose_name='安装时间')
    provider_keys = models.CharField(max_length=256, blank=True, default='', verbose_name='关联厂商key列表')
    error_msg = models.TextField(blank=True, default='', verbose_name='错误信息')

    class Meta:
        db_table = table_prefix + "cloud_sdk"
        verbose_name = "云存储SDK记录"
        verbose_name_plural = verbose_name
        ordering = ('id',)
        app_label = "syscloud"

    def __str__(self):
        return f"{self.sdk_name} - {self.get_install_status_display()}"
