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
# | EditDate: 2024-04-22
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Nginx安装/卸载
# ------------------------------

import os,re
import time
import requests
import psutil
from utils.common import ReadFile,is_service_running,GetTmpPath,GetInstallPath,WriteFile,DeleteFile,GetLogsPath,RunCommandReturnCode,GetPidCpuPercent,RunCommand,GetProcessNameInfo,GetRandomSet
from utils.security.files import download_url_file,get_file_name_from_url,get_github_quick_downloadurl
from pathlib import Path
from django.conf import settings
import subprocess
import importlib
from utils.server.system import system
from apps.systask.subprocessMg import job_subprocess_add,job_subprocess_del

def get_nginx_path_info():
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,'nginx')
    install_path = root_path+'/nginx'
    log_path = install_path+'/logs'
    return {
        'name':"nginx",
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'windows_abspath_exe_path':os.path.join(install_abspath_path,'nginx.exe'),
        'w_nginx_server':os.path.join(install_abspath_path,'nginx_server.exe'),
        'abspath_conf_path':os.path.join(install_abspath_path,'conf','nginx.conf'),
        'abspath_tmpconf_path':os.path.join(install_abspath_path,'conf','nginx_tmp.conf'),
        'linux_exe_path':os.path.join(install_abspath_path,"sbin",'nginx'),
        'log_abspath_path':os.path.join(install_abspath_path,'logs'),
        'log_path':log_path,
        'access_log_path':log_path+'/access.log',
        'error_log_path':log_path+'/error.log'
    }

def nginx_install_call_back(version={},call_back=None,ok=True):
    if call_back:
        job_id = version['job_id']
        job_subprocess_del(job_id)
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id,version=version,ok=ok)
    
