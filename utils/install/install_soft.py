#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-08-10
# +-------------------------------------------------------------------
# | EditDate: 2024-11-16
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# 如意商店安装软件
# ------------------------------
import os
from utils.common import GetInstallPath,ReadFile
from utils.install.nginx import *
from utils.install.redis import *
from utils.install.mysql import *
from utils.install.python import *
from utils.install.go import *
from utils.install.supervisor import *
from utils.install.docker import *

def Check_Soft_Running(name="",is_windows = True,simple_check=False):
    if name == 'nginx':
        return is_nginx_running(is_windows=is_windows,simple_check=simple_check)
    elif name == 'redis':
        return is_redis_running(is_windows=is_windows,simple_check=simple_check)
    elif name == 'mysql':
        return is_mysql_running(is_windows=is_windows,simple_check=simple_check)
    elif name == 'docker':
        return is_docker_running(is_windows=is_windows,simple_check=simple_check)
    elif name == 'supervisor':
        return is_supervisor_running(is_windows=is_windows)
    return False

def Check_Soft_Installed(name="",version=None,get_status=True,is_windows = True,simple_check=False):
    """
    get_status:是否获取运行状态
    version:针对python环境的安装有多个版本同时存在，需要指定获取哪个版本的，其他的可以为None
    """
    install_base_directory = os.path.abspath(GetInstallPath())
    install_directory = os.path.join(install_base_directory,name)
    version_path = os.path.join(install_directory,version,'version.ry') if version else os.path.join(install_directory,'version.ry')
    c_version = ""
    status = False
    install_path = ""
    if os.path.exists(version_path):
        c_version = ReadFile(version_path)
        if get_status:
            status =  Check_Soft_Running(name=name,is_windows=is_windows,simple_check=simple_check)
        install_path = GetInstallPath()+"/"+name+"/"+version if version else GetInstallPath()+"/"+name
        return True,c_version,status,install_path
    return False,c_version,status,install_path

def Ry_Install_Soft(type=2,name="",version={},is_windows=True,call_back=None):
    if name == 'nginx':
        Install_Nginx(type=type,version=version,is_windows=is_windows,call_back=call_back)
    elif name == 'redis':
        Install_Redis(type=type,version=version,is_windows=is_windows,call_back=call_back)
    elif name == 'mysql':
        Install_Mysql(type=type,version=version,is_windows=is_windows,call_back=call_back)
    elif name == 'docker':
        Install_Docker(type=type,version=version,is_windows=is_windows,call_back=call_back)
    elif name == 'python':
        Install_Python(type=type,version=version,is_windows=is_windows,call_back=call_back)
    elif name == 'go':
        Install_Go(type=type,version=version,is_windows=is_windows,call_back=call_back)
    elif name == 'supervisor':
        Install_Supervisor(type=type,version=version,is_windows=is_windows,call_back=call_back)
    return True

def Ry_Uninstall_Soft(name="",is_windows=True,version=None):
    if name == 'nginx':
        Uninstall_Nginx(is_windows=is_windows)
    elif name == 'redis':
        Uninstall_Redis(is_windows=is_windows)
    elif name == 'mysql':
        Uninstall_Mysql(is_windows=is_windows)
    elif name == 'docker':
        Uninstall_Docker(is_windows=is_windows)
    elif name == 'python':
        Uninstall_Python(version=version,is_windows=is_windows)
    elif name == 'go':
        Uninstall_Go(version=version,is_windows=is_windows)
    elif name == 'supervisor':
        Uninstall_Supervisor(is_windows=is_windows)
    return True

def Ry_Start_Soft(name="",is_windows=True):
    if name == 'nginx':
        Start_Nginx(is_windows=is_windows)
    elif name == 'redis':
        Start_Redis(is_windows=is_windows)
    elif name == 'mysql':
        Start_Mysql(is_windows=is_windows)
    elif name == 'docker':
        Start_Docker(is_windows=is_windows)
    elif name == 'supervisor':
        Start_Supervisor(is_windows=is_windows)
    return True

def Ry_Stop_Soft(name="",is_windows=True):
    if name == 'nginx':
        Stop_Nginx(is_windows=is_windows)
    elif name == 'redis':
        Stop_Redis(is_windows=is_windows)
    elif name == 'mysql':
        Stop_Mysql(is_windows=is_windows)
    elif name == 'docker':
        Stop_Docker(is_windows=is_windows)
    elif name == 'supervisor':
        Stop_Supervisor(is_windows=is_windows)
    return True

