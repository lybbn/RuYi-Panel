# -*- coding: utf-8 -*-

"""
@Remark: 自定义序列化器
"""
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.request import Request
from rest_framework.serializers import ModelSerializer

class CustomModelSerializer(ModelSerializer):
    """
    增强DRF的ModelSerializer
    (1)self.request能获取到rest_framework.request.Request对象
    """
    # 添加默认时间返回格式
    create_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False, read_only=True)
    update_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)

    def __init__(self, instance=None, data=empty, request=None, **kwargs):
        super().__init__(instance, data, **kwargs)
        self.request: Request = request or self.context.get('request', None)