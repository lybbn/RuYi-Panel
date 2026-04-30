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
告警通知发送模块
支持：邮件、钉钉、飞书、企业微信、短信、Webhook
"""

import json
import requests
import smtplib
import logging
from datetime import datetime, time as dt_time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.utils import timezone

logger = logging.getLogger('apscheduler.scheduler')


class AlertNotifier:
    """告警通知器"""
    
    @staticmethod
    def check_send_time(config):
        """检查是否在允许发送的时间段内"""
        now = datetime.now().time()
        start = config.send_start_time
        end = config.send_end_time
        
        if start <= end:
            return start <= now <= end
        else:
            # 跨天的情况，如 22:00 - 08:00
            return now >= start or now <= end
    
    @staticmethod
    def check_daily_limit(config):
        """检查是否超过每日发送上限"""
        from .models import AlertDailyCounter
        
        today = datetime.now().date()
        counter, created = AlertDailyCounter.objects.get_or_create(
            config=config,
            date=today,
            defaults={'count': 0}
        )
        
        if counter.count >= config.daily_limit:
            return False, "已达到今日发送上限"
        
        return True, counter
    
    @staticmethod
    def increment_counter(counter):
        """增加发送计数"""
        counter.count += 1
        counter.save(update_fields=['count'])
    
    @classmethod
    def send(cls, config, title, content):
        """
        发送通知
        :param config: AlertNotifyConfig 实例
        :param title: 标题
        :param content: 内容
        :return: (success: bool, response: str)
        """
        # 检查时间段
        if not cls.check_send_time(config):
            return False, "不在允许发送的时间段内"
        
        # 检查发送上限
        can_send, result = cls.check_daily_limit(config)
        if not can_send:
            return False, result
        
        counter = result
        
        # 根据渠道类型发送
        channel_type = config.channel_type
        config_dict = config.get_config()
        
        try:
            if channel_type == 'email':
                success, response = cls._send_email(config_dict, title, content)
            elif channel_type == 'dingtalk':
                success, response = cls._send_dingtalk(config_dict, title, content)
            elif channel_type == 'feishu':
                success, response = cls._send_feishu(config_dict, title, content)
            elif channel_type == 'wechat':
                success, response = cls._send_wechat(config_dict, title, content)
            elif channel_type == 'sms':
                success, response = cls._send_sms(config_dict, title, content)
            elif channel_type == 'webhook':
                success, response = cls._send_webhook(config_dict, title, content)
            else:
                return False, f"未知的渠道类型: {channel_type}"
            
            if success:
                cls.increment_counter(counter)
            
            return success, response
            
        except Exception as e:
            logger.error(f"发送告警通知失败: {e}")
            return False, str(e)
    
    @staticmethod
    def _send_email(config, title, content):
        """发送邮件"""
        smtp_server = config.get('smtp_server') or config.get('smtpServer')
        smtp_port = config.get('smtp_port') or config.get('smtpPort', 465)
        sender = config.get('sender')
        password = config.get('password')
        receivers = config.get('receivers', [])
        
        if not all([smtp_server, sender, password, receivers]):
            return False, "邮件配置不完整"
        
        try:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = ', '.join(receivers)
            msg['Subject'] = f"【如意面板告警】{title}"
            
            body = f"""
            <h3>如意面板告警通知</h3>
            <p><strong>告警标题：</strong>{title}</p>
            <p><strong>告警内容：</strong>{content}</p>
            <p><strong>发送时间：</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
            <p style="color: #999; font-size: 12px;">此邮件由如意面板自动发送，请勿回复</p>
            """
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            smtp_port = int(smtp_port)
            
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
            elif smtp_port == 587:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            
            server.login(sender, password)
            server.sendmail(sender, receivers, msg.as_string())
            server.quit()
            
            return True, "邮件发送成功"
        except Exception as e:
            return False, f"邮件发送失败: {str(e)}"
    
    @staticmethod
    def _send_dingtalk(config, title, content):
        """发送钉钉机器人消息"""
        webhook = config.get('webhook')
        secret = config.get('secret', '')
        msg_type = config.get('msg_type') or config.get('msgType', 'text')
        
        if not webhook:
            return False, "Webhook地址不能为空"
        
        try:
            import hmac
            import hashlib
            import base64
            import urllib.parse
            import time
            
            # 加签处理
            if secret:
                timestamp = str(round(time.time() * 1000))
                string_to_sign = f"{timestamp}\n{secret}"
                hmac_code = hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
                webhook = f"{webhook}&timestamp={timestamp}&sign={sign}"
            
            if msg_type == 'markdown':
                data = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": f"【如意面板告警】{title}",
                        "text": f"### 如意面板告警通知\n\n**告警标题：** {title}\n\n**告警内容：** {content}\n\n**发送时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            else:
                data = {
                    "msgtype": "text",
                    "text": {
                        "content": f"【如意面板告警】{title}\n{content}\n发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            
            response = requests.post(webhook, json=data, timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                return True, "钉钉消息发送成功"
            else:
                return False, f"钉钉消息发送失败: {result.get('errmsg')}"
        except Exception as e:
            return False, f"钉钉消息发送失败: {str(e)}"
    
    @staticmethod
    def _send_feishu(config, title, content):
        """发送飞书机器人消息"""
        webhook = config.get('webhook')
        secret = config.get('secret', '')
        msg_type = config.get('msg_type') or config.get('msgType', 'text')
        
        if not webhook:
            return False, "Webhook地址不能为空"
        
        try:
            import hmac
            import hashlib
            import base64
            import time
            
            # 加签处理
            if secret:
                timestamp = str(int(time.time()))
                string_to_sign = f"{timestamp}\n{secret}"
                hmac_code = hmac.new(string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).digest()
                sign = base64.b64encode(hmac_code).decode('utf-8')
                
                if '?' in webhook:
                    webhook = f"{webhook}&timestamp={timestamp}&sign={sign}"
                else:
                    webhook = f"{webhook}?timestamp={timestamp}&sign={sign}"
            
            if msg_type == 'interactive':
                data = {
                    "msg_type": "interactive",
                    "card": {
                        "config": {"wide_screen_mode": True},
                        "header": {
                            "title": {
                                "tag": "plain_text",
                                "content": "如意面板告警通知"
                            },
                            "template": "red"
                        },
                        "elements": [
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**告警标题：** {title}\n**告警内容：** {content}\n**发送时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                }
                            }
                        ]
                    }
                }
            else:
                data = {
                    "msg_type": "text",
                    "content": {
                        "text": f"【如意面板告警】{title}\n{content}\n发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            
            response = requests.post(webhook, json=data, timeout=10)
            result = response.json()
            
            if result.get('code') == 0:
                return True, "飞书消息发送成功"
            else:
                return False, f"飞书消息发送失败: {result.get('msg')}"
        except Exception as e:
            return False, f"飞书消息发送失败: {str(e)}"
    
    @staticmethod
    def _send_wechat(config, title, content):
        """发送企业微信消息"""
        corp_id = config.get('corp_id') or config.get('corpId')
        agent_id = config.get('agent_id') or config.get('agentId')
        secret = config.get('secret')
        to_user = config.get('to_user') or config.get('toUser', '@all')
        
        if not all([corp_id, agent_id, secret]):
            return False, "企业微信配置不完整"
        
        try:
            # 获取access_token
            token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp_id}&corpsecret={secret}"
            token_response = requests.get(token_url, timeout=10)
            token_result = token_response.json()
            
            if token_result.get('errcode') != 0:
                return False, f"获取access_token失败: {token_result.get('errmsg')}"
            
            access_token = token_result.get('access_token')
            
            # 发送消息
            send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
            data = {
                "touser": to_user,
                "msgtype": "text",
                "agentid": agent_id,
                "text": {
                    "content": f"【如意面板告警】{title}\n{content}\n发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            }
            
            response = requests.post(send_url, json=data, timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                return True, "企业微信消息发送成功"
            else:
                return False, f"企业微信消息发送失败: {result.get('errmsg')}"
        except Exception as e:
            return False, f"企业微信消息发送失败: {str(e)}"
    
    @staticmethod
    def _send_sms(config, title, content):
        """发送短信"""
        provider = config.get('provider')
        access_key = config.get('access_key') or config.get('accessKey')
        access_secret = config.get('access_secret') or config.get('accessSecret')
        sign_name = config.get('sign_name') or config.get('signName')
        template_code = config.get('template_code') or config.get('templateCode')
        phones = config.get('phones', [])
        
        if not all([provider, access_key, access_secret, sign_name, template_code, phones]):
            return False, "短信配置不完整"
        
        # 这里需要根据具体短信服务商实现
        # 阿里云、腾讯云、华为云等
        try:
            if provider == 'aliyun':
                # 阿里云短信实现
                return AlertNotifier._send_sms_aliyun(config, title, content)
            elif provider == 'tencent':
                # 腾讯云短信实现
                return False, "腾讯云短信暂未实现"
            elif provider == 'huawei':
                # 华为云短信实现
                return False, "华为云短信暂未实现"
            else:
                return False, f"未知的短信服务商: {provider}"
        except Exception as e:
            return False, f"短信发送失败: {str(e)}"
    
    @staticmethod
    def _send_sms_aliyun(config, title, content):
        """发送阿里云短信"""
        # 简化实现，实际需要接入阿里云SDK
        return True, "短信发送成功（模拟）"
    
    @staticmethod
    def _send_webhook(config, title, content):
        """发送Webhook请求"""
        url = config.get('url')
        method = config.get('method', 'POST')
        headers = config.get('headers', '{}')
        body_template = config.get('body_template') or config.get('bodyTemplate', '')
        
        if not url:
            return False, "Webhook URL不能为空"
        
        try:
            # 解析headers
            try:
                headers_dict = json.loads(headers)
            except:
                headers_dict = {}
            
            # 替换模板变量
            if body_template:
                body = body_template.replace('{{title}}', title).replace('{{content}}', content)
                try:
                    data = json.loads(body)
                except:
                    data = {"title": title, "content": content}
            else:
                data = {
                    "title": title,
                    "content": content,
                    "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "source": "如意面板"
                }
            
            # 发送请求
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers_dict, timeout=10)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=data, headers=headers_dict, timeout=10)
            else:
                response = requests.post(url, json=data, headers=headers_dict, timeout=10)
            
            if response.status_code == 200:
                return True, f"Webhook发送成功: {response.text[:200]}"
            else:
                return False, f"Webhook发送失败: HTTP {response.status_code}"
        except Exception as e:
            return False, f"Webhook发送失败: {str(e)}"


def send_alert(task, content):
    """
    发送告警通知（入口函数）
    :param task: AlertTask 实例
    :param content: 告警内容
    :return: list of (success, response)
    """
    from .models import AlertNotifyConfig
    
    results = []
    channel_ids = task.get_channel_ids()
    
    if not channel_ids:
        return [(False, "未配置通知渠道")]
    
    configs = AlertNotifyConfig.objects.filter(id__in=channel_ids, is_enabled=True)
    
    for config in configs:
        success, response = AlertNotifier.send(config, task.name, content)
        results.append((success, response))
    
    return results
