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

# ------------------------------
# 监控数据采集定时任务
# ------------------------------

import logging
from apps.systask.scheduler import scheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger('apscheduler.scheduler')

# 监控数据采集任务ID
MONITOR_COLLECT_JOB_ID = 'monitor_data_collect'

def get_monitor_config():
    """
    获取监控配置
    """
    try:
        from apps.sysmonitor.models import MonitorConfig
        config = MonitorConfig.objects.first()
        return config
    except Exception as e:
        logger.error(f"获取监控配置失败: {e}")
        return None

def register_monitor_task():
    """
    注册监控数据采集定时任务
    根据配置决定是否启用，默认每60秒采集一次数据
    """
    try:
        # 确保调度器已启动
        if not scheduler.running:
            scheduler.start()
            logger.info("调度器已启动")
        
        # 检查任务是否已存在
        existing_job = scheduler.get_job(MONITOR_COLLECT_JOB_ID)
        if existing_job:
            logger.info(f"监控数据采集任务已存在: {MONITOR_COLLECT_JOB_ID}")
            return
        
        # 获取配置
        config = get_monitor_config()
        interval = config.collect_interval if config else 60
        is_enabled = config.is_enabled if config else False
        
        # 如果监控未启用，不注册任务
        if not is_enabled:
            logger.info("监控功能已关闭，跳过任务注册")
            return
        
        # 添加监控数据采集任务
        scheduler.add_job(
            func=collect_monitor_data,
            trigger=IntervalTrigger(seconds=interval),
            id=MONITOR_COLLECT_JOB_ID,
            name='系统监控数据采集',
            replace_existing=True,
            misfire_grace_time=300  # 5分钟的宽限时间
        )
        logger.info(f"监控数据采集任务注册成功，采集间隔: {interval}秒")
    except Exception as e:
        logger.error(f"注册监控数据采集任务失败: {e}")

def collect_monitor_data():
    """
    执行监控数据采集
    采集前检查监控是否启用
    """
    try:
        # 检查监控是否启用
        config = get_monitor_config()
        if config and not config.is_enabled:
            logger.debug("监控功能已关闭，跳过数据采集")
            return
        
        # 延迟导入避免循环依赖
        from apps.sysmonitor.views import MonitorDataCollector
        MonitorDataCollector.collect_all()
        logger.debug("监控数据采集完成")
        
        # 触发告警检查（资源类告警）
        try:
            from apps.sysalert.tasks import check_resource_alert
            check_resource_alert()
        except Exception as alert_e:
            logger.error(f"告警检查失败: {alert_e}")
            
    except Exception as e:
        logger.error(f"监控数据采集失败: {e}")

def remove_monitor_task():
    """
    移除监控数据采集定时任务
    """
    try:
        scheduler.remove_job(MONITOR_COLLECT_JOB_ID)
        logger.info("监控数据采集任务已移除")
    except Exception:
        pass

def update_monitor_task_interval(seconds):
    """
    更新监控数据采集间隔
    @param seconds: 采集间隔（秒）
    """
    try:
        # 检查任务是否存在
        existing_job = scheduler.get_job(MONITOR_COLLECT_JOB_ID)
        if not existing_job:
            # 任务不存在，重新注册
            register_monitor_task()
            return
        
        scheduler.reschedule_job(
            MONITOR_COLLECT_JOB_ID,
            trigger=IntervalTrigger(seconds=seconds)
        )
        logger.info(f"监控数据采集间隔已更新为: {seconds}秒")
    except Exception as e:
        logger.error(f"更新监控数据采集间隔失败: {e}")

def toggle_monitor_task(enabled):
    """
    启用或禁用监控任务
    @param enabled: True启用，False禁用
    """
    try:
        # 确保调度器已启动
        if not scheduler.running:
            scheduler.start()
            logger.info("调度器已启动")
        
        config = get_monitor_config()
        interval = config.collect_interval if config else 60
        
        existing_job = scheduler.get_job(MONITOR_COLLECT_JOB_ID)
        
        if enabled:
            # 启用监控
            if existing_job:
                logger.info("监控数据采集任务已在运行")
            else:
                scheduler.add_job(
                    func=collect_monitor_data,
                    trigger=IntervalTrigger(seconds=interval),
                    id=MONITOR_COLLECT_JOB_ID,
                    name='系统监控数据采集',
                    replace_existing=True,
                    misfire_grace_time=300
                )
                logger.info(f"监控数据采集任务已启用，采集间隔: {interval}秒")
        else:
            # 禁用监控
            if existing_job:
                scheduler.remove_job(MONITOR_COLLECT_JOB_ID)
                logger.info("监控数据采集任务已禁用")
            else:
                logger.info("监控数据采集任务未运行")
    except Exception as e:
        logger.error(f"切换监控任务状态失败: {e}")
