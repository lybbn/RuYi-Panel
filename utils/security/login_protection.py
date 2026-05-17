#!/usr/bin
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | Date: 2026-04-29
# +-------------------------------------------------------------------

# ------------------------------
# 登录暴力破解防护
# ------------------------------

import time
from django.core.cache import cache
from utils.request_util import get_request_ip

LOGIN_RATE_PREFIX = 'login_rate:'
LOGIN_FAIL_PREFIX = 'login_fail:'
LOGIN_BAN_PREFIX = 'login_ban:'
LOGIN_BAN_LEVEL_PREFIX = 'login_ban_level:'

RATE_LIMIT = 10
RATE_WINDOW = 60

FAIL_THRESHOLD_L2 = 5
BAN_DURATION_L2 = 600

FAIL_THRESHOLD_L3 = 15
FAIL_WINDOW_L3 = 3600
BAN_DURATION_L3 = 3600


def _get_client_ip(request):
    return get_request_ip(request)


def check_login_allowed(request):
    """
    检查IP是否允许登录
    返回: (allowed: bool, msg: str, remaining_seconds: int)
    """
    ip = _get_client_ip(request)
    if not ip or ip == 'unknown':
        return True, '', 0

    ban_key = LOGIN_BAN_PREFIX + ip
    ban_info = cache.get(ban_key)
    if ban_info:
        remaining = ban_info.get('expire_at', 0) - int(time.time())
        if remaining > 0:
            minutes = remaining // 60
            seconds = remaining % 60
            if minutes > 0:
                msg = f'登录失败次数过多，请 {minutes}分{seconds}秒 后重试'
            else:
                msg = f'登录失败次数过多，请 {seconds}秒 后重试'
            return False, msg, remaining
        else:
            cache.delete(ban_key)
            cache.delete(LOGIN_BAN_LEVEL_PREFIX + ip)
            cache.delete(LOGIN_FAIL_PREFIX + ip)
            cache.delete(LOGIN_RATE_PREFIX + ip)

    rate_key = LOGIN_RATE_PREFIX + ip
    rate_count = cache.get(rate_key, 0)
    if rate_count >= RATE_LIMIT:
        return False, '操作过于频繁，请稍后再试', RATE_WINDOW

    return True, '', 0


def record_login_success(request):
    """
    登录成功后清除失败计数和频率计数
    """
    ip = _get_client_ip(request)
    if not ip or ip == 'unknown':
        return
    cache.delete(LOGIN_FAIL_PREFIX + ip)
    cache.delete(LOGIN_RATE_PREFIX + ip)


def record_login_failure(request):
    """
    登录失败后记录计数，判断是否触发封禁
    返回: (banned: bool, msg: str, remaining_seconds: int)
    """
    ip = _get_client_ip(request)
    if not ip or ip == 'unknown':
        return False, '', 0

    rate_key = LOGIN_RATE_PREFIX + ip
    try:
        cache.incr(rate_key)
    except ValueError:
        cache.set(rate_key, 1, RATE_WINDOW)

    fail_key = LOGIN_FAIL_PREFIX + ip
    fail_count = cache.get(fail_key, 0)
    fail_count += 1
    cache.set(fail_key, fail_count, FAIL_WINDOW_L3)

    if fail_count >= FAIL_THRESHOLD_L3:
        _ban_ip(ip, BAN_DURATION_L3, 3)
        msg = f'连续登录失败{fail_count}次，IP已被封禁1小时'
        return True, msg, BAN_DURATION_L3

    if fail_count >= FAIL_THRESHOLD_L2:
        ban_level_key = LOGIN_BAN_LEVEL_PREFIX + ip
        current_level = cache.get(ban_level_key, 0)
        if current_level < 2:
            _ban_ip(ip, BAN_DURATION_L2, 2)
            msg = f'连续登录失败{fail_count}次，请10分钟后重试'
            return True, msg, BAN_DURATION_L2

    remaining_attempts = FAIL_THRESHOLD_L2 - fail_count
    if remaining_attempts > 0:
        return False, f'账号/密码错误，还剩{remaining_attempts}次尝试机会', 0

    return False, '账号/密码错误', 0


def _ban_ip(ip, duration, level):
    """
    封禁IP
    """
    ban_key = LOGIN_BAN_PREFIX + ip
    ban_level_key = LOGIN_BAN_LEVEL_PREFIX + ip
    expire_at = int(time.time()) + duration
    cache.set(ban_key, {'expire_at': expire_at, 'level': level}, duration)
    cache.set(ban_level_key, level, duration)


def get_login_ban_status(request):
    """
    获取当前IP的封禁状态（供前端查询）
    返回: dict or None
    """
    ip = _get_client_ip(request)
    if not ip or ip == 'unknown':
        return None

    ban_key = LOGIN_BAN_PREFIX + ip
    ban_info = cache.get(ban_key)
    if not ban_info:
        return None

    remaining = ban_info.get('expire_at', 0) - int(time.time())
    if remaining <= 0:
        cache.delete(ban_key)
        cache.delete(LOGIN_BAN_LEVEL_PREFIX + ip)
        cache.delete(LOGIN_FAIL_PREFIX + ip)
        cache.delete(LOGIN_RATE_PREFIX + ip)
        return None

    return {
        'banned': True,
        'remaining_seconds': remaining,
        'level': ban_info.get('level', 1),
    }