def Install_Nginx(type=2,version={},is_windows=True,call_back=None):
    """
    @name 安装nginx
    @parma call_back 为执行回调函数的方法路径
    @author lybbn<2024-04-22>
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
        #检测系统是否已安装过nginx（主要检测80和443端口是否被占用）
        if is_service_running(80) or is_service_running(443):
            error_msg = "[error]检测到本机已安装并开启了http(s)服务，请关闭后再试!!!"
            WriteFile(log_path,error_msg+'\n',mode='a',write=is_write_log)
            raise ValueError(error_msg)
        download_url = version.get('url',None)
        WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
        filename = get_file_name_from_url(download_url)
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_nginx_path_info()
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
            from apps.systask.tasks import func_unzip
            func_unzip(save_path,install_base_directory)
            # 如果目标文件夹已经存在，先删除它
            system.ForceRemoveDir(install_directory)
            # 重命名源文件夹为目标文件夹
            os.rename(src_folder, install_directory)
            WriteFile(log_path,"解压成功\n",mode='a',write=is_write_log)
            # 新建版本文件
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(log_path,"正在配置nginx...\n",mode='a',write=is_write_log)
            WriteFile(soft_paths['abspath_conf_path'],RY_GET_NGINX_CONFIG(is_windows=True))
            WriteFile(soft_paths['install_path']+'/html/index.html',RY_GET_NGINX_INDEX_HTML())
        else:
            r_process = subprocess.Popen(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","nginx.sh"),'install',version['c_version'],version['version']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,bufsize=1, preexec_fn=os.setsid)
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
                if not os.path.exists(soft_paths['linux_exe_path']):
                    raise ValueError(r_stderr.strip())
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(log_path,"正在配置nginx...\n",mode='a',write=is_write_log)
            WriteFile(soft_paths['abspath_conf_path'],RY_GET_NGINX_CONFIG(is_windows=False))
            WriteFile(soft_paths['install_path']+'/html/index.html',RY_GET_NGINX_INDEX_HTML())
        
        # 删除下载的文件
        DeleteFile(save_path,empty_tips=False)
        WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
        if is_windows:
            #安装服务
            WriteFile(log_path,"正在安装nginx为系统服务...\n",mode='a',write=is_write_log)
            isok,msg = SET_WINDOWS_SERVICE(log_path=log_path)
            if not isok:
                raise Exception(msg)
            from utils.server.windows import install_as_service
            service_name = soft_paths['name']
            soft_exe_path = soft_paths['w_nginx_server']
            soft_args = ''
            isok, msg = install_as_service(name=service_name,display_name=service_name,path=soft_exe_path,args=soft_args,description="Nginx web service",start_type=2)
            if not isok:WriteFile(log_path,f"安装nginx系统服务失败：{msg}\n",mode='a',write=is_write_log)

        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        version['install_path'] = install_directory
        nginx_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"正在启动nginx服务...\n",mode='a',write=is_write_log)
        Start_Nginx(is_windows=is_windows)
        WriteFile(log_path,"nginx启动成功\n",mode='a',write=is_write_log)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        nginx_install_call_back(version=version,call_back=call_back,ok=False)
        return False

def Uninstall_Nginx(is_windows=True):
    """
    @name 卸载nginx
    @author lybbn<2024-04-22>
    """
    soft_paths = get_nginx_path_info()
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            Stop_Nginx(is_windows=is_windows)
            time.sleep(0.1)
            from utils.server.windows import uninstall_service
            uninstall_service("nginx")
            system.ForceRemoveDir(install_path)
    else:
        try:
            subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","nginx.sh"),'uninstall'], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True

def is_nginx_running(is_windows=True,simple_check=False):
    if simple_check:
        if is_service_running(80) or is_service_running(443):
            return True
        return False
    soft_paths = get_nginx_path_info()
    soft_name ='nginx' if is_windows else "nginx"
    if is_windows:
        log_path = soft_paths['log_path']
        pid_file = log_path+'/nginx.pid'
        """检查指定的 PID 文件是否对应一个正在运行的 Nginx 进程。"""
        from utils.server.windows import get_service_status
        if get_service_status("nginx") == 1:
            return True
        if not os.path.isfile(pid_file):
            return False
        try:
            with open(pid_file, 'r') as f:
                pid = f.read().strip()
            
            # 检查 PID 是否有效
            if not pid.isdigit():
                return False

            # 使用 tasklist 命令检查进程是否存在
            try:
                result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True)
                # 解析 tasklist 的输出
                return 'nginx.exe' in result.stdout
            except FileNotFoundError:
                # 在某些系统中，tasklist 可能不可用
                return False
        except Exception as e:
            print(f"检查进程失败: {e}")
            return False
    else:
        info_list = GetProcessNameInfo(soft_name,{},is_windows=is_windows)
        if len(info_list)>0:
            return True
        return False

def check_nginx_config(conf_path = None,is_windows=True):
    """
    @name 检查 Nginx 配置文件是否正确。
    @author lybbn<2024-04-22>
    :param conf_path: 要测试的 Nginx 配置文件路径
    :return: 如果配置文件正确，则返回 True，否则返回 False
    """
    try:
        soft_paths = get_nginx_path_info()
        exe_path = soft_paths['windows_abspath_exe_path'] if is_windows else soft_paths['linux_exe_path']
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if is_windows:
                    code = RunCommandReturnCode([exe_path,"-t", "-c",conf_path],cwd=soft_paths['install_path'])
                    return True if code == 0 else False
                else:
                    result = subprocess.run([exe_path,"-t", "-c",conf_path],capture_output=True, text=True, check=True)
                    return result.returncode == 0
            except Exception as e:
                raise ValueError(f"重载Nginx时发生错误: {e}")
        else:
            raise ValueError(f"Nginx未安装")
    except Exception as e:
        return False

def Start_Nginx(is_windows=True):
    """
    @name 启动nginx
    @author lybbn<2024-04-22>
    """
    soft_paths = get_nginx_path_info()
    if is_windows:
        exe_path = soft_paths['windows_abspath_exe_path']
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if not is_nginx_running(is_windows=True):
                    # 启动 Nginx
                    # code = RunCommandReturnCode("start nginx.exe",cwd=soft_paths['install_path'],env_path=soft_paths['install_path'])
                    # return True if code == 0 else False
                    from utils.server.windows import set_service_status
                    isok,msg = set_service_status("nginx","start")
                    if not isok:raise Exception(msg)
                    time.sleep(1)
                    if not is_nginx_running(is_windows=True):
                        return False
                return True
            except Exception as e:
                raise ValueError(f"启动Nginx时发生错误: {e}")
        else:
            raise ValueError(f"Nginx未安装")
    else:
        exe_path = soft_paths['linux_exe_path']
        r_status = False
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if not is_nginx_running(is_windows=False,simple_check=True):
                    subprocess.run(["systemctl", "start", "nginx"], check=True,timeout=15)
                else:
                    r_status = True
                time.sleep(1)
                if not r_status and is_nginx_running(is_windows=False,simple_check=True):
                    r_status = True
            except Exception as e:
                raise ValueError(f"启动Nginx时发生错误: {e}")
            if not r_status:
                raise ValueError(f"Nginx启动错误")
        else:
            raise ValueError(f"Nginx未安装")

def Stop_Nginx(is_windows=True):
    """
    @name 停止nginx
    @author lybbn<2024-04-22>
    """
    soft_paths = get_nginx_path_info()
    if is_windows:
        exe_path = soft_paths['windows_abspath_exe_path']
        try:
            if is_nginx_running(is_windows=True):
                # code = RunCommandReturnCode([exe_path,"-s", "stop"],cwd=soft_paths['install_path'])
                # return True if code == 0 else False
                from utils.server.windows import set_service_status
                isok,msg = set_service_status("nginx","stop")
                if not isok:raise Exception(msg)
                time.sleep(1)
                if is_nginx_running(is_windows=True):
                    return False
            return True
        except Exception as e:
            raise ValueError(f"停止Nginx时发生错误: {e}")
    else:
        if is_nginx_running(is_windows=is_windows):
            try:
                subprocess.run(["sudo", "systemctl", "stop", "nginx"], check=True)
                time.sleep(1)
                if is_nginx_running(is_windows=False):
                    return False
                else:
                    return True
            except Exception as e:
                raise ValueError(f"停止Nginx时发生错误: {e}")
        # try:
        #     # 查找 Nginx 进程 ID
        #     result = subprocess.run(["ps", "-aux"], capture_output=True, text=True, check=True)
        #     nginx_processes = [line for line in result.stdout.splitlines() if "nginx: master process" in line]

        #     # 从进程信息中提取 PID 并停止 Nginx
        #     for process in nginx_processes:
        #         pid = process.split()[1]
        #         subprocess.run(["sudo", "kill", "-QUIT", pid], check=True)
        #     return True
        # except:
        #     raise ValueError(f"停止Nginx时发生错误: {e}")
    return True
        
def Restart_Nginx(is_windows=True):
    """
    @name 重启nginx
    @author lybbn<2024-04-22>
    """
    if is_windows:
        Stop_Nginx(is_windows=is_windows)
        time.sleep(0.1)
        Start_Nginx(is_windows=is_windows)
    else:
        result,err,code = RunCommand("systemctl restart nginx", returncode=True)
        if code == 0 or not err:
            pass
        else:
            raise Exception(err)

def Reload_Nginx(is_windows=True):
    """
    @name 重载nginx
    @author lybbn<2024-04-22>
    """
    soft_paths = get_nginx_path_info()
    exe_path = soft_paths['windows_abspath_exe_path'] if is_windows else  soft_paths['linux_exe_path']
    conf_path = soft_paths['abspath_conf_path']
    # 确保路径存在
    if os.path.exists(exe_path):
        check_nginx_config(conf_path=conf_path,is_windows=is_windows)
        try:
            if is_windows:
                command = [exe_path,"-s", "reload"]
                code = RunCommandReturnCode(command,cwd=soft_paths['install_path'])
            else:
                res,err,code = RunCommand("systemctl reload nginx",returncode=True)
            return True if code == 0 else False
        except Exception as e:
            raise ValueError(f"重载Nginx时发生错误: {e}")
    else:
        raise ValueError(f"Nginx未安装")

def RY_GET_NGINX_CONF(is_windows=True):
    soft_paths = get_nginx_path_info()
    conf_path = soft_paths['abspath_conf_path']
    return ReadFile(conf_path)

def RY_GET_NGINX_PORT(is_windows=True):
    return 80
    
def RY_SAVE_NGINX_CONF(conf="",is_windows=True):
    soft_paths = get_nginx_path_info()
    conf_path = soft_paths['abspath_conf_path']
    conf_tmp_path = soft_paths['abspath_tmpconf_path']
    WriteFile(conf_tmp_path,content=conf)
    if check_nginx_config(conf_path=conf_tmp_path,is_windows=is_windows):
        WriteFile(conf_path,content=conf)
    else:
        raise ValueError("配置文件错误!!!")
    return True

def RY_GET_NGINX_LOADSTATUS(is_windows=True):
    try:
        response = requests.get("http://localhost/nginx_status",timeout=1)
        # 确保请求成功
        response.raise_for_status()
        resdata = response.text
        tmp_data = resdata.split()
        status_info = {}
        
        if "request_time" in tmp_data:
            status_info['AcceptedConnections'] = tmp_data[8]
            status_info['HandledConnections'] = tmp_data[9]
            status_info['TotalRequests'] = tmp_data[10]
            status_info['Reading'] = tmp_data[13]
            status_info['Writing'] = tmp_data[15]
            status_info['Waiting'] = tmp_data[17]
        else:
            status_info['AcceptedConnections'] = tmp_data[9]
            status_info['HandledConnections'] = tmp_data[7]
            status_info['TotalRequests'] = tmp_data[8]
            status_info['Reading'] = tmp_data[11]
            status_info['Writing'] = tmp_data[13]
            status_info['Waiting'] = tmp_data[15]
        status_info['ActiveConnections'] = tmp_data[2]
        nginx_cpu = {}
        worker_mem = 0
        time.sleep(0.1)
        soft_name = "nginx.exe" if is_windows else 'nginx'
        nginx_processes = [proc for proc in psutil.process_iter(attrs=['name','pid']) if proc.info['name'] == soft_name]
        if is_windows:
            worker = len(nginx_processes) - 1
            for proc0 in nginx_processes:
                try:
                    memory_info = proc0.memory_info()
                    worker_mem += memory_info.rss  # Resident Set Size (RSS), physical memory used
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            worker_mem = f"{worker_mem / (1024 * 1024):.2f} MB"
        else:
            worker = int(RunCommand("ps aux|grep nginx|grep 'worker process'|wc -l")[0])
            worker_mem = int(RunCommand("ps aux|grep nginx|grep 'worker process'|awk '{memsum+=$6};END {print memsum}'")[0])
            worker_mem = f"{worker_mem / (1024):.2f} MB"
        for proc1 in nginx_processes:
            GetPidCpuPercent(proc1.info['pid'], nginx_cpu)
        status_info['Worker'] = worker
        status_info['WorkerCpu'] = round(float(nginx_cpu[soft_name]), 2)
        status_info['WorkerMem'] = worker_mem
        return status_info
    except Exception as e:
        raise ValueError("获取失败")

def RY_GET_NGINX_PERFORMANCE(is_windows=True):
    nginx_conf = RY_GET_NGINX_CONF()
    if not nginx_conf:raise ValueError("nginx未安装")
    parameters = {
        "worker_processes": r"worker_processes\s+(auto|\d+);",
        "worker_connections": r"worker_connections\s+(\d+);",
        "keepalive_timeout": r"keepalive_timeout\s+(\d+);",
        "gzip": r"gzip\s+(on|off);",
        "gzip_min_length": r"gzip_min_length\s+(\d+k?);",
        "gzip_comp_level": r"gzip_comp_level\s+(\d);",
        "client_max_body_size": r"client_max_body_size\s+([\d\w]+);",
        "server_names_hash_bucket_size": r"server_names_hash_bucket_size\s+(\d+);",
        "client_header_buffer_size": r"client_header_buffer_size\s+(\d+k?);",
        "client_body_buffer_size": r"client_body_buffer_size\s+(\d+k?);"
    }
    
    results = {}
    for param, pattern in parameters.items():
        match = re.search(pattern, nginx_conf)
        if match:
            value = match.group(1)
            # Convert values to appropriate types
            if param in ["worker_connections", "keepalive_timeout", "gzip_comp_level", "server_names_hash_bucket_size"]:
                results[param] = int(value)
            elif param in ["worker_processes"]:
                if value == "auto":
                    results[param] = "auto"
                else:
                    results[param] = int(value)
            elif param == "client_max_body_size":#转为MB
                # If needed, handle units like "k", "m", etc.
                if value[-1] in 'kK':
                    results[param] = round(int(value[:-1]) / 1024,1)
                if value[-1] in 'mM':
                    results[param] = int(value[:-1])
                else:
                    results[param] = int(value)
            elif param in ["client_header_buffer_size", "client_body_buffer_size","gzip_min_length"]:#转为KB
                if value[-1] in 'kK':
                    results[param] = int(value[:-1])
                elif value[-1] in 'mM':
                    results[param] = int(value[:-1]) * 1024
                else:
                    results[param] = int(value)
            else:
                results[param] = value  # For "gzip", we keep it as string
        else:
            results[param] = "未匹配到"

    return results

def RY_SET_NGINX_PERFORMANCE(cont,is_windows=True):
    soft_paths = get_nginx_path_info()
    conf_path = soft_paths['abspath_conf_path']
    nginx_conf = ReadFile(conf_path)
    if not nginx_conf:raise ValueError("nginx未安装")
    parameters = {
        "worker_processes": r"worker_processes\s+(auto|\d+);",
        "worker_connections": r"worker_connections\s+(\d+);",
        "keepalive_timeout": r"keepalive_timeout\s+(\d+);",
        "gzip": r"gzip\s+(on|off);",
        "gzip_min_length": r"gzip_min_length\s+(\d+k?);",
        "gzip_comp_level": r"gzip_comp_level\s+(\d);",
        "client_max_body_size": r"client_max_body_size\s+([\d\w]+);",
        "server_names_hash_bucket_size": r"server_names_hash_bucket_size\s+(\d+);",
        "client_header_buffer_size": r"client_header_buffer_size\s+(\d+k?);",
        "client_body_buffer_size": r"client_body_buffer_size\s+(\d+k?);"
    }
    for param, pattern in parameters.items():
        if param in cont:
            value = str(cont[param])
            if param == "worker_processes":
                if not re.search(r"auto|\d+", value):raise ValueError('worker_processes参数值错误')
            elif param == "gzip":
                if value not in ["on","off"]:raise ValueError("gzip参数值错误")
            else:
                if not re.search(r"\d+", value):raise ValueError(f"{param}参数值错误")
                if param in ["gzip_min_length","client_header_buffer_size","client_body_buffer_size"]:
                    value = f"{value}k"
                elif param in ["client_max_body_size"]:
                    value = f"{value}m"
            
            if re.search(pattern, nginx_conf):
                # Update existing parameter
                nginx_conf = re.sub(pattern, f"{param} {value};", nginx_conf)

    WriteFile(conf_path,nginx_conf)
    return True
    

def RY_GET_NGINX_CONFIG(is_windows=True):
    cpu_count = psutil.cpu_count()
    worker_connections = cpu_count * 1024
    soft_paths = get_nginx_path_info()
    log_path = soft_paths['log_path']
    access_log_path = soft_paths['access_log_path']
    error_log_path = soft_paths['error_log_path']
    pid_path = log_path+'/nginx.pid'
    vhost_path = settings.RUYI_VHOST_PATH.replace("\\", "/")
    vhost_nginx_path = vhost_path+'/nginx/*.conf'
    proxy_cache_path = soft_paths['install_path']+'/temp/proxy_cache_dir'
    if is_windows:
        if not os.path.exists(proxy_cache_path):
            os.makedirs(proxy_cache_path)
    
    lua_package_path=""
    if not is_windows:
        lua_package_path='lua_package_path "/ruyi/server/nginx/lib/lua/?.lua;;";'
    
    user_www ="user www www;"
    if is_windows:user_www=""

    conf = f"""{user_www}
