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
# Docker 容器类
# ------------------------------
import time
import os
import docker.types
from utils.common import ast_convert,is_service_running
from utils.ruyiclass.dockerInclude.ry_dk_common import format_to_dict,get_sys_cpumem_info

class main:
    client=None#容器连接客户端
    driver_list=["bridge","macvlan","ipvlan","overlay"] #还有none,host
    system_networks = {'none', 'bridge', 'host','ruyi-network'}
    def __init__(self,client=None):
        self.client = client
        
    def get_container_ip(self, container_networks):
        data = []
        for network in container_networks:
            data.append(container_networks[network]['IPAddress'])
        return data
        
    def add(self,cont={}):
        """
        添加动容器
        """
        try:
            name = cont.get('name',"")
            if not name:return False, "缺少容器名"
            
            image = cont.get('image',"") # 使用的镜像
            if not image:return False, "缺少镜像名"
            syscpumeminfo = get_sys_cpumem_info()
            total_memory = syscpumeminfo['total_memory']
            cpu_count = syscpumeminfo['cpu_count']
            cpu_quota = int(cont.get('cpu_quota',0))
            if cpu_quota:
                if cpu_quota > cpu_count:
                    return False, "CPU限制已超过可用内核数"
                cpu_quota = cpu_quota * 100000
                
            cpu_shares = int(cont.get('cpu_shares',1024))
            
            mem_limit = int(cont.get('mem_limit',0))
            if not mem_limit:
                mem_limit=None
            else:
                mem_limit_byte = mem_limit * 1024 * 1024
                if mem_limit_byte>total_memory:return False,"内存限制已超过可用量"
                if mem_limit_byte < 6291456:
                    return False, "内存限制不能小于6MB"
            
            mem_reservation = int(cont.get('mem_reservation',0))
            if not mem_reservation:
                mem_reservation = None
            else:
                mem_reservation_byte = mem_limit * 1024 * 1024
                if mem_reservation_byte>total_memory:return False,"最小内存已超过可用量"
                if mem_reservation_byte < 6291456:
                    return False, "最小内存不能小于6MB"
            
            publish_all_ports = cont.get('publish_all_ports',False)
            ports = ast_convert(cont.get('ports',[]))
            if publish_all_ports or not ports:
                ports={}
            else:
                new_ports = {}
                for pt in ports:
                    hostPort = pt["hostPort"]
                    containerPort = pt["containerPort"]
                    protocol = pt["protocol"]
                    if ":" in hostPort or "-" in hostPort:
                        return False, "暂不支持此格式端口"
                    if ":" in containerPort or "-" in containerPort:
                        return False, "暂不支持此格式端口"
                    if not protocol in ["tcp","udp"]:
                        return False,"协议错误"
                    if is_service_running(port=int(hostPort)):
                        return False,f"{hostPort}端口已被占用，请更换！！！"
                    new_ports[str(containerPort) + "/"+protocol] = int(hostPort)
                ports = new_ports
            
            networks = ast_convert(cont.get('networks',[]))
            networking_config={}
            if not networks:
                network = None
            else:
                for ntw in networks:
                    name = ntw["name"]
                    ipv4_address =ntw["ipv4_address"]
                    tmp_ipdict = {"ipv4_address": ipv4_address} if ipv4_address else {}
                    networking_config[name] = tmp_ipdict
                network = networks[0]["name"]#默认连接到第一个网络
                
            volumes = ast_convert(cont.get('volumes',[]))
            if not volumes:
                volumes = None
            else:
                new_volumes = {}
                for item in volumes:
                    if item["type"] not in ["volume","localdir"]:return False,"挂载参数错误"
                    new_volumes[item["local_dir"]] = {
                        "bind": item["container_dir"],
                        "mode": item["mode"]
                    }
                volumes = new_volumes
                
            restart_policy = cont.get('restart_policy','no')
            default_restart_policy = {"Name": restart_policy}
            if restart_policy == "on-failure":
                restart_policy = {"Name": "on-failure", "MaximumRetryCount": 5}
            else:
                restart_policy=default_restart_policy
            
            command = cont.get('command',None)
            if not command:command=None
            
            auto_remove = cont.get('auto_remove',False)
            privileged = cont.get('privileged',False)
            tty = cont.get('tty',False)
            stdin_open = cont.get('stdin_open',False)
            
            labels = format_to_dict(cont.get('labels',''))
            env = format_to_dict(cont.get('env',''))
            entrypoint = cont.get('entrypoint','')
            res = self.client.containers.create(
                name=name,
                image=image,
                restart_policy=restart_policy,
                command=command,
                entrypoint=entrypoint,
                environment=env,
                labels=labels,
                ports=ports,  # {'80/tcp': 8080} {'容器端口/协议': 宿主机端口}将容器的tcp 80端口映射到主机的8080端口
                network=network, #连接到哪个网络，'bridge'
                networking_config=networking_config, #{"my_custom_network": {"ipv4_address": "192.168.1.100"}}
                volumes=volumes,
                cpu_quota=int(cpu_quota) or 0,
                cpu_shares=cpu_shares,
                mem_limit=mem_limit,
                publish_all_ports=publish_all_ports,#暴露所有端口
                detach=True,  # 后台运行容器
                stdin_open=stdin_open,
                tty=tty,
                privileged=privileged,
                auto_remove=auto_remove#停止自动删除
            )
            return True,"添加成功"
        except Exception as e:
            return False,f"添加失败：{e}"
        
    def start(self, cont={}):
        """
        启动容器
        :param get:
        :return:
        """
        try:
            id = cont.get('id',"")
            container = self.client.containers.get(id)
            container.start()
            time.sleep(1)
            res = self.client.containers.get(id)
            if res.attrs['State']['Status'] != "running":
                return False, "启动失败"
            return True, "启动成功!"
        except docker.errors.APIError as e:
            if "cannot start a paused container, try unpause instead" in str(e):
                return False,f"无法启动一个已暂停的容器"
            elif "Unable to enable DNAT rule" in str(e):
                return False,"端口映射失败，请检查端口冲突问题"
            return False, f"启动失败：{e}"
        except Exception as e:
            return False, f"启动失败：{e}"
        
    def stop(self,cont={}):
        """停止容器"""
        try:
            id = cont.get('id',"")
            container = self.client.containers.get(id)
            container.stop()
            time.sleep(1)
            res = self.client.containers.get(id)
            if res.attrs['State']['Status'] != "exited":
                return False, "停止失败"
            return True, "停止成功"
        except docker.errors.APIError as e:
            if "is already paused" in str(e):
                return False, "容器已暂停,无需停止"
            if "No such container" in str(e):
                return True, "容器已停止并删除(停止删除属性)"
            return False, f"停止失败：{e}"
    
    def pause(self,cont={}):
        """
        暂停容器(暂停容器所有的进程)
        """
        try:
            id = cont.get('id',"")
            container = self.client.containers.get(id)
            container.pause()
            time.sleep(1)
            res = self.client.containers.get(id)
            if res.attrs['State']['Status'] != "paused":
                return False, "暂停失败"
            return True, "暂停成功"
        except docker.errors.APIError as e:
            if "is already paused" in str(e):
                return False, "容器已被暂停"
            if "is not running" in str(e):
                return False, "该容器未启动，无法暂停"
            if "is not paused" in str(e):
                return False, "容器或已被删除，请检查容器是否有【停止后立即删除的选项】"
            return False,str(e)
        except Exception as e:
            return False, f"暂停失败：{e}"
        
    def unpause(self, cont={}):
        """
        恢复已暂停的容器
        """
        try:
            id = cont.get('id',"")
            container = self.client.containers.get(id)
            container.unpause()
            time.sleep(1)
            res = self.client.containers.get(id)
            if res.attrs['State']['Status'] != "running":
                return False, "恢复失败"
            return True, "恢复成功"
        except Exception as e:
            return False, f"恢复失败：{e}"
        
    def reload(self, cont={}):
        """
        重载容器
        """
        try:
            id = cont.get('id',"")
            container = self.client.containers.get(id)
            container.reload()
            time.sleep(1)
            res = self.client.containers.get(id)
            if res.attrs['State']['Status'] != "running":
                return False, "重载失败"
            return True, "重载成功"
        except Exception as e:
            return False, f"重载失败：{e}"
        
    def restart(self, cont={}):
        """
        重启容器
        """
        try:
            id = cont.get('id',"")
            container = self.client.containers.get(id)
            container.restart()
            time.sleep(1)
            res = self.client.containers.get(id)
            if res.attrs['State']['Status'] != "running":
                return False, "重启失败"
            return True, "重启成功"
        except Exception as e:
            if "container is marked for removal and cannot be started" in str(e):
                return False, "容器或已被删除，请检查容器是否有【停止后立即删除的选项】"
            if "is already paused" in str(e):
                return False, "容器已暂停，请先恢复"
            return False, f"重启失败：{e}"
    
    def set_status(self,cont={}):
        """设置容器状态"""
        try:
            status=cont.get('status',"")
            if status == "start":
                return self.start(cont=cont)
            elif status == "stop":
                return self.stop(cont=cont)
            elif status == "pause":
                return self.pause(cont=cont)
            elif status == "unpause":
                return self.unpause(cont=cont)
            elif status == "restart":
                return self.restart(cont=cont)
            elif status == "reload":
                return self.reload(cont=cont)
            return False,"不支持的操作"
        except Exception as e:
            return False, f"设置状态失败：{e}"
    
    def remove(self,cont={}):
        """
        删除容器
        """
        id = cont.get('id',"")
        force = cont.get('force',False)
        try:
            id = cont.get('id',"")
            container = self.client.containers.get(id)
            container.remove(force=force)
            return True, "删除成功"
        except Exception as e:
            if "container is running: stop the container before removing or force remove" in str(e):
                return False, "容器正在运行，请强制删除"
            return False,f"删除失败: {e}"
    
    def local_container_list(self):
        if not self.client:
            return []
        return self.client.containers.list()

    def edit(self, cont={}):
        """
        编辑容器配置（需要先停止、删除、重新创建）
        """
        try:
            id = cont.get('id', "")
            if not id:
                return False, "缺少容器ID"
            
            # 获取原容器信息
            try:
                old_container = self.client.containers.get(id)
                old_attrs = old_container.attrs
            except Exception as e:
                return False, f"获取容器信息失败：{e}"
            
            # 获取原容器配置
            old_name = old_attrs['Name'].lstrip('/')
            old_image = old_attrs['Config']['Image']
            old_status = old_attrs['State']['Status']
            
            # 获取新配置
            cpu_quota = int(cont.get('cpu_quota', 0))
            mem_limit = int(cont.get('mem_limit', 0))
            ports = ast_convert(cont.get('ports', []))
            networks = ast_convert(cont.get('networks', []))
            volumes = ast_convert(cont.get('volumes', []))
            restart_policy = cont.get('restart_policy', old_attrs['HostConfig']['RestartPolicy']['Name'])
            
            # 验证配置
            syscpumeminfo = get_sys_cpumem_info()
            total_memory = syscpumeminfo['total_memory']
            cpu_count = syscpumeminfo['cpu_count']
            
            if cpu_quota:
                if cpu_quota > cpu_count:
                    return False, "CPU限制已超过可用内核数"
                cpu_quota = cpu_quota * 100000
            
            if mem_limit:
                mem_limit_byte = mem_limit * 1024 * 1024
                if mem_limit_byte > total_memory:
                    return False, "内存限制已超过可用量"
                if mem_limit_byte < 6291456:
                    return False, "内存限制不能小于6MB"
            else:
                mem_limit = None
            
            # 处理端口映射
            new_ports = {}
            if ports:
                for pt in ports:
                    hostPort = pt["hostPort"]
                    containerPort = pt["containerPort"]
                    protocol = pt["protocol"]
                    if ":" in hostPort or "-" in hostPort:
                        return False, "暂不支持此格式端口"
                    if ":" in containerPort or "-" in containerPort:
                        return False, "暂不支持此格式端口"
                    if protocol not in ["tcp", "udp"]:
                        return False, "协议错误"
                    # 检查端口是否被其他服务占用（排除当前容器）
                    if is_service_running(port=int(hostPort)):
                        # 检查是否是当前容器占用的端口
                        old_ports = old_attrs['HostConfig']['PortBindings'] or {}
                        port_in_use_by_self = False
                        for old_container_port, old_host_bindings in old_ports.items():
                            if old_host_bindings:
                                for binding in old_host_bindings:
                                    if binding and binding.get('HostPort') == hostPort:
                                        port_in_use_by_self = True
                                        break
                        if not port_in_use_by_self:
                            return False, f"{hostPort}端口已被占用，请更换！！！"
                    new_ports[str(containerPort) + "/" + protocol] = int(hostPort)
            
            # 处理网络配置
            networking_config = {}
            network = None
            if networks:
                for ntw in networks:
                    name = ntw["name"]
                    ipv4_address = ntw.get("ipv4_address", "")
                    tmp_ipdict = {"ipv4_address": ipv4_address} if ipv4_address else {}
                    networking_config[name] = tmp_ipdict
                network = networks[0]["name"]
            else:
                # 使用原网络配置
                old_networks = old_attrs['NetworkSettings']['Networks']
                if old_networks:
                    for net_name, net_config in old_networks.items():
                        network = net_name
                        break
            
            # 处理挂载配置
            new_volumes = {}
            if volumes:
                for item in volumes:
                    if item["type"] not in ["volume", "localdir"]:
                        return False, "挂载参数错误"
                    new_volumes[item["local_dir"]] = {
                        "bind": item["container_dir"],
                        "mode": item["mode"]
                    }
            else:
                # 使用原挂载配置
                old_mounts = old_attrs['Mounts']
                for mount in old_mounts:
                    if mount['Type'] == 'bind':
                        new_volumes[mount['Source']] = {
                            "bind": mount['Destination'],
                            "mode": 'rw' if mount['RW'] else 'ro'
                        }
            
            # 处理重启策略
            if restart_policy == "on-failure":
                restart_policy = {"Name": "on-failure", "MaximumRetryCount": 5}
            else:
                restart_policy = {"Name": restart_policy}
            
            # 获取其他配置（保持原配置）
            command = old_attrs['Config']['Cmd']
            entrypoint = old_attrs['Config']['Entrypoint']
            env = old_attrs['Config']['Env'] or []
            labels = old_attrs['Config']['Labels'] or {}
            tty = old_attrs['Config']['Tty']
            stdin_open = old_attrs['Config']['OpenStdin']
            privileged = old_attrs['HostConfig']['Privileged']
            auto_remove = old_attrs['HostConfig']['AutoRemove']
            publish_all_ports = old_attrs['HostConfig']['PublishAllPorts']
            
            # 停止原容器
            if old_status == 'running':
                try:
                    old_container.stop(timeout=10)
                    time.sleep(1)
                except Exception as e:
                    return False, f"停止原容器失败：{e}"
            
            # 删除原容器
            try:
                old_container.remove(force=True)
                time.sleep(1)
            except Exception as e:
                return False, f"删除原容器失败：{e}"
            
            # 创建新容器
            new_container = self.client.containers.create(
                name=old_name,
                image=old_image,
                restart_policy=restart_policy,
                command=command,
                entrypoint=entrypoint,
                environment=env,
                labels=labels,
                ports=new_ports,
                network=network,
                networking_config=networking_config if networking_config else None,
                volumes=new_volumes if new_volumes else None,
                cpu_quota=int(cpu_quota) or 0,
                cpu_shares=1024,
                mem_limit=mem_limit,
                publish_all_ports=publish_all_ports,
                detach=True,
                stdin_open=stdin_open,
                tty=tty,
                privileged=privileged,
                auto_remove=auto_remove
            )
            
            # 如果原容器是运行状态，启动新容器
            if old_status == 'running':
                try:
                    new_container.start()
                    time.sleep(1)
                    res = self.client.containers.get(new_container.id)
                    if res.attrs['State']['Status'] != "running":
                        return False, "容器已重建但启动失败，请检查配置"
                except Exception as e:
                    return False, f"容器已重建但启动失败：{e}"
            
            return True, "修改成功"
        except Exception as e:
            return False, f"修改失败：{e}"

    def logs(self, cont={}):
        """
        获取容器日志
        """
        try:
            id = cont.get('id', "")
            since = cont.get('since', None)
            tail = cont.get('tail', "all")
            timestamps = cont.get('timestamps', True)

            # 优化策略：如果指定了行数，优先按行数截取，忽略时间范围，以提升性能
            if tail != "all":
                try:
                    tail = int(tail)
                    since = None # 强制忽略 since
                except:
                    tail = "all"

            container = self.client.containers.get(id)
            
            # 优化：如果是按行数获取（通常行数不会太大，如 500/1000/2000），直接使用非流式读取
            # 这样可以避免建立流的开销和 Python 逐行循环的低效
            if isinstance(tail, int) and tail <= 5000:
                try:
                    # stream=False 返回 bytes
                    logs_bytes = container.logs(stdout=True, stderr=True, stream=False, timestamps=timestamps, tail=tail, since=since)
                    return True, logs_bytes.decode('utf-8', errors='ignore')
                except Exception:
                    # 如果直接读取失败，回退到流式读取
                    pass

            # 使用 stream=True 流式读取，避免一次性加载大文件导致内存溢出或阻塞
            # 即使 tail=500，Docker 守护进程也可能需要时间准备流
            log_generator = container.logs(stdout=True, stderr=True, stream=True, timestamps=timestamps, tail=tail, since=since)
            
            log_content = []
            max_lines = 5000 # 硬性限制最大返回行数，防止前端渲染卡死
            count = 0
            
            # 增加超时控制，防止后端长时间阻塞
            start_time = time.time()
            timeout_limit = 15 # 15秒超时
            
            try:
                for line in log_generator:
                    # 检查超时
                    if time.time() - start_time > timeout_limit:
                        log_content.append(f"\n[系统提示] 日志读取超时（{timeout_limit}s），仅显示部分内容...\n")
                        break
                    
                    # 解码
                    try:
                        line_str = line.decode('utf-8', errors='ignore')
                    except:
                        line_str = str(line)
                        
                    log_content.append(line_str)
                    count += 1
                    
                    if count >= max_lines:
                        log_content.append(f"\n[系统提示] 日志内容过长，已截断显示前 {max_lines} 行...\n")
                        break
            except Exception as e:
                # 流读取过程中可能发生错误（如容器突然停止）
                log_content.append(f"\n[系统提示] 日志流读取中断: {str(e)}\n")

            return True, "".join(log_content)
        except Exception as e:
            return False, f"获取日志失败：{e}"

    def stats(self, cont={}):
        """
        获取容器实时监控数据
        """
        try:
            id = cont.get('id',"")
            container = self.client.containers.get(id)
            # stream=False to get a single snapshot
            stats = container.stats(stream=False)
            return True, stats
        except Exception as e:
            return False, f"获取监控数据失败：{e}"

    def clear_logs(self, cont={}):
        """
        清空容器日志
        """
        try:
            id = cont.get('id', "")
            container = self.client.containers.get(id)
            log_path = container.attrs.get('LogPath', "")
            
            if not log_path:
                return False, "无法获取日志路径或未启用日志"
            
            # 简单判断 log_path 是否看起来像是有日志
            if log_path.endswith(".log"):
                log_dir = os.path.dirname(log_path)
                log_filename = os.path.basename(log_path)
                
                # 使用临时容器清空日志，兼容性最好
                try:
                    # 使用 sh -c "> path" 清空文件
                    cmd = f"sh -c '> /log_mount/{log_filename}'"
                    
                    self.client.containers.run(
                        "alpine", 
                        cmd,
                        volumes={log_dir: {'bind': '/log_mount', 'mode': 'rw'}},
                        remove=True
                    )
                    return True, "日志已清空"
                except Exception as e:
                    return False, f"清空失败: {e}"
            else:
                return False, "非文件日志，无法清空"

        except Exception as e:
            return False, f"操作失败：{e}"