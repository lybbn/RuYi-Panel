import os
import platform
import psutil
import threading
import subprocess
import time
import uuid
from apps.sysai.tools.base import register_tool, AIToolRegistry
from utils.common import RunCommand


class CommandManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.commands = {}
                    cls._instance._cmd_lock = threading.Lock()
        return cls._instance

    def start_command(self, command: str, cwd: str = None) -> tuple:
        cmd_id = str(uuid.uuid4())[:8]
        if not cwd:
            cwd = os.getcwd()

        shell_cmd = command
        is_windows = os.name == 'nt'
        if is_windows:
            shell_cmd = ["powershell", "-Command", command]

        try:
            process = subprocess.Popen(
                shell_cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                shell=not is_windows,
            )
        except Exception as e:
            return None, str(e)

        cmd_info = {
            "id": cmd_id,
            "process": process,
            "output": [],
            "status": "running",
            "start_time": time.time(),
            "cwd": cwd,
            "command": command,
        }

        with self._cmd_lock:
            self.commands[cmd_id] = cmd_info

        t = threading.Thread(target=self._read_output, args=(cmd_id, process), daemon=True)
        t.start()

        return cmd_id, None

    def _read_output(self, cmd_id, process):
        try:
            for line in iter(process.stdout.readline, ''):
                with self._cmd_lock:
                    if cmd_id in self.commands:
                        self.commands[cmd_id]["output"].append(line)
        except Exception:
            pass
        finally:
            try:
                process.stdout.close()
            except Exception:
                pass
            return_code = process.wait()
            with self._cmd_lock:
                if cmd_id in self.commands:
                    self.commands[cmd_id]["status"] = "done"
                    self.commands[cmd_id]["returncode"] = return_code

    def get_status(self, cmd_id: str, priority: str = "bottom", limit: int = 500):
        with self._cmd_lock:
            if cmd_id not in self.commands:
                return None
            cmd = self.commands[cmd_id]
            output_lines = cmd["output"]
            if priority == "bottom":
                lines = output_lines[-limit:]
            else:
                lines = output_lines[:limit]
            return {
                "status": cmd["status"],
                "returncode": cmd.get("returncode"),
                "output": "".join(lines),
                "cwd": cmd["cwd"],
                "command": cmd["command"],
                "elapsed": round(time.time() - cmd["start_time"], 1),
            }

    def stop_command(self, cmd_id: str):
        with self._cmd_lock:
            if cmd_id not in self.commands:
                return False
            cmd = self.commands[cmd_id]
            if cmd["status"] == "running":
                try:
                    cmd["process"].terminate()
                    cmd["status"] = "stopped"
                except Exception:
                    pass
                return True
            return False

    def cleanup_old(self, max_age: int = 3600):
        now = time.time()
        with self._cmd_lock:
            to_remove = []
            for cmd_id, cmd in self.commands.items():
                if cmd["status"] != "running" and now - cmd["start_time"] > max_age:
                    to_remove.append(cmd_id)
            for cmd_id in to_remove:
                del self.commands[cmd_id]


_CMD_MANAGER = CommandManager()


@register_tool(id='get_system_info', category='system', name_cn='系统信息', risk_level='low')
def get_system_info():
    """获取服务器系统基本信息，包括主机名、操作系统、CPU、内存、磁盘使用情况、运行时间、系统负载等综合信息。当用户询问服务器状态、系统概况时使用此工具。"""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu_percent = psutil.cpu_percent(interval=1)
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
    boot_time = psutil.boot_time()

    import time
    uptime_seconds = int(time.time() - boot_time)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60

    disks = []
    for p in psutil.disk_partitions():
        if os.name == 'nt' and 'cdrom' in p.opts:
            continue
        try:
            usage = psutil.disk_usage(p.mountpoint)
            disks.append({
                'device': p.device,
                'mount': p.mountpoint,
                'fstype': p.fstype,
                'total_gb': round(usage.total / (1024**3), 2),
                'used_gb': round(usage.used / (1024**3), 2),
                'free_gb': round(usage.free / (1024**3), 2),
                'percent': usage.percent,
            })
        except (PermissionError, OSError):
            continue

    return {
        'hostname': platform.node(),
        'os': platform.system(),
        'os_version': platform.version(),
        'architecture': platform.machine(),
        'python_version': platform.python_version(),
        'cpu_count': psutil.cpu_count(),
        'cpu_percent': cpu_percent,
        'load_avg_1m': round(load_avg[0], 2),
        'load_avg_5m': round(load_avg[1], 2),
        'load_avg_15m': round(load_avg[2], 2),
        'memory': {
            'total_gb': round(mem.total / (1024**3), 2),
            'used_gb': round(mem.used / (1024**3), 2),
            'available_gb': round(mem.available / (1024**3), 2),
            'percent': mem.percent,
        },
        'swap': {
            'total_gb': round(swap.total / (1024**3), 2),
            'used_gb': round(swap.used / (1024**3), 2),
            'percent': swap.percent,
        },
        'disks': disks,
        'uptime': f'{days}天{hours}小时{minutes}分钟',
        'boot_time': boot_time,
    }