worker_processes  auto;
pid        {pid_path};
events {{
    worker_connections  {worker_connections};
    multi_accept on;
}}
http {{
    include       mime.types;
    default_type  application/octet-stream;
    server_names_hash_bucket_size 512;
    client_header_buffer_size 32k;
    large_client_header_buffers 4 32k;
    client_max_body_size 50m;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                          '$status $body_bytes_sent "$http_referer" '
                          '"$http_user_agent" "$http_x_forwarded_for"';

    access_log  {access_log_path};
    error_log   {error_log_path};

    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout  60;
    types_hash_max_size 2048;
    
    gzip on;
    gzip_min_length  1k;
    gzip_buffers     4 16k;
    gzip_http_version 1.1;
    gzip_comp_level 2;
    gzip_types     text/plain application/javascript application/x-javascript text/javascript text/css application/xml;
    gzip_vary on;
    gzip_proxied   expired no-cache no-store private auth;
    gzip_disable   "MSIE [1-6]\.";
    
    server_tokens off;
    
    #ruyi_limit_conn_zone please do not delete
    
    client_body_buffer_size 512k;
    proxy_cache_path {proxy_cache_path} levels=1:2 keys_zone=cache_one:20m max_size=5g inactive=1d;
    proxy_connect_timeout 60;
    proxy_read_timeout 60;
    proxy_send_timeout 60;
    proxy_buffer_size 32k;
    proxy_buffers 4 64k;
    proxy_busy_buffers_size 128k;
    proxy_temp_file_write_size 128k;
    proxy_next_upstream error timeout invalid_header http_500 http_503 http_404;
    proxy_cache cache_one;
    
    {lua_package_path}
    #ruyi_waf_line please do not delete
    
    server {{
        listen 80;
        server_name localhost;
    
        location /nginx_status {{
            stub_status on;
            access_log off;
            allow 127.0.0.1;
            deny all;
        }}
    }}
    
    include {vhost_nginx_path};

}}
    """
    return conf
    
def RY_GET_NGINX_INDEX_HTML(is_windows=True):
    html = f"""<html>
