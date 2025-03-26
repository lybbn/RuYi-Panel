#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-03-11
# +-------------------------------------------------------------------
# | EditDate: 2025-03-11
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Go web 类
# ------------------------------
import psutil,time,datetime
import re,os,subprocess
from utils.common import current_os,ReadFile,RunCommand,GetLogsPath,WriteFile,ast_convert,DeleteFile
from django.conf import settings
from apps.system.models import Sites
from utils.server.system import system

class GoClient:
    is_windows=True
    siteName = None
    sitePath = None
    
    go_bin_path = "/ruyi/server/go/rygo/bin"
    confBasePath = None
    scriptsPath=None
    log_base_path = None
    project_config = None
    
    def __init__(self, *args, **kwargs):
        self.is_windows = True if current_os == 'windows' else False
        self.siteName = kwargs.get('siteName', '')
        self.sitePath = kwargs.get('sitePath', '').replace("\\","/")
        self.project_config = kwargs.get('cont', '')
        self.confBasePath = settings.RUYI_VHOST_PATH.replace("\\","/") +"/go_project/"+self.siteName
        self.scriptsPath = self.confBasePath + "/scripts"
        self.log_base_path = self.sitePath+"/logs"
        if not os.path.exists(self.confBasePath): os.makedirs(self.confBasePath, mode=0o755)
        if not os.path.exists(self.log_base_path): os.makedirs(self.log_base_path, mode=0o755)
        
    def get_conf_path(self):
        """
        取配置路径
        """
        data =  {
            "confBasePath":self.confBasePath,
            "scriptsPath":self.scriptsPath,
            'log_base_path':self.log_base_path,
            'log_command':self.log_base_path+'/command.log',
            'command_pid':self.sitePath+f'/{self.siteName}.pid',
            'go_bin_path':self.go_bin_path
        }
        return data
    
    def create_site(self):
        """
        创建站点
        """
        try:
            cont = self.project_config
            # 创建网站根目录
            if not os.path.exists(self.sitePath):
                try:
                    os.makedirs(self.sitePath)
                except Exception as e:
                    errmsg = '创建根目录失败：%s'%e
                    raise Exception(errmsg)
            port = cont.get("port","")
            start_command = cont.get("start_command","")
            bin = cont.get("bin","")
            if not start_command:raise Exception("缺少启动命令")
            if not bin:raise Exception("缺少项目可执行文件")
            #创建配置文件
            self.create_site_config()
            #放通防火墙
            allowport = cont.get("allowport",False)
            if allowport:
                system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':port,'handle':'accept'})
            #正在启动
            isstart = self.start_site()
            if not isstart:
                raise Exception("启动失败")
            return True,"ok"
        except Exception as e:
            return False,e
    
    def get_project_pids(self,pid):
        """
        取项目pid列表
        """
        try:
            if not isinstance(pid,int):
                pid = int(pid)
            p = psutil.Process(pid)
            child_pids = [c.pid for c in p.children(recursive=True) if c.status() != psutil.STATUS_ZOMBIE]
            return [p.pid] + child_pids
        except:
            return []
    
    def get_project_pid_process(self):
        """
        通过进程列表筛选项目信息获取进程pid
        """
        cont = self.project_config
        start_method = "command"
        pids = []
        try:
            for i in psutil.process_iter(['pid', 'exe', 'cmdline']):
                try:
                    if i.status() == psutil.STATUS_ZOMBIE:continue
                    cmdlines = " ".join(i.cmdline())
                    start_command = cont.get("start_command","")
                    if start_command in cmdlines:
                        pids.append(i.pid)
                except:
                    pass
        except:
            return None
        if pids:return min(pids)
        return None
        
    def is_project_running(self,is_simple=False):
        """
        项目是否运行，运行则返回pid，未运行则返回空数组或None,或False
        is_simple:简单通过pid文件判断，不深入判断，如为False则进一步通过进程列表筛选，返回进程pid
        """
        cont = self.project_config
        start_method = "command"
        conf = self.get_conf_path()
        pid_path = conf[f'{start_method}_pid']
        pid = ReadFile(pid_path)
        if is_simple:
            if not pid:
                return False
            try:
                pid = int(pid)
                psutil.Process(pid)
                return pid
            except:
                return False
        else:
            try:
                pid = int(pid)
                psutil.Process(pid)
                return pid
            except:
                pid = self.get_project_pid_process()
            if not pid:
                return False
            pids = self.get_project_pids(pid=pid)
            if not pids:
                return []
            return min(pids)
        
    def get_preexec_fn(self,user):
        import pwd
        pid = pwd.getpwnam(user)
        uid = pid.pw_uid
        gid = pid.pw_gid

        def _preexec_fn():
            os.setgid(gid)
            os.setuid(uid)
        return _preexec_fn
    
    def ExecCommand(self,cmdstr,cwd=None,env=None,user=None,shell=True):
        """
        运行命令（保持子进程独立，不受父进程退出后而被终止）
        """
        if not self.is_windows:
            preexec_fn = lambda: os.setuid(0)#默认root的uid
            if user:preexec_fn = self.get_preexec_fn(user)
            subprocess.Popen(cmdstr,cwd=cwd,bufsize=4096,stdin=subprocess.PIPE,stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=shell,preexec_fn=preexec_fn, env=env)
        else:
            subprocess.Popen(cmdstr,cwd=cwd,bufsize=4096,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=shell,env=env,creationflags=subprocess.DETACHED_PROCESS)
    
    def edit_site(self,is_need_time=True):
        """
        修改站点
        """
        self.create_run_script()
        cont = self.project_config
        #放通防火墙
        port = cont.get("port","")
        allowport = cont.get("allowport",False)
        if allowport:
            system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':port,'handle':'accept'})
        self.start_site()
        return True
    
    def start_site(self):
        """
        启动站点
        """
        if not self.is_project_running():
            cont = self.project_config
            conf = self.get_conf_path()
            start_method = "command"
            script_path = self.get_run_script_path()
            if not os.path.exists(script_path):
                self.create_run_script()
            method_pid = f"{start_method}_pid"
            sitepid = conf[method_pid]
            if os.path.exists(sitepid):
                os.remove(sitepid)
            start_user = cont["start_user"]
            env = None
            if not self.is_windows:
                RunCommand(f"chown -R {start_user}:{start_user} {self.sitePath}")
                os.chmod(script_path, 0o755)
                os.chmod(self.sitePath, 0o755)
                from pwd import getpwnam
                start_user_info = getpwnam(start_user)
                start_user_uid = start_user_info.pw_uid
                start_user_group_uid = start_user_info.pw_gid
                os.chown(script_path, start_user_uid, start_user_group_uid)
                #设置环境变量
                env = os.environ.copy()
                env['PATH'] = conf['go_bin_path'] + ':' + env['PATH']  # 把虚拟环境的 bin 路径加入 PATH

            self.ExecCommand([script_path],cwd=self.sitePath,user=start_user, env=env)
            time.sleep(1)

            if self.is_project_running():
                return True
            return False
            
        return True
    
    def stop_site(self):
        """
        停止站点（强制关闭）
        """
        if not self.is_project_running():
            return True
        cont = self.project_config
        conf = self.get_conf_path()
        start_method = "command"
        method_pid = f"{start_method}_pid"
        sitepid = conf[method_pid]
        pid = ReadFile(sitepid)
        is_force = False
        if not pid:
            pid = self.get_project_pid_process()
            if not pid:return True
            is_force = True
        pids = self.get_project_pids(pid=pid)
        if not pids:
            if not is_force:
                pid = self.get_project_pid_process()
                if not pid:return True
                pids = self.get_project_pids(pid=pid)
                if not pids:return True
            else:
                return True
        self.kill_pids(pids=pids)
        if os.path.exists(sitepid):
            os.remove(sitepid)
        return True
    
    def restart_site(self):
        """
        重启站点
        """
        self.stop_site()
        res = self.start_site()
        return res
    
    def delete_site(self):
        """
        删除站点
        """
        site_ins = Sites.objects.filter(name=self.siteName,type=1).first()
        if not site_ins:return False,"未找到站点"
        #删除脚本
        system.ForceRemoveDir(self.confBasePath)
        #删除日志
        conf = self.get_conf_path()
        log_command = conf['log_command']
        system.ForceRemoveDir(log_command)
        DeleteFile(conf['command_pid'],empty_tips=False)
        site_ins.delete()
        return True,"ok"
    
    def kill_pids(self,pids=None):
        """
        结束进程列表
        """
        if not pids:
            return True
        for pid in pids:
            try:
                p = psutil.Process(pid)
                p.terminate()
            except:
                pass
        time.sleep(0.2)
        for pid in pids:
            try:
                p = psutil.Process(pid)
                p.kill()
            except:
                pass
        return True
    
    def format_create_time(self,timestamp):
        return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    def get_process_pids_resources(self,thread_pids):
        """
        获取指定线程或进程的总 CPU 占用和内存使用情况。
        :param thread_pids: 线程或进程的 PID 列表
        :return: 返回总的 CPU 占用百分比和内存使用情况（单位：MB）
        """
        total_cpu = 0
        total_memory = 0
        # 获取系统的总内存信息
        total_system_memory = psutil.virtual_memory().total
        total_threads = 0

        for thread_pid in thread_pids:
            try:
                thread_process = psutil.Process(thread_pid)
                # 获取该进程的 CPU 占用百分比，指定一个时间间隔来计算
                total_cpu += thread_process.cpu_percent(interval=0.1)
                # 获取该进程的内存使用情况 (RSS: Resident Set Size，实际使用的物理内存)
                process_memory = thread_process.memory_info().rss
                total_memory += process_memory
                total_threads += thread_process.num_threads()
            except:
                continue
        memory_usage_percent = (total_memory / total_system_memory) * 100
        # 输出总的 CPU 占用和内存使用
        return total_cpu,memory_usage_percent,total_threads,total_memory / 1024 / 1024  # 返回内存使用量单位是 MB
    
    def get_loadstatus(self):
        """
        获取项目负载状态
        @author lybbn <2024-12-03>
        """
        data = {
            'cpu_p':"",
            'mem_p':"",
            'mem_used':"",
            'create_time':"",
            'cmdline':"",
            'threads':"",
            'pids':[],
            'fpid':"",
            'fpid_name':"",
            'user':""
        }
        cont = self.project_config
        start_method = "command"
        conf = self.get_conf_path()
        pid_path = conf[f'{start_method}_pid']
        pid = ReadFile(pid_path)
        if not pid:
            return data
        try:
            pid = int(pid)
            process = psutil.Process(pid)
            with process.oneshot():# 使用 oneshot() 进行性能优化,减少不必要的系统调用
                cmdline = process.cmdline()
                create_time = process.create_time()  # 进程创建时间
                child_pids = [c.pid for c in process.children(recursive=True) if c.status() != psutil.STATUS_ZOMBIE]
                pids =  [process.pid] + child_pids
                cpu_percent,memory_percent,threads_nums,mem_used = self.get_process_pids_resources(pids)
                data['mem_used'] = f"{mem_used:.2f} MB"
                data["pids"] = pids
                data["cpu_p"] = round(cpu_percent, 2)
                data["mem_p"] = round(memory_percent, 2)
                data["create_time"] = self.format_create_time(create_time)
                data["cmdline"] = " ".join(cmdline)
                data['threads'] = threads_nums
                parent_pidinfo= process.parent()
                data['fpid'] = process.ppid()
                data['fpid_name'] = parent_pidinfo.name() if parent_pidinfo else ""
                data['user'] = process.username()
            return data
        except:
            return data
    
    def create_site_config(self):
        """
        创建站点配置
        @author lybbn <2025-03-11>
        @param: cont 配置项
        """
        self.create_run_script()
        
    def get_run_script_name(self):
        """
        取运行脚本名称
        @author lybbn <2024-12-01>
        @param: cont 配置项
        """
        script_name = ""
        cont = self.project_config
        if self.is_windows:
            script_name = f"{self.siteName}_cmd.bat"
        else:
            script_name = f"{self.siteName}_cmd.sh"
        return script_name
    
    def get_run_script_path(self):
        """
        取运行脚本路径
        @author lybbn <2024-12-01>
        @param: cont 配置项
        """
        return self.scriptsPath+"/"+self.get_run_script_name()
    
    def create_run_script(self):
        """
        创建启动脚本
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        cont = self.project_config
        conf = self.get_conf_path()
        start_command = cont.get("start_command","")
        try:
            port = int(cont.get("port",0))
        except:
            port = 0
        if self.is_windows:
            log_path = conf[f'log_command']
            command_line = f"{start_command} >> {log_path} 2>&1"
            content = f"""
@echo off
chcp 65001 > nul
cd /d {self.sitePath}
{command_line}
"""
        else:
            log_path = conf['log_command']
            command_line = f"nohup {start_command} &>> {log_path} &"
            
            method_pid = "command_pid"
            sitepid = conf[method_pid]
            command_set_pid = f"echo $! > {sitepid}"
            content = f"""#!/bin/bash
LANG=en_US.UTF-8
cd {self.sitePath}
{command_line}
{command_set_pid}
"""
            script_path = self.get_run_script_path()
            WriteFile(script_path,content)

    def autoStart(self):
        """
        开机启动
        @author lybbn <2025-03-11>
        @param: cont 配置项
        """
        cont = self.project_config
        autostart = cont.get("autostart",False)
        if autostart:
            res = self.start_site()
            return res
        return True
        