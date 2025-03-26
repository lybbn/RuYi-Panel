#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-25
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# windows系统命令工具类封装
# ------------------------------

import re,sys
import wget
import pythoncom
import subprocess
import platform
import os, time
import psutil
import winreg
from django.conf import settings
from django.core.cache import cache
from pathlib import Path
import win32security
import win32com.client
import win32serviceutil
import win32service
import win32api
import win32netcon
import win32net
from typing import Tuple, Optional
import shutil
from datetime import datetime
from utils.common import RunCommand,ReadFile,DeleteFile,WriteFile,check_is_port,check_is_ipv4,check_is_ipv6,GetTmpPath

BASE_DIR = Path(__file__).resolve().parent

def ReadReg(path, key):
    """
    读取注册表
    @path 注册表路径
    @key 注册表键值
    """
    import winreg
    try:
        newKey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        value, type = winreg.QueryValueEx(newKey, key)
        return value
    except:
        return False

def get_file_name_from_url(url):
    """
    @name 使用 os.path.basename() 函数获取 URL 中的文件名
    @author lybbn<2024-02-22>
    """
    file_name = os.path.basename(url)
    return file_name

def download_url_file_wget(url, save_path=""):
    """
    @name 下载网络文件wget
    @save_path 下载本地路径名称（包含文件名），为空则默认存储在tmp中
    @author lybbn<2025-02-22>
    """
    try:
        if not save_path:
            save_directory = GetTmpPath()
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
            filename = get_file_name_from_url(url)
            save_path = os.path.join(save_directory, filename)
        else:
            save_directory = os.path.dirname(save_path)
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)

        # 如果文件已存在，跳过下载
        if os.path.exists(save_path):
            return True, "下载成功"

        # 下载文件
        wget.download(url, out=save_path, bar=None)

        return True, "下载成功"
    except Exception as e:
        return False, f"网络文件错误: {str(e)}"

def is_os_64bit():
    """
    判断是否x64系统
    """
    bites = {'AMD64': 64, 'x86_64': 64, 'i386': 32, 'x86': 32}
    info = platform.uname()
    if bites.get(info.machine) == 64:
        return True
    return False

def _check_is_app_setup(path, arrs):
    """
    查找软件是否安装
    @path 注册表路径
    @arrs 软件信息列表
    """
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    keynums = winreg.QueryInfoKey(key)[0]
    for i in range(int(keynums)):
        try:
            rKey = winreg.EnumKey(key, i)
            val = ReadReg(path + '\\' + rKey, 'DisplayName')
            if not val: continue
            num = 0
            for name in arrs:
                if val.find(name) >= 0:
                    num += 1
                else:
                    num = 0
            if len(arrs) == num: return True
        except:
            continue
    return False

def is_app_installed(arrs):
    """
    根据多个软件信息查找软件是否安装
    @arrs 软件信息列表
    """
    res = _check_is_app_setup(r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall', arrs)
    if not res:
        if is_os_64bit(): res = _check_is_app_setup(r'SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall', arrs)
    return res

def check_is_installed_vc(version="2013", bit='x64'):
    """
    根据php版本判断是否安装所需vc++
    @phpVersion php版本
    @bit 系统位数
    return bool 是否安装
    """
    arrs = ['Visual C++', bit]
    arrs.append(version)
    return is_app_installed(arrs)

def install_vc(version="2013", bit='x64',force=False):
    """
    安装vc++指定版本
    @version vc版本号
    @bit 系统位数
    @force 是否强制安装，不强制会检测系统是否已安装
    VC++ 2015-2022 是 向后兼容 的，安装最新版（14.x）即可覆盖 2015/2017/2019/2022 的需求。
    但某些旧软件（如 MySQL 5.7）可能强制要求 VC++ 2013，需单独安装。
    """
    if not force:
        if check_is_installed_vc(version=version,bit=bit):
            return True
    download_url_dict = {
        "2008x64":{
            "name":"vcredist_x64.exe",
            "url":"https://download.microsoft.com/download/5/D/8/5D8C65CB-C849-4025-8E95-C3966CAFD8AE/vcredist_x64.exe"
        },
        "2012x64":{
            "name":"vcredist_x64.exe",
            "url":"https://download.microsoft.com/download/1/6/B/16B06F60-3B20-4FF2-B699-5E9B7962F9AE/VSU_4/vcredist_x64.exe"
        },
        "2013x64":{
            "name":"vcredist_x64.exe",
            "url":"https://aka.ms/highdpimfc2013x64enu"
        },
        "2015x64":{
            "name":"VC_redist.x64.exe",
            "url":"https://aka.ms/vs/17/release/vc_redist.x64.exe"
        },
        "2017x64":{
            "name":"VC_redist.x64.exe",
            "url":"https://aka.ms/vs/17/release/vc_redist.x64.exe"
        },
        "2019x64":{
            "name":"VC_redist.x64.exe",
            "url":"https://aka.ms/vs/17/release/vc_redist.x64.exe"
        },
        "2022x64":{
            "name":"VC_redist.x64.exe",
            "url":"https://aka.ms/vs/17/release/vc_redist.x64.exe"
        },
    }
    datainfo = download_url_dict.get(version+bit,None)
    if not datainfo:return False
    download_url = datainfo['url']
    savePath = GetTmpPath()+"/"+datainfo['name']
    isok,msg = download_url_file_wget(download_url,save_path=savePath)
    if not isok:
        return False
    RunCommand(f"{savePath} /install /quiet /norestart")
    return True

def get_mac_address():
    """
    获取mac
    """
    import uuid
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e + 2] for e in range(0, 11, 2)])

def md5(strings):
    """
    @name 生成md5
    @param strings 要被处理的字符串
    @return string(32)
    """
    if type(strings) != bytes:
        strings = strings.encode()
    import hashlib
    m = hashlib.md5()
    m.update(strings)
    return m.hexdigest()