def Ry_Restart_Soft(name="",is_windows=True):
    if name == 'nginx':
        Restart_Nginx(is_windows=is_windows)
    elif name == 'redis':
        Restart_Redis(is_windows=is_windows)
    elif name == 'mysql':
        Restart_Mysql(is_windows=is_windows)
    elif name == 'docker':
        Restart_Docker(is_windows=is_windows)
    elif name == 'supervisor':
        Restart_Supervisor(is_windows=is_windows)
    return True

def Ry_Reload_Soft(name="",is_windows=True):
    if name == 'nginx':
        Reload_Nginx(is_windows=is_windows)
    elif name == 'mysql':
        Reload_Mysql(is_windows=is_windows)
    elif name == 'supervisor':
        Reload_Supervisor(is_windows=is_windows)
    return True

def Ry_Get_Soft_Info_Path(name="",type="all",version=None,is_windows=True):
    if name == 'nginx':
        allinfo = get_nginx_path_info()
        if type == 'all':
            return allinfo
        elif type == 'error':
            return allinfo['error_log_path']
        elif type == 'access':
            return allinfo['access_log_path']
    elif name == 'redis':
        allinfo = get_redis_path_info()
        if type == 'all':
            return allinfo
    elif name == 'mysql':
        allinfo = get_mysql_path_info()
        if type == 'all':
            return allinfo
        elif type == 'error':
            return allinfo['error_log_path']
        elif type == 'slow':
            return allinfo['slow_log_path']
    elif name == 'docker':
        allinfo = get_docker_path_info()
        if type == 'all':
            return allinfo
    elif name == 'python':
        allinfo = get_python_path_info(version)
        if type == 'all':
            return allinfo
    elif name == 'go':
        allinfo = get_go_path_info(version)
        if type == 'all':
            return allinfo
    elif name == 'supervisor':
        allinfo = get_supervisor_path_info()
        if type == 'all':
            return allinfo
        elif type == 'access':
            return RY_GET_SUPERVISOR_CONF_OPTIONS(is_windows=is_windows)['logfile']
    return ""

def Ry_Get_Soft_LoadStatus(name="",is_windows=True):
    if name == 'nginx':
        return RY_GET_NGINX_LOADSTATUS(is_windows=is_windows)
    elif name == 'redis':
        return RY_GET_REDIS_LOADSTATUS(is_windows=is_windows)
    elif name == 'mysql':
        return RY_GET_MYSQL_LOADSTATUS(is_windows=is_windows)
    return ""

def Ry_Get_Soft_Performance(name="",is_windows=True):
    if name == 'nginx':
        return RY_GET_NGINX_PERFORMANCE(is_windows=is_windows)
    elif name == 'mysql':
        return RY_GET_MYSQL_PERFORMANCE(is_windows=is_windows)
    return ""

def Ry_Set_Soft_Performance(name="",cont={},is_windows=True):
    if name == 'nginx':
        return RY_SET_NGINX_PERFORMANCE(cont,is_windows=is_windows)
    elif name == 'mysql':
        return RY_SET_MYSQL_PERFORMANCE(cont,is_windows=is_windows)
    return True

def Ry_Get_Soft_Conf(name="",is_windows=True):
    if name == 'nginx':
        return RY_GET_NGINX_CONF(is_windows=is_windows)
    elif name == 'redis':
        return RY_GET_REDIS_CONF(is_windows=is_windows)
    elif name == 'mysql':
        return RY_GET_MYSQL_CONF(is_windows=is_windows)
    elif name == 'docker':
        return RY_GET_DOCKER_CONF(is_windows=is_windows)
    elif name == 'supervisor':
        return RY_GET_SUPERVISOR_CONF(is_windows=is_windows)
    return ""

def Ry_Save_Soft_Conf(name="",conf="",is_windows=True):
    if name == 'nginx':
        return RY_SAVE_NGINX_CONF(conf=conf,is_windows=is_windows)
    elif name == 'redis':
        return RY_SAVE_REDIS_CONF(conf=conf,is_windows=is_windows)
    elif name == 'mysql':
        return RY_SAVE_MYSQL_CONF(conf=conf,is_windows=is_windows)
    elif name == 'docker':
        return RY_SAVE_DOCKER_CONF(conf=conf,is_windows=is_windows)
    elif name == 'supervisor':
        return RY_SAVE_SUPERVISOR_CONF(conf=conf,is_windows=is_windows)
    return True

def Ry_Get_Soft_Port(name="",is_windows=True):
    if name == 'nginx':
        return RY_GET_NGINX_PORT(is_windows=is_windows)
    elif name == 'redis':
        return RY_GET_REDIS_PORT(is_windows=is_windows)
    elif name == 'mysql':
        return RY_GET_MYSQL_PORT(is_windows=is_windows)
    return ""