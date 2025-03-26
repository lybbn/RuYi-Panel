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
# Docker 网络类
# ------------------------------

from utils.common import current_os
import docker.types

class main:
    is_windows=True
    client=None#容器连接客户端
    driver_list=["bridge","macvlan","ipvlan","overlay"] #还有none,host
    system_networks = {}
    linux_system_networks = {'none', 'bridge', 'host','ruyi-network'}
    # windows_system_networks = {'none', 'nat', 'Default Switch','ruyi-network'}
    windows_system_networks = {'none', 'bridge', 'host','ruyi-network'}
    def __init__(self,client=None):
        self.is_windows = True if current_os == 'windows' else False
        if self.is_windows:
            self.system_networks = self.windows_system_networks
        else:
            self.system_networks = self.linux_system_networks
        self.client = client
        
    def format_to_dict(self,input_str):
        """
        转为dict字典
        params: input_str 格式"key1=value1\nkey2=value2"
        return {'key1':'value1','key2':'value2'}
        """
        if not input_str:return {}
        return dict(line.split('=') for line in input_str.split('\n'))
        
    def add(self,cont={}):
        """
        添加网络
        """
        try:
            enIpv4 = cont.get('enIpv4',False)
            name = cont.get('name',"")
            driver = cont.get('driver',"bridge")
            labels = cont.get('labels',"")
            if driver not in self.driver_list:return False,"模式错误"
            if enIpv4:
                subnet = cont.get('subnet','')
                if not subnet:return False,"请填写子网"
                gateway = cont.get('gateway','')
                iprange = cont.get('iprange','')
                ipam_pool = docker.types.IPAMPool(
                    subnet=subnet,
                    gateway=gateway,
                    iprange=iprange
                )
                ipam_config = docker.types.IPAMConfig(
                    pool_configs=[ipam_pool]
                )
            else:
                ipam_config = None
            self.client.networks.create(
                name=name,
                driver=driver,
                ipam=ipam_config,
                labels=self.format_to_dict(labels)
            )
            return True,"添加网络成功"
        except Exception as e:
            if "operation is not permitted on predefined" in str(e):
                return False,f"【{name}】与现有网络重名，请更换"
            return False,f"添加失败：{e}"
        
    def remove(self,cont={}):
        """
        删除网络
        """
        id = cont.get('id',"")
        try:
            networks = self.client.networks.get(id)
            attrs = networks.attrs
            if attrs['Name'] in ["bridge","none","host"]:
                return False, "不能删除系统默认网络"
            networks.remove()
            return True, "删除成功！"
        except Exception as e:
            if " has active endpoints" in str(e):
                return False,"无法删除正在使用中的网络"
            return False,f"删除失败: {e}"
        
    def prune(self,cont={}):
        """
        清除未使用网络
        """
        try:
            networks = self.local_network_list()
            networks_to_remove = []
            for net in networks:
                # 检查网络是否未被使用，且不是系统网络
                if net.name not in self.system_networks and len(net.containers) == 0:
                    networks_to_remove.append(net)

            # 删除筛选出的网络
            for network in networks_to_remove:
                network.remove()
            # self.client.networks.prune()
            return True, "清除成功！"
        except Exception as e:
            return False,f"清除失败: {e}"
    
    def get_network_info(self,name):
        """
        获取指定网络名信息
        """
        try:
            network = self.client.networks.get(name)
            return network.attrs
        except Exception as e:
            return {}
    
    def local_network_list(self):
        if not self.client:
            return []
        return self.client.networks.list()