def to_size(size):
    """
    字节单位转换
    @size 字节大小
    return 返回带单位的格式(如：1 GB)
    """
    if not size: return '0.00 b'
    size = float(size)

    d = ('b', 'KB', 'MB', 'GB', 'TB')
    s = d[0]
    for b in d:
        if size < 1024: return ("%.2f" % size) + ' ' + b
        size = size / 1024
        s = b
    return ("%.2f" % size) + ' ' + b


def is_64bitos():
    """
    判断是否x64系统(windows、linux都适用)
    利用platform.uname()
    windows:uname_result(system='Windows', node='xxxxx', release='10', version='10.0.19042', machine='AMD64')
    linux:uname_result(system='Linux', node='xxxx', release='5.10.134-12.2.al8.x86_64', version='#1 SMP Thu Oct 27 10:07:15 CST 2022', machine='x86_64', processor='x86_64')
    """
    info = platform.uname()
    return info.machine.endswith('64')


def get_registry_value(key, subkey, value):
    """
    读取注册表信息
    @key 注册表类型
    @subkey 注册表路径
    @value 注册表具体key值
    """
    key = getattr(winreg, key)
    handle = winreg.OpenKey(key, subkey)
    (value, type) = winreg.QueryValueEx(handle, value)
    return value


def WriteLog(logMsg,EXEC_LOG_PATH=None):
    """
    写入LOG日志
    """
    try:
        with open(EXEC_LOG_PATH, 'w+') as f:
            f.write(logMsg)
            f.close()
    except:
        pass


def GetSystemVersion():
    """
    取操作系统版本
    """
    try:
        key = 'lybbn_sys_version'
        version = cache.get(key)
        if version: return version
        bit = 'x86'
        if is_64bitos(): bit = 'x64'

        def get(key):
            return get_registry_value("HKEY_LOCAL_MACHINE", "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", key)

        os = get("ProductName")
        build = get("CurrentBuildNumber")

        version = "%s (build %s) %s (Py%s)" % (os, build, bit, platform.python_version())
        cache.set(key, version, 10000)
        return version
    except Exception as ex:
        version = "未知系统版本"
        cache.set(key, version, 10000)
        return version

def GetSimpleSystemVersion():
    """
    取操作系统版本(简易 如windows 11 或centos 7)
    """
    try:
        key = 'lybbn_sys_simple_version'
        version = cache.get(key)
        if version: return version
        info = platform.uname()
        major_version = int(info.version.split(".")[0])
        version = "%s %s" % (info.system, major_version)
        cache.set(key, version, 10000)
        return version
    except Exception as ex:
        version = "未知系统版本"
        cache.set(key, version, 10000)
        return version

def GetLoadAverage():
    """
    取负载信息
    """
    data = {}
    data['one'] = 0
    data['five'] = 0
    data['fifteen'] = 0
    data['max'] = psutil.cpu_count() * 2
    data['limit'] = data['max']
    data['safe'] = data['max'] * 0.75
    data['percent'] = 0
    return data

def GetMemInfo():
    """
    取内存信息
    """
    mem = psutil.virtual_memory()
    memInfo = {}
    memInfo['percent'] = mem.percent
    memInfo['total'] = round(float(mem.total) / 1024 / 1024 / 1024, 2)
    memInfo['free'] = round(float(mem.free) / 1024 / 1024 / 1024, 2)
    memInfo['used'] = round(float(mem.used) / 1024 / 1024 / 1024, 2)
    return memInfo

def get_disk_iostat():
    """
    获取磁盘IO
    """
    iokey = 'iostat'
    diskio = cache.get(iokey)
    mtime = int(time.time())
    if not diskio:
        diskio = {}
        diskio['info'] = None
        diskio['time'] = mtime
    diskio_1 = diskio['info']
    stime = mtime - diskio['time']
    if not stime: stime = 1
    diskInfo = {}
    diskInfo['ALL'] = {}
    diskInfo['ALL']['read_count'] = 0
    diskInfo['ALL']['write_count'] = 0
    diskInfo['ALL']['read_bytes'] = 0
    diskInfo['ALL']['write_bytes'] = 0
    diskInfo['ALL']['read_time'] = 0
    diskInfo['ALL']['write_time'] = 0
    diskInfo['ALL']['read_merged_count'] = 0
    diskInfo['ALL']['write_merged_count'] = 0
    try:
        diskio_2 = psutil.disk_io_counters(perdisk=True)
        if not diskio_1:
            diskio_1 = diskio_2
        i = 0
        for disk_name in diskio_2.keys():
            disk_name_alias = "磁盘"+str(0)
            diskInfo[disk_name_alias] = {}
            diskInfo[disk_name_alias]['read_count'] = int((diskio_2[disk_name].read_count - diskio_1[disk_name].read_count) / stime)
            diskInfo[disk_name_alias]['write_count'] = int((diskio_2[disk_name].write_count - diskio_1[disk_name].write_count) / stime)
            diskInfo[disk_name_alias]['read_bytes'] = int((diskio_2[disk_name].read_bytes - diskio_1[disk_name].read_bytes) / stime)
            diskInfo[disk_name_alias]['write_bytes'] = int((diskio_2[disk_name].write_bytes - diskio_1[disk_name].write_bytes) / stime)
            diskInfo[disk_name_alias]['read_time'] = int((diskio_2[disk_name].read_time - diskio_1[disk_name].read_time) / stime)
            diskInfo[disk_name_alias]['write_time'] = int((diskio_2[disk_name].write_time - diskio_1[disk_name].write_time) / stime)
            diskInfo[disk_name_alias]['read_merged_count'] = 0
            diskInfo[disk_name_alias]['write_merged_count'] = 0

            diskInfo['ALL']['read_count'] += diskInfo[disk_name_alias]['read_count']
            diskInfo['ALL']['write_count'] += diskInfo[disk_name_alias]['write_count']
            diskInfo['ALL']['read_bytes'] += diskInfo[disk_name_alias]['read_bytes']
            diskInfo['ALL']['write_bytes'] += diskInfo[disk_name_alias]['write_bytes']
            if diskInfo['ALL']['read_time'] < diskInfo[disk_name_alias]['read_time']:
                diskInfo['ALL']['read_time'] = diskInfo[disk_name_alias]['read_time']
            if diskInfo['ALL']['write_time'] < diskInfo[disk_name_alias]['write_time']:
                diskInfo['ALL']['write_time'] = diskInfo[disk_name_alias]['write_time']
            diskInfo['ALL']['read_merged_count'] += diskInfo[disk_name_alias]['read_merged_count']
            diskInfo['ALL']['write_merged_count'] += diskInfo[disk_name_alias]['write_merged_count']
            i = i+1

        cache.set(iokey, {'info': diskio_2, 'time': mtime})
    except:
        return diskInfo
    return diskInfo

