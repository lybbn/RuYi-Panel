#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-05-06
# +-------------------------------------------------------------------
# | EditDate: 2025-05-06
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# PHP web 类
# ------------------------------
import psutil,time,datetime
import re,os,subprocess
from utils.common import current_os,ReadFile,RunCommand,GetLogsPath,WriteFile,ast_convert,DeleteFile
from django.conf import settings
from apps.system.models import Sites
from utils.server.system import system
from utils.install.php import (
    get_php_path_info, get_php_fpm_port,
    Start_PHP, Stop_PHP, Restart_PHP, Reload_PHP, is_php_running
)

class PhpClient:
    is_windows=True
    siteName = None
    sitePath = None

    confBasePath = None
    scriptsPath=None
    log_base_path = None
    project_config = None

    def __init__(self, *args, **kwargs):
        self.is_windows = True if current_os == 'windows' else False
        self.siteName = kwargs.get('siteName', '')
        self.sitePath = kwargs.get('sitePath', '').replace("\\","/")
        self.project_config = kwargs.get('cont', {})
        self.confBasePath = settings.RUYI_VHOST_PATH.replace("\\","/") +"/php_project/"+self.siteName
        self.scriptsPath = self.confBasePath + "/scripts"
        self.log_base_path = self.sitePath+"/logs"
        if not os.path.exists(self.confBasePath): os.makedirs(self.confBasePath, mode=0o755)
        if not os.path.exists(self.log_base_path): os.makedirs(self.log_base_path, mode=0o755)

    def get_conf_path(self):
        data = {
            "confBasePath":self.confBasePath,
            "scriptsPath":self.scriptsPath,
            'log_base_path':self.log_base_path,
            'log_command':self.log_base_path+'/command.log',
            'command_pid':self.confBasePath+f'/{self.siteName}.pid',
        }
        return data

    def create_site(self):
        try:
            cont = self.project_config
            if not os.path.exists(self.sitePath):
                try:
                    os.makedirs(self.sitePath)
                except Exception as e:
                    raise Exception(f'创建根目录失败：{e}')
            php_version = cont.get("php_version","")
            if not php_version:
                raise Exception("请选择PHP版本")
            port = cont.get("port","")
            if not port:
                raise Exception("请输入项目端口")
            self.create_site_config()
            allowport = cont.get("allowport",False)
            if allowport:
                system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':port,'handle':'accept'})
            isstart = self.start_site()
            if not isstart:
                raise Exception("启动失败")
            return True,"ok"
        except Exception as e:
            return False,e

    def is_project_running(self,is_simple=False):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return False
        try:
            return is_php_running(php_version,is_windows=self.is_windows)
        except:
            return False

    def start_site(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return False
        try:
            if is_php_running(php_version,is_windows=self.is_windows):
                return True
            num_workers = cont.get("num_workers",4)
            Start_PHP(version=php_version,is_windows=self.is_windows,num_workers=num_workers)
            time.sleep(1)
            return is_php_running(php_version,is_windows=self.is_windows)
        except:
            return False

    def stop_site(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return True
        try:
            if not is_php_running(php_version,is_windows=self.is_windows):
                return True
            Stop_PHP(version=php_version,is_windows=self.is_windows)
            return True
        except:
            return True

    def restart_site(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return False
        try:
            Restart_PHP(version=php_version,is_windows=self.is_windows)
            return True
        except:
            return False

    def reload_site(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return False
        try:
            Reload_PHP(version=php_version,is_windows=self.is_windows)
            return True
        except:
            return False

    def edit_site(self,is_need_time=True):
        self.create_run_script()
        cont = self.project_config
        port = cont.get("port","")
        allowport = cont.get("allowport",False)
        if allowport:
            system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':port,'handle':'accept'})
        self.restart_site()
        return True

    def delete_site(self):
        site_ins = Sites.objects.filter(name=self.siteName,type=3).first()
        if not site_ins:return False,"未找到站点"
        self.stop_site()
        system.ForceRemoveDir(self.confBasePath)
        site_ins.delete()
        return True,"ok"

    def get_project_pids(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return []
        soft_paths = get_php_path_info(php_version)
        pids = []
        if self.is_windows:
            php_cgi_name = 'php-cgi.exe'
            for proc in psutil.process_iter(['name','exe','pid']):
                try:
                    if proc.info['name'] == php_cgi_name:
                        if soft_paths['install_abspath_path'].lower() in (proc.info['exe'] or '').lower():
                            pids.append(proc.info['pid'])
                except:
                    pass
        else:
            fpm_path = soft_paths['linux_abspath_fpm_path']
            for proc in psutil.process_iter(['name','exe','pid','cmdline']):
                try:
                    cmdline = " ".join(proc.info.get('cmdline') or [])
                    if 'php-fpm' in (proc.info['name'] or '') and php_version in cmdline:
                        pids.append(proc.info['pid'])
                except:
                    pass
        return pids

    def get_loadstatus(self):
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
        php_version = cont.get("php_version","")
        if not php_version:
            return data
        pids = self.get_project_pids()
        if not pids:
            return data
        try:
            total_cpu = 0
            total_memory = 0
            total_system_memory = psutil.virtual_memory().total
            total_threads = 0
            main_pid = min(pids)
            main_process = psutil.Process(main_pid)
            create_time = main_process.create_time()
            cmdline = main_process.cmdline()
            user = main_process.username()
            for pid in pids:
                try:
                    p = psutil.Process(pid)
                    total_cpu += p.cpu_percent(interval=0.1)
                    total_memory += p.memory_info().rss
                    total_threads += p.num_threads()
                except:
                    continue
            memory_usage_percent = (total_memory / total_system_memory) * 100
            data['cpu_p'] = round(total_cpu, 2)
            data['mem_p'] = round(memory_usage_percent, 2)
            data['mem_used'] = f"{total_memory / 1024 / 1024:.2f} MB"
            data['threads'] = total_threads
            data['pids'] = pids
            data['create_time'] = datetime.datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
            data['cmdline'] = " ".join(cmdline)
            data['user'] = user
            parent = main_process.parent()
            data['fpid'] = main_process.ppid()
            data['fpid_name'] = parent.name() if parent else ""
        except:
            pass
        return data

    def create_site_config(self):
        self.create_run_script()
        self.create_nginx_proxy_conf()

    def create_run_script(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return
        soft_paths = get_php_path_info(php_version)
        conf = self.get_conf_path()
        if self.is_windows:
            php_cgi_path = soft_paths['windows_abspath_phpcgi_path']
            php_ini_path = soft_paths['windows_abspath_conf_path']
            fpm_port = soft_paths['fpm_port']
            num_workers = int(cont.get("num_workers",4))
            log_path = conf['log_command']
            pid_file = conf['command_pid']
            lines = ["@echo off","chcp 65001 > nul"]
            for i in range(num_workers):
                lines.append(f'start "" /b "{php_cgi_path}" -b 127.0.0.1:{fpm_port} -c "{php_ini_path}" >> "{log_path}" 2>&1')
            lines.append(f'echo done >> "{log_path}"')
            content = "\n".join(lines)
        else:
            fpm_path = soft_paths['linux_abspath_fpm_path']
            fpm_conf = soft_paths['linux_abspath_fpm_conf_path']
            pid_file = conf['command_pid']
            log_path = conf['log_command']
            content = f"""#!/bin/bash
LANG=en_US.UTF-8
cd {self.sitePath}
nohup {fpm_path} --fpm-config {fpm_conf} &>> {log_path} &
echo $! > {pid_file}
"""
        script_path = self.get_run_script_path()
        WriteFile(script_path,content)

    def create_nginx_proxy_conf(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return
        soft_paths = get_php_path_info(php_version)
        fpm_port = soft_paths['fpm_port']
        domains = cont.get("domains",[])
        if not domains:
            return
        from utils.ruyiclass.nginxClass import NginxClient
        domain_list = []
        for d in domains:
            if isinstance(d,str):
                domain_list.append({'domain':d,'port':80})
            elif isinstance(d,dict):
                domain_list.append(d)
        nginx_conf_path = os.path.join(self.confBasePath, f"{self.siteName}.conf")
        nginx_client = NginxClient(siteName=self.siteName,sitePath=self.sitePath)
        nginx_client.create_php_proxy_conf(
            domains=domain_list,
            fpm_port=fpm_port,
            conf_path=nginx_conf_path,
            is_windows=self.is_windows
        )

    def get_run_script_name(self):
        if self.is_windows:
            return f"{self.siteName}_cmd.bat"
        else:
            return f"{self.siteName}_cmd.sh"

    def get_run_script_path(self):
        return self.scriptsPath+"/"+self.get_run_script_name()

    def autoStart(self):
        cont = self.project_config
        autostart = cont.get("autostart",False)
        if autostart:
            return self.start_site()
        return True
