#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-23
# +-------------------------------------------------------------------

# ------------------------------
# 多数据库路由器(分库) 提升性能
# ------------------------------

class RuyiDatabasesRouter:
    """
    @name 多数据库路由器
    @author lybbn<2024-01-23>
    """
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'syslogs':
            return 'logs'
        elif model._meta.app_label in ["systask","django_apscheduler"]:
            return 'tasks'
        elif model._meta.app_label == 'sysshop':
            return 'shop'
        elif model._meta.app_label == 'sysbak':
            return 'backup'
        elif model._meta.app_label == 'sysdocker':
            return 'docker'
        elif model._meta.app_label == 'sysmonitor':
            return 'monitor'
        elif model._meta.app_label == 'sysalert':
            return 'alert'
        elif model._meta.app_label == 'syswaf':
            if model.__name__ == 'WafAttackLog':
                return 'waf_logs'
            return 'waf'
        elif model._meta.app_label == 'sysai':
            return 'ai'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'syslogs':
            return 'logs'
        elif model._meta.app_label in ["systask","django_apscheduler"]:
            return 'tasks'
        elif model._meta.app_label == 'sysshop':
            return 'shop'
        elif model._meta.app_label == 'sysbak':
            return 'backup'
        elif model._meta.app_label == 'sysdocker':
            return 'docker'
        elif model._meta.app_label == 'sysmonitor':
            return 'monitor'
        elif model._meta.app_label == 'sysalert':
            return 'alert'
        elif model._meta.app_label == 'syswaf':
            if model.__name__ == 'WafAttackLog':
                return 'waf_logs'
            return 'waf'
        elif model._meta.app_label == 'sysai':
            return 'ai'
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'system':
            return db == 'default'
        elif app_label == 'syslogs':
            return db == 'logs'
        elif app_label in ["systask","django_apscheduler"]:
            return db == 'tasks'
        elif app_label == 'sysshop':
            return db == 'shop'
        elif app_label == 'sysbak':
            return db == 'backup'
        elif app_label == 'sysdocker':
            return db == 'docker'
        elif app_label == 'sysmonitor':
            return db == 'monitor'
        elif app_label == 'sysalert':
            return db == 'alert'
        elif app_label == 'syswaf':
            if model_name == 'wafattacklog':
                return db == 'waf_logs'
            return db == 'waf'
        elif app_label == 'sysai':
            return db == 'ai'
        else:
            return db == 'default'
