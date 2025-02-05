#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-09-21
# +-------------------------------------------------------------------

# ------------------------------
# 项目初始化
# ------------------------------
import os
import logging
from ruyi import settings
import socket
import random
from django.core.management.base import BaseCommand
from django.core.management import call_command
from apps.system.initialize import main
from utils.common import generate_random_string,WriteFile,ReadFile,get_online_public_ip,GetRandomSet,is_service_running,GetPanelPort,GetSecurityPath
from utils.sslPem import generateRuyiSSLPem

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-05-03
    @EditData:2024-05-03
    @Email:1042594286@qq.com
    @name:项目初始化命令: python manage.py init
    @使用场景：项目初始安装时（有只初始化一次限制）
    """

    def add_arguments(self, parser):
        parser.add_argument('init_name', nargs='*', type=str, )
        parser.add_argument('-y', nargs='*')
        parser.add_argument('-Y', nargs='*')
        parser.add_argument('-n', nargs='*')
        parser.add_argument('-N', nargs='*')
        parser.add_argument('-u', nargs='*')#管理员账号
        parser.add_argument('-p', nargs='*')#管理员密码

    def handle(self, *args, **options):
        is_inited = ReadFile(settings.RUYI_ISINITED_FILE)
        if is_inited:
            print("已执行过一次如意面板初始化操作，再次执行会导致数据异常！！！")
            return 
        is_delete = True
        username = None
        password = None
        if isinstance(options.get('y'), list) or isinstance(options.get('Y'), list):
            is_delete = True
        if isinstance(options.get('n'), list) or isinstance(options.get('N'), list):
            is_delete = False
        if isinstance(options.get('u'), list):
            username = options.get('u')[0]
        if isinstance(options.get('p'), list):
            password = options.get('p')[0]
        print(f"正在初始化【数据库】")
        databases = settings.DATABASES
        for key in databases:
            database_path = databases[key]['NAME']
            if not os.path.exists(database_path):
                print("正在创建数据库【%s】"%database_path)
                if not os.path.exists(os.path.dirname(database_path)):
                    os.makedirs(os.path.dirname(database_path))# 如果数据库文件所在目录不存在，则创建目录
                open(database_path, 'w').close()# 如果数据库文件不存在，则创建数据库文件
        call_command('makemigrations')
        call_command('migrate')
        call_command('migrate', database='logs')
        call_command('migrate', database='tasks')
        call_command('migrate', database='shop')
        call_command('migrate', database='backup')
        print("正在初始化数据...")
        try:
            if not username:username = "ry"+GetRandomSet(6)
            if not password:password = GetRandomSet(12)
            main(delete=is_delete,username=username,password=password)
        except ModuleNotFoundError:
            pass
        print("初始化数据完成！")
        print(f"正在初始化【缓存】")
        caches = settings.CACHES
        for key in caches:
            if "FileBasedCache" in caches[key]['BACKEND']:
                cache_path = caches[key]['LOCATION']
                if not os.path.exists(cache_path):
                    os.makedirs(cache_path)
        print("初始化缓存完成！")
        print("正在初始化如意配置...")
        initSettingsSecretKey()
        initRuyiPanelPort()
        initRuyiPanelSecrityPath()
        InitSys()
        print("初始化如意配置完成！")
        border_length = 50
        border = '+' * border_length
        p_port = GetPanelPort()
        p_spath = GetSecurityPath()
        hostname = socket.gethostname()
        ip_addresses = socket.gethostbyname_ex(hostname)[2]
        hosts = [ip for ip in ip_addresses if not ip.startswith("127.")]
        internal_ip = "127.0.0.1" if not hosts else hosts[0]
        external_url = f"http://{ReadFile(settings.RUYI_PUBLICIP_FILE)}:{p_port}{p_spath}"
        internal_url = f"http://{internal_ip}:{p_port}{p_spath}"
        print(border)
        print(f"外网面板地址: {external_url}")
        print(f"内网面板地址: {internal_url}")
        print(f"username: {username}")
        print(f"password: {password}")
        print(border)

def initSettingsSecretKey():
    """
    @name 初始化如意配置SECRET_KEY
    @author lybbn<2024-01-13>
    """
    secret_key = "ruyi-insecure-%s"%generate_random_string(30)
    RUYI_SECRET_KEY_FILE = settings.RUYI_SECRET_KEY_FILE
    WriteFile(file_path=RUYI_SECRET_KEY_FILE,content=secret_key)
    print("已初始化settings中SECRET_KEY操作，保障面板安全性")

def initRuyiPanelSecrityPath():
    """
    @name 初始化如意配置安全入口
    @author lybbn<2024-02-13>
    """
    sec_file_path = "/"+GetRandomSet(6)
    WriteFile(settings.RUYI_SECURITY_PATH_FILE,sec_file_path)
    print("已初始化如意面板安全入口为：%s，保障面板安全性"%sec_file_path)

def initRuyiPanelPort():
    """
    @name 初始化如意配置访问端口
    @author lybbn<2024-02-13>
    """
    port = 6789
    is_ok = False
    for i in range(5):
        zhanyong = is_service_running(port)
        if not zhanyong:
            is_ok = True
            break
        else:
            port = random.randint(30000, 38999)
    if not is_ok:
        port = 6789
    WriteFile(settings.RUYI_PORT_FILE,port)
    print("已初始化如意面板访问端口：%s"%str(port))
 
def InitSys():
    """
    @name 如意系统耗时初始化
    @author lybbn<2024-01-13>
    """
    hosts = []
    host = ReadFile(settings.RUYI_PUBLICIP_FILE)
    if not host:
        print("正在获取服务器公网IP地址...")
        host = get_online_public_ip()
        if host:
            print("获取服务器公网IP地址：%s"%host)
            WriteFile(settings.RUYI_PUBLICIP_FILE,host)
        else:
            print("获取服务器公网IP失败!!!")
    if host:
        hostname = socket.gethostname()
        ip_addresses = socket.gethostbyname_ex(hostname)[2]
        hosts = [ip for ip in ip_addresses if not ip.startswith("127.")]
        hosts.append('127.0.0.1')
        hosts.insert(0, host)
    print("正在生成如意面板SSL证书信息...")
    ruyi_root_password,ruyi_root,private_key,certificate = generateRuyiSSLPem(hosts=hosts)
    if certificate:
        print("SSL证书信息生成成功")
    else:
        print("SSL证书信息生成失败!!!")
    WriteFile(settings.RUYI_ISINITED_FILE,"ok")