def GetNetWork():
    """
    获取网卡信息
    """

    cache_timeout = 86400
    otime = cache.get("otime")
    ntime = time.time()
    networkInfo = {}
    networkInfo['ALL'] = {}
    networkInfo['ALL']['upTotal'] = 0
    networkInfo['ALL']['downTotal'] = 0
    networkInfo['ALL']['up'] = 0
    networkInfo['ALL']['down'] = 0
    networkInfo['ALL']['downPackets'] = 0
    networkInfo['ALL']['upPackets'] = 0
    networkIo_list = psutil.net_io_counters(pernic=True)

    for net_key in networkIo_list.keys():
        if net_key.find('Loopback') >= 0 or net_key.find('Teredo') >= 0 or net_key.find('isatap') >= 0: continue

        networkIo = networkIo_list[net_key][:4]
        up_key = "{}_up".format(net_key)
        down_key = "{}_down".format(net_key)
        otime_key = "otime"

        if not otime:
            otime = time.time()

            cache.set(up_key, networkIo[0], cache_timeout)
            cache.set(down_key, networkIo[1], cache_timeout)
            cache.set(otime_key, otime, cache_timeout)

        networkInfo[net_key] = {}
        up = cache.get(up_key)
        down = cache.get(down_key)
        if not up:
            up = networkIo[0]
        if not down:
            down = networkIo[1]
        networkInfo[net_key]['upTotal'] = networkIo[0]
        networkInfo[net_key]['downTotal'] = networkIo[1]
        try:
            networkInfo[net_key]['up'] = round(float(networkIo[0] - up) / 1024 / (ntime - otime), 2)
            networkInfo[net_key]['down'] = round(float(networkIo[1] - down) / 1024 / (ntime - otime), 2)
        except:
            networkInfo['ALL']['up'] = 0
            networkInfo['ALL']['down'] = 0

            networkInfo[net_key]['up'] = 0
            networkInfo[net_key]['down'] = 0

        networkInfo[net_key]['downPackets'] = networkIo[3]
        networkInfo[net_key]['upPackets'] = networkIo[2]

        networkInfo['ALL']['upTotal'] += networkInfo[net_key]['upTotal']
        networkInfo['ALL']['downTotal'] += networkInfo[net_key]['downTotal']
        networkInfo['ALL']['up'] += networkInfo[net_key]['up']
        networkInfo['ALL']['down'] += networkInfo[net_key]['down']
        networkInfo['ALL']['downPackets'] += networkInfo[net_key]['downPackets']
        networkInfo['ALL']['upPackets'] += networkInfo[net_key]['upPackets']

        cache.set(up_key, networkIo[0], cache_timeout)
        cache.set(down_key, networkIo[1], cache_timeout)
        cache.set(otime_key, time.time(), cache_timeout)

    networkInfo['ALL']['up'] = round(float(networkInfo['ALL']['up']), 2)
    networkInfo['ALL']['down'] = round(float(networkInfo['ALL']['down']), 2)

    return networkInfo

def GetBootTime():
    """
    取系统启动时间
    """
    key = 'lybbn_sys_time'
    sys_time = cache.get(key)
    if sys_time: return sys_time
    import math
    tStr = time.time() - psutil.boot_time()
    min = tStr / 60
    hours = min / 60
    days = math.floor(hours / 24)
    hours = math.floor(hours - (days * 24))
    min = math.floor(min - (days * 60 * 24) - (hours * 60))
    sys_time = "{}天".format(int(days))
    cache.set(key, sys_time, 1800)
    return sys_time


def get_physical_cpu_count():
    try:
        # 连接到 WMI
        wmi = win32com.client.GetObject("winmgmts:")
        # 查询 CPU 信息
        cpus = wmi.InstancesOf("Win32_Processor")
        # 统计物理 CPU 颗数
        device_ids = set()
        for cpu in cpus:
            device_ids.add(cpu.Properties_("DeviceID").Value)
        return len(device_ids)
    except:
        return 1

