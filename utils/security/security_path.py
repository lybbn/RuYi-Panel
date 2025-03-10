#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-03  
# +-------------------------------------------------------------------

# ------------------------------
# 安全入口
# ------------------------------
import os
from django.views.generic import TemplateView
from django.http import HttpResponse
from utils.request_util import get_request_path
from django.shortcuts import redirect
from django.conf import settings

security_path_authed_key = 'security_path_authed'

#安全入口
#安全入口启用：有安全入口重定向到index.html模板、没有安全入口直接nginx 404
#安全入口关闭：访问默认页时返回index.html模板，其他返回nginx 404
def security_path_view(request):
    request_path = get_request_path(request)
    # if request.session.get(security_path_authed_key,False) and request_path == settings.RUYI_SECURITY_PATH:
    #     return redirect('/')
    is_auth_security_path = False
    if settings.RUYI_SECURITY_PATH != '/ry' and not request.session.get(security_path_authed_key,False) and not request.user.is_authenticated:
        is_auth_security_path = True
    if is_auth_security_path:
        # 进行安全检查
        if not request_path == settings.RUYI_SECURITY_PATH:
            return ResponseNginx404()
    request.session[security_path_authed_key] = True
    if request.user.is_authenticated and request_path == settings.RUYI_SECURITY_PATH:
        return redirect('/')
    return TemplateView.as_view(template_name="index.html")(request)

#返回nginx 404 错误页，降低信息泄露风险，提升安全性
def ResponseNginx404(state = 404):
    html_content = '''<html>
<head><title>404 Not Found</title></head>
<body>
<center><h1>404 Not Found</h1></center>
<hr><center>nginx/1.20.1</center>
</body>
</html>'''
    return HttpResponse(html_content, content_type='text/html',status=state,charset='utf-8')

#404 Return 接口
def response_404_view(request):
    return ResponseNginx404()
