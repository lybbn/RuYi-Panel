# coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板 RUYI
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-03-10
# +-------------------------------------------------------------------

# ------------------------------
# 进程监控
# ------------------------------

import json
import os
import time
import psutil

from django.core.cache import cache

class ProcessMonitor:
    """进程监控类，用于获取进程列表和进程详细信息。"""
    cache_key="process_monitor_cache"
    def __init__(self,cache_timeout=60):
        self.__cpu_time = None  # 总的CPU时间缓存
        self.old_info = {}  # 存储上次CPU时间的缓存
        self.new_info = {}  # 存储当前的CPU时间
        self.cache_timeout = cache_timeout
    
    def get_cpu_time(self):
        """
        获取当前系统的总CPU时间
        :return: 系统总CPU时间
        """
        if self.__cpu_time:
            return self.__cpu_time
        cpu_times = psutil.cpu_times()
        self.__cpu_time = cpu_times.user + cpu_times.system + cpu_times.nice + cpu_times.idle
        return self.__cpu_time
    
    def get_process_cpu_time(self, p_cpu_times):
        """
        获取指定进程的CPU时间
        :param p_cpu_time: 进程CPU时间
        :return: 进程CPU时间
        """
        cpu_time = 0.00
        for p in p_cpu_times: cpu_time += p
        return cpu_time
        
    def get_cpu_usage(self,pid,p_cpu_times):
        cpu_times = self.get_cpu_time()
        process_cpu_time = self.get_process_cpu_time(p_cpu_times)
        if not self.old_info:
            # 从缓存中加载旧数据
            self.get_old()

        if pid not in self.old_info:
            # 如果当前进程在缓存中不存在，初始化新信息并返回0
            self.new_info[pid] = {'cpu_time': process_cpu_time}
            return 0.00

        try:
            # 计算CPU占用率
            percent = round(100.00 * (process_cpu_time - self.old_info[pid]['cpu_time']) / (cpu_times - self.old_info['cpu_time']),2)
        except ZeroDivisionError:
            # 防止除零错误，返回0
            return 0.00

        # 更新当前缓存信息
        self.new_info[pid] = {'cpu_time': process_cpu_time}
        if percent > 0:
            return percent
        return 0.00
    
    def get_old(self):
        """
        从缓存中加载上次的CPU时间数据
        :return: 是否成功加载旧数据
        """
        if self.old_info:
            return True
        # 从缓存中加载旧的CPU时间数据
        data = cache.get(self.cache_key)
        if not data:
            return False
        self.old_info = data
        return True

    def save_old(self):
        """
        将当前的CPU时间信息保存到缓存中
        """
        cache.set(self.cache_key, self.new_info, timeout=self.cache_timeout)
    
    def get_processes_list(self,pid_filter=None,name_filter=None,user_filter=None):
        processes_info = []

        for proc in psutil.process_iter(['pid', 'ppid', 'name','exe', 'cmdline', 'num_threads', 'cpu_percent', 'memory_info', 'create_time', 'open_files', 'status', 'username']):
            try:
                memory_info_ps = proc.memory_info()
                memory_full_info_ps = proc.memory_full_info()
                memory_info = {}
                memory_info['rss'] = memory_info_ps.rss
                memory_info['vms'] = memory_info_ps.vms
                memory_info['shared'] = memory_info_ps.shared
                memory_info['text'] = memory_info_ps.text
                memory_info['data'] = memory_info_ps.data
                memory_info['lib'] = memory_info_ps.lib
                memory_info['dirty'] = memory_info_ps.dirty
                memory_info['pss'] = memory_full_info_ps.pss
                memory_info['swap'] = memory_full_info_ps.swap
                
                process_cpu_time = proc.cpu_times()
                
                proc_info = proc.as_dict(attrs=['pid', 'ppid', 'name','exe', 'cmdline', 'num_threads', 'cpu_percent', 'memory_info', 'create_time', 'open_files', 'status', 'username'])
                # 获取进程信息
                process_info = {
                    'pid': proc_info['pid'],  # 进程ID
                    'ppid': proc_info['ppid'],  # 父进程ID
                    'name': proc_info['name'],  # 进程名称
                    'num_threads': proc_info['num_threads'],  # 线程数量
                    'cpu_percent': self.get_cpu_usage(proc_info['pid'],process_cpu_time),
                    'memory_info': memory_info,
                    'create_time': proc_info['create_time'],  # 启动时间（时间戳）
                    'status': proc_info['status'],  # 进程状态
                    'connections': proc.net_connections(),
                    'username': proc_info['username'],  # 所属用户
                    'io_read':proc.io_counters()[0],
                    'io_write':proc.io_counters()[1],
                    'exe':proc_info['exe'],
                    'cmdline':proc_info['cmdline'],
                    'open_files': proc_info['open_files'],
                }
                # 过滤条件
                if pid_filter and str(process_info['pid']) != str(pid_filter):
                    continue  # 跳过不符合 PID 过滤条件的进程
                if name_filter and name_filter.lower() not in process_info['name'].lower():
                    continue  # 跳过不符合名称过滤条件的进程
                if user_filter and user_filter.lower() != process_info['username'].lower():
                    continue  # 跳过不符合用户过滤条件的进程
                processes_info.append(process_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # 忽略无法访问或已终止的进程
                continue
        return processes_info
    
    def terminate_process_pid(self,pid):
        """
        终止指定 PID 的进程。
        
        :param pid: 进程ID
        :return: 是否成功终止进程
        """
        try:
            process = psutil.Process(pid)
            process.terminate()  # 发送 SIGTERM 信号
            return True,"终止成功"
        except psutil.NoSuchProcess:
            return False,f"进程 {pid} 不存在"
        except psutil.AccessDenied:
            return False,f"无权限终止进程 {pid}"

    def kill_process_pid(self,pid):
        """
        强制终止指定 PID 的进程。
        
        :param pid: 进程ID
        :return: 是否成功终止进程
        """
        try:
            process = psutil.Process(pid)
            process.kill()  # 发送 SIGKILL 信号
            return True,"终止成功"
        except psutil.NoSuchProcess:
            return False,f"进程 {pid} 不存在"
        except psutil.AccessDenied:
            return False,f"无权限终止进程 {pid}"