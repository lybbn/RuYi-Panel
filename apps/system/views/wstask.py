#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-01-13
# +-------------------------------------------------------------------
# | EditDate: 2025-01-13
# +-------------------------------------------------------------------

# ------------------------------
# ws通道
# ------------------------------

import json
import asyncio
import subprocess
from channels.generic.websocket import AsyncWebsocketConsumer
from utils.ruyiclass.dockerClass import DockerClient
from utils.ruyiclass.dockerInclude.ry_dk_square import main as dk_square
from utils.common import getTimestamp13
from apps.syslogs.logutil import asyncRuyiAddOpLog

class WSTaskConsumer(AsyncWebsocketConsumer):
    ruyi_ws_task_error_flag="ruyi_wstask_error"
    ruyi_ws_task_success_flag="ruyi_wstask_success"
    ruyi_ws_request_flag = 'ruyi_request_flag'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.missed_heartbeats = 0  # 未收到的心跳计数器
        self.heartbeat_limit = 3  # 最大允许未收到心跳次数
        self.heartbeat_timeout = 30  # 心跳超时间，单位：秒
        self.client_data = None #临时存储ws客户端发送的数据
    
    async def connect(self):
        self.room_group_name = "wstask"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()
        self.heartbeat_task = asyncio.create_task(self.heartbeat_checker())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )
        if hasattr(self, 'heartbeat_task'):
            if self.heartbeat_task:self.heartbeat_task.cancel()
        if hasattr(self, 'docker_pull_task'):
            if self.docker_pull_task:self.docker_pull_task.cancel()
        if hasattr(self, 'rum_cmd_task'):
            if self.rum_cmd_task:self.rum_cmd_task.cancel()
        if hasattr(self, 'get_compose_log_task'):
            if self.get_compose_log_task:self.get_compose_log_task.cancel()

    @classmethod
    async def decode_json(cls, text_data):
        return json.loads(text_data)
    
    async def receive(self, text_data=None, bytes_data=None):
        try:
            content = await self.decode_json(text_data)
            self.client_data = content
            action = content.get('action',None)
            data = content.get('data',None)
            if action == 'docker_pull':
                # await self.docker_pull(data) #耗时任务堵塞
                self.docker_pull_task = asyncio.create_task(self.docker_pull(data))
            elif action == 'runcmd':
                cmd=data.get('cmd','')
                self.rum_cmd_task = asyncio.create_task(self.run_command(cmd))
            elif action == 'get_compose_log':
                self.get_compose_log_task = asyncio.create_task(self.get_compose_log(data))
            elif action == 'heartBeat':
                self.missed_heartbeats = 0  # 重置未收到心跳计数器
                await self.send_message(action='heartBeat',message={'timestamp':getTimestamp13()})
        except Exception as e:
            await self.send_message(action='error',message=str(e))
                
    async def heartbeat_checker(self):
        """周期性检查是否收到心跳消息"""
        while True:
            await asyncio.sleep(self.heartbeat_timeout)  # 每 30 秒检查一次
            if self.missed_heartbeats >= self.heartbeat_limit:
                # 如果连续 N 次未收到心跳消息，则主动关闭连接
                await self.close()
                break
            else:
                # 增加未收到心跳的计数
                self.missed_heartbeats += 1

    async def send_message(self,action='output', message=''):
        """
        @name 自定义发送消息给客户端
        @author lybbn<2024-01-13>
        """
        # 发送消息给客户端
        msg = json.dumps({'action':action,'data':message})
        await self.send(text_data=msg)

    async def docker_pull(self, cont):
        try:
            client = DockerClient(conn=False)
            # 将同步的拉取操作放入一个异步线程
            if not cont:cont={}
            cont.update({'_ws':self})
            isok,msg = await client.pull_ws(cont)
            if isok:
                await self.send_message(action='success',message=msg)
            else:
                await self.send_message(action='error',message="")
        except Exception as e:
            await self.send_message(action='error',message=str(e))

    async def get_compose_log(self, cont):
        try:
            dksquare = dk_square()
            # 将同步的拉取操作放入一个异步线程
            if not cont:cont={}
            cont.update({'_ws':self})
            await dksquare.get_ws_logs(cont)
        except Exception as e:
            await self.send_message(action='error',message=str(e))
            
    async def run_command(self,cmd):
        WHITE_CMDS = ["docker","tail","cat"]
        DANGEROUS_ENDINGS = [';', '&&', '||', '|', '`', '>', '<', '>>']
        process = None
        try:
            if not cmd:
                await self.send_message(action='error',message="请输入命令")
                return
            cmd = cmd.strip()
            # 检查命令是否在白名单中
            is_white_cmd = False
            for w in WHITE_CMDS:
                if cmd.startswith(w):
                    is_white_cmd = True
                    break
                    
            if not is_white_cmd:
                await self.send_message(action='error',message="不支持此命令(有需要请联系如意面板作者)")
                return
                
            # 检查危险命令结尾
            if any(cmd.endswith(ending) for ending in DANGEROUS_ENDINGS):
                await self.send_message(action='error',message="危险的命令结尾(有需要请联系如意面板作者)")
                return
                
            # 启动子进程
            process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                bufsize=1,  # 行缓冲
                universal_newlines=True  # 文本模式
            )
            
            # 异步读取输出
            async def stream_output():
                try:
                    while True:
                        output = await asyncio.get_event_loop().run_in_executor(
                            None, 
                            process.stdout.readline
                        )
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            await self.send_message(message=output.strip())
                except Exception as e:
                    await self.send_message(action='error', message=f"输出读取错误: {str(e)}")
                    
                # 处理错误输出
                error_output = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    process.stderr.read
                )
                
                if error_output:
                    await self.send_message(action='error', message=error_output.strip())
                else:
                    await self.send_message(action='success', message=f"")
                    
                # 记录操作日志
                logtxt = f"{cmd}" if not error_output else f"错误：{error_output}"
                await asyncRuyiAddOpLog(self, msg=f"【执行命令】=> {logtxt}", status=not error_output, module="cmdmg")
                
            # 启动输出流任务
            await stream_output()
            
        except Exception as e:
            await self.send_message(action='error', message=f"命令执行错误: {str(e)}")
        finally:
            # 确保子进程被终止
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)  # 等待进程终止
                except subprocess.TimeoutExpired:
                    process.kill()  # 如果超时，强制终止