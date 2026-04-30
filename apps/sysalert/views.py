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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone
from utils.jsonResponse import SuccessResponse, ErrorResponse, DetailResponse
from utils.customView import CustomAPIView
from utils.common import get_parameter_dic, current_os
from utils.pagination import CustomPagination
from .models import AlertNotifyConfig, AlertTask, AlertLog
from .notify import AlertNotifier
from .tasks import register_website_check_task, remove_website_check_task
import json
import logging

logger = logging.getLogger('apscheduler.scheduler')


class AlertNotifyConfigListView(CustomAPIView):
    """
    告警通知渠道列表
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取通知渠道列表"""
        configs = AlertNotifyConfig.objects.all().order_by('id')
        result = []
        for config in configs:
            item = {
                'id': config.id,
                'name': config.name,
                'channel_type': config.channel_type,
                'channel_type_name': config.get_channel_type_display(),
                'is_enabled': config.is_enabled,
                'daily_limit': config.daily_limit,
                'send_start_time': config.send_start_time.strftime('%H:%M'),
                'send_end_time': config.send_end_time.strftime('%H:%M'),
                'config': config.get_config(),
                'icon_type': config.icon_type,
                'icon': config.icon,
                'icon_color': config.icon_color,
                'create_at': config.create_at.strftime('%Y-%m-%d %H:%M:%S') if config.create_at else None,
            }
            result.append(item)
        return DetailResponse(data=result)
    
    def post(self, request):
        """创建通知渠道"""
        data = request.data
        
        name = data.get('name')
        channel_type = data.get('channel_type')
        config_dict = data.get('config', {})
        is_enabled = data.get('is_enabled', False)
        daily_limit = data.get('daily_limit', 3)
        send_start_time = data.get('send_start_time', '00:00')
        send_end_time = data.get('send_end_time', '23:59')
        
        if not name or not channel_type:
            return ErrorResponse(msg='名称和渠道类型不能为空')
        
        try:
            config = AlertNotifyConfig.objects.create(
                name=name,
                channel_type=channel_type,
                is_enabled=is_enabled,
                daily_limit=daily_limit,
                send_start_time=send_start_time,
                send_end_time=send_end_time,
            )
            config.set_config(config_dict)
            config.save()
            return SuccessResponse(msg='创建成功')
        except Exception as e:
            return ErrorResponse(msg=f'创建失败: {str(e)}')

class AlertNotifyConfigDetailView(CustomAPIView):
    """
    告警通知渠道详情
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """获取渠道详情"""
        try:
            config = AlertNotifyConfig.objects.get(pk=pk)
            data = {
                'id': config.id,
                'name': config.name,
                'channel_type': config.channel_type,
                'channel_type_name': config.get_channel_type_display(),
                'is_enabled': config.is_enabled,
                'daily_limit': config.daily_limit,
                'send_start_time': config.send_start_time.strftime('%H:%M'),
                'send_end_time': config.send_end_time.strftime('%H:%M'),
                'config': config.get_config(),
            }
            return DetailResponse(data=data)
        except AlertNotifyConfig.DoesNotExist:
            return ErrorResponse(msg='配置不存在')
    
    def put(self, request, pk):
        """更新通知渠道"""
        try:
            config = AlertNotifyConfig.objects.get(pk=pk)
            data = request.data
            
            config.name = data.get('name', config.name)
            config.is_enabled = data.get('is_enabled', config.is_enabled)
            config.daily_limit = data.get('daily_limit', config.daily_limit)
            config.send_start_time = data.get('send_start_time', config.send_start_time)
            config.send_end_time = data.get('send_end_time', config.send_end_time)
            
            if 'config' in data:
                config.set_config(data['config'])
            
            config.save()
            return SuccessResponse(msg='更新成功')
        except AlertNotifyConfig.DoesNotExist:
            return ErrorResponse(msg='配置不存在')
        except Exception as e:
            return ErrorResponse(msg=f'更新失败: {str(e)}')
    
    def delete(self, request, pk):
        """删除通知渠道"""
        try:
            config = AlertNotifyConfig.objects.get(pk=pk)
            config.delete()
            return SuccessResponse(msg='删除成功')
        except AlertNotifyConfig.DoesNotExist:
            return ErrorResponse(msg='配置不存在')


class AlertNotifyConfigTestView(CustomAPIView):
    """
    测试通知渠道
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """测试发送"""
        try:
            config = AlertNotifyConfig.objects.get(pk=pk)
            success, response = AlertNotifier.send(
                config,
                '测试告警',
                '这是一条测试告警消息，如果您收到此消息，说明通知渠道配置正确。'
            )
            
            if success:
                return SuccessResponse(msg=f'测试发送成功: {response}')
            else:
                return ErrorResponse(msg=f'测试发送失败: {response}')
                
        except AlertNotifyConfig.DoesNotExist:
            return ErrorResponse(msg='配置不存在')
        except Exception as e:
            return ErrorResponse(msg=f'测试失败: {str(e)}')