def GetCpuInfo(interval=1):
    """
    取CPU详细信息
    """
    cpuCount = cache.get('lybbn_cpu_cpuCount')
    if not cpuCount:
        cpuCount = psutil.cpu_count()
        cache.set('lybbn_cpu_cpuCount', cpuCount, 86400)
    cpuNum = cache.get('lybbn_cpu_cpuNum')
    if not cpuNum:
        cpuNum = psutil.cpu_count(logical=False)
        cache.set('lybbn_cpu_cpuNum', cpuNum, 86400)

    # used = cache.get('lybbn_cpu_used')
    # if not used:
    #     used = psutil.cpu_percent(interval)
    #     cache.set('lybbn_cpu_used',used,20)

    used_all = cache.get('lybbn_cpu_used_all')
    if not used_all:
        used_all = psutil.cpu_percent(percpu=True)

    used_total = 0
    for x in used_all: used_total += x

    cpuW = cache.get('lybbn_cpu_cpuW')
    if not cpuW:
        # ret = os.popen('wmic cpu get NumberOfCores').read()
        # cpuW = 0
        # arrs = ret.strip().split('\n\n')
        # for x in arrs:
        #     val = x.strip()
        #     if not val: continue
        #     try:
        #         val = int(val)
        #         cpuW += 1
        #     except:
        #         pass
        cpuW = get_physical_cpu_count()
            
        cache.set('lybbn_cpu_cpuW', cpuW, 86400)

    cpu_name = cache.get('lybbn_cpu_cpu_name')
    if not cpu_name:
        try:
            cpu_name = '{} * {}'.format(
                ReadReg(r'HARDWARE\DESCRIPTION\System\CentralProcessor\0', 'ProcessorNameString').strip(), cpuW)
        except:
            cpu_name = ''
        cache.set('lybbn_cpu_cpu_name', cpu_name, 86400)

    tmp = 0
    if cpuW:
        tmp = cpuNum / cpuW

    used = 0
    if used_total:
        used = round(used_total / cpuCount, 2)
    return used, cpuCount, used_all, cpu_name, tmp, cpuW


def GetDiskInfo():
    """
    取磁盘分区信息
    """
    key = 'lybbn_sys_disk'
    diskInfo = cache.get(key)
    if diskInfo: return diskInfo
    try:
        diskIo = psutil.disk_partitions()
    except:
        import string
        diskIo = []
        for c in string.ascii_uppercase:
            disk = c + ':'
            if os.path.isdir(disk):
                data = {}
                data['mountpoint'] = disk + '/'
                diskIo.append(data)

    diskInfo = []
    for disk in diskIo:
        try:
            tmp = {}
            tmp['path'] = disk.mountpoint.replace("\\", "/")
            usage = psutil.disk_usage(disk.mountpoint)
            tmp['size'] = [to_size(usage.total), to_size(usage.used), to_size(usage.free), usage.percent]
            tmp['inodes'] = False
            diskInfo.append(tmp)
        except:
            pass
    cache.set(key, diskInfo, 10)
    return diskInfo

def GetFileLastNumsLines(path,num=1000, encoding='utf-8', errors='replace'):
    """
    获取指定文件的指定尾行数内容
    """
    if not os.path.exists(path): 
        return ""
    
    filesize = os.path.getsize(path)
    if filesize == 0: 
        return ""
    
    num = int(num)
    total_lines_wanted = num
    BLOCK_SIZE = 4096  # 每次读取4KB大小
    lines = []
    
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)  # 定位到文件末尾
            block_end_byte = f.tell()
            lines_to_go = total_lines_wanted
            
            while lines_to_go > 0 and block_end_byte > 0:
                # 计算块的起始位置
                block_start_byte = max(block_end_byte - BLOCK_SIZE, 0)
                f.seek(block_start_byte)
                block = f.read(block_end_byte - block_start_byte)
                
                # 查找换行符
                block_lines = block.split(b'\n')
                lines_to_go -= len(block_lines)
                
                # 将读取的块的所有行添加到结果
                lines = block_lines + lines
                block_end_byte = block_start_byte
            
            # 确保只返回需要的行数
            byte_data = b'\n'.join(lines[-total_lines_wanted:])
            return byte_data.decode(encoding, errors=errors)
    
    except Exception as e:
        return ""

firewall_protocol_map = {
    1: "ICMP",
    6: "TCP",
    17: "UDP",
    41: "IPv6",
    47: "GRE",
    48: "ESP",
    58: "ICMPv6",
    255: "ALL",
}

firewall_action_map = {
    0:"block",
    1:"allow",
}

firewall_profiles_map = {
    1:"domain",
    2:"private",
    4:"public",
    6:"private,public",
    7:"all",
    2147483647:"all",
}

firewall_api_items_name_map = {
    "Action":'操作',
    "ApplicationName":'程序',
    "Description":'描述',
    "Direction":'进站/出站',
    "EdgeTraversal":'边缘穿越',
    "EdgeTraversalOptions":'边缘穿越选项',
    "Enabled":'已启用',
    "Grouping":'组',
    "IcmpTypesAndCodes":'ICMP设置',
    "InterfaceTypes":'接口类型',
    "Interfaces":'接口',
    "LocalAddresses":'本地地址', # * 所有IP
    "LocalAppPackageId":'应用程序包',
    "LocalPorts":'本地端口',
    "LocalUserAuthorizedList":'授权的本地计算机',
    "LocalUserOwner":'本地用户所有者',
    "Name":'名称',
    "Profiles":'配置文件',
    "Protocol":'协议',
    "RemoteAddresses":'远程地址',
    "RemoteMachineAuthorizedList":'授权的远程计算机',
    "RemotePorts":'远程端口',
    "RemoteUserAuthorizedList":'授权的远程用户',
    "SecureFlags":'安全',
    "serviceName":'服务名'
}

