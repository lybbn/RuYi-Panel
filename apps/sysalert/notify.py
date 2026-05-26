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
import time
import re
from datetime import datetime, time as dt_time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.utils import timezone

logger = logging.getLogger('apscheduler.scheduler')

_wechat_token_cache = {}


def _camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def _normalize_config(config_dict):
    normalized = {}
    for key, value in config_dict.items():
        snake_key = _camel_to_snake(key)
        normalized[snake_key] = value
    return normalized


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
        config_dict = _normalize_config(config.get_config())
        
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
        smtp_server = config.get('smtp_server')
        smtp_port = config.get('smtp_port', 465)
        sender = config.get('sender')
        password = config.get('password')
        receivers = config.get('receivers', [])
        
        if isinstance(receivers, str):
            receivers = [r.strip() for r in receivers.split(',') if r.strip()]
        
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
        msg_type = config.get('msg_type', 'text')
        
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
        msg_type = config.get('msg_type', 'text')
        
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
        corp_id = config.get('corp_id')
        agent_id = config.get('agent_id')
        secret = config.get('secret')
        to_user = config.get('to_user', '@all')
        msg_type = config.get('msg_type', 'text')
        
        if not all([corp_id, agent_id, secret]):
            return False, "企业微信配置不完整"
        
        try:
            agent_id = int(agent_id)
            
            cache_key = f"{corp_id}_{secret}"
            cached = _wechat_token_cache.get(cache_key)
            if cached and cached.get('expires_at', 0) > time.time():
                access_token = cached['token']
            else:
                token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp_id}&corpsecret={secret}"
                token_response = requests.get(token_url, timeout=10)
                token_result = token_response.json()
                
                if token_result.get('errcode') != 0:
                    return False, f"获取access_token失败: {token_result.get('errmsg')}"
                
                access_token = token_result.get('access_token')
                _wechat_token_cache[cache_key] = {
                    'token': access_token,
                    'expires_at': time.time() + 7000
                }
            
            send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
            
            if msg_type == 'markdown':
                data = {
                    "touser": to_user,
                    "msgtype": "markdown",
                    "agentid": agent_id,
                    "markdown": {
                        "content": f"## 如意面板告警通知\n> **告警标题：** {title}\n> **告警内容：** {content}\n> **发送时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            else:
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
        access_key = config.get('access_key')
        access_secret = config.get('access_secret')
        sign_name = config.get('sign_name')
        template_code = config.get('template_code')
        phones = config.get('phones', [])
        
        if isinstance(phones, str):
            phones = [p.strip() for p in phones.split(',') if p.strip()]
        
        if not all([provider, access_key, access_secret, sign_name, template_code, phones]):
            return False, "短信配置不完整"
        
        try:
            if provider == 'aliyun':
                return AlertNotifier._send_sms_aliyun(config, title, content, phones)
            elif provider == 'tencent':
                return AlertNotifier._send_sms_tencent(config, title, content, phones)
            elif provider == 'huawei':
                return AlertNotifier._send_sms_huawei(config, title, content, phones)
            else:
                return False, f"未知的短信服务商: {provider}"
        except Exception as e:
            return False, f"短信发送失败: {str(e)}"
    
    @staticmethod
    def _send_sms_aliyun(config, title, content, phones):
        """发送阿里云短信"""
        import hmac
        import hashlib
        import base64
        import uuid
        
        access_key_id = config.get('access_key')
        access_key_secret = config.get('access_secret')
        sign_name = config.get('sign_name')
        template_code = config.get('template_code')
        
        api_url = 'https://dysmsapi.aliyuncs.com/'
        
        template_param = json.dumps({
            'title': title,
            'content': content[:80],
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, ensure_ascii=False)
        
        success_count = 0
        fail_count = 0
        errors = []
        
        for phone in phones:
            try:
                params = {
                    'PhoneNumbers': phone,
                    'SignName': sign_name,
                    'TemplateCode': template_code,
                    'TemplateParam': template_param,
                    'Action': 'SendSms',
                    'Version': '2017-05-25',
                    'Format': 'JSON',
                    'AccessKeyId': access_key_id,
                    'SignatureMethod': 'HMAC-SHA1',
                    'SignatureVersion': '1.0',
                    'SignatureNonce': str(uuid.uuid4()),
                    'Timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'RegionId': 'cn-hangzhou',
                }
                
                sorted_params = sorted(params.items())
                query_string = '&'.join([
                    f'{AlertNotifier._aliyun_percent_encode(k)}={AlertNotifier._aliyun_percent_encode(v)}'
                    for k, v in sorted_params
                ])
                
                string_to_sign = 'GET&%2F&' + AlertNotifier._aliyun_percent_encode(query_string)
                
                sign = base64.b64encode(
                    hmac.new(
                        (access_key_secret + '&').encode('utf-8'),
                        string_to_sign.encode('utf-8'),
                        digestmod=hashlib.sha1
                    ).digest()
                ).decode('utf-8')
                
                params['Signature'] = sign
                
                response = requests.get(api_url, params=params, timeout=10)
                result = response.json()
                
                if result.get('Code') == 'OK':
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{phone}: {result.get('Message', '未知错误')}")
            except Exception as e:
                fail_count += 1
                errors.append(f"{phone}: {str(e)}")
        
        if success_count > 0 and fail_count == 0:
            return True, f"阿里云短信发送成功({success_count}条)"
        elif success_count > 0:
            return True, f"阿里云短信部分成功({success_count}条)，失败: {'; '.join(errors)}"
        else:
            return False, f"阿里云短信发送失败: {'; '.join(errors)}"
    
    @staticmethod
    def _aliyun_percent_encode(s):
        import urllib.parse
        if not isinstance(s, str):
            s = str(s)
        encoded = urllib.parse.quote(s, safe='')
        return encoded.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')
    
    @staticmethod
    def _send_sms_tencent(config, title, content, phones):
        """发送腾讯云短信"""
        import hashlib
        import hmac
        import time
        
        secret_id = config.get('access_key')
        secret_key = config.get('access_secret')
        sign_name = config.get('sign_name')
        template_code = config.get('template_code')
        sdk_app_id = config.get('sdk_app_id', '')
        
        if not sdk_app_id:
            return False, "腾讯云短信缺少SdkAppId配置"
        
        host = 'sms.tencentcloudapi.com'
        service = 'sms'
        action = 'SendSms'
        version = '2021-01-11'
        region = 'ap-guangzhou'
        
        template_param_set = [title, content[:80], datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        
        success_count = 0
        fail_count = 0
        errors = []
        
        for phone in phones:
            try:
                if not phone.startswith('+'):
                    phone = '+86' + phone
                
                timestamp = int(time.time())
                date_stamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d')
                
                payload = json.dumps({
                    'PhoneNumberSet': [phone],
                    'SmsSdkAppId': sdk_app_id,
                    'SignName': sign_name,
                    'TemplateId': template_code,
                    'TemplateParamSet': template_param_set,
                })
                
                http_request_method = 'POST'
                canonical_uri = '/'
                canonical_querystring = ''
                content_type = 'application/json; charset=utf-8'
                canonical_headers = f'content-type:{content_type}\nhost:{host}\nx-tc-action:{action.lower()}\n'
                signed_headers = 'content-type;host;x-tc-action'
                hashed_payload = hashlib.sha256(payload.encode('utf-8')).hexdigest()
                canonical_request = f'{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{hashed_payload}'
                
                algorithm = 'TC3-HMAC-SHA256'
                credential_scope = f'{date_stamp}/{service}/tc3_request'
                hashed_canonical_request = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
                string_to_sign = f'{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}'
                
                secret_date = hmac.new(f'TC3{secret_key}'.encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
                secret_service = hmac.new(secret_date, service.encode('utf-8'), hashlib.sha256).digest()
                secret_signing = hmac.new(secret_service, 'tc3_request'.encode('utf-8'), hashlib.sha256).digest()
                signature = hmac.new(secret_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
                
                authorization = f'{algorithm} Credential={secret_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}'
                
                headers = {
                    'Authorization': authorization,
                    'Content-Type': content_type,
                    'Host': host,
                    'X-TC-Action': action,
                    'X-TC-Timestamp': str(timestamp),
                    'X-TC-Version': version,
                    'X-TC-Region': region,
                }
                
                response = requests.post(f'https://{host}', headers=headers, data=payload, timeout=10)
                result = response.json()
                
                response_status = result.get('Response', {})
                send_status_set = response_status.get('SendStatusSet', [])
                
                if send_status_set and send_status_set[0].get('Code') == 'Ok':
                    success_count += 1
                else:
                    fail_count += 1
                    err_msg = send_status_set[0].get('Message', response_status.get('Error', {}).get('Message', '未知错误')) if send_status_set else response_status.get('Error', {}).get('Message', '未知错误')
                    errors.append(f"{phone}: {err_msg}")
            except Exception as e:
                fail_count += 1
                errors.append(f"{phone}: {str(e)}")
        
        if success_count > 0 and fail_count == 0:
            return True, f"腾讯云短信发送成功({success_count}条)"
        elif success_count > 0:
            return True, f"腾讯云短信部分成功({success_count}条)，失败: {'; '.join(errors)}"
        else:
            return False, f"腾讯云短信发送失败: {'; '.join(errors)}"
    
    @staticmethod
    def _send_sms_huawei(config, title, content, phones):
        """发送华为云短信"""
        import hashlib
        import hmac
        import base64
        import time
        
        app_key = config.get('access_key')
        app_secret = config.get('access_secret')
        sign_name = config.get('sign_name')
        template_code = config.get('template_code')
        sender = config.get('sender', '88230102099')
        
        api_url = config.get('api_url', 'https://smsapi.cn-north-4.myhuaweicloud.com:443/sms/batchSendSms/v1')
        
        template_var_values = json.dumps([title, content[:80], datetime.now().strftime('%Y-%m-%d %H:%M:%S')], ensure_ascii=False)
        
        success_count = 0
        fail_count = 0
        errors = []
        
        for phone in phones:
            try:
                if not phone.startswith('+'):
                    phone = '+86' + phone
                
                wsse_header = AlertNotifier._build_huawei_wsse_header(app_key, app_secret)
                
                body_data = {
                    'from': sender,
                    'to': phone,
                    'templateId': template_code,
                    'templateParas': template_var_values,
                    'signature': sign_name,
                }
                
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Authorization': 'WSSE realm="SDP",profile="UsernameToken",type="Appkey"',
                    'X-WSSE': wsse_header,
                }
                
                response = requests.post(api_url, data=body_data, headers=headers, timeout=10)
                result = response.json()
                
                code = result.get('code', '')
                if code == '000000':
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{phone}: {result.get('description', code)}")
            except Exception as e:
                fail_count += 1
                errors.append(f"{phone}: {str(e)}")
        
        if success_count > 0 and fail_count == 0:
            return True, f"华为云短信发送成功({success_count}条)"
        elif success_count > 0:
            return True, f"华为云短信部分成功({success_count}条)，失败: {'; '.join(errors)}"
        else:
            return False, f"华为云短信发送失败: {'; '.join(errors)}"
    
    @staticmethod
    def _build_huawei_wsse_header(app_key, app_secret):
        import hashlib
        import hmac
        import base64
        import time
        import uuid
        
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        nonce = str(uuid.uuid4())
        
        digest = hashlib.sha256((nonce + now).encode('utf-8')).digest()
        password_digest = base64.b64encode(digest).decode('utf-8')
        
        wsse = (
            f'UsernameToken Username="{app_key}",'
            f'PasswordDigest="{password_digest}",'
            f'Nonce="{nonce}",'
            f'Created="{now}"'
        )
        return wsse
    
    @staticmethod
    def _send_webhook(config, title, content):
        """发送Webhook请求"""
        url = config.get('url')
        method = config.get('method', 'POST')
        headers = config.get('headers', '{}')
        body_template = config.get('body_template', '')
        
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
            
            if 200 <= response.status_code < 300:
                return True, f"Webhook发送成功: {response.text[:200]}"
            else:
                return False, f"Webhook发送失败: HTTP {response.status_code} - {response.text[:200]}"
        except Exception as e:
            return False, f"Webhook发送失败: {str(e)}"


def send_alert(task, content):
    """
    发送告警通知（入口函数）
    :param task: AlertTask 实例
    :param content: 告警内容
    :return: list of (success, response, channel_name, channel_type)
    """
    from .models import AlertNotifyConfig
    
    results = []
    channel_ids = task.get_channel_ids()
    
    if not channel_ids:
        return [(False, "未配置通知渠道", "", "")]
    
    configs = AlertNotifyConfig.objects.filter(id__in=channel_ids)
    enabled_ids = set()
    
    for config in configs:
        if not config.is_enabled:
            results.append((False, f"渠道 [{config.name}] 已禁用，已跳过", config.name, config.channel_type))
            continue
        enabled_ids.add(config.id)
        success, response = AlertNotifier.send(config, task.name, content)
        results.append((success, response, config.name, config.channel_type))
    
    skipped_ids = set(channel_ids) - enabled_ids - {c.id for c in configs}
    for sid in skipped_ids:
        results.append((False, f"渠道ID [{sid}] 不存在，已跳过", str(sid), ""))
    
    return results
