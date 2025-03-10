#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-01-13
# +-------------------------------------------------------------------
# | EditDate: 2024-01-13
# +-------------------------------------------------------------------

# ------------------------------
# webssh
# ------------------------------

import sys,os
import asyncio
from threading import Thread
import time
import json
import paramiko
from utils.common import getTimestamp13,GetLocalSSHPort,GetLocalSSHUser,SetSSHSupportKey,RunCommand,ReadFile,isSSHRunning,SetSSHServiceStatus,SetSSHSupportRootPass
from io import BytesIO, StringIO
from django.http.request import QueryDict
from apps.system.models import TerminalServer
from channels.db import database_sync_to_async
from channels.generic.websocket import WebsocketConsumer,AsyncWebsocketConsumer
from django.conf import settings

# SSH_LOG_PATH = os.path.join(settings.BASE_DIR,'logs','terminal.log')
# paramiko.util.log_to_file(SSH_LOG_PATH)

def KeepSSHRunning():
    if not isSSHRunning():
        SetSSHServiceStatus(action="restart")

class WebSSHConsumerAsync(AsyncWebsocketConsumer):

    async def connect(self):
        """
        @name 连接ssh
        @author lybbn<2024-01-13>
        """

        # 建立WebSocket连接
        await self.accept()

        self.terminal_id = None
        self.ssh_conn = None
        self.channel = None
        self.process_output_task = None
        self.active = False

        # 获取连接初始信息
        query_string = self.scope.get('query_string')
        ssh_args = QueryDict(query_string=query_string, encoding='utf-8')
        cols = int(ssh_args.get('cols',80))
        rows = int(ssh_args.get('rows',24))
        self.terminal_id = ssh_args.get('id',None)
        
        # 连接到SSH服务器
        self.ssh_conn = paramiko.SSHClient()
        # SSH客户端Host策略,目的是接受不在本地Known_host文件下的主机。
        self.ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
        self.ssh_conn.load_system_host_keys()
        try:
            await self.send_message(message='连接中...\r\n')
            await self.connect_ssh()
        except Exception as e:
            await self.handle_ssh_exception(e)
            return

        if not self.ssh_conn:
            await self.send_message(message='连接ssh失败\r\n')
            await self.close()
            return
        
        # 开启交互式终端
        self.channel = self.ssh_conn.invoke_shell(term='xterm',width=cols,height=rows)
        # 设置后端ssh通道保活时间
        self.channel.transport.set_keepalive(40)
        # 将通道设置为非阻塞模式
        # self.channel.setblocking(0.1)
        self.active = True
        await self.send_message(message='连接成功 \r\n')
        self.process_output_task = asyncio.create_task(self.process_output())

    async def handle_ssh_exception(self,e):
        """
        @name ssh连接错误异常消息处理
        @author lybbn<2024-01-13>
        """
        e = str(e)
        if isinstance(e, paramiko.AuthenticationException):
            errors = f"认证失败：{e}"
        elif isinstance(e, paramiko.SSHException):
            errors = f"SSH连接错误：{e}"
        elif isinstance(e, paramiko.BadHostKeyException):
            errors = f"无效的主机密钥：{e}"
        elif e.find('Connection reset by peer') != -1:
            errors = '目标服务器主动拒绝连接'
        elif e.find('Error reading SSH protocol banner') != -1:
            errors = '协议头响应超时'
        elif e.find('Authentication failed') != -1:
            errors = f'SSH认证失败：{e}'
        elif not e:
            errors = 'SSH协议握手超时'
        elif e.find('Unable to connect to port') != -1:
            errors = f'连接失败：{e}'
        else:
            errors = f'未知错误: {e}'

        await self.send_message(message='Exception: %s\r\n' % errors)
        await self.close()
    
    async def disconnect(self, close_code):
        """
        @name 断开socket
        @author lybbn<2024-01-13>
        """
        try:
            self.active = False
            if self.channel:
                self.channel.close()
            # 关闭SSH连接
            if self.ssh_conn:
                self.ssh_conn.close()
            if self.process_output_task:
                self.process_output_task.cancel()
        except:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        """
        @name 处理前端发送的消息
        @author lybbn<2024-01-13>
        """
        if text_data:
            await self.process_command(text_data)
    
    async def process_command(self,text_data):
        """
        @name 处理前端发送的指令
        @author lybbn<2024-01-13>
        """
        content = await self.decode_json(text_data)
        ws_type = content['type']
        data = content.get('data',None)
        if ws_type == 'cmd':
            # 将客户端输入的命令发送给SSH服务器
            await self.send_command(data)
        elif ws_type == 'resize':
            await self.resize(content)
        elif ws_type == 'heartBeat':
            await self.send_message(type='heartBeat',message={'timestamp':getTimestamp13()})

    async def send_command(self,data):
        """
        @name 转发客户端命令给ssh服务端
        @author lybbn<2024-01-13>
        """
        # 将客户端输入的命令发送给SSH服务器
        if self.channel:
            self.channel.send(data)

    async def process_output(self):
        """
        @name 转发服务端消息给客户端（self.channel.recv非阻塞）
        @author lybbn<2024-01-13>
        """
        bufsize = 1024  # 初始接收数据的大小
        while self.active:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(bufsize)
                    if not data:
                        await self.close()
                        break
                    # 根据需要动态调整 bufsize 的大小
                    bufsize = self.calculate_new_bufsize(data)
                    # 将SSH连接输出发送给客户端
                    try:
                        r_data = data.decode('utf-8','ignore')
                    except:
                        try:
                            r_data = data.decode()
                        except:
                            r_data = str(data)
                    await self.send_message(message=r_data)
                if self.channel.closed:
                    await self.close()
                    break
                await asyncio.sleep(0.1)  # 添加适当的延迟以避免占用过多的计算资源
            except Exception as e:
                await self.send_message(message='[error]'+str(e)+' \r\n')
                if self.channel.closed:
                    await self.close()
                break

    async def process_output_block(self):
        """
        @name 转发服务端消息给客户端（self.channel.recv阻塞）
        @author lybbn<2024-01-13>
        """
        loop = asyncio.get_event_loop()
        while self.active:
            try:
                data = await loop.run_in_executor(None, self.channel.recv, 1024)  # 读取数据，调整缓冲区大小为1024
                if not data:
                    await self.close()
                    break
                # 将SSH连接输出发送给客户端
                await self.send_message(message=data.decode('utf-8'))
                if self.channel.closed:
                    await self.close()
                    break
                await asyncio.sleep(0.1)  # 添加适当的延迟以避免占用过多的计算资源
            except Exception as e:
                await self.send_message(message=str(e)+' \r\n')
                await self.close()
                break

    @database_sync_to_async
    def connect_ssh(self):
        """
        @name 连接ssh
        @author lybbn<2024-01-13>
        """
        if self.terminal_id and not str(self.terminal_id) == '0':
            # 获取SSH连接信息
            ssh_info = TerminalServer.objects.filter(id=self.terminal_id).first()
            if not ssh_info:
                self.send_message(message='无此主机信息\r\n')
                self.close()
            targethost = ssh_info.host
            if targethost in ["127.0.0.1","localhost"]:
                KeepSSHRunning()
                if ssh_info.type == 0 and ssh_info.username=="root":
                    SetSSHSupportRootPass()
            # 连接到SSH服务器
            if ssh_info.type == 0:
                self.ssh_conn.connect(
                    hostname=targethost,
                    username=ssh_info.username,
                    password=ssh_info.password,
                    port=ssh_info.port,
                    timeout=30,
                    banner_timeout=30,
                    allow_agent=False,
                    look_for_keys=False
                )
                    
            else:
                tmppkey = ssh_info.pkey.encode('utf-8')
                if sys.version_info[0] == 2:
                    pk_file = BytesIO(tmppkey)
                else:
                    pk_file = StringIO(tmppkey)
                pkey_passwd = ssh_info.pkey_passwd
                if pkey_passwd:
                    pkey = paramiko.RSAKey.from_private_key(pk_file,password=ssh_info.pkey_passwd)
                else:
                    pkey = paramiko.RSAKey.from_private_key(pk_file)
                self.ssh_conn.connect(
                    hostname=self.ssh_info.host,
                    port=self.ssh_info.port,
                    username=self.ssh_info.username,
                    pkey=pkey,
                    timeout=30,
                    banner_timeout=30
                )
        else:#直连本机
            ssh_host = "127.0.0.1"
            ssh_port = GetLocalSSHPort()
            ssh_user = GetLocalSSHUser()
            home_path = '/home/' + ssh_user
            if ssh_user == 'root':
                home_path = '/root'
            SetSSHSupportKey()
            authorized_keys_path = f"{home_path}/.ssh/authorized_keys"
            id_rsa_file = f"{home_path}/.ssh/id_rsa"
            if not os.path.exists(id_rsa_file) or not os.path.exists(authorized_keys_path):
                self.generate_key(authorized_keys_path,id_rsa_file)
            pkey = paramiko.RSAKey.from_private_key_file(id_rsa_file)
            KeepSSHRunning()
            self.ssh_conn.connect(
                hostname=ssh_host,
                port=ssh_port,
                username=ssh_user,
                pkey=pkey,
                timeout=30,
                banner_timeout=30
            )
    
    def generate_key(self,authorized_keys_path,key_path):
        """
        @name 生成rsa 公钥\私钥
        @key_path 私钥路径
        @author lybbn<2024-01-13>
        """
        # 确保 .ssh 目录存在
        ssh_dir = os.path.dirname(key_path)
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, mode=0o700)  # 创建目录并设置权限
        # 创建 RSA 密钥
        key = paramiko.RSAKey.generate(4096)
        # 保存私钥
        key.write_private_key_file(key_path)
        # 保存公钥
        public_key = f"{key.get_name()} {key.get_base64()}"
        
        with open(f"{key_path}.pub", 'w') as pub_file:
            pub_file.write(public_key)
        os.chmod(key_path, 0o400)
        os.chmod(f"{key_path}.pub", 0o600)
        with open(authorized_keys_path, 'a') as auth_keys_file:
            auth_keys_file.write(public_key + '\n')
        

    async def resize(self, data):
        """
        @name 调整终端大小
        @author lybbn<2024-01-13>
        """
        try:
            cols = int(data['cols'])
            rows = int(data['rows'])
            self.channel.resize_pty(width=cols, height=rows)
        except:
            pass

    async def send_message(self,type='cmd', message=''):
        """
        @name 自定义发送消息给客户端
        @author lybbn<2024-01-13>
        """
        # 发送消息给客户端
        msg = json.dumps({'type':type,'data':message})
        await self.send(text_data=msg)

    @classmethod
    async def decode_json(cls, text_data):
        return json.loads(text_data)
    
    def calculate_new_bufsize(self, data):
        """
        @name 动态计算输出缓存大小
        @author lybbn<2024-01-13>
        """
        buffer_length = len(data)
        if buffer_length < 1024:
            return 1024 #如果数据大小小于 1KB，则使用 1KB 的缓冲区
        elif buffer_length < 1024*10:
            return 1024*10 # 使用 10KB 的缓冲区 
        else:
            return 1024*20

