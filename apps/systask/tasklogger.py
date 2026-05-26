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
# 任务执行日志记录器
# ------------------------------

import os
import logging
from django.conf import settings
from logging.handlers import RotatingFileHandler
from utils.common import GetLogsPath
logger = logging.getLogger()

def tasklogger(job_id):
    """
    @name 配置任务执行日志记录器
    @author lybbn<2024-02-07>
    """

    if len(settings.TASK_LOGGERS_DIC) > 50:
        _cleanup_old_loggers()

    if job_id in settings.TASK_LOGGERS_DIC:
        return settings.TASK_LOGGERS_DIC[job_id]

    tasklogger = logging.getLogger(job_id)
    # tasklogger = logging.getLogger("apscheduler.scheduler")#可能出现互相记录情况
    tasklogger.setLevel(logging.INFO)
    # 设置 'propagate' 为 False，防止日志传播到父日志记录器
    tasklogger.propagate = False
    if tasklogger.handlers:
        settings.TASK_LOGGERS_DIC[job_id] = tasklogger
        return tasklogger
    task_log_root_path = os.path.join(GetLogsPath(),"ruyitask")
    if not os.path.exists(task_log_root_path):
        os.makedirs(task_log_root_path)
    task_log_path = os.path.join(task_log_root_path,job_id+".log")
    if not os.path.exists(task_log_path):
        with open(task_log_path, 'w', encoding="utf-8") as f:
            pass
    file_handler = RotatingFileHandler(
        task_log_path,
        maxBytes=1024 * 1024 * 50,  # 每个日志文件的最大大小
        backupCount=3,  # 保留的日志文件数量
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] - %(message)s')
    file_handler.setFormatter(formatter)
    tasklogger.addHandler(file_handler)
    
    settings.TASK_LOGGERS_DIC[job_id] = tasklogger
    return tasklogger

def _cleanup_old_loggers():
    """
    @name 清理过多的Logger实例，释放内存
    @author lybbn<2024-02-18>
    """
    try:
        keys_to_remove = list(settings.TASK_LOGGERS_DIC.keys())[:30]
        for key in keys_to_remove:
            tl = settings.TASK_LOGGERS_DIC[key]
            for handler in tl.handlers[:]:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.flush()
                    handler.close()
                tl.removeHandler(handler)
            for f in tl.filters[:]:
                tl.removeFilter(f)
            del settings.TASK_LOGGERS_DIC[key]
    except Exception:
        pass

def deleteTaskLogs(job_id):
    """
    @name 删除执行日志文件,如果job_id则删除指定，如果job_id为空，则清除所有任务执行日志
    @author lybbn<2024-02-07>
    """
    task_log_root_path = os.path.join(GetLogsPath(),"ruyitask")
    if job_id:
        log_file_prefix = job_id + ".log"
        if job_id in settings.TASK_LOGGERS_DIC:
            taskloggers = settings.TASK_LOGGERS_DIC[job_id]
            for handler in taskloggers.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.flush()
                    handler.close()
            #清空处理程序和过滤器
            for handler in taskloggers.handlers[:]:
                taskloggers.removeHandler(handler)
            for filter in taskloggers.filters[:]:
                taskloggers.removeFilter(filter)
            del settings.TASK_LOGGERS_DIC[job_id]
        delete_rotating_log_files(task_log_root_path,log_file_prefix)
    else:
        for i in settings.TASK_LOGGERS_DIC:
            taskloggers = settings.TASK_LOGGERS_DIC[i]
            for handler in taskloggers.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.flush()
                    handler.close()
            #清空处理程序和过滤器
            for handler in taskloggers.handlers[:]:
                taskloggers.removeHandler(handler)
            for filter in taskloggers.filters[:]:
                taskloggers.removeFilter(filter)
        settings.TASK_LOGGERS_DIC = {}
        delete_files_in_folder(task_log_root_path)

def delete_rotating_log_files(log_dir, log_file_prefix):
    """
    @name 删除指定文件夹下，指定文件前缀的文件
    @author lybbn<2024-02-07>
    """
    for file in os.listdir(log_dir):
        if file.startswith(log_file_prefix):
            file_path = os.path.join(log_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"删除任务日志文件错误 {file_path}: {e}")

def delete_files_in_folder(folder_path):
    """
    @name 删除指定文件夹下，所有文件（不包含子文件夹）
    @author lybbn<2024-02-07>
    """
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"删除任务日志文件夹下所有任务日志文件错误 {file_path}: {e}")