@register_tool(id='get_cpu_info', category='system', name_cn='CPU信息', risk_level='low')
def get_cpu_info():
    """获取CPU详细信息，包括每个核心的使用率、CPU频率、核心数等。当用户需要详细CPU性能数据时使用。"""
    cpu_percent_per_cpu = psutil.cpu_percent(interval=1, percpu=True)
    cpu_freq = psutil.cpu_freq()

    return {
        'cpu_count_physical': psutil.cpu_count(logical=False),
        'cpu_count_logical': psutil.cpu_count(logical=True),
        'cpu_percent_total': sum(cpu_percent_per_cpu) / len(cpu_percent_per_cpu),
        'cpu_percent_per_cpu': cpu_percent_per_cpu,
        'cpu_freq_current_mhz': round(cpu_freq.current, 0) if cpu_freq else None,
        'cpu_freq_min_mhz': round(cpu_freq.min, 0) if cpu_freq else None,
        'cpu_freq_max_mhz': round(cpu_freq.max, 0) if cpu_freq else None,
    }


@register_tool(id='get_memory_info', category='system', name_cn='内存信息', risk_level='low')
def get_memory_info():
    """获取内存和交换分区使用详情，包括总量、已用、可用、使用率等。当用户需要详细内存数据时使用。"""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        'virtual': {
            'total_gb': round(mem.total / (1024**3), 2),
            'available_gb': round(mem.available / (1024**3), 2),
            'used_gb': round(mem.used / (1024**3), 2),
            'free_gb': round(mem.free / (1024**3), 2),
            'cached_gb': round(mem.cached / (1024**3), 2) if hasattr(mem, 'cached') else 0,
            'buffers_gb': round(mem.buffers / (1024**3), 2) if hasattr(mem, 'buffers') else 0,
            'percent': mem.percent,
        },
        'swap': {
            'total_gb': round(swap.total / (1024**3), 2),
            'used_gb': round(swap.used / (1024**3), 2),
            'free_gb': round(swap.free / (1024**3), 2),
            'percent': swap.percent,
        }
    }


@register_tool(id='get_disk_info', category='system', name_cn='磁盘信息', risk_level='low')
def get_disk_info():
    """获取磁盘分区和使用详情，包括每个分区的设备名、挂载点、文件系统类型、容量和使用率等。"""
    result = []
    for p in psutil.disk_partitions():
        if os.name == 'nt' and 'cdrom' in p.opts:
            continue
        try:
            usage = psutil.disk_usage(p.mountpoint)
            result.append({
                'device': p.device,
                'mount': p.mountpoint,
                'fstype': p.fstype,
                'opts': p.opts,
                'total_gb': round(usage.total / (1024**3), 2),
                'used_gb': round(usage.used / (1024**3), 2),
                'free_gb': round(usage.free / (1024**3), 2),
                'percent': usage.percent,
            })
        except (PermissionError, OSError):
            continue
    return {'disks': result, 'total_partitions': len(result)}


@register_tool(id='get_network_info', category='system', name_cn='网络信息', risk_level='low')
def get_network_info():
    """获取网络IO统计和当前网络连接列表，包括发送接收字节数、连接数、各连接状态等。"""
    net_io = psutil.net_io_counters()
    net_addrs = psutil.net_if_addrs()
    net_stats = psutil.net_if_stats()

    interfaces = []
    for iface, addrs in net_addrs.items():
        stat = net_stats.get(iface)
        iface_info = {
            'name': iface,
            'is_up': stat.isup if stat else False,
            'speed_mbps': stat.speed if stat else 0,
            'addresses': [],
        }
        for addr in addrs:
            iface_info['addresses'].append({
                'family': str(addr.family),
                'address': addr.address,
                'netmask': addr.netmask,
            })
        interfaces.append(iface_info)

    connections = []
    for conn in psutil.net_connections(kind='inet'):
        try:
            connections.append({
                'local_addr': f'{conn.laddr.ip}:{conn.laddr.port}' if conn.laddr else '',
                'remote_addr': f'{conn.raddr.ip}:{conn.raddr.port}' if conn.raddr else '',
                'status': conn.status,
                'pid': conn.pid,
            })
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

    return {
        'io': {
            'bytes_sent_gb': round(net_io.bytes_sent / (1024**3), 4),
            'bytes_recv_gb': round(net_io.bytes_recv / (1024**3), 4),
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'errin': net_io.errin,
            'errout': net_io.errout,
            'dropin': net_io.dropin,
            'dropout': net_io.dropout,
        },
        'interfaces': interfaces,
        'connections_count': len(connections),
        'connections_sample': connections[:30],
    }


