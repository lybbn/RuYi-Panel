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
# Docker 类
# ------------------------------
import os
import json
import docker
from datetime import datetime
from utils.common import current_os,ReadFile,WriteFile,GetRootPath,GetInstallPath
import math
import utils.ruyiclass.dockerInclude.ry_dk_image as dk_image
import utils.ruyiclass.dockerInclude.ry_dk_network as dk_network
import utils.ruyiclass.dockerInclude.ry_dk_container as dk_container
import utils.ruyiclass.dockerInclude.ry_dk_volumes as dk_volumes
from apps.syslogs.logutil import asyncRuyiAddOpLog
from apps.sysdocker.models import RyDockerRepo

def get_sha_id(shastr):
    if ":" in shastr:
        id_part = shastr.split(":")[1]
        return id_part
    return shastr

def calculate_total_pages(total_nums, limit):
    return math.ceil(int(total_nums) / int(limit))

def get_docker_path_info():
    ry_root_path = GetRootPath()
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,'docker')
    install_path = root_path+'/docker'
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'windows_abspath_docker_bin':os.path.join(install_abspath_path,'docker','docker.exe'),
        'windows_abspath_dockerd_bin':os.path.join(install_abspath_path,'docker','dockerd.exe'),
        'linux_docker_bin':"/usr/bin/docker",
        'windows_daemon_conf':os.path.join(install_abspath_path,'daemon.json'),
        'linux_daemon_conf':"/etc/docker/daemon.json",
        'data_root':ry_root_path+"/data/docker",
    }

