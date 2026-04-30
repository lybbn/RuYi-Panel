#!/usr/bin
#coding: utf-8
from django.core.management.base import BaseCommand
from django.core.cache import cache
from utils.security.login_protection import LOGIN_RATE_PREFIX, LOGIN_FAIL_PREFIX, LOGIN_BAN_PREFIX, LOGIN_BAN_LEVEL_PREFIX


class Command(BaseCommand):
    """
    @name 清除登录封禁和失败计数: python manage.py clearLoginBan
    @desc 只清除指定IP: python manage.py clearLoginBan --ip=192.168.1.100
    """

    def add_arguments(self, parser):
        parser.add_argument('--ip', type=str, default='', help='指定IP，为空则清除所有')

    def handle(self, *args, **options):
        ip = options.get('ip', '')
        prefixes = [LOGIN_RATE_PREFIX, LOGIN_FAIL_PREFIX, LOGIN_BAN_PREFIX, LOGIN_BAN_LEVEL_PREFIX]

        if ip:
            for prefix in prefixes:
                cache.delete(prefix + ip)
            self.stdout.write(self.style.SUCCESS(f'已清除 IP {ip} 的登录封禁和计数'))
        else:
            raw_cache = cache._cache
            cleared = 0
            for raw_key in raw_cache:
                raw_key_str = str(raw_key)
                for prefix in prefixes:
                    if prefix in raw_key_str:
                        logical_key = raw_key_str.split(':', 2)[-1] if raw_key_str.startswith(':') else raw_key_str
                        cache.delete(logical_key)
                        cleared += 1
                        break
            self.stdout.write(self.style.SUCCESS(f'已清除所有登录封禁和计数，共 {cleared} 条记录'))
