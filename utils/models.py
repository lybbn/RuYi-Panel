# -*- coding: utf-8 -*-

"""
@Remark: 公共基础model类
"""
import uuid

from django.apps import apps

from django.db import models

from ruyi import settings

table_prefix = "ruyi_"  # 数据库表名前缀


def make_uuid():
    # .hex 将生成的uuid字符串中的 － 删除，带-是36位字符，不带-是32位随机字符串
    return str(uuid.uuid4().hex)

class BaseModel(models.Model):
    """
    基本模型,可直接继承使用，一般不需要使用审计字段的模型可以使用
    覆盖字段时, 字段名称请勿修改
    """
    update_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name='更新时间')
    create_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name='创建时间')

    class Meta:
        abstract = True  # 表示该类是一个抽象类，只用来继承，不参与迁移操作
        verbose_name = '基本模型'
        verbose_name_plural = verbose_name