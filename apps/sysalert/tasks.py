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

"""
告警检查定时任务
"""

import logging
import requests
import re
import os
from datetime import datetime, timedelta
from django.utils import timezone
from apps.systask.scheduler import scheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger('apscheduler.scheduler')

# 告警检查任务ID前缀
ALERT_CHECK_JOB_PREFIX = 'alert_check_'
ALERT_SSL_CHECK_JOB_ID = 'alert_ssl_check'
ALERT_SSH_CHECK_JOB_ID = 'alert_ssh_check'
ALERT_PANEL_LOGIN_CHECK_JOB_ID = 'alert_panel_login_check'


def register_all_alert_tasks():
    """注册所有告警检查任务"""
    try:
        # 确保调度器已启动
        if not scheduler.running:
            scheduler.start()
        
        # 注册资源监控告警（5分钟）
        _register_resource_alert_task()
        
        # 注册SSL过期检查（每天）
        _register_ssl_check_task()
        
        # 注册SSH安全检测（5分钟）
        _register_ssh_check_task()
        
        # 注册面板登录检测（5分钟）
        _register_panel_login_check_task()
        
        logger.info("所有告警检查任务注册完成")
    except Exception as e:
        logger.error(f"注册告警检查任务失败: {e}")


def _register_resource_alert_task():
    """注册资源监控告警任务"""
    job_id = f"{ALERT_CHECK_JOB_PREFIX}resource"
    
    try:
        existing_job = scheduler.get_job(job_id)
        if existing_job:
            logger.info(f"资源告警任务已存在: {job_id}")
            return
        
        scheduler.add_job(
            func=check_resource_alert,
            trigger=IntervalTrigger(minutes=5),
            id=job_id,
            name='系统资源告警检查',
            replace_existing=True,
            misfire_grace_time=300
        )
        logger.info(f"资源告警任务注册成功")
    except Exception as e:
        logger.error(f"注册资源告警任务失败: {e}")


def _register_ssl_check_task():
    """注册SSL过期检查任务"""
    try:
        existing_job = scheduler.get_job(ALERT_SSL_CHECK_JOB_ID)
        if existing_job:
            logger.info(f"SSL检查任务已存在")
            return
        
        from apscheduler.triggers.cron import CronTrigger
        scheduler.add_job(
            func=check_ssl_expire,
            trigger=CronTrigger(hour=9, minute=0),  # 每天上午9点检查
            id=ALERT_SSL_CHECK_JOB_ID,
            name='SSL证书过期检查',
            replace_existing=True,
            misfire_grace_time=3600
        )
        logger.info(f"SSL检查任务注册成功")
    except Exception as e:
        logger.error(f"注册SSL检查任务失败: {e}")


def _register_ssh_check_task():
    """注册SSH安全检测任务"""
    try:
        existing_job = scheduler.get_job(ALERT_SSH_CHECK_JOB_ID)
        if existing_job:
            logger.info(f"SSH检查任务已存在")
            return
        
        scheduler.add_job(
            func=check_ssh_security,
            trigger=IntervalTrigger(minutes=5),
            id=ALERT_SSH_CHECK_JOB_ID,
            name='SSH安全检测',
            replace_existing=True,
            misfire_grace_time=300
        )
        logger.info(f"SSH检查任务注册成功")
    except Exception as e:
        logger.error(f"注册SSH检查任务失败: {e}")


def _register_panel_login_check_task():
    """注册面板登录检测任务"""
    try:
        existing_job = scheduler.get_job(ALERT_PANEL_LOGIN_CHECK_JOB_ID)
        if existing_job:
            logger.info(f"面板登录检查任务已存在")
            return
        
        scheduler.add_job(
            func=check_panel_login,
            trigger=IntervalTrigger(minutes=5),
            id=ALERT_PANEL_LOGIN_CHECK_JOB_ID,
            name='面板登录安全检测',
            replace_existing=True,
            misfire_grace_time=300
        )
        logger.info(f"面板登录检查任务注册成功")
    except Exception as e:
        logger.error(f"注册面板登录检查任务失败: {e}")


