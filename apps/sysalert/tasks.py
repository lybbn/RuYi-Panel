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
from django.db.models import Avg as DjangoAvg, Q
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
        
        # 注册WAF攻击尖峰检测（5分钟）
        _register_waf_attack_check_task()
        
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
                elif task.task_type == 'disk_io':
                    _check_disk_io_alert(task, threshold)
                elif task.task_type == 'network_io':
                    _check_network_io_alert(task, threshold)
                elif task.task_type == 'load_avg':
                    _check_load_alert(task, threshold)
                    
            except Exception as e:
                logger.error(f"检查资源告警任务失败 [{task.name}]: {e}")
                
    except Exception as e:
        logger.error(f"资源告警检查失败: {e}")


def _check_cpu_alert(task, threshold, duration):
    """检查CPU告警"""
    from apps.sysmonitor.models import MonitorCpu
    
    time_threshold = timezone.now() - timedelta(minutes=duration)
    records = MonitorCpu.objects.filter(record_time__gte=time_threshold).order_by('-record_time')
    
    if not records.exists():
        return
    
    over_threshold_count = records.filter(usage_percent__gt=threshold).count()
    is_over = over_threshold_count >= records.count() * 0.8
    
    if is_over:
        avg_usage = records.aggregate(avg=DjangoAvg('usage_percent'))['avg']
        content = f"CPU使用率持续超过{threshold}%，当前平均使用率：{avg_usage:.1f}%"
        _trigger_alert(task, content)
    elif task.is_alerting:
        avg_usage = records.aggregate(avg=DjangoAvg('usage_percent'))['avg']
        content = f"CPU使用率已恢复正常，当前平均使用率：{avg_usage:.1f}%"
        _trigger_recovery(task, content)


def _check_memory_alert(task, threshold, duration):
    """检查内存告警"""
    from apps.sysmonitor.models import MonitorMemory
    
    time_threshold = timezone.now() - timedelta(minutes=duration)
    records = MonitorMemory.objects.filter(record_time__gte=time_threshold).order_by('-record_time')
    
    if not records.exists():
        return
    
    over_threshold_count = records.filter(usage_percent__gt=threshold).count()
    is_over = over_threshold_count >= records.count() * 0.8
    
    if is_over:
        avg_usage = records.aggregate(avg=DjangoAvg('usage_percent'))['avg']
        content = f"内存使用率持续超过{threshold}%，当前平均使用率：{avg_usage:.1f}%"
        _trigger_alert(task, content)
    elif task.is_alerting:
        avg_usage = records.aggregate(avg=DjangoAvg('usage_percent'))['avg']
        content = f"内存使用率已恢复正常，当前平均使用率：{avg_usage:.1f}%"
        _trigger_recovery(task, content)


def _check_disk_alert(task, threshold):
    """检查磁盘告警"""
    from utils.server.system import system
    
    try:
        disk_info = system.GetDiskInfo()
        has_over = False
        over_disks = []
        for disk in disk_info:
            usage_percent = disk.get('usage_percent', 0)
            if usage_percent > threshold:
                has_over = True
                path = disk.get('path', '/')
                over_disks.append(f"{path}({usage_percent}%)")
        
        if has_over:
            content = f"以下磁盘使用率超过{threshold}%：{', '.join(over_disks)}"
            _trigger_alert(task, content)
        elif task.is_alerting:
            content = f"磁盘使用率已恢复正常，所有磁盘使用率均低于{threshold}%"
            _trigger_recovery(task, content)
    except Exception as e:
        logger.error(f"检查磁盘告警失败: {e}")


def _check_load_alert(task, threshold):
    """检查系统负载告警"""
    import psutil
    
    try:
        load_avg = psutil.getloadavg()[0]
        cpu_count = psutil.cpu_count()
        load_threshold = cpu_count * (threshold / 100)
        is_over = load_avg > load_threshold
        
        if is_over:
            content = f"系统负载过高，当前负载：{load_avg:.2f}，CPU核心数：{cpu_count}"
            _trigger_alert(task, content)
        elif task.is_alerting:
            content = f"系统负载已恢复正常，当前负载：{load_avg:.2f}，CPU核心数：{cpu_count}"
            _trigger_recovery(task, content)
    except Exception as e:
        logger.error(f"检查负载告警失败: {e}")


