# -*- coding: utf-8 -*-

"""
@Remark: 节点模块WebSocket Consumer - 文件传输进度推送 + 负载均衡配置反馈
@author lybbn<2026-06-03>
"""
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from utils.common import getTimestamp13


class FileTransferConsumer(AsyncWebsocketConsumer):
    """文件互传WebSocket - 实时进度推送"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.missed_heartbeats = 0
        self.heartbeat_limit = 3
        self.heartbeat_timeout = 30

    async def connect(self):
        self.room_group_name = "file_transfer"
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
            elif action == 'subscribe':
                task_id = content.get('data', {}).get('task_id')
                if task_id:
                    group_name = f"file_transfer_{task_id}"
                    await self.channel_layer.group_add(group_name, self.channel_name)
        except Exception as e:
            await self.send(text_data=json.dumps({'action': 'error', 'data': str(e)}))

    async def heartbeat_checker(self):
        while True:
            await asyncio.sleep(self.heartbeat_timeout)
            if self.missed_heartbeats >= self.heartbeat_limit:
                await self.close()
                break
            self.missed_heartbeats += 1

    async def transfer_progress(self, event):
        """接收Channel Layer推送的传输进度并转发给客户端"""
        await self.send(text_data=json.dumps({
            'action': 'transfer_progress',
            'data': event.get('data', {})
        }))


class LoadBalanceConsumer(AsyncWebsocketConsumer):
    """负载均衡WebSocket - 配置检查和生成进度反馈"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.missed_heartbeats = 0
        self.heartbeat_limit = 3
        self.heartbeat_timeout = 30

    async def connect(self):
        self.room_group_name = "loadbalance"
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

    async def config_progress(self, event):
        """接收Channel Layer推送的配置进度并转发给客户端"""
        await self.send(text_data=json.dumps({
            'action': 'config_progress',
            'data': event.get('data', {})
        }))
