#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | django-vue-lyadmin
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
# linux系统命令工具类封装
# ------------------------------
import pwd
import grp
import os, sys, re, time, json
import psutil
from django.core.cache import cache
from pathlib import Path
import subprocess
import platform
from utils.common import check_is_ipv4,check_is_port,RunCommand,GetLinuxFirewallStatus,RunCommandReturnCode,ReadFile,WriteFile,is_service_running,ParseXMLFile

BASE_DIR = Path(__file__).resolve().parent

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

def WriteLog(logMsg,EXEC_LOG_PATH=None):
    """
    写日志
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
    key = 'lybbn_sys_version'
    version = cache.get(key)
    if version: return version
    try:
        # Python 3.8 已移除 此方法 "linux_distribution()"
        platform_dist = platform.linux_distribution()
        version = platform_dist[0] + " " + platform_dist[1]
    except:
        with os.popen("cat /etc/redhat-release", "r") as p:
            release = p.read()
        version = release.replace('release ', '').replace('Linux', '').replace('(Core)', '').strip()

    pyv_info = sys.version_info
    version = "{} {}(Py{}.{}.{})".format(version, os.uname().machine, pyv_info.major, pyv_info.minor, pyv_info.micro)
    cache.set(key, version, 86400)
    return version


def GetSimpleSystemVersion():
    """
    取操作系统版本(简易 如windows 11 或centos 7)
    """
    key = 'lybbn_sys_simple_version'
    version = cache.get(key)
    if version: return version
    try:
        # Python 3.8 已移除 此方法 "linux_distribution()"
        platform_dist = platform.linux_distribution()
        version = platform_dist[0] + " " + platform_dist[1]
    except:
        with os.popen("cat /etc/redhat-release", "r") as p:
            release = p.read()
        version = release.replace('release ', '').replace('Linux', '').replace('(Core)', '').strip()

    version = "{} {}".format(version, os.uname().machine)
    cache.set(key, version, 86400)
    return version

def GetLoadAverage():
    """
    取系统负载
    """
    try:
        c = os.getloadavg()
    except:
        c = [0, 0, 0]
    data = {}
    data['one'] = float(c[0])
    data['five'] = float(c[1])
    data['fifteen'] = float(c[2])
    data['max'] = psutil.cpu_count() * 2
    data['limit'] = data['max']
    data['safe'] = data['max'] * 0.75
    temppercent = round(data['one'] / data['max'] * 100)
    data['percent'] = 100 if temppercent > 100 else temppercent
    return data


def GetMemInfo():
    """
    取内存信息
    """
    mem = psutil.virtual_memory()
    memInfo = {}
    memInfo2 = {'memTotal': int(mem.total / 1024 / 1024), 'memFree': int(mem.free / 1024 / 1024),
                'memBuffers': int(mem.buffers / 1024 / 1024), 'memCached': int(mem.cached / 1024 / 1024)}
    memInfo['total'] = round(float(mem.total) / 1024 / 1024 / 1024, 2)
    memInfo['free'] = round((memInfo2['memFree'] + memInfo2['memBuffers'] + memInfo2['memCached']) / 1024, 2)
    memInfo['used'] = round(float(mem.used) / 1024 / 1024 / 1024, 2)
    memInfo['percent'] = round((int(mem.used) / 1024 / 1024) / memInfo2['memTotal'] * 100, 1)
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
        if os.path.exists('/proc/diskstats'):
            diskio_2 = psutil.disk_io_counters(perdisk=True)
            if not diskio_1:
                diskio_1 = diskio_2
            for disk_name in diskio_2.keys():
                diskInfo[disk_name] = {}
                diskInfo[disk_name]['read_count'] = int(
                    (diskio_2[disk_name].read_count - diskio_1[disk_name].read_count) / stime)
                diskInfo[disk_name]['write_count'] = int(
                    (diskio_2[disk_name].write_count - diskio_1[disk_name].write_count) / stime)
                diskInfo[disk_name]['read_bytes'] = int(
                    (diskio_2[disk_name].read_bytes - diskio_1[disk_name].read_bytes) / stime)
                diskInfo[disk_name]['write_bytes'] = int(
                    (diskio_2[disk_name].write_bytes - diskio_1[disk_name].write_bytes) / stime)
                diskInfo[disk_name]['read_time'] = int(
                    (diskio_2[disk_name].read_time - diskio_1[disk_name].read_time) / stime)
                diskInfo[disk_name]['write_time'] = int(
                    (diskio_2[disk_name].write_time - diskio_1[disk_name].write_time) / stime)
                diskInfo[disk_name]['read_merged_count'] = int(
                    (diskio_2[disk_name].read_merged_count - diskio_1[disk_name].read_merged_count) / stime)
                diskInfo[disk_name]['write_merged_count'] = int(
                    (diskio_2[disk_name].write_merged_count - diskio_1[disk_name].write_merged_count) / stime)

                diskInfo['ALL']['read_count'] += diskInfo[disk_name]['read_count']
                diskInfo['ALL']['write_count'] += diskInfo[disk_name]['write_count']
                diskInfo['ALL']['read_bytes'] += diskInfo[disk_name]['read_bytes']
                diskInfo['ALL']['write_bytes'] += diskInfo[disk_name]['write_bytes']
                if diskInfo['ALL']['read_time'] < diskInfo[disk_name]['read_time']:
                    diskInfo['ALL']['read_time'] = diskInfo[disk_name]['read_time']
                if diskInfo['ALL']['write_time'] < diskInfo[disk_name]['write_time']:
                    diskInfo['ALL']['write_time'] = diskInfo[disk_name]['write_time']
                diskInfo['ALL']['read_merged_count'] += diskInfo[disk_name]['read_merged_count']
                diskInfo['ALL']['write_merged_count'] += diskInfo[disk_name]['write_merged_count']

            cache.set(iokey, {'info': diskio_2, 'time': mtime})
    except:
        return diskInfo
    return diskInfo


def GetNetWork():
    """
    取网卡数据
    """
    cache_timeout = 86400
    otime = cache.get("lybbn_otime")
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
        networkIo = networkIo_list[net_key][:4]
        up_key = "{}_up".format(net_key)
        down_key = "{}_down".format(net_key)
        otime_key = "lybbn_otime"

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
        networkInfo[net_key]['up'] = round(float(networkIo[0] - up) / 1024 / (ntime - otime), 2)
        networkInfo[net_key]['down'] = round(float(networkIo[1] - down) / 1024 / (ntime - otime), 2)
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
    取系统启动时间(天)
    """
    key = 'lybbn_sys_time'
    sys_time = cache.get(key)
    if sys_time: return sys_time
    uptime_seconds = time.mktime(time.localtime(time.time())) - psutil.boot_time()
    run_days = int(uptime_seconds / 86400)
    # run_hour = int((uptime_seconds % 86400) / 3600)
    # run_minute = int((uptime_seconds % 3600) / 60)
    # run_second = int(uptime_seconds % 60)
    sys_time = "{}天".format(run_days)
    cache.set(key, sys_time, 1800)
    return sys_time