def _check_disk_io_alert(task, threshold):
    """检查磁盘IO告警（使用MonitorDiskIO速率数据）"""
    from apps.sysmonitor.models import MonitorDiskIO
    
    try:
        time_threshold = timezone.now() - timedelta(minutes=5)
        records = MonitorDiskIO.objects.filter(record_time__gte=time_threshold).order_by('-record_time')
        
        if not records.exists():
            return
        
        avg_read = records.aggregate(avg=DjangoAvg('read_bytes'))['avg'] or 0
        avg_write = records.aggregate(avg=DjangoAvg('write_bytes'))['avg'] or 0
        avg_total_mbps = (avg_read + avg_write) / (1024 * 1024)
        
        if avg_total_mbps > threshold:
            content = f"磁盘IO过高，最近5分钟平均读写速率：{avg_total_mbps:.1f}MB/s，阈值：{threshold}MB/s"
            _trigger_alert(task, content)
        elif task.is_alerting:
            content = f"磁盘IO已恢复正常，当前平均读写速率：{avg_total_mbps:.1f}MB/s"
            _trigger_recovery(task, content)
    except Exception as e:
        logger.error(f"检查磁盘IO告警失败: {e}")


def _check_network_io_alert(task, threshold):
    """检查网络流量告警（使用MonitorNetwork速率数据）"""
    from apps.sysmonitor.models import MonitorNetwork
    
    try:
        time_threshold = timezone.now() - timedelta(minutes=5)
        records = MonitorNetwork.objects.filter(record_time__gte=time_threshold).order_by('-record_time')
        
        if not records.exists():
            return
        
        avg_up = records.aggregate(avg=DjangoAvg('up_bytes'))['avg'] or 0
        avg_down = records.aggregate(avg=DjangoAvg('down_bytes'))['avg'] or 0
        avg_total_mbps = (avg_up + avg_down) / (1024 * 1024)
        
        if avg_total_mbps > threshold:
            content = f"网络流量过高，最近5分钟平均速率：{avg_total_mbps:.1f}MB/s，阈值：{threshold}MB/s"
            _trigger_alert(task, content)
        elif task.is_alerting:
            content = f"网络流量已恢复正常，当前平均速率：{avg_total_mbps:.1f}MB/s"
            _trigger_recovery(task, content)
    except Exception as e:
        logger.error(f"检查网络流量告警失败: {e}")


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
        log_files = ['/var/log/secure', '/var/log/auth.log']
        log_file = None
        
        for f in log_files:
            if os.path.exists(f):
                log_file = f
                break
        
        if not log_file:
            return
        
        time_threshold = datetime.now() - timedelta(minutes=5)
        fail_count = 0
        
        with open(log_file, 'r') as f:
            for line in f:
                if 'Failed password' in line or 'authentication failure' in line:
                    line_time = _parse_syslog_time(line)
                    if line_time and line_time >= time_threshold:
                        fail_count += 1
                    elif not line_time:
                        fail_count += 1
        
        if fail_count >= threshold:
            content = f"检测到SSH登录失败 {fail_count} 次，可能存在暴力破解"
            _trigger_alert(task, content)
        elif task.is_alerting:
            content = f"SSH登录失败次数已恢复正常，最近5分钟失败 {fail_count} 次"
            _trigger_recovery(task, content)
            
    except Exception as e:
        logger.error(f"检查SSH登录失败失败: {e}")


def _parse_syslog_time(line):
    """解析syslog行的时间戳"""
    try:
        current_year = datetime.now().year
        if re.match(r'^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', line):
            time_str = line[:15]
            return datetime.strptime(f"{current_year} {time_str}", "%Y %b %d %H:%M:%S")
        elif re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', line):
            time_str = line[:19]
            return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        pass
    return None


