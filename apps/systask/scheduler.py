#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-27
# +-------------------------------------------------------------------
# | EditDate: 2024-01-27
# +-------------------------------------------------------------------

# ------------------------------
# apscheduler instance
# ------------------------------

from django.conf import settings
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ProcessPoolExecutor, ThreadPoolExecutor

class Scheduler:
    
    TASK_THREAD_EXECUTOR_MAX_WORKERS = 10
    TASK_PROCESS_EXECUTOR_MAX_WORKERS = 10
    TASK_THREAD_STATUS = True
    TASK_PROCESS_STATUS = True
    
    #配置执行器
    @staticmethod
    def task_executor():
        executor = None

        process_executor = ProcessPoolExecutor(Scheduler.TASK_PROCESS_EXECUTOR_MAX_WORKERS)
        thread_executor = ThreadPoolExecutor(Scheduler.TASK_THREAD_EXECUTOR_MAX_WORKERS)

        if Scheduler.TASK_THREAD_STATUS and Scheduler.TASK_PROCESS_STATUS:
            executor = {
                'default': thread_executor,
                'processpool': process_executor
            }

        if Scheduler.TASK_PROCESS_STATUS and not Scheduler.TASK_THREAD_STATUS:
            executor = {
                'default': process_executor
            }

        if Scheduler.TASK_THREAD_STATUS and not Scheduler.TASK_PROCESS_STATUS:
            executor = {
                'default': thread_executor
            }

        return executor
    
    _instance = None
    # 任务相关配置
    job_defaults = {
        # 合并执行
        'coalesce': True,
        # 同一时间同个任务最大执行次数为1
        'max_instances': 1,
        'misfire_grace_time':1,#解决重启后过期任务被执行一次的bug
    }

    def __new__(cls):
        if not cls._instance:
            executors = cls.task_executor()  # 获取执行器字典
            cls._instance = BackgroundScheduler(timezone=settings.TIME_ZONE,job_defaults=cls.job_defaults,executors=executors)
        return cls._instance

scheduler = Scheduler()