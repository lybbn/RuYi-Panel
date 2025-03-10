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