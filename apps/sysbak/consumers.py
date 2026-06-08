import json
from channels.generic.websocket import AsyncWebsocketConsumer


class BackupProgressConsumer(AsyncWebsocketConsumer):
    """备份还原进度推送 WebSocket"""

    async def connect(self):
        self.group_name = 'backup_progress'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def backup_progress(self, event):
        """接收进度消息并推送到前端"""
        await self.send(text_data=json.dumps({
            'type': 'progress',
            'module': event.get('module', ''),
            'item_id': event.get('item_id', ''),
            'item_name': event.get('item_name', ''),
            'status': event.get('status', ''),
            'msg': event.get('msg', ''),
            'total_progress': event.get('total_progress', 0),
        }))