def GetFirewallRules(param = {"dir":"in"}):
    """
    @author:lybbn
    获取防火墙规则列表(不含动态规则)
    dir:方向 in、out、all
    """
    data = []
    try:
        # 初始化 COM
        pythoncom.CoInitialize()
        fw_policy = win32com.client.Dispatch('HNetCfg.FwPolicy2')
        fw_rules = fw_policy.Rules
        dir = param.get("dir","in")
        search = param.get("search",None)
        status = str(param.get("status",""))
        if dir in ["in","out"]:
            if dir == "in":
                dir = 1
            else:
                dir = 2
        elif dir == "all":
            dir = 0
        else:
            return []
        for line in fw_rules:
            try:
                if dir and not dir == line.Direction:
                    continue
                if line.Protocol not in [6,17]:#只获取tcp、udp
                    continue
                rulename = line.Name
                rulestatus = line.Enabled
                local_ips = getattr(line, 'LocalAddresses', '')
                remote_ips = getattr(line, 'RemoteAddresses', '')
                local_ports = getattr(line, 'LocalPorts', '')
                remote_ports = getattr(line, 'RemotePorts', '')
                if search:
                    if str(rulename).lower().find(search.lower()) == -1:#未找到
                        continue
                if status:
                    if status == "false" and not rulestatus:
                        pass
                    elif status == "true" and rulestatus:
                        pass
                    else:
                        continue
                if not local_ports:
                    if line.Protocol in [1]:
                        local_ports = "*"
                    else:
                        continue
                if remote_ips == "LocalSubnet":
                    continue
                if line.Profiles not in [2,4,6,7,2147483647]:#只取私有、公共、和所有 作用域
                    continue
                ApplicationName = line.ApplicationName
                if line.ApplicationName == "System":
                    continue
                else:
                    APNameKeywords = ["svchost.exe", "mdeserver.exe","wmplayer.exe","wmpnetwk.exe","msdtc.exe","spoolsv.exe","vdsldr.exe","vds.exe","snmptrap.exe","unsecapp.exe","RmtTpmVscMgrSvr.exe","lsass.exe","proximityuxhost.exe","wininit.exe","NetEvtFwdr.exe","WUDFHost.exe","CastSrv.exe","msra.exe","deviceenroller.exe","omadmclient.exe","dmcertinst.exe"]
                    is_apname_jump_step = False
                    for i in APNameKeywords:
                        if ApplicationName and ApplicationName.endswith(i):
                            is_apname_jump_step = True
                            break
                    if is_apname_jump_step:
                        continue
                GroupKeywords = ["IncrediBuild", "iSCSI", "Game Bar","mDNS","Media Center","Microsoft","Windows","WLAN","Wi-Fi","TPM","SNMP"]
                is_jump_step = False
                for i in GroupKeywords:
                    if line.Grouping and line.Grouping.startswith(i):
                        is_jump_step = True
                        break
                if is_jump_step:
                    continue
                tempdic = {}
                tempdic['name'] = rulename#规则名
                tempdic['status'] = rulestatus#状态
                tempdic['direction'] = "in" if line.Direction == 1 else "out"
                tempdic['protocol'] = firewall_protocol_map.get(line.Protocol, str(line.Protocol))
                tempdic['profiles'] = firewall_profiles_map.get(line.Profiles, str(line.Profiles))
                tempdic['localip'] = local_ips
                tempdic['remoteip'] = remote_ips
                tempdic['localport'] = local_ports
                tempdic['remoteport'] = remote_ports
                tempdic['handle'] = firewall_action_map.get(line.Action, str(line.Action))
                if tempdic not in data:#过滤重复项
                    data.append(tempdic)
            except:
                continue

    except Exception as e:
        print(f"Error get firewall rule list: {e}")
        return []
    finally:
        # 清理 COM
        pythoncom.CoUninitialize()
    return data

def GetFirewallStatus():
    """
    取防火墙状态(当前网络连接的防火墙)
    """
    try:
        # 初始化 COM
        pythoncom.CoInitialize()
        fw_mgr = win32com.client.Dispatch("HNetCfg.FwMgr")
        firewall_enabled = fw_mgr.LocalPolicy.CurrentProfile.FirewallEnabled
        return firewall_enabled
    except Exception as e:
        pass
    finally:
        # 清理 COM
        pythoncom.CoUninitialize()
    return True

def StartFirewall():
    """
    启动防火墙(当前网络连接的防火墙) 需管理员权限运行
    """
    try:
        # 初始化 COM
        pythoncom.CoInitialize()
        fw_mgr = win32com.client.Dispatch("HNetCfg.FwMgr")
        profile = fw_mgr.LocalPolicy.CurrentProfile
        profile.FirewallEnabled = True
        return True
    except Exception as e:
        return False
    finally:
        # 清理 COM
        pythoncom.CoUninitialize()

def StartFirewall2():
    """
    启动防火墙("Private","Public" 网络环境) 需管理员权限运行
    """
    try:
        subprocess.run(['netsh', 'advfirewall', 'set', 'allprofiles', 'state', 'on'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, check=True)
        return True
    except:
        return False

def StopFirewall():
    """
    关闭防火墙(当前网络连接的防火墙) 需管理员权限运行
    """
    try:
        # 初始化 COM
        pythoncom.CoInitialize()
        fw_mgr = win32com.client.Dispatch("HNetCfg.FwMgr")
        profile = fw_mgr.LocalPolicy.CurrentProfile
        profile.FirewallEnabled = False
        return True
    except:
        return False
    finally:
        # 清理 COM
        pythoncom.CoUninitialize()
    
def StopFirewall2():
    """
    关闭防火墙("Private","Public" 网络环境) 需管理员权限运行
    """
    try:
        subprocess.run(['netsh', 'advfirewall', 'set', 'allprofiles', 'state', 'off'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, check=True)
        return True
    except:
        return False

def SetFirewallStatus(status = ""):
    """
    设置防火墙状态
    """
    if status not in ['stop', 'start']:
        return False, '类型错误'
    f_status = GetFirewallStatus()
    if status == "start":
        if f_status:
            return True, "启动防火墙成功"
        else:
            if StartFirewall2():
                return True, "启动防火墙成功"
            else:
                return False, "启动防火墙失败"
    else:
        if not f_status:
            return True, "关闭防火墙成功"
        else:
            if StopFirewall2():
                return True, "关闭防火墙成功"
            else:
                return False, "关闭防火墙失败"

def GetFirewallInfo():
    """
    获取防火墙信息
    """
    ping = False
    if os.path.exists(settings.RUYI_PING_FILE):ping = True
    data = {
        'installed':True,
        'status':GetFirewallStatus(),
        'version':"",
        'name':"",
        'ping':ping
    }
    return data

def SetFirewallPing(status = True):
    """
    设置防火墙Ping（需管理员权限）
    status: True 禁止ping、False 允许ping
    """
    if status:
        command = 'netsh advfirewall firewall add rule name="RUYI Block Ping Inbound" dir=in action=block protocol=1 profile=any enable=yes'
    else:
        command = 'netsh advfirewall firewall delete rule name="RUYI Block Ping Inbound"'
    resout,reserr,code = RunCommand(command,returncode=True)
    if code == 0:
        if status:
            WriteFile(settings.RUYI_PING_FILE,"1")
        else:
            DeleteFile(settings.RUYI_PING_FILE,empty_tips=False)
        return True,""
    else:
         # 处理特定错误信息
        if "Invalid value specified" in reserr or "指定的值无效" in reserr:
            if status:
                WriteFile(settings.RUYI_PING_FILE,"1")
            else:
                DeleteFile(settings.RUYI_PING_FILE,empty_tips=False)
            return True,""
        else:
            return False,reserr


def SetFirewallRuleStatus(param={}):
    """
    设置防火墙规则状态(需管理员权限)
    """
    rule_name = param.get("name","")
    status = param.get("status",True)
    statusname = "yes"
    if not status:
        statusname = "no"
    command = f'netsh advfirewall firewall set rule name="{rule_name}" new enable={statusname}'
    try:
        subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, check=True)
        return True
    except:
        return False
    
def SetFirewallRuleAction(param={}):
    """
    设置防火墙规则策略(需管理员权限)
    """
    rule_name = param.get("name","")
    action = param.get("handle","")
    if action not in ["allow","block"]:
        return False
    command = f'netsh advfirewall firewall set rule name="{rule_name}" new action={action}'
    try:
        subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, check=True)
        return True
    except:
        return False