def check_resource_alert():
    """检查系统资源告警"""
    try:
        from .models import AlertTask
        from apps.sysmonitor.models import MonitorCpu, MonitorMemory, MonitorDiskIO
        
        # 获取启用的资源类告警任务
        resource_types = ['cpu_usage', 'mem_usage', 'disk_usage', 'disk_io', 'network_io', 'load_avg']
        tasks = AlertTask.objects.filter(task_type__in=resource_types, is_enabled=True)
        
        for task in tasks:
            try:
                config = task.get_config()
                threshold = config.get('threshold', 80)
                duration = config.get('duration', 5)
                
                if task.task_type == 'cpu_usage':
                    _check_cpu_alert(task, threshold, duration)
                elif task.task_type == 'mem_usage':
                    _check_memory_alert(task, threshold, duration)
                elif task.task_type == 'disk_usage':
                    _check_disk_alert(task, threshold)
                elif task.task_type == 'load_avg':
                    _check_load_alert(task, threshold)
                    
            except Exception as e:
                logger.error(f"检查资源告警任务失败 [{task.name}]: {e}")
                
    except Exception as e:
        logger.error(f"资源告警检查失败: {e}")


def _check_cpu_alert(task, threshold, duration):
    """检查CPU告警"""
    from apps.sysmonitor.models import MonitorCpu
    from .notify import send_alert
    
    # 获取最近N分钟的数据
    time_threshold = timezone.now() - timedelta(minutes=duration)
    records = MonitorCpu.objects.filter(record_time__gte=time_threshold).order_by('-record_time')
    
    if not records.exists():
        return
    
    # 检查是否持续超过阈值
    over_threshold_count = records.filter(usage_percent__gt=threshold).count()
    if over_threshold_count >= records.count() * 0.8:  # 80%的时间超过阈值
        avg_usage = records.aggregate(avg=models.Avg('usage_percent'))['avg']
        content = f"CPU使用率持续超过{threshold}%，当前平均使用率：{avg_usage:.1f}%"
        _trigger_alert(task, content)


def _check_memory_alert(task, threshold, duration):
    """检查内存告警"""
    from apps.sysmonitor.models import MonitorMemory
    
    time_threshold = timezone.now() - timedelta(minutes=duration)
    records = MonitorMemory.objects.filter(record_time__gte=time_threshold).order_by('-record_time')
    
    if not records.exists():
        return
    
    over_threshold_count = records.filter(usage_percent__gt=threshold).count()
    if over_threshold_count >= records.count() * 0.8:
        avg_usage = records.aggregate(avg=models.Avg('usage_percent'))['avg']
        content = f"内存使用率持续超过{threshold}%，当前平均使用率：{avg_usage:.1f}%"
        _trigger_alert(task, content)


def _check_disk_alert(task, threshold):
    """检查磁盘告警"""
    from utils.server.system import system
    
    try:
        disk_info = system.GetDiskInfo()
        for disk in disk_info:
            usage_percent = disk.get('usage_percent', 0)
            if usage_percent > threshold:
                path = disk.get('path', '/')
                content = f"磁盘 {path} 使用率超过{threshold}%，当前使用率：{usage_percent}%"
                _trigger_alert(task, content)
    except Exception as e:
        logger.error(f"检查磁盘告警失败: {e}")


def _check_load_alert(task, threshold):
    """检查系统负载告警"""
    import psutil
    
    try:
        load_avg = psutil.getloadavg()[0]  # 1分钟平均负载
        cpu_count = psutil.cpu_count()
        
        # 负载超过CPU核心数 * 阈值比例
        if load_avg > cpu_count * (threshold / 100):
            content = f"系统负载过高，当前负载：{load_avg:.2f}，CPU核心数：{cpu_count}"
            _trigger_alert(task, content)
    except Exception as e:
        logger.error(f"检查负载告警失败: {e}")


def check_ssl_expire():
    """检查SSL证书过期"""
    try:
        from .models import AlertTask
        from apps.system.models import Sites, SiteDomains
        from utils.sslPem import getCertInfo
        
        tasks = AlertTask.objects.filter(task_type='ssl_expire', is_enabled=True)
        
        for task in tasks:
            try:
                config = task.get_config()
                days_before = config.get('days_before', 15)
                site_ids = config.get('site_ids', [])  # 空列表表示所有站点
                
                if site_ids:
                    sites = Sites.objects.filter(id__in=site_ids)
                else:
                    sites = Sites.objects.all()
                
                for site in sites:
                    try:
                        sslcfg = site.sslcfg
                        if not sslcfg:
                            continue
                        
                        if isinstance(sslcfg, str):
                            import json
                            sslcfg = json.loads(sslcfg)
                        
                        cert_path = sslcfg.get('cert_path')
                        if not cert_path or not os.path.exists(cert_path):
                            continue
                        
                        # 获取证书信息
                        cert_info = getCertInfo(cert_path)
                        if not cert_info:
                            continue
                        
                        end_time = cert_info.get('endTime')
                        if not end_time:
                            continue
                        
                        # 计算剩余天数
                        days_left = (end_time - datetime.now()).days
                        
                        if days_left <= days_before:
                            domain = site.name or site.domains
                            content = f"站点 {domain} 的SSL证书将在 {days_left} 天后过期，请及时续签"
                            _trigger_alert(task, content)
                            
                    except Exception as e:
                        logger.error(f"检查站点SSL失败 [{site.name}]: {e}")
                        
            except Exception as e:
                logger.error(f"检查SSL告警任务失败 [{task.name}]: {e}")
                
    except Exception as e:
        logger.error(f"SSL过期检查失败: {e}")