class AlertNotifyConfigToggleView(CustomAPIView):
    """
    切换通知渠道启用状态
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """切换启用状态"""
        try:
            config = AlertNotifyConfig.objects.get(pk=pk)
            config.is_enabled = not config.is_enabled
            config.save(update_fields=['is_enabled'])
            return SuccessResponse(
                msg='已启用' if config.is_enabled else '已禁用',
                data={'is_enabled': config.is_enabled}
            )
        except AlertNotifyConfig.DoesNotExist:
            return ErrorResponse(msg='配置不存在')


class AlertTaskListView(CustomAPIView):
    """
    告警任务列表
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取任务列表"""
        params = get_parameter_dic(request)
        keyword = params.get('keyword', '')
        task_type = params.get('type', '')
        
        queryset = AlertTask.objects.all().order_by('-id')
        
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        if task_type:
            queryset = queryset.filter(task_type=task_type)
        
        page_obj = CustomPagination()
        page_data = page_obj.paginate_queryset(queryset, request)
        
        result = []
        for task in page_data:
            channel_ids = task.get_channel_ids()
            channels = AlertNotifyConfig.objects.filter(id__in=channel_ids)
            channel_names = [c.name for c in channels]
            
            item = {
                'id': task.id,
                'name': task.name,
                'task_type': task.task_type,
                'task_type_name': task.get_task_type_display(),
                'is_enabled': task.is_enabled,
                'channels': channel_ids,
                'channel_names': channel_names,
                'silence_minutes': task.silence_minutes,
                'check_interval': task.check_interval,
                'last_trigger': task.last_trigger.strftime('%Y-%m-%d %H:%M:%S') if task.last_trigger else None,
                'config': task.get_config(),
                'create_at': task.create_at.strftime('%Y-%m-%d %H:%M:%S') if task.create_at else None,
            }
            result.append(item)
        
        return page_obj.get_paginated_response(result)
    
    def post(self, request):
        """创建告警任务"""
        data = request.data
        
        name = data.get('name')
        task_type = data.get('task_type')
        channels = data.get('channels', [])
        config = data.get('config', {})
        silence_minutes = data.get('silence_minutes', 30)
        check_interval = data.get('check_interval', 300)
        is_enabled = data.get('is_enabled', True)
        
        if not name or not task_type:
            return ErrorResponse(msg='任务名称和类型不能为空')
        
        try:
            task = AlertTask.objects.create(
                name=name,
                task_type=task_type,
                channels=','.join(map(str, channels)) if channels else '',
                silence_minutes=silence_minutes,
                check_interval=check_interval,
                is_enabled=is_enabled,
            )
            task.set_config(config)
            task.save()
            
            # 如果是网站监控任务，注册定时器
            if task_type in ['site_down', 'site_slow'] and is_enabled:
                register_website_check_task(task.id, check_interval)
            
            return SuccessResponse(msg='创建成功')
        except Exception as e:
            return ErrorResponse(msg=f'创建失败: {str(e)}')


class AlertTaskDetailView(CustomAPIView):
    """
    告警任务详情
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """获取任务详情"""
        try:
            task = AlertTask.objects.get(pk=pk)
            channel_ids = task.get_channel_ids()
            channels = AlertNotifyConfig.objects.filter(id__in=channel_ids)
            channel_names = [c.name for c in channels]
            
            data = {
                'id': task.id,
                'name': task.name,
                'task_type': task.task_type,
                'task_type_name': task.get_task_type_display(),
                'is_enabled': task.is_enabled,
                'channels': channel_ids,
                'channel_names': channel_names,
                'silence_minutes': task.silence_minutes,
                'check_interval': task.check_interval,
                'last_trigger': task.last_trigger.strftime('%Y-%m-%d %H:%M:%S') if task.last_trigger else None,
                'config': task.get_config(),
            }
            return DetailResponse(data=data)
        except AlertTask.DoesNotExist:
            return ErrorResponse(msg='任务不存在')
    
    def put(self, request, pk):
        """更新告警任务"""
        try:
            task = AlertTask.objects.get(pk=pk)
            data = request.data
            
            old_enabled = task.is_enabled
            old_interval = task.check_interval
            old_type = task.task_type
            
            task.name = data.get('name', task.name)
            task.is_enabled = data.get('is_enabled', task.is_enabled)
            task.silence_minutes = data.get('silence_minutes', task.silence_minutes)
            task.check_interval = data.get('check_interval', task.check_interval)
            
            if 'channels' in data:
                task.channels = ','.join(map(str, data['channels'])) if data['channels'] else ''
            if 'config' in data:
                task.set_config(data['config'])
            
            task.save()
            
            # 处理网站监控任务的定时器
            if task.task_type in ['site_down', 'site_slow']:
                if task.is_enabled:
                    # 如果启用状态或间隔变化，重新注册
                    if not old_enabled or old_interval != task.check_interval:
                        register_website_check_task(task.id, task.check_interval)
                else:
                    # 如果禁用，移除定时器
                    remove_website_check_task(task.id)
            
            return SuccessResponse(msg='更新成功')
        except AlertTask.DoesNotExist:
            return ErrorResponse(msg='任务不存在')
        except Exception as e:
            return ErrorResponse(msg=f'更新失败: {str(e)}')
    
    def delete(self, request, pk):
        """删除告警任务"""
        try:
            task = AlertTask.objects.get(pk=pk)
            
            # 移除网站监控定时器
            if task.task_type in ['site_down', 'site_slow']:
                remove_website_check_task(task.id)
            
            task.delete()
            return SuccessResponse(msg='删除成功')
        except AlertTask.DoesNotExist:
            return ErrorResponse(msg='任务不存在')


