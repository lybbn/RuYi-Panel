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
import shutil
from utils.common import RunCommand,ReadFile,DeleteFile,WriteFile,check_is_port,check_is_ipv4,check_is_ipv6

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
        ret = os.popen('wmic cpu get NumberOfCores').read()
        cpuW = 0
        arrs = ret.strip().split('\n\n')
        for x in arrs:
            val = x.strip()
            if not val: continue
            try:
                val = int(val)
                cpuW += 1
            except:
                pass

        cache.set('lybbn_cpu_cpuW', cpuW, 86400)

    cpu_name = cache.get('lybbn_cpu_cpu_name')
    if not cpu_name:
        try:
            cpu_name = '{} * {}'.format(
                ReadReg(r'HARDWARE\DESCRIPTION\System\CentralProcessor\0', 'ProcessorNameString').strip(), cpuW);
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
        diskIo = psutil.disk_partitions();
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

def GetFileLastNumsLines(path,num=1000):
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
            return b'\n'.join(lines[-total_lines_wanted:])
    
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
        import subprocess
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
    # 遍历所有进程
    for proc in psutil.process_iter(['pid', 'name', 'cwd']):
        try:
            # # 过滤cmd进程
            # if proc.name() == 'cmd.exe':
            cwd = proc.info.get('cwd',"")
            cwd = cwd.replace("//",'/').replace("\\",'/') if cwd else ""
            if cwd and is_subdirectory(cwd,target_directory):
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
        subprocess.run(f'setx /m PATH "{bin_dir};%PATH%"',check=True)
    return True