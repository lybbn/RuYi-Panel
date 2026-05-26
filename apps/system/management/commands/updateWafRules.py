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

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2026-05-16
    @name:更新WAF防护规则命令: python manage.py updateWafRules
    @使用场景：增量更新WAF规则，新增规则自动创建，已有规则不覆盖
    """

    help = '更新WAF防护规则（增量：新增规则自动创建，已有规则不覆盖）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='强制重建所有规则（删除已有规则后从JSON重建，会覆盖在线修改）',
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            default=True,
            help='更新后同步配置到Nginx（默认开启）',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        do_sync = options.get('sync', True)

        from apps.syswaf.init_data import init_waf_data

        self.stdout.write(self.style.WARNING(
            f'正在{"强制重建" if force else "增量更新"}WAF规则...'
        ))

        categories, rules, config, ip_group, from_remote = init_waf_data(force=force)

        source = '远程' if from_remote else '本地'
        self.stdout.write(self.style.SUCCESS(
            f'规则更新完成（来源: {source}）: 新增分类 {categories} 个, 新增规则 {rules} 条'
        ))

        if do_sync and (categories > 0 or rules > 0):
            self.stdout.write('正在同步配置到Nginx...')
            try:
                from apps.syswaf.services import WafConfigSync
                syncer = WafConfigSync()
                syncer.sync_rules()

                from utils.install.nginx import Reload_Nginx, is_nginx_running
                from utils.common import current_os
                is_windows = current_os == "windows"
                if is_nginx_running(is_windows=is_windows, simple_check=True):
                    Reload_Nginx(is_windows=is_windows)
                    self.stdout.write(self.style.SUCCESS('Nginx已重载，规则已生效'))
                else:
                    self.stdout.write(self.style.WARNING('Nginx未运行，规则已同步但未生效'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'同步配置失败: {e}'))
        elif not do_sync:
            self.stdout.write(self.style.WARNING('已跳过Nginx同步（--no-sync）'))
        else:
            self.stdout.write(self.style.SUCCESS('无新增规则，无需同步'))
