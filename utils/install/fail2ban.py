#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-25
# +-------------------------------------------------------------------
# | EditDate: 2025-02-25
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Fail2Ban 安装/卸载
# ------------------------------

import os
import time
import subprocess
from utils.common import (
    ReadFile, WriteFile, DeleteDir, GetTmpPath, GetInstallPath,
    RunCommand, RunCommandReturnCode, ConvertToUnixLineEndings,GetLogsPath,CreateInstallProcess,CleanupInstallProcess,SafeReadStderr,ReleaseMemory
)
from utils.security.files import download_url_file
from django.conf import settings
from apps.systask.subprocessMg import job_subprocess_add
import importlib

def get_fail2ban_path_info():
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path, "fail2ban")
    install_path = root_path + "/fail2ban"
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path': install_abspath_path,
        'install_path': install_path,
        'bin_path': os.path.join(install_abspath_path, 'bin'),
        'pid_path': '/var/run/fail2ban/fail2ban.pid',
        'socket_path': '/var/run/fail2ban/fail2ban.sock',
        'config_path': '/etc/fail2ban',
        'jail_config_path': '/etc/fail2ban/jail.local',
        'log_path': '/var/log/fail2ban.log',
        'data_config_path': os.path.join(settings.RUYI_DATA_BASE_PATH, "fail2ban"),
    }

def fail2ban_install_call_back(version={}, call_back=None, ok=True):
    if call_back:
        job_id = version.get('job_id')
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id, version=version, ok=ok)