@register_tool(id='get_process_list', category='system', name_cn='进程列表', risk_level='low')
def get_process_list(limit: int = 20, sort_by: str = 'cpu'):
    """获取系统进程列表，可按CPU或内存使用率排序。当用户需要查看占用资源最多的进程时使用。

    Args:
        limit: 返回的进程数量，默认20
        sort_by: 排序方式，可选 cpu 或 memory，默认 cpu
    """
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status', 'create_time', 'cmdline']):
        try:
            info = proc.info
            info['memory_mb'] = round(info.get('memory_percent', 0) * psutil.virtual_memory().total / (1024**2) / 100, 2) if info.get('memory_percent') else 0
            processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort_by == 'memory':
        processes.sort(key=lambda x: x.get('memory_percent', 0) or 0, reverse=True)
    else:
        processes.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)

    return {
        'processes': processes[:limit],
        'total': len(processes),
        'sort_by': sort_by,
    }


@register_tool(id='execute_command', category='system', name_cn='执行命令', risk_level='high')
def execute_command(command: str, timeout: int = 30):
    """在服务器上执行命令并返回结果。⚠️此为高危操作，仅用于系统诊断和管理。

    **重要：命令必须适配当前操作系统！**
    - Windows系统使用：dir、tasklist、netstat、sc、powershell、wmic 等Windows命令
    - Linux系统使用：ls、ps、grep、systemctl、journalctl 等Linux命令
    - 不确定操作系统时，先用 get_system_info 工具查询

    **路径规则：命令中涉及文件或目录路径时，必须使用绝对路径，禁止使用相对路径！**
    - 正确：ls /var/log/nginx/access.log、type C:\\Windows\\System32\\drivers\\etc\\hosts
    - 错误：ls ./nginx/access.log、type hosts

    **禁止使用此工具写入文件内容！写入文件必须使用 write_file 工具。**
    - 禁止：cat > file << 'EOF'、echo "content" > file、tee file
    - 正确：使用 write_file 工具

    禁止执行的危险操作：
    - 删除系统文件或目录（如 rm -rf、del /f /s）
    - 修改系统关键配置
    - 格式化磁盘、修改分区表
    - 安装或卸载系统级软件包（除非用户明确要求）
    - 写入文件内容（必须使用 write_file 工具）

    Args:
        command: 要执行的命令（必须适配当前操作系统，路径必须使用绝对路径）
        timeout: 命令超时时间（秒），默认30秒
    """
    from apps.sysai.agent.file_safety import is_command_denied
    denied = is_command_denied(command)
    if denied:
        return {'command': command, 'error': denied}

    registry = AIToolRegistry()
    registry.emit_progress('execute_command', 'tool.log', 0, 'Executing command...')

    try:
        out, err = RunCommand(command, timeout=timeout)
        registry.emit_progress('execute_command', 'tool.log', 0, 'Command completed, processing output...')
        output = out
        if err:
            output += f'\n[STDERR]: {err}'
        return {
            'command': command,
            'returncode': 0 if not err else 1,
            'output': output[:10000],
            'truncated': len(output) > 10000,
        }
    except Exception as e:
        return {
            'command': command,
            'error': str(e),
        }