def check_website_down():
    """检查网站宕机（由独立调度器按任务配置频率执行）"""
    try:
        from .models import AlertTask
        
        tasks = AlertTask.objects.filter(task_type__in=['site_down', 'site_slow'], is_enabled=True)
        
        for task in tasks:
            try:
                config = task.get_config()
                urls = config.get('urls', [])
                timeout = config.get('timeout', 10)
                
                for url in urls:
                    try:
                        start_time = datetime.now()
                        response = requests.get(url, timeout=timeout, allow_redirects=True)
                        response_time = (datetime.now() - start_time).total_seconds()
                        
                        # 检查宕机
                        if task.task_type == 'site_down':
                            if response.status_code >= 400:
                                content = f"网站 {url} 访问异常，状态码：{response.status_code}"
                                _trigger_alert(task, content)
                        
                        # 检查响应慢
                        elif task.task_type == 'site_slow':
                            slow_threshold = config.get('slow_threshold', 5)
                            if response_time > slow_threshold:
                                content = f"网站 {url} 响应缓慢，响应时间：{response_time:.2f}秒"
                                _trigger_alert(task, content)
                                
                    except requests.RequestException as e:
                        if task.task_type == 'site_down':
                            content = f"网站 {url} 无法访问，错误：{str(e)}"
                            _trigger_alert(task, content)
                            
            except Exception as e:
                logger.error(f"检查网站告警任务失败 [{task.name}]: {e}")
                
    except Exception as e:
        logger.error(f"网站宕机检查失败: {e}")


def check_ssh_security():
    """检查SSH安全"""
    try:
        from .models import AlertTask
        from utils.common import current_os
        
        if current_os == 'windows':
            return
        
        tasks = AlertTask.objects.filter(task_type__in=['ssh_fail', 'ssh_new_ip'], is_enabled=True)
        
        for task in tasks:
            try:
                config = task.get_config()
                
                if task.task_type == 'ssh_fail':
                    threshold = config.get('threshold', 5)
                    _check_ssh_fail(task, threshold)
                elif task.task_type == 'ssh_new_ip':
                    _check_ssh_new_ip(task)
                    
            except Exception as e:
                logger.error(f"检查SSH告警任务失败 [{task.name}]: {e}")
                
    except Exception as e:
        logger.error(f"SSH安全检测失败: {e}")


def _check_ssh_fail(task, threshold):
    """检查SSH登录失败"""
    try:
        # 分析 /var/log/secure 或 /var/log/auth.log
        log_files = ['/var/log/secure', '/var/log/auth.log']
        log_file = None
        
        for f in log_files:
            if os.path.exists(f):
                log_file = f
                break
        
        if not log_file:
            return
        
        # 读取最近5分钟的日志
        time_threshold = datetime.now() - timedelta(minutes=5)
        fail_count = 0
        
        with open(log_file, 'r') as f:
            for line in f:
                if 'Failed password' in line or 'authentication failure' in line:
                    fail_count += 1
        
        if fail_count >= threshold:
            content = f"检测到SSH登录失败 {fail_count} 次，可能存在暴力破解"
            _trigger_alert(task, content)
            
    except Exception as e:
        logger.error(f"检查SSH登录失败失败: {e}")


def _check_ssh_new_ip(task):
    """检查SSH新IP登录"""
    # 需要维护已知的IP白名单，检测到新IP时告警
    # 简化实现，实际需要记录历史登录IP
    pass


def check_panel_login():
    """检查面板登录安全"""
    try:
        from .models import AlertTask
        from apps.syslogs.models import OperationLog
        
        tasks = AlertTask.objects.filter(task_type='panel_login_fail', is_enabled=True)
        
        for task in tasks:
            try:
                config = task.get_config()
                threshold = config.get('threshold', 5)
                
                # 查询最近5分钟的登录失败记录
                time_threshold = timezone.now() - timedelta(minutes=5)
                fail_count = OperationLog.objects.filter(
                    create_at__gte=time_threshold,
                    module='login',
                    # 需要添加失败标记字段
                ).count()
                
                if fail_count >= threshold:
                    content = f"面板登录失败 {fail_count} 次，请检查是否存在暴力破解"
                    _trigger_alert(task, content)
                    
            except Exception as e:
                logger.error(f"检查面板登录告警任务失败 [{task.name}]: {e}")
                
    except Exception as e:
        logger.error(f"面板登录检测失败: {e}")


