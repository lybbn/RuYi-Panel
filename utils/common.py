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
# 公用方法
# ------------------------------
import re
import os
import shutil
import socket
import ast
import random
import string
import time
import json
import datetime
import platform
import chardet
import subprocess
from rest_framework.request import Request
from django.http import QueryDict
from django.conf import settings
import psutil
import requests
import xml.etree.ElementTree as EleT

# 获取当前操作系统
current_os = platform.system().lower()

def ProgramRootPath():
    """
    @name 取项目真实根目录
    @author lybbn<2025-01-23>
    """
    return str(settings.BASE_DIR).replace("\\","/")

def compare_versions(version1, version2):
    """
    @name 比较两个版本号
    @author lybbn<2025-01-13>
    return 0 相同、1 version1大 、-1 version1 小
    """
    # 将版本号按"."分割成数字列表
    v1_parts = [int(part) for part in version1.split('.')]
    v2_parts = [int(part) for part in version2.split('.')]
    
    # 比较对应位置的数字
    length = max(len(v1_parts), len(v2_parts))
    
    # 如果版本号长度不一致，补充零
    v1_parts.extend([0] * (length - len(v1_parts)))
    v2_parts.extend([0] * (length - len(v2_parts)))
    
    # 比较各个部分
    for i in range(length):
        if v1_parts[i] < v2_parts[i]:
            return -1  # version1 更旧
        elif v1_parts[i] > v2_parts[i]:
            return 1   # version1 更新
    
    return 0  # 两个版本相同

def get_python_pip():
    """
    @name 取系统python、pip
    @author lybbn<2024-11-13>
    """
    if current_os == "windows":
        return {
            "python":"python",
            "pip":"pip"
        }
    else:
        return {
            "python":"rypython",
            "pip":"rypip"
        }

def check_is_port(port):
    """
    @name 是否有效端口
    @author lybbn<2024-01-13>
    """
    try:
        if isinstance(port, str):
            port = int(port)
        if port > 65535 or port < 1:
            return False
        return True
    except:
        return False

