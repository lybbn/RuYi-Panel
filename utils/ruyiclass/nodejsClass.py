#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-05-21
# +-------------------------------------------------------------------
# | EditDate: 2025-05-21
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Node.js web 类
# ------------------------------
import psutil,time,datetime
import re,os,subprocess
from utils.common import current_os,ReadFile,RunCommand,GetLogsPath,WriteFile,ast_convert,DeleteFile
from django.conf import settings
from apps.system.models import Sites
from utils.server.system import system

class NodeClient:
    is_windows=True
    siteName = None
    sitePath = None

    node_bin_path = ""
    confBasePath = None
    scriptsPath=None
    log_base_path = None
    project_config = None

    def __init__(self, *args, **kwargs):
        self.is_windows = True if current_os == 'windows' else False
        self.siteName = kwargs.get('siteName', '')
        self.sitePath = kwargs.get('sitePath', '').replace("\\","/")
        self.project_config = kwargs.get('cont', '')
        self.confBasePath = settings.RUYI_VHOST_PATH.replace("\\","/") +"/nodejs_project/"+self.siteName
        self.scriptsPath = self.confBasePath + "/scripts"
        self.log_base_path = self.sitePath+"/logs"
        if not os.path.exists(self.confBasePath): os.makedirs(self.confBasePath, mode=0o755)
        if not os.path.exists(self.log_base_path): os.makedirs(self.log_base_path, mode=0o755)

    def get_conf_path(self):
        default_node_exe = self._get_node_exe(self.project_config.get("version","") if self.project_config else "")
        default_node_bin = os.path.dirname(default_node_exe) if default_node_exe and default_node_exe != "node" else ""
        data =  {
            "confBasePath":self.confBasePath,
            "scriptsPath":self.scriptsPath,
            'log_base_path':self.log_base_path,
            'log_command':self.log_base_path+'/command.log',
            'log_pm2':self.log_base_path+'/pm2.log',
            'command_pid':self.sitePath+f'/{self.siteName}.pid',
            'pm2_pid':self.sitePath+f'/{self.siteName}_pm2.pid',
            'node_bin_path':default_node_bin
        }
        return data

    def create_site(self):
        try:
            cont = self.project_config
            if not os.path.exists(self.sitePath):
                try:
                    os.makedirs(self.sitePath)
                except Exception as e:
                    errmsg = '创建根目录失败：%s'%e
                    raise Exception(errmsg)
            port = cont.get("port","")
            start_command = cont.get("start_command","")
            if not start_command:raise Exception("缺少启动命令")
            self.create_site_config()
            allowport = cont.get("allowport",False)
            if allowport:
                system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':port,'handle':'accept'})
            install_deps = cont.get("install_deps",False)
            if install_deps:
                self.install_dependencies()
            isstart = self.start_site()
            if not isstart:
                raise Exception("启动失败")
            return True,"ok"
        except Exception as e:
            return False,e

    def install_dependencies(self):
        cont = self.project_config
        pkg_manager = cont.get("pkg_manager","npm")
        version = cont.get("version","")
        node_exe = self._get_node_exe(version)
        pkg_cmd = self._get_pkg_cmd(pkg_manager, version)
        cmd = f"{pkg_cmd} install"
        if self.is_windows:
            env = os.environ.copy()
            node_bin = os.path.dirname(node_exe)
            env['PATH'] = node_bin + ';' + env.get('PATH','')
            subprocess.Popen(cmd,cwd=self.sitePath,bufsize=4096,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,shell=True,creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,env=env)
        else:
            env = os.environ.copy()
            node_bin = os.path.dirname(node_exe)
            env['PATH'] = node_bin + ':' + env.get('PATH','')
            self.ExecCommand(cmd,cwd=self.sitePath,env=env,user=cont.get("start_user","www"))
        time.sleep(3)

    def _get_node_exe(self, version=""):
        from utils.install.nodejs import get_nodejs_path_info
        if not version:
            from utils.install.install_soft import Check_Soft_Installed
            from utils.common import GetSoftList
            soft_list = GetSoftList()
            for s in soft_list:
                if s['name'] == 'nodejs':
                    version = s['versions'][0]['c_version']
                    break
        if not version:
            return "node"
        info = get_nodejs_path_info(version)
        if self.is_windows:
            return info.get('windows_abspath_node_path','node')
        return info.get('linux_abspath_node_path','node')

    def _get_pkg_cmd(self, pkg_manager="npm", version=""):
        node_dir = ""
        if version:
            from utils.install.nodejs import get_nodejs_path_info
            info = get_nodejs_path_info(version)
            if self.is_windows:
                node_dir = info.get('windows_abspath_bin_path','')
            else:
                node_dir = info.get('linux_abspath_bin_path','')
        if node_dir:
            if self.is_windows:
                return os.path.join(node_dir, pkg_manager + '.cmd')
            return os.path.join(node_dir, pkg_manager)
        return pkg_manager

    def get_project_pids(self,pid):
        try:
            if not isinstance(pid,int):
                pid = int(pid)
            p = psutil.Process(pid)
            child_pids = [c.pid for c in p.children(recursive=True) if c.status() != psutil.STATUS_ZOMBIE]
            return [p.pid] + child_pids
        except:
            return []

    def get_project_pid_process(self):
        cont = self.project_config
        pids = []
        site_path_match = self.sitePath.replace("\\", "/").lower()
        try:
            for i in psutil.process_iter(['pid', 'exe', 'cmdline']):
                try:
                    if i.status() == psutil.STATUS_ZOMBIE:continue
                    cmdlines = " ".join(i.cmdline()).replace("\\", "/").lower()
                    start_command = cont.get("start_command","").lower()
                    if start_command and start_command in cmdlines and site_path_match in cmdlines:
                        pids.append(i.pid)
                except:
                    pass
        except:
            return None
        if pids:return min(pids)
        return None

    def is_project_running(self,is_simple=False):
        cont = self.project_config
        start_method = cont.get("start_method","command")
        conf = self.get_conf_path()
        pid_path = conf[f'{start_method}_pid']
        pid = ReadFile(pid_path)
        if is_simple:
            if not pid:
                return False
            try:
                pid = int(pid)
                psutil.Process(pid)
                return True
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
                return False
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
        if not self.is_windows:
            preexec_fn = lambda: os.setuid(0)
            if user:preexec_fn = self.get_preexec_fn(user)
            subprocess.Popen(cmdstr,cwd=cwd,bufsize=4096,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,shell=shell,preexec_fn=preexec_fn, env=env,start_new_session=True)
        else:
            subprocess.Popen(cmdstr,cwd=cwd,bufsize=4096,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,shell=shell,env=env,creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)

    def exec_bat(self, pid_file=None, bat_path=None):
        if not os.path.exists(bat_path):
            return
        try:
            env = os.environ.copy()
            cont = self.project_config
            version = cont.get("version","")
            if version:
                from utils.install.nodejs import get_nodejs_path_info
                info = get_nodejs_path_info(version)
                node_bin = info.get('windows_abspath_bin_path','')
                if node_bin:
                    env['PATH'] = node_bin + ';' + env.get('PATH','')
            process = subprocess.Popen(
                ['cmd', '/c', bat_path],
                shell=True,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                cwd=self.sitePath,
                env=env
            )
            time.sleep(2)
            pid = self.get_project_pid_process()
            if not pid:
                pid = process.pid
            if pid and pid_file:
                with open(pid_file, 'w') as f:
                    f.write(str(pid))
        except Exception:
            pass

    def edit_site(self,is_need_time=True):
        self.create_run_script()
        cont = self.project_config
        port = cont.get("port","")
        allowport = cont.get("allowport",False)
        if allowport:
            system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':port,'handle':'accept'})
        self.start_site()
        return True

    def start_site(self):
        if not self.is_project_running():
            cont = self.project_config
            conf = self.get_conf_path()
            start_method = cont.get("start_method","command")
            script_path = self.get_run_script_path()
            if not os.path.exists(script_path):
                self.create_run_script()
            method_pid = f"{start_method}_pid"
            sitepid = conf[method_pid]
            if os.path.exists(sitepid):
                os.remove(sitepid)
            start_user = cont.get("start_user","www")
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
                env = os.environ.copy()
                version = cont.get("version","")
                if version:
                    from utils.install.nodejs import get_nodejs_path_info
                    info = get_nodejs_path_info(version)
                    node_bin = info.get('linux_abspath_bin_path','')
                    if node_bin:
                        env['PATH'] = node_bin + ':' + env.get('PATH','')
                else:
                    default_node_exe = self._get_node_exe("")
                    default_node_bin = os.path.dirname(default_node_exe)
                    if default_node_bin and default_node_bin != '.':
                        env['PATH'] = default_node_bin + ':' + env.get('PATH','')

            if self.is_windows:
                self.exec_bat(bat_path=script_path, pid_file=sitepid)
            else:
                self.ExecCommand(['bash',script_path],cwd=self.sitePath,user=start_user, env=env,shell=False)
            time.sleep(2)

            if self.is_project_running():
                pid = self.is_project_running()
                if pid and not ReadFile(sitepid):
                    with open(sitepid, 'w') as f:
                        f.write(str(pid))
                return True
            return False

        return True

    def stop_site(self):
        if not self.is_project_running():
            return True
        cont = self.project_config
        conf = self.get_conf_path()
        start_method = cont.get("start_method","command")
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
        self.stop_site()
        res = self.start_site()
        return res

    def delete_site(self):
        site_ins = Sites.objects.filter(name=self.siteName,type=2).first()
        if not site_ins:return False,"未找到站点"
        self.stop_site()
        system.ForceRemoveDir(self.confBasePath)
        conf = self.get_conf_path()
        DeleteFile(conf['log_command'],empty_tips=False)
        DeleteFile(conf['log_pm2'],empty_tips=False)
        DeleteFile(conf['command_pid'],empty_tips=False)
        DeleteFile(conf['pm2_pid'],empty_tips=False)
        site_ins.delete()
        return True,"ok"

    def kill_pids(self,pids=None):
        if not pids:
            return True
        for pid in pids:
            try:
                p = psutil.Process(pid)
                p.terminate()
            except:
                pass
        time.sleep(1)
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
        total_cpu = 0
        total_memory = 0
        total_system_memory = psutil.virtual_memory().total
        total_threads = 0

        for thread_pid in thread_pids:
            try:
                thread_process = psutil.Process(thread_pid)
                total_cpu += thread_process.cpu_percent(interval=0.1)
                process_memory = thread_process.memory_info().rss
                total_memory += process_memory
                total_threads += thread_process.num_threads()
            except:
                continue
        memory_usage_percent = (total_memory / total_system_memory) * 100
        return total_cpu,memory_usage_percent,total_threads,total_memory / 1024 / 1024

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
        start_method = cont.get("start_method","command")
        conf = self.get_conf_path()
        pid_path = conf[f'{start_method}_pid']
        pid = ReadFile(pid_path)
        if not pid:
            return data
        try:
            pid = int(pid)
            process = psutil.Process(pid)
            with process.oneshot():
                cmdline = process.cmdline()
                create_time = process.create_time()
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
        self.create_run_script()

    def get_run_script_name(self):
        cont = self.project_config
        start_method = cont.get("start_method","command")
        if self.is_windows:
            script_name = f"{self.siteName}_{start_method}.bat"
        else:
            script_name = f"{self.siteName}_{start_method}.sh"
        return script_name

    def get_run_script_path(self):
        return self.scriptsPath+"/"+self.get_run_script_name()

    def create_run_script(self):
        cont = self.project_config
        conf = self.get_conf_path()
        start_method = cont.get("start_method","command")
        start_command = cont.get("start_command","")
        version = cont.get("version","")
        try:
            port = int(cont.get("port",0))
        except:
            port = 0

        node_exe = self._get_node_exe(version)

        if start_method == "pm2":
            self._create_pm2_script(cont, conf, node_exe)
        else:
            self._create_command_script(cont, conf, start_command, node_exe)

    def _create_command_script(self, cont, conf, start_command, node_exe):
        if self.is_windows:
            log_path = conf[f'log_command']
            command_line = f"{start_command} >> {log_path} 2>&1"
            content = f"""
@echo off
chcp 65001 > nul
cd /d {self.sitePath}
set PATH={os.path.dirname(node_exe)};%PATH%
start "" /b {command_line}
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
export PATH={os.path.dirname(node_exe)}:$PATH
{command_line}
{command_set_pid}
"""
        script_path = self.get_run_script_path()
        WriteFile(script_path,content)

    def _create_pm2_script(self, cont, conf, node_exe):
        entry_file = cont.get("entry_file","")
        pkg_manager = cont.get("pkg_manager","npm")
        if self.is_windows:
            log_path = conf[f'log_command']
            pm2_cmd = self._get_pkg_cmd("pm2", cont.get("version",""))
            if not os.path.exists(pm2_cmd.replace(".cmd","").replace(".exe","")):
                pm2_cmd = "pm2"
            command_line = f"{pm2_cmd} start {entry_file} --name {self.siteName}"
            content = f"""
@echo off
chcp 65001 > nul
cd /d {self.sitePath}
set PATH={os.path.dirname(node_exe)};%PATH%
start "" /b {command_line} >> {log_path} 2>&1
"""
        else:
            log_path = conf['log_pm2']
            pm2_cmd = self._get_pkg_cmd("pm2", cont.get("version",""))
            if not os.path.exists(pm2_cmd):
                pm2_cmd = "pm2"
            method_pid = "pm2_pid"
            sitepid = conf[method_pid]
            command_set_pid = f"echo $! > {sitepid}"
            content = f"""#!/bin/bash
LANG=en_US.UTF-8
cd {self.sitePath}
export PATH={os.path.dirname(node_exe)}:$PATH
nohup {pm2_cmd} start {entry_file} --name {self.siteName} &>> {log_path} &
{command_set_pid}
"""
        script_path = self.get_run_script_path()
        WriteFile(script_path,content)

    def autoStart(self):
        cont = self.project_config
        autostart = cont.get("autostart",False)
        if autostart:
            res = self.start_site()
            return res
        return True
