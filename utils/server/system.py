#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | django-vue-lyadmin
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------

# ------------------------------
# 系统命令封装
# ------------------------------

import sys,os,platform
from django.conf import settings
from django.core.cache import cache

BASE_DIR = settings.BASE_DIR
plat = platform.system().lower()
if plat == 'windows':
    from . import windows as myos
else:
    from . import linux as myos


class system:

    isWindows = False

    def __init__(self):
        self.isWindows = self.isWindows()

    def isWindows(self):
        if plat == 'windows':
            return True
        return False

    def GetSystemAllInfo(self,isCache=False):
        """
        获取系统所有信息
        """
        data = {}
        data['mem'] = self.GetMemInfo()
        data['load_average'] = self.GetLoadAverage()
        data['network_stat'] = self.GetNetWork()
        data['diskio_stat'] = self.GetDiskIostat()
        data['cpu'] = self.GetCpuInfo(1)
        data['disk'] = self.GetDiskInfo()
        data['time'] = self.GetBootTime()
        data['system'] = self.GetSystemVersion()
        data['system_simple'] = self.GetSimpleSystemVersion()
        data['is_windows'] = self.isWindows
        return data

    def GetMemInfo(self):
        memInfo =  myos.GetMemInfo()
        return memInfo

    def GetLoadAverage(self):
        data = myos.GetLoadAverage()
        return data

    def GetNetWork(self):
        data = myos.GetNetWork()
        return data
    
    def GetDiskIostat(self):
        data = myos.get_disk_iostat()
        return data

    def GetCpuInfo(self,interval=1):
        data = myos.GetCpuInfo(interval)
        return data

    def GetBootTime(self):
        data = myos.GetBootTime()
        return data

    def GetDiskInfo(self):
        data = myos.GetDiskInfo()
        return data

    def GetSystemVersion(self):
        data = myos.GetSystemVersion()
        return data
    
    def GetSimpleSystemVersion(self):
        data = myos.GetSimpleSystemVersion()
        return data
    
    @classmethod
    def GetFirewallStatus(self):
        isok = myos.GetFirewallStatus()
        return isok
    
    @classmethod
    def GetFileLastNumsLines(cls,path,num=1000):
        data = myos.GetFileLastNumsLines(path=path,num=num)
        return data
    
    @classmethod
    def GetUidName(cls,file_path,uid=0):
        data = myos.GetUidName(file_path,uid)
        return data
    
    @classmethod
    def GetGroupidName(cls,file_path,gid=0):
        data = myos.GetGroupidName(file_path,gid=gid)
        return data
    
    @classmethod
    def RestartServer(cls):
        myos.RestartServer()

    @classmethod
    def RestartRuyi(cls):
        myos.RestartRuyi()
        
    @classmethod
    def ForceRemoveDir(cls,dir):
        myos.ForceRemoveDir(dir)
        
    @classmethod
    def GetFirewallRules(cls,param = {}):
        data = myos.GetFirewallRules(param=param)
        return data
    
    @classmethod
    def GetFirewallInfo(cls):
        data = myos.GetFirewallInfo()
        return data
    
    @classmethod
    def SetFirewallPing(cls,status):
        isok,msg = myos.SetFirewallPing(status=status)
        return isok,msg
    
    @classmethod
    def SetFirewallStatus(cls,status):
        isok,msg = myos.SetFirewallStatus(status=status)
        return isok,msg
    
    @classmethod
    def DelFirewallRule(cls,param):
        isok = myos.DelFirewallRule(param=param)
        return isok
    
    @classmethod
    def AddFirewallRule(cls,param):
        isok = myos.AddFirewallRule(param=param)
        return isok
    
    @classmethod
    def EditFirewallRule(cls,param):
        isok = myos.EditFirewallRule(param=param)
        return isok
    
    @classmethod
    def SetFirewallRuleStatus(cls,param):
        isok = myos.SetFirewallRuleStatus(param=param)
        return isok
    
    @classmethod
    def SetFirewallRuleAction(cls,param):
        isok = myos.SetFirewallRuleAction(param=param)
        return isok
    
    @classmethod
    def GetPortProxyRules(cls,param):
        data = myos.GetPortProxyRules(param=param)
        return data
    
    @classmethod
    def AddPortProxyRules(cls,param):
        isok,msg = myos.AddPortProxyRules(param=param)
        return isok,msg
    
    @classmethod
    def DelPortProxyRules(cls,param):
        isok,msg = myos.DelPortProxyRules(param=param)
        return isok,msg
    
    @classmethod
    def AddBinToPath(cls,param):
        isok= myos.AddBinToPath(param)
        return isok

    @classmethod
    def GetServiceStatus(cls, name: str) -> dict:
        if plat == 'windows':
            status_code = myos.get_service_status(name)
            state_map = {-1: '未安装', 0: '已停止', 1: '运行中', 2: '正在启动', 3: '正在停止', 4: '已暂停', 5: '继续等待', 6: '暂停等待'}
            return {
                'service_name': name,
                'is_active': status_code == 1,
                'is_enabled': None,
                'pid': None,
                'status_code': status_code,
                'status_text': state_map.get(status_code, '未知'),
            }
        else:
            return myos.get_service_status(name)

    @classmethod
    def SetServiceStatus(cls, name: str, action: str):
        if plat == 'windows':
            valid_actions = {'start', 'stop', 'restart', 'pause', 'continue'}
            if action == 'reload':
                return False, 'Windows 不支持 reload 操作，请使用 restart'
            if action == 'enable':
                return False, 'Windows 不支持 enable 操作，请使用 sc config 设置启动类型'
            if action == 'disable':
                return False, 'Windows 不支持 disable 操作，请使用 sc config 设置启动类型'
            if action not in valid_actions:
                return False, f'无效操作: {action}，可用操作: {", ".join(valid_actions)}'
            return myos.set_service_status(name, action)
        else:
            return myos.set_service_status(name, action)

    @classmethod
    def ListServices(cls, service_type: str = 'running') -> dict:
        return myos.list_services(service_type)

    @classmethod
    def GetServiceLogs(cls, name: str, lines: int = 50, since: str = '1 hour ago') -> dict:
        return myos.get_service_logs(name, lines, since)