def check_is_ipv4(ip):
    """
    @name 是否ipv4
    @author lybbn<2024-01-13>
    """
    pattern = re.compile(
        r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    return bool(pattern.match(ip))

def is_valid_ipv4_segment(ip_segment):
    """
    @name 是否ipv4段
    @author lybbn<2024-01-13>
    """
    pattern = r'^(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
    if re.match(pattern, ip_segment):
        ip, subnet = ip_segment.split('/')
        octets = ip.split('.')
        if all(0 <= int(octet) <= 255 for octet in octets) and 0 <= int(subnet) <= 32:
            return True
    return False

def check_is_ipv6(ip):
    """
    @name 是否ipv6
    @author lybbn<2024-01-13>
    """
    try:
        socket.inet_pton(socket.AF_INET6, ip)
    except:
        return False
    return True

def check_is_domain(domain):
    """
    @name 是否域名
    @author lybbn<2024-03-16>
    """
    pattern = re.compile(
        r'^([\w\-\*]{1,150}\.){1,8}([\w\-]{1,30}|[\w\-]{1,30}\.[\w\-]{1,24})$'
    )
    return bool(pattern.match(domain))

def check_is_email(email):
    """
    @name 是否邮箱
    @author lybbn<2024-03-16>
    """
    pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    return bool(pattern.match(email))

def check_is_url(url_str):
    """
    @name 是否url地址
    @author lybbn<2024-03-16>
    """
    url_pattern = re.compile(r'^(https?|ftp):\/\/[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    return bool(url_pattern.match(url_str))

def check_contains_chinese(data):
    """
    @name 检查字符串是否包含中文
    """
    return bool(re.search(r'[\u4e00-\u9fa5]', data))

def check_url_site_canuse(url):
    """
    @name 检测目标url网站是否可用
    @author lybbn<2024-12-16>
    """
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except:
        return False

def map_to_list(mapobj):
    """
    @name map转换为list
    @author lybbn<2024-01-13>
    """
    try:
        if type(mapobj) != list and type(mapobj) != str: mapobj = list(mapobj)
        return mapobj
    except: 
        return []

def get_parameter_dic(request, *args, **kwargs):
    """
    @name 获取请求参数
    @author lybbn<2024-01-13>
    """
    if isinstance(request, Request) == False:
        return {}

    query_params = request.query_params
    if isinstance(query_params, QueryDict):
        query_params = query_params.dict()
    result_data = request.data
    if isinstance(result_data, QueryDict):
        result_data = result_data.dict()

    if query_params != {}:
        return query_params
    else:
        return result_data

def formatdatetime(datatimes):
    """
    格式化日期时间为指定格式
    :param datatimes: 数据库中存储的datetime日期时间,也可以是字符串形式(2021-09-23 11:22:03.1232000)
    :return: 格式化后的日期时间如：2021-09-23 11:22:03
    """
    if datatimes:
        try:
            if isinstance(datatimes, str):
                if "." in datatimes:
                    arrays = datatimes.split(".",maxsplit=1)
                    if arrays:
                        return arrays[0]
            return datatimes.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            return datatimes
    return datatimes

def formatTimestamp2Datetime(timestamp):
    """
    格式化unix时间戳为为指定时间日期格式
    :param timestamp: unix时间戳
    :return: 格式化后的日期时间如：2021-09-23 11:22:03
    """
    if timestamp:
        try:
            dt = datetime.datetime.fromtimestamp(float(timestamp))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            return timestamp
    return timestamp

def getTimestamp13():
    """
    @name 获取当前服务器13位时间戳
    @author lybbn<2024-01-13>
    """
    timestamp = int(time.time())
    return timestamp * 1000

def get_online_public_ip():
    """
    @name 取公网IP
    @author lybbn<2024-01-13>
    """
    try:
        response = requests.get('https://api.ipify.org/?format=json')
        data = response.json()
        public_ip = data['ip']
        return public_ip
    except Exception as e:
        try:
            response = requests.get('https://httpbin.org/ip')
            response.raise_for_status()  # 检查请求是否成功
            ip = response.json()['origin']
            return ip
        except:
            return None

#读取文件内容
def ReadFile(filename,mode='r'):
    """
    filename:文件（包含路径）
    返回：若文件不存在则返回None
    """
    try:
        with open(filename, mode) as file:
            content = file.read()
            # 处理文件内容
    except:
        try:
            with open(filename, mode, encoding="utf-8", errors='ignore') as file:
                content = file.read()
        except:
            try:
                with open(filename, mode, encoding="GBK", errors='ignore') as file:
                    content = file.read()
            except:
                return None
    return content

#写入文件内容，不存在则创建
def WriteFile(file_path,content,mode="w",write=True,encoding="utf-8"):
    """
    @name 写入文件内容，不存在则创建
    @author lybbn<2024-01-13>
    file_path:文件（包含路径）
    content:写入的内容
    mode: w 覆盖写入（默认）、a 追加写入
    write:是否写入
    """
    if write:
        # 获取文件所在的目录路径
        directory = os.path.dirname(file_path)

        # 检查目录是否存在，如果不存在则创建
        if not os.path.exists(directory):
            os.makedirs(directory)
        if 'b' in mode:encoding = None
        # 写入内容到文件
        with open(file_path, mode,encoding=encoding) as f:
            if isinstance(content, int):
                content = str(content)
            f.write(content)

def DeleteFile(path,empty_tips=True):
    """
    @name 删除文件
    @author lybbn<2024-02-22>
    """
    if empty_tips:
        if not os.path.exists(path) and not os.path.islink(path):
            raise ValueError("要删除的文件不存在")
        os.remove(path)
    if os.path.exists(path):
        os.remove(path)

def DeleteDir(path):
    """
    @name 删除目录
    @author lybbn<2024-02-22>
    """
    if not os.path.exists(path):
        return
    if os.path.islink(path):
        os.remove(path)
    else:
        shutil.rmtree(path)

def GetSecurityPath():
    """
    @name 获取面板安全路径
    @author lybbn<2024-02-07>
    """
    try:
        f = open(settings.RUYI_SECURITY_PATH_FILE)
        spath = f.read()
        f.close()
        if not spath: spath = '/ry'
    except:
        spath = '/ry'
    return spath

def GetLetsencryptPath():
    """
    @name 获取Letsencrypt证书配置文件路径
    @author lybbn<2024-02-07>
    """
    return os.path.join(settings.BASE_DIR,"data","config","letsencrypt.json")

def GetLetsencryptLogPath():
    """
    @name 获取申请Letsencrypt证书产生日志的路径
    @author lybbn<2024-02-07>
    """
    return os.path.join(settings.BASE_DIR,"logs","letsencrypt.log")

def GetLetsencryptRootPath():
    """
    @name 获取申请Letsencrypt证书保存根路径
    @author lybbn<2024-02-07>
    """
    return os.path.join(settings.RUYI_VHOST_PATH,"cert","letsencrypt")

def GetSoftConfigPath():
    """
    @name 获取软件商店配置JSON路径
    @author lybbn<2024-02-07>
    """
    return os.path.join(settings.BASE_DIR,"config","softlist.json")

def GetSoftConfig():
    """
    @name 读取软件商店配置JSON
    @author lybbn<2024-02-07>
    """
    config_path = GetSoftConfigPath()
    if not os.path.exists(config_path):
        return {}
    content = ReadFile(config_path)
    if not content: 
        return {}
    config_json = json.loads(content)
    return config_json

def GetSoftList(all=False):
    """
    @name 读取软件商店列表
    @author lybbn<2024-02-07>
    """
    config_json = GetSoftConfig()
    if not config_json:
        return {}
    if current_os == 'windows':
        softlist = config_json['windows']['soft']
    else:
        softlist = config_json['linux']['soft']
    if not all:
        data=[]
        for sftlsit in softlist:
            if sftlsit.get("show",None):
                data.append(sftlsit)
        softlist=data
    return softlist

def GetConfig():
    """
    @name 读取配置文件
    @author lybbn<2024-02-07>
    file_path:文件（包含路径）
    """
    config_path = os.path.join(settings.BASE_DIR,"config","config.json")
    if not os.path.exists(config_path):
        return {}
    content = ReadFile(config_path)
    if not content: 
        return {}
    return json.loads(content)

def GetWebRootPath():
    """
    @name 读取如意网站根目录
    @author lybbn<2024-02-07>
    """
    
    def getDefaultPath():
        config = GetConfig()
        if current_os == 'windows':
            www_path = config['windows']['wwwroot_path']
        else:
            www_path = config['linux']['wwwroot_path']
        return www_path
    
    try:
        f = open(os.path.join(settings.BASE_DIR,"data",'wwwroot.ry'))
        www_path = f.read()
        f.close()
        if not www_path: www_path = getDefaultPath()
    except:
        www_path = getDefaultPath()
    return www_path
    
def GetRootPath():
    """
    @name 读取如意根目录
    @author lybbn<2024-02-07>
    """
    config = GetConfig()
    if current_os == 'windows':
        root_path = config['windows']['root_path']
    else:
        root_path = config['linux']['root_path']
    return root_path

def GetInstallPath():
    """
    @name 读取如意程序或三方程序的安装目录
    @author lybbn<2024-02-07>
    """
    config = GetConfig()
    if current_os == 'windows':
        install_path = config['windows']['install_path']
    else:
        install_path = config['linux']['install_path']
    return install_path

def GetDataPath():
    """
    @name 读取如意程序数据目录
    @author lybbn<2025-03-01>
    """
    config = GetConfig()
    if current_os == 'windows':
        data_path = config['windows']['data_path']
    else:
        data_path = config['linux']['data_path']
    return data_path

def GetLogsPath():
    """
    @name 读取日志文件路径
    @author lybbn<2024-02-07>
    """
    config = GetConfig()
    if current_os == 'windows':
        logs_path = config['windows']['logs_path']
    else:
        logs_path = config['linux']['logs_path']
    return logs_path

def GetBackupPath():
    """
    @name 读取备份目录路径
    @author lybbn<2024-02-07>
    """
    def getDefaultPath():
        config = GetConfig()
        if current_os == 'windows':
            backup_path = config['windows']['backup_path']
        else:
            backup_path = config['linux']['backup_path']
        return backup_path
    
    try:
        f = open(os.path.join(settings.BASE_DIR,"data",'backup.ry'))
        backup_path = f.read()
        f.close()
        if not backup_path: backup_path = getDefaultPath()
    except:
        backup_path = getDefaultPath()
    return backup_path

def GetTmpPath():
    """
    @name 读取临时目录路径
    @author lybbn<2024-02-07>
    """
    config = GetConfig()
    if current_os == 'windows':
        tmp_path = config['windows']['tmp_path']
    else:
        tmp_path = config['linux']['tmp_path']
    return tmp_path

def GetPanelPath():
    """
    @name 读取面板目录路径
    @author lybbn<2024-02-07>
    """
    config = GetConfig()
    if current_os == 'windows':
        tmp_path = config['windows']['panel_path']
    else:
        tmp_path = config['linux']['panel_path']
    return tmp_path

def GetPanelPort():
    """
    @name 获取面板端口
    @author lybbn<2024-02-07>
    """
    try:
        f = open(settings.RUYI_PORT_FILE)
        port = int(f.read())
        f.close()
        if not port: port = 6789
    except:
        port = 6789
    return port

def GetPanelBindAddress():
    """
    @name 获取面板监听地址
    @author lybbn<2024-02-07>
    """
    try:
        f = open(os.path.join(settings.BASE_DIR,"data",'bindaddress.ry'))
        host = f.read()
        f.close()
        if not host: host = '0.0.0.0'
    except:
        host = '0.0.0.0'
    return host

def isSSLEnable():
    """
    @name 面板是否开启了SSL
    @author lybbn<2024-02-07>
    """
    return os.path.exists(settings.RUYI_SSL_ENABLE_FILE)

#生成随机得指定位数字母+数字字符串
def GetRandomSet(bits):
    """
    bits:数字是几就生成几位
    """
    num_set = [chr(i) for i in range(48,58)]
    char_set = [chr(i) for i in range(97,123)]
    total_set = num_set + char_set
    value_set = "".join(random.sample(total_set, bits))
    return value_set

def generate_random_string(length):
    """
    @name 随机生成指定长度的字符串，包含字母+数字+自定义特殊字符
    @author lybbn<2024-01-13>
    filename:文件（包含路径）
    content:写入的内容
    """
    special_chars = '!@#$%^*=+-'
    all_chars = string.ascii_letters + string.digits + special_chars
    random_string = ''.join(random.choice(all_chars) for _ in range(length))
    return random_string

#把字符串转换成数组对象等
def ast_convert(string):
    if string:
        try:
            return ast.literal_eval(string)
        except Exception as e:
            try:
                if isinstance(string, str):
                    return json.loads(string)
                return string
            except:
                return string
    return None

def RunCommand(cmdstr,cwd=None,shell=True,bufsize=4096,returncode=False,timeout=None,env=None):
    """
    @name 执行命令(输出结果)
    @author lybbn<2024-02-18>
    @param cmdstr 命令 [必传]
    @param cwd 执行命令的工作目录
    @param returncode 是否需要返回returncode 0 成功、 1 失败
    @timeout 命令超时时间 单位s秒
    """
    if platform.system() == 'Windows':
        commands_list = cmdstr.split("\n")
        commands = '&'.join(commands_list)
    else:
        commands_list = cmdstr.split("\n")
        commands = '; '.join(commands_list)
    try:
        process = subprocess.Popen(commands,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=shell,bufsize=bufsize,env=env)

        # 获取输出结果
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()  # 如果超时，则杀死子进程
        stdout, stderr = process.communicate()

    # 检测输出编码
    stdout_encoding = chardet.detect(stdout)['encoding'] or 'utf-8'
    stderr_encoding = chardet.detect(stderr)['encoding'] or 'utf-8'
    try:
        out = stdout.decode(stdout_encoding)
        err = stderr.decode(stderr_encoding)
    except:
        try:
            out = stdout.decode('utf-8')
            err = stderr.decode('utf-8')
        except:
            try:
                out = stdout.decode('gb2312')
                err = stderr.decode('gb2312')
            except:
                try:
                    out = stdout.decode('utf-16')
                    err = stderr.decode('utf-16')
                except:
                    try:
                        out = stdout.decode('latin-1')
                        err = stderr.decode('latin-1')
                    except:
                        out = stdout.decode('gb2312', 'ignore')
                        err = stderr.decode('gb2312', 'ignore')
    
    if returncode:
        return out, err,process.returncode
    return out, err 

def RunCommandReturnCode(cmdstr, cwd=None,env_path=None, shell=True,timeout=None):
    """
    @name 执行命令(输出状态码)
    @author lybbn<2024-02-18>
    @param cwd 执行命令的工作目录
    @param env_path 环境变量(需要加入的环境变量路径)
    @param cmdstr 命令 [必传]
    """
    try:
        env = os.environ.copy()
        if env_path:
            if current_os == 'windows':
                env['PATH'] = env_path+";" + env['PATH']
            else:
                env['PATH'] = env_path+":" + env['PATH']
        sub = subprocess.Popen(cmdstr, cwd=cwd,stdin=subprocess.PIPE,env=env,shell=shell, bufsize=4096)
        start_time = time.time()
        while True:
            retcode = sub.poll()
            if retcode is not None:
                break
            # 检查是否超时
            if timeout:
                if time.time() - start_time > timeout:
                    sub.terminate()  # 尝试正常结束子进程
                    try:
                        sub.wait(timeout=5)  # 等待子进程终止
                    except subprocess.TimeoutExpired:
                        sub.kill()  # 如果在超时内未能结束，强制结束
                    return -1  # 返回一个错误代码，表示超时
            time.sleep(0.1)
        return sub.returncode
    except Exception as e:
        return None

def md5(strings):
    """
    @name md5加密
    @author lybbn<2024-02-18>
    @param strings 要md5的字符串
    """
    if type(strings) != bytes:
        strings = strings.encode()
    import hashlib
    m = hashlib.md5()
    m.update(strings)
    return m.hexdigest()

def utc_to_time(utcstr):
    """
    UTC时间转时间戳
    """
    utcstr = utcstr.split('.')[0]
    utc_date = datetime.datetime.strptime(utcstr, "%Y-%m-%dT%H:%M:%SZ")
    return int(time.mktime(utc_date.timetuple())) + (3600 * 8)# 北京时间

def is_service_running(port=80):
    """
    @name 检测本机指定端口是否开启
    @author lybbn<2024-04-22>
    """
    try:
        # 尝试连接到指定的端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)  # 设置超时时间
            s.connect(('localhost', port))
            return True
    except (socket.timeout, socket.error):
        return False
    
def GetPidCpuPercent(pid, pid_cpu_percent):
    """
    @name 获取指定pid进程cpu使用率
    @author lybbn<2024-08-18>
    @
    """
    try:
        s = psutil.Process(pid)
        if s.name() not in pid_cpu_percent.keys():
            pid_cpu_percent[s.name()] = float(s.cpu_percent(interval=0.01))
        pid_cpu_percent[s.name()] += float(s.cpu_percent(interval=0.01))
    except:
        pass
    
def GetPidCpuPercent(pid, pid_cpu_percent):
    """
    @name 获取指定pid进程cpu使用率
    @author lybbn<2024-08-18>
    @params pid 进程pid
    """
    try:
        s = psutil.Process(pid)
        if s.name() not in pid_cpu_percent.keys():
            pid_cpu_percent[s.name()] = float(s.cpu_percent(interval=0.01))
        pid_cpu_percent[s.name()] += float(s.cpu_percent(interval=0.01))
    except:
        pass
    
def GetProcessNameInfo(process_name,process_info,is_windows=True):
    """
    @name 获取指定进程名的信息
    @author lybbn<2024-08-18>
    @params process_name进程名
    @params process_info回调变量 
    """
    try:
        if is_windows:
            res,err = RunCommand('wmic process where name="%s" get ProcessId,Name,ExecutablePath,WorkingSetSize'%process_name)
            output = res.strip().splitlines()
            # 检查是否有足够的数据
            if len(output) <= 1:
                return []
            headers = output[0].split()
            processes = []
            # 处理每一行数据
            for line in output[1:]:
                values = line.split()
                if len(values) == len(headers):
                    process_info = dict(zip(headers, values))
                    processes.append(process_info)
            process_info[process_name] = processes
            return processes
        else:
            processes = []
            for pid in os.listdir('/proc'):
                if pid.isdigit():  # 只处理数字命名的目录，即进程 ID
                    try:
                        # 获取进程名称
                        with open(f'/proc/{pid}/comm', 'r') as f:
                            name = f.read().strip()
                        if name != process_name:
                            continue
                        # 获取可执行路径
                        exe_path = os.readlink(f'/proc/{pid}/exe')
                        # 获取工作集大小 (VmRSS)
                        working_set_size = 'N/A'
                        with open(f'/proc/{pid}/status', 'r') as f:
                            for line in f:
                                if line.startswith('VmRSS:'):
                                    working_set_size = line.split()[1]
                                    break

                        processes.append({
                            'ProcessId': pid,
                            'Name': name,
                            'ExecutablePath': exe_path,
                            'WorkingSetSize': working_set_size
                        })
                    except FileNotFoundError:
                        continue
            process_info[process_name] = processes
            return processes
    except:
        return []
    
def GetLocalSSHPort():
    """
    @name 获取本机SSH服务的端口
    @author lybbn<2024-08-18>
    @return int 类型
    """
    filep = '/etc/ssh/sshd_config'
    conf = ReadFile(filep)
    if not conf:return 22
    allport = re.findall(r".*Port\s+[0-9]+",conf)
    port = 22
    for p in allport:
        rep = r"^\s*Port\s+([0-9]+)\s*"
        tc = re.findall(rep,p)
        if tc:port = int(tc[0])
    return port

def GetLocalSSHUser():
    """
    @name 获取本机SSH服务需要使用的端口
    @author lybbn<2024-08-18>
    @return 用户名
    """
    local_user = 'root'
    conf = ReadFile('/etc/ssh/sshd_config')
    if not conf: return local_user

    if conf.find('PermitRootLogin yes') != -1: return local_user

    userlist  = GetLinuxLocalUserlist()
    login_user = ''
    for u in userlist:
        if u['username'] == 'root': continue
        if u['loginshell'] == '/bin/bash':
            login_user = u['username']
            break

    if not login_user:
        return local_user

    return login_user

def GetLinuxLocalUserlist():
    """
    @name 获取Linux本地用户列表
    @author lybbn<2024-08-18>
    @return list
    """
    pdata = ReadFile('/etc/passwd')
    userlist = []
    for i in pdata.split("\n"):
        tmplist = i.split(':')
        if len(tmplist) < 7: continue
        info = {}
        info['username']=tmplist[0]
        info['password']=tmplist[1]
        info['uid']=tmplist[2]
        info['gid']=tmplist[3]
        info['msg']=tmplist[4]
        info['home']=tmplist[5]
        info['loginshell'] = tmplist[6]
        userlist.append(info)
    return userlist

def SetSSHServiceStatus(action="reload"):
    """
    @name 设置SSH服务状态 reload、restart、start、stop
    @author lybbn<2024-08-18>
    """
    command = f"systemctl {action} sshd.service"
    if os.path.exists('/bin/systemctl'):
        command = f"systemctl {action} sshd.service"
    elif os.path.exists('/usr/sbin/service'):
        command = f"service sshd {action}"
    elif os.path.exists('/etc/init.d/sshd'):
        command = f"/etc/init.d/sshd {action}"

    RunCommandReturnCode(command)
    
def isSSHRunning():
    """
    @name 获取SSH服务是否运行
    @author lybbn<2024-08-18>
    """
    sshport = GetLocalSSHPort()
    ps_command = f"ss -tunlp | grep ssh |grep :{sshport}| grep -v grep"
    result,err = RunCommand(ps_command)
    if result:
        return True
    return False
    
def SetSSHSupportRootPass():
    """
    @name 设置SSH服务支持root密码登录和密钥登录
    @author lybbn<2024-08-18>
    @return bool
    """
    conf = ReadFile('/etc/ssh/sshd_config')
    if not conf: return False
    root_pass_re = r'^\s*#?\s*PermitRootLogin\s*([\w\-]+)'
    tmp1 = re.search(root_pass_re, conf,re.M)
    permitstr = 'PermitRootLogin yes'
    if not tmp1:
        newconf = conf + f'\n{permitstr}'
    else:
        newconf = conf.replace(tmp1.group(),permitstr)
    pass_str = r'\n#?PasswordAuthentication\s\w+'
    if len(re.findall(pass_str, conf)) == 0:
        newconf = newconf + '\nPasswordAuthentication yes'
    else:
        newconf = re.sub(pass_str, '\nPasswordAuthentication yes', newconf)
    WriteFile('/etc/ssh/sshd_config', newconf)
    SetSSHServiceStatus()
    return True

def SetSSHSupportKey():
    """
    @name 设置SSH服务支持密钥登录
    @author lybbn<2024-08-18>
    @return bool
    """
    conf = ReadFile('/etc/ssh/sshd_config')
    if not conf: return False
    pub_key = r'\n#?PubkeyAuthentication\s\w+'
    if len(re.findall(pub_key, conf)) == 0:
        newconf = conf + '\nPubkeyAuthentication yes'
    else:
        newconf = re.sub(pub_key,'\nPubkeyAuthentication yes',conf)
    #新版ssh已弃用RSAAuthentication
    # rsa_str = r'\n#?RSAAuthentication\s\w+'
    # if len(re.findall(rsa_str, newconf)) == 0:
    #     newconf = newconf + '\nRSAAuthentication yes'
    # else:
    #     newconf = re.sub(rsa_str,'\nRSAAuthentication yes',newconf)
    WriteFile('/etc/ssh/sshd_config', newconf)
    SetSSHServiceStatus()
    return True

def GetLinuxFirewallStatus():
    """
    @name 获取Linux防火墙状态(不支持iptables)
    @author lybbn<2024-08-18>
    @return 1 已启动、0 未启动 、-1 未安装
    """
    firewalls = {
        '/usr/sbin/firewalld': 'systemctl is-active firewalld',
        '/usr/sbin/ufw': "ufw status verbose|grep -E '(Status: active|激活)'",
    }
    for firewall, command in firewalls.items():
        if not os.path.exists(firewall): continue
        result,err,code = RunCommand(command, returncode=True)
        if code == 0 or not err:
            result =result.strip() if result else ""
            if 'firewalld' in firewall and result == "active":
                return 1
            elif 'ufw' in firewall and result:
                return 1
            return 0
        else:
            return -1
    return -1

def ParseXMLFile(filepath):
    """
    @name 解析XML文件
    @author lybbn<2024-08-18>
    """
    try:
        tree = EleT.parse(filepath)
        root = tree.getroot()
        return root
    except:
        return None
    
def format_size(byte_size):
    """
    @name 转换单位
    @author lybbn<2024-08-18>
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    
    # 如果输入的字节数小于 0，则返回 None
    if byte_size < 0:
        return None
    
    # 如果字节数小于 1024，直接返回原始字节数
    if byte_size < 1024:
        return f"{byte_size} B"
    
    # 根据字节数逐级转换为更大的单位
    i = 0
    while byte_size >= 1024 and i < len(units) - 1:
        byte_size /= 1024
        i += 1
    
    # 返回转换后的大小，保留 2 位小数
    return f"{byte_size:.2f} {units[i]}"

def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
        return True
    except:
        return False