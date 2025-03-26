#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-16
# +-------------------------------------------------------------------
# | EditDate: 2025-02-16
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Docker安装/卸载
# ------------------------------

import os
import re
import time
from utils.common import check_url_site_canuse,ReadFile,is_service_running,GetTmpPath,GetRootPath,GetInstallPath,WriteFile,DeleteFile,GetLogsPath,RunCommandReturnCode,DeleteDir,RunCommand,GetProcessNameInfo,is_admin
from utils.security.files import download_url_file,get_file_name_from_url,get_github_quick_downloadurl,download_url_file_wget
from pathlib import Path
import subprocess
import importlib
from utils.server.system import system
from utils.ruyiclass.dockerClass import DockerClient
from django.conf import settings
from apps.systask.subprocessMg import job_subprocess_add,job_subprocess_del

def get_docker_path_info():
    ry_root_path = GetRootPath()
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,'docker')
    install_path = root_path+'/docker'
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'windows_abspath_docker_bin':os.path.join(install_abspath_path,'docker','resources','bin','docker.exe'),
        'windows_abspath_dockerd_bin':os.path.join(install_abspath_path,'docker','resources','dockerd.exe'),
        'windows_abspath_compose_bin':os.path.join(install_abspath_path,'docker','resources','bin','docker-compose.exe'),
        'windows_abspath_desktop_bin':os.path.join(install_abspath_path,'docker','Docker Desktop.exe'),
        'windows_abspath_uninstall_bin':os.path.join(install_abspath_path,'docker','Docker Desktop Installer.exe'),
        'linux_docker_bin':"/usr/bin/docker",
        'windows_daemon_conf':os.path.expanduser("~/.docker/daemon.json"),
        'linux_daemon_conf':"/etc/docker/daemon.json",
        'data_root':ry_root_path+"/data/docker",
    }

def docker_install_call_back(version={},call_back=None,ok=True):
    if call_back:
        job_id = version['job_id']
        job_subprocess_del(job_id)
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id,version=version,ok=ok)


