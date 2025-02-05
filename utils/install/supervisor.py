#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-11-27
# +-------------------------------------------------------------------
# | EditDate: 2024-11-27
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Supervisor 安装/卸载
# ------------------------------

import os
import time
from utils.common import ReadFile,get_python_pip,RunCommandReturnCode,DeleteDir,GetTmpPath,GetInstallPath,WriteFile,DeleteFile,GetLogsPath,RunCommand
from utils.security.files import download_url_file,get_file_name_from_url
import subprocess
import importlib
from utils.server.system import system
from django.conf import settings

def get_supervisor_path_info():
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,"supervisor")
    install_path = root_path+"/supervisor"
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'w_supervisord':'supervisord',
        'w_supervisor_service':'supervisor_service',
        'w_supervisorctl':'supervisorctl',
        'l_supervisorctl':os.path.join(install_abspath_path,'bin','supervisorctl'),
        'l_abspath_supervisord_path':os.path.join(install_abspath_path,'bin','supervisord'),
        'w_config_path':os.path.join(install_abspath_path,"rysupervisord.conf"),
        'l_config_path':os.path.join("/etc","rysupervisord.conf"),
        'configs_path':os.path.join(settings.RUYI_DATA_BASE_PATH,"supervisor"),
        'logs_path':os.path.join(install_abspath_path,"logs"),#所有进程的日志文件夹
        'tmp_abspath_path':os.path.join(install_abspath_path,'tmp'),
    }
    
def supervisor_install_call_back(version={},call_back=None,ok=True):
    if call_back:
        job_id = version['job_id']
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id,version=version,ok=ok)

def check_supervisor_version(softPath=""):
    try:
        if not softPath:
            softPath = "supervisor"
        output = subprocess.check_output([softPath, "--version"], stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        version = output.decode().strip()
        if version:
            return version
        return None
    except:
        return None

def is_supervisor_running(is_windows=True,simple_check=False):
    if is_windows:
        try:
            result = subprocess.run(['sc', 'query', 'supervisord'],stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if 'RUNNING' in result.stdout:
                return True
            else:
                return False
        except:
            return False
    else:
        try:
            result = subprocess.run(['systemctl', 'is-active','rysupervisord'],stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stdout.strip()
            if result.returncode == 0 and "active" == output:
                return True
            else:
                return False
        except:
            return False

def Install_Supervisor(type=2,version={},is_windows=True,call_back=None):
    """
    @name 安装Supervisor
    @parma call_back 为执行回调函数的方法路径
    @author lybbn<2024-11-27>
    """
    try:
        name = version['name']
        log = version.get('log',None)#是否开启日志
        is_write_log = False
        log_path = ""
        if log:
            is_write_log = True
            log_path = os.path.join(os.path.abspath(GetLogsPath()),name,log)
        WriteFile(log_path,"-------------------安装任务已开始-------------------\n",mode='a',write=is_write_log)
        download_url = version.get('url',None)
        WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
        filename = get_file_name_from_url(download_url)
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_supervisor_path_info()
        install_base_directory = soft_paths['root_abspath_path']
        install_directory = soft_paths['install_abspath_path']
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        save_path = os.path.join(save_directory, filename)
        #开始下载
        ok,msg = download_url_file(url=download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
        if not ok:
            WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
            raise ValueError(msg)
        configs_path = soft_paths['configs_path']
        if not os.path.exists(configs_path):
            os.makedirs(configs_path)
        if is_windows:
            WriteFile(log_path,"【%s】下载完成\n"%filename,mode='a',write=is_write_log)
            WriteFile(log_path,"开始安装...%s\n",mode='a',write=is_write_log)
            subprocess.run([get_python_pip()['pip'], 'install',filename],check=True,text=True,capture_output=True,cwd=save_directory)
            from shutil import which as whichCommand
            supervisord_path = whichCommand("supervisord")
            if not supervisord_path:
                raise Exception("安装失败，无法执行安装后的supervisor")
            WriteFile(log_path,"开始生成配置文件...%s\n",mode='a',write=is_write_log)
            WriteFile(soft_paths['w_config_path'],Default_Supervisor_Windows_Config())
            tmp_abspath_path = soft_paths['tmp_abspath_path']
            if not os.path.exists(tmp_abspath_path):
                os.makedirs(tmp_abspath_path)
            WriteFile(log_path,"开始生成安装服务...%s\n",mode='a',write=is_write_log)
            subprocess.run([get_python_pip()['python'], '-m',"supervisor.services","install","-c",soft_paths['w_config_path']],check=True,text=True,capture_output=True)
            # 新建版本文件
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
        else:
            r_process = subprocess.Popen(['bash', GetInstallPath()+'/ruyi/utils/install/bash/supervisor.sh','install',version['c_version'],filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,bufsize=4096)
            # 持续读取输出
            while True:
                r_output = r_process.stdout.readline()
                if r_output == '' and r_process.poll() is not None:
                    break
                if r_output:
                    WriteFile(log_path,f"{r_output.strip()}\n",mode='a',write=is_write_log)
            # 获取标准错误
            r_stderr = r_process.stderr.read()
            if r_stderr:
                if not os.path.exists(soft_paths['l_abspath_supervisord_path']):
                    raise Exception(r_stderr.strip())
            tmp_abspath_path = soft_paths['tmp_abspath_path']
            if not os.path.exists(tmp_abspath_path):
                os.makedirs(tmp_abspath_path)
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
        
        # 删除下载的文件
        DeleteFile(save_path,empty_tips=False)
        WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        WriteFile(log_path,"启动中...\n",mode='a',write=is_write_log)
        isrunning = Start_Supervisor(is_windows=is_windows)
        if not isrunning:
            raise Exception("无法启动supervisor")
        WriteFile(log_path,"启动成功\n",mode='a',write=is_write_log)
        version['install_path'] = install_directory
        supervisor_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        supervisor_install_call_back(version=version,call_back=call_back,ok=False)
        return False
    
def Uninstall_Supervisor(is_windows=True):
    """
    @name 卸载supervisor
    @author lybbn<2024-11-27>
    """
    soft_paths = get_supervisor_path_info()
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            time.sleep(0.1)
            RunCommand("supervisor_service remove")
            subprocess.run([get_python_pip()['pip'], 'uninstall',"supervisor-win","-y"],check=True,text=True,capture_output=True)
            system.ForceRemoveDir(install_path)
    else:
        try:
            subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","supervisor.sh"),'uninstall'], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True

def Start_Supervisor(is_windows=True):
    """
    @name 启动Supervisor
    @author lybbn<2024-11-22>
    """
    if is_windows:
        try:
            if not is_supervisor_running(is_windows=True):
                code = RunCommandReturnCode("supervisor_service start")
                return True if code == 0 else False
            return True
        except Exception as e:
            raise ValueError(f"启动Supervisor时发生错误: {e}")
    else:
        r_status = False
        try:
            if not is_supervisor_running(is_windows=False,simple_check=True):
                subprocess.run(["sudo", "systemctl", "start", "rysupervisord"], check=True)
            else:
                r_status = True
            time.sleep(0.5)
            if not r_status and is_supervisor_running(is_windows=False):
                r_status = True
        except Exception as e:
            raise ValueError(f"启动Supervisor时发生错误: {e}")
        if not r_status:
            raise ValueError(f"Supervisor启动错误")
        return r_status

def Stop_Supervisor(is_windows=True):
    """
    @name 停止Supervisor
    @author lybbn<2024-11-22>
    """
    if is_windows:
        try:
            if is_supervisor_running(is_windows=True):
                code = RunCommandReturnCode("supervisor_service stop")
                return True if code == 0 else False
            return True
        except subprocess.CalledProcessError as e:
            raise ValueError(f"停止Supervisor时发生错误: {e}")
    else:
        if is_supervisor_running(is_windows=is_windows):
            try:
                subprocess.run(["sudo", "systemctl", "stop", "rysupervisord"], check=True)
                time.sleep(1)
                if is_supervisor_running(is_windows=False):
                    return False
                else:
                    return True
            except Exception as e:
                raise ValueError(f"停止Supervisor时发生错误: {e}")
    return True
        
def Restart_Supervisor(is_windows=True):
    """
    @name 重启Supervisor
    @author lybbn<2024-11-22>
    """
    if is_windows:
        RunCommand("supervisor_service restart")
    else:
        RunCommand("systemctl restart rysupervisord")
    return True

def Reload_Supervisor(is_windows=True,update=False):
    """
    @name 重载Supervisor（是否使用update）
    @author lybbn<2024-11-22>
    """
    try:
        if is_windows:
            command = ["supervisor_service","update"]
            code = RunCommandReturnCode(command)
        else:
            if not update:
                res,err,code = RunCommand("systemctl reload rysupervisord",returncode=True)
            else:
                soft_paths = get_supervisor_path_info()
                conf_path = RY_GET_SUPERVISOR_CONFIG_PATH(is_windows=is_windows)
                supervisorctl = soft_paths['l_supervisorctl']
                res,err,code = RunCommand(f"/usr/local/ruyi/python/bin/python3 /ruyi/server/supervisor/bin/supervisorctl -c {conf_path} update",returncode=True)
        return True if code == 0 else False
    except Exception as e:
        raise ValueError(f"重载Supervisor时发生错误: {e}")
    
def RY_GET_SUPERVISOR_CONF_OPTIONS(is_windows=True):
    conf_path = RY_GET_SUPERVISOR_CONFIG_PATH(is_windows=is_windows)
    import configparser
    config = configparser.ConfigParser()
    config.read(conf_path)
    result = {
        "logfile":""
    }
    try:
        result['logfile'] = config.get('supervisord', 'logfile').split(";")[0].strip()
    except:
        pass
    return result

def RY_GET_SUPERVISOR_CONFIG_PATH(is_windows=True):
    soft_paths = get_supervisor_path_info()
    conf_path = soft_paths['w_config_path'] if is_windows else soft_paths['l_config_path']
    return conf_path

def RY_GET_SUPERVISOR_CONF(is_windows=True):
    conf_path = RY_GET_SUPERVISOR_CONFIG_PATH(is_windows=is_windows)
    return ReadFile(conf_path)

def RY_SAVE_SUPERVISOR_CONF(conf="",is_windows=True):
    conf_path = RY_GET_SUPERVISOR_CONFIG_PATH(is_windows=is_windows)
    WriteFile(conf_path,content=conf)

def Default_Supervisor_Windows_Config():
    """
    @name supervisor windows 默认配置
    @author lybbn<2024-11-27>
    """
    soft_paths = get_supervisor_path_info()
    configs_path = soft_paths['configs_path']
    tmp_abspath_path = soft_paths['tmp_abspath_path']
    content = f"""; Sample supervisor config file.
;
; For more information on the config file, please see:
; http://supervisord.org/configuration.html

;[inet_http_server]         ; inet (TCP) server disabled by default
;port=127.0.0.1:9001        ; ip_address:port specifier, *:port for all iface
;username=user              ; default is no username (open server)
;password=123               ; default is no password (open server)

[supervisord]
logfile={tmp_abspath_path}\\supervisord.log ; (main log file;default $CWD/supervisord.log)
logfile_maxbytes=50MB               ; (max main logfile bytes b4 rotation;default 50MB)
logfile_backups=10                  ; (num of main logfile rotation backups;default 10)
loglevel=info                       ; (log level;default info; others: debug,warn,trace)
pidfile={tmp_abspath_path}\\supervisord.pid ; (supervisord pidfile;default supervisord.pid)
nodaemon=false                      ; (start in foreground if true;default false)
silent=false                 ; no logs to stdout if true; default false
minfds=1024                         ; (min. avail startup file descriptors;default 1024)
minprocs=200                        ; (min. avail process descriptors;default 200)
;umask=022                          ; (process file creation umask;default 022)
;user=chrism                        ; (default is current user, required if root)
;identifier=supervisor              ; (supervisord identifier, default is 'supervisor')
;directory=%(ENV_TMP)s              ; (default is not to cd during start)
;nocleanup=true                     ; (don't clean up tempfiles at start;default false)
;childlogdir=%(ENV_TMP)s            ; ('AUTO' child log dir, default $TEMP)
;environment=KEY="value"            ; (key value pairs to add to environment)
;strip_ansi=false                   ; (strip ansi escape codes in logs; def. false)
;delaysecs=0.5                      ; (delay system processing per seconds; def. 0.5)

; The rpcinterface:supervisor section must remain in the config file for
; RPC (supervisorctl/web interface) to work.  Additional interfaces may be
; added by defining them in separate [rpcinterface:x] sections.

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

; The supervisorctl section configures how supervisorctl will connect to
; supervisord.  configure it match the settings in either the unix_http_server
; or inet_http_server section.

[supervisorctl]
;serverurl=http://127.0.0.1:9001 ; use an http:// url to specify an inet socket
;username=chris              ; should be same as in [*_http_server] if set
;password=123                ; should be same as in [*_http_server] if set
;prompt=mysupervisor         ; cmd line prompt (default "supervisor")
;history_file=~/.sc_history  ; use readline history if available

; The sample program section below shows all possible program subsection values.
; Create one or more 'real' program: sections to be able to control them under
; supervisor.

;[program:theprogramname]
;command=cmd.exe               ; the program (relative uses PATH, can take args)
;process_name=%(program_name)s ; process_name expr (default %(program_name)s)
;numprocs=1                    ; number of processes copies to start (def 1)
;directory=%(ENV_TMP)s         ; directory to cwd to before exec (def no cwd)
;umask=022                     ; umask for process (default None)
;priority=999                  ; the relative start priority (default 999)
;autostart=true                ; start at supervisord start (default: true)
;startsecs=1                   ; # of secs prog must stay up to be running (def. 1)
;startretries=3                ; max # of serial start failures when starting (default 3)
;autorestart=unexpected        ; when to restart if exited after running (def: unexpected)
;exitcodes=0                   ; 'expected' exit codes used with autorestart (default 0)
;stopsignal=QUIT               ; signal used to kill process (default TERM)
;stopwaitsecs=10               ; max num secs to wait b4 SIGKILL (default 10)
;stopasgroup=false             ; send stop signal to the UNIX process group (default false)
;killasgroup=false             ; SIGKILL the UNIX process group (def false)
;user=chrism                   ; setuid to this UNIX account to run the program
;redirect_stderr=true          ; redirect proc stderr to stdout (default false)
;stdout_logfile=a\\path        ; stdout log path, NONE for none; default AUTO
;stdout_logfile_maxbytes=1MB   ; max # logfile bytes b4 rotation (default 50MB)
;stdout_logfile_backups=10     ; # of stdout logfile backups (0 means none, default 10)
;stdout_capture_maxbytes=1MB   ; number of bytes in 'capturemode' (default 0)
;stdout_events_enabled=false   ; emit events on stdout writes (default false)
;stdout_syslog=false           ; send stdout to syslog with process name (default false)
;stderr_logfile=a\\path        ; stderr log path, NONE for none; default AUTO
;stderr_logfile_maxbytes=1MB   ; max # logfile bytes b4 rotation (default 50MB)
;stderr_logfile_backups=10     ; # of stderr logfile backups (0 means none, default 10)
;stderr_capture_maxbytes=1MB   ; number of bytes in 'capturemode' (default 0)
;stderr_events_enabled=false   ; emit events on stderr writes (default false)
;stderr_syslog=false           ; send stderr to syslog with process name (default false)
;environment=A="1",B="2"       ; process environment additions (def no adds)
;serverurl=AUTO                ; override serverurl computation (childutils)
;cpupriority=normal            ; cpu priority; .def normal; others: realtime, high, above, below, idle
;cpuaffinity=0                 ; number of cores of cpu is usable by process. def 0 (all cores)
;systemjob=true                ; if process die with supervisor. def true

; The sample eventlistener section below shows all possible eventlistener
; subsection values.  Create one or more 'real' eventlistener: sections to be
; able to handle event notifications sent by supervisord.

;[eventlistener:theeventlistenername]
;command=path\\eventlistener   ; the program (relative uses PATH, can take args)
;process_name=%(program_name)s ; process_name expr (default %(program_name)s)
;numprocs=1                    ; number of processes copies to start (def 1)
;events=EVENT                  ; event notif. types to subscribe to (req'd)
;buffer_size=10                ; event buffer queue size (default 10)
;directory=%(ENV_TMP)s         ; directory to cwd to before exec (def no cwd)
;umask=022                     ; umask for process (default None)
;priority=-1                   ; the relative start priority (default -1)
;autostart=true                ; start at supervisord start (default: true)
;startsecs=1                   ; # of secs prog must stay up to be running (def. 1)
;startretries=3                ; max # of serial start failures when starting (default 3)
;autorestart=unexpected        ; autorestart if exited after running (def: unexpected)
;exitcodes=0                   ; 'expected' exit codes used with autorestart (default 0)
;stopsignal=TERM               ; signal used to kill process (default TERM)
;stopwaitsecs=10               ; max num secs to wait b4 SIGKILL (default 10)
;stopasgroup=false             ; send stop signal to the UNIX process group (default false)
;killasgroup=false             ; SIGKILL the UNIX process group (def false)
;user=chrism                   ; setuid to this UNIX account to run the program
;redirect_stderr=false         ; redirect_stderr=true is not allowed for eventlisteners
;stdout_logfile=a\\path        ; stdout log path, NONE for none; default AUTO
;stdout_logfile_maxbytes=1MB   ; max # logfile bytes b4 rotation (default 50MB)
;stdout_logfile_backups=10     ; # of stdout logfile backups (0 means none, default 10)
;stdout_events_enabled=false   ; emit events on stdout writes (default false)
;stdout_syslog=false           ; send stdout to syslog with process name (default false)
;stderr_logfile=a\\path        ; stderr log path, NONE for none; default AUTO
;stderr_logfile_maxbytes=1MB   ; max # logfile bytes b4 rotation (default 50MB)
;stderr_logfile_backups=10     ; # of stderr logfile backups (0 means none, default 10)
;stderr_events_enabled=false   ; emit events on stderr writes (default false)
;stderr_syslog=false           ; send stderr to syslog with process name (default false)
;environment=A="1",B="2"       ; process environment additions
;serverurl=AUTO                ; override serverurl computation (childutils)

; The sample group section below shows all possible group values.  Create one
; or more 'real' group: sections to create "heterogeneous" process groups.

;[group:thegroupname]
;programs=progname1,progname2  ; each refers to 'x' in [program:x] definitions
;priority=999                  ; the relative start priority (default 999)

; The [include] section can just contain the "files" setting.  This
; setting can list multiple files (separated by whitespace or
; newlines).  It can also contain wildcards.  The filenames are
; interpreted as relative to this file.  Included files *cannot*
; include files themselves.

[include]
files = {configs_path}\\*.ini
"""
    return content