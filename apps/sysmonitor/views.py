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
# 系统监控类视图
# ------------------------------

import os
import json
import time
import psutil
import platform
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from utils.jsonResponse import SuccessResponse, ErrorResponse, DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.server.system import system
from django.conf import settings
from apps.sysmonitor.models import (
    MonitorConfig, MonitorCpu, MonitorMemory, MonitorDiskIO,
    MonitorNetwork, MonitorLoad
)

plat = platform.system().lower()


class MonitorConfigView(CustomAPIView):
    """
    系统监控配置
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取监控配置"""
        config = MonitorConfig.objects.first()
        if not config:
            config = MonitorConfig.objects.create(
                is_enabled=True,
                log_save_days=30,
                collect_interval=60
            )
        
        # 计算日志占用大小（计算monitor数据库文件大小）
        log_size = 0
        try:
            db_config = settings.DATABASES.get('monitor')
            if db_config and db_config['ENGINE'] == 'django.db.backends.sqlite3':
                db_path = db_config['NAME']
                if os.path.exists(db_path):
                    log_size = os.path.getsize(db_path)
        except Exception as e:
            print(f"计算监控数据库大小失败: {e}")
        
        # 解析网卡和磁盘过滤配置
        network_interfaces = []
        disk_devices = []
        try:
            if config.network_interfaces:
                network_interfaces = json.loads(config.network_interfaces)
        except:
            network_interfaces = []
        try:
            if config.disk_devices:
                disk_devices = json.loads(config.disk_devices)
        except:
            disk_devices = []
        
        data = {
            'id': config.id,
            'is_enabled': config.is_enabled,
            'log_save_days': config.log_save_days,
            'collect_interval': config.collect_interval,
            'log_size': log_size,
            'log_size_human': self._format_bytes(log_size),
            'network_interfaces': network_interfaces,
            'disk_devices': disk_devices
        }
        return DetailResponse(data=data)
    
    def post(self, request):
        """保存监控配置"""
        data = request.data
        config = MonitorConfig.objects.first()
        if not config:
            config = MonitorConfig()
        
        old_interval = config.collect_interval if config.id else 60
        old_is_enabled = config.is_enabled if config.id else True
        
        config.is_enabled = data.get('is_enabled', config.is_enabled if config.id else True)
        config.log_save_days = data.get('log_save_days', config.log_save_days if config.id else 30)
        config.collect_interval = data.get('collect_interval', config.collect_interval if config.id else 60)
        
        # 验证采集间隔是否在合理范围内
        if config.collect_interval < 5:
            config.collect_interval = 5
        
        # 保存网卡和磁盘过滤配置
        if 'network_interfaces' in data:
            try:
                network_interfaces = data['network_interfaces']
                if isinstance(network_interfaces, list):
                    config.network_interfaces = json.dumps(network_interfaces)
            except:
                pass
        
        if 'disk_devices' in data:
            try:
                disk_devices = data['disk_devices']
                if isinstance(disk_devices, list):
                    config.disk_devices = json.dumps(disk_devices)
            except:
                pass
        
        config.save()
        
        # 动态调整定时任务
        try:
            from apps.sysmonitor.tasks import toggle_monitor_task, update_monitor_task_interval
            
            # 如果启用状态发生变化
            if old_is_enabled != config.is_enabled:
                toggle_monitor_task(config.is_enabled)
            # 如果监控已启用且采集间隔发生变化
            elif config.is_enabled and old_interval != config.collect_interval:
                update_monitor_task_interval(config.collect_interval)
                
        except Exception as e:
            import logging
            logger = logging.getLogger('sysmonitor')
            logger.error(f"更新监控任务失败: {e}")
        
        return SuccessResponse(msg="保存成功")
    
    def _format_bytes(self, size):
        """格式化字节大小"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.2f}KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size/1024/1024:.2f}MB"
        else:
            return f"{size/1024/1024/1024:.2f}GB"


class MonitorClearLogsView(CustomAPIView):
    """
    清空监控日志
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # 清空所有监控数据表
        MonitorCpu.objects.all().delete()
        MonitorMemory.objects.all().delete()
        MonitorDiskIO.objects.all().delete()
        MonitorNetwork.objects.all().delete()
        MonitorLoad.objects.all().delete()
        
        # 尝试执行 VACUUM 释放空间 (仅限 SQLite)
        try:
            db_config = settings.DATABASES.get('monitor')
            if db_config and db_config['ENGINE'] == 'django.db.backends.sqlite3':
                from django.db import connections
                with connections['monitor'].cursor() as cursor:
                    cursor.execute("VACUUM")
        except Exception as e:
            print(f"执行 VACUUM 失败: {e}")
        
        return SuccessResponse(msg="日志已清空")


