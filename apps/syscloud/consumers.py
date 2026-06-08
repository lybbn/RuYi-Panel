# -*- coding: utf-8 -*-

"""
@Remark: 云存储模块WebSocket Consumer - 上传进度推送
@author lybbn<2026-06-05>
"""
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from utils.common import getTimestamp13


class CloudUploadConsumer(AsyncWebsocketConsumer):
    """云存储上传进度WebSocket - 实时进度推送"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.missed_heartbeats = 0
        self.heartbeat_limit = 3
        self.heartbeat_timeout = 30

    async def connect(self):
        self.room_group_name = "cloud_upload"
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()
        self.heartbeat_task = asyncio.create_task(self.heartbeat_checker())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )
        if hasattr(self, 'heartbeat_task') and self.heartbeat_task:
            self.heartbeat_task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            content = json.loads(text_data)
            action = content.get('action', '')
            if action == 'heartBeat':
                self.missed_heartbeats = 0
                await self.send(text_data=json.dumps({
                    'action': 'heartBeat',
                    'data': {'timestamp': getTimestamp13()}
                }))
        except Exception as e:
            await self.send(text_data=json.dumps({'action': 'error', 'data': str(e)}))

    async def heartbeat_checker(self):
        while True:
            await asyncio.sleep(self.heartbeat_timeout)
            if self.missed_heartbeats >= self.heartbeat_limit:
                await self.close()
                break
            self.missed_heartbeats += 1

    async def upload_progress(self, event):
        """接收Channel Layer推送的上传进度并转发给客户端"""
        await self.send(text_data=json.dumps({
            'action': 'upload_progress',
            'data': event.get('data', {})
        }))
