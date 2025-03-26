#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-16
# +-------------------------------------------------------------------
# | EditDate: 2025-02-16
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Docker 公用方法
# ------------------------------
import json
import psutil
from utils.common import WriteFile,RunCommand,current_os

def get_sys_cpumem_info():
    cpu_count = psutil.cpu_count(logical=False)  # 物理核心数
    logical_cpu_count = psutil.cpu_count(logical=True)  # 逻辑核心数（包括超线程）
    memory = psutil.virtual_memory()
    total_memory = memory.total  # 总内存（字节）
    available_memory = memory.available  # 可用内存（字节）
    data={
        "cpu_count":cpu_count,
        "logical_cpu_count":logical_cpu_count,
        "total_memory":total_memory,
        "available_memory":available_memory
    }
    return data

def format_to_dict(input_str):
    """
    转为dict字典
    params: input_str 格式"key1=value1\nkey2=value2"
    return {'key1':'value1','key2':'value2'}
    """
    if not input_str:return {}
    return dict(line.split('=') for line in input_str.split('\n'))

def docker_client_low_level(url=None):
    """
    docker低级接口
    """
    if not url:
        if current_os == "windows":
            # url="npipe:////./pipe/docker_engine"
            url="npipe:////./pipe/dockerDesktopLinuxEngine"
        else:
            url="unix:///var/run/docker.sock"
    try:
        import docker
    except:
        RunCommand("rypip install docker")
        import docker
    try:
        client = docker.APIClient(base_url=url)
        return client
    except docker.errors.DockerException:
        return None
    return None

def WriteLog(log_path, generator, task_name, max_iterations=2000):
    """实时写入流日志
    author:lybbn
    {"status": "Pulling fs layer"}
    {"status": "Downloading", "progressDetail": {"current": 4096, "total": 12345}}
    {"status": "Pull complete"}
    {"status": "Digest: sha256:..."}
    {"status": "Status: Downloaded newer image for ubuntu:latest"}
    """
    iteration_count = 0
    while iteration_count < max_iterations:
        try:
            stout = next(generator)
            iteration_count += 1
            try:
                stdout_json = json.loads(stout)
                if 'status' in stdout_json:
                    output_str = f"{stdout_json['status']}\n"
                    WriteFile(log_path, output_str,mode="a")
                
                if 'stream' in stdout_json:
                    output_str = stdout_json['stream']
                    WriteFile(log_path, output_str,mode="a")
            
            except json.JSONDecodeError:
                WriteFile(log_path, f"解析输出错误，原内容: {stout}\n",mode="a")
            except Exception as e:
                WriteFile(log_path, f"输出异常: {e}\n",mode="a")
        except StopIteration:
            WriteFile(log_path, f"{task_name} complete\n")
            break
        except ValueError as ve:
            WriteFile(log_path, f"ValueError occurred in {task_name}: {ve}\n")
        except Exception as e:
            WriteFile(log_path, f"Error in {task_name}: {str(e)}\n")
            
    if iteration_count >= max_iterations:
        WriteFile(log_path, f"【{task_name}】超出输出读取次数限制\n",mode="a")