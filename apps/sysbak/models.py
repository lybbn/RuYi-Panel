from django.db import models
from utils.models import table_prefix,BaseModel
from apps.systask.models import CrontabTask
from django_apscheduler.models import DjangoJob

class RuyiBackup(models.Model):
    
    TYPE_CHOICES = (
        (1, "数据库备份"),
        (2, "网站备份"),
        (3, "目录备份"),
    )
    STORETYPE_CHOICE = (
        ("local", "本地"),
        ("remote", "远程"),
    )
    cron = models.ForeignKey(CrontabTask,db_constraint=False,on_delete=models.DO_NOTHING,verbose_name="关联计划任务",null=True,blank=True,default=0)
    job = models.ForeignKey(DjangoJob,db_constraint=False,on_delete=models.DO_NOTHING,verbose_name="关联job",null=True,blank=True,default=0)
    name = models.CharField(verbose_name="文件名称",max_length=255,null=True,blank=True)
    filename = models.TextField(verbose_name="绝对路径名称",null=True,blank=True)
    size = models.IntegerField(default=0,verbose_name="文件大小")
    remark = models.TextField(verbose_name="备注",null=True,blank=True)
    fid = models.CharField(verbose_name="关联id",max_length=255,null=True,blank=True)#根据type类型记录关联id
    type = models.CharField(verbose_name="类型",max_length=255,null=True,blank=True,choices=TYPE_CHOICES)
    store_type = models.CharField(verbose_name="存储",max_length=255,null=True,blank=True,choices=STORETYPE_CHOICE,default='local')
    create_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name='创建时间')

    class Meta:
        db_table = table_prefix + "backup"
        verbose_name = "备份列表"
        verbose_name_plural = verbose_name
        ordering = ("-create_at",)
        app_label = "sysbak"