def getCpuInfoDict():
    """
    取/proc/cpuinfo信息字典
    """
    cpuinfo = {}
    procinfo = {}
    nprocs = 0
    with open('/proc/cpuinfo') as f:
        for line in f:
            if not line.strip():
                cpuinfo['proc%s' % nprocs] = procinfo
                nprocs = nprocs + 1
                procinfo = {}
            else:
                if len(line.split(':')) == 2:
                    procinfo[line.split(':')[0].strip()] = line.split(':')[1].strip()
                else:
                    procinfo[line.split(':')[0].strip()] = ''
    return cpuinfo


def GetCpuInfo(interval=1):
    """
    取CPU信息
    """

    cpuCount = cache.get('lybbn_cpu_cpuCount')
    if not cpuCount:
        cpuCount = psutil.cpu_count()
        cache.set('lybbn_cpu_cpuCount', cpuCount, 86400)
    cpuNum = cache.get('lybbn_cpu_cpuNum')
    if not cpuNum:
        cpuNum = psutil.cpu_count(logical=False)
        cache.set('lybbn_cpu_cpuNum', cpuNum, 86400)

    cpuW = cache.get('lybbn_cpu_cpuW')
    if not cpuW:
        cpuW = int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
        cache.set('lybbn_cpu_cpuW', cpuW, 86400)

    used = psutil.cpu_percent(interval)

    used_all = psutil.cpu_percent(percpu=True)

    cpu_name = cache.get('lybbn_cpu_cpu_name')
    if not cpu_name:
        cpu_name = ""
        try:
            cpuinfo = getCpuInfoDict()
            cpu_name = cpuinfo['proc0']['model name'] + " * {}".format(cpuW)
        except:
            pass
        cache.set('lybbn_cpu_cpu_name', cpu_name, 86400)

    return used, cpuCount, used_all, cpu_name, cpuNum, cpuW


def GetDiskInfo():
    # 取磁盘分区信息
    key = 'lybbn_sys_disk'
    diskInfo = cache.get(key)
    if diskInfo: return diskInfo

    with os.popen("df -hT -P|grep '/'|grep -v tmpfs|grep -v 'snap/core'|grep -v udev", "r") as p:
        temp = p.read()

    with os.popen("df -i -P|grep '/'|grep -v tmpfs|grep -v 'snap/core'|grep -v udev", "r") as p:
        tempInodes = p.read()

    tempList = temp.split('\n')
    tempInodesList = tempInodes.split('\n')
    diskInfo = []
    n = 0
    cuts = ['/mnt/cdrom', '/boot', '/boot/efi', '/dev', '/dev/shm', '/run/lock', '/run', '/run/shm', '/run/user']
    for tmp in tempList:
        n += 1
        try:
            inodes = tempInodesList[n - 1].split()
            disk = re.findall(r"^(.+)\s+([\w\.]+)\s+([\w\.]+)\s+([\w\.]+)\s+([\w\.]+)\s+([\d%]{2,4})\s+(/.{0,100})$",
                              tmp.strip())
            if disk: disk = disk[0]
            if len(disk) < 6: continue
            if disk[2].find('M') != -1: continue
            if disk[2].find('K') != -1: continue
            if len(disk[6].split('/')) > 10: continue
            if disk[6] in cuts: continue
            if disk[6].find('docker') != -1: continue
            if disk[1].strip() in ['tmpfs']: continue
            arr = {}
            arr['filesystem'] = disk[0].strip()
            arr['type'] = disk[1].strip()
            arr['path'] = disk[6]
            tmp1 = [disk[2], disk[3], disk[4], disk[5].split('%')[0]]
            arr['size'] = tmp1
            arr['inodes'] = [inodes[1], inodes[2], inodes[3], inodes[4]]
            diskInfo.append(arr)
        except Exception as ex:
            continue
    cache.set(key, diskInfo, 1000)
    return diskInfo

