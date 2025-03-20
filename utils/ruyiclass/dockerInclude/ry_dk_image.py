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
# Docker 镜像类
# ------------------------------
import os,json
from utils.common import GetLogsPath,WriteFile
import docker.errors
from asgiref.sync import sync_to_async
import asyncio
from utils.ruyiclass.dockerInclude.ry_dk_common import WriteLog,docker_client_low_level

class main:
    client=None#容器连接客户端
    log_path=os.path.join(GetLogsPath(),"docker","imagetmp.log")
    def __init__(self,client=None):
        self.client = client
        
    def set_tag(self,image_name,new_tag):
        """
        给镜像设置标签
        """
        try:
            image = self.client.images.get(image_name)
            # 设置标签
            new_image_name = f"{image_name}:{new_tag}"
            image.tag(new_image_name)
            return True,"设置成功"
        except docker.errors.ImageNotFound:
            return False,"镜像未找到"
        except docker.errors.APIError as e:
            return False,f"设置标签错误: {e}"
        
    def pull(self,cont={}):
        """
        拉取镜像
        """
        image_name=cont.get("image_name","")
        url=cont.get("url","")
        is_auth = cont.get("is_auth",None)
        username = cont.get("username",None)
        password = cont.get("password",None)
        if not image_name:return False,"请提供镜像名"
        try:
            if ':' not in image_name:
                image_name = f'{image_name}:latest'
            auth_config = {
                "username": username,
                "password": password,
                "registry":url if url else None
            }
            auth_config = auth_config if is_auth else None
            tag=cont.get("tag",None)
            if not hasattr(cont,"tag"):
                tag = image_name.split(":")[-1]
            if url and url != "docker.io":
                image_name = f"{url}/{image_name}"
            dkclient = docker_client_low_level()
            if not dkclient:False, f'无法获取docker连接'
            ret = dkclient.pull(
                repository=image_name,
                auth_config=auth_config,
                tag=tag,
                stream=True
            )
            WriteFile(self.log_path,"")
            WriteLog(self.log_path,ret,f'{image_name}镜像拉取')
            if ret:
                return True, f'【{image_name}】镜像拉取成功'
            else:
                return False, f'【{image_name}】镜像拉取失败'
        except docker.errors.ImageNotFound as e:
            if "pull access denied for" in str(e):
                return False,f"【{image_name}】拉取失败，需要dockerhub的账号密码"
            return False,f"拉取失败: {e}"

        except docker.errors.NotFound as e:
            if "not found: manifest unknown" in str(e):
                return False,f"【{image_name}】拉取失败，仓库无此镜像"
            return False, f"【{image_name}】拉取失败:{e}"
        except docker.errors.APIError as e:
            if "invalid tag format" in str(e):
                return False,f"【{image_name}】拉取失败, 镜像格式错误, 如: mysql:latest"
            return False,f"【{image_name}】拉取失败：{e}"
        
    @sync_to_async
    def pull_docker_image(self,client,image_name, auth_config, tag):
        
        return client.pull(
            repository=image_name,
            auth_config=auth_config,
            tag=tag,
            stream=True
        )
    
    @sync_to_async
    def get_lover_level_client(self):
        return docker_client_low_level()
        
    async def pull_ws(self,cont={}):
        """
        拉取镜像
        """
        _ws = cont.get("_ws",None)
        await _ws.send_message(message="开始执行拉取前环境检查,请等待...")
        image_name=cont.get("image_name","").lstrip("/")
        url=cont.get("url","")
        is_auth = cont.get("is_auth",None)
        username = cont.get("username",None)
        password = cont.get("password",None)
        
        if not image_name:
            await _ws.send_message(message="[error]请提供镜像名")
            return False,"请提供镜像名"
        try:
            if ':' not in image_name:
                image_name = f'{image_name}:latest'
            auth_config = {
                "username": username,
                "password": password,
                "registry":url if url else None
            }
            auth_config = auth_config if is_auth else None
            tag=cont.get("tag",None)
            if not hasattr(cont,"tag"):
                tag = image_name.split(":")[-1]
            if url and url != "docker.io":
                image_name = f"{url.lstrip("/")}/{image_name}"
            dkclient = await self.get_lover_level_client()
            if not dkclient:
                await _ws.send_message(message=f"[error]无法获取docker连接")
                return False,f"[error]无法获取docker连接"
            await _ws.send_message(message=f"{image_name} 正在拉取中...")
            ret = await self.pull_docker_image(
                dkclient,
                image_name,
                auth_config,
                tag
            )
            taskname = f"[{image_name}]镜像拉取任务"
            await _ws.send_message(message=f"已开始{taskname}")
            
            if not ret:
                await _ws.send_message(message=f'[{image_name}]镜像拉取失败')
                return False, f'[{image_name}]镜像拉取失败'
            max_iterations = 3000
            iteration_count = 0
            while iteration_count < max_iterations:
                try:
                    stout = next(ret)
                    iteration_count += 1
                    try:
                        stdout_json = json.loads(stout)
                        if 'status' in stdout_json:
                            output_str = f"{stdout_json['status']}"
                            await _ws.send_message(message=output_str)
                        
                        if 'stream' in stdout_json:
                            output_str = stdout_json['stream']
                            await _ws.send_message(message=output_str)
                    
                    except json.JSONDecodeError:
                        await _ws.send_message(message=f"解析输出错误，原内容: {stout}")
                    except Exception as e:
                        await _ws.send_message(message=f"输出异常: {e}")
                except StopIteration:
                    await _ws.send_message(message=f"{taskname} complete")
                    return True, f"[{image_name}]镜像拉取成功"
                except ValueError as e:
                    await _ws.send_message(message=f"ValueError occurred in {taskname}: {e}")
                    return False, f'[{image_name}]镜像拉取失败'
                except Exception as e:
                    await _ws.send_message(message=f"Error in {taskname}: {str(e)}")
                    return False, f'[{image_name}]镜像拉取失败'
                
        except docker.errors.ImageNotFound as e:
            if "pull access denied for" in str(e):
                await _ws.send_message(message=f"[{image_name}]拉取失败，需要dockerhub的账号密码")
                return False,f"[{image_name}]拉取失败，需要dockerhub的账号密码"
            return False,f"拉取失败: {e}"

        except docker.errors.NotFound as e:
            if "not found: manifest unknown" in str(e):
                await _ws.send_message(message=f"[{image_name}]拉取失败，仓库无此镜像")
                return False,f"[{image_name}]拉取失败，仓库无此镜像"
            await _ws.send_message(message=f"[{image_name}]拉取失败:{e}")
            return False, f"[{image_name}]拉取失败:{e}"
        except docker.errors.APIError as e:
            if "invalid tag format" in str(e):
                await _ws.send_message(message=f"[{image_name}]拉取失败, 镜像格式错误, 如: mysql:latest")
                return False,f"[{image_name}]拉取失败, 镜像格式错误, 如: mysql:latest"
            await _ws.send_message(message=f"[{image_name}]拉取失败：{e}")
            return False,f"[{image_name}]拉取失败：{e}"
      
    def load(self,cont):
        """
        导入镜像
        """
        try:
            path = cont.get('path',"")
            images = self.client.images
            with open(path,'rb') as f:
                images.load(f)
            return True,"镜像导入成功"
        except Exception as e:
            return False,f"导入镜像时出现错误: {e}"
    
    def remove(self,cont):
        """
        删除镜像
        """
        name = cont.get('name',"")
        force = cont.get('force',False)
        if not name:return False,"缺少镜像名称"
        try:
            self.client.images.remove(name,force=force)
            return True,"删除镜像成功"
        except docker.errors.ImageNotFound as e:
            return False,"删除失败，镜像不存在"
        except docker.errors.APIError as e:
            if "image is referenced in multiple repositories" in str(e):
                return False, "此镜像在多个仓库引用，请强制删除"
            if "using its referenced image" in str(e):
                return False, "镜像正在使用中，请先删除容器再执行删除镜像"
            return False,f"删除镜像失败：{e}"
    
    def prune(self,cont={}):
        """
        清除未使用镜像
        """
        dangling = cont.get('dangling',False)
        try:
            prune_result = self.client.images.prune(filters={'dangling': dangling})
            if not prune_result['ImagesDeleted']:
                return True, "没有无用镜像可清理"
            return True, "清除成功！"
        except Exception as e:
            return False,f"清除失败: {e}"
    
    def local_images_list(self,all=False):
        if not self.client:
            return []
        return self.client.images.list(all=all)
    
    def statistics(self,cont={}):
        """
        获取本地镜像统计
        """
        images = self.local_images_list()
        images_list = []
        for image in images:
            i_attrs = image.attrs
            short_id = image.short_id
            images_list.append({
                'id': short_id,
                'size': i_attrs['Size']
            })
        num = len(images_list)
        size = 0
        for i in images_list:
            size += i['size']
        data = {'nums':num,'size':size}
        return True,data