@register_tool(id='start_command', category='system', name_cn='启动后台命令', risk_level='high')
def start_command(command: str, cwd: str = ''):
    """在服务器上启动一个后台命令，立即返回命令ID，不等待命令完成。适用于长时间运行的命令（如安装软件、编译项目、下载文件等）。

    启动后使用 check_command_status 工具查询命令执行状态和输出，使用 stop_command 工具终止命令。

    **重要：命令必须适配当前操作系统！**
    - Windows系统使用：dir、tasklist、netstat、sc、powershell 等Windows命令
    - Linux系统使用：ls、ps、grep、systemctl 等Linux命令

    **路径规则：命令中涉及文件或目录路径时，必须使用绝对路径，禁止使用相对路径！**

    Args:
        command: 要执行的命令（必须适配当前操作系统，路径必须使用绝对路径）
        cwd: 命令执行的工作目录，默认为当前目录
    """
    from apps.sysai.agent.file_safety import is_command_denied
    denied = is_command_denied(command)
    if denied:
        return {'command': command, 'error': denied}

    work_dir = cwd if cwd else None
    cmd_id, err = _CMD_MANAGER.start_command(command, work_dir)
    if err:
        return {'command': command, 'error': err}

    return {
        'command_id': cmd_id,
        'command': command,
        'status': 'running',
        'message': f'命令已在后台启动，ID: {cmd_id}。请使用 check_command_status 工具查询执行状态。',
    }


@register_tool(id='check_command_status', category='system', name_cn='查询命令状态', risk_level='low')
def check_command_status(command_id: str, output_priority: str = 'bottom'):
    """查询后台命令的执行状态和输出内容。

    Args:
        command_id: 命令ID（由 start_command 返回）
        output_priority: 输出优先级，'bottom'显示最新输出，'top'显示最早输出，默认bottom
    """
    status_info = _CMD_MANAGER.get_status(command_id, output_priority)
    if not status_info:
        return {'error': f'命令ID {command_id} 不存在或已过期'}

    return {
        'command_id': command_id,
        'status': status_info['status'],
        'returncode': status_info.get('returncode'),
        'output': status_info['output'][:10000],
        'truncated': len(status_info['output']) > 10000,
        'elapsed': status_info['elapsed'],
        'cwd': status_info['cwd'],
    }


@register_tool(id='stop_command', category='system', name_cn='终止后台命令', risk_level='medium')
def stop_command_tool(command_id: str):
    """终止一个正在运行的后台命令。

    Args:
        command_id: 要终止的命令ID
    """
    success = _CMD_MANAGER.stop_command(command_id)
    if success:
        return {'command_id': command_id, 'status': 'stopped', 'message': f'命令 {command_id} 已终止'}
    else:
        return {'command_id': command_id, 'error': f'命令 {command_id} 不存在或已结束'}


@register_tool(id='get_system_logs', category='system', name_cn='系统日志', risk_level='low')
def get_system_logs(log_type: str = 'syslog', lines: int = 50):
    """获取系统日志内容，支持查看系统日志、认证日志、内核日志等。当用户需要排查系统问题时使用。

    Args:
        log_type: 日志类型，可选 syslog(系统日志)、auth(认证日志)、kern(内核日志)、nginx(Nginx日志)，默认syslog
        lines: 返回的日志行数，默认50
    """
    is_windows = os.name == 'nt'

    if is_windows:
        log_sources = {
            'syslog': 'System',
            'auth': 'Security',
            'application': 'Application',
        }
        source = log_sources.get(log_type, 'System')
        try:
            out, err = RunCommand(
                f'wevtutil qe {source} /c:{lines} /rd:true /f:text 2>nul',
                timeout=15,
            )
            if not out.strip():
                out = f'Windows 事件日志 "{source}" 中暂无记录或需要管理员权限。'
            return {
                'log_type': log_type,
                'log_source': source,
                'lines': lines,
                'content': out[:10000],
            }
        except Exception as e:
            return {'error': f'读取 Windows 事件日志失败: {str(e)}'}
    else:
        log_paths = {
            'syslog': '/var/log/syslog',
            'auth': '/var/log/auth.log',
            'kern': '/var/log/kern.log',
            'nginx_access': '/var/log/nginx/access.log',
            'nginx_error': '/var/log/nginx/error.log',
            'messages': '/var/log/messages',
            'secure': '/var/log/secure',
        }

        log_file = log_paths.get(log_type)
        if not log_file:
            available = ', '.join(log_paths.keys())
            return {'error': f'不支持的日志类型: {log_type}，可用类型: {available}'}

        if not os.path.exists(log_file):
            return {'error': f'日志文件不存在: {log_file}'}

        try:
            out, err = RunCommand(f'tail -n {lines} {log_file}', timeout=10)
            return {
                'log_type': log_type,
                'log_file': log_file,
                'lines': lines,
                'content': out[:10000],
            }
        except Exception as e:
            return {'error': f'读取日志失败: {str(e)}'}