class AlertTaskToggleView(CustomAPIView):
    """
    切换告警任务启用状态
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        """切换启用状态"""
        try:
            task = AlertTask.objects.get(pk=pk)
            task.is_enabled = not task.is_enabled
            task.save(update_fields=['is_enabled'])
            
            # 处理网站监控定时器
            if task.task_type in ['site_down', 'site_slow']:
                if task.is_enabled:
                    register_website_check_task(task.id, task.check_interval)
                else:
                    remove_website_check_task(task.id)
            
            return SuccessResponse(
                msg='已启用' if task.is_enabled else '已禁用',
                data={'is_enabled': task.is_enabled}
            )
        except AlertTask.DoesNotExist:
            return ErrorResponse(msg='任务不存在')


class AlertLogListView(CustomAPIView):
    """
    告警日志列表
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取日志列表"""
        params = get_parameter_dic(request)
        task_type = params.get('type', '')
        status_str = params.get('status', '')
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        queryset = AlertLog.objects.all().order_by('-create_at')
        
        if task_type:
            queryset = queryset.filter(task__task_type=task_type)
        if status_str != '':
            try:
                status = int(status_str)
                queryset = queryset.filter(status=status)
            except (ValueError, TypeError):
                pass
        if start_date:
            queryset = queryset.filter(create_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(create_at__lte=end_date)
        
        page_obj = CustomPagination()
        page_data = page_obj.paginate_queryset(queryset, request)
        
        result = []
        for log in page_data:
            item = {
                'id': log.id,
                'task_id': log.task_id,
                'task_name': log.task.name if log.task else '-',
                'task_type': log.task.task_type if log.task else '-',
                'task_type_name': log.task.get_task_type_display() if log.task else '-',
                'content': log.content,
                'channels': log.channels,
                'status': log.status,
                'status_name': '成功' if log.status == 0 else '失败',
                'response': log.response,
                'create_at': log.create_at.strftime('%Y-%m-%d %H:%M:%S') if log.create_at else None,
            }
            result.append(item)
        
        return page_obj.get_paginated_response(result)


class AlertLogDetailView(CustomAPIView):
    """
    告警日志详情
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        """获取日志详情"""
        try:
            log = AlertLog.objects.get(pk=pk)
            data = {
                'id': log.id,
                'task_id': log.task_id,
                'task_name': log.task.name if log.task else '-',
                'task_type': log.task.task_type if log.task else '-',
                'task_type_name': log.task.get_task_type_display() if log.task else '-',
                'content': log.content,
                'channels': log.channels,
                'status': log.status,
                'status_name': '成功' if log.status == 0 else '失败',
                'response': log.response,
                'create_at': log.create_at.strftime('%Y-%m-%d %H:%M:%S') if log.create_at else None,
            }
            return DetailResponse(data=data)
        except AlertLog.DoesNotExist:
            return ErrorResponse(msg='日志不存在')


