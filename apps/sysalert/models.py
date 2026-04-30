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
import json

class AlertNotifyConfig(BaseModel):
    """
    告警通知渠道配置
    """
    CHANNEL_CHOICES = (
        ('email', '邮件'),
        ('dingtalk', '钉钉'),
        ('feishu', '飞书'),
        ('wechat', '企业微信'),
        ('sms', '短信'),
        ('webhook', 'Webhook'),
    )
    
    # Icon 类型选择
    ICON_TYPE_CHOICES = (
        ('icon', 'Element Plus 图标'),
        ('image', '图片'),
    )
    
    name = models.CharField(max_length=50, verbose_name='渠道名称')
    channel_type = models.CharField(max_length=20, choices=CHANNEL_CHOICES, verbose_name='渠道类型')
    config = models.TextField(verbose_name='配置JSON', default='{}')
    is_enabled = models.BooleanField(default=False, verbose_name='是否启用')
    # 发送限制配置
    daily_limit = models.IntegerField(default=3, verbose_name='每日发送上限')
    send_start_time = models.TimeField(default='00:00', verbose_name='允许发送开始时间')
    send_end_time = models.TimeField(default='23:59', verbose_name='允许发送结束时间')
    # 前端展示配置
    icon_type = models.CharField(max_length=10, choices=ICON_TYPE_CHOICES, default='icon', verbose_name='图标类型')
    icon = models.CharField(max_length=100, default='', verbose_name='图标名称或图片路径')
    icon_color = models.CharField(max_length=20, default='#409eff', verbose_name='图标颜色')
    
    class Meta:
        db_table = table_prefix + "alert_notify_config"
        verbose_name = '告警通知渠道'
        verbose_name_plural = verbose_name
        ordering = ('-id',)
        app_label = "sysalert"
    
    def get_config(self):
        """获取配置字典"""
        try:
            return json.loads(self.config)
        except:
            return {}
    
    def set_config(self, config_dict):
        """设置配置"""
        self.config = json.dumps(config_dict, ensure_ascii=False)


class AlertTask(BaseModel):
    """
    告警任务
    """
    TYPE_CHOICES = (
        # 系统资源
        ('cpu_usage', 'CPU使用率'),
        ('mem_usage', '内存使用率'),
        ('disk_usage', '磁盘使用率'),
        ('disk_io', '磁盘IO'),
        ('network_io', '网络流量'),
        ('load_avg', '系统负载'),
        # 网站SSL
        ('ssl_expire', 'SSL证书过期'),
        ('site_down', '网站宕机'),
        ('site_slow', '网站响应慢'),
        # 安全
        ('waf_attack', 'WAF攻击'),
        ('ssh_fail', 'SSH登录失败'),
        ('ssh_new_ip', 'SSH新IP登录'),
        ('panel_login_fail', '面板登录失败'),
        # 定时任务
        ('cron_fail', '定时任务失败'),
    )
    
    name = models.CharField(max_length=100, verbose_name='任务名称')
    task_type = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name='任务类型')
    config = models.TextField(verbose_name='任务配置JSON', default='{}')
    channels = models.TextField(verbose_name='通知渠道ID列表', help_text='逗号分隔')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    last_trigger = models.DateTimeField(null=True, blank=True, verbose_name='最近触发时间')
    silence_minutes = models.IntegerField(default=30, verbose_name='静默时间(分钟)')
    # 检查频率（仅部分类型可配置）
    check_interval = models.IntegerField(default=300, verbose_name='检查间隔(秒)', help_text='仅网站宕机类型可配置')
    
    class Meta:
        db_table = table_prefix + "alert_task"
        verbose_name = '告警任务'
        verbose_name_plural = verbose_name
        ordering = ('-id',)
        app_label = "sysalert"
    
    def get_config(self):
        """获取配置字典"""
        try:
            return json.loads(self.config)
        except:
            return {}
    
    def set_config(self, config_dict):
        """设置配置"""
        self.config = json.dumps(config_dict, ensure_ascii=False)
    
    def get_channel_ids(self):
        """获取渠道ID列表"""
        if not self.channels:
            return []
        return [int(x.strip()) for x in self.channels.split(',') if x.strip().isdigit()]


class AlertLog(BaseModel):
    """
    告警日志
    """
    STATUS_CHOICES = (
        (0, '成功'),
        (1, '失败'),
    )
    
    task = models.ForeignKey(AlertTask, on_delete=models.CASCADE, verbose_name='告警任务')
    content = models.TextField(verbose_name='告警内容')
    channels = models.TextField(verbose_name='实际发送渠道', help_text='逗号分隔')
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0, verbose_name='发送状态')
    response = models.TextField(null=True, blank=True, verbose_name='响应信息')
    
    class Meta:
        db_table = table_prefix + "alert_log"
        verbose_name = '告警日志'
        verbose_name_plural = verbose_name
        ordering = ('-create_at',)
        app_label = "sysalert"


class AlertDailyCounter(BaseModel):
    """
    每日告警发送计数
    用于控制每日发送上限
    """
    config = models.ForeignKey(AlertNotifyConfig, on_delete=models.CASCADE, verbose_name='通知渠道')
    date = models.DateField(verbose_name='日期')
    count = models.IntegerField(default=0, verbose_name='发送次数')
    
    class Meta:
        db_table = table_prefix + "alert_daily_counter"
        verbose_name = '每日发送计数'
        verbose_name_plural = verbose_name
        unique_together = ('config', 'date')
        app_label = "sysalert"
