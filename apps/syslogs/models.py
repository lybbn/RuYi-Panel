from django.db import models
from utils.models import table_prefix,BaseModel

class OperationLog(models.Model):
    
    MODULE_CHOICES = (
        ("dbmg", "数据库管理"),
        ("login", "用户登录"),
        ("safe", "安全"),
        ("softmg", "软件管理"),
        ("filemg", "文件管理"),
        ("sitemg", "网站管理"),
        ("dellog", "清空日志"),
        ("panelst", "面板设置"),
        ("taskmg", "计划任务"),
    )

    username = models.CharField(max_length=255, verbose_name="用户名", null=True, blank=True)
    module = models.CharField(max_length=255,choices=MODULE_CHOICES, verbose_name="请求模块", null=True, blank=True)
    path = models.CharField(max_length=255, verbose_name="请求地址", null=True, blank=True)
    body = models.TextField(verbose_name="请求参数", null=True, blank=True)
    ip = models.CharField(max_length=32, verbose_name="请求ip地址", null=True, blank=True)
    ip_area = models.CharField(max_length=100, verbose_name="IP归属地", null=True, blank=True, help_text="IP归属地")
    browser = models.CharField(max_length=64, verbose_name="请求浏览器", null=True, blank=True)
    status = models.BooleanField(default=True,verbose_name="状态")
    request_os = models.CharField(max_length=64, verbose_name="操作系统", null=True, blank=True)
    msg = models.TextField(verbose_name="自定义内容", null=True, blank=True)
    create_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name='创建时间')

    class Meta:
        db_table = table_prefix + "operation_log"
        verbose_name = "操作日志"
        verbose_name_plural = verbose_name
        ordering = ("-create_at",)
        app_label = "syslogs"