def check_fail2ban_version():
    try:
        result = subprocess.run(
            ['fail2ban-server', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version_line = result.stdout.strip().split('\n')[0]
            return version_line.replace('Fail2Ban', '').strip().split()[0] if version_line else None
        return None
    except:
        return None

def is_fail2ban_running():
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'fail2ban'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0 and result.stdout.strip() == 'active'
    except:
        return False

def is_fail2ban_installed():
    paths = get_fail2ban_path_info()
    if os.path.exists(paths['install_abspath_path']):
        return True
    if os.path.exists('/usr/bin/fail2ban-server'):
        return True
    return False

def get_fail2ban_status():
    installed = is_fail2ban_installed()
    running = is_fail2ban_running() if installed else False
    version = check_fail2ban_version() if installed else None
    return {
        'installed': installed,
        'running': running,
        'version': version
    }

def Install_Fail2Ban(version={}, call_back=None):
    try:
        name = version.get('name', 'fail2ban')
        log = version.get('log', None)
        is_write_log = False
        log_path = ""
        if log:
            is_write_log = True
            log_path = os.path.join(os.path.abspath(GetLogsPath()), name, log)
        
        WriteFile(log_path, "-------------------安装任务已开始-------------------\n", mode='a', write=is_write_log)
        
        soft_paths = get_fail2ban_path_info()
        install_directory = soft_paths['install_abspath_path']
        
        WriteFile(log_path, "开始安装Fail2Ban...\n", mode='a', write=is_write_log)
        
        script_path = os.path.join(settings.BASE_DIR, "utils", "install", "bash", "fail2ban.sh")
        ConvertToUnixLineEndings(script_path)
        
        r_process = CreateInstallProcess(
            ['bash', script_path, 'install', version.get('c_version', 'auto'), '']
        )
        job_subprocess_add(version['job_id'], r_process)
        try:
            while True:
                r_output = r_process.stdout.readline()
                if r_output == '' and r_process.poll() is not None:
                    break
                if r_output:
                    WriteFile(log_path, f"{r_output.strip()}\n", mode='a', write=is_write_log)
                time.sleep(0.1)
            r_stderr = SafeReadStderr(r_process)
            if r_stderr:
                WriteFile(log_path, f"[stderr] {r_stderr.strip()[:2000]}\n", mode='a', write=is_write_log)
        finally:
            CleanupInstallProcess(r_process, version['job_id'])
            r_process = None
        
        if not is_fail2ban_installed():
            raise Exception("Fail2Ban安装失败")
        
        version_file = os.path.join(install_directory, 'version.ry')
        WriteFile(version_file, version.get('c_version', 'auto'))
        
        WriteFile(log_path, "安装成功，安装目录：%s\n" % install_directory, mode='a', write=is_write_log)
        WriteFile(log_path, "启动中...\n", mode='a', write=is_write_log)
        
        Start_Fail2Ban()
        
        WriteFile(log_path, "启动成功\n", mode='a', write=is_write_log)
        
        version['install_path'] = install_directory
        fail2ban_install_call_back(version=version, call_back=call_back, ok=True)
        
        WriteFile(log_path, "-------------------安装任务已结束-------------------\n", mode='a', write=is_write_log)
        version.clear()
        soft_paths.clear()
        ReleaseMemory()
        return True
        
    except Exception as e:
        WriteFile(log_path, f"【错误】异常信息如下：\n{e}\n", mode='a', write=is_write_log)
        fail2ban_install_call_back(version=version, call_back=call_back, ok=False)
        version.clear()
        ReleaseMemory()
        return False

def Uninstall_Fail2Ban():
    soft_paths = get_fail2ban_path_info()
    try:
        script_path = os.path.join(settings.BASE_DIR, "utils", "install", "bash", "fail2ban.sh")
        ConvertToUnixLineEndings(script_path)
        subprocess.run(['bash', script_path, 'uninstall'], capture_output=False, text=True)
        return True
    except Exception as e:
        raise ValueError(e)

def Start_Fail2Ban():
    try:
        result = subprocess.run(
            ['systemctl', 'start', 'fail2ban'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            raise ValueError(f"启动失败: {result.stderr}")
        time.sleep(1)
        return is_fail2ban_running()
    except Exception as e:
        raise ValueError(f"启动Fail2Ban时发生错误: {e}")

def Stop_Fail2Ban():
    try:
        subprocess.run(
            ['systemctl', 'stop', 'fail2ban'],
            capture_output=True,
            text=True,
            timeout=30
        )
        return True
    except Exception as e:
        raise ValueError(f"停止Fail2Ban时发生错误: {e}")

def Restart_Fail2Ban():
    try:
        subprocess.run(
            ['systemctl', 'restart', 'fail2ban'],
            capture_output=True,
            text=True,
            timeout=30
        )
        time.sleep(1)
        return is_fail2ban_running()
    except Exception as e:
        raise ValueError(f"重启Fail2Ban时发生错误: {e}")

def Reload_Fail2Ban():
    try:
        subprocess.run(
            ['fail2ban-client', 'reload'],
            capture_output=True,
            text=True,
            timeout=30
        )
        return True
    except Exception as e:
        raise ValueError(f"重载Fail2Ban配置时发生错误: {e}")

def Get_Fail2Ban_Jail_Status(jail_name='sshd'):
    try:
        result = subprocess.run(
            ['fail2ban-client', 'status', jail_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except:
        return None

def Get_Fail2Ban_Banned_IPs(jail_name='sshd'):
    try:
        result = subprocess.run(
            ['fail2ban-client', 'status', jail_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            output = result.stdout
            banned_list = []
            if 'Banned IP list:' in output:
                ips_part = output.split('Banned IP list:')[1].strip()
                if ips_part:
                    banned_list = [ip.strip() for ip in ips_part.split() if ip.strip()]
            return banned_list
        return []
    except:
        return []

def Get_Fail2Ban_Banned_IPs_With_Details(jail_name='sshd'):
    """获取封禁IP列表，包含剩余时间等详细信息
    
    从 fail2ban 数据库查询封禁记录，计算剩余时间
    """
    import sqlite3
    import time
    
    try:
        # 获取封禁列表
        result = subprocess.run(
            ['fail2ban-client', 'status', jail_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return []
        
        output = result.stdout
        banned_list = []
        if 'Banned IP list:' in output:
            ips_part = output.split('Banned IP list:')[1].strip()
            if ips_part:
                banned_list = [ip.strip() for ip in ips_part.split() if ip.strip()]
        
        if not banned_list:
            return []
        
        # 获取 jail 的 bantime 配置
        bantime_result = subprocess.run(
            ['fail2ban-client', 'get', jail_name, 'bantime'],
            capture_output=True,
            text=True,
            timeout=5
        )
        bantime = 3600  # 默认1小时
        if bantime_result.returncode == 0:
            try:
                bantime = int(bantime_result.stdout.strip())
            except:
                pass
        
        # 从数据库查询封禁时间
        db_path = '/var/lib/fail2ban/fail2ban.sqlite3'
        ban_times = {}
        
        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # 查询 bans 表获取封禁时间
                cursor.execute(
                    "SELECT ip, timeofban FROM bans WHERE jail = ?",
                    (jail_name,)
                )
                rows = cursor.fetchall()
                for row in rows:
                    ip, timeofban = row
                    ban_times[ip] = timeofban
                
                conn.close()
        except Exception as e:
            print(f"Read fail2ban db error: {e}")
        
        # 计算剩余时间
        current_time = time.time()
        banned_details = []
        
        for ip in banned_list:
            ban_time = ban_times.get(ip, 0)
            if ban_time > 0:
                # 计算剩余时间 = 封禁时长 - (当前时间 - 封禁开始时间)
                elapsed = current_time - ban_time
                remaining = max(0, bantime - elapsed)
            else:
                # 如果数据库中没有记录，假设刚封禁
                remaining = bantime
            
            banned_details.append({
                'ip': ip,
                'remaining_time': int(remaining),
                'ban_time': ban_time,
                'jail': jail_name
            })
        
        return banned_details
    except Exception as e:
        print(f"Get banned IPs with details error: {e}")
        return []

def Ban_IP(ip, jail_name='sshd'):
    try:
        result = subprocess.run(
            ['fail2ban-client', 'set', jail_name, 'banip', ip],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

def Unban_IP(ip, jail_name='sshd'):
    try:
        result = subprocess.run(
            ['fail2ban-client', 'set', jail_name, 'unbanip', ip],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

def Get_Fail2Ban_Jails():
    try:
        result = subprocess.run(
            ['fail2ban-client', 'status'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            output = result.stdout
            jails = []
            if 'Jail list:' in output:
                jails_part = output.split('Jail list:')[1].strip()
                if jails_part:
                    jails = [j.strip() for j in jails_part.split(',') if j.strip()]
            return jails
        return []
    except:
        return []

def Read_Jail_Config():
    paths = get_fail2ban_path_info()
    config_path = paths['jail_config_path']
    if os.path.exists(config_path):
        return ReadFile(config_path)
    return ""

def Write_Jail_Config(content):
    paths = get_fail2ban_path_info()
    config_path = paths['jail_config_path']
    config_dir = os.path.dirname(config_path)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    WriteFile(config_path, content)
    Reload_Fail2Ban()
    return True

def Toggle_Jail(jail_name, enabled):
    """启用或禁用指定的 jail"""
    try:
        config_content = Read_Jail_Config()
        if not config_content:
            return False
        
        # 检查是否已存在该 jail 配置
        jail_exists = f'[{jail_name}]' in config_content
        
        if not jail_exists:
            # 如果 jail 不存在，创建新的 jail 配置
            jail_config = _get_default_jail_config(jail_name)
            jail_config['enabled'] = str(enabled).lower()
            
            # 追加到配置文件末尾
            new_section = f"\n\n[{jail_name}]\n"
            for key, value in jail_config.items():
                new_section += f"{key} = {value}\n"
            
            config_content = config_content.rstrip() + new_section
            Write_Jail_Config(config_content)
            return True
        
        # 解析配置
        lines = config_content.split('\n')
        new_lines = []
        in_target_jail = False
        jail_start_idx = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 检查是否是目标 jail 的节
            if stripped == f'[{jail_name}]':
                in_target_jail = True
                jail_start_idx = i
                new_lines.append(line)
                continue
            
            # 检查是否进入下一个节
            if in_target_jail and stripped.startswith('[') and stripped.endswith(']'):
                in_target_jail = False
            
            # 在目标 jail 节内处理 enabled 配置
            if in_target_jail and stripped.startswith('enabled'):
                new_lines.append(f'enabled = {str(enabled).lower()}')
                continue
            
            new_lines.append(line)
        
        # 如果在 jail 节内没有找到 enabled，添加它
        if in_target_jail and jail_start_idx >= 0:
            has_enabled = False
            for i in range(jail_start_idx, len(new_lines)):
                if new_lines[i].strip().startswith('[') and i > jail_start_idx:
                    break
                if new_lines[i].strip().startswith('enabled'):
                    has_enabled = True
                    break
            if not has_enabled:
                new_lines.insert(jail_start_idx + 1, f'enabled = {str(enabled).lower()}')
        
        Write_Jail_Config('\n'.join(new_lines))
        return True
    except Exception as e:
        print(f"Toggle jail error: {e}")
        return False

def _get_default_jail_config(jail_name):
    """获取默认的 jail 配置"""
    default_configs = {
        'sshd': {
            'enabled': 'false',
            'port': 'ssh',
            'filter': 'sshd',
            'logpath': '/var/log/secure',
            'maxretry': '5',
            'bantime': '3600',
            'findtime': '600'
        },
        'mysqld': {
            'enabled': 'false',
            'port': '3306',
            'filter': 'mysqld-auth',
            'logpath': '/var/log/mysql/error.log',
            'maxretry': '5',
            'bantime': '3600',
            'findtime': '600'
        }
    }
    return default_configs.get(jail_name, {
        'enabled': 'false',
        'maxretry': '5',
        'bantime': '3600',
        'findtime': '600'
    })

def Set_Jail_Config(jail_name, maxretry=5, bantime=3600, findtime=600, port=None):
    """设置 jail 的配置参数"""
    try:
        config_content = Read_Jail_Config()
        if not config_content:
            return False
        
        lines = config_content.split('\n')
        new_lines = []
        in_target_jail = False
        jail_start_idx = -1
        config_keys = {'maxretry', 'bantime', 'findtime'}
        if port is not None:
            config_keys.add('port')
        updated_keys = set()
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 检查是否是目标 jail 的节
            if stripped == f'[{jail_name}]':
                in_target_jail = True
                jail_start_idx = i
                new_lines.append(line)
                continue
            
            # 检查是否进入下一个节
            if in_target_jail and stripped.startswith('[') and stripped.endswith(']'):
                in_target_jail = False
            
            # 在目标 jail 节内处理配置
            if in_target_jail:
                for key in config_keys:
                    if stripped.startswith(key):
                        if key == 'maxretry':
                            new_lines.append(f'maxretry = {maxretry}')
                        elif key == 'bantime':
                            new_lines.append(f'bantime = {bantime}')
                        elif key == 'findtime':
                            new_lines.append(f'findtime = {findtime}')
                        elif key == 'port' and port is not None:
                            new_lines.append(f'port = {port}')
                        updated_keys.add(key)
                        break
                else:
                    new_lines.append(line)
                continue
            
            new_lines.append(line)
        
        # 添加未更新的配置项
        if in_target_jail and jail_start_idx >= 0:
            remaining_keys = config_keys - updated_keys
            insert_idx = len(new_lines)
            # 找到 jail 节的结束位置
            for i in range(jail_start_idx + 1, len(new_lines)):
                if new_lines[i].strip().startswith('['):
                    insert_idx = i
                    break
            
            for key in remaining_keys:
                if key == 'maxretry':
                    new_lines.insert(insert_idx, f'maxretry = {maxretry}')
                elif key == 'bantime':
                    new_lines.insert(insert_idx, f'bantime = {bantime}')
                elif key == 'findtime':
                    new_lines.insert(insert_idx, f'findtime = {findtime}')
                elif key == 'port' and port is not None:
                    new_lines.insert(insert_idx, f'port = {port}')
        
        Write_Jail_Config('\n'.join(new_lines))
        return True
    except Exception as e:
        print(f"Set jail config error: {e}")
        return False

def Get_Ignore_IP_List():
    """获取白名单IP列表"""
    try:
        config_content = Read_Jail_Config()
        if not config_content:
            return []
        
        for line in config_content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('ignoreip'):
                value = stripped.split('=', 1)[1].strip()
                ips = [ip.strip() for ip in value.split() if ip.strip()]
                return ips
        return []
    except:
        return []

def Add_Ignore_IP(ip):
    """添加IP到白名单"""
    try:
        config_content = Read_Jail_Config()
        if not config_content:
            return False
        
        lines = config_content.split('\n')
        new_lines = []
        updated = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('ignoreip'):
                current_value = stripped.split('=', 1)[1].strip()
                ips = [i.strip() for i in current_value.split() if i.strip()]
                if ip not in ips:
                    ips.append(ip)
                new_lines.append(f'ignoreip = {" ".join(ips)}')
                updated = True
            else:
                new_lines.append(line)
        
        # 如果没有找到 ignoreip 行，在 DEFAULT 节添加
        if not updated:
            default_idx = -1
            for i, line in enumerate(new_lines):
                if line.strip() == '[DEFAULT]':
                    default_idx = i
                    break
            if default_idx >= 0:
                new_lines.insert(default_idx + 1, f'ignoreip = {ip}')
            else:
                # 在文件开头添加 DEFAULT 节
                new_lines.insert(0, '[DEFAULT]')
                new_lines.insert(1, f'ignoreip = {ip}')
        
        Write_Jail_Config('\n'.join(new_lines))
        return True
    except Exception as e:
        print(f"Add ignore IP error: {e}")
        return False

def Remove_Ignore_IP(ip):
    """从白名单移除IP"""
    try:
        config_content = Read_Jail_Config()
        if not config_content:
            return False
        
        lines = config_content.split('\n')
        new_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('ignoreip'):
                current_value = stripped.split('=', 1)[1].strip()
                ips = [i.strip() for i in current_value.split() if i.strip() and i.strip() != ip]
                if ips:
                    new_lines.append(f'ignoreip = {" ".join(ips)}')
            else:
                new_lines.append(line)
        
        Write_Jail_Config('\n'.join(new_lines))
        return True
    except Exception as e:
        print(f"Remove ignore IP error: {e}")
        return False