def AddFirewallRule(param={}):
    """
    添加防火墙规则(需管理员权限)
    """
    rule_name = param.get("name","")
    protocol = param.get("protocol","")
    localport = param.get("localport","")
    direction = param.get("direction","")
    action = param.get("handle","")
    command = f"netsh advfirewall firewall add rule name={rule_name} dir={direction} action={action} protocol={protocol}"
    if localport and not localport == "*":
        command = command + f' localport={localport}'
    sout,serr,code = RunCommand(command,returncode=True)
    if code == 0:
        return True
    return False

def EditFirewallRule(param={}):
    """
    编辑防火墙规则(需管理员权限)
    """
    rule_name = param.get("name","")
    localport = param.get("localport","")
    action = param.get("handle","")
    if action not in ["allow","block"]:
        return False
    command = f'netsh advfirewall firewall set rule name="{rule_name}" new action={action} localport={localport}'
    try:
        subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, check=True)
        return True
    except:
        return False

def DelFirewallRule(param={}):
    """
    删除防火墙规则(需管理员权限)
    """
    try:
        rule_name = param.get("name","")
        if not rule_name:return False
        protocol = param.get("protocol","")
        localport = param.get("localport","")
        command = f'netsh advfirewall firewall delete rule name="{rule_name}"'
        if protocol:
            protocol = protocol.lower()
            if protocol not in ['tcp','udp']:return False
            command = command + f" protocol={protocol}"
        if localport and not localport == "*":
            command = command + f" localport={localport}"
        subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, check=True)
        return True
    except:
        return False

def GetPortProxyRules(param={}):
    """
    取所有端口转发列表
    """
    search = param.get("search",None)
    ret = RunCommand('netsh interface portproxy show all')[0]
    tmpdatas = re.findall(r"(.+?)\s+(\d+?)\s+(.+?)\s+(\d+)",ret)
    data = []

    for d in tmpdatas:
        item = {}
        item['localip'] = d[0].strip()
        item['localport'] = d[1].strip()
        item['remoteip'] = d[2].strip()
        item['remoteport'] = d[3].strip()

        if search:
            hasContent = False
            for i in item:
                if item[i].find(search.lower()) > -1:
                    hasContent = True
                    break
            if not hasContent:
                continue
        data.append(item)
    return data

def AddPortProxyRules(param={}):
    """
    添加端口转发
    """
    localport = param.get("localport",0)
    remoteport = param.get("remoteport",0)
    remoteip = param.get("remoteip","")
    if not check_is_port(localport):
        return False,"源端口格式错误：1-65535"
    if not check_is_port(remoteport):
        return False,"目标端口格式错误：1-65535"
    if not check_is_ipv4(remoteip):
        return False,"ip格式错误，应为ipv4"
    command = f"netsh interface portproxy add v4tov4 listenport={localport} listenaddress=0.0.0.0 connectport={remoteport} connectaddress={remoteip}"
    sout,serr,code = RunCommand(command,returncode=True)
    if code == 0:
        return True,""
    return False,serr

def DelPortProxyRules(param={}):
    """
    删除端口转发规则
    """
    try:
        localport = param.get("localport",0)
        if not check_is_port(localport):
            return False,"源端口格式错误：1-65535"
        command = f'netsh interface portproxy delete v4tov4 listenaddress="0.0.0.0"  listenport="{localport}"'
        subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, check=True)
        return True,""
    except:
        return False,"删除失败"
    
def RestartServer():
    """
    重启系统
    """
    try:
        os.system("shutdown /r /f /t 0")
    except:
        pass

def RestartRuyi():
    """
    重启如意
    """
    try:
        pid = os.getpid()
        subprocess.run(["start.bat", str(pid)], check=True)
    except:
        pass

def GetUidName(file_path,uid=0):
    """
    通过系统uid获取对应名称
    """
    #如果运行GetUidName在file_path所在的分区，可能导致文件占用导致获取失败
    try:
        security_descriptor = win32security.GetFileSecurity(file_path, win32security.OWNER_SECURITY_INFORMATION)
        owner_sid = security_descriptor.GetSecurityDescriptorOwner()
        owner_name, domain_name, type = win32security.LookupAccountSid(None, owner_sid)
        return owner_name
    except Exception as e:
        return ""
    
