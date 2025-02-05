#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-02-16
# +-------------------------------------------------------------------

# ------------------------------
# 请求安全校验中间件
# ------------------------------
from utils.request_util import get_request_path
from django.conf import settings
from utils.security.security_path import ResponseNginx404,security_path_authed_key

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 在处理每个请求之前进行安全校验
        # 安全入口检查(正式环境启用)
        if False:
            request_path = get_request_path(request)
            is_auth_security_path = False
            if settings.RUYI_SECURITY_PATH != '/ry' and not request.session.get(security_path_authed_key,False) and not request.user.is_authenticated:
                is_auth_security_path = True
            if is_auth_security_path:
                # 进行安全检查
                if not request_path == settings.RUYI_SECURITY_PATH:
                    return ResponseNginx404()
                request.session[security_path_authed_key] = True
        response = self.get_response(request)
        return response