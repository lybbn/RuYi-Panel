#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-04-22
# +-------------------------------------------------------------------
# | EditDate: 2024-08-18
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Redis安装/卸载
# ------------------------------

import os
import re
import time
from utils.common import ReadFile,is_service_running,GetTmpPath,GetInstallPath,WriteFile,DeleteFile,GetLogsPath,RunCommandReturnCode,GetPidCpuPercent,RunCommand,GetProcessNameInfo
from utils.security.files import download_url_file,get_file_name_from_url
from pathlib import Path
import subprocess
import importlib
from utils.server.system import system
from utils.ruyiclass.redisClass import RedisClient
from django.conf import settings
from apps.systask.subprocessMg import job_subprocess_add,job_subprocess_del

def get_redis_path_info():
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,'redis')
    install_path = root_path+'/redis'
    log_path = install_path
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'windows_abspath_exe_path':os.path.join(install_abspath_path,'redis-server.exe'),
        'windows_abspath_cli_exe_path':os.path.join(install_abspath_path,'redis-cli.exe'),
        'linux_abspath_exe_path':os.path.join(install_abspath_path,'redis-server'),
        'linux_abspath_cli_path':os.path.join(install_abspath_path,'redis-cli'),
        'abspath_conf_path':os.path.join(install_abspath_path,'redis.conf'),
        'pid_path':os.path.join(install_path,'redis.pid'),
        'log_abspath_path':install_abspath_path,
        'log_path':log_path,
        'log_file_path':log_path+'/redis.log',
    }

def redis_install_call_back(version={},call_back=None,ok=True):
    if call_back:
        job_id = version['job_id']
        job_subprocess_del(job_id)
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id,version=version,ok=ok)
    