class DockerClient:
    is_windows=True
    docker_url="unix:///var/run/docker.sock"
    docker_path_info={}
    def __init__(self,conn=True):
        self.is_windows = True if current_os == 'windows' else False
        self.docker_path_info = get_docker_path_info()
        if conn:
            try:
                # 尝试连接到 Docker 服务
                # self.client = docker.from_env()
                self.client = docker.DockerClient(base_url=self.docker_url)
            except:
                self.client = None
            
    def is_docker_running(self,close_conn=False):
        """
        检查 Docker 是否正在运行
        """
        if self.client:
            try:
                self.client.ping()  # 发送 ping 命令，检查 Docker 是否在线
                if close_conn:self.client.close()
                return True
            except:
                return False
        else:
            return False
        
    def get_daemon_config(self):
        data={}
        if self.is_windows:
            conf_path = self.docker_path_info['windows_daemon_conf']
        else:
            conf_path = self.docker_path_info['linux_daemon_conf']
        try:
            if os.path.exists(conf_path):
                conf = json.loads(ReadFile(conf_path))
                data=conf
        except:
            pass
        return data
    
    def get_registry_mirrors(self):
        """
        获取镜像加速信息
        """
        data={
            "registry_mirrors": []
        }
        try:
            conf = self.get_daemon_config()
            if "registry-mirrors" not in conf:
                mirrors = []
            else:
                mirrors = conf['registry-mirrors']
                
        except:
            mirrors = []
        data['registry_mirrors']=mirrors
        return data
    
    def add_insecure_registries(self,cont={}):
        """
        添加授信
        """
        url = cont.get('url',None)
        if not url:return False,"缺少url"
        try:
            conf = self.get_daemon_config()
            if "insecure-registries" not in conf:
                irs = []
            else:
                irs = conf['insecure-registries']
            irs.append(url)
            conf['insecure-registries'] = irs
            self.save_daemon_config({'content':conf})
            return True,"添加成功，重启docker生效"
        except Exception as e:
            return False,e
    
    def save_daemon_config(self,cont):
        """
        保存配置
        """
        content = cont.get('content',{})
        if self.is_windows:
            conf_path = self.docker_path_info['windows_daemon_conf']
        else:
            conf_path = self.docker_path_info['linux_daemon_conf']
        if isinstance(content,dict):
            content = json.dumps(content)
        WriteFile(conf_path,content=content)
        return True
    
    def close(self):
        if self.client:self.client.close()
    
    def login_test(self, repo_url, username, password):
        """
        仓库登录测试
        params: repo_url 仓库地址，加上协议
        """
        try:
            res = self.client.login(
                registry=repo_url,
                username=username,
                password=password,
                reauth=False
            )
            return True,str(res)
        except Exception as e:
            if "unauthorized: incorrect username or password" in str(e):
                return False,f"账号密码错误：{e}"
            return False,f"登录失败：{e}"
    
    def local_images_list(self,all=False):
        if not self.client:
            return []
        return self.client.images.list(all=all)
    
    def local_containers_list(self,all=True):
        if not self.client:
            return []
        return self.client.containers.list(all=all)
    
    def is_image_in_use(self,container_list=[],image_id=None):
        """
        判断某个镜像id是否被其他容器使用
        """
        # 获取所有容器（包括停止的容器）
        if not container_list:
            container_list = self.local_containers_list()
        for container in container_list:
            # 检查容器的镜像 ID 是否与传入的镜像 ID 匹配
            if container.image.id == image_id:
                return True
        return False
    
    def paginated_data(self,data=[],page=1,limit=10):
        total_nums = len(data)
        total_pages = calculate_total_pages(total_nums,limit)
        if page<1:page=1
        if page>total_pages:page=total_pages
        # 根据分页参数对结果进行切片
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        p_data = data[start_idx:end_idx]
        return p_data
    
    def get_local_images_list(self,cont):
        search = cont.get('search',None)
        is_simple = cont.get('is_simple',"")#取所有本地镜像，且不分页
        used = str(cont.get('used',""))
        page_number = int(cont.get('page',1))
        limit = int(cont.get('limit',10))
        images = self.local_images_list()
        images_list = []
        if str(is_simple) == "1":
            for image in images:
                i_attrs = image.attrs
                tags = i_attrs['RepoTags']
                c_name =tags[0] if tags and len(tags)>0 else ""
                short_id = image.short_id
                images_list.append({
                    'id': get_sha_id(short_id),
                    'name':c_name
                })
            total_nums = len(images_list)
            return images_list,total_nums,total_nums,1
        container_list = self.local_containers_list()
        for image in images:
            i_attrs = image.attrs
            tags = i_attrs['RepoTags']
            c_name =tags[0] if tags and len(tags)>0 else ""
            short_id = image.short_id
            l_data = {
                'id': get_sha_id(short_id),#i_attrs.id
                'used': "1" if self.is_image_in_use(container_list=container_list,image_id=image.id) else "0",
                'name':c_name,
                'tags': tags,
                'size': i_attrs['Size'],
                'created': i_attrs['Created'],
                'work_dir': i_attrs['GraphDriver']['Data']['WorkDir'],
                'hostname': i_attrs['Config']['Hostname']
            }
            if search:
                search = search.strip().lower()
                if not search in c_name.lower() and not search in short_id:
                    continue
            if used:
                if not l_data['used'] == used:continue
            images_list.append(l_data)
        try:
            if images_list:images_list = sorted(images_list, key=lambda x: datetime.strptime(x['created'], '%Y-%m-%dT%H:%M:%SZ'),reverse=True)
        except:
            pass
        total_nums = len(images_list)
        paginated_data = self.paginated_data(images_list,page=page_number,limit=limit)
        return paginated_data,total_nums,limit,page_number
    
    def get_local_containers_list(self,cont):
        all = cont.get('all',True)#获取所有容器（包含已停止的）
        status = cont.get('status',None)
        search = cont.get('search',None)
        page_number = int(cont.get('page',1))
        limit = int(cont.get('limit',10))
        containers = self.local_containers_list(all=all)
        container_list = []
        for container in containers:
            c_status=container.status
            c_name = container.name
            c_attrs = container.attrs
            l_data = {
                'id': get_sha_id(container.short_id),
                'name': c_name,
                'status': c_status,
                "image": c_attrs["Config"]["Image"],
                "created": c_attrs["Created"],
                "ip": dk_container.main().get_container_ip(c_attrs["NetworkSettings"]['Networks']),
                "ports": c_attrs["NetworkSettings"]["Ports"],
                "detail": c_attrs,
                "cpu_usage": "",
                'is_appstore':False
            }
            if status and not c_status == status:
                continue
            if search and not search.lower() in c_name.lower():
                continue
            container_list.append(l_data)
        total_nums = len(container_list)
        paginated_data = self.paginated_data(container_list,page=page_number,limit=limit)
        return paginated_data,total_nums,limit,page_number
    
    def get_local_network_list(self,cont):
        networklist = dk_network.main(client=self.client).local_network_list()
        search = cont.get('search',None)
        page_number = int(cont.get('page',1))
        limit = int(cont.get('limit',10))
        data_list = []
        system_networks = ['none', 'bridge', 'host','ruyi-network']
        for dl in networklist:
            c_attrs = dl.attrs
            c_name = str(c_attrs["Name"])
            subnet = ""
            gateway = ""
            if c_attrs["IPAM"]["Config"]:
                if "Subnet" in c_attrs["IPAM"]["Config"][0]:
                    subnet = c_attrs["IPAM"]["Config"][0]["Subnet"]
                if "Gateway" in c_attrs["IPAM"]["Config"][0]:
                    gateway = c_attrs["IPAM"]["Config"][0]["Gateway"]
            l_data = {
                'id': get_sha_id(c_attrs['Id']),
                'name': c_name,
                'created': c_attrs['Created'],
                "driver":c_attrs["Driver"],
                "subnet":subnet,
                "gateway": gateway,
                "labels": c_attrs["Labels"],
                "system":c_name in system_networks
            }
            if search:
                search = search.strip().lower()
                if search not in c_name.lower():
                    continue
            data_list.append(l_data)
        try:
            if data_list:data_list = sorted(data_list, key=lambda x:datetime.fromisoformat(x['created']),reverse=True)
        except:
            pass
        total_nums = len(data_list)
        paginated_data = self.paginated_data(data_list,page=page_number,limit=limit)
        return paginated_data,total_nums,limit,page_number
    
    def get_volumes_list(self,cont):
        volumes_ins = dk_volumes.main(client=self.client)
        volumeslist = volumes_ins.get_volumes_list()
        status = cont.get('status',None)
        search = cont.get('search',None)
        page_number = int(cont.get('page',1))
        limit = int(cont.get('limit',10))
        container_list = self.local_containers_list()
        data_list = []
        for dl in volumeslist:
            c_attrs = dl.attrs
            c_name = dl.name
            l_data = {
                'name': c_name,
                'created': c_attrs['CreatedAt'],
                "driver":c_attrs["Driver"],
                "mountpoint":c_attrs["Mountpoint"],
                "scope":c_attrs["Scope"],
                "labels": c_attrs["Labels"],
                "usage_data":c_attrs.get('UsageData',""),
                "detail":c_attrs
            }
            l_data = volumes_ins.get_container_name(l_data,container_list)
            if search:
                search = search.strip().lower()
                if search not in c_name.lower():
                    continue
            data_list.append(l_data)
        try:
            if data_list:data_list = sorted(data_list, key=lambda x:datetime.fromisoformat(x['created']),reverse=True)
        except:
            pass
        total_nums = len(data_list)
        paginated_data = self.paginated_data(data_list,page=page_number,limit=limit)
        return paginated_data,total_nums,limit,page_number
    
    def delete(self,cont={}):
        """
        删除镜像、容器、网络、存储、仓库
        """
        action_type = cont.get("action_type",None)
        if not self.client:return False,"连接容器失败"
        res=False
        msg="类型错误"
        if action_type == "image":
            res,msg = dk_image.main(client=self.client).remove(cont)
        elif action_type == "network":
            res,msg = dk_network.main(client=self.client).remove(cont)
        elif action_type == "container":
            res,msg = dk_container.main(client=self.client).remove(cont)
        elif action_type == "volumes":
            res,msg = dk_volumes.main(client=self.client).remove(cont)
        return res,msg
    
    def prune(self,cont={}):
        """
        清除未使用的镜像、网络
        """
        action_type = cont.get("action_type",None)
        if not self.client:return False,"连接容器失败"
        res=False
        msg="类型错误"
        if action_type == "network":
            res,msg = dk_network.main(client=self.client).prune()
        elif action_type == "volumes":
            res,msg = dk_volumes.main(client=self.client).prune()
        return res,msg
    
    def add(self,cont={}):
        """
        添加镜像、容器、网络、存储卷、仓库
        """
        action_type = cont.get("action_type",None)
        if not self.client:return False,"连接容器失败"
        res=False
        msg="类型错误"
        if action_type == "network":
            res,msg = dk_network.main(client=self.client).add(cont)
        elif action_type == "container":
            res,msg = dk_container.main(client=self.client).add(cont)
        elif action_type == "volumes":
            res,msg = dk_volumes.main(client=self.client).add(cont)
        return res,msg
    
    def set_status(self,cont={}):
        """
        设置容器状态
        """
        res=False
        msg="类型错误"
        action_type = cont.get("action_type",None)
        if not self.client:return False,"连接容器失败"
        if action_type == "container":
            res,msg = dk_container.main(client=self.client).set_status(cont=cont)
        return res,msg
    
    def get_network_gateway(self,name):
        """
        获取网络网关
        """
        info = dk_network.main(client=self.client).get_network_info(name)
        if not info:return ""
        return info["IPAM"]["Config"][0]["Gateway"]

    async def pull_ws(self,cont):
        """
        拉取镜像
        """
        wsinstace = cont.get("_ws",None)
        repo_id = cont.get("repo_id",None)
        method = cont.get("method",None)
        is_auth = cont.get("is_auth",False)
        if method == "repo":
            repo_ins =await RyDockerRepo.objects.aget(id=repo_id)
            if not repo_ins:
                return False,"无此仓库"
            cont['username'] = repo_ins.username
            cont['password'] = repo_ins.password
            cont['url'] = repo_ins.url
        else:
            cont['url'] = ""
        res,msg = await dk_image.main().pull_ws(cont)
        await asyncRuyiAddOpLog(wsinstace,msg=f"【容器】-【镜像】=> {msg}",status=res,module="dockermg")
        return res,msg