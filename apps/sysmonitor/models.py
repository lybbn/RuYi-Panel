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

from django.db import models
from utils.models import table_prefix, BaseModel

class MonitorConfig(models.Model):
    """
    系统监控配置
    """
    is_enabled = models.BooleanField(default=False, verbose_name="监控开关")
    log_save_days = models.IntegerField(default=30, verbose_name="日志保存天数")
    log_path = models.CharField(max_length=255, verbose_name="日志存储路径", null=True, blank=True)
    collect_interval = models.IntegerField(default=60, verbose_name="采集间隔(秒)")
    # 网口过滤配置（JSON格式存储要监控的网卡列表，空列表表示监控所有）
    network_interfaces = models.TextField(verbose_name="监控网卡列表", null=True, blank=True, default='[]')
    # 磁盘过滤配置（JSON格式存储要监控的磁盘列表，空列表表示监控所有）
    disk_devices = models.TextField(verbose_name="监控磁盘列表", null=True, blank=True, default='[]')
    
    class Meta:
        db_table = table_prefix + "monitor_config"
        verbose_name = '监控配置'
        verbose_name_plural = verbose_name
        ordering = ('-id',)
        app_label = "sysmonitor"


class MonitorCpu(models.Model):
    """
    CPU监控历史数据
    """
    record_time = models.DateTimeField(verbose_name="记录时间", db_index=True)
    usage_percent = models.FloatField(default=0, verbose_name="CPU使用率(%)")
    cpu_count = models.IntegerField(default=0, verbose_name="CPU逻辑核心数")
    cpu_count_physical = models.IntegerField(default=0, verbose_name="CPU物理核心数")
    cpu_name = models.CharField(max_length=255, verbose_name="CPU名称", null=True, blank=True)
    # 进程信息 (JSON格式存储占用前5的进程)
    top_processes = models.TextField(verbose_name="Top进程列表", null=True, blank=True)
    
    class Meta:
        db_table = table_prefix + "monitor_cpu"
        verbose_name = 'CPU监控数据'
        verbose_name_plural = verbose_name
        ordering = ('-record_time',)
        app_label = "sysmonitor"
        indexes = [
            models.Index(fields=['record_time']),
        ]


class MonitorMemory(models.Model):
    """
    内存监控历史数据
    """
    record_time = models.DateTimeField(verbose_name="记录时间", db_index=True)
    usage_percent = models.FloatField(default=0, verbose_name="内存使用率(%)")
    mem_total = models.FloatField(default=0, verbose_name="内存总量(MB)")
    mem_used = models.FloatField(default=0, verbose_name="内存已用(MB)")
    mem_free = models.FloatField(default=0, verbose_name="内存空闲(MB)")
    mem_available = models.FloatField(default=0, verbose_name="内存可用(MB)")
    mem_buffers = models.FloatField(default=0, verbose_name="Buffers(MB)", null=True, blank=True)
    mem_cached = models.FloatField(default=0, verbose_name="Cached(MB)", null=True, blank=True)
    # 进程信息 (JSON格式存储占用前5的进程)
    top_processes = models.TextField(verbose_name="Top进程列表", null=True, blank=True)
    
    class Meta:
        db_table = table_prefix + "monitor_memory"
        verbose_name = '内存监控数据'
        verbose_name_plural = verbose_name
        ordering = ('-record_time',)
        app_label = "sysmonitor"
        indexes = [
            models.Index(fields=['record_time']),
        ]


class MonitorDiskIO(models.Model):
    """
    磁盘IO监控历史数据
    参考宝塔面板：存储每秒速率（差值计算）
    """
    record_time = models.DateTimeField(verbose_name="记录时间", db_index=True)
    disk_name = models.CharField(max_length=50, default='', verbose_name="磁盘名称", db_index=True)
    read_bytes = models.FloatField(default=0, verbose_name="读取速率(B/s)")
    write_bytes = models.FloatField(default=0, verbose_name="写入速率(B/s)")
    read_count = models.IntegerField(default=0, verbose_name="读取次数(次/s)")
    write_count = models.IntegerField(default=0, verbose_name="写入次数(次/s)")
    read_time = models.IntegerField(default=0, verbose_name="读取耗时(ms/s)")
    write_time = models.IntegerField(default=0, verbose_name="写入耗时(ms/s)")
    total_read_bytes = models.BigIntegerField(default=0, verbose_name="累计读取字节数")
    total_write_bytes = models.BigIntegerField(default=0, verbose_name="累计写入字节数")
    top_processes = models.TextField(verbose_name="Top进程列表", null=True, blank=True)
    
    class Meta:
        db_table = table_prefix + "monitor_disk_io"
        verbose_name = '磁盘IO监控数据'
        verbose_name_plural = verbose_name
        ordering = ('-record_time',)
        app_label = "sysmonitor"
        indexes = [
            models.Index(fields=['record_time']),
            models.Index(fields=['disk_name']),
        ]


class MonitorNetwork(models.Model):
    """
    网络流量监控历史数据
    参考宝塔面板：存储每秒速率（差值计算），支持多网卡
    """
    record_time = models.DateTimeField(verbose_name="记录时间", db_index=True)
    interface_name = models.CharField(max_length=50, default='', verbose_name="网卡名称", db_index=True)
    up_bytes = models.FloatField(default=0, verbose_name="上行速率(B/s)")
    up_packets = models.IntegerField(default=0, verbose_name="上行包数(个/s)")
    up_err = models.IntegerField(default=0, verbose_name="上行错误包数(个/s)")
    up_drop = models.IntegerField(default=0, verbose_name="上行丢弃包数(个/s)")
    down_bytes = models.FloatField(default=0, verbose_name="下行速率(B/s)")
    down_packets = models.IntegerField(default=0, verbose_name="下行包数(个/s)")
    down_err = models.IntegerField(default=0, verbose_name="下行错误包数(个/s)")
    down_drop = models.IntegerField(default=0, verbose_name="下行丢弃包数(个/s)")
    total_up_bytes = models.BigIntegerField(default=0, verbose_name="累计上行字节数")
    total_down_bytes = models.BigIntegerField(default=0, verbose_name="累计下行字节数")
    
    class Meta:
        db_table = table_prefix + "monitor_network"
        verbose_name = '网络监控数据'
        verbose_name_plural = verbose_name
        ordering = ('-record_time',)
        app_label = "sysmonitor"
        indexes = [
            models.Index(fields=['record_time']),
            models.Index(fields=['interface_name']),
        ]


class MonitorLoad(models.Model):
    """
    系统负载监控历史数据 (仅Linux)
    """
    record_time = models.DateTimeField(verbose_name="记录时间", db_index=True)
    load_one = models.FloatField(default=0, verbose_name="1分钟负载")
    load_five = models.FloatField(default=0, verbose_name="5分钟负载")
    load_fifteen = models.FloatField(default=0, verbose_name="15分钟负载")
    usage_percent = models.FloatField(default=0, verbose_name="负载使用率(%)")
    cpu_count = models.IntegerField(default=0, verbose_name="CPU核心数")
    top_processes = models.TextField(verbose_name="Top进程列表", null=True, blank=True)
    
    class Meta:
        db_table = table_prefix + "monitor_load"
        verbose_name = '系统负载监控数据'
        verbose_name_plural = verbose_name
        ordering = ('-record_time',)
        app_label = "sysmonitor"
        indexes = [
            models.Index(fields=['record_time']),
        ]