<head><title>404 Not Found</title></head>
<body>
<center><h1>404 Not Found</h1></center>
<hr><center>nginx</center>
</body>
</html>
    """
    return html

def SET_WINDOWS_SERVICE(log_path=None,is_write_log=True):
    soft_paths = get_nginx_path_info()
    install_path = soft_paths['install_path']
    download_url="https://github.com/winsw/winsw/releases/download/v3.0.0-alpha.11/WinSW-x64.exe"
    filename = get_file_name_from_url(download_url)
    save_path = os.path.join(install_path, filename)
    nginx_server = soft_paths['w_nginx_server']
    
    #开始下载
    ok,msg = download_url_file(url=download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
    if not ok:
        if "github.com" in download_url:
            WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
            WriteFile(log_path,"正在尝试github文件加速下载...\n",mode='a',write=is_write_log)
            new_download_url = get_github_quick_downloadurl(download_url)
            if not new_download_url:
                return False,"加速下载失败！！！"
            ok,msg = download_url_file(url=new_download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
            if not ok:
                return False,"加速下载文件失败！！！"
        else:
            return False,"[error]【%s】下载失败，原因：%s"%(filename,msg)
    os.rename(save_path, nginx_server)
    SET_NGINX_WINDOWS_SERVICE_CONFIG()
    return True,None

def SET_NGINX_WINDOWS_SERVICE_CONFIG():
    soft_paths = get_nginx_path_info()
    install_path = soft_paths['install_path']
    log_path = soft_paths['log_path']
    exe_path = soft_paths['windows_abspath_exe_path']
    content = f"""
<service>
    <id>nginx</id>
    <name>nginx</name>
    <description>nginx</description>
    <logpath>{log_path}</logpath>
    <logmode>roll</logmode>
    <depend></depend>

    <executable>{exe_path}</executable>
    <stopexecutable>{exe_path} -s stop</stopexecutable>
</service>"""
    WriteFile(install_path+"/nginx_server.xml",content)