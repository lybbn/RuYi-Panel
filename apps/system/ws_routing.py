# -*- coding: utf-8 -*-

"""
@Remark: websocket的路由文件
"""
from django.urls import re_path,path

from apps.system.views import rdp_tunnel
from apps.system.views import ssh_terminal
from apps.system.views import wstask
from apps.sysnode.consumers import FileTransferConsumer, LoadBalanceConsumer
from apps.sysbak.consumers import BackupProgressConsumer
from apps.syscloud.consumers import CloudUploadConsumer

websocket_urlpatterns = [
    path('api/webssh/', ssh_terminal.WebSSHConsumerAsync.as_asgi()),
    path('api/webrdp/', rdp_tunnel.WebRDPConsumerAsync.as_asgi()),
    path('api/wstask/', wstask.WSTaskConsumer.as_asgi()),
    path('api/wsfiletransfer/', FileTransferConsumer.as_asgi()),
    path('api/wsloadbalance/', LoadBalanceConsumer.as_asgi()),
    path('api/wsbackup/', BackupProgressConsumer.as_asgi()),
    path('api/wscloudupload/', CloudUploadConsumer.as_asgi()),
]
