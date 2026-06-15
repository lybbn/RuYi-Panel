#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-17
# +-------------------------------------------------------------------
# | EditDate: 2025-02-17
# +-------------------------------------------------------------------

# ------------------------------
# docker 容器管理
# ------------------------------
import os
import psutil
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic,DeleteDir
from utils.jsonResponse import ErrorResponse,DetailResponse,SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.dockerClass import DockerClient, get_sha_id
from apps.sysdocker.models import RyDockerApps
from utils.ruyiclass.dockerInclude.ry_dk_square import main as dksquare

class RYDockerLimitManageView(CustomAPIView):
    """
    get:
    获取系统信息（用于容器最大限制）
    """
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
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
        return DetailResponse(data=data)

class RYDockerContainerManageView(CustomAPIView):
    """
    get:
    获取容器
    post:
    设置容器
    """
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        docker_client = DockerClient()
        page_obj,total_nums,limit,page_number = docker_client.get_local_containers_list(cont=reqData)
        return SuccessResponse(data=page_obj,total=total_nums,page=page_number,limit=limit)
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        docker_client = DockerClient()
        if action == "delete":
            name = reqData.get('name',"")
            if not name:return DetailResponse(msg="缺少参数")
            reqData['action_type']="container"
            isok,msg = docker_client.delete(reqData)
            if not isok:return ErrorResponse(msg=msg)
            # 同步清理容器广场的关联数据
            try:
                sq_ins = RyDockerApps.objects.filter(name=name).first()
                if sq_ins:
                    newsq = dksquare()
                    app_path = newsq.get_dkapp_path(cont={"appname":sq_ins.appname,"name":name})
                    sq_ins.delete()
                    DeleteDir(app_path)
            except Exception:
                pass
            RuyiAddOpLog(request,msg=f"【容器】- 删除容器：{name}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "add":
            name = reqData.get('name',"")
            reqData['action_type']="container"
            isok,msg = docker_client.add(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】- 添加容器：{name}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "set_status":
            status = reqData.get("status","")
            name = reqData.get('name',"")
            if not name:return DetailResponse(msg="缺少参数")
            reqData['action_type']="container"
            isok,msg = docker_client.set_status(cont=reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】- {status} => {name}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "get_logs":
            isok,data = docker_client.get_container_logs(cont=reqData)
            if not isok:return ErrorResponse(msg=data)
            return DetailResponse(data=data)
        elif action == "get_stats":
            isok,data = docker_client.get_container_stats(cont=reqData)
            if not isok:return ErrorResponse(msg=data)
            return DetailResponse(data=data)
        elif action == "clear_logs":
            isok,msg = docker_client.clear_container_logs(cont=reqData)
            if not isok:return ErrorResponse(msg=msg)
            return DetailResponse(msg=msg)
        elif action == "edit":
            id = reqData.get('id',"")
            name = reqData.get('name',"")
            if not id:return ErrorResponse(msg="缺少容器ID")
            reqData['action_type']="container"
            isok,msg = docker_client.edit(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】- 编辑容器：{name}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "upgrade":
            id = reqData.get('id',"")
            name = reqData.get('name',"")
            new_image = reqData.get('new_image',"")
            if not id:return ErrorResponse(msg="缺少容器ID")
            if not new_image:return ErrorResponse(msg="缺少新镜像名")
            reqData['action_type']="container"
            isok,msg = docker_client.upgrade(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】- 升级容器：{name} => {new_image}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "rename":
            id = reqData.get('id',"")
            name = reqData.get('name',"")
            new_name = reqData.get('new_name',"")
            if not id:return ErrorResponse(msg="缺少容器ID")
            if not new_name:return ErrorResponse(msg="缺少新容器名称")
            reqData['action_type']="container"
            isok,msg = docker_client.rename(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】- 重命名容器：{name} => {new_name}",module="dockermg")
            return DetailResponse(msg=msg)
        return ErrorResponse(msg="类型错误")

class RYDockerOverviewManageView(CustomAPIView):
    """
    get:
    获取Docker总览统计数据
    """
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
        docker_client = DockerClient()
        if not docker_client.client:
            return ErrorResponse(msg="Docker未连接，请检查Docker服务是否启动")
        
        if not docker_client.is_docker_running():
            return ErrorResponse(msg="Docker服务未运行，请启动Docker服务")
        
        try:
            containers = docker_client.local_containers_list(all=True)
            container_list = []
            running_containers = []
            running_count = 0
            stopped_count = 0
            paused_count = 0
            
            for container in containers:
                try:
                    c_attrs = container.attrs
                    c_status = container.status
                    
                    if c_status == "running":
                        running_count += 1
                        running_containers.append(container)
                    elif c_status == "paused":
                        paused_count += 1
                    else:
                        stopped_count += 1
                    
                    container_list.append({
                        'id': get_sha_id(container.short_id),
                        'name': container.name,
                        'status': c_status,
                        'image': c_attrs.get('Config', {}).get('Image', ''),
                        'created': c_attrs.get('Created', ''),
                        'ip': [net.get('IPAddress', '') for net in c_attrs.get('NetworkSettings', {}).get('Networks', {}).values()],
                        'ports': c_attrs.get('NetworkSettings', {}).get('Ports', {}),
                        'cpu_percent': 0,
                        'online_cpus': 0,
                        'mem_percent': 0,
                        'mem_usage': 0,
                        'mem_limit': 0,
                        'detail': c_attrs
                    })
                except:
                    continue
            
            stats_map = {}
            for rc in running_containers:
                try:
                    stats = rc.stats(stream=False)
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                    system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                    online_cpus = stats['cpu_stats'].get('online_cpus', len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [1])))
                    cpu_percent = round((cpu_delta / system_delta) * online_cpus * 100.0, 2) if system_delta > 0 and cpu_delta > 0 else 0
                    
                    mem_usage = stats['memory_stats'].get('usage', 0)
                    mem_limit = stats['memory_stats'].get('limit', 0)
                    mem_percent = round((mem_usage / mem_limit) * 100, 2) if mem_limit > 0 else 0
                    
                    stats_map[rc.name] = {
                        'cpu_percent': cpu_percent,
                        'online_cpus': online_cpus,
                        'mem_percent': mem_percent,
                        'mem_usage': mem_usage,
                        'mem_limit': mem_limit
                    }
                except:
                    continue
            
            for item in container_list:
                if item['name'] in stats_map:
                    s = stats_map[item['name']]
                    item['cpu_percent'] = s['cpu_percent']
                    item['online_cpus'] = s['online_cpus']
                    item['mem_percent'] = s['mem_percent']
                    item['mem_usage'] = s['mem_usage']
                    item['mem_limit'] = s['mem_limit']
            
            images = docker_client.local_images_list()
            images_count = len(images)
            images_size = sum(img.attrs.get('Size', 0) for img in images)
            
            networks = docker_client.client.networks.list()
            networks_count = len(networks)
            
            volumes = docker_client.client.volumes.list()
            volumes_count = len(volumes)
            volumes_size = 0
            try:
                df_info = docker_client.client.df()
                for vol_info in df_info.get('Volumes', []):
                    usage = vol_info.get('UsageData', {})
                    if usage:
                        volumes_size += usage.get('Size', 0)
            except Exception:
                for vol in volumes:
                    usage = vol.attrs.get('UsageData', {})
                    if usage:
                        volumes_size += usage.get('Size', 0)
            
            repos_count = 0
            try:
                from apps.sysdocker.models import RyDockerRepo
                repos_count = RyDockerRepo.objects.count()
            except:
                pass
            
            docker_info = {}
            try:
                info = docker_client.client.info()
                docker_info = {
                    'server_version': info.get('ServerVersion', ''),
                    'storage_driver': info.get('Driver', ''),
                    'containers_total': info.get('Containers', 0),
                    'containers_running': info.get('ContainersRunning', 0),
                    'containers_stopped': info.get('ContainersStopped', 0),
                    'containers_paused': info.get('ContainersPaused', 0),
                    'images_count': info.get('Images', 0),
                    'os': info.get('OperatingSystem', ''),
                    'architecture': info.get('Architecture', ''),
                    'cpu_count': info.get('NCPU', 0),
                    'total_memory': info.get('MemTotal', 0),
                }
            except Exception as e:
                import logging
                import platform
                logger = logging.getLogger('django')
                logger.error(f"获取Docker信息失败: {str(e)}")
                try:
                    version_info = docker_client.client.version()
                    docker_info['server_version'] = version_info.get('Version', '')
                    docker_info['os'] = version_info.get('Os', '')
                    docker_info['architecture'] = version_info.get('Arch', '')
                except:
                    pass
                docker_info.setdefault('os', platform.system())
                docker_info.setdefault('architecture', platform.machine())
                docker_info.setdefault('cpu_count', psutil.cpu_count(logical=True))
                docker_info.setdefault('total_memory', psutil.virtual_memory().total)
            
            return DetailResponse(data={
                'containers': container_list,
                'containers_count': len(container_list),
                'containers_running': running_count,
                'containers_stopped': stopped_count,
                'containers_paused': paused_count,
                'images_count': images_count,
                'images_size': images_size,
                'networks_count': networks_count,
                'volumes_count': volumes_count,
                'volumes_size': volumes_size,
                'repos_count': repos_count,
                'docker_info': docker_info
            })
        except Exception as e:
            return ErrorResponse(msg=f"获取总览数据失败: {str(e)}")