def _check_feature_enabled(feature_name,log_path=None):
    """检查指定Windows功能是否已启用"""
    try:
        import locale
        # 获取系统默认编码
        sys_encoding = locale.getpreferredencoding()
        
        result = subprocess.run(
            ['dism', '/online', '/get-featureinfo', f'/featurename:{feature_name}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=sys_encoding,
            errors='replace'  # 替换无法解码的字符
        )
        WriteFile(log_path,f"检查{feature_name}返回内容stdout：{result.stdout}\n",mode='a',write=True)
        WriteFile(log_path,f"检查{feature_name}返回内容stderr：{result.stderr}\n",mode='a',write=True)
        # 确保输出不为None
        output = result.stdout or ""
        return "State : Enabled" in output or "状态 : 已启用" in output
    except Exception as e:
        WriteFile(log_path,f"检查功能状态失败: {str(e)}\n",mode='a',write=True)
        return False
    
def _install_wsl2(log_path):
    """安装WSL2所需组件"""
    soft_paths = get_docker_path_info()
    try:
        # 启用必要功能
        features = [
            'Microsoft-Windows-Subsystem-Linux',
            'VirtualMachinePlatform',
            'HypervisorPlatform'
        ]
        for feature in features:
            if not _check_feature_enabled(feature,log_path=log_path):
                WriteFile(log_path,f"正在启用功能: {feature}\n",mode='a',write=True)
                sout,serr,retcode = RunCommand(f"dism /online /enable-feature /featurename:{feature} /all /NoRestart",returncode=True)
                if retcode == 3010:
                    WriteFile(log_path,f"已安装{feature}，但需要重启windows生效！！！\n",mode='a',write=True)
                elif retcode == 0:
                    WriteFile(log_path,f"安装{feature}，成功\n",mode='a',write=True)
                else:
                    raise Exception(f"安装{feature}返回异常内容：{serr}\n")
        # 更新WSL内核(弃用，无法访问更新)
        # print("正在更新WSL内核...")
        # subprocess.run(
        #     ['wsl', '--update'],
        #     check=True,
        #     stdout=subprocess.DEVNULL,
        #     stderr=subprocess.DEVNULL
        # )

        # WriteFile(log_path,"更新WSL内核\n",mode='a',write=True)
        # download_url="https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi"
        # filename="wsl_update_x64.msi"
        # save_directory = os.path.abspath(GetTmpPath())
        # save_path = os.path.join(save_directory, filename)
        # ok,msg = download_url_file(url=download_url,save_path=save_path,chunk_size=32768,process=True,log_path=log_path)
        # if ok:
        #     try:
        #         subprocess.run(
        #             ['msiexec', '/i',save_path,'/qn'],
        #             check=True,
        #             stdout=subprocess.DEVNULL,
        #             stderr=subprocess.DEVNULL
        #         )
        #     except Exception as e:
        #         WriteFile(log_path,f"更新WSL内核失败：{e}\n",mode='a',write=True)
        # #删除下载的文件
        # DeleteFile(save_path,empty_tips=False)
        
        # # 设置默认版本为WSL2
        # WriteFile(log_path,"正在设置WSL2为默认版本...\n",mode='a',write=True)
        # try:
        #     set_ver_result = subprocess.run(
        #         ['wsl', '--set-default-version', '2'],
        #         text=True,
        #         stdout=subprocess.DEVNULL,
        #         stderr=subprocess.DEVNULL,
        #         timeout=10
        #     )
        #     WriteFile(log_path,f"命令输出stdout:{set_ver_result.stdout}\n",mode='a',write=True)
        #     WriteFile(log_path,f"命令输出sterr:{set_ver_result.stderr}\n",mode='a',write=True)
        # except Exception as e:
        #     WriteFile(log_path,f"错误: {str(e)}\n",mode='a',write=True)
        
        #WriteFile(log_path,"正在安装linux发行版Centos7...\n",mode='a',write=True)
        #安装linux发行版
        # linux_download_url="https://ghfast.top/https://github.com/mishamosher/CentOS-WSL/releases/download/7.9-2211/CentOS7.zip"
        # linux_filename = get_file_name_from_url(linux_download_url)
        # linux_save_path=os.path.join(save_directory, linux_filename)
        # jiasu_url = ["https://ghfast.top","https://github.moeyy.xyz","https://ghproxy.cfd"]
        # is_linux_download_ok=False
        # for jsurl in jiasu_url:
        #     if check_url_site_canuse(jsurl):
        #         b_linux_download_url=f"{jsurl}/{linux_download_url}"
        #         bcok,bcmsg = download_url_file(url=b_linux_download_url,save_path=linux_save_path,process=True,log_path=log_path,chunk_size=32768)
        #         if bcok:
        #             is_linux_download_ok=True
        #             break
        # if is_linux_download_ok:
        #     install_directory=soft_paths['install_abspath_path']
        #     from apps.systask.tasks import func_unzip
        #     func_unzip(save_path,install_directory)
        #     install_exe_path=os.path.join(install_directory,"CentOS7","CentOS7.exe")
        #     subprocess.run(
        #         [install_exe_path],
        #         check=True,
        #         creationflags=subprocess.CREATE_NO_WINDOW,
        #         stdout=subprocess.DEVNULL,
        #         stderr=subprocess.DEVNULL
        #     )
        #卸载 wsl --unregister <发行版名称>
        return True
    except Exception as e:
        WriteFile(log_path,f"安装过程中出错: {e}\n",mode='a',write=True)
        return False

def Install_Docker(type=2,version={},is_windows=True,call_back=None):
    """
    @name 安装Docker
    @parma call_back 为执行回调函数的方法路径
    @author lybbn<2025-02-16>
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
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_docker_path_info()
        install_base_directory = soft_paths['root_abspath_path']
        install_directory = soft_paths['install_abspath_path']
        data_root = soft_paths['data_root']
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        if not os.path.exists(data_root):
            os.makedirs(data_root)
        if is_windows:
            if not is_admin():
                raise Exception("需管理员权限执行安装\n")
            download_url = version.get('url',None)
            WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
            filename = get_file_name_from_url(download_url)
            save_path = os.path.join(save_directory, filename)
            #开始下载
            ok,msg = download_url_file_wget(url=download_url,save_path=save_path,process=True,log_path=log_path)
            if not ok:
                if "github.com" in download_url:
                    WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
                    WriteFile(log_path,"正在尝试github文件加速下载...\n",mode='a',write=is_write_log)
                    new_download_url = get_github_quick_downloadurl(download_url)
                    if not new_download_url:
                        raise ValueError("加速下载失败！！！")
                    ok,msg = download_url_file(url=new_download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
                    if not ok:
                        raise ValueError("加速下载文件失败！！！")
                else:
                    WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
                    raise ValueError(msg)
            WriteFile(log_path,"【%s】下载完成\n"%filename,mode='a',write=is_write_log)
            WriteFile(log_path,"开始安装...\n",mode='a',write=is_write_log)
            installation_dir = os.path.join(install_directory,'docker')
            #,f"--wsl-default-data-root={data_root}","--relaunch-as-admin"
            command = [save_path, "install", "--quiet", "--accept-license","--always-run-service","--backend=wsl-2",f"--installation-dir={installation_dir}"]#--backend=hyper-v
            r_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,universal_newlines=True, text=True,bufsize=1, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            job_subprocess_add(version['job_id'],r_process)
            install_log_p = "C:/ProgramData/DockerDesktop/install-log-admin.txt"
            WriteFile(log_path,f"请查看Dokcer Desktop安装进度日志：{install_log_p}\n",mode='a',write=is_write_log)
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
                windows_abspath_docker_bin = soft_paths['windows_abspath_docker_bin']
                WriteFile(log_path,f"{r_stderr.strip()}\n",mode='a',write=is_write_log)
                if not os.path.exists(windows_abspath_docker_bin):
                    raise ValueError(r_stderr.strip())

            WriteFile(log_path,"Docker Desktop 安装成功\n",mode='a',write=is_write_log)
            
            # 新建版本文件
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(log_path,"正在配置docker...\n",mode='a',write=is_write_log)
            WriteFile(soft_paths['windows_daemon_conf'],RY_GET_DOCKER_DEFAULT_CONF(is_windows=True))
            #删除下载的文件
            DeleteFile(save_path,empty_tips=False)
            WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
        else:
            r_process = subprocess.Popen(['bash', GetInstallPath()+'/ruyi/utils/install/bash/docker.sh','install',version['c_version']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,bufsize=1, preexec_fn=os.setsid)
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
                if not os.path.exists('/usr/bin/dockerd'):
                    raise ValueError(r_stderr.strip())
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
        
        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        version['install_path'] = install_directory
        docker_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"正在启动docker服务...\n",mode='a',write=is_write_log)
        Start_Docker(is_windows=is_windows)
        WriteFile(log_path,"docker启动成功\n",mode='a',write=is_write_log)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        docker_install_call_back(version=version,call_back=call_back,ok=False)
        return False

def Install_Docker_bak(type=2,version={},is_windows=True,call_back=None):
    """
    @name 安装Docker,自定义二进制安装
    @parma call_back 为执行回调函数的方法路径
    @author lybbn<2025-02-16>
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
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_docker_path_info()
        install_base_directory = soft_paths['root_abspath_path']
        install_directory = soft_paths['install_abspath_path']
        data_root = soft_paths['data_root']
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        if not os.path.exists(data_root):
            os.makedirs(data_root)
        if is_windows:
            if not is_admin():
                raise Exception("需管理员权限执行安装\n")
            install_env_res = _install_wsl2(log_path)
            if not install_env_res:
                WriteFile(log_path,"安装Windows虚拟化环境失败，请手动安装！！！\n",mode='a',write=is_write_log)
            # if not _check_feature_enabled("HypervisorPlatform"):
            #     #dism /online /enable-feature /featurename:HypervisorPlatform /all /NoRestart
            #     raise Exception("当前windows系统启用Hyper-v服务")
            download_url = version.get('url',None)
            WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
            filename = get_file_name_from_url(download_url)
            save_path = os.path.join(save_directory, filename)
            #开始下载
            ok,msg = download_url_file(url=download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
            if not ok:
                WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
                raise ValueError(msg)
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
            #docker-compose
            compose_download_url = "https://github.com/docker/compose/releases/latest/download/docker-compose-windows-x86_64.exe"
            WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%("docker-compose",compose_download_url),mode='a',write=is_write_log)
            compose_save_path = os.path.join(install_directory,'docker', "docker-compose.exe")
            #开始下载
            cok,cmsg = download_url_file(url=compose_download_url,save_path=compose_save_path,process=True,log_path=log_path,chunk_size=32768)
            if not cok:
                WriteFile(log_path,"【docker-compose.exe】下载失败，正使用加速地址下载\n",mode='a',write=is_write_log)
                jiasu_url = ["https://ghfast.top","https://github.moeyy.xyz","https://ghproxy.cfd"]
                is_dl_ok = False
                for jsurl in jiasu_url:
                    if check_url_site_canuse(jsurl):
                        b_compose_download_url=f"{jsurl}/{compose_download_url}"
                        bcok,bcmsg = download_url_file(url=b_compose_download_url,save_path=compose_save_path,process=True,log_path=log_path,chunk_size=32768)
                        if bcok:
                            is_dl_ok = True
                            break
                if not is_dl_ok:
                    WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%("docker-compose.exe",msg),mode='a',write=is_write_log)
                    raise ValueError(msg)
            WriteFile(log_path,"【docker-compose.exe】下载完成\n",mode='a',write=is_write_log)
            
            # 新建版本文件
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(log_path,"正在配置docker...\n",mode='a',write=is_write_log)
            WriteFile(soft_paths['windows_daemon_conf'],RY_GET_DOCKER_DEFAULT_CONF(is_windows=True))
            try:
                subprocess.run([soft_paths['windows_abspath_dockerd_bin'],f'--config-file={soft_paths['windows_daemon_conf']}', '--register-service','--service-name=dockerd'], capture_output=False, text=True)
                subprocess.run(['sc','config','dockerd','start=auto'], capture_output=False, text=True)
            except Exception as e:
                raise Exception(f"注册dokcerd service 失败：{e}")
            
            #删除下载的文件
            DeleteFile(save_path,empty_tips=False)
            WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
            WriteFile(log_path,"正在添加docker系统命令路径...\n",mode='a',write=is_write_log)
            bin_path = os.path.join(install_directory,'docker')
            system.AddBinToPath(bin_path)
        else:
            r_process = subprocess.Popen(['bash', GetInstallPath()+'/ruyi/utils/install/bash/docker.sh','install',version['c_version']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,bufsize=1, preexec_fn=os.setsid)
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
                if not os.path.exists('/usr/bin/dockerd'):
                    raise ValueError(r_stderr.strip())
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
        
        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        version['install_path'] = install_directory
        docker_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"正在启动docker服务...\n",mode='a',write=is_write_log)
        Start_Docker(is_windows=is_windows)
        WriteFile(log_path,"docker启动成功\n",mode='a',write=is_write_log)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        docker_install_call_back(version=version,call_back=call_back,ok=False)
        return False