class AlertLogClearView(CustomAPIView):
    """
    清空告警日志
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """清理过期日志"""
        try:
            days = request.data.get('days', 30)
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            deleted_count, _ = AlertLog.objects.filter(create_at__lt=cutoff_date).delete()
            return SuccessResponse(msg=f'已清理 {deleted_count} 条日志')
        except Exception as e:
            return ErrorResponse(msg=f'清理失败: {str(e)}')


class AlertTaskTypeListView(CustomAPIView):
    """
    告警任务类型列表
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取任务类型列表"""
        types = [
            {'value': 'cpu_usage', 'label': 'CPU使用率', 'category': 'system', 'icon': 'Cpu'},
            {'value': 'mem_usage', 'label': '内存使用率', 'category': 'system', 'icon': 'Coin'},
            {'value': 'disk_usage', 'label': '磁盘使用率', 'category': 'system', 'icon': 'Folder'},
            {'value': 'disk_io', 'label': '磁盘IO', 'category': 'system', 'icon': 'DataLine'},
            {'value': 'network_io', 'label': '网络流量', 'category': 'system', 'icon': 'Connection'},
            {'value': 'load_avg', 'label': '系统负载', 'category': 'system', 'icon': 'Odometer'},
            {'value': 'ssl_expire', 'label': 'SSL证书过期', 'category': 'website', 'icon': 'Document'},
            {'value': 'site_down', 'label': '网站宕机', 'category': 'website', 'icon': 'Link'},
            {'value': 'site_slow', 'label': '网站响应慢', 'category': 'website', 'icon': 'Timer'},
            {'value': 'waf_attack', 'label': 'WAF攻击', 'category': 'security', 'icon': 'Shield'},
            {'value': 'ssh_fail', 'label': 'SSH登录失败', 'category': 'security', 'icon': 'Lock'},
            {'value': 'ssh_new_ip', 'label': 'SSH新IP登录', 'category': 'security', 'icon': 'User'},
            {'value': 'panel_login_fail', 'label': '面板登录失败', 'category': 'security', 'icon': 'Key'},
            {'value': 'cron_fail', 'label': '定时任务失败', 'category': 'task', 'icon': 'Clock'},
        ]
        return DetailResponse(data=types)


class AlertChannelTypeListView(CustomAPIView):
    """
    通知渠道类型列表
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取渠道类型列表"""
        types = [
            {'value': 'email', 'label': '邮件', 'icon': 'Message'},
            {'value': 'dingtalk', 'label': '钉钉', 'icon': 'img:dingding.png'},
            {'value': 'feishu', 'label': '飞书', 'icon': 'img:feishu.png'},
            {'value': 'wechat', 'label': '企业微信', 'icon': 'img:qiyeweixin.png'},
            {'value': 'sms', 'label': '短信', 'icon': 'Phone'},
            {'value': 'webhook', 'label': 'Webhook', 'icon': 'Link'},
        ]
        return DetailResponse(data=types)


class AlertDashboardStatsView(CustomAPIView):
    """
    告警仪表盘统计
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取统计数据"""
        try:
            from datetime import datetime, timedelta
            
            # 今日告警数
            today = datetime.now().date()
            today_count = AlertLog.objects.filter(
                create_at__date=today
            ).count()
            
            # 本周告警数
            week_ago = datetime.now() - timedelta(days=7)
            week_count = AlertLog.objects.filter(
                create_at__gte=week_ago
            ).count()
            
            # 启用中的任务数
            active_tasks = AlertTask.objects.filter(is_enabled=True).count()
            
            # 启用中的渠道数
            active_channels = AlertNotifyConfig.objects.filter(is_enabled=True).count()
            
            # 最近7天告警趋势
            trend = []
            for i in range(6, -1, -1):
                date = datetime.now().date() - timedelta(days=i)
                count = AlertLog.objects.filter(create_at__date=date).count()
                trend.append({
                    'date': date.strftime('%m-%d'),
                    'count': count
                })
            
            # 告警类型分布
            type_distribution = []
            for task_type, task_name in AlertTask.TYPE_CHOICES:
                count = AlertLog.objects.filter(task__task_type=task_type).count()
                if count > 0:
                    type_distribution.append({
                        'type': task_type,
                        'name': task_name,
                        'count': count
                    })
            
            data = {
                'today_count': today_count,
                'week_count': week_count,
                'active_tasks': active_tasks,
                'active_channels': active_channels,
                'trend': trend,
                'type_distribution': type_distribution,
            }
            return DetailResponse(data=data)
        except Exception as e:
            return ErrorResponse(msg=f'获取统计失败: {str(e)}')
