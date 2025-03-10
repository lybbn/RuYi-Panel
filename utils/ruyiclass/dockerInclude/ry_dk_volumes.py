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
# Docker 存储卷类
# ------------------------------

from utils.ruyiclass.dockerInclude.ry_dk_common import format_to_dict
import docker.errors

class main:
    client=None#容器连接客户端
    def __init__(self,client=None):
        self.client = client
        
    def get_container_name(self, volume_data, container_list):
        '''
        取存储卷对应使用的容器列表(一个存储卷多个容器可共享使用)
        '''
        temp_data = volume_data
        if 'containers' not in temp_data:
            temp_data['containers'] = []
        for container in container_list:
            c_attrs = container.attrs
            if not c_attrs['Mounts']:
                continue
            for mount in c_attrs['Mounts']:
                if temp_data['name'] == mount.get('Name',''):
                    temp_data['containers'].append(c_attrs['Name'].replace("/",""))
        temp_data['containers'] = list(set(temp_data['containers']))
        return temp_data
        
    def add(self,cont={}):
        """
        添加存储卷
        """
        try:
            name = cont.get('name',"")
            if not name or len(name)<4:return False,"名称至少4个字符"
            driver = cont.get('driver',"local")
            driver_opts = format_to_dict(cont.get('driver_opts',None))
            labels = format_to_dict(cont.get('labels',None))
            if not driver_opts:driver_opts = None
            if not labels:labels = None
            
            self.client.volumes.create(
                name=name,
                driver=driver,
                driver_opts=driver_opts,
                labels=labels
            )
            return True,"添加存储卷成功"
        except docker.errors.APIError as e:
            if "volume name is too short, names should be at least two alphanumeric characters" in str(e):
                return False, "存储卷名至少2个字符"
            if "volume name" in str(e):
                return False, "存储卷名已存在"
            return False, f"添加失败！ {e}"
        except Exception as e:
            if "driver_opts must be a dictionary" in str(e):
                return False, "选项和标签必须是键值对，如：key=value"
            return False,f"添加失败：{e}"
        
    def remove(self,cont={}):
        """
        删除存储卷
        """
        id = cont.get('id',"")
        try:
            volumes = self.client.volumes.get(id)
            volumes.remove()
            return True, "删除成功！"
        except Exception as e:
            if "volume is in use" in str(e):
                return False, "无法删除，正在使用中的存储卷"
            if "no such volume" in str(e):
                return False, "存储卷不存在"
            return False,f"删除失败: {e}"
        
    def prune(self,cont={}):
        """
        清除未使用的存储卷
        """
        try:
            self.client.volumes.prune()
            return True, "清除成功！"
        except Exception as e:
            return False,f"清除失败: {e}"
    
    def get_volumes_list(self):
        if not self.client:
            return []
        return self.client.volumes.list()