def Uninstall_Docker(is_windows=True):
    """
    @name 卸载Dokcer
    @author lybbn<2024-08-18>
    """
    soft_paths = get_docker_path_info()
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            Stop_Docker(is_windows=is_windows)
            exe_path = soft_paths['windows_abspath_uninstall_bin']
            if os.path.exists(exe_path):
                time.sleep(0.5)
                if is_docker_running():
                    time.sleep(3)
                try:
                    subprocess.run([exe_path,'uninstall',"--quiet","--force"], capture_output=False, text=True)
                except Exception as e:
                    print(f"卸载dokcer-desktop失败：{e}")
                time.sleep(2)
            if not os.path.exists(exe_path):
                system.ForceRemoveDir(install_path)
            else:
                raise ValueError("Docker Desktop正在卸载中，请稍后再试")
    else:
        try:
            subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","docker.sh"),'uninstall'], capture_output=False, text=True)
            DeleteDir(install_path)
        except Exception as e:
            raise ValueError(e)
    return True

def is_docker_running(is_windows=True,simple_check=False):
    if simple_check:
        docker_client = DockerClient()
        return docker_client.is_docker_running(close_conn=True)
    soft_name ='Docker Desktop' if is_windows else "dockerd"
    info_list = GetProcessNameInfo(soft_name,{},is_windows=is_windows)
    if len(info_list)>0:
        return True
    return False