def _check_ssh_new_ip(task):
    """检查SSH新IP登录"""
    try:
        from .models import AlertNotifyConfig
        
        config = task.get_config()
        known_ips = config.get('known_ips', [])
        
        log_files = ['/var/log/secure', '/var/log/auth.log']
        log_file = None
        
        for f in log_files:
            if os.path.exists(f):
                log_file = f
                break
        
        if not log_file:
            return
        
        time_threshold = datetime.now() - timedelta(minutes=5)
        new_ips = set()
        
        with open(log_file, 'r') as f:
            for line in f:
                if 'Accepted password' in line or 'Accepted publickey' in line:
                    line_time = _parse_syslog_time(line)
                    if line_time and line_time < time_threshold:
                        continue
                    
                    ip_match = re.search(r'from\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    if ip_match:
                        ip = ip_match.group(1)
                        if known_ips and ip not in known_ips:
                            new_ips.add(ip)
        
        if new_ips:
            content = f"检测到新IP通过SSH登录：{', '.join(new_ips)}，请确认是否为授权访问"
            _trigger_alert(task, content)
        elif task.is_alerting:
            content = "SSH新IP登录告警已解除，最近5分钟无异常IP登录"
            _trigger_recovery(task, content)
    except Exception as e:
        logger.error(f"检查SSH新IP登录失败: {e}")


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
                
                time_threshold = timezone.now() - timedelta(minutes=5)
                fail_count = OperationLog.objects.filter(
                    create_at__gte=time_threshold,
                    module='login',
                    status__in=['fail', 'failed', 0, False],
                ).count()
                
                if fail_count >= threshold:
                    content = f"面板登录失败 {fail_count} 次，请检查是否存在暴力破解"
                    _trigger_alert(task, content)
                elif task.is_alerting:
                    content = f"面板登录失败次数已恢复正常，最近5分钟失败 {fail_count} 次"
                    _trigger_recovery(task, content)
                    
            except Exception as e:
                logger.error(f"检查面板登录告警任务失败 [{task.name}]: {e}")
                
    except Exception as e:
        logger.error(f"面板登录检测失败: {e}")


def check_cron_fail(error_msg):
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
        
        # 检查任务级别每日推送上限
        today = timezone.now().date()
        today_count = AlertLog.objects.filter(task=task, create_at__date=today, status=0).count()
        if task.push_count > 0 and today_count >= task.push_count:
            return  # 已达到今日推送上限
        
        # 发送通知
        results = send_alert(task, content)
        
        # 记录日志（每条日志对应一个实际发送渠道）
        for success, response, channel_name, channel_type in results:
            AlertLog.objects.create(
                task=task,
                content=content,
                channels=channel_name or task.channels,
                channel_type=channel_type,
                status=0 if success else 1,
                response=response[:500] if response else None
            )
        
        # 更新最后触发时间
        task.last_trigger = timezone.now()
        task.is_alerting = True
        task.save(update_fields=['last_trigger', 'is_alerting'])
        
        logger.info(f"告警触发 [{task.name}]: {content}")
        
    except Exception as e:
        logger.error(f"触发告警失败 [{task.name}]: {e}")


def _trigger_recovery(task, content):
    """
    触发告警恢复通知
    :param task: AlertTask 实例
    :param content: 恢复内容
    """
    from .models import AlertLog
    from .notify import send_alert
    
    try:
        today = timezone.now().date()
        today_count = AlertLog.objects.filter(task=task, create_at__date=today, status=0).count()
        if task.push_count > 0 and today_count >= task.push_count:
            logger.info(f"告警恢复 [{task.name}]: 已达今日推送上限，跳过恢复通知")
            task.is_alerting = False
            task.save(update_fields=['is_alerting'])
            return
        
        results = send_alert(task, content)
        
        for success, response, channel_name, channel_type in results:
            AlertLog.objects.create(
                task=task,
                content=content,
                channels=channel_name or task.channels,
                channel_type=channel_type,
                status=0 if success else 1,
                response=response[:500] if response else None
            )
        
        task.is_alerting = False
        task.last_trigger = timezone.now()
        task.save(update_fields=['is_alerting', 'last_trigger'])
        
        logger.info(f"告警恢复 [{task.name}]: {content}")
        
    except Exception as e:
        logger.error(f"触发恢复通知失败 [{task.name}]: {e}")


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
        slow_threshold = config.get('slow_threshold', 5)
        
        has_alert = False
        alert_contents = []
        recovery_contents = []
        
        for url in urls:
            try:
                start_time = datetime.now()
                response = requests.get(url, timeout=timeout, allow_redirects=True)
                response_time = (datetime.now() - start_time).total_seconds()
                
                if task.task_type == 'site_down':
                    if response.status_code >= 400:
                        has_alert = True
                        alert_contents.append(f"网站 {url} 访问异常，状态码：{response.status_code}")
                    elif task.is_alerting:
                        recovery_contents.append(f"网站 {url} 已恢复正常，状态码：{response.status_code}")
                
                elif task.task_type == 'site_slow':
                    if response_time > slow_threshold:
                        has_alert = True
                        alert_contents.append(f"网站 {url} 响应缓慢，响应时间：{response_time:.2f}秒")
                    elif task.is_alerting:
                        recovery_contents.append(f"网站 {url} 响应已恢复正常，响应时间：{response_time:.2f}秒")
                        
            except requests.RequestException as e:
                if task.task_type == 'site_down':
                    has_alert = True
                    alert_contents.append(f"网站 {url} 无法访问，错误：{str(e)}")
                elif task.task_type == 'site_slow' and task.is_alerting:
                    pass
        
        if has_alert:
            _trigger_alert(task, '；'.join(alert_contents))
        elif task.is_alerting and recovery_contents:
            _trigger_recovery(task, '；'.join(recovery_contents))
                    
    except AlertTask.DoesNotExist:
        remove_website_check_task(task_id)
    except Exception as e:
        logger.error(f"检查网站失败 [{task_id}]: {e}")


ALERT_WAF_CHECK_JOB_ID = 'alert_waf_attack_check'


def _register_waf_attack_check_task():
    """注册WAF攻击尖峰检测任务"""
    try:
        existing_job = scheduler.get_job(ALERT_WAF_CHECK_JOB_ID)
        if existing_job:
            logger.info(f"WAF攻击检测任务已存在")
            return

        scheduler.add_job(
            func=check_waf_attack,
            trigger=IntervalTrigger(minutes=5),
            id=ALERT_WAF_CHECK_JOB_ID,
            name='WAF攻击尖峰检测',
            replace_existing=True,
            misfire_grace_time=300
        )
        logger.info(f"WAF攻击检测任务注册成功")
    except Exception as e:
        logger.error(f"注册WAF攻击检测任务失败: {e}")


def check_waf_attack():
    """
    检查WAF攻击尖峰
    逻辑：每5分钟检查一次，统计5分钟内达到最低告警级别的攻击数量，
    超过阈值（默认10次）则通过sysalert发送通知
    """
    try:
        from apps.syswaf.models import WafGlobalConfig, WafAttackLog

        global_config = WafGlobalConfig.get_instance()
        if not global_config.alert_enabled:
            return

        # 确定严重级别过滤
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        min_severity = global_config.alert_min_severity or 'high'
        min_order = severity_order.get(min_severity, 1)
        severity_levels = [k for k, v in severity_order.items() if v <= min_order]

        # 统计最近5分钟的攻击数量
        time_threshold = timezone.now() - timedelta(minutes=5)
        attack_count = WafAttackLog.objects.filter(
            create_at__gte=time_threshold,
            severity__in=severity_levels
        ).count()

        # 阈值：5分钟内达到10次攻击即触发
        threshold = 10

        from .models import AlertTask
        task = AlertTask.objects.filter(task_type='waf_attack', is_enabled=True).first()

        if attack_count >= threshold:
            if not task:
                return  # 没有配置告警任务，不发送
            content = f"检测到WAF攻击尖峰：最近5分钟内共 {attack_count} 次攻击（级别≥{dict(WafGlobalConfig.SEVERITY_CHOICES).get(min_severity, min_severity)}），请及时查看"
            _trigger_alert(task, content)
        elif task and task.is_alerting:
            content = f"WAF攻击已趋于平缓，最近5分钟内 {attack_count} 次攻击"
            _trigger_recovery(task, content)

    except Exception as e:
        logger.error(f"WAF攻击检测失败: {e}")
