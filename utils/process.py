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

import psutil
import time
from django.core.cache import cache
from utils.common import current_os

class ProcessMonitor:
    """进程监控类，用于获取进程列表和进程详细信息。"""
    cache_key = "ruyi_process_cpu_percent"
    is_windows = False

    def __init__(self, cache_timeout=120):
        self.cache_timeout = cache_timeout
        self.pid_cpuinfo = {}
        self.sum_cpus = psutil.cpu_count() or 1
        self.is_windows = current_os == 'windows'
        
    def _timer(self):
        return time.monotonic() * self.sum_cpus
        
    def get_cpu_percent(self, pid,process_cpu_time):
        all_pid_cpuinfo = cache.get(self.cache_key,{})
        cached_data = all_pid_cpuinfo.get(pid, (0, 0, 0))
        st0, tt0_0, tt0_1 = cached_data
        st1, tt1_0, tt1_1 = self._timer(), process_cpu_time.user, process_cpu_time.system
        proc_time = (tt1_0 - tt0_0) + (tt1_1 - tt0_1)
        time = st1 - st0
        try:
            cpus_percent = (proc_time / time) * 100  # 计算 CPU 使用率百分比
        except ZeroDivisionError:
            cpus_percent = 0.0  # 防止除以零异常
        all_pid_cpuinfo[pid] = [st1, tt1_0, tt1_1]
        
        res =  "{:.2f}".format(cpus_percent)
        
        # 更新总缓存键
        cache.set(self.cache_key, all_pid_cpuinfo, timeout=self.cache_timeout)

        return res


    def get_processes_list(self, pid_filter=None, name_filter=None, user_filter=None):
        """
        获取进程列表
        :param pid_filter: 进程ID过滤
        :param name_filter: 进程名称过滤
        :param user_filter: 用户过滤
        :return: 进程信息列表
        """
        processes_info = []

        for proc in psutil.process_iter(['pid', 'ppid', 'name', 'exe', 'cmdline', 'num_threads', 'cpu_percent', 'memory_info', 'create_time', 'open_files', 'status', 'username']):
            try:
                memory_info_ps = proc.memory_info()
                memory_full_info_ps = proc.memory_full_info()
                memory_info = {
                    'rss': memory_info_ps.rss,
                    'vms': memory_info_ps.vms,
                    'shared': memory_info_ps.shared,
                    'text': memory_info_ps.text,
                    'data': memory_info_ps.data,
                    'lib': memory_info_ps.lib,
                    'dirty': memory_info_ps.dirty,
                    'pss': memory_full_info_ps.pss,
                    'swap': memory_full_info_ps.swap
                }

                process_cpu_time = proc.cpu_times()
                proc_info = proc.as_dict(attrs=['pid', 'ppid', 'name', 'exe', 'cmdline', 'num_threads', 'cpu_percent', 'memory_info', 'create_time', 'open_files', 'status', 'username'])
                connections = proc.net_connections()
                new_connections = []
                for conn in connections:
                    new_connections.append({
                        "status": conn.status,
                        "laddr":f"{conn.laddr[0]}:{conn.laddr[1]}",
                        "raddr": f"{conn.raddr[0]}:{conn.raddr[1]}" if conn.raddr else 'N/A',
                    })
                # 获取 CPU 使用率
                process_info = {
                    'pid': proc_info['pid'],
                    'ppid': proc_info['ppid'],
                    'name': proc_info['name'],
                    'num_threads': proc_info['num_threads'],
                    'cpu_percent': self.get_cpu_percent(proc_info['pid'],process_cpu_time),
                    'memory_info': memory_info,
                    'create_time': proc_info['create_time'],
                    'status': proc_info['status'],
                    'connections': new_connections,
                    'username': proc_info['username'],
                    'io_read': proc.io_counters().read_bytes,
                    'io_write': proc.io_counters().write_bytes,
                    'exe': proc_info['exe'],
                    'cmdline': proc_info['cmdline'],
                    'open_files': proc_info['open_files'],
                    'environ': proc.environ()
                }

                # 过滤条件
                if pid_filter and str(process_info['pid']) != str(pid_filter):
                    continue
                if name_filter and name_filter.lower() not in process_info['name'].lower():
                    continue
                if user_filter and user_filter.lower() != process_info['username'].lower():
                    continue

                processes_info.append(process_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return processes_info

    def terminate_process_pid(self, pid):
        """
        终止指定 PID 的进程。
        :param pid: 进程ID
        :return: 是否成功终止进程
        """
        try:
            process = psutil.Process(pid)
            process.terminate()
            return True, "终止成功"
        except psutil.NoSuchProcess:
            return False, f"进程 {pid} 不存在"
        except psutil.AccessDenied:
            return False, f"无权限终止进程 {pid}"

    def kill_process_pid(self, pid):
        """
        强制终止指定 PID 的进程。
        :param pid: 进程ID
        :return: 是否成功终止进程
        """
        try:
            process = psutil.Process(pid)
            process.kill()
            return True, "终止成功"
        except psutil.NoSuchProcess:
            return False, f"进程 {pid} 不存在"
        except psutil.AccessDenied:
            return False, f"无权限终止进程 {pid}"