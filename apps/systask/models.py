import json
import os,datetime
import importlib
from django.db import models
from utils.models import table_prefix,BaseModel
from django_apscheduler.models import DjangoJob

class CrontabTask(BaseModel):
    TYPE_CHOICES = (
        (0, "shell"),
        (1, "bk_database"),
        (2, "bk_website"),
        (3, "bk_dir"),
        (4, "access_url"),
        
    )
    PERIOD_TYPE_CHOICES = (
        (0, ""),
        (1, "每天"),
        (2, "每周"),
        (3, "每月"),
        (4, "每小时"),
        (5, "每隔N天"),
        (6, "每隔N时"),
        (7, "每隔N分"),
        (8, "每隔N秒"),
    )
    TARGETBK_TYPE_CHOICES = (
        (0, ""),
        (1, "local"),
    )

    DB_TYPE_CHOICES = (
        (0, "mysql"),
    )

    job = models.OneToOneField(DjangoJob,db_constraint=False,on_delete=models.DO_NOTHING,verbose_name="关联DjangoJob",null=True,blank=True)
    name = models.CharField(max_length=255,verbose_name="任务名称")
    is_sys = models.BooleanField(default=False,verbose_name="是否系统任务")
    status = models.BooleanField(default=True,verbose_name="任务状态")
    period_type = models.SmallIntegerField(choices=PERIOD_TYPE_CHOICES, verbose_name="周期类型", default=0)
    year = models.IntegerField(default=0,verbose_name="年")
    month = models.IntegerField(default=0,verbose_name="月")
    week = models.IntegerField(default=0,verbose_name="周")
    day = models.IntegerField(default=0,verbose_name="天")
    hour = models.IntegerField(default=0,verbose_name="小时")
    minute = models.IntegerField(default=0,verbose_name="分钟")
    second = models.IntegerField(default=0,verbose_name="秒")
    shell_body = models.TextField(verbose_name="执行shell内容",null=True,blank=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, verbose_name="类型", default=0)
    database = models.TextField(verbose_name="备份数据库",null=True,blank=True)#ALL表示所有、单个数据库为要备份数据库的id、多个用英文逗号分割
    website = models.TextField(verbose_name="备份网站",null=True,blank=True)#ALL表示所有、单个网站为要备份网站的id、多个用英文逗号分割
    dir = models.TextField(verbose_name="备份目录",null=True,blank=True)#要备份目录的绝对路径
    exclude_rules = models.TextField(verbose_name="备份目录排除规则",null=True,blank=True)#在此规则内的目录或文件忽略不备份，一行一个
    url = models.TextField(verbose_name="url内容",null=True,blank=True)#url内容
    db_type = models.SmallIntegerField(choices=DB_TYPE_CHOICES, verbose_name="备份数据库类型", default=0)
    backup_to = models.SmallIntegerField(choices=TARGETBK_TYPE_CHOICES, verbose_name="备份到目标", default=0)
    saveNums = models.IntegerField(default=0,verbose_name="保留份数")

    class Meta:
        db_table = table_prefix + "crontab_task"
        verbose_name = '定时任务表'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "systask"
        
class SysTaskCenter(BaseModel):
    TYPE_CHOICES = (
        (0, "安装软件"),
        (1, "其他"),
    )
    TASK_STATUS_CHOICES = (
        (0, "待处理"),
        (1, "进行中"),
        (2, "已失败"),
        (3, "已完成"),
    )
    job = models.ForeignKey(DjangoJob,db_constraint=False,on_delete=models.DO_NOTHING,verbose_name="关联DjangoJob",null=True,blank=True)
    name = models.CharField(max_length=100,verbose_name="任务名称",null=True,blank=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, verbose_name="类型", default=0)
    log = models.TextField(verbose_name="日志名称（filename）",null=True,blank=True)
    status = models.SmallIntegerField(choices=TASK_STATUS_CHOICES, verbose_name="任务状态", default=0)
    duration = models.IntegerField(verbose_name="耗时(秒)",default=0)
    func_path = models.TextField(blank=True, null=True) # 默认为存储函数的路径 'path.to.module.function'  
    params = models.TextField(blank=True, null=True)  # 任务参数（JSON格式）
    exec_at = models.DateTimeField(null=True, blank=True, verbose_name='执行时间')
    
    def get_params(self,isList = False):
        """获取任务参数"""
        json_params = {}
        if self.params:
            json_params = json.loads(self.params)
            if not isList:
                return json_params
            return [value for key, value in json_params.items()]
        if isList:
            json_params = []
        return json_params
    
    def execute_task(self):
        """执行任务"""
        module_path, function_name = self.func_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        params = self.get_params(isList=True)
        job_id, file_extension = os.path.splitext(os.path.basename(self.log))
        nowtime = datetime.datetime.now()
        try:
            from apps.systask.tasks import installTask
            django_job = installTask(job_id,function,func_args=params)
            self.status = 1
            self.exec_at = nowtime
        except Exception as e:
            django_job = None
            self.status = 2
        new_job_id = django_job.id if django_job else None
        self.job_id = new_job_id
        self.save()

    class Meta:
        db_table = table_prefix + "systask_center"
        verbose_name = '系统任务中心'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "systask"