def Start_Docker(is_windows=True):
    """
    @name 启动docker
    @author lybbn<2025-01-16>
    """
    soft_paths = get_docker_path_info()
    if is_windows:
        exe_path = soft_paths['windows_abspath_docker_bin']
        r_status = False
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if not is_docker_running(is_windows=True):
                    subprocess.run([exe_path,'desktop','start'], capture_output=False, text=True)
                else:
                    r_status = True
                    return True
                time.sleep(3)
                if not r_status and is_docker_running(is_windows=True):
                    r_status = True
            except Exception as e:
                raise ValueError(f"启动Docker时发生错误: {e}")
            if not r_status:
                raise ValueError(f"Docker启动错误")
        else:
            raise ValueError(f"Docker未安装")
    else:
        exe_path = soft_paths['linux_docker_bin']
        r_status = False
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if not is_docker_running(is_windows=False,simple_check=True):
                    subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","docker.sh"),'start'], capture_output=False, text=True,timeout=20)
                else:
                    r_status = True
                    return True
                time.sleep(1)
                if not r_status and is_docker_running(is_windows=False,simple_check=True):
                    r_status = True
            except Exception as e:
                raise ValueError(f"启动Docker时发生错误: {e}")
            if not r_status:
                raise ValueError(f"Docker启动错误")
        else:
            raise ValueError(f"Docker未安装")