class MonitorHistoryDataView(CustomAPIView):
    """
    获取监控历史数据（优化版）
    """
    permission_classes = [IsAuthenticated]
    
    # 最大返回数据条数
    MAX_LIMIT = 1200
    # 默认返回数据条数
    DEFAULT_LIMIT = 720

    def _get_limit(self, request):
        try:
            limit = int(request.query_params.get('limit', self.DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        if limit <= 0:
            limit = self.DEFAULT_LIMIT
        return min(limit, self.MAX_LIMIT)

    def _should_include_processes(self, request):
        value = str(request.query_params.get('include_processes', '')).lower()
        return value in ['1', 'true', 'yes', 'on']
    
    def get(self, request):
        monitor_type = request.query_params.get('type', 'cpu')
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        limit = self._get_limit(request)
        include_processes = self._should_include_processes(request)
        # 网卡/磁盘筛选参数
        interface_name = request.query_params.get('interface', '')
        disk_name = request.query_params.get('disk', '')
        
        # 根据类型选择模型
        model_map = {
            'cpu': MonitorCpu,
            'memory': MonitorMemory,
            'disk_io': MonitorDiskIO,
            'network': MonitorNetwork,
            'load': MonitorLoad,
        }
        
        model = model_map.get(monitor_type)
        if not model:
            return ErrorResponse(msg="无效的监控类型")
        
        # 使用values()减少内存占用，只查询需要的字段
        fields = ['id', 'record_time']
        
        if monitor_type == 'cpu':
            fields.extend(['usage_percent', 'cpu_count', 'cpu_name'])
            if include_processes:
                fields.append('top_processes')
        elif monitor_type == 'memory':
            fields.extend(['usage_percent', 'mem_total', 'mem_used', 'mem_free', 'mem_available'])
            if include_processes:
                fields.append('top_processes')
        elif monitor_type == 'disk_io':
            fields.extend(['disk_name', 'read_bytes', 'write_bytes', 'read_count', 'write_count', 'read_time', 'write_time'])
            if include_processes:
                fields.append('top_processes')
        elif monitor_type == 'network':
            fields.extend(['interface_name', 'up_bytes', 'down_bytes', 'up_packets', 'down_packets'])
        elif monitor_type == 'load':
            fields.extend(['usage_percent', 'load_one', 'load_five', 'load_fifteen'])
            if include_processes:
                fields.append('top_processes')
        
        queryset = model.objects.values(*fields)
        
        # 时间过滤
        if start_time:
            try:
                start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                queryset = queryset.filter(record_time__gte=start)
            except:
                pass
        
        if end_time:
            try:
                end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                queryset = queryset.filter(record_time__lte=end)
            except:
                pass
        else:
            # 默认查询最近24小时
            queryset = queryset.filter(record_time__gte=timezone.now() - timedelta(hours=24))
        
        # 网卡/磁盘筛选
        if monitor_type == 'disk_io' and disk_name:
            queryset = queryset.filter(disk_name=disk_name)
        elif monitor_type == 'network' and interface_name:
            queryset = queryset.filter(interface_name=interface_name)
        elif monitor_type == 'disk_io':
            # 默认只查询总计数据（disk_name为空字符串）
            queryset = queryset.filter(disk_name='')
        elif monitor_type == 'network':
            # 默认只查询总计数据（interface_name为空字符串）
            queryset = queryset.filter(interface_name='')
        
        # 限制数据量并排序
        queryset = queryset.order_by('-record_time')[:limit]
        
        # 转换为列表，避免在循环中查询数据库
        data = list(queryset)
        data.reverse()
        
        # 格式化数据
        result = []
        for item in data:
            record = {
                'id': item['id'],
                'record_time': item['record_time'].strftime('%m-%d %H:%M:%S'),
                'timestamp': int(item['record_time'].timestamp() * 1000),
            }
            
            if monitor_type == 'cpu':
                record['usage_percent'] = round(item['usage_percent'], 2)
                record['cpu_count'] = item['cpu_count']
                record['cpu_name'] = item['cpu_name']
                if include_processes:
                    try:
                        record['top_processes'] = json.loads(item['top_processes']) if item.get('top_processes') else []
                    except:
                        record['top_processes'] = []
                
            elif monitor_type == 'memory':
                record['usage_percent'] = round(item['usage_percent'], 2)
                record['mem_total'] = item['mem_total']
                record['mem_used'] = item['mem_used']
                record['mem_free'] = item['mem_free']
                record['mem_available'] = item['mem_available']
                if include_processes:
                    try:
                        record['top_processes'] = json.loads(item['top_processes']) if item.get('top_processes') else []
                    except:
                        record['top_processes'] = []
                
            elif monitor_type == 'disk_io':
                record['disk_name'] = item['disk_name']
                record['read_bytes'] = item['read_bytes']
                record['write_bytes'] = item['write_bytes']
                record['read_count'] = item['read_count']
                record['write_count'] = item['write_count']
                record['read_time'] = item['read_time']
                record['write_time'] = item['write_time']
                if include_processes:
                    try:
                        record['top_processes'] = json.loads(item['top_processes']) if item.get('top_processes') else []
                    except:
                        record['top_processes'] = []
                
            elif monitor_type == 'network':
                record['interface_name'] = item['interface_name']
                record['up_bytes'] = item['up_bytes']
                record['down_bytes'] = item['down_bytes']
                record['up_packets'] = item['up_packets']
                record['down_packets'] = item['down_packets']
                
            elif monitor_type == 'load':
                record['usage_percent'] = round(item['usage_percent'], 2)
                record['load_one'] = item['load_one']
                record['load_five'] = item['load_five']
                record['load_fifteen'] = item['load_fifteen']
                if include_processes:
                    try:
                        record['top_processes'] = json.loads(item['top_processes']) if item.get('top_processes') else []
                    except:
                        record['top_processes'] = []
            
            result.append(record)
        
        return DetailResponse(data={
            'list': result,
            'is_windows': plat == 'windows'
        })

class MonitorCollectDataView(CustomAPIView):
    """
    采集并保存监控数据（供定时任务调用）
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """手动触发数据采集"""
        MonitorDataCollector.collect_all()
        return SuccessResponse(msg="数据采集完成")


class MonitorDataCollector:
    """
    监控数据采集器（供定时任务调用）
    """
    
    @classmethod
    def collect_all(cls):
        """采集所有监控数据"""
        config = MonitorConfig.objects.first()
        if not config or not config.is_enabled:
            return False
        
        now = timezone.now()
        
        cls._collect_cpu(now)
        cls._collect_memory(now)
        cls._collect_disk_io(now)
        cls._collect_network(now)
        
        if plat != 'windows':
            cls._collect_load(now)
        
        return True
    
    @classmethod
    def _collect_cpu(cls, now):
        """采集CPU数据（使用非阻塞方式）"""
        try:
            # 使用非阻塞方式获取CPU使用率
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_count = psutil.cpu_count()
            cpu_count_physical = psutil.cpu_count(logical=False)
            
            # CPU名称只获取一次并缓存
            if not hasattr(cls, '_cpu_name'):
                cls._cpu_name = ""
                try:
                    if plat == 'windows':
                        import winreg
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                        cls._cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                        winreg.CloseKey(key)
                    else:
                        with open('/proc/cpuinfo', 'r') as f:
                            for line in f:
                                if 'model name' in line:
                                    cls._cpu_name = line.split(':')[1].strip()
                                    break
                except:
                    pass
            
            top_processes = cls._get_top_processes('cpu', 5)
            
            MonitorCpu.objects.create(
                record_time=now,
                usage_percent=cpu_percent,
                cpu_count=cpu_count,
                cpu_count_physical=cpu_count_physical,
                cpu_name=cls._cpu_name,
                top_processes=json.dumps(top_processes)
            )
        except Exception as e:
            print(f"采集CPU数据失败: {e}")
    
    @classmethod
    def _collect_memory(cls, now):
        """采集内存数据"""
        try:
            mem = psutil.virtual_memory()
            mem_total = mem.total / 1024 / 1024
            mem_used = mem.used / 1024 / 1024
            mem_free = mem.free / 1024 / 1024
            mem_available = getattr(mem, 'available', 0) / 1024 / 1024
            mem_buffers = getattr(mem, 'buffers', 0) / 1024 / 1024
            mem_cached = getattr(mem, 'cached', 0) / 1024 / 1024
            
            top_processes = cls._get_top_processes('memory', 5)
            
            MonitorMemory.objects.create(
                record_time=now,
                usage_percent=mem.percent,
                mem_total=round(mem_total, 2),
                mem_used=round(mem_used, 2),
                mem_free=round(mem_free, 2),
                mem_available=round(mem_available, 2),
                mem_buffers=round(mem_buffers, 2),
                mem_cached=round(mem_cached, 2),
                top_processes=json.dumps(top_processes)
            )
        except Exception as e:
            print(f"采集内存数据失败: {e}")
    
    # 类变量用于保存上一次采集的数据（用于计算差值）
    _last_disk_io = {}
    _last_network_io = {}
    _last_collect_time = None
    
    @classmethod
    def _collect_disk_io(cls, now):
        """
        采集磁盘IO数据
        参考宝塔面板：使用差值计算获取每秒速率
        """
        try:
            # 获取采集间隔（默认60秒）
            config = MonitorConfig.objects.first()
            interval = config.collect_interval if config else 60
            
            # 获取磁盘过滤配置
            disk_filter = []
            if config and config.disk_devices:
                try:
                    disk_filter = json.loads(config.disk_devices)
                except:
                    disk_filter = []
            
            # 获取所有磁盘IO数据（perdisk=True获取每个磁盘的数据）
            disk_io_dict = psutil.disk_io_counters(perdisk=True)
            
            if not disk_io_dict:
                return
            
            # 不再采集磁盘IO top5进程
            top_processes = []
            
            # 计算总计值
            total_read_bytes = 0
            total_write_bytes = 0
            total_read_count = 0
            total_write_count = 0
            total_read_time = 0
            total_write_time = 0
            
            for disk_name, disk_io in disk_io_dict.items():
                # 如果有过滤配置，只采集指定的磁盘
                if disk_filter and disk_name not in disk_filter:
                    continue
                
                # 获取上一次的累计值
                last_io = cls._last_disk_io.get(disk_name, {})
                
                # 计算差值（速率 = (当前值 - 上次值) / 间隔）
                if last_io:
                    read_bytes_rate = max(0, (disk_io.read_bytes - last_io.get('read_bytes', 0)) / interval)
                    write_bytes_rate = max(0, (disk_io.write_bytes - last_io.get('write_bytes', 0)) / interval)
                    read_count_rate = max(0, int((disk_io.read_count - last_io.get('read_count', 0)) / interval))
                    write_count_rate = max(0, int((disk_io.write_count - last_io.get('write_count', 0)) / interval))
                    read_time_rate = max(0, int((disk_io.read_time - last_io.get('read_time', 0)) / interval))
                    write_time_rate = max(0, int((disk_io.write_time - last_io.get('write_time', 0)) / interval))
                else:
                    # 第一次采集，速率为0
                    read_bytes_rate = 0
                    write_bytes_rate = 0
                    read_count_rate = 0
                    write_count_rate = 0
                    read_time_rate = 0
                    write_time_rate = 0
                
                # 保存当前累计值供下次使用
                cls._last_disk_io[disk_name] = {
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes,
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count,
                    'read_time': disk_io.read_time,
                    'write_time': disk_io.write_time,
                }
                
                # 累加到总计
                total_read_bytes += read_bytes_rate
                total_write_bytes += write_bytes_rate
                total_read_count += read_count_rate
                total_write_count += write_count_rate
                total_read_time += read_time_rate
                total_write_time += write_time_rate
                
                # 保存单个磁盘的数据（如果有过滤配置或磁盘数量大于1）
                if disk_filter or len(disk_io_dict) > 1:
                    MonitorDiskIO.objects.create(
                        record_time=now,
                        disk_name=disk_name,
                        read_bytes=round(read_bytes_rate, 2),
                        write_bytes=round(write_bytes_rate, 2),
                        read_count=read_count_rate,
                        write_count=write_count_rate,
                        read_time=read_time_rate,
                        write_time=write_time_rate,
                        total_read_bytes=disk_io.read_bytes,
                        total_write_bytes=disk_io.write_bytes,
                        top_processes=json.dumps(top_processes) if disk_name == list(disk_io_dict.keys())[0] else '[]'
                    )
            
            # 保存总计数据
            MonitorDiskIO.objects.create(
                record_time=now,
                disk_name='',  # 空字符串表示总计
                read_bytes=round(total_read_bytes, 2),
                write_bytes=round(total_write_bytes, 2),
                read_count=total_read_count,
                write_count=total_write_count,
                read_time=total_read_time,
                write_time=total_write_time,
                total_read_bytes=sum(io.read_bytes for io in disk_io_dict.values()),
                total_write_bytes=sum(io.write_bytes for io in disk_io_dict.values()),
                top_processes=json.dumps(top_processes)
            )
        except Exception as e:
            print(f"采集磁盘IO数据失败: {e}")
    
    @classmethod
    def _collect_network(cls, now):
        """
        采集网络数据
        参考宝塔面板：使用差值计算获取每秒速率，支持多网卡
        """
        try:
            # 获取采集间隔（默认60秒）
            config = MonitorConfig.objects.first()
            interval = config.collect_interval if config else 60
            
            # 获取网口过滤配置
            interface_filter = []
            if config and config.network_interfaces:
                try:
                    interface_filter = json.loads(config.network_interfaces)
                except:
                    interface_filter = []
            
            # 获取所有网卡IO数据（pernic=True获取每个网卡的数据）
            net_io_dict = psutil.net_io_counters(pernic=True)
            
            if not net_io_dict:
                return
            
            # 计算总计值
            total_up_bytes = 0
            total_down_bytes = 0
            total_up_packets = 0
            total_down_packets = 0
            total_up_err = 0
            total_up_drop = 0
            total_down_err = 0
            total_down_drop = 0
            
            for interface_name, net_io in net_io_dict.items():
                # 跳过回环网卡（lo/Loopback）
                if interface_name.lower() in ['lo', 'loopback']:
                    continue
                
                # 如果有过滤配置，只采集指定的网卡
                if interface_filter and interface_name not in interface_filter:
                    continue
                
                # 获取上一次的累计值
                last_io = cls._last_network_io.get(interface_name, {})
                
                # 计算差值（速率 = (当前值 - 上次值) / 间隔）
                if last_io:
                    up_bytes_rate = max(0, (net_io.bytes_sent - last_io.get('bytes_sent', 0)) / interval)
                    down_bytes_rate = max(0, (net_io.bytes_recv - last_io.get('bytes_recv', 0)) / interval)
                    up_packets_rate = max(0, int((net_io.packets_sent - last_io.get('packets_sent', 0)) / interval))
                    down_packets_rate = max(0, int((net_io.packets_recv - last_io.get('packets_recv', 0)) / interval))
                    up_err_rate = max(0, int((net_io.errin - last_io.get('errin', 0)) / interval))
                    up_drop_rate = max(0, int((net_io.dropin - last_io.get('dropin', 0)) / interval))
                    down_err_rate = max(0, int((net_io.errout - last_io.get('errout', 0)) / interval))
                    down_drop_rate = max(0, int((net_io.dropout - last_io.get('dropout', 0)) / interval))
                else:
                    # 第一次采集，速率为0
                    up_bytes_rate = 0
                    down_bytes_rate = 0
                    up_packets_rate = 0
                    down_packets_rate = 0
                    up_err_rate = 0
                    up_drop_rate = 0
                    down_err_rate = 0
                    down_drop_rate = 0
                
                # 保存当前累计值供下次使用
                cls._last_network_io[interface_name] = {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv,
                    'errin': net_io.errin,
                    'dropin': net_io.dropin,
                    'errout': net_io.errout,
                    'dropout': net_io.dropout,
                }
                
                # 累加到总计
                total_up_bytes += up_bytes_rate
                total_down_bytes += down_bytes_rate
                total_up_packets += up_packets_rate
                total_down_packets += down_packets_rate
                total_up_err += up_err_rate
                total_up_drop += up_drop_rate
                total_down_err += down_err_rate
                total_down_drop += down_drop_rate
                
                # 保存单个网卡的数据（如果有过滤配置或网卡数量大于1）
                if interface_filter or len(net_io_dict) > 1:
                    MonitorNetwork.objects.create(
                        record_time=now,
                        interface_name=interface_name,
                        up_bytes=round(up_bytes_rate, 2),
                        down_bytes=round(down_bytes_rate, 2),
                        up_packets=up_packets_rate,
                        down_packets=down_packets_rate,
                        up_err=up_err_rate,
                        up_drop=up_drop_rate,
                        down_err=down_err_rate,
                        down_drop=down_drop_rate,
                        total_up_bytes=net_io.bytes_sent,
                        total_down_bytes=net_io.bytes_recv
                    )
            
            # 保存总计数据
            MonitorNetwork.objects.create(
                record_time=now,
                interface_name='',  # 空字符串表示总计
                up_bytes=round(total_up_bytes, 2),
                down_bytes=round(total_down_bytes, 2),
                up_packets=total_up_packets,
                down_packets=total_down_packets,
                up_err=total_up_err,
                up_drop=total_up_drop,
                down_err=total_down_err,
                down_drop=total_down_drop,
                total_up_bytes=sum(io.bytes_sent for io in net_io_dict.values()),
                total_down_bytes=sum(io.bytes_recv for io in net_io_dict.values())
            )
        except Exception as e:
            print(f"采集网络数据失败: {e}")
    
    @classmethod
    def _collect_load(cls, now):
        """采集系统负载数据（仅Linux）"""
        try:
            load_avg = os.getloadavg()
            cpu_count = psutil.cpu_count()
            max_load = cpu_count * 2
            percent = min(100, round(load_avg[0] / max_load * 100, 2))
            
            top_processes = cls._get_top_processes('cpu', 5)
            
            MonitorLoad.objects.create(
                record_time=now,
                load_one=load_avg[0],
                load_five=load_avg[1],
                load_fifteen=load_avg[2],
                usage_percent=percent,
                cpu_count=cpu_count,
                top_processes=json.dumps(top_processes)
            )
        except Exception as e:
            print(f"采集负载数据失败: {e}")
    
    @classmethod
    def _get_top_processes(cls, sort_by='cpu', limit=5):
        """获取占用资源最高的进程（优化版，减少系统调用）"""
        processes = []
        try:
            # 只获取必要的属性，减少系统调用
            attrs = ['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'username']
            
            for proc in psutil.process_iter(attrs):
                try:
                    pinfo = proc.info
                    # 跳过无效进程
                    if pinfo['pid'] == 0:
                        continue
                        
                    memory_rss = 0
                    if pinfo.get('memory_info'):
                        memory_rss = pinfo['memory_info'].rss / 1024 / 1024
                    
                    # 磁盘IO只在需要时获取
                    disk_read = 0
                    disk_write = 0
                    if sort_by == 'disk':
                        try:
                            io_counters = proc.io_counters()
                            disk_read = io_counters.read_bytes
                            disk_write = io_counters.write_bytes
                        except:
                            pass
                    
                    processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'] or '',
                        'cpu_percent': pinfo['cpu_percent'] or 0,
                        'memory_percent': pinfo['memory_percent'] or 0,
                        'memory_rss': round(memory_rss, 2),
                        'username': pinfo['username'] or '',
                        'disk_read': disk_read,
                        'disk_write': disk_write
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # 排序
            if sort_by == 'cpu':
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            elif sort_by == 'memory':
                processes.sort(key=lambda x: x['memory_rss'], reverse=True)
            elif sort_by == 'disk':
                processes.sort(key=lambda x: x['disk_read'] + x['disk_write'], reverse=True)
            
            return processes[:limit]
        except Exception:
            return []
    
    @classmethod
    def clean_old_data(cls, days):
        """清理过期数据"""
        try:
            expire_time = timezone.now() - timedelta(days=days)
            MonitorCpu.objects.filter(record_time__lt=expire_time).delete()
            MonitorMemory.objects.filter(record_time__lt=expire_time).delete()
            MonitorDiskIO.objects.filter(record_time__lt=expire_time).delete()
            MonitorNetwork.objects.filter(record_time__lt=expire_time).delete()
            MonitorLoad.objects.filter(record_time__lt=expire_time).delete()
            
            # 尝试执行 VACUUM 释放空间 (仅限 SQLite)
            try:
                db_config = settings.DATABASES.get('monitor')
                if db_config and db_config['ENGINE'] == 'django.db.backends.sqlite3':
                    from django.db import connections
                    with connections['monitor'].cursor() as cursor:
                        cursor.execute("VACUUM")
            except Exception as e:
                print(f"执行 VACUUM 失败: {e}")
                
        except Exception as e:
            print(f"清理过期数据失败: {e}")


class MonitorDevicesView(CustomAPIView):
    """
    获取系统网卡和磁盘列表
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取网卡和磁盘列表"""
        device_type = request.query_params.get('type', 'all')
        
        result = {}
        
        if device_type in ['all', 'network']:
            # 获取网卡列表
            try:
                net_io_dict = psutil.net_io_counters(pernic=True)
                network_interfaces = []
                for name, io in net_io_dict.items():
                    # 跳过回环网卡
                    if name.lower() in ['lo', 'loopback']:
                        continue
                    network_interfaces.append({
                        'name': name,
                        'bytes_sent': io.bytes_sent,
                        'bytes_recv': io.bytes_recv,
                        'packets_sent': io.packets_sent,
                        'packets_recv': io.packets_recv
                    })
                result['network'] = network_interfaces
            except Exception as e:
                result['network'] = []
                print(f"获取网卡列表失败: {e}")
        
        if device_type in ['all', 'disk']:
            # 获取磁盘列表
            try:
                disk_io_dict = psutil.disk_io_counters(perdisk=True)
                disk_devices = []
                for name, io in disk_io_dict.items():
                    disk_devices.append({
                        'name': name,
                        'read_bytes': io.read_bytes,
                        'write_bytes': io.write_bytes,
                        'read_count': io.read_count,
                        'write_count': io.write_count
                    })
                result['disk'] = disk_devices
            except Exception as e:
                result['disk'] = []
                print(f"获取磁盘列表失败: {e}")
        
        return DetailResponse(data=result)
