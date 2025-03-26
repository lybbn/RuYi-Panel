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
    
    def _get_process_connection_count(self, proc):
        """
        获取单个进程的连接数量（内部方法）
        """
        try:
            # 获取进程的连接数量
            connections = proc.connections()
            return len(connections)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0
        
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

        if self.is_windows:
            processes_info = self.windows_get_processes_list(pid_filter=pid_filter, name_filter=name_filter, user_filter=user_filter)  
        else:
            processes_info = self.linux_get_processes_list(pid_filter=pid_filter, name_filter=name_filter, user_filter=user_filter)
        return processes_info
    
    def get_pid_detail_info(self,pid):
        try:
            if isinstance(pid,str):pid = int(pid)
            proc = psutil.Process(pid)
            # 获取进程基本信息
            proc_info = proc.as_dict(attrs=['pid', 'ppid', 'name', 'exe', 'cmdline', 'num_threads', 'cpu_percent', 'memory_info', 'create_time', 'open_files', 'status', 'username'])

            # 获取内存信息
            memory_info_ps = proc.memory_info()
            memory_info = {
                'rss': memory_info_ps.rss,
                'vms': memory_info_ps.vms,
            }
            if not self.is_windows:
                memory_info['shared'] = memory_info_ps.shared
                memory_info['text'] = memory_info_ps.text
                memory_info['data'] = memory_info_ps.data
                memory_info['lib'] = memory_info_ps.lib
                memory_info['dirty'] = memory_info_ps.dirty
                memory_info['pss'] = memory_info_ps.pss
                memory_info['swap'] = memory_info_ps.swap

            # 获取 CPU 时间
            process_cpu_time = proc.cpu_times()

            # 获取 I/O 信息
            io_read = io_write = 0
            try:
                io_counters = proc.io_counters()
                io_read = io_counters.read_bytes
                io_write = io_counters.write_bytes
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            connections = proc.net_connections()
            new_connections = []
            for conn in connections:
                new_connections.append({
                    "status": conn.status,
                    "laddr":f"{conn.laddr[0]}:{conn.laddr[1]}",
                    "raddr": f"{conn.raddr[0]}:{conn.raddr[1]}" if conn.raddr else 'N/A',
                })
            # 构建进程信息字典
            process_info = {
                'pid': proc_info['pid'],
                'ppid': proc_info['ppid'],
                'name': proc_info['name'],
                'num_threads': proc_info['num_threads'],
                'cpu_percent': self.get_cpu_percent(proc_info['pid'], process_cpu_time),
                'memory_info': memory_info,
                'create_time': proc_info['create_time'],
                'status': proc_info['status'],
                'connections': new_connections,
                'username': proc_info['username'],
                'io_read': io_read,
                'io_write': io_write,
                'exe': proc_info['exe'],
                'cmdline': proc_info['cmdline'],
                'open_files': proc_info['open_files'],
                'environ': proc.environ()
            }

            return process_info
        except Exception as e:
            print(e)
            return {}

    def _get_windows_process_info(self, pid, pid_filter=None, name_filter=None, user_filter=None):
        """
        获取单个进程的信息（内部方法）
        Author: lybbn
        """
        try:
            proc = psutil.Process(pid)
            # 获取进程基本信息
            proc_info = proc.as_dict(attrs=['pid', 'ppid', 'name', 'num_threads', 'memory_info', 'create_time', 'status', 'username'])

            # 提前过滤
            if pid_filter and str(proc_info['pid']) != str(pid_filter):
                return None
            if name_filter and name_filter.lower() not in proc_info['name'].lower():
                return None
            if user_filter and user_filter.lower() != proc_info['username'].lower():
                return None

            # 获取内存信息
            memory_info_ps = proc.memory_info()
            memory_info = {
                'rss': memory_info_ps.rss,
                'vms': memory_info_ps.vms,
            }

            # 获取 CPU 时间
            process_cpu_time = proc.cpu_times()

            # 获取 I/O 信息
            # io_read = io_write = 0
            # try:
            #     io_counters = proc.io_counters()
            #     io_read = io_counters.read_bytes
            #     io_write = io_counters.write_bytes
            # except (psutil.AccessDenied, psutil.NoSuchProcess):
            #     pass

            # 构建进程信息字典
            process_info = {
                'pid': proc_info['pid'],
                'ppid': proc_info['ppid'],
                'name': proc_info['name'],
                'num_threads': proc_info['num_threads'],
                'cpu_percent': self.get_cpu_percent(proc_info['pid'], process_cpu_time),
                'memory_info': memory_info,
                'create_time': proc_info['create_time'],
                'status': proc_info['status'],
                'connections': self._get_process_connection_count(proc),
                'username': proc_info['username'],
                # 'io_read': io_read,
                # 'io_write': io_write,
                # 'exe': proc_info['exe'],
                # 'cmdline': proc_info['cmdline'],
                # 'open_files': proc_info['open_files'],
                # 'environ': proc.environ()
            }

            return process_info
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def windows_get_processes_list(self, pid_filter=None, name_filter=None, user_filter=None):
        """
        获取进程列表
        :param pid_filter: 进程ID过滤
        :param name_filter: 进程名称过滤
        :param user_filter: 用户过滤
        :return: 进程信息列表
        Author: lybbn
        """
        from concurrent.futures import ProcessPoolExecutor, as_completed
        processes_info = []
        pids = [proc.pid for proc in psutil.process_iter(['pid'])]
        # 使用线程池并发获取进程信息
        with ProcessPoolExecutor() as executor:
            futures = []
            for pid in pids:
                futures.append(executor.submit(self._get_windows_process_info, pid, pid_filter, name_filter, user_filter))

            for future in as_completed(futures):
                result = future.result()
                if result:
                    processes_info.append(result)

        return processes_info
    
    def linux_get_processes_list(self, pid_filter=None, name_filter=None, user_filter=None):
        """
        获取进程列表
        :param pid_filter: 进程ID过滤
        :param name_filter: 进程名称过滤
        :param user_filter: 用户过滤
        :return: 进程信息列表
        Author: lybbn
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