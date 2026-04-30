#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Copyright (c) 如意面板 All rights reserved.
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------

"""
告警系统初始数据配置
"""

# 告警通知渠道默认配置
ALERT_NOTIFY_CONFIGS = [
    {
        "id": 1,
        "name": "邮件通知",
        "channel_type": "email",
        "is_enabled": False,
        "daily_limit": 3,
        "send_start_time": "00:00",
        "send_end_time": "23:59",
        "icon_type": "icon",
        "icon": "Message",
        "icon_color": "#409eff",
        "config": {
            "smtpServer": "",
            "smtpPort": 465,
            "sender": "",
            "password": "",
            "receivers": []
        }
    },
    {
        "id": 2,
        "name": "钉钉机器人",
        "channel_type": "dingtalk",
        "is_enabled": False,
        "daily_limit": 3,
        "send_start_time": "00:00",
        "send_end_time": "23:59",
        "icon_type": "image",
        "icon": "dingding.png",
        "icon_color": "#0089ff",
        "config": {
            "webhook": "",
            "secret": "",
            "msgType": "text"
        }
    },
    {
        "id": 3,
        "name": "飞书机器人",
        "channel_type": "feishu",
        "is_enabled": False,
        "daily_limit": 3,
        "send_start_time": "00:00",
        "send_end_time": "23:59",
        "icon_type": "image",
        "icon": "feishu.png",
        "icon_color": "#3370ff",
        "config": {
            "webhook": "",
            "secret": "",
            "msgType": "text"
        }
    },
    {
        "id": 4,
        "name": "企业微信",
        "channel_type": "wechat",
        "is_enabled": False,
        "daily_limit": 3,
        "send_start_time": "00:00",
        "send_end_time": "23:59",
        "icon_type": "image",
        "icon": "qiyeweixin.png",
        "icon_color": "#00c853",
        "config": {
            "corpId": "",
            "agentId": "",
            "secret": "",
            "toUser": ""
        }
    },
    {
        "id": 5,
        "name": "短信通知",
        "channel_type": "sms",
        "is_enabled": False,
        "daily_limit": 3,
        "send_start_time": "00:00",
        "send_end_time": "23:59",
        "icon_type": "icon",
        "icon": "Iphone",
        "icon_color": "#ff9800",
        "config": {
            "provider": "aliyun",
            "accessKey": "",
            "accessSecret": "",
            "signName": "",
            "templateCode": "",
            "phones": []
        }
    },
    {
        "id": 6,
        "name": "Webhook",
        "channel_type": "webhook",
        "is_enabled": False,
        "daily_limit": 3,
        "send_start_time": "00:00",
        "send_end_time": "23:59",
        "icon_type": "icon",
        "icon": "Link",
        "icon_color": "#9c27b0",
        "config": {
            "url": "",
            "method": "POST",
            "headers": "",
            "bodyTemplate": ""
        }
    },
]


def init_alert_notify_config(force=False):
    """
    初始化告警通知渠道配置
    
    Args:
        force: 是否强制重新初始化（删除已有数据）
    
    Returns:
        tuple: (created_count, skipped_count)
    """
    from apps.sysalert.models import AlertNotifyConfig
    
    if force:
        AlertNotifyConfig.objects.filter(
            id__in=[cfg.get('id') for cfg in ALERT_NOTIFY_CONFIGS]
        ).delete()
    
    created_count = 0
    skipped_count = 0
    
    for config_data in ALERT_NOTIFY_CONFIGS:
        config_id = config_data.get("id")
        config_dict = config_data.get('config', {})
        
        # 准备 defaults 数据（排除 config 字段）
        defaults = {k: v for k, v in config_data.items() if k != 'config'}
        
        # 使用 get_or_create，存在则跳过，不存在则创建
        obj, created = AlertNotifyConfig.objects.get_or_create(
            id=config_id,
            defaults=defaults
        )
        
        if created or force:
            obj.set_config(config_dict)
            obj.save()
            created_count += 1
        else:
            skipped_count += 1
    
    return created_count, skipped_count
