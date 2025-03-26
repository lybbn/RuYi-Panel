"""
Request工具类
"""
import json
from utils.common import is_private_ip,ReadFile,WriteFile
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.urls.resolvers import ResolverMatch
from rest_framework_simplejwt.authentication import JWTAuthentication
from user_agents import parse
from django.conf import settings
from utils.ip_util import IPQQwry

def get_client_info(request):
    """
    获取请求用户的客户端信息
    """
    
    if hasattr(request, 'ruyi_ws_request_flag') and request.ruyi_ws_request_flag == 'ruyi_request_flag':
        user = request.scope.get("user",None)
        ip = request.scope.get('client', ('', ''))[0] # 获取客户端的 IP 地址
        return {
            'username': user.username if user else "",
            'ip': ip,
            'ip_area':get_ip_area(ip),
            'path': request.scope.get('path', ''),
            'body': {},  # WebSocket 没有 HTTP 请求的 body
            'request_os': 'Unknown',  # WebSocket 通常不携带操作系统信息
            'browser': 'WebSocket Client',  # 浏览器可以设置为 'WebSocket Client'
            'request_msg':  getattr(request, 'client_data', None),
        }
    else:
        ip = get_request_ip(request)
        body = getattr(request, 'request_data', {})
        return {
            'username':request.user.username,
            'ip':ip,
            'ip_area':get_ip_area(ip),
            'path':get_request_path(request),
            'body':body,
            'request_os': get_os(request),
            'browser': get_browser(request),
            'request_msg': request.session.get('request_msg'),
        }

def get_ip_area(ip):
    """
    获取ip地址归属地
    """
    if ip in ['localhost','127.0.0.1']:
        return "本机地址"
    try:
        if is_private_ip(ip):
            return "局域网"
    except:
        pass
    area = IPQQwry().get_local_ips_area([ip])[0]
    return area

def get_request_user(request):
    """
    获取请求user
    (1)如果request里的user没有认证,那么则手动认证一次
    :param request:
    :return:
    """
    user: AbstractBaseUser = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return user
    try:
        user, token = JWTAuthentication().authenticate(request)
    except Exception as e:
        pass
    return user or AnonymousUser()


def get_request_ip(request):
    """
    获取请求IP
    :param request:
    :return:
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[-1].strip()
        return ip
    ip = request.META.get('REMOTE_ADDR', '') or getattr(request, 'request_ip', None)
    return ip or 'unknown'

    # ip = getattr(request, 'request_ip', None)
    # if ip:
    #     return ip
    # ip = request.META.get('REMOTE_ADDR', '')
    # if not ip:
    #     x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    #     if x_forwarded_for:
    #         ip = x_forwarded_for.split(',')[-1].strip()
    #     else:
    #         ip = 'unknown'
    # return ip

def get_request_data(request):
    """
    获取请求参数
    :param request:
    :return:
    """
    request_data = getattr(request, 'request_data', None)
    if request_data:
        return request_data
    data: dict = {**request.GET.dict(), **request.POST.dict()}
    if not data:
        try:
            body = request.body
            if body:
                data = json.loads(body)
        except Exception as e:
            pass
        if not isinstance(data, dict):
            data = {'data': data}
    return data


def get_request_path(request, *args, **kwargs):
    """
    获取请求路径
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    request_path = getattr(request, 'request_path', None)
    if request_path:
        return request_path
    values = []
    for arg in args:
        if len(arg) == 0:
            continue
        if isinstance(arg, str):
            values.append(arg)
        elif isinstance(arg, (tuple, set, list)):
            values.extend(arg)
        elif isinstance(arg, dict):
            values.extend(arg.values())
    if len(values) == 0:
        return request.path
    path: str = request.path
    for value in values:
        path = path.replace('/' + value, '/' + '{id}')
    return path


def get_request_canonical_path(request, ):
    """
    获取请求路径
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    request_path = getattr(request, 'request_canonical_path', None)
    if request_path:
        return request_path
    path: str = request.path
    resolver_match: ResolverMatch = request.resolver_match
    for value in resolver_match.args:
        path = path.replace(f"/{value}", "/{id}")
    for key, value in resolver_match.kwargs.items():
        if key == 'pk':
            path = path.replace(f"/{value}", f"/{{id}}")
            continue
        path = path.replace(f"/{value}", f"/{{{key}}}")

    return path


def get_browser(request, ):
    """
    获取浏览器名
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    browser=""
    try:
        ua_string = request.META['HTTP_USER_AGENT']
        if ua_string:
            user_agent = parse(ua_string)
            browser = user_agent.get_browser()
    except:
        pass
    return browser


def get_os(request, ):
    """
    获取操作系统
    :param request:
    :param args:
    :param kwargs:
    :return:
    """
    theos = ""
    try:
        ua_string = request.META['HTTP_USER_AGENT']
        if ua_string:
            user_agent = parse(ua_string)
            theos = user_agent.get_os()
    except:
        pass
    return theos


def get_verbose_name(queryset=None, view=None, model=None):
    """
    获取 verbose_name
    :param request:
    :param view:
    :return:
    """
    try:
        if queryset is not None and hasattr(queryset, 'model'):
            model = queryset.model
        elif view and hasattr(view.get_queryset(), 'model'):
            model = view.get_queryset().model
        elif view and hasattr(view.get_serializer(), 'Meta') and hasattr(view.get_serializer().Meta, 'model'):
            model = view.get_serializer().Meta.model
        if model:
            return getattr(model, '_meta').verbose_name
        else:
            model = queryset.model._meta.verbose_name
    except Exception as e:
        pass
    return model if model else ""