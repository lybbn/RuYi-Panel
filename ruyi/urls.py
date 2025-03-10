"""ruyi URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls import handler500
from django.urls import path,re_path,include
from apps.system.views.login import *
from apps.system.views.file_manage import RYFileMediaView,RYGetFileDownloadView
from utils.streamingmedia_response import streamingmedia_serve
from django.conf import settings
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from utils.security.security_path import security_path_view,response_404_view

urlpatterns = [
    path('api/captcha/', CaptchaView.as_view()),
    path('api/token/', LoginView.as_view(), name='login'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('fileMedia/', RYFileMediaView.as_view(), name='file_media'),
    path('download/', RYGetFileDownloadView.as_view(), name='download'),
    path('api/sys/', include('apps.system.urls')),
    path('api/logs/', include('apps.syslogs.urls')),
    path('api/task/', include('apps.systask.urls')),
    path('api/bak/', include('apps.sysbak.urls')),
    path('api/docker/', include('apps.sysdocker.urls')),
    path('static/<path:path>', streamingmedia_serve, {'document_root': os.path.join(settings.STATIC_ROOT, "static") },),  # 处理静态文件
    path('media/<path:path>', streamingmedia_serve, {'document_root': os.path.join(settings.STATIC_ROOT, "static") },),  # 处理媒体文件
    re_path(r'^(logo\.png|favicon\.ico)$', streamingmedia_serve, {'document_root': settings.STATIC_ROOT},),
]

security_path = settings.RUYI_SECURITY_PATH
if security_path == '/ry': security_path = ''

if security_path:
    urlpatterns += [
        #安全入口
        path(security_path, security_path_view,name='安全入口'),
    ]

urlpatterns += [
    re_path(r'', security_path_view,name='首页'),
    re_path(r'^.*', response_404_view,name='默认路由重定向'),#404页面
]