def GetGroupidName(file_path,gid=0):
    """
    通过系统goup id（所属组id）获取对应名称
    """
    try:
        group_sid = win32security.GetFileSecurity(file_path, win32security.GROUP_SECURITY_INFORMATION).GetSecurityDescriptorGroup()
        group_name, domain, type = win32security.LookupAccountSid(None, group_sid)
        return group_name
    except Exception as e:
        return ""

def is_subdirectory(child_path, parent_path):
    child = Path(child_path).resolve()
    parent = Path(parent_path).resolve()
    child_path = str(child)
    parent_path = str(parent)
    if child_path == parent_path:
        return True
    elif parent_path in child_path:
        return True
    return False

def kill_cmd_if_working_dir(target_directory):
    target_directory = target_directory.replace("//",'/').replace("\\",'/')
    import signal
    safe_processes = ['python.exe', 'pythonw.exe', 'django.exe']  # 不杀死这些进程
    # 遍历所有进程
    for proc in psutil.process_iter(['pid', 'name', 'cwd']):
        try:
            # # 过滤cmd进程
            # if proc.name() == 'cmd.exe':
            cwd = proc.info.get('cwd',"")
            cwd = cwd.replace("//",'/').replace("\\",'/') if cwd else ""
            if cwd and is_subdirectory(cwd,target_directory) and proc.name() not in safe_processes:
                # 打印进程信息
                print(f"Killing process Name:{proc.name()} with PID: {proc.pid} working directory: {cwd}")
                # 杀死进程
                proc.send_signal(signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def ForceRemoveDir(directory):
    """
    强制删除目录(或文件)
    """
    if os.path.exists(directory):
        try:
            os.chmod(directory, 0o777)
            shutil.rmtree(directory)
        except OSError as e:
            try:
                kill_cmd_if_working_dir(directory)
                shutil.rmtree(directory)
            except:
                raise ValueError(f"目录被占用：{directory}")
        except Exception as e:
            raise ValueError(f"强制删除目录错误: {e}")
        
def AddBinToPath(bin_dir):
    """
    添加命令到系统路径（环境变量）(管理员权限)
    """
    current_path = os.environ.get('PATH', '')
    if bin_dir not in current_path:
        updated_path = f"{bin_dir};{current_path}"
        os.environ['PATH'] = updated_path
        res = backup_system_path()
        if not res:return False
        # subprocess.run(f'setx /m PATH "{updated_path}',check=True)
        add_to_system_path(bin_dir)
    return True

def backup_system_path():
    """备份当前的 PATH 值到文件"""
    try:
        # 打开系统环境变量的注册表键
        reg_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
            0,
            winreg.KEY_READ
        )

        # 获取当前的 PATH 值
        current_path, _ = winreg.QueryValueEx(reg_key, 'Path')

        # 关闭注册表键
        winreg.CloseKey(reg_key)

        # 生成备份文件名（包含当前时间）
        backup_file = f"{GetTmpPath()}/system_path_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        # 将 PATH 值写入备份文件
        with open(backup_file, 'w') as f:
            f.write(current_path)

        print(f"当前 PATH 已备份到文件: {backup_file}")
        return backup_file
    except Exception as e:
        print(f"备份 PATH 时出错: {e}")
        return None

def add_to_system_path(new_path):
    import ctypes
    # 打开系统环境变量的注册表键
    reg_key = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
        0,
        winreg.KEY_ALL_ACCESS
    )

    try:
        # 获取当前的 PATH 值
        current_path, reg_type = winreg.QueryValueEx(reg_key, 'Path')

        # 检查新路径是否已经存在
        if new_path in current_path:
            return

        # 更新 PATH
        updated_path = f"{current_path};{new_path}"
        winreg.SetValueEx(reg_key, 'Path', 0, reg_type, updated_path)

    finally:
        # 关闭注册表键
        winreg.CloseKey(reg_key)

    # 广播环境变量更改
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x02, 5000, None)

def get_service_status(name: str) -> int:
    """
    获取 Windows 服务状态
    
    参数:
        name: 服务名称
        
    返回:
        -1: 服务未安装
        0: 服务已停止
        1: 服务正在运行
        2: 服务正在启动
        3: 服务正在停止
        4: 服务已暂停
        5: 服务继续等待
        6: 服务暂停等待
    """
    try:
        status = win32serviceutil.QueryServiceStatus(name)
        current_state = status[1]
        
        # 更详细的状态返回
        state_map = {
            win32service.SERVICE_STOPPED: 0,
            win32service.SERVICE_START_PENDING: 2,
            win32service.SERVICE_STOP_PENDING: 3,
            win32service.SERVICE_RUNNING: 1,
            win32service.SERVICE_CONTINUE_PENDING: 5,
            win32service.SERVICE_PAUSE_PENDING: 6,
            win32service.SERVICE_PAUSED: 4,
        }
        
        return state_map.get(current_state, -1)
    except win32service.error as e:
        if e.winerror == 1060:  # 服务不存在
            return -1
        return -1

