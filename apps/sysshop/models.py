import json
from django.db import models
from utils.models import table_prefix,BaseModel

class RySoftShop(BaseModel):

    STATUS_CHOICES = (
        (0, "未安装"),
        (1, "已启动"),
        (2, "已停止"),
    )
    TYPE_CHOICES = (
        (0, "未分类"),
        (2, "数据库"),
        (3, "Web服务器"),
        (4, "运行环境"),
        (5, "安全防护"),
    )
    name = models.CharField(max_length=100, verbose_name='软件名')
    install_path = models.CharField(max_length=255, verbose_name='安装路径',null=True,blank=True)
    install_version = models.CharField(max_length=100, verbose_name='安装版本',null=True,blank=True)
    installed = models.BooleanField(verbose_name="是否安装", default=False)
    status = models.SmallIntegerField(choices=STATUS_CHOICES, verbose_name="状态", default=0)
    password = models.CharField(max_length=255, verbose_name='软件密码',null=True,blank=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES, verbose_name="分类", default=0)
    info = models.TextField(blank=True, null=True)  # 软件信息（JSON格式）
    is_default = models.BooleanField(verbose_name="是否默认", default=True)#go环境多个版本，确认哪个是默认环境（默认新安装的为默认，其他如果存在默认情况则直接改非默认）
    
    def get_info(self):
        """获取软件信息"""
        json_info = {}
        if self.info:
            json_info = json.loads(self.info)
        return json_info
    
    class Meta:
        db_table = table_prefix + "shop"
        verbose_name = '软件列表'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysshop"