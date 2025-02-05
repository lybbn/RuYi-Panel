#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-11-19
# +-------------------------------------------------------------------
# | EditDate: 2024-11-19
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# python web 类
# ------------------------------
import configparser
import psutil,time,datetime
import re,os,subprocess
from utils.common import current_os,ReadFile,RunCommand,GetLogsPath,WriteFile,ast_convert,DeleteFile
from utils.install.python import get_python_path_info
from django.conf import settings
from apps.system.models import Sites
from utils.server.system import system

class PythonClient:
    is_windows=True
    siteName = None
    sitePath = None
    confBasePath = None
    scriptsPath=None
    pyenv_path = None
    python_version=None
    log_base_path = None
    log_create_path = None
    project_config = None
    pip_source_dic = {
        "阿里云": "https://mirrors.aliyun.com/pypi/simple/",
        "华为云": "https://mirrors.huaweicloud.com/repository/pypi/simple/",
        "清华大学": "https://pypi.tuna.tsinghua.edu.cn/simple/",
    }
    
    def __init__(self, *args, **kwargs):
        self.is_windows = True if current_os == 'windows' else False
        self.siteName = kwargs.get('siteName', '')
        self.sitePath = kwargs.get('sitePath', '').replace("\\","/")
        self.project_config = kwargs.get('cont', '')
        self.python_version = self.project_config.get('version', '')
        self.confBasePath = settings.RUYI_VHOST_PATH.replace("\\","/") +"/python_project/"+self.siteName
        self.scriptsPath = self.confBasePath + "/scripts"
        self.pyenv_path = self.sitePath+"/venv"
        self.log_base_path = self.sitePath+"/logs"
        self.log_create_path = GetLogsPath()+"/python/"+ self.siteName +"_create.log"
        if not os.path.exists(self.confBasePath): os.makedirs(self.confBasePath, mode=0o755)
        if not os.path.exists(self.log_base_path): os.makedirs(self.log_base_path, mode=0o755)
        
    def write_create_log(self,logstr,mode="ab+",is_error=False):
        """
        写创建日志
        """
        if not self.log_create_path:
            return
        with open(self.log_create_path, mode) as f:
            if isinstance(logstr, int):
                logstr = str(logstr)
            if is_error:
                logstr = "x" * 70 + "\n" + "错误：{}".format(logstr) + "\n"
                logstr += "x" * 70 + "\n"
            else:
                if logstr == "":
                    logstr +=""
                else:
                    logstr += "\n"
            f.write(logstr.encode('utf-8'))
        
    def get_conf_path(self,is_force=True):
        """
        取配置路径
        is_force:是否根据配置文件同步获取配置
        """
        pyconf = get_python_path_info(self.python_version)
        pyexe = pyconf['windows_abspath_python_path'] if self.is_windows else pyconf['linux_abspath_python_path']
        pipexe = (self.pyenv_path+"/Scripts/pip") if self.is_windows else (self.pyenv_path+"/bin/pip")
        data =  {
            "confBasePath":self.confBasePath,
            "scriptsPath":self.scriptsPath,
            "pyenv_path":self.pyenv_path,
            'pyexe':pyexe,#项目选择版本的python
            'pipexe':pipexe,#虚拟环境中的pip
            'log_base_path':self.log_base_path,
            'log_create_path':self.log_create_path,
            'log_access_gunicorn':self.log_base_path+'/gunicorn_access.log',
            'log_error_gunicorn':self.log_base_path+'/gunicorn_error.log',
            'log_uwsgi':self.log_base_path+'/uwsgi.log',
            'log_command':self.log_base_path+'/command.log',
            'log_daphne':self.log_base_path+'/daphne.log',
            'gunicorn_pid':self.sitePath+'/gunicorn.pid',
            'uwsgi_pid':self.sitePath+'/uwsgi.pid',
            'command_pid':self.sitePath+f'/{self.siteName}.pid',
            'daphne_pid':self.sitePath+f'/{self.siteName}.pid',
            'gunicorn_conf_path':self.sitePath+"/gunicorn_config.py",
            'uwsgi_conf_path':self.sitePath+"/uwsgi_config.ini",
        }
        if is_force:
            start_method = self.project_config.get("start_method","")
            if start_method in ["uwsgi","gunicorn"]:
                try:
                    conf_path = data[f'{start_method}_conf_path']
                    if os.path.exists(conf_path):
                        if start_method == "uwsgi":
                            config = configparser.ConfigParser()
                            config.read(conf_path)
                            keySelect = "uwsgi"
                            log_path = config.get(keySelect, 'daemonize',fallback='')
                            pidfile_path = config.get(keySelect, 'pidfile',fallback='')
                            if log_path:data['log_uwsgi'] = log_path
                            if pidfile_path:data['uwsgi_pid'] = pidfile_path
                        elif start_method == "gunicorn":
                            conf_content = ReadFile(conf_path)
                            pidfile_re = r'\n\s?pidfile\s*=\s*(.+)'
                            pidfile_res = re.findall(pidfile_re, conf_content)
                            pidfile_path = (pidfile_res[0]).strip().strip("'") if pidfile_res else ""
                            if pidfile_path:data['gunicorn_pid'] = pidfile_path
                            accesslog_re = r'\n\s?accesslog\s*=\s*(.+)'
                            accesslog_res = re.findall(accesslog_re, conf_content)
                            accesslog_path = (accesslog_res[0]).strip().strip("'") if accesslog_res and not accesslog_res=="-" else ""
                            if accesslog_path:data['log_access_gunicorn'] = accesslog_path
                            errorlog_re = r'\n\s?errorlog\s*=\s*(.+)'
                            errorlog_res = re.findall(errorlog_re, conf_content)
                            errorlog_path = (errorlog_res[0]).strip().strip("'") if errorlog_res and not errorlog_res=="-" else ""
                            if errorlog_path:data['log_error_gunicorn'] = errorlog_path
                except:
                    pass
        return data
    
    def create_site(self):
        """
        创建站点
        """
        try:
            self.write_create_log("", mode="wb+")
            cont = self.project_config
            # 创建网站根目录
            if not os.path.exists(self.sitePath):
                try:
                    os.makedirs(self.sitePath)
                except Exception as e:
                    errmsg = '创建根目录失败：%s'%e
                    raise Exception(errmsg)
            start_method = cont.get("start_method","")
            start_command = cont.get("start_command","")
            framework = cont.get("framework","")
            rukou = cont.get("rukou","")
            install_reqs = cont.get("install_reqs","")
            requirements = cont.get("requirements","")
            if not start_method in ['command','daphne','uwsgi','gunicorn']:raise Exception("启动方式错误")
            if start_method in ['command'] and not start_command:raise Exception("缺少启动命令")
            if framework not in ['python'] and not rukou:raise Exception("缺少入口文件")
            
            self.write_create_log(f"开始创建Python项目站点：{self.siteName} 环境")
            self.write_create_log(f"【*】开始创建虚拟环境...")
            #创建虚拟环境
            ispyenvok = self.create_python_env()
            if ispyenvok:
                self.write_create_log(f"----- 虚拟环境创建成功✔")
            else:
                raise Exception("虚拟环境创建失败")
            #安装依赖
            if install_reqs and requirements:
                self.write_create_log(f"【*】开始安装依赖...")
                ispyinsrqok = self.install_requirements(cont=cont)
                if ispyinsrqok:
                    self.write_create_log(f"----- 安装依赖成功✔")
                else:
                    raise Exception("安装依赖失败")
                self.install_extra_requirements()
            #创建配置文件
            self.write_create_log(f"【*】正在创建配置...")
            self.create_site_config()
            self.write_create_log(f"----- 创建成功✔")
            #正在启动
            self.write_create_log(f"【*】启动项目...")
            isstart = self.start_site()
            if not isstart:
                raise Exception("启动失败")
            else:
                self.write_create_log(f"----- 启动成功✔")
            self.write_create_log(f"执行【{self.siteName}】项目创建成功✔")
            self.write_create_log(f"create project success by ruyi")
            return True,"ok"
        except Exception as e:
            self.write_create_log(e,is_error=True)
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
        start_method = cont.get("start_method","command")
        pids = []
        try:
            for i in psutil.process_iter(['pid', 'exe', 'cmdline']):
                try:
                    if i.status() == psutil.STATUS_ZOMBIE:continue
                    cmdlines = " ".join(i.cmdline())
                    if start_method in ['command']:
                        start_command = cont.get("start_command","")
                        if self.pyenv_path in i.exe() and start_command in cmdlines:
                            pids.append(i.pid)
                    else:
                        if self.pyenv_path in i.exe() and start_method in i.exe() and start_method in cmdlines and self.sitePath in cmdlines:
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
    
    def install_all_need_requirements(self,cont={}):
        """
        安装站点所有依赖
        """
        self.install_requirements(cont=cont,log=False)
        self.install_extra_requirements(log=False)
    
    def edit_site(self,is_need_time=True):
        """
        修改站点
        """
        res = self.sync_db_to_conf()
        if not res:return False
        self.create_run_script()
        cont = self.project_config
        install_reqs = cont.get("install_reqs","")
        requirements = cont.get("requirements","")
        sleeptime = 5
        if is_need_time:sleeptime=10
        #安装依赖（异步）
        if install_reqs and requirements:
            import threading
            t = threading.Thread(
                target=self.install_all_need_requirements,
                args=(
                    cont,
                ))
            t.start()
            time.sleep(sleeptime)
        self.start_site()
        return True
    
    def getApplicationAppName(self):
        """
        获取flask或django中application模块中的app名字
        """
        cont = self.project_config
        framework = cont.get("framework","")
        application = cont.get("application","")
        if framework == "django":
            return application.split('.')[0]
        elif framework == "flask":
            return application.split(':')[0]
        return None
    
    def start_site(self):
        """
        启动站点
        """
        if not self.is_project_running():
            cont = self.project_config
            conf = self.get_conf_path()
            start_method = cont.get("start_method","command")
            framework = cont.get("framework","")
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
                env['PATH'] = self.pyenv_path+"/bin" + ':' + env['PATH']  # 把虚拟环境的 bin 路径加入 PATH
                env['PYTHONHOME'] = self.pyenv_path
                env['VIRTUAL_ENV'] = self.pyenv_path
                if framework == "django":
                    appname = self.getApplicationAppName()
                    env['DJANGO_SETTINGS_MODULE'] = f"{appname}.settings"

            if start_method in ["uwsgi","gunicorn"]:
                self.ExecCommand([script_path],cwd=self.sitePath,env=env)
            else:
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
        #删除虚拟环境
        system.ForceRemoveDir(self.pyenv_path)
        #删除日志
        conf = self.get_conf_path()
        log_create_path = conf['log_create_path']
        log_access_gunicorn = conf['log_access_gunicorn']
        log_error_gunicorn = conf['log_error_gunicorn']
        log_uwsgi = conf['log_uwsgi']
        log_command = conf['log_command']
        log_daphne = conf['log_daphne']
        system.ForceRemoveDir(log_create_path)
        system.ForceRemoveDir(log_access_gunicorn)
        system.ForceRemoveDir(log_error_gunicorn)
        system.ForceRemoveDir(log_uwsgi)
        system.ForceRemoveDir(log_command)
        system.ForceRemoveDir(log_daphne)
        DeleteFile(conf['gunicorn_pid'],empty_tips=False)
        DeleteFile(conf['uwsgi_pid'],empty_tips=False)
        DeleteFile(conf['command_pid'],empty_tips=False)
        DeleteFile(conf['daphne_pid'],empty_tips=False)
        DeleteFile(conf['gunicorn_conf_path'],empty_tips=False)
        DeleteFile(conf['uwsgi_conf_path'],empty_tips=False)
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
        start_method = cont.get("start_method","command")
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

    @staticmethod
    def get_framework_file(path=None):
        """
        获取项目requirements依赖文件
        @author lybbn <2024-11-22>
        @param: path 项目根目录路径
        """
        if not path:return None
        path = os.path.abspath(path)
        requirements_path = os.path.join(path, 'requirements.txt')
        if os.path.exists(requirements_path):
            return requirements_path
        keyword = "requirements"
        for file in os.listdir(path):
            rqf = os.path.join(path, file)
            if os.path.isfile(rqf) and keyword.lower() in file.lower():
                return rqf
        return None
    
    @staticmethod
    def get_sgi_from_requirement(requirements):
        """
        根据requirements依赖文件获取是否要启用asgi或wsgi
        @author lybbn <2024-11-22>
        @param: requirements 依赖文件路径
        """
        if not requirements:return None
        content = ReadFile(requirements)
        if not content:return "wsgi"
        content = content.lower()
        rep = r'(asgiref|channels|paramiko|async\s{1,2}def|await)'
        if re.search(rep, content, re.IGNORECASE):
            return "asgi"
        return "wsgi"
    
    @staticmethod
    def get_project_framework(requirements):
        """
        获取项目框架（根据requirements文件检测），默认返回python
        @author lybbn <2024-11-22>
        @param: requirements 文件路径
        """
        frameworks = ['django', 'flask']
        content = ReadFile(requirements)
        if not content:return "python"
        content = content.lower()
        for fm in frameworks:
            if fm in content:
                return fm
        return "python"
    
    @staticmethod
    def get_rukou(cont={}):
        """
        获取项目入口文件
        @author lybbn <2024-11-22>
        @param: requirements 文件路径
        """
        path = cont.get("path",None)
        framework = cont.get("framework","python")
        if framework == "python":return None
        for file in os.listdir(path):
            f_path = os.path.join(path, file)
            if os.path.isfile(f_path):
                if framework == "flask":
                    if file in ['app.py','run.py','runserver.py','main.py']:
                        return f_path
            elif os.path.isdir(f_path):
                for file1 in os.listdir(f_path):
                    f_path1 = os.path.join(path, file, file1)
                    if os.path.isfile(f_path1):
                        if framework == "django":
                            if file1 in ['wsgi.py','asgi.py']:
                                return f_path1
        return None
    
    @staticmethod
    def get_project_application(cont={},sgi=""):
        """
        入口文件获取项目application 参数 如django的 application.asgi:application 和flask的 app:app
        @author lybbn <2024-11-22>
        @param: path 入口文件
        """
        rukou = cont.get("rukou",None)
        framework = cont.get("framework",None)
        if not rukou:return ""
        if framework == "python":return ""
        folder_path = os.path.dirname(rukou)
        content = ReadFile(rukou)
        if framework == "django":
            module = os.path.basename(folder_path)
            instance_name = "application"
            sgi = sgi if sgi else os.path.basename(rukou).replace(".py","")
            if content:
                match = re.search(r'\b(\w+)\s*=\s*get_'+ re.escape(sgi)+r'_application\(\)', content)
                instance_name = match.group(1)
            return f"{module}.{sgi}:{instance_name}"
        elif framework == "flask":
            module = os.path.basename(rukou).replace(".py","")
            instance_name = "app"
            if content:
                pattern = r'\b(\w+)\s*\.run\([^\)]*\)'
                matches = re.findall(pattern, content)
                if matches:
                    instance_name = matches[0]
            return f"{module}:{instance_name}"
        return None
    
    @staticmethod
    def get_env_info(path="",rukou=""):
        """
        根据项目目录获取项目环境信息
        @author lybbn <2024-11-22>
        @param: path 项目根目录路径
        @param: rukou 项目入口文件路径
        """
        info = {
            "application":"",
            "framework": None,
            "requirements": None,
            "rukou": None,
            "sgi": None
        }
        if not path:return info
        if not os.path.exists(path):return info
        info['requirements'] = PythonClient.get_framework_file(path=path)
        info['framework'] = PythonClient.get_project_framework(info['requirements'])
        info['rukou'] = rukou if rukou else PythonClient.get_rukou(cont={'path':path,'framework':info['framework']})
        if not rukou: 
            info['sgi'] =  PythonClient.get_sgi_from_requirement(info['requirements'])
        else:
            if info['framework'] == "django":
                info['sgi'] = os.path.basename(rukou).replace(".py","")
        if info['framework'] == "python":
            info['sgi'] = None
        elif info['framework'] == "django":
            sgipy = info['sgi']+".py"
            if info['sgi'] and sgipy not in info['rukou']:
                folder_path = os.path.dirname(info['rukou'])
                info['rukou'] = os.path.join(folder_path, sgipy)
        info['application'] = PythonClient.get_project_application(cont=info)
        return info
    
    def create_python_env(self,log=True):
        """
        创建python 虚拟环境
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        conf = self.get_conf_path()
        pyexe = conf['pyexe']
        if not log:
            res,err,code = RunCommand(f"{pyexe} -m venv {self.pyenv_path}",returncode=True)
            if code == 0:
                return True
            return False
        else:
            r_process = subprocess.Popen([pyexe, "-m",'venv',self.pyenv_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # 持续读取输出
            while True:
                r_output = r_process.stdout.readline()
                if r_output == '' and r_process.poll() is not None:
                    break
                if r_output:
                    self.write_create_log(f"{r_output.strip()}")
            if r_process.returncode == 0:
                return True
            return False
    
    def install_requirements(self,cont={},log=True):
        """
        安装requirements
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        requirements = cont.get("requirements","")
        if not requirements:return False
        conf = self.get_conf_path()
        pipexe = conf['pipexe']
        pipsource = self.pip_source_dic['阿里云']
        if not log:
            res,err,code = RunCommand(f"{pipexe} install -r {requirements} -i {pipsource}",returncode=True)
            if code == 0:
                return True
            return False
        else:
            r_process = subprocess.Popen([pipexe, "install","-r",requirements,"-i",pipsource], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # 持续读取输出
            while True:
                r_output = r_process.stdout.readline()
                if r_output == '' and r_process.poll() is not None:
                    break
                if r_output:
                    self.write_create_log(f"{r_output.strip()}")
            if r_process.returncode == 0:
                return True
            return False
        
    def install_extra_requirements(self,log=True):
        """
        安装额外的requirements（项目所需）
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        cont = self.project_config
        start_method = cont.get("start_method","command")
        sgi = cont.get("sgi","")
        if start_method in ["uwsgi","daphne","gunicorn"]:
            conf = self.get_conf_path()
            pipexe = conf['pipexe']
            pipsource = self.pip_source_dic['阿里云']
            extra_pip = start_method
            if start_method == "gunicorn" and sgi == "asgi":
                extra_pip = f"{extra_pip} uvicorn"
            if not log:
                res,err,code = RunCommand(f"{pipexe} install {extra_pip} -i {pipsource}",returncode=True)
                if code == 0:
                    return True
                return False
            else:
                self.write_create_log(f"开启安装额外pip包：{extra_pip}")
                r_process = subprocess.Popen([pipexe, "install",extra_pip,"-i",pipsource], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                # 持续读取输出
                while True:
                    r_output = r_process.stdout.readline()
                    if r_output == '' and r_process.poll() is not None:
                        break
                    if r_output:
                        self.write_create_log(f"{r_output.strip()}")
                if r_process.returncode == 0:
                    return True
                return False
        return True
    
    def get_requirements_list(self):
        """
        获取requirements pip list
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        conf = self.get_conf_path()
        pipexe = conf['pipexe']
        data = []
        res,err,code = RunCommand(f"{pipexe} list",returncode=True)
        if code == 0:
            for d in res.split("\n")[2:]:
                try:
                    tmpcontent = d.strip()
                    if tmpcontent:
                        tlist = tmpcontent.split()
                        data.append({"name":tlist[0],"version":tlist[1]})
                except:
                    pass
        return data
    
    def requirements_uninstall_module(self,cont={}):
        """
        卸载requirements pip 指定库
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        name = cont.get("name","")
        if not name:return False
        conf = self.get_conf_path()
        pipexe = conf['pipexe']
        res,err,code = RunCommand(f"{pipexe} uninstall {name} -y",returncode=True)
        if code == 0:
            return True
        return False
    
    def requirements_install_module(self,cont={}):
        """
        安装requirements pip 指定库
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        name = cont.get("name","")
        if not name:return False
        version = cont.get("version","")
        sourcename = cont.get("sourcename","")
        if not sourcename:sourcename="阿里云"
        pipsource = self.pip_source_dic.get(sourcename,"阿里云")
        if not name:return False
        conf = self.get_conf_path()
        pipexe = conf['pipexe']
        if version:name = f"{name}=={version}"
        res,err,code = RunCommand(f"{pipexe} install {name} -i {pipsource}",returncode=True)
        if code == 0:
            return True
        return False
    
    def create_site_config(self):
        """
        创建站点配置
        @author lybbn <2024-11-23>
        @param: cont 配置项
        """
        cont = self.project_config
        conf = self.get_conf_path()
        start_method = cont.get("start_method","")
        content = None
        config_path = None
        if start_method == "uwsgi":
            content = self.default_uwsgi_config()
            config_path = conf['uwsgi_conf_path']
            WriteFile(config_path,content)
        elif start_method == "gunicorn":
            content = self.default_gunicorn_config()
            config_path = conf['gunicorn_conf_path']
            WriteFile(config_path,content)
        self.create_run_script()
        
    def default_uwsgi_config(self):
        """
        uwsgi配置
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        cont = self.project_config
        conf = self.get_conf_path()
        uwsgi_pid = conf['uwsgi_pid']
        log_uwsgi = conf['log_uwsgi']
        root_path = self.sitePath
        start_user = cont.get("start_user","root")
        sgi = cont.get("sgi","wsgi")
        rukou = cont.get("rukou","")
        port = cont.get("port","")
        application = cont.get("application","")
        sgifile = f"{sgi}-file = {rukou}"
        enableThreads = "true" if sgi == "asgi" else "false"
        host = cont.get("host","127.0.0.1")
        protocol = cont.get("protocol","http")
        content = f"""[uwsgi]
# 启用主进程
master=true

# 启用线程
enable-threads = {str(enableThreads).lower()}

# 项目根目录
chdir = {root_path}

# 指定 ASGI或WSGI 应用的文件路径（django）
{sgifile}

# 设置 uWSGI 主进程的PID文件路径
pidfile = {uwsgi_pid}

# 入口文件 application
module = {application}

# 设置模式和监听的端口
{protocol} = {host}:{port}
#socket = {host}:{port}
#socket = /tmp/{self.siteName}.sock

# 设置工作进程数
workers = 4

# 设置线程数
threads = 2

# 调整请求缓冲区大小（默认4KB）
buffer-size = 65536 

# 设置进程和线程的超时
harakiri = 60

# 最大请求数，到了后就会自动重启
max-requests = 5000

# 服务退出或重启，自动删除pid和socket文件
vacuum = True

# 启动时将 uWSGI 设置为后台守护进程，并指定日志文件路径
daemonize = {log_uwsgi}
#disable-logging=true

# 设置 uWSGI 服务的用户和组
uid = {start_user}
gid = {start_user}

# 指定虚拟环境目录
virtualenv = {self.pyenv_path}
"""
        return content
    
    def default_gunicorn_config(self):
        """
        gunicorn配置
        @author lybbn <2024-11-22>
        @param: cont 配置项
        """
        cont = self.project_config
        conf = self.get_conf_path()
        log_base_path = conf['log_base_path']
        gunicorn_pid = conf['gunicorn_pid']
        root_path = self.sitePath
        start_user = cont.get("start_user","root")
        sgi = cont.get("sgi","wsgi")
        rukou = cont.get("rukou","")
        port = cont.get("port","")
        application = cont.get("application","")
        worker_class = "uvicorn.workers.UvicornWorker" if sgi == "asgi" else "sync"
        host = cont.get("host","127.0.0.1")
        content = f"""#gunicorn配置文件（linux部署）
# coding:utf-8

import multiprocessing

# 并行工作进程数,cpu数量*2 推荐,一般建议设置为 CPU 核心数的 2-4 倍
workers = multiprocessing.cpu_count() * 2

# 指定每个进程开启的线程数（适用于异步工作模式）,只在使用异步模式时有效
threads = 2

#启动用户
user = '{start_user}'

# 启动工作模式协程，此处使用与uvicorn配合使用 uvicorn.workers.UvicornWorker（支持ASGI）
worker_class = '{worker_class}'

# 设置最大并发量（每个worker处理请求的工作线程数，正整数，默认为1）
worker_connections = 10000

# 最大客户端并发数量，默认情况下这个值为1000。此设置将影响gevent和eventlet工作模式
# 每个工作进程将在处理max_requests请求后自动重新启动该进程
max_requests = 10000
max_requests_jitter = 200

# 绑定的ip与端口
bind = '{host}:{port}'

# 设置守护进程,将进程交给第三方管理
daemon = 'false'

# 设置进程文件目录（用于停止服务和重启服务，请勿删除）
pidfile = '{gunicorn_pid}'

# 设置访问日志和错误信息日志路径,设置='-'表示不记录，只输出到控制台
accesslog = '{log_base_path}/gunicorn_access.log'
errorlog = '{log_base_path}/gunicorn_error.log'

# 日志级别，这个日志级别指的是错误日志的级别，而访问日志的级别无法设置
# debug:调试级别，记录的信息最多；
# info:普通级别；
# warning:警告消息；
# error:错误消息；
# critical:严重错误消息；
loglevel = 'info'

# 设置gunicorn访问日志格式，错误日志无法设置
access_log_format = '' # worker_class 为 uvicorn.workers.UvicornWorker 时，日志格式为Django的loggers

# 监听队列
backlog = 512
#进程名
proc_name = '{self.siteName}_gunicorn_process'

# 设置超时时间60s，默认为30s。按自己的需求进行设置timeout = 60
timeout = 60

# 超时重启
graceful_timeout = 300

# 在keep-alive连接上等待请求的秒数，默认情况下值为2。一般设定在1~5秒之间。
keepalive = 3
"""
        return content
    
    def sync_db_to_conf(self):
        """
        同步数据库配置到uwsgi和gunicorn的配置文件
        @author lybbn <2024-12-02>
        @param: cont 配置项
        """
        cont = self.project_config
        conf = self.get_conf_path()
        start_method = cont.get("start_method","")#当前使用的启动方式
        try:
            if start_method in ["uwsgi","gunicorn"]:
                port = str(cont['port'])
                protocol = cont['protocol']
                host = cont['host']
                sgi = cont['sgi']
                rukou = cont['rukou']
                application = cont['application']
                start_user = cont['start_user']
                jianting_str = f"{host}:{port}"
                if start_method == "uwsgi":
                    config_path = conf['uwsgi_conf_path']
                    if not os.path.exists(config_path):
                        content = self.default_uwsgi_config()
                        WriteFile(config_path,content)
                        return True
                    else:
                        #configobj 保留配置文件注释
                        from configobj import ConfigObj
                        config = ConfigObj(config_path,encoding="utf-8")
                        keySelect = "uwsgi"
                        config[keySelect]['uid'] = start_user
                        config[keySelect]['gid'] = start_user
                        config[keySelect]['module'] = application
                        if sgi == "asgi":
                            if 'wsgi-file' in config.get(keySelect, {}):
                                del config[keySelect]['wsgi-file']
                            config[keySelect]['asgi-file'] = rukou
                        elif sgi == "wsgi":
                            if 'asgi-file' in config.get(keySelect, {}):
                                del config[keySelect]['asgi-file']
                            config[keySelect]['wsgi-file'] = rukou
                        http_p = config.get(keySelect, {}).get('http', "")
                        socket_p = config.get(keySelect, {}).get('socket', "")
                        if http_p:
                            if protocol == "http":
                                config[keySelect]['http'] = jianting_str
                            else:
                                if 'http' in config.get(keySelect, {}):
                                    del config[keySelect]['http']
                                config[keySelect]['socket'] = jianting_str
                        elif socket_p:
                            if protocol == "socket":
                                config[keySelect]['socket'] = jianting_str
                            else:
                                if 'socket' in config.get(keySelect, {}):
                                    del config[keySelect]['socket']
                                config[keySelect]['http'] = jianting_str
                        config.write()
                        return True
                        
                elif start_method == "gunicorn":
                    config_path = conf['gunicorn_conf_path']
                    if not os.path.exists(config_path):
                        content = self.default_gunicorn_config()
                        WriteFile(config_path,content)
                        return True
                    else:
                        conf_content = ReadFile(config_path)
                        user_re = r"user\s*=\s*[^\n]*\n"
                        conf_content = re.sub(user_re, f"user = '{start_user}'\n", conf_content)
                        bind_re = r"bind\s*=\s*[^\n]*\n"
                        conf_content = re.sub(bind_re, f"bind = '{host}:{port}'\n", conf_content)
                        worker_class = "uvicorn.workers.UvicornWorker" if sgi == "asgi" else "sync"
                        worker_class_re = r"worker_class\s*=\s*[^\n]*\n"
                        conf_content = re.sub(worker_class_re, f"worker_class = '{worker_class}'\n", conf_content)
                        WriteFile(config_path,conf_content)
                        return True
                        
        except:
            return False
        return True
    
    def sync_conf_to_db(self):
        """
        同步uwsgi和gunicorn的配置文件到数据库
        @author lybbn <2024-12-01>
        @param: cont 配置项
        """
        cont = self.project_config
        conf = self.get_conf_path()
        start_method = cont.get("start_method","")#当前使用的启动方式
        try:
            if start_method in ["uwsgi","gunicorn"]:
                old_port = int(cont['port'])
                old_protocol = cont['protocol']
                old_host = cont['host']
                old_start_user = cont['start_user']
                old_rukou = cont['rukou']
                old_sgi = cont['sgi']
                old_application = cont['application']
                isDiff = False
                newcont = cont
                if start_method == "uwsgi":
                    config = configparser.ConfigParser()
                    config_path = conf['uwsgi_conf_path']
                    config.read(config_path)
                    keySelect = "uwsgi"
                    http_p = config.get(keySelect, 'http',fallback='')
                    socket_p = config.get(keySelect, 'socket',fallback='')#不支持直接同步socket文件，只同步socket IP+端口形式
                    start_user = config.get(keySelect, 'uid',fallback='root').strip()
                    wsgifile = config.get(keySelect, 'wsgi-file',fallback='')
                    asgifile = config.get(keySelect, 'asgi-file',fallback='')
                    if http_p:
                        http_p_arr = http_p.strip().split(":")
                        port = int(http_p_arr[1])
                        host = http_p_arr[0] if http_p_arr[0] else "127.0.0.1"
                        protocol = "http"
                    elif socket_p:
                        socket_p_arr = socket_p.strip().split(":")
                        if len(socket_p_arr) == 2:
                            port = int(socket_p_arr[1])
                            host = socket_p_arr[0] if socket_p_arr[0] else "127.0.0.1"
                            protocol = "socket"
                        else:
                            port = old_port
                            host = old_host
                            protocol = old_protocol
                    if not start_user == old_start_user:
                        isDiff = True
                        newcont['start_user'] = start_user
                    if not host == old_host:
                        isDiff = True
                        newcont['host'] = host
                    if not protocol == old_protocol:
                        isDiff = True
                        newcont['protocol'] = protocol
                    if not port == old_port:
                        isDiff = True
                        newcont['port'] = port
                    if wsgifile and not wsgifile == old_rukou:
                        isDiff = True
                        newcont['sgi'] = "wsgi"
                        newcont['rukou'] = wsgifile
                        newcont['application'] = PythonClient.get_project_application(cont=newcont)
                    if asgifile and not asgifile == old_rukou:
                        isDiff = True
                        newcont['sgi'] = "asgi"
                        newcont['rukou'] = asgifile
                        newcont['application'] = PythonClient.get_project_application(cont=newcont)
                else:
                    config_path = conf['gunicorn_conf_path']
                    conf_content = ReadFile(config_path)
                    bind_re = r'\n\s?bind\s*=\s*(.+)'
                    bind_res = re.findall(bind_re, conf_content)
                    bind = (bind_res[0]).strip().strip("'") if bind_res else ""
                    bind_arr = bind.strip().split(":")
                    port = int(bind_arr[1])
                    host = bind_arr[0] if bind_arr[0] else "127.0.0.1"
                    protocol = "http"
                    user_re = r'\n\s?user\s*=\s*(.+)'
                    user_res = re.findall(user_re, conf_content)
                    start_user = (user_res[0]).strip().strip("'") if user_res else "root"
                    worker_class_re = r'\n\s?worker_class\s*=\s*(.+)'
                    worker_class_res = re.findall(worker_class_re, conf_content)
                    worker_class = (worker_class_res[0]).strip().strip("'") if worker_class_res else "sync"
                    sgi = "asgi" if worker_class == "uvicorn.workers.UvicornWorker" else "wsgi"
                    if not start_user == old_start_user:
                        isDiff = True
                        newcont['start_user'] = start_user
                    if not host == old_host:
                        isDiff = True
                        newcont['host'] = host
                    if not protocol == old_protocol:
                        isDiff = True
                        newcont['protocol'] = protocol
                    if not port == old_port:
                        isDiff = True
                        newcont['port'] = port
                    if not sgi == old_sgi:
                        isDiff = True
                        newcont['sgi'] = sgi
                        newcont['application'] = PythonClient.get_project_application(cont=newcont,sgi=sgi)
                if isDiff:Sites.objects.filter(name=self.siteName).update(project_cfg=newcont)
        except:
            return False
        return True
        
    def get_run_script_name(self):
        """
        取运行脚本名称
        @author lybbn <2024-12-01>
        @param: cont 配置项
        """
        script_name = ""
        cont = self.project_config
        start_method = cont.get("start_method","")
        if self.is_windows:
            if start_method in ["commnad"]:
                script_name = f"{self.siteName}_cmd.bat"
            else:
                script_name = f"{self.siteName}_{start_method}.bat"
        else:
            if start_method in ["commnad"]:
                script_name = f"{self.siteName}_cmd.sh"
            else:
                script_name = f"{self.siteName}_{start_method}.sh"
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
        start_method = cont.get("start_method","")
        start_command = cont.get("start_command","")
        application = cont.get("application","")
        try:
            port = int(cont.get("port",0))
        except:
            port = 0
        host = cont.get("host","127.0.0.1")
        if self.is_windows:
            log_path = conf[f'log_{start_method}']
            command_line = ""
            if start_method in ["command"]:
                command_line = f"{start_command} >> {log_path} 2>&1"
            elif start_method =="daphne":
                command_line = f"{self.pyenv_path}/bin/daphne -b {host} -p {port} --proxy-headers {application} >> {log_path} 2>&1"
            content = f"""
@echo off
chcp 65001 > nul
cd /d {self.sitePath}
venv\Scripts\activate
{command_line}
"""
        else:
            command_line = ""
            if start_method in ["command"]:
                log_path = conf['log_command']
                command_line = f"nohup {start_command} &>> {log_path} &"
            elif start_method =="gunicorn":
                gunicorn_conf_path = conf['gunicorn_conf_path']
                log_error_path = conf['log_error_gunicorn']
                log_access_gunicorn = conf['log_access_gunicorn']
                command_line = f"nohup gunicorn -c {gunicorn_conf_path} {application} &>> {log_error_path} &"
            elif start_method =="uwsgi":
                uwsgi_conf_path = conf['uwsgi_conf_path']
                log_path = conf['log_uwsgi']
                command_line = f"uwsgi -d --ini {uwsgi_conf_path}"
            elif start_method =="daphne":
                log_path = conf['log_daphne']
                command_line = f"nohup daphne -b {host} -p {port} --proxy-headers {application} &>> {log_path} &"
            if start_method in ["command","daphne"]:
                method_pid = f"{start_method}_pid"
                sitepid = conf[method_pid]
                command_set_pid = f"echo $! > {sitepid}"
            else:
                command_set_pid = ""
            content = f"""#!/bin/bash
LANG=en_US.UTF-8
cd {self.sitePath}
source venv/bin/activate
{command_line}
{command_set_pid}
"""

            script_path = self.get_run_script_path()
            WriteFile(script_path,content)

    def autoStart(self):
        """
        开机启动
        @author lybbn <2024-12-01>
        @param: cont 配置项
        """
        cont = self.project_config
        autostart = cont.get("autostart",False)
        if autostart:
            res = self.start_site()
            return res
        return True
            
        