class WebSSHConsumer(WebsocketConsumer):

    def connect(self):
        """
        @name 连接ssh
        @author lybbn<2024-01-13>
        """

        # 建立WebSocket连接
        self.accept()

        self.terminal_id = None
        self.ssh_conn = None
        self.channel = None
        self.process_output_task = None
        self.active = False

        # 获取连接初始信息
        query_string = self.scope.get('query_string')
        ssh_args = QueryDict(query_string=query_string, encoding='utf-8')
        cols = int(ssh_args.get('cols',80))
        rows = int(ssh_args.get('rows',24))
        self.terminal_id = ssh_args.get('id',None)
        
        # 连接到SSH服务器
        self.ssh_conn = paramiko.SSHClient()
        # SSH客户端Host策略,目的是接受不在本地Known_host文件下的主机。
        self.ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
        self.ssh_conn.load_system_host_keys()
        try:
            self.send_message(message='连接中...\r\n')
            self.connect_ssh()
        except Exception as e:
            self.handle_ssh_exception(e)
            return

        # 开启交互式终端
        self.channel = self.ssh_conn.invoke_shell(term='xterm',width=cols,height=rows)
        # 设置后端ssh通道保活时间
        self.channel.transport.set_keepalive(30)
        # 将通道设置为非阻塞模式
        self.channel.setblocking(0)
        self.channel.settimeout(0)
        self.active = True
        self.send_message(message='连接成功 \r\n')
        # self.process_output_task = asyncio.create_task(self.process_output())
        Thread(target=self.process_output).start()

    def handle_ssh_exception(self,e):
        """
        @name ssh连接错误异常消息处理
        @author lybbn<2024-01-13>
        """
        e = str(e)
        if isinstance(e, paramiko.AuthenticationException):
            errors = "认证失败：{}".format(e)
        elif isinstance(e, paramiko.SSHException):
            errors = "SSH连接错误：{}".format(e)
        elif isinstance(e, paramiko.BadHostKeyException):
            errors = "无效的主机密钥：{}".format(e)
        elif e.find('Connection reset by peer') != -1:
            errors = '目标服务器主动拒绝连接'
        elif e.find('Error reading SSH protocol banner') != -1:
            errors = '协议头响应超时'
        elif not e:
            errors = 'SSH协议握手超时'
        elif e.find('Unable to connect to port') != -1:
            errors = '连接失败{}'.format(e)
        else:
            import traceback
            errorMsg = traceback.format_exc()
            errors = '未知错误: {}'.format(errorMsg)

        self.send_message(message='Exception: %s\r\n' % errors)
        self.close()
    
    def disconnect(self, close_code):
        """
        @name 断开socket
        @author lybbn<2024-01-13>
        """
        self.active = False
        if self.channel:
            self.channel.close()
        # 关闭SSH连接
        if self.ssh_conn:
            self.ssh_conn.close()
        if self.process_output_task:
            self.process_output_task.cancel()

    def receive(self, text_data=None, bytes_data=None):
        """
        @name 处理前端发送的消息
        @author lybbn<2024-01-13>
        """
        if text_data:
            Thread(target=self.process_command, args=[text_data]).start()
            # self.process_command(text_data)
    
    def process_command(self,text_data):
        """
        @name 处理前端发送的指令
        @author lybbn<2024-01-13>
        """
        content = self.decode_json(text_data)
        ws_type = content['type']
        data = content.get('data',None)
        if ws_type == 'cmd':
            # 将客户端输入的命令发送给SSH服务器
            self.send_command(data)
        elif ws_type == 'resize':
            self.resize(content)
        elif ws_type == 'heartBeat':
            timestamp = content['timestamp']
            self.send_message(type='heartBeat',message={'timestamp':timestamp})
        
    def ssh_to_ws(self):
        """
        @name 转发服务端消息给客户端（self.channel.recv非阻塞）
        @author lybbn<2024-01-13>
        """
        bufsize = 1024  # 初始接收数据的大小
        while not self.channel.exit_status_ready():
            data = self.channel.recv(bufsize)
            if not data:
                break
            # 根据需要动态调整 bufsize 的大小
            bufsize = self.calculate_new_bufsize(data)
            # 将SSH连接输出发送给客户端
            try:
                r_data = data.decode('utf-8','ignore')
            except:
                try:
                    r_data = data.decode()
                except:
                    r_data = str(data)
            self.send_message(message=r_data)
            
    def send_command(self,data):
        """
        @name 转发客户端命令给ssh服务端
        @author lybbn<2024-01-13>
        """
        # 将客户端输入的命令发送给SSH服务器
        self.channel.send(data)
        time.sleep(0.1)  # 延迟，以确保接收到的是命令执行结果

    def process_output(self):
        """
        @name 转发服务端消息给客户端（self.channel.recv非阻塞）
        @author lybbn<2024-01-13>
        """
        bufsize = 1024  # 初始接收数据的大小
        while self.active:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(bufsize)
                    # if not data:
                    #     self.close()
                    #     break
                    # 根据需要动态调整 bufsize 的大小
                    bufsize = self.calculate_new_bufsize(data)
                    # 将SSH连接输出发送给客户端
                    try:
                        r_data = data.decode('utf-8','ignore')
                    except:
                        try:
                            r_data = data.decode()
                        except:
                            r_data = str(data)
                    self.send_message(message=r_data)
                # if self.channel.closed:
                #     self.close()
                #     break
                # time.sleep(0.1)
            except Exception as e:
                print("异常退出:%s"%(str(e)))
                self.send_message(message='\r\n[错误内容]'+str(e)+' \r\n')
                # self.close()
                break

    def connect_ssh(self):
        """
        @name 连接ssh
        @author lybbn<2024-01-13>
        """
        # 获取SSH连接信息
        ssh_info = TerminalServer.objects.get(id=self.terminal_id)
        # 连接到SSH服务器
        if ssh_info.type == 0:
            self.ssh_conn.connect(
                ssh_info.host,
                username=ssh_info.username,
                password=ssh_info.password,
                port=ssh_info.port,
                timeout=30
            )
        else:
            tmppkey = ssh_info.pkey.encode('utf-8')
            if sys.version_info[0] == 2:
                pk_file = BytesIO(tmppkey)
            else:
                pk_file = StringIO(tmppkey)
            pkey_passwd = ssh_info.pkey_passwd
            if pkey_passwd:
                pkey = paramiko.RSAKey.from_private_key(pk_file,password=ssh_info.pkey_passwd)
            else:
                pkey = paramiko.RSAKey.from_private_key(pk_file)
            self.ssh_conn.connect(
                hostname=self.ssh_info.host,
                port=self.ssh_info.port,
                username=self.ssh_info.username,
                pkey=pkey,
                timeout=30
            )

    def resize(self, data):
        """
        @name 调整终端大小
        @author lybbn<2024-01-13>
        """
        try:
            self.channel.resize_pty(width=int(data['cols']), height=int(data['rows']))
        except:
            pass

    def send_message(self,type='cmd', message=''):
        """
        @name 自定义发送消息给客户端
        @author lybbn<2024-01-13>
        """
        # 发送消息给客户端
        msg = json.dumps({'type':type,'data':message})
        self.send(text_data=msg)

    @classmethod
    def decode_json(cls, text_data):
        return json.loads(text_data)
    
    def calculate_new_bufsize(self, data):
        """
        @name 动态计算输出缓存大小
        @author lybbn<2024-01-13>
        """
        buffer_length = len(data)
        if buffer_length < 1024:
            return 1024 #如果数据大小小于 1KB，则使用 1KB 的缓冲区
        elif buffer_length < 1024*33:
            return 1024*32 # 使用 32KB 的缓冲区 
        else:
            return 1024*60
        
    