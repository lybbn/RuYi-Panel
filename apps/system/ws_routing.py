# -*- coding: utf-8 -*-

"""
@Remark: websocket的路由文件
"""
from django.urls import re_path,path

from apps.system.views import ssh_terminal
from apps.system.views import wstask

websocket_urlpatterns = [
    path('api/webssh/', ssh_terminal.WebSSHConsumerAsync.as_asgi()),
    path('api/wstask/', wstask.WSTaskConsumer.as_asgi()),
]