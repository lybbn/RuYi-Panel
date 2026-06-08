from django.db import models
from utils.models import table_prefix,BaseModel
from apps.systask.models import CrontabTask
from django_apscheduler.models import DjangoJob


class RuyiBackup(models.Model):
    
    TYPE_CHOICES = (
        (1, "数据库备份"),
        (2, "网站备份"),
        (3, "目录备份"),
        (4, "应用备份"),#dkapps
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


class PanelBackup(BaseModel):
    BACKUP_STATUS_CHOICES = (
        (0, "等待中"),
        (1, "备份中"),
        (2, "已完成"),
        (3, "失败"),
    )
    RESTORE_STATUS_CHOICES = (
        (0, "未还原"),
        (1, "还原中"),
        (2, "还原完成"),
        (3, "还原失败"),
    )
    STORE_TYPE_CHOICES = (
        ("local", "本地"),
        ("cloud", "云存储"),
    )
    name = models.CharField(max_length=255, verbose_name='备份名称')
    backup_data = models.TextField(verbose_name="备份数据配置JSON", default='[]')
    store_type = models.CharField(max_length=32, choices=STORE_TYPE_CHOICES, default='local', verbose_name='存储位置')
    cloud_account_id = models.IntegerField(null=True, blank=True, verbose_name='云存储账号ID')
    file_path = models.TextField(verbose_name="备份文件路径", null=True, blank=True)
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    file_sha256 = models.CharField(max_length=64, verbose_name='文件SHA256', null=True, blank=True)
    backup_status = models.SmallIntegerField(choices=BACKUP_STATUS_CHOICES, default=0, verbose_name='备份状态')
    estimated_size = models.BigIntegerField(default=0, verbose_name='预计大小(字节)')
    backup_config = models.TextField(verbose_name="备份详细配置JSON", null=True, blank=True, default='{}')
    error_msg = models.TextField(verbose_name="错误信息", null=True, blank=True, default='')
    done_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    total_time = models.IntegerField(default=0, verbose_name='耗时(秒)')
    # 新增字段
    backup_log = models.TextField(verbose_name="备份日志", null=True, blank=True, default='')
    restore_status = models.SmallIntegerField(choices=RESTORE_STATUS_CHOICES, default=0, verbose_name='还原状态')
    restore_log = models.TextField(verbose_name="还原日志", null=True, blank=True, default='')
    restore_done_time = models.DateTimeField(null=True, blank=True, verbose_name='还原完成时间')
    restore_total_time = models.IntegerField(default=0, verbose_name='还原耗时(秒)')
    backup_count_success = models.IntegerField(default=0, verbose_name='备份成功项数')
    backup_count_failed = models.IntegerField(default=0, verbose_name='备份失败项数')
    is_encrypted = models.BooleanField(default=False, verbose_name='是否加密')
    is_scheduled = models.BooleanField(default=False, verbose_name='是否定时备份')
    cron_id = models.IntegerField(null=True, blank=True, verbose_name='关联计划任务ID')
    exclude_dirs = models.TextField(verbose_name="排除目录", null=True, blank=True, default='[]')
    pre_restore_backup_id = models.IntegerField(null=True, blank=True, verbose_name='还原前备份ID')

    class Meta:
        db_table = table_prefix + "panel_backup"
        verbose_name = '面板备份还原'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysbak"


class BackupItemDetail(BaseModel):
    STATUS_CHOICES = (
        (0, '等待'),
        (1, '进行中'),
        (2, '成功'),
        (3, '失败'),
    )
    backup = models.ForeignKey(PanelBackup, on_delete=models.CASCADE, related_name='items', verbose_name='关联备份')
    module = models.CharField(max_length=50, verbose_name='模块名称')
    item_id = models.CharField(max_length=100, verbose_name='数据项ID')
    item_name = models.CharField(max_length=255, verbose_name='数据项名称')
    item_type = models.CharField(max_length=50, null=True, blank=True, verbose_name='数据项类型')
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0, verbose_name='状态')
    file_path = models.TextField(verbose_name="备份文件路径", null=True, blank=True)
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小')
    error_msg = models.TextField(verbose_name="错误信息", null=True, blank=True, default='')
    extra_data = models.TextField(verbose_name="额外数据JSON", null=True, blank=True, default='{}')

    class Meta:
        db_table = table_prefix + "backup_item_detail"
        verbose_name = '备份项详情'
        verbose_name_plural = verbose_name
        ordering = ('module', 'id')
        app_label = "sysbak"


class BackupSchedule(BaseModel):
    SCHEDULE_TYPE_CHOICES = (
        ('daily', '每天'),
        ('weekly', '每周'),
        ('monthly', '每月'),
    )
    name = models.CharField(max_length=255, verbose_name='计划名称')
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES, verbose_name='计划类型')
    schedule_config = models.TextField(verbose_name="计划配置JSON", default='{}')
    backup_config = models.TextField(verbose_name="备份配置JSON", default='{}')
    store_type = models.CharField(max_length=32, default='local', verbose_name='存储位置')
    cloud_account_id = models.IntegerField(null=True, blank=True, verbose_name='云存储账号ID')
    keep_count = models.IntegerField(default=3, verbose_name='保留份数')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    last_run_time = models.DateTimeField(null=True, blank=True, verbose_name='上次执行时间')
    cron_task = models.ForeignKey(
        CrontabTask, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='关联计划任务',
        db_constraint=False,
    )

    class Meta:
        db_table = table_prefix + "backup_schedule"
        verbose_name = '备份计划'
        verbose_name_plural = verbose_name
        app_label = "sysbak"
