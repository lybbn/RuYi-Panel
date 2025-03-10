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