def install_as_service(
    name: str,
    display_name: str,
    path: str,
    args: Optional[str] = None,
    description: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    start_type: int = win32service.SERVICE_AUTO_START,
    dependencies: Optional[list] = None
) -> Tuple[bool, str]:
    """
    安装程序为 Windows 系统服务
    
    参数:
        name: 服务名称
        display_name: 显示名称
        path: 可执行文件路径
        args: 服务启动参数
        description: 服务描述
        username: 启动用户(格式: "Domain\\Username" 或 ".\\Username" 本地用户)
        password: 用户密码
        start_type: 启动类型 (默认自动启动)
        dependencies: 依赖的服务列表
        
    返回:
        (成功状态, 错误信息)
    """
    try:
        # 规范化路径和用户名
        path = path.replace('/', '\\')
        
        if username and '\\' not in username:
            username = f'.\\{username}'
        
        # 检查是否已安装
        if get_service_status(name) != -1:
            return True, f"服务 '{name}' 已存在"
        
        # 安装服务
        win32serviceutil.InstallService(
            pythonClassString=None,  # 不使用Python服务类
            serviceName=name,
            displayName=display_name,
            startType=start_type,
            errorControl=win32service.SERVICE_ERROR_NORMAL,
            bRunInteractive=0,
            serviceDeps=dependencies,
            userName=username,
            password=password,
            exeName=path,
            perfMonIni=None,
            perfMonDll=None,
            exeArgs=args,
            description=description,
            delayedstart=None
        )
        
        # 验证安装是否成功
        if get_service_status(name) == -1:
            return False, "服务安装失败"
            
        return True, "服务安装成功"
        
    except win32service.error as e:
        error_msg = f"安装服务失败: {win32api.FormatMessage(e.winerror)}"
        return False, error_msg
    except Exception as e:
        return False, f"未知错误: {str(e)}"

def set_service_status(name: str, action: str) -> Tuple[bool, str]:
    """
    设置服务状态
    
    参数:
        name: 服务名称
        action: 操作 (start/stop/restart/pause/continue)
        
    返回:
        (成功状态, 错误信息)
    """
    try:
        action = action.lower()
        valid_actions = {'start', 'stop', 'restart', 'pause', 'continue'}
        
        if action not in valid_actions:
            return False, f"无效的操作: {action}"
            
        if get_service_status(name) == -1:
            return False, f"服务 '{name}' 不存在"
            
        if action == 'start':
            win32serviceutil.StartService(name)
        elif action == 'stop':
            win32serviceutil.StopService(name)
        elif action == 'restart':
            win32serviceutil.RestartService(name)
        elif action == 'pause':
            win32serviceutil.PauseService(name)
        elif action == 'continue':
            win32serviceutil.ResumeService(name)
            
        return True, f"服务 '{name}' 已成功 {action}"
        
    except win32service.error as e:
        error_msg = f"操作失败: {win32api.FormatMessage(e.winerror)}"
        return False, error_msg
    except Exception as e:
        return False, f"未知错误: {str(e)}"

def uninstall_service(name: str) -> Tuple[bool, str]:
    """
    卸载 Windows 服务
    
    参数:
        name: 服务名称
        
    返回:
        (成功状态, 错误信息)
    """
    try:
        if get_service_status(name) == -1:
            return False, f"服务 '{name}' 不存在"
            
        # 先停止服务
        set_service_status(name, 'stop')
        
        # 卸载服务
        win32serviceutil.RemoveService(name)
        
        # 验证是否卸载成功
        if get_service_status(name) != -1:
            return False, "服务卸载失败"
            
        return True, f"服务 '{name}' 已成功卸载"
        
    except win32service.error as e:
        error_msg = f"卸载失败: {win32api.FormatMessage(e.winerror)}"
        return False, error_msg
    except Exception as e:
        return False, f"未知错误: {str(e)}"
    
def check_user_exists(username: str) -> bool:
    """
    检查用户是否已存在
    
    参数:
        username: 要检查的用户名
        
    返回:
        bool: 用户是否存在
    """
    try:
        resume_handle = 0
        while True:
            users, total, resume = win32net.NetUserEnum(
                None,  # 本地计算机
                3,  # 用户信息级别
                win32netcon.FILTER_NORMAL_ACCOUNT,
                resume_handle
            )
            for user in users:
                if user['name'].lower() == username.lower():
                    return True
            if not resume:
                break
        return False
    except win32net.error as e:
        raise RuntimeError(f"检查用户失败: {win32api.FormatMessage(e.winerror)}") from e

def create_service_account(
    username: str,
    password: str,
    description: str = "Service account",
    allow_service_logon: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    创建服务账户并设置必要权限
    
    参数:
        username: 用户名
        password: 密码
        description: 账户描述
        allow_service_logon: 是否允许作为服务登录
        
    返回:
        (成功状态, 错误信息)
    """
    try:
        # 1. 检查用户是否已存在
        if check_user_exists(username):
            return True, f"用户 '{username}' 已存在"

        # 2. 准备用户信息
        user_info = {
            'name': username,
            'password': password,
            'priv': win32netcon.USER_PRIV_USER,
            'flags': win32netcon.UF_NORMAL_ACCOUNT | win32netcon.UF_SCRIPT,
            'comment': description,
            'password_age': 0,
            'home_dir': None,
            'script_path': None
        }

        # 3. 创建用户
        win32net.NetUserAdd(None, 1, user_info)

        # 4. 验证用户是否创建成功
        if not check_user_exists(username):
            return False, f"用户 '{username}' 创建失败"

        # 5. 设置服务登录权限
        if allow_service_logon:
            _grant_service_logon_right(username)

        return True, None

    except win32net.error as e:
        return False, f"创建用户失败: {win32api.FormatMessage(e.winerror)}"
    except Exception as e:
        return False, f"未知错误: {str(e)}"

def _grant_service_logon_right(username: str) -> Tuple[bool, Optional[str]]:
    """
    授予用户作为服务登录的权限
    
    参数:
        username: 用户名
        
    返回:
        (成功状态, 错误信息)
    """
    try:
        # 1. 获取用户SID
        sid, domain, account_type = win32security.LookupAccountName(None, username)
        
        # 2. 打开本地安全策略
        policy = win32security.LsaOpenPolicy(
            None,
            win32security.POLICY_ALL_ACCESS
        )
        
        # 3. 添加服务登录权限
        win32security.LsaAddAccountRights(
            policy,
            sid,
            ('SeServiceLogonRight',)
        )
        
        # 4. 关闭策略句柄
        win32security.LsaClose(policy)
        
        return True, None
        
    except win32security.error as e:
        return False, f"授予权限失败: {win32api.FormatMessage(e.winerror)}"
    except Exception as e:
        return False, f"未知错误: {str(e)}"