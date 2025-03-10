from django.db import models
from utils.models import table_prefix,BaseModel

class RyDocker(BaseModel):

    STATUS_CHOICES = (
        ("", "未知"),
        ("paused", "已暂停"),
        ("running", "已启动"),
        ("exited", "已停止"),
    )
    name = models.CharField(max_length=100, verbose_name='容器名称')
    image_name = models.CharField(max_length=100, verbose_name='镜像名称')
    install_version = models.CharField(max_length=100, verbose_name='安装版本',null=True,blank=True)
    is_appstore = models.BooleanField(verbose_name="是否商店应用", default=False)
    ports = models.TextField(blank=True, null=True,verbose_name="端口映射")
    network = models.TextField(blank=True, null=True,verbose_name="网络")
    status = models.CharField(choices=STATUS_CHOICES, verbose_name="状态", default="",max_length=50)
    
    class Meta:
        db_table = table_prefix + "docker"
        verbose_name = '容器'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysdocker"
        
class RyDockerRepo(BaseModel):

    PROTOCOL_CHOICES = (
        ("http", "http"),
        ("https", "https")
    )
    name = models.CharField(max_length=100, verbose_name='仓库名称')
    url = models.TextField(blank=True, null=True,verbose_name="仓库URL")#去除协议前缀的url
    protocol = models.CharField(max_length=30, verbose_name='协议',choices=PROTOCOL_CHOICES,default="https")
    is_auth = models.BooleanField(verbose_name="是否认证", default=False)
    username = models.CharField(max_length=100, verbose_name='仓库用户名',null=True,blank=True)
    password = models.CharField(max_length=200, verbose_name='仓库密码',null=True,blank=True)
    
    class Meta:
        db_table = table_prefix + "docker_repo"
        verbose_name = '容器仓库'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysdocker"
        
class RyDockerApps(BaseModel):

    STATUS_CHOICES = (
        ("install", "安装中"),
        ("paused", "已暂停"),
        ("running", "已启动"),
        ("exited", "已停止"),
    )
    appid = models.IntegerField(verbose_name='所属应用id', default=0,null=True,blank=True)
    appname = models.CharField(verbose_name='所属应用名称',max_length=100,null=True,blank=True)
    type = models.CharField(verbose_name='所属应用类型',max_length=50,null=True,blank=True)
    name = models.CharField(max_length=100, verbose_name='应用名称')
    version = models.CharField(max_length=30, verbose_name='安装版本')
    cpu = models.IntegerField(verbose_name='cpu限制', default=0)
    mem = models.IntegerField(verbose_name='内存限制', default=0)
    allowport = models.BooleanField(verbose_name="放通外网端口", default=False)
    advanced = models.BooleanField(verbose_name="高级配置", default=False)
    params = models.TextField(blank=True, null=True,verbose_name="环境参数字典")
    status = models.CharField(choices=STATUS_CHOICES, verbose_name="状态", default="install",max_length=50)
    
    class Meta:
        db_table = table_prefix + "docker_apps"
        verbose_name = '容器广场APP' #已安装
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysdocker"