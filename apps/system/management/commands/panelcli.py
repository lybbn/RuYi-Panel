import re,socket
import random
from django.core.management.base import BaseCommand
from apps.system.models import Users
from utils.common import generate_random_string,WriteFile,GetRandomSet,is_service_running,ReadFile,GetPanelPort,GetSecurityPath
from ruyi import settings

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-05-03
    @EditData:2024-05-03
    @Email:1042594286@qq.com
    @name:如意面板综合命令行综合工具箱: python manage.py panelcli
    """
    
    def add_arguments(self, parser):
        parser.add_argument(
            'action', 
            type=str, 
            choices=['set_safepath','set_secretkey','set_port','set_username','get_version','get_panelinfo'], 
            help='选择要执行的操作：set_safepath、set_secretkey、set_port、set_username、get_version、get_panelinfo'
        )
        
        parser.add_argument('-d','--data',help='参数')

    def handle(self, *args, **options):
        action = options.get('action',"")
        if action == 'get_version':
            self.getVersion()
        elif action == 'set_safepath':
            self.setRuyiPanelSecrityPath(options)
        elif action == 'set_secretkey':
            self.setSecretKey(options)
        elif action == 'set_port':
            self.setRuyiPanelPort(options)
        elif action == 'set_username':
            self.setPanelUsername(options)
        elif action == 'get_panelinfo':
            self.getSysInfo()
        else:
            self.stdout.write(self.style.ERROR('无效的命令'))
    
    def getSysInfo(self):
        """
        @name 获取如意面板信息
        @author lybbn<2024-01-13>
        """
        border_length = 50
        border = '+' * border_length
        p_port = GetPanelPort()
        p_spath = GetSecurityPath()
        hostname = socket.gethostname()
        ip_addresses = socket.gethostbyname_ex(hostname)[2]
        hosts = [ip for ip in ip_addresses if not ip.startswith("127.")]
        internal_ip ="127.0.0.1" if not hosts else hosts[0]
        external_url = f"http://{ReadFile(settings.RUYI_PUBLICIP_FILE)}:{p_port}{p_spath}"
        internal_url = f"http://{internal_ip}:{p_port}{p_spath}"
        us = Users.objects.filter(is_superuser=True).first()
        username =us.username if us else ""
        print(border)
        print(f"外网面板地址: {external_url}")
        print(f"内网面板地址: {internal_url}")
        print(f"username: {username}")
        print(f"password: ******")
        print(border)
         
    def getVersion(self):
        """
        @name 获取如意版本信息
        @author lybbn<2024-01-13>
        """
        RUYI_SYSVERSION_FILE = settings.RUYI_SYSVERSION_FILE
        version = ReadFile(RUYI_SYSVERSION_FILE)
        print(f"获取如意版本信息：v{version}")
    
    def setPanelUsername(self,options):
        """
        @name 如意配置用户名
        @author lybbn<2024-01-13>
        """
        data = options['data']
        if data is None:
            data = 'ry'+GetRandomSet(6)
        if len(data)<5 or len(data)>16:
            self.stdout.write(self.style.ERROR('用户名长度需为5-16位'))
            return
        us = Users.objects.filter(is_superuser=True).first()
        if not us:
            self.stdout.write(self.style.ERROR('设置错误，无此用户'))
            return
        us.username=data
        us.save()
        print("已设置如意面板用户名为：%s"%data)

    def setSecretKey(self,options):
        """
        @name 如意配置SECRET_KEY
        @author lybbn<2024-01-13>
        """
        data = options['data']
        if data is None:
            data = generate_random_string(30)
        secret_key = "ruyi-insecure-%s"%data
        RUYI_SECRET_KEY_FILE = settings.RUYI_SECRET_KEY_FILE
        WriteFile(file_path=RUYI_SECRET_KEY_FILE,content=secret_key)
        print("已设置如意秘钥，需重启如意面板生效！！！")
    
    def setRuyiPanelSecrityPath(self,options):
        """
        @name 如意配置安全入口
        @author lybbn<2024-02-13>
        """
        data = options['data']
        
        if data is None:
            data = GetRandomSet(6)
        if not re.match("^[A-Za-z0-9]+$", data):
            self.stdout.write(self.style.ERROR('安全入口只能为字母、数字'))
            return
        if len(data)<5 or len(data)>16:
            self.stdout.write(self.style.ERROR('安全入口长度5-16位'))
            return
        sec_file_path = "/"+data
        RUYI_SYSTEM_PATH_LIST = [
            '/', '/login/', '/api', '/api/','/api/captcha/','/static/','/media/','/ry/','/ry','/settings','/home','/websites','/databases','/databases','/terminal',
            '/files','/crontab','/logs','/appstore','/firewall',"/monitors"
        ]
        if sec_file_path in RUYI_SYSTEM_PATH_LIST:
            self.stdout.write(self.style.ERROR('安全入口不能包含系统路径'))
            return
        
        WriteFile(settings.RUYI_SECURITY_PATH_FILE,sec_file_path)
        print("已设置面板安全入口为：%s，需重启如意面板生效！！！"%sec_file_path)
    
    def setRuyiPanelPort(self,options):
        """
        @name 如意配置访问端口
        @author lybbn<2024-02-13>
        """
        data = options['data']
        
        if data is None:
            data = random.randint(30000, 38999)
        else:
            data = int(data)
        if data < 1 or data>65534:
            self.stdout.write(self.style.ERROR('端口范围需1-65534'))
            return
        port = data
        is_ok = is_service_running(port)
        if is_ok:
            self.stdout.write(self.style.ERROR('设置错误，端口被占用'))
            return
        WriteFile(settings.RUYI_PORT_FILE,port)
        print("已设置面板访问端口：%s，需重启如意面板生效！！！"%str(port))