def Stop_Docker(is_windows=True):
    """
    @name 停止docker
    @author lybbn<2025-01-16>
    """
    if is_windows:
        soft_paths = get_docker_path_info()
        exe_path = soft_paths['windows_abspath_docker_bin']
        try:
            if is_docker_running(is_windows=True):
                code = RunCommandReturnCode([exe_path,"desktop", "stop"])
                return True if code == 0 else False
            return True
        except Exception as e:
            raise ValueError(f"停止Docker时发生错误: {e}")
    else:
        if is_docker_running(is_windows=is_windows):
            try:
                subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","docker.sh"),'stop'], capture_output=False, text=True)
                time.sleep(1)
                if is_docker_running(is_windows=False):
                    return False
                else:
                    return True
            except Exception as e:
                raise ValueError(f"停止Docker时发生错误: {e}")
    return True
        
def Restart_Docker(is_windows=True):
    """
    @name 重启docker
    @author lybbn<2025-01-16>
    """
    if is_windows:
        Stop_Docker(is_windows=is_windows)
        time.sleep(0.1)
        Start_Docker(is_windows=is_windows)
    else:
        try:
            subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","docker.sh"),'restart'], capture_output=False, text=True)
            time.sleep(0.5)
            if is_docker_running(is_windows=False):
                return False
            else:
                return True
        except Exception as e:
            raise ValueError(f"重启Docker时发生错误: {e}")
    return True

def RY_GET_DOCKER_CONF(is_windows=True):
    soft_paths = get_docker_path_info()
    if is_windows:
        conf_path=soft_paths['windows_daemon_conf']
    else:
        conf_path = soft_paths['linux_daemon_conf']
    return ReadFile(conf_path)

def RY_SAVE_DOCKER_CONF(conf="",is_windows=True):
    soft_paths = get_docker_path_info()
    if is_windows:
        conf_path=soft_paths['windows_daemon_conf']
    else:
        conf_path = soft_paths['linux_daemon_conf']
    WriteFile(conf_path,content=conf)
    
def RY_GET_DOCKER_DEFAULT_CONF(is_windows=True):
    soft_paths = get_docker_path_info()
    data_root = soft_paths['data_root']
    
    #"data-root": "{data_root}",
    # "experimental": {str(False).lower()},
    # "features": {{
    #     "buildkit": {str(True).lower()},
    #     "quota": {str(False).lower()}
    # }},
    if is_windows:
        conf = f"""{{
    
    "log-driver":"json-file",
    "log-opts":{{
        "max-size" :"10m",
        "max-file":"3"
    }},
    "builder": {{
        "gc": {{
            "defaultKeepStorage": "20GB",
            "enabled": {str(True).lower()}
        }}
    }},
    "registry-mirrors": [
        "https://docker.1ms.run"
    ]
}}"""
    else:
        pass
    return conf