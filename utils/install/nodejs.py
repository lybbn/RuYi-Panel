#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-05-21
# +-------------------------------------------------------------------
# | EditDate: 2025-05-21
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Node.js 安装/卸载
# ------------------------------

import os,platform,re
import time
from pathlib import Path
from utils.common import DeleteDir,GetTmpPath,GetInstallPath,WriteFile,DeleteFile,GetLogsPath,RunCommand,ReadFile,ConvertToUnixLineEndings,CreateInstallProcess,CleanupInstallProcess,SafeReadStderr,ReleaseMemory
from utils.security.files import download_url_file,get_file_name_from_url
import subprocess
import importlib
from utils.server.system import system
from django.conf import settings
from apps.systask.subprocessMg import job_subprocess_add

def get_nodejs_path_info(version):
    root_path = GetInstallPath()+"/nodejs"
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,version)
    install_path = root_path+"/"+version
    public_abspath_path = os.path.join(root_abspath_path,'rynode')
    public_abspath_bin_path = os.path.join(public_abspath_path,'bin')
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'windows_abspath_bin_path':os.path.join(install_abspath_path,'bin'),
        'linux_abspath_bin_path':os.path.join(install_abspath_path,'bin'),
        'windows_abspath_node_path':os.path.join(install_abspath_path,'node.exe'),
        'linux_abspath_node_path':os.path.join(install_abspath_path,'bin','node'),
        'windows_abspath_npm_path':os.path.join(install_abspath_path,'npm.cmd'),
        'linux_abspath_npm_path':os.path.join(install_abspath_path,'bin','npm'),
        'public_abspath_path':public_abspath_path,
        'public_abspath_bin_path':public_abspath_bin_path,
        'w_public_abs_node_path':os.path.join(public_abspath_bin_path,"node.exe"),
        'l_public_abs_node_path':os.path.join(public_abspath_bin_path,"node"),
    }

def nodejs_install_call_back(version={},call_back=None,ok=True):
    if call_back:
        job_id = version.get('job_id')
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

def check_node_version(nodePath=""):
    try:
        if not nodePath:
            nodePath = "node"
        if platform.system().lower() == 'windows':
            output = subprocess.check_output([nodePath, "--version"], stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            output = subprocess.check_output([nodePath, "--version"], stderr=subprocess.STDOUT)
        version = output.decode().strip()
        version_match = re.search(r'v(\d+\.\d+\.\d+)', version)
        if version_match:
            return version_match.group(1)
        else:
            return None
    except:
        return None

def create_default_env(version,version_path,is_windows=True):
    soft_paths = get_nodejs_path_info(version)
    p_path = soft_paths['public_abspath_path']
    if os.path.exists(p_path) or os.path.islink(p_path):
        if os.path.islink(p_path):
            os.remove(p_path)
        elif is_windows and os.path.isdir(p_path):
            try:
                subprocess.run(['cmd', '/c', 'rmdir', p_path], capture_output=True)
            except Exception:
                DeleteDir(p_path)
        else:
            DeleteDir(p_path)
    try:
        os.symlink(version_path, p_path)
    except OSError:
        if is_windows:
            subprocess.run(['cmd', '/c', 'mklink', '/J', p_path, version_path], capture_output=True)
        else:
            raise
    bin_path = soft_paths['public_abspath_bin_path']
    if not is_windows:
        if os.path.exists("/etc/profile"):
            pcont = ReadFile("/etc/profile")
            if not f"export NODEJS_HOME={p_path}" in pcont:
                RunCommand(f"echo 'export NODEJS_HOME={p_path}' >> /etc/profile")
                RunCommand("source /etc/profile")
    system.AddBinToPath(bin_path)

def Install_Nodejs(type=2,version={},is_windows=True,call_back=None):
    try:
        name = version['name']
        log = version.get('log',None)
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
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_nodejs_path_info(version['c_version'])
        install_base_directory = soft_paths['root_abspath_path']
        install_directory = soft_paths['install_abspath_path']
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        filename = get_file_name_from_url(download_url)
        save_path = os.path.join(save_directory, filename)
        if is_windows:
            WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
            ok,msg = download_url_file(url=download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
            if not ok:
                WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
                raise ValueError(msg)
            WriteFile(log_path,"【%s】下载完成\n"%filename,mode='a',write=is_write_log)
            src_folder = os.path.join(install_base_directory,Path(filename).stem)
            WriteFile(log_path,"正在解压安装文件到%s\n"%install_directory,mode='a',write=is_write_log)
            from apps.systask.tasks import func_unzip
            func_unzip(save_path,install_base_directory)
            if os.path.exists(install_directory):
                system.ForceRemoveDir(install_directory)
            os.rename(src_folder, install_directory)
            WriteFile(log_path,"解压成功\n",mode='a',write=is_write_log)
            WriteFile(log_path,"正在检测安装结果...\n",mode='a',write=is_write_log)
            time.sleep(0.5)
            install_version = check_node_version(soft_paths['windows_abspath_node_path'])
            if not install_version:
                raise Exception("安装失败，无法执行安装后的node")
            WriteFile(log_path,f"安装成功，检测后安装版本：{install_version}\n",mode='a',write=is_write_log)
            WriteFile(log_path,f"开始创建默认Node.js环境...\n",mode='a',write=is_write_log)
            create_default_env(version['c_version'],soft_paths['install_abspath_path'],is_windows=is_windows)
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            DeleteFile(save_path,empty_tips=False)
            WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
        else:
            script_path = GetInstallPath()+'/ruyi/utils/install/bash/nodejs.sh'
            ConvertToUnixLineEndings(script_path)
            r_process = CreateInstallProcess(['bash', script_path,'install',version['c_version'],filename])
            job_subprocess_add(version['job_id'],r_process)
            try:
                while True:
                    r_output = r_process.stdout.readline()
                    if r_output == '' and r_process.poll() is not None:
                        break
                    if r_output:
                        WriteFile(log_path,f"{r_output.strip()}\n",mode='a',write=is_write_log)
                    time.sleep(0.1)
                r_stderr = SafeReadStderr(r_process)
                if r_stderr:
                    if not os.path.exists(soft_paths['linux_abspath_node_path']) or "ERROR: Install nodejs fielded" in str(r_stderr):
                        raise Exception(r_stderr.strip()[:2000])
            finally:
                CleanupInstallProcess(r_process, version['job_id'])
                r_process = None
            WriteFile(log_path,f"开始创建默认Node.js环境...\n",mode='a',write=is_write_log)
            create_default_env(version['c_version'],soft_paths['install_abspath_path'],is_windows=is_windows)
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])

        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        version['install_path'] = install_directory
        nodejs_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        version.clear()
        soft_paths.clear()
        ReleaseMemory()
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        nodejs_install_call_back(version=version,call_back=call_back,ok=False)
        version.clear()
        ReleaseMemory()
        return False

def Uninstall_Nodejs(version=None,is_windows=True):
    if not version: raise ValueError("未提供版本号")
    soft_paths = get_nodejs_path_info(version)
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            time.sleep(0.1)
            system.ForceRemoveDir(install_path)
    else:
        try:
            script_path = os.path.join(settings.BASE_DIR,"utils","install","bash","nodejs.sh")
            ConvertToUnixLineEndings(script_path)
            subprocess.run(['bash', script_path,'uninstall',version], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True
