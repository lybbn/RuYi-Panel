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

import os
import time
import json
import asyncio
import subprocess
from channels.generic.websocket import AsyncWebsocketConsumer
from utils.ruyiclass.dockerClass import DockerClient
from utils.ruyiclass.dockerInclude.ry_dk_square import main as dk_square
from utils.common import getTimestamp13, GetLogsPath
from apps.syslogs.logutil import asyncRuyiAddOpLog
from utils.server.system import system

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
        if hasattr(self, 'get_update_log_task'):
            if self.get_update_log_task:self.get_update_log_task.cancel()

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
            elif action == 'get_tail_file':
                self.rum_cmd_task = asyncio.create_task(self.get_tail_file(data))
            elif action == 'get_compose_log':
                self.get_compose_log_task = asyncio.create_task(self.get_compose_log(data))
            elif action == 'get_update_log':
                self.get_update_log_task = asyncio.create_task(self.get_update_log(data))
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

    async def get_tail_file(self,cont):
        success_flag = "ruyi_successful_flag"
        failed_flag = "ruyi_failed_flag"
        filepath = cont.get("filepath","")
        if not filepath:
            await self.send_message(action='error', message="缺少文件路径")
            return
        lines = cont.get("lines",100)
        realtime = cont.get("realtime",False)
        timeout = 60*5
        start_time = time.time()
        if not realtime:
            data = system.GetFileLastNumsLines(filepath,lines)
            await self.send_message(message=data)
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                # 移动到文件末尾
                file.seek(0, os.SEEK_END)

                while True:
                    current_time = time.time()
                    # 如果超时，则退出
                    if current_time - start_time >= timeout:
                        break
                    # 读取新增内容
                    line = file.readline()
                    if line:
                        await self.send_message(message=line.strip())

                        # 检查是否包含停止标志
                        if success_flag in line or failed_flag in line:
                            await self.close()  # 关闭 WebSocket 连接
                            break
                    else:
                        await asyncio.sleep(0.05)
        except FileNotFoundError:
            await self.send_message(action='error', message=f"文件 {filepath} 不存在")
            await self.close()
        except Exception as e:
            await self.send_message(action='error', message=f"{e}")
            await self.close()
    
    async def get_update_log(self, cont):
        success_flag = "ruyi_successful_flag"
        failed_flag = "ruyi_failed_flag"
        filepath = os.path.join(GetLogsPath(), 'ruyi_updatepanel.log')
        lines = cont.get("lines", 200)
        realtime = cont.get("realtime", True)
        timeout = 60 * 15
        start_time = time.time()

        def _delete_stale_log(fp):
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass

        await asyncio.to_thread(_delete_stale_log, filepath)

        while not await asyncio.to_thread(os.path.exists, filepath):
            if time.time() - start_time >= 30:
                await self.send_message(action='error', message="⏳ 等待日志文件超时，可能升级进程未启动")
                return
            await asyncio.sleep(0.2)

        if not realtime:
            data = await asyncio.to_thread(system.GetFileLastNumsLines, filepath, lines)
            await self.send_message(message=data)
            return

        def _read_initial_lines(fp, max_lines):
            with open(fp, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                total = len(all_lines)
                start_idx = max(0, total - max_lines)
                result = []
                for i in range(start_idx, total):
                    result.append(all_lines[i])
                return result, f.tell()

        def _read_new_lines(fp, offset):
            new_lines = []
            new_offset = offset
            with open(fp, 'r', encoding='utf-8') as f:
                f.seek(offset)
                while True:
                    line = f.readline()
                    if not line:
                        break
                    if not line.endswith('\n'):
                        # 读到不完整的行，回退 offset，等下次再读
                        new_offset = f.tell() - len(line.encode('utf-8'))
                        break
                    new_lines.append(line)
                # 无论是否读到新行，都更新 offset 为当前文件位置
                new_offset = f.tell()
            return new_lines, new_offset

        last_offset = 0
        try:
            initial_lines, last_offset = await asyncio.to_thread(_read_initial_lines, filepath, lines)
            for line in initial_lines:
                await self.send_message(message=line)
                if success_flag in line or failed_flag in line:
                    await self.close()
                    return

            while True:
                current_time = time.time()
                if current_time - start_time >= timeout:
                    await self.send_message(action='error', message="⚠️ 更新操作超时（15分钟），请检查后台进程或查看日志文件")
                    break

                current_size = await asyncio.to_thread(os.path.getsize, filepath)

                if current_size > last_offset:
                    new_lines, last_offset = await asyncio.to_thread(_read_new_lines, filepath, last_offset)
                    for line in new_lines:
                        await self.send_message(message=line)
                        if success_flag in line or failed_flag in line:
                            await self.close()
                            return

                await asyncio.sleep(0.3)

        except FileNotFoundError:
            await self.send_message(action='error', message=f"❌ 日志文件不存在: {filepath}")
            await self.close()
        except Exception as e:
            await self.send_message(action='error', message=f"❌ 读取日志出错: {e}")
            await self.close()
            
    async def run_command(self, cmd):
        WHITE_CMDS = ["docker", "tail", "cat"]
        DANGEROUS_ENDINGS = [';', '&&', '||', '|', '`', '>', '<', '>>']
        process = None
        try:
            if not cmd:
                await self.send_message(action='error', message="请输入命令")
                return
            cmd = cmd.strip()
            # 检查命令是否在白名单中
            is_white_cmd = False
            for w in WHITE_CMDS:
                if cmd.startswith(w):
                    is_white_cmd = True
                    break

            if not is_white_cmd:
                await self.send_message(action='error', message="不支持此命令(有需要请联系如意面板作者)")
                return

            # 检查危险命令结尾
            if any(cmd.endswith(ending) for ending in DANGEROUS_ENDINGS):
                await self.send_message(action='error', message="危险的命令结尾(有需要请联系如意面板作者)")
                return

            # 启动子进程
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # 异步读取输出
            async def stream_output():
                try:
                    while True:
                        output = await process.stdout.readline()
                        if output == b'' and process.returncode is not None:
                            break
                        if output:
                            await self.send_message(message=output.decode().strip())
                except Exception as e:
                    await self.send_message(action='error', message=f"输出读取错误: {str(e)}")

                # 处理错误输出
                error_output = await process.stderr.read()
                if error_output:
                    await self.send_message(action='error', message=error_output.decode().strip())
                else:
                    await self.send_message(action='success', message=f"")

                # 记录操作日志
                logtxt = f"{cmd}" if not error_output else f"错误：{error_output.decode().strip()}"
                await asyncRuyiAddOpLog(self, msg=f"【执行命令】=> {logtxt}", status=not error_output, module="cmdmg")

            # 启动输出流任务
            await stream_output()

        except Exception as e:
            await self.send_message(action='error', message=f"命令执行错误: {str(e)}")
        finally:
            # 确保子进程被终止
            if process and process.returncode is None:
                try:
                    # 使用 asyncio.wait_for 添加超时
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()  # 确保进程被清理
