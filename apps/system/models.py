from django.db import models
from django.contrib.auth.models import AbstractBaseUser,UserManager
from utils.models import table_prefix,BaseModel
from datetime import datetime

class Users(AbstractBaseUser, BaseModel):

    username = models.CharField(max_length=255, unique=True, db_index=True, verbose_name='用户账号')
    email = models.EmailField(max_length=255, verbose_name="邮箱", null=True, blank=True)
    mobile = models.CharField(max_length=255,verbose_name="电话", null=True, blank=True)
    is_staff = models.BooleanField(verbose_name="是否员工",default=False)
    is_superuser = models.BooleanField(verbose_name="是否超级管理员",default=False)

    objects = UserManager()
    EMAIL_FIELD = "email"
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = table_prefix + "users"
        verbose_name = '用户表'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "system"

class SiteGroup(BaseModel):

    name = models.CharField(max_length=255, verbose_name='分组名')
    is_default = models.BooleanField(default=False,verbose_name="是否默认分组")
    
    class Meta:
        db_table = table_prefix + "sites_group"
        verbose_name = '站点分组'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "system"

class Sites(BaseModel):

    TYPE_CHOICES = (
        (0, "Static"),#静态
        (1, "Python"),
        (2, "Node"),
        (3, "Php"),
        (4, "Go"),
    )

    name = models.CharField(max_length=255, verbose_name='站点名', null=True, blank=True)
    remark = models.CharField(max_length=255, verbose_name='备注', null=True, blank=True)
    path = models.CharField(max_length=255, verbose_name='站点根目录', null=True, blank=True)
    status = models.BooleanField(default=True, verbose_name="站点状态")
    type = models.IntegerField(verbose_name='类型', default=0,choices=TYPE_CHOICES)
    group = models.ForeignKey(SiteGroup, null=True,blank=True,verbose_name='所属分组', on_delete=models.CASCADE, db_constraint=False,default=0)
    sslcfg = models.TextField(verbose_name="SSL配置", null=True, blank=True,default=dict)
    wafcfg = models.TextField(verbose_name="WAF配置", null=True, blank=True,default=dict)
    project_cfg = models.TextField(verbose_name="项目配置", null=True, blank=True,default=dict)
    endTime = models.DateTimeField(null=True, blank=True, verbose_name='到期时间')#为空表示永不过期
    is_default = models.BooleanField(default=False,verbose_name="是否默认站点")
    access_log = models.BooleanField(default=True, verbose_name="启用访问日志")
    error_log = models.BooleanField(default=True, verbose_name="启用错误日志")
    
    def is_expired(self):
        now = datetime.now()
        # 如果 endTime 为 None，表示永不过期
        if self.endTime is None:
            return False
        return self.endTime < now
    
    class Meta:
        db_table = table_prefix + "sites"
        verbose_name = '站点'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "system"

class SiteDomains(BaseModel):

    name = models.CharField(max_length=255, verbose_name='域名', null=True, blank=True)
    port = models.IntegerField(verbose_name='端口', default=0)
    site = models.ForeignKey(Sites, null=True,blank=True,verbose_name='所属网站', on_delete=models.CASCADE, db_constraint=False)
    
    class Meta:
        db_table = table_prefix + "site_domains"
        verbose_name = '站点域名'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "system"

class CertManage(BaseModel):
    STORETYPE_CHOICE = (
        ("local", "本地"),
        ("remote", "远程"),
    )
    APPLY_TYPE_CHOICE = (
        (0, "自签名"),
        (1, "远程"),
    )

    name = models.CharField(max_length=255, verbose_name='域名', null=True, blank=True)
    path = models.CharField(max_length=255, verbose_name='证书目录', null=True, blank=True)
    endTime = models.DateTimeField(null=True, blank=True, verbose_name='到期时间')
    info = models.TextField(verbose_name="证书信息", null=True, blank=True,default=dict)
    store_type = models.CharField(verbose_name="存储",max_length=255,null=True,blank=True,choices=STORETYPE_CHOICE,default='local')
    
    class Meta:
        db_table = table_prefix + "cert"
        verbose_name = '证书管理'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "system"

class Databases(BaseModel):

    DB_TYPE_CHOICES = (
        (0, "MySQL"),
        (1, "SqlServer"),
        (2, "MongoDB"),
        (3, "PgSql"),
        (4, "Redis"),
    )
    ACCEPT_CHOICES = (
        ("all", "所有人"),
        ("localhost", "本地服务器"),
        ("ip", "指定IP"),
    )
    
    db_host = models.CharField(max_length=255, verbose_name='服务器地址', null=True, blank=True)
    db_name = models.CharField(max_length=255, verbose_name='数据库名', null=True, blank=True)
    db_port = models.IntegerField(verbose_name='数据库端口', default=0)
    format = models.CharField(max_length=60, verbose_name='数据库编码', null=True, blank=True)
    db_user = models.CharField(max_length=255, verbose_name='用户名', null=True, blank=True)
    db_pass = models.CharField(max_length=255, verbose_name="密码", null=True, blank=True)
    accept = models.CharField(max_length=255,choices=ACCEPT_CHOICES, verbose_name='访问权限', null=True, blank=True)
    accept_ips = models.TextField(verbose_name="允许的多个ip（逗号分割）", null=True, blank=True)
    remark = models.CharField(max_length=255, verbose_name='备注', null=True, blank=True)
    db_type = models.IntegerField(verbose_name='数据库类型', default=0,choices=DB_TYPE_CHOICES)
    is_remote = models.BooleanField(verbose_name='是否远程数据库',default = False)#默认本地数据库

    class Meta:
        db_table = table_prefix + "databases"
        verbose_name = '数据库表'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "system"


class TerminalServer(BaseModel):
    TYPE_CHOICES = (
        (0, "密码验证"),
        (1, "私钥验证"),
    )
    host = models.CharField(max_length=100, verbose_name="服务器IP/域名")
    port = models.IntegerField(verbose_name="端口号", default=22,help_text="端口号")
    remark = models.CharField(max_length=100,verbose_name="备注",null=True,blank=True)
    username = models.CharField(max_length=200, verbose_name="用户名")
    password = models.CharField(max_length=200, verbose_name="密码",null=True,blank=True)
    pkey = models.CharField(max_length=255, verbose_name="私钥",null=True,blank=True)
    pkey_passwd = models.CharField(max_length=255, verbose_name="私钥密码",null=True,blank=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, verbose_name="验证方式", default=0,help_text="验证方式")

    class Meta:
        db_table = table_prefix + "terminal"
        verbose_name = "终端服务器列表"
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "system"

class CommonCommands(BaseModel):
    
    name = models.CharField(max_length=100, verbose_name="命令名称",null=True,blank=True)
    shell = models.TextField(verbose_name="常用命令",null=True,blank=True)

    class Meta:
        db_table = table_prefix + "common_commands"
        verbose_name = "常用命令"
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "system"

class Config(models.Model):

    config = models.TextField(verbose_name="面板配置", null=True, blank=True,default=dict)
    mysql_root = models.CharField(max_length=100, verbose_name="mysql的root密码",null=True,blank=True)

    
    class Meta:
        db_table = table_prefix + "config"
        verbose_name = '配置'
        verbose_name_plural = verbose_name
        ordering = ('-id',)
        app_label = "system"