def check_cron_fail(task_id, error_msg):
    """检查定时任务失败（由任务系统调用）"""
    try:
        from .models import AlertTask
        
        tasks = AlertTask.objects.filter(task_type='cron_fail', is_enabled=True)
        
        for task in tasks:
            content = f"定时任务执行失败：{error_msg}"
            _trigger_alert(task, content)
            
    except Exception as e:
        logger.error(f"检查定时任务失败告警失败: {e}")


def _trigger_alert(task, content):
    """
    触发告警
    :param task: AlertTask 实例
    :param content: 告警内容
    """
    from .models import AlertLog
    from .notify import send_alert
    
    try:
        # 检查静默期
        if task.last_trigger:
            silence_end = task.last_trigger + timedelta(minutes=task.silence_minutes)
            if timezone.now() < silence_end:
                return  # 在静默期内，不发送
        
        # 发送通知
        results = send_alert(task, content)
        
        # 记录日志
        for success, response in results:
            AlertLog.objects.create(
                task=task,
                content=content,
                channels=task.channels,
                status=0 if success else 1,
                response=response[:500] if response else None
            )
        
        # 更新最后触发时间
        task.last_trigger = timezone.now()
        task.save(update_fields=['last_trigger'])
        
        logger.info(f"告警触发 [{task.name}]: {content}")
        
    except Exception as e:
        logger.error(f"触发告警失败 [{task.name}]: {e}")


def register_website_check_task(task_id, interval_seconds):
    """
    注册网站监控任务
    :param task_id: AlertTask ID
    :param interval_seconds: 检查间隔（秒）
    """
    job_id = f"{ALERT_CHECK_JOB_PREFIX}website_{task_id}"
    
    try:
        # 移除旧任务
        existing_job = scheduler.get_job(job_id)
        if existing_job:
            scheduler.remove_job(job_id)
        
        # 添加新任务
        scheduler.add_job(
            func=check_single_website,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=job_id,
            name=f'网站监控-{task_id}',
            args=[task_id],
            replace_existing=True,
            misfire_grace_time=60
        )
        logger.info(f"网站监控任务注册成功: {job_id}")
    except Exception as e:
        logger.error(f"注册网站监控任务失败 [{task_id}]: {e}")


def remove_website_check_task(task_id):
    """移除网站监控任务"""
    job_id = f"{ALERT_CHECK_JOB_PREFIX}website_{task_id}"
    try:
        existing_job = scheduler.get_job(job_id)
        if existing_job:
            scheduler.remove_job(job_id)
            logger.info(f"网站监控任务已移除: {job_id}")
    except Exception as e:
        logger.error(f"移除网站监控任务失败 [{task_id}]: {e}")


def check_single_website(task_id):
    """检查单个网站"""
    try:
        from .models import AlertTask
        
        task = AlertTask.objects.get(id=task_id, is_enabled=True)
        config = task.get_config()
        urls = config.get('urls', [])
        timeout = config.get('timeout', 10)
        
        for url in urls:
            try:
                start_time = datetime.now()
                response = requests.get(url, timeout=timeout, allow_redirects=True)
                response_time = (datetime.now() - start_time).total_seconds()
                
                # 检查宕机
                if task.task_type == 'site_down':
                    if response.status_code >= 400:
                        content = f"网站 {url} 访问异常，状态码：{response.status_code}"
                        _trigger_alert(task, content)
                
                # 检查响应慢
                elif task.task_type == 'site_slow':
                    slow_threshold = config.get('slow_threshold', 5)
                    if response_time > slow_threshold:
                        content = f"网站 {url} 响应缓慢，响应时间：{response_time:.2f}秒"
                        _trigger_alert(task, content)
                        
            except requests.RequestException as e:
                if task.task_type == 'site_down':
                    content = f"网站 {url} 无法访问，错误：{str(e)}"
                    _trigger_alert(task, content)
                    
    except AlertTask.DoesNotExist:
        # 任务不存在，移除调度
        remove_website_check_task(task_id)
    except Exception as e:
        logger.error(f"检查网站失败 [{task_id}]: {e}")
