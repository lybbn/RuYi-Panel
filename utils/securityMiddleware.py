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
import re
import json
from utils.request_util import get_request_path
from django.conf import settings
from utils.security.security_path import ResponseNginx404,security_path_authed_key
from django.http import JsonResponse

def get_post_data(request):
    try:
        request_params = {}
        if request.method == 'POST' and request.content_type == 'application/json':
            request_params = json.loads(request.body)
        return request_params
    except:
        return {}

whiteList = {
    '/api/captcha/': {},
    '/api/token/': {},
    '/api/token/refresh/': {},
    '/api/sys/softinfoMg/': {"action":["get_soft_info","get_redis_dblist","get_redis_keylist"]},
    '/api/sys/softmanage/': {"action":["get_conf","get_loadstatus"]},
    '/api/sys/fileManage/': {"action":["list_dir"]},
    '/api/sys/softlist/': {},
    '/api/logs/opLog/': {"action":["get_runserver_log","get_runerror_log","get_runaccess_log","get_runtask_log"]},
}

whiteMethodList = ['GET', 'POST']

def ValidationApi(reqApi, validApi):
    """
    验证当前用户是否有接口权限
    :param reqApi: 当前请求的接口
    :param validApi: 用于验证的接口
    :return: True或者False
    """
    if validApi is not None:
        valid_api = validApi.replace('{id}', '.*?')
        matchObj = re.match(valid_api, reqApi, re.M | re.I)
        if matchObj:
            return True
        else:
            return False
    else:
        return False

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_path = get_request_path(request)
        # demo 模式
        if settings.RUYI_DEMO:
            if request.method not in whiteMethodList:
                return JsonResponse({'code':403,'msg': '演示模式，禁止操作'}, status=200)
            if request.method == 'POST':
                if request_path in whiteList:
                    allowed_params = whiteList[request_path]
                    if not allowed_params:
                        pass
                    else:
                        reqData = get_post_data(request)
                        for param, allowed_values in allowed_params.items():
                            request_value = reqData.get(param)
                            if request_value not in allowed_values:
                                return JsonResponse({'code':403,'msg': '演示模式，禁止操作'}, status=200)
                else:
                    return JsonResponse({'code':403,'msg': '演示模式，禁止操作'}, status=200)

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