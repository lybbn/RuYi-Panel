#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-03
# +-------------------------------------------------------------------

# ------------------------------
# 操作系统/项目 不能删除目录
# ------------------------------

from utils.common import GetRootPath,GetInstallPath

#linux 系统目录
Linux_System_List = [
    {'path':'/dev','desc':'系统设备目录'},
    {'path':'/mnt','desc':'系统挂载目录'},
    {'path':'/media','desc':'系统多媒体目录'},
    {'path':'/tmp','desc':'系统临时目录'},
    {'path':'/sys','desc':'系统目录'},
    {'path':'/proc','desc':'系统进程目录'},
    {'path': '/etc', 'desc': '系统配置目录'},
    {'path': '/boot', 'desc': '系统引导目录'},
    {'path': '/root', 'desc': '根用户家目录'},
    {'path': '/home', 'desc': '用户家目录'},
    {'path': '/var', 'desc': '系统目录'},
    {'path': '/', 'desc': '系统根目录'},
    {'path': '/*', 'desc': '系统根目录'},
    {'path': '/bin', 'desc': '系统命令目录'},
    {'path': '/usr/bin', 'desc': '用户命令目录'},
    {'path': '/sbin', 'desc': '系统管理员命令目录'},
    {'path': '/usr/sbin', 'desc': '系统管理员命令目录'},
    {'path': '/lib', 'desc': '系统动态库目录'},
    {'path': '/lib32', 'desc': '系统动态库目录'},
    {'path': '/lib64', 'desc': '系统动态库目录'},
    {'path': '/usr/lib', 'desc': '用户库目录'},
    {'path': '/usr/lib64', 'desc': '用户库目录'},
    {'path': '/usr/local/lib', 'desc': '用户库目录'},
    {'path': '/usr/local/lib64', 'desc': '用户库目录'},
    {'path': '/usr/local/libexec', 'desc': '用户库目录'},
    {'path': '/usr/local/sbin', 'desc': '系统脚本目录'},
    {'path': '/usr/local/bin', 'desc': '系统脚本目录'},
    {'path': '/var/log', 'desc': '系统日志目录'},
]

#Windows 系统目录
Windows_System_List = [
    {'path': 'c:/', 'desc': 'C盘禁止删除'},
    {'path': 'c:/Windows', 'desc': 'Windows 操作系统核心文件目录'},
    {'path': 'c:/Program Files', 'desc': '应用程序安装目录（64 位系统）'},
    {'path': 'c:/Program Files (x86)', 'desc': '应用程序安装目录（32 位系统）'},
    {'path': 'c:/Users', 'desc': '用户个人文件目录'},
    {'path': 'c:/ProgramData', 'desc': '应用程序共享数据目录'},
    {'path': 'c:/Windows/System32', 'desc': 'Windows 系统关键系统文件目录'},
    {'path': 'c:/Users/Public', 'desc': '公共用户文件目录'},
]

#如意面板 目录
RUYI_System_List = [
    {'path':GetRootPath(),'desc':'如意根目录'},
    {'path':GetInstallPath(),'desc':'如意程序目录'},
]

def check_in_black_list(path,is_windows=False):
    for ry in RUYI_System_List:
        if path == ry['path']:
            return True
    if is_windows:
        for wd in Windows_System_List:
            if path == wd['path']:
                return True
    else:
        for lx in Linux_System_List:
            if path == lx['path']:
                return True
    return False

def check_no_delete(path,is_windows=False):
    """
    @name 检查哪些目录不能被删除
    @author lybbn<2024-02-22>
    """
    path = path.replace('//', '/')
    if path[-1:] == '/' or path[-1:] == '\\':
        path = path[:-1]
    if is_windows:
        drive_name = path.split(':')[0]
        if not drive_name:
            raise ValueError("路径错误")
        drive_name = drive_name.lower()
        path_without_drive =path.split(':')[1] if drive_name else None
        if not path_without_drive:
            raise ValueError("不能直接删除磁盘")
        path = drive_name+":"+path_without_drive
        for wd in Windows_System_List:
            if path == wd['path']:
                raise ValueError("【%s】不可删除！"%wd['desc'])
    for ry in RUYI_System_List:
        if path == ry['path']:
            raise ValueError("【%s】不可删除！"%ry['desc'])
    if not is_windows:
        for lx in Linux_System_List:
            if path == lx['path']:
                raise ValueError("【%s】不可删除！"%lx['desc'])