def Install_Redis(type=2,version={},is_windows=True,call_back=None):
    """
    @name 安装Redis
    @parma call_back 为执行回调函数的方法路径
    @author lybbn<2024-08-18>
    """
    try:
        name = version['name']
        log = version.get('log',None)#是否开启日志
        is_write_log = False
        log_path = ""
        if log:
            is_write_log = True
            log_path = os.path.join(os.path.abspath(GetLogsPath()),name,log)
        WriteFile(log_path,"-------------------安装任务已开始-------------------\n",mode='a',write=is_write_log)
        #检测系统是否已安装过redis（主要检测6379端口是否被占用）
        if is_service_running(6379):
            error_msg = "[error]检测到本机已安装并开启了redis服务，请关闭后再试!!!"
            raise ValueError(error_msg)
        download_url = version.get('url',None)
        WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
        filename = get_file_name_from_url(download_url)
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_redis_path_info()
        install_base_directory = soft_paths['root_abspath_path']
        install_directory = soft_paths['install_abspath_path']
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        save_path = os.path.join(save_directory, filename)
        #开始下载
        ok,msg = download_url_file(url=download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
        if not ok:
            WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
            raise ValueError(msg)
        if is_windows:
            WriteFile(log_path,"【%s】下载完成\n"%filename,mode='a',write=is_write_log)
            src_folder = os.path.join(install_base_directory,Path(filename).stem)
            WriteFile(log_path,"正在解压安装文件到%s\n"%install_directory,mode='a',write=is_write_log)
            # 如果目标文件夹已经存在，先删除它
            system.ForceRemoveDir(install_directory)
            from apps.systask.tasks import func_unzip
            func_unzip(save_path,install_directory)
            # 重命名源文件夹为目标文件夹
            # os.rename(src_folder, install_directory)
            WriteFile(log_path,"解压成功\n",mode='a',write=is_write_log)
            # 新建版本文件
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(log_path,"正在配置redis...\n",mode='a',write=is_write_log)
        else:
            r_process = subprocess.Popen(['bash', GetInstallPath()+'/ruyi/utils/install/bash/redis.sh','install',version['c_version']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,bufsize=1, preexec_fn=os.setsid)
            job_subprocess_add(version['job_id'],r_process)
            # 持续读取输出
            while True:
                r_output = r_process.stdout.readline()
                if r_output == '' and r_process.poll() is not None:
                    break
                if r_output:
                    WriteFile(log_path,f"{r_output.strip()}\n",mode='a',write=is_write_log)
                time.sleep(0.1)

            # 获取标准错误
            r_stderr = r_process.stderr.read()
            if r_stderr:
                if not os.path.exists(soft_paths['install_path']+'/redis-cli'):
                    raise ValueError(r_stderr.strip())
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
        
        RY_SET_DEFAULT_REDIS_CONFIG(is_windows=is_windows)
        
        # 删除下载的文件
        DeleteFile(save_path,empty_tips=False)
        WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        version['install_path'] = install_directory
        redis_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"正在启动redis服务...\n",mode='a',write=is_write_log)
        Start_Redis(is_windows=is_windows)
        WriteFile(log_path,"reids启动成功\n",mode='a',write=is_write_log)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        redis_install_call_back(version=version,call_back=call_back,ok=False)
        return False

def Uninstall_Redis(is_windows=True):
    """
    @name 卸载Redis
    @author lybbn<2024-08-18>
    """
    soft_paths = get_redis_path_info()
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            Stop_Redis(is_windows=is_windows)
            time.sleep(0.1)
            system.ForceRemoveDir(install_path)
    else:
        try:
            subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","redis.sh"),'uninstall'], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True

def is_redis_running(is_windows=True,simple_check=False):
    soft_paths = get_redis_path_info()
    conf_path = soft_paths['abspath_conf_path']
    c_content = ReadFile(conf_path)
    if not c_content:
        return False
    port = int(re.findall(r'\n\s*port\s+(\d+)', c_content)[0])
    if simple_check:
        if is_service_running(port):
            return True
        return False
    if not is_service_running(port):
        return False
    soft_name ='redis-server.exe' if is_windows else "redis-server"
    # if is_windows:
    #     result = subprocess.run([soft_paths['windows_abspath_cli_exe_path'], 'ping'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #     return result.stdout.decode().strip() == 'PONG'
    # else:
    info_list = GetProcessNameInfo(soft_name,{},is_windows=is_windows)
    if len(info_list)>0:
        return True
    return False

def Start_Redis(is_windows=True):
    """
    @name 启动redis
    @author lybbn<2024-08-18>
    """
    soft_paths = get_redis_path_info()
    conf_path = soft_paths['abspath_conf_path']
    if is_windows:
        exe_path = soft_paths['windows_abspath_exe_path']
        r_status = False
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if not is_redis_running(is_windows=True):
                    subprocess.Popen([exe_path, conf_path],cwd=soft_paths['install_path'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)#CREATE_NEW_CONSOLE 新窗口 、CREATE_NO_WINDOW 隐藏窗口
                else:
                    r_status = True
                time.sleep(2)
                if not r_status and is_redis_running(is_windows=True):
                    r_status = True
            except Exception as e:
                raise ValueError(f"启动Redis时发生错误: {e}")
            if not r_status:
                raise ValueError(f"Redis启动错误")
        else:
            raise ValueError(f"Redis未安装")
    else:
        exe_path = soft_paths['linux_abspath_exe_path']
        r_status = False
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if not is_redis_running(is_windows=False,simple_check=True):
                    subprocess.run(["systemctl", "start", "redis"], check=True,timeout=15)
                else:
                    r_status = True
                time.sleep(1)
                if not r_status and is_redis_running(is_windows=False,simple_check=True):
                    r_status = True
            except Exception as e:
                raise ValueError(f"启动Redis时发生错误: {e}")
            if not r_status:
                raise ValueError(f"Redis启动错误")
        else:
            raise ValueError(f"Redis未安装")

def Stop_Redis(is_windows=True):
    """
    @name 停止redis
    @author lybbn<2024-08-18>
    """
    # soft_paths = get_redis_path_info()
    # if is_windows:
    #     cli_path = soft_paths['windows_abspath_cli_exe_path']
    # else:
    #     cli_path = soft_paths['linux_abspath_cli_path']
    try:
        if is_redis_running(is_windows=is_windows):
            # code = RunCommandReturnCode([cli_path,"shutdown"],cwd=soft_paths['install_path'])
            # return True if code == 0 else False
            db_conn = Redis_Connect()
            if not db_conn:
                raise ValueError("连接失败")
            db_conn.shutdown()
            return True
        return True
    except subprocess.CalledProcessError as e:
        raise ValueError(f"停止Redis时发生错误: {e}")
        
def Restart_Redis(is_windows=True):
    """
    @name 重启redis
    @author lybbn<2024-08-18>
    """
    Stop_Redis(is_windows=is_windows)
    time.sleep(0.1)
    Start_Redis(is_windows=is_windows)

def RY_GET_REDIS_CONF(is_windows=True):
    soft_paths = get_redis_path_info()
    conf_path = soft_paths['abspath_conf_path']
    return ReadFile(conf_path)

def RY_GET_REDIS_PORT(is_windows=True):
    conf_options = RY_GET_REDIS_CONF_OPTIONS(is_windows=is_windows)
    return conf_options['port']

def RY_SAVE_REDIS_CONF(conf="",is_windows=True):
    soft_paths = get_redis_path_info()
    conf_path = soft_paths['abspath_conf_path']
    WriteFile(conf_path,content=conf)

def RY_GET_REDIS_CONF_OPTIONS(is_windows=True):
    conf = RY_GET_REDIS_CONF(is_windows=is_windows)
    if not conf:
        return False
    result = {}
    get_keys = ["bind", "port", "timeout", "maxclients", "databases", "requirepass", "maxmemory"]
    for k in get_keys:
        val = ""
        rep = r"\n%s\s+(.+)" % k
        re_res = re.search(rep, conf)
        if not re_res:
            if k == "maxmemory":
                val = "0"
            if k == "maxclients":
                val = "10000"
            if k == "requirepass":
                val = ""
        else:
            if k == "maxmemory":
                val = int(re_res.group(1)) / 1024 / 1024
            else:
                val = re_res.group(1)
        result[k] = val
    return result

def Redis_Connect(db_host="127.0.0.1",db_port=6379,db_password="",db=0,socket_connect_timeout=5,socket_timeout=3,max_connections=10,local=True,preload=False,db_nums=16):
    """
    连接redis
    @db 连接哪个数据库的索引
    @max_connections 设置最大连接数 
    return 数据库连接
    """
    conf_options = {}
    if local:
        conf_options = RY_GET_REDIS_CONF_OPTIONS()
        if not conf_options:
            return None
        db_nums = conf_options['databases']
    if preload:
        RedisClient.preload_redis_connections(db_host=db_host,db_port=db_port,db_password=db_password,db=db,socket_connect_timeout=socket_connect_timeout,socket_timeout=socket_timeout,max_connections=max_connections,local=local,localOptions=conf_options,db_nums=db_nums)
    db_conn = RedisClient.get_client(db_host=db_host,db_port=db_port,db_password=db_password,db=db,socket_connect_timeout=socket_connect_timeout,socket_timeout=socket_timeout,max_connections=max_connections,local=local,localOptions=conf_options)
    return db_conn
    
def RY_GET_REDIS_LOADSTATUS(is_windows=True):
    if is_redis_running(is_windows=is_windows):
        try:
            soft_paths = get_redis_path_info()
            conf_path = soft_paths['abspath_conf_path']
            c_content = ReadFile(conf_path)
            if not c_content:
                raise ValueError("redis未安装")
            port = int(re.findall(r'\n\s*port\s+(\d+)', c_content)[0])
            password = re.findall(r'\n\s*requirepass\s+(.+)', c_content)
            if password:
                password = password[0]
            else:
                password = ''
            import redis
            r = redis.Redis(host='localhost', port=port, db=0,password=password)
            redis_info = r.info()
            data = {
                'redis_version':redis_info['redis_version'],
                'os':redis_info['os'],
                'role':redis_info['role'],
                'tcp_port':redis_info['tcp_port'],
                'uptime_in_days':redis_info['uptime_in_days'],
                'config_file':redis_info['config_file'],
                'connected_clients':redis_info['connected_clients'],
                'used_memory':redis_info['used_memory'],
                'used_memory_human':redis_info['used_memory_human'],
                'used_memory_rss':redis_info['used_memory_rss'],
                'used_memory_peak_human':redis_info['used_memory_peak_human'],
                'mem_fragmentation_ratio':redis_info['mem_fragmentation_ratio'],
                'aof_enabled':"否" if redis_info['aof_enabled'] == 0 else "是",
                'used_cpu_sys':redis_info['used_cpu_sys'],
                'used_cpu_user':redis_info['used_cpu_user'],
                'used_cpu_sys_children':redis_info['used_cpu_sys_children'],
                'used_cpu_user_children':redis_info['used_cpu_user_children'],
                'latest_fork_usec':redis_info['latest_fork_usec'],
                'total_connections_received':redis_info['total_connections_received'],
                'total_commands_processed':redis_info['total_commands_processed'],
                'instantaneous_ops_per_sec':redis_info['instantaneous_ops_per_sec'],
                'total_net_input_bytes':redis_info['total_net_input_bytes'],
                'total_net_output_bytes':redis_info['total_net_output_bytes'],
                'instantaneous_input_kbps':redis_info['instantaneous_input_kbps'],
                'instantaneous_output_kbps':redis_info['instantaneous_output_kbps'],
                'keyspace_hits':redis_info['keyspace_hits'],
                'keyspace_misses':redis_info['keyspace_misses'],
                'keyspace_misses':redis_info['keyspace_misses'],
            }
            return data
        except Exception as e:
            raise ValueError("redis连接失败")
    else:
        raise ValueError("redis未运行")

def RY_SET_DEFAULT_REDIS_CONFIG(is_windows=True):
    soft_paths = get_redis_path_info()
    log_file_path = soft_paths['log_file_path']
    pid_file_path = soft_paths['pid_path']
    install_path = soft_paths['install_path']
    conf_path = soft_paths['abspath_conf_path']
    new_port = 6379
    new_password = ''
    new_ip = '127.0.0.1'
    if is_windows:
        log_file_path = '"redis.log"'
        pid_file_path = str(Path(pid_file_path).resolve()).replace("\\","\\\\")
        install_path = str(Path(install_path).resolve()).replace("\\","\\\\")
        exam_conf_path = install_path+"/redis.windows.conf"
    else:
        exam_conf_path = conf_path

    # 读取配置文件
    with open(exam_conf_path, 'r', encoding='utf-8') as file:
        config_lines = file.readlines()
    # 写入新的配置文件
    with open(conf_path, 'w',encoding="utf-8") as file:
        for line in config_lines:
            # 替换密码
            if line.startswith('requirepass '):
                file.write(f'requirepass {new_password}\n')
            # 替换端口
            elif line.startswith('port '):
                file.write(f'port {new_port}\n')
            # 替换绑定 IP 地址
            elif line.startswith('bind '):
                file.write(f'bind {new_ip}\n')
            # 替换日志文件路径
            elif line.startswith('logfile '):
                file.write(f'logfile {log_file_path}\n')
            # 替换 PID 文件路径
            elif "pidfile " in line:
                file.write(f'{line}\npidfile {pid_file_path}\n')
            elif line.startswith('pidfile '):
                file.write(f'')
            # 替换数据目录
            elif line.startswith('dir '):
                file.write(f'dir {install_path}\n')
            else:
                file.write(line)