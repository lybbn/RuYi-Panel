#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | Date: 2026-02-08
# +-------------------------------------------------------------------

import os
import json
import struct
import socket
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from utils.common import ReadFile
from utils.request_util import get_request_ip
from apps.system.models import Users

def ip_to_int(ip):
    try:
        return struct.unpack("!I", socket.inet_aton(ip))[0]
    except:
        return 0

def is_ip_in_range(ip, start_ip, end_ip):
    try:
        ip_int = ip_to_int(ip)
        start_int = ip_to_int(start_ip)
        end_int = ip_to_int(end_ip)
        return start_int <= ip_int <= end_int
    except:
        return False

class APIKeyAuthentication(BaseAuthentication):
    """
    API密钥认证
    """
    def authenticate(self, request):
        # 读取API配置
        config_path = os.path.join(settings.RUYI_DATA_BASE_PATH, 'api_config.json')
        if not os.path.exists(config_path):
            return None
        try:
            config = json.loads(ReadFile(config_path))
        except:
            return None
        if not config.get('api_enable', False):
            return None
        api_key = request.META.get('HTTP_RY_API_KEY') or request.GET.get('api_key')
        if not api_key:
            return None
        if str(api_key) != str(config.get('api_key')):
            raise AuthenticationFailed('无效的API密钥')
        # 检查IP白名单
        whitelist = config.get('api_ip_whitelist', [])
        # 如果白名单不为空，则进行检查
        if whitelist:
            client_ip = get_request_ip(request)
            is_allowed = False
            for rule in whitelist:
                rule = rule.strip()
                if not rule:
                    continue
                
                # 所有IP
                if rule == '*':
                    is_allowed = True
                    break
                
                # IP段 (192.168.1.1-192.168.1.255)
                if '-' in rule:
                    parts = rule.split('-')
                    if len(parts) == 2:
                        start_ip = parts[0].strip()
                        end_ip = parts[1].strip()
                        if is_ip_in_range(client_ip, start_ip, end_ip):
                            is_allowed = True
                            break
                
                # 单IP
                else:
                    if client_ip == rule:
                        is_allowed = True
                        break
            
            if not is_allowed:
                raise AuthenticationFailed('IP未授权')
        
        # 认证通过，返回超级管理员用户
        user = Users.objects.filter(is_superuser=True).first()
        if not user:
            raise AuthenticationFailed('系统未配置用户')
            
        return (user, None)
