#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-10-22
# +-------------------------------------------------------------------
# | EditDate: 2024-10-22
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Php环境安装/卸载
# ------------------------------

import os,platform
import time
from utils.common import ReadFile,GetTmpPath,GetInstallPath,WriteFile,DeleteFile,GetLogsPath,RunCommandReturnCode,RunCommand
from utils.security.files import download_url_file,get_file_name_from_url
import subprocess
import importlib
from utils.server.system import system
from django.conf import settings
from apps.systask.subprocessMg import job_subprocess_add,job_subprocess_del

def get_php_path_info(version):
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,'php',version)
    install_path = root_path+'/php/'+version
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'windows_abspath_python_path':os.path.join(install_abspath_path,'python.exe'),
        'windows_abspath_pip_path':os.path.join(install_abspath_path,'Scripts','pip.exe'),
        'linux_abspath_python_path':os.path.join(install_abspath_path,'bin','python3'),
        'linux_abspath_pip_path':os.path.join(install_abspath_path,'bin','pip3'),
    }
    
def python_install_call_back(version={},call_back=None,ok=True):
    if call_back:
        job_id = version['job_id']
        job_subprocess_del(job_id)
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id,version=version,ok=ok)

def isSupportSys():
    if platform.architecture()[0] == '64bit':
        arch = platform.machine().lower()
        if arch in ['x86_64','amd64','aarch64']:
            return True
        return False
    return False

def check_python_version(pythonPath=""):
    try:
        if not pythonPath:
            pythonPath = "python"
        output = subprocess.check_output([pythonPath, "--version"], stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        version = output.decode().strip().split()[1]
        return tuple(map(int, version.split(".")))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
        
def Install_Python(type=2,version={},is_windows=True,call_back=None):
    """
    @name 安装Python
    @parma call_back 为执行回调函数的方法路径
    @author lybbn<2024-10-18>
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
        if isSupportSys():
            WriteFile(log_path,"检测系统为64位，环境检测通过 ✔\n",mode='a',write=is_write_log)
        else:
            raise Exception("暂不支持非arm64、amd64和x86_64系统，环境检测不通过 ✖")
        download_url = version.get('url',None)
        WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
        filename = get_file_name_from_url(download_url)
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_python_path_info(version['c_version'])
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
            # 如果目标文件夹已经存在，先删除它
            system.ForceRemoveDir(install_directory)
            if not os.path.exists(install_directory):
                os.makedirs(install_directory)
            WriteFile(log_path,"安装中，请耐心等待...\n",mode='a',write=is_write_log)
            subprocess.run([save_path, "/quiet",f"TargetDir={os.path.normpath(install_directory)}", "InstallAllUsers=1", "PrependPath=1","Include_test=0"],creationflags=subprocess.CREATE_NO_WINDOW)
            WriteFile(log_path,"正在检测安装结果...\n",mode='a',write=is_write_log)
            time.sleep(0.5)
            install_version = check_python_version(soft_paths['windows_abspath_python_path'])
            if not install_version:
                raise Exception("安装失败，无法执行安装后的python")
            WriteFile(log_path,f"安装成功，检测后安装版本：{install_version}\n",mode='a',write=is_write_log)
            # 新建版本文件
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
        else:
            r_process = subprocess.Popen(['bash', GetInstallPath()+'/ruyi/utils/install/bash/python.sh','install',version['c_version'],filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,bufsize=1, preexec_fn=os.setsid)
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
                if not os.path.exists(soft_paths['linux_abspath_python_path']):
                    raise Exception(r_stderr.strip())
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
        
        # 删除下载的文件
        DeleteFile(save_path,empty_tips=False)
        WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        version['install_path'] = install_directory
        python_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        python_install_call_back(version=version,call_back=call_back,ok=False)
        return False

def Uninstall_Python(version=None,is_windows=True):
    """
    @name 卸载Python
    @author lybbn<2024-11-16>
    """
    if not version: raise ValueError("未提供版本号")
    soft_paths = get_python_path_info(version)
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            time.sleep(0.1)
            system.ForceRemoveDir(install_path)
    else:
        try:
            subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","python.sh"),'uninstall',version], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True