def GetFileLastNumsLines(path, num=1000):
    """
    获取指定文件的指定尾行数内容(适合大文件读取)
    优化后的大文件读取方法
    """
    if not os.path.exists(path): 
        return ""
    
    filesize = os.path.getsize(path)
    if filesize == 0: 
        return ""
    
    num = str(num)
    result,err = RunCommand(f"tail -n {num} {path}",bufsize=-1)
    if err:
        raise Exception(err)
    return result
    

def GetFileLastNumsLines_2(path, num=1000):
    """
    获取指定文件的指定尾行数内容(大文件读取较慢)
    优化后的大文件读取方法
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

def isFirewalld():
    if os.path.exists('/usr/sbin/firewalld'): return True
    return False

def isUfW():
    if os.path.exists('/usr/sbin/ufw'): return True
    return False

def getFirewalldRuleList(param = {"dir":"in"}):
    """
    获取Firewalld防火墙规则列表(缺点：规则的顺序不好排)
    默认情况下，firewalld 允许所有出站流量
    """
    dir = param.get("dir","in")
    search = param.get("search",None)
    rstatus = str(param.get("status",""))
    data = []
    resout,reserr,code = RunCommand("firewall-cmd --zone=public --list-ports",returncode=True)
    if code == 0:
        ports = resout.strip().split(' ')
        for port in ports:
            p_p = port.split("/")
            protocol = p_p[1]
            direction = 'in'
            handle = 'accept'
            desc = ''
            port = p_p[0]
            if search:
                if str(port).find(search) == -1:#未找到
                    continue
            status=True
            data.append({
                'protocol': protocol,
                'port': p_p[0],
                'status':status,
                'status_info': {},
                'direction': direction,
                'handle': handle,
                'address':"all",
                'family':"all",
                'desc':desc
            })
        data.reverse()

    resout2,reserr2,code2 = RunCommand("firewall-cmd --zone=public --list-rich-rules",returncode=True)
    if code2 == 0:
        rules = resout2.strip().split('\n')
        for rule in rules:
            if not rule:
                continue
            rule_arr = rule.split(' ')
            handle = rule_arr[-1]
            family='all'
            address='all'
            l_port = "all"
            protocol="all"
            direction = 'in'
            desc=''
            matchfamily = re.search(r'family="(\w+)"', rule)
            if matchfamily:
                family = matchfamily.group(1)
            matchaddress = re.search(r'source address="(\w+)"', rule)
            if matchaddress:
                direction = 'in'
                address = matchaddress.group(1)
            matchport = re.search(r'port port="(\w+)"', rule)
            if matchport:
                l_port = matchport.group(1)
            matchprotocol = re.search(r'protocol="(\w+)"', rule)
            if matchprotocol:
                protocol = matchprotocol.group(1)
            status=True
            if search:
                if str(l_port).find(search) == -1:#未找到
                    continue
            data.append({
                'protocol': protocol,
                'port': l_port,
                'status':status,
                'status_info': {},
                'direction': direction,
                'handle': handle,
                'address':address,
                'family':family,
                'desc':desc
            })
    return data

def get_pid_by_port(port):
    """
    取端口的pid（其中一个）
    """
    for conn in psutil.net_connections(kind='inet'):
        # 检查是否为 LISTEN 状态，且本地端口为指定的端口
        if conn.status == 'LISTEN' and str(conn.laddr.port) == str(port):
            return conn.pid  # 返回匹配的进程 PID
    return None  # 如果没有找到匹配的连接

def GetFirewallRules(param = {"dir":"in"}):
    """
    获取防火墙规则列表
    默认情况下，firewalld 允许所有出站流量
    """
    dir = param.get("dir","in")
    search = param.get("search",None)
    rstatus = str(param.get("status",""))
    data = []
    if isFirewalld():
        rootp = ParseXMLFile("/etc/firewalld/zones/public.xml")
        if not rootp:return []
        for child in rootp:
            direction = 'in'
            handle = 'accept'
            desc = ''
            address='all'
            family='all'
            status=True
            if child.tag == "port":
                protocol = child.attrib['protocol']
                port = child.attrib['port']
                if search:
                    if str(port).find(search) == -1:#未找到
                        continue
                data.append({
                    'protocol': protocol,
                    'port': port,
                    'status':status,
                    'status_info': {},
                    'direction': direction,
                    'handle': handle,
                    'address':address,
                    'family':family,
                    'desc':desc
                })
            elif child.tag == "rule":
                family = child.attrib['family']
                protocol="all"
                port="all"
                for subcr in child:
                    if subcr.tag == 'port':
                        protocol = subcr.attrib['protocol']
                        port = subcr.attrib['port']
                        if search:
                            if str(port).find(search) == -1:#未找到
                                continue
                    elif subcr.tag == 'drop':
                        handle = 'drop'
                    elif subcr.tag == 'reject':
                        handle = 'reject'
                    elif subcr.tag == 'source':
                        if "address" in subcr.attrib.keys():
                            address = subcr.attrib['address']
                    
                data.append({
                    'protocol': protocol,
                    'port': port,
                    'status':status,
                    'status_info': {},
                    'direction': direction,
                    'handle': handle,
                    'address':address,
                    'family':family,
                    'desc':desc
                })
        
    elif isUfW():
        content = ReadFile("/etc/ufw/user.rules")
        start_index = content.find('### RULES ###')
        end_index = content.find('### END RULES ###')
        result = content[start_index + 15:end_index]
        #取#号描述
        srules = [rule for rule in result.split('\n') if rule != '' and '###' in rule]
        for rule in srules:
            rule = rule.split(' ')
            rule = [i for i in rule if i != '']
            status=True
            l_port = rule[5] if rule[5].find(':') == -1 else rule[5].replace(':', '-')
            if search:
                if str(l_port).find(search) == -1:#未找到
                    continue
            data.append({
                'protocol': rule[4] if rule[4] != 'any' else 'all',
                'port': l_port,
                'handle': 'accept' if rule[3] == 'allow' else 'drop',
                'address': rule[8] if rule[8] != '0.0.0.0/0' else 'all',
                'direction':rule[9],
                'family':'all',
                'status':status,
                'status_info': {},
                'desc':''
            })

        unique_set = set(tuple(sorted(item.items())) for item in data)
        data = [dict(item) for item in unique_set]
    else:
        return []
    newData = []
    for d in data:
        if d['port'] == "all" or d['port'].find('-') != -1 or d['port'].find(':') != -1:
            d['status'] = -1
        else:
            if is_service_running(int(d['port'])):
                d['status'] = True
                #pid,err = RunCommand(f"lsof -t -i :{d['port']}")
                pid,err = RunCommand(f"ss -ltunp | grep :{d['port']} | awk -F'pid=' '{{for(i=2;i<=NF;i++) print $i}}' | awk -F',' '{{print $1}}'")
                if pid:
                    pid_arr = sorted(list(filter(None, pid.split('\n'))))
                    one_pid = int(pid_arr[0])
                    try:
                        process = psutil.Process(one_pid)
                        process_name = process.name()
                        if process_name == "RuYi-Panel":
                            process_cmd = "/usr/local/ruyi/python/bin/python3 start.py"
                        else:
                            process_cmd = process.cmdline()
                            process_cmd = " ".join(process_cmd)
                        d['status_info']={
                            'pid': ', '.join(pid_arr),
                            'name': process_name,
                            'cmd': process_cmd
                        }
                    except:
                        pass
            else:
                d['status'] = False
        if rstatus:
            if rstatus == "false" and not d['status']:
                pass
            elif rstatus == "true" and (d['status'] or d['status']==-1):
                pass
            else:
                continue
        newData.append(d)
    return newData

def GetFirewallStatus():
    """
    取防火墙状态(当前网络连接的防火墙)
    """
    res = GetLinuxFirewallStatus()
    return res

def SetFirewallStatus(status = ""):
    """
    设置防火墙状态
    """
    if status not in ['stop', 'start']:
        return False, '类型错误'
    f_status = GetFirewallStatus()
    if f_status == -1:
        return False, "防火墙未安装"
    if status == "start":
        if f_status:
            return True, "启动防火墙成功"
        else:
            if isFirewalld():
                RunCommand('systemctl enable firewalld')
                RunCommandReturnCode('systemctl start firewalld',timeout=10)
            elif isUfW():
                RunCommand('echo y|ufw enable')
            time.sleep(1)
            if GetFirewallStatus():
                return True, "启动防火墙成功"
            return False, "启动防火墙失败"
    else:
        if not f_status:
            return True, "关闭防火墙成功"
        else:
            if isFirewalld():
                RunCommand('systemctl disable firewalld')
                RunCommandReturnCode('systemctl stop firewalld',timeout=10)
            elif isUfW():
                RunCommand('echo y|ufw disable')
            time.sleep(1)
            if GetFirewallStatus() == 0:
                return True, "关闭防火墙成功"
            return False, "关闭防火墙失败"

def GetSysPingStatus():
    """
    获取系统ping状态
    True 禁止ping 、False 允许ping
    """
    disping = False
    try:
        conf = ReadFile('/etc/sysctl.conf')
        if not conf:return False
        match = re.search(r'^\s*net\.ipv4\.icmp_echo_ignore_all\s*=\s*(\d+)', conf, re.MULTILINE)
        if match:
            value = match.group(1)
            if value == '0':  # 0 表示允许 ping，1 表示不允许
                return False
            elif value == '1':
                return True
            return False
    except:
        disping = False
    return disping

def GetFirewallInfo():
    """
    获取防火墙信息
    """
    name = ""
    if isFirewalld():
        name = "firewalld"
    elif isUfW():
        name = "ufw"
    ping = GetSysPingStatus()
    f_res = GetFirewallStatus()
    installed = True
    f_status = False
    if f_res == 1:
        f_status = True
    elif f_res == 0:
        f_status = False
    else:
        installed = False
    data = {
        'installed':installed,
        'status':f_status,
        'version':"",
        'name':name,
        'ping':ping
    }
    return data

def SetFirewallRuleAction(param={}):
    """
    设置防火墙规则策略
    """
    newhandle = param.get("newhandle","")
    if newhandle not in ["accept","drop"]:
        return False
    if DelFirewallRule(param=param,is_reload=False):
        param['handle'] = newhandle
        res = AddFirewallRule(param=param,is_reload=True)
        return res
    return False

def ReloadFirewall():
    """
    重载防火墙
    """
    if isFirewalld():
        RunCommand('firewall-cmd --reload &')
    elif isUfW():
        RunCommand('ufw reload &')
    return True

def SetFirewallPing(status = True):
    """
    设置防火墙Ping
    status: True 禁止ping、False 允许ping
    """
    
    conf = ReadFile("/etc/sysctl.conf")
    if not conf:return False,"设置失败"
    if status:
        status="1"
    else:
        status="0"
    if conf.find('net.ipv4.icmp_echo') != -1:
        conf = re.sub(r"net\.ipv4\.icmp_echo.*",'net.ipv4.icmp_echo_ignore_all='+status,conf)
    else:
        conf += "\nnet.ipv4.icmp_echo_ignore_all="+status
    WriteFile("/etc/sysctl.conf",conf)
    RunCommand("sysctl -p")
    return True,""

def DelFirewallRule(param={},is_reload=True):
    """
    删除防火墙规则
    """
    try:
        handle = param.get("handle","")
        if not handle:return False
        protocol = param.get("protocol","")
        if protocol not in ['tcp','udp',"all"]:return False
        localport = param.get("localport","")
        address = param.get("address","")
        if isFirewalld():
            if not address or address == "all":
                if handle == "accept":
                    command = f'firewall-cmd --permanent --zone=public --remove-port={localport}/{protocol}'
                else:
                    command = f'firewall-cmd --permanent --remove-rich-rule="rule family=ipv4 port protocol="{protocol}" port="{localport}" {handle}"'
            else:
                if protocol == "all" and localport =="all":
                    command = f'firewall-cmd --permanent --remove-rich-rule="rule family="ipv4" source address="{address}" {handle}"'
                else:
                    command = f'firewall-cmd --permanent --remove-rich-rule="rule family="ipv4" source address="{address}" port protocol="{protocol}" port="{localport}" {handle}"'
        elif isUfW():
            handle = "allow" if handle == "accept" else "deny"
            if not address or address == "all":
                command = f'ufw delete {handle} {localport}/{protocol}'
            else:
                command = f'ufw delete {handle} proto {protocol} from {address} to any port {localport}'
        else:
            return False
        RunCommand(command)
        if is_reload:ReloadFirewall()
        return True
    except Exception as e:
        return False

def is_valid_port_expression(port_expression):
    """
    校验端口规则是否正确
    80
    80,888
    80-999
    80:90
    """
    pattern = r'^(?:(\d{1,5})(?:-(\d{1,5}))?(?:,\s*(\d{1,5})(?:-(\d{1,5}))?)*|(\d{1,5}:\d{1,5})(?:,\s*(\d{1,5}:\d{1,5}))*|\s*)$'
    
    # 匹配并验证
    if re.match(pattern, port_expression):
        # 分割多个端口
        ports = [p.strip() for p in port_expression.split(',')]
        for port in ports:
            # 检查范围格式（88:99）
            if ':' in port:
                start, end = port.split(':')
                if not (start.isdigit() and end.isdigit()):
                    return False
                if not (0 <= int(start) <= 65535 and 0 <= int(end) <= 65535 and int(start) <= int(end)):
                    return False
            # 如果是范围（如 80-90）
            elif '-' in port:
                start, end = port.split('-')
                if not (start.isdigit() and end.isdigit()):
                    return False
                if not (0 <= int(start) <= 65535 and 0 <= int(end) <= 65535 and int(start) <= int(end)):
                    return False
            else:
                # 单个端口
                if not (port.isdigit() and 0 <= int(port) <= 65535):
                    return False
        return True
    return False

def AddFirewallRule(param={},is_reload=True):
    """
    添加防火墙规则
    """
    handle = param.get("handle","")
    if not handle:return False
    protocol = param.get("protocol","")
    if protocol not in ['tcp','udp','tcp/udp','all']:return False
    localport = param.get("localport","")
    address = param.get("address","")
    try:
        command_list = []
        ports = []
        protocols = []
        addresss = []
        if not is_valid_port_expression(localport):
            return False
        if localport.find(',') != -1:
            ports = localport.split(",")
        else:
            ports.append(localport)
        if "/" in protocol or protocol == 'all':
            protocols = ['tcp','udp']
        else:
            protocols.append(protocol)
        if address.find(',') != -1:
            addresss = address.split(",")
        else:
            addresss.append(address)
        if isFirewalld():
            if not address or address == "all":
                if handle == "accept":
                    for lp in ports:
                        if ":" in lp:lp = lp.replace(":", "-")
                        for po in protocols:
                            command = f'firewall-cmd --permanent --zone=public --add-port={lp}/{po}'
                            command_list.append(command)
                else:
                    for lp in ports:
                        if ":" in lp:lp = lp.replace(":", "-")
                        for po in protocols:
                            command = f'firewall-cmd --permanent --add-rich-rule="rule family=ipv4 port protocol="{po}" port="{lp}" drop"'
                            command_list.append(command)
            else:
                for lp in ports:
                    if ":" in lp:lp = lp.replace(":", "-")
                    for po in protocols:
                        for ad in addresss:
                            command = f'firewall-cmd --permanent --add-rich-rule="rule family="ipv4" source address="{ad}" port protocol="{po}" port="{lp}" {handle}"'
                            command_list.append(command)
        elif isUfW():
            handle = "allow" if handle == "accept" else "deny"
            if not address or address == "all":
                for lp in ports:
                    if "-" in lp:lp = lp.replace("-", ":")
                    for po in protocols:
                        command = f'ufw {handle} {lp}/{po}'
                        command_list.append(command)
            else:
                for lp in ports:
                    if "-" in lp:lp = lp.replace("-", ":")
                    for po in protocols:
                        for ad in addresss:
                            command = f'ufw {handle} proto {po} from {ad} to any port {lp}'
                            command_list.append(command)
        else:
            return False
        
        for m in command_list:
            RunCommand(m)
            time.sleep(0.1)
        if is_reload:ReloadFirewall()
        return True
    except:
        return False

def EditFirewallRule(param={}):
    """
    编辑防火墙规则
    """
    handle = param.get("handle","")
    if not handle:return False
    protocol = param.get("protocol","")
    if protocol not in ['tcp','udp','tcp/udp','all']:return False
    localport = param.get("localport","")
    address = param.get("address","")
    oldData = param.get("oldData","")
    if DelFirewallRule(param=oldData,is_reload=False):
        res = AddFirewallRule(param=param)
        return res
    return False

def EnableForward(is_cache=True):
    """
    开启端口转发功能
    is_cache 是否使用缓存功能
    """
    key = 'enableforward'
    if is_cache:
        forward = cache.get(key)
        if forward:
            return True
    sysconf = ReadFile("/etc/sysctl.conf")
    if not sysconf:return False
    if sysconf.find('net.ipv4.ip_forward') != -1:
        sysconf = re.sub(r"#?\s*net\.ipv4\.ip_forward\s*=\s*\d",'net.ipv4.ip_forward=1',sysconf)
    else:
        sysconf += "\nnet.ipv4.ip_forward=1"
    if isFirewalld():
        #开启IP伪装
        RunCommand('firewall-cmd --add-masquerade --permanent')
        ReloadFirewall()
    elif isUfW():
        uwfconf = ReadFile("/etc/default/ufw")
        if not uwfconf:return False
        if uwfconf.find('DEFAULT_FORWARD_POLICY') != -1:
            uwfconf = re.sub(r'DEFAULT_FORWARD_POLICY="DROP"','DEFAULT_FORWARD_POLICY="ACCEPT"',uwfconf)
        else:
            uwfconf += '\nDEFAULT_FORWARD_POLICY="ACCEPT"'
        WriteFile("/etc/default/ufw",uwfconf)
        ReloadFirewall()
    else:
        return False
    WriteFile("/etc/sysctl.conf",sysconf)
    RunCommand("sysctl -p")
    if is_cache:cache.set(key, 1, 86400*2)
    return True

def CloseForward():
    """
    关闭端口转发功能
    """
    sysconf = ReadFile("/etc/sysctl.conf")
    if not sysconf:return False
    if sysconf.find('net.ipv4.ip_forward') != -1:
        sysconf = re.sub(r"#?\s*net\.ipv4\.ip_forward\s*=\s*\d",'net.ipv4.ip_forward=0',sysconf)
    else:
        sysconf += "\nnet.ipv4.ip_forward=0"
    if isFirewalld():
        RunCommand('firewall-cmd --remove-masquerade --permanent')
        ReloadFirewall()
    elif isUfW():
        uwfconf = ReadFile("/etc/default/ufw")
        if not uwfconf:return False
        if uwfconf.find('DEFAULT_FORWARD_POLICY') != -1:
            uwfconf = re.sub(r'DEFAULT_FORWARD_POLICY="ACCEPT"','DEFAULT_FORWARD_POLICY="DROP"',uwfconf)
        else:
            uwfconf += '\nDEFAULT_FORWARD_POLICY="DROP"'
        WriteFile("/etc/default/ufw",uwfconf)
        ReloadFirewall()
    RunCommand("sysctl -p")
    return True

def GetPortProxyRules(param={}):
    """
    取所有端口转发列表
    """
    search = param.get("search",None)
    data = []
    EnableForward()
    if isFirewalld():
        rootp = ParseXMLFile("/etc/firewalld/zones/public.xml")
        if not rootp:return []
        for child in rootp:
            if child.tag == "forward-port":
                protocol = child.attrib['protocol']
                localport = child.attrib['port']
                remoteip = child.attrib.get('to-addr', '')
                remoteport = child.attrib['to-port']
                if search:
                    if str(localport).find(search) == -1:#未找到
                        continue
                data.append({
                    'protocol': protocol,
                    'localport': localport,
                    'remoteip':remoteip,
                    'remoteport':remoteport,
                })
    elif isUfW():
        ucont = ReadFile("/etc/ufw/before.rules")
        if not ucont:return []
        if ucont.find('*nat') == -1:return []
        ucont_list = ucont.split('\n')
        start_index = ucont_list.index(":POSTROUTING ACCEPT [0:0]")
        end_index = ucont_list.index("COMMIT")
        srules = ucont_list[start_index:end_index]
        for rule in srules:
            localport = ""
            remoteip = ""
            protocol = ""
            remoteport = ""
            if "-j REDIRECT --to-port" in rule:
                remoteip="127.0.0.1"
                reb1 = r"-p (\w+) --dport (\d+) -j REDIRECT --to-port (\d+)"
                match = re.search(reb1, rule)
                if match:
                    protocol = match.group(1)
                    localport = str(match.group(2))
                    remoteport = str(match.group(3))
            elif "-j DNAT --to-destination" in rule:
                reb1 = r"-p (\w+) --dport (\d+) -j DNAT --to-destination (\w+):(\d+)"
                match = re.search(reb1, rule)
                if match:
                    protocol = match.group(1)
                    localport = str(match.group(2))
                    remoteip = match.group(3)
                    remoteport = str(match.group(4))
            else:
                continue
            if search:
                if str(localport).find(search) == -1 and str(remoteport).find(search) == -1 and remoteip.find(search) == -1:#未找到
                    continue
            data.append({
                'protocol': protocol,
                'localport': localport,
                'remoteip':remoteip,
                'remoteport':remoteport,
            })

        unique_set = set(tuple(sorted(item.items())) for item in data)
        data = [dict(item) for item in unique_set]
    return data

def AddPortProxyRules(param={},is_reload=True):
    """
    添加端口转发
    """
    protocol = param.get("protocol","")
    localport = param.get("localport",0)
    remoteport = param.get("remoteport",0)
    remoteip = param.get("remoteip","")
    if protocol not in ["tcp","udp","tcp/udp","all"]:return False,"协议错误"
    protocols = []
    if protocol == "all" or "/" in protocol:
        protocols = ['tcp','udp']
    else:
        protocols.append(protocol)
    if not remoteip:remoteip="127.0.0.1"
    if not check_is_port(localport):
        return False,"源端口格式错误：1-65535"
    if not check_is_port(remoteport):
        return False,"目标端口格式错误：1-65535"
    if not check_is_ipv4(remoteip):
        return False,"ip格式错误，应为ipv4"
    if isFirewalld():
        for op in protocols:
            command = f'firewall-cmd --permanent --zone=public --add-forward-port=port={localport}:proto={op}:toaddr={remoteip}:toport={remoteport}'
            RunCommand(command)
    elif isUfW():
        ucont = ReadFile("/etc/ufw/before.rules")
        if not ucont:return False,"无法读取配置"
        if ucont.find('*nat') == -1:
            ucont = "*nat\n" + ":PREROUTING ACCEPT [0:0]\n" + ":POSTROUTING ACCEPT [0:0]\n" + "COMMIT\n" + ucont
        ucont_list = ucont.split('\n')
        POSTROUTING_index = ucont_list.index(":POSTROUTING ACCEPT [0:0]")
        rule_str = ""
        for op in protocols:
            if remoteip == "127.0.0.1":#本机端口转发
                rule_str = rule_str + f"-A PREROUTING -p {op} --dport {localport} -j REDIRECT --to-port {remoteport}\n"
            else:
                rule_str = rule_str + f"-A PREROUTING -p {op} --dport {localport} -j DNAT --to-destination {remoteip}:{remoteport}\n"
        if not remoteip == "127.0.0.1":
            rule_str = rule_str + f"-A POSTROUTING -d {remoteip} -j MASQUERADE\n"
        ucont_list.insert(POSTROUTING_index + 1, rule_str)
        newucont = '\n'.join(ucont_list)
        WriteFile("/etc/ufw/before.rules",newucont)
    else:
        return False,"不支持的防火墙"
    if is_reload:ReloadFirewall()
    return True,"ok"
    
def DelPortProxyRules(param={},is_reload=True):
    """
    删除端口转发规则
    """
    protocol = param.get("protocol","")
    localport = param.get("localport",0)
    remoteport = param.get("remoteport",0)
    remoteip = param.get("remoteip","")
    if protocol not in ["tcp","udp","tcp/udp","all"]:return False,"协议错误"
    protocols = []
    if protocol == "all" or "/" in protocol:
        protocols = ['tcp','udp']
    else:
        protocols.append(protocol)
    if not remoteip:remoteip="127.0.0.1"
    if not check_is_port(localport):
        return False,"源端口格式错误：1-65535"
    if not check_is_port(remoteport):
        return False,"目标端口格式错误：1-65535"
    if not check_is_ipv4(remoteip):
        return False,"ip格式错误，应为ipv4"
    if isFirewalld():
        for op in protocols:
            command = f'firewall-cmd --permanent --zone=public --remove-forward-port=port={localport}:proto={op}:toaddr={remoteip}:toport={remoteport}'
            RunCommand(command)
    elif isUfW():
        ucont = ReadFile("/etc/ufw/before.rules")
        if not ucont:return False,"无法读取配置"
        if remoteip == "127.0.0.1":
            rule_str = f"-A PREROUTING -p {op} --dport {localport} -j REDIRECT --to-port {remoteport}\n"
        else:
            rule_str = f"-A PREROUTING -p {op} --dport {localport} -j DNAT --to-destination {remoteip}:{remoteport}\n"
            rule_str = rule_str + f"-A POSTROUTING -d {remoteip} -j MASQUERADE\n"
        ucont = ucont.replace(rule_str, "")
        WriteFile("/etc/ufw/before.rules",ucont)
    else:
        return False,"不支持的防火墙"
    if is_reload:ReloadFirewall()
    return True,"ok"

def EditPortProxyRules(param={}):
    """
    编辑端口转发规则
    """
    protocol = param.get("protocol","")
    localport = param.get("localport",0)
    remoteport = param.get("remoteport",0)
    remoteip = param.get("remoteip","")
    if protocol not in ["tcp","udp","tcp/udp","all"]:return False,"协议错误"
    protocols = []
    if protocol == "all" or "/" in protocol:
        protocols = ['tcp','udp']
    else:
        protocols.append(protocol)
    if not remoteip:remoteip="127.0.0.1"
    if not check_is_port(localport):
        return False,"源端口格式错误：1-65535"
    if not check_is_port(remoteport):
        return False,"目标端口格式错误：1-65535"
    if not check_is_ipv4(remoteip):
        return False,"ip格式错误，应为ipv4"
    oldData = param.get("oldData","")
    if DelPortProxyRules(param=oldData,is_reload=False):
        res = AddPortProxyRules(param=param)
        return res
    return False

def RestartServer():
    """
    重启系统
    """
    try:
        os.system("sync && init 6 &")
    except:
        pass

def RestartRuyi():
    """
    重启如意
    """
    try:
        os.system("systemctl stop ruyi;systemctl start ruyi")
    except:
        pass

def GetUidName(file_path,uid=0):
    """
    通过系统uid获取对应名称
    """
    try:
        return pwd.getpwuid(uid).pw_name
    except Exception as e:
        return ""
    
def GetGroupidName(file_path,gid=0):
    """
    通过系统goup id（所属组id）获取对应名称
    """
    try:
        return grp.getgrgid(gid).gr_name
    except Exception as e:
        return ""
    
def ForceRemoveDir(directory):
    """
    强制删除目录
    """
    sys_dir = ['/root','/','/proc','/*','/root/*']
    if directory in sys_dir:
        raise ValueError("受保护的目录，无法删除!!!")
    if os.path.exists(directory):
        try:
            # 执行 rm -rf 命令
            subprocess.run(['rm', '-rf', directory], check=True)
        except subprocess.CalledProcessError as e:
            raise ValueError(f"强制删除目录错误: {e}")

def AddBinToPath(bin_dir):
    """
    添加命令到系统路径（环境变量）
    """
    if os.path.exists("/etc/profile"):
        # current_path = os.environ.get('PATH', '')
        # if bin_dir not in current_path:
        pcont = ReadFile("/etc/profile")
        if not f"export PATH={bin_dir}:$PATH" in pcont:
            RunCommand(f"echo 'export PATH={bin_dir}:$PATH' >> /etc/profile")
            RunCommand("source /etc/profile")
        return True
    else:
        raise Exception("无/etc/profile文件")