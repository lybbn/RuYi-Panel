#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-11-28
# +-------------------------------------------------------------------
# | EditDate: 2024-11-28
# +-------------------------------------------------------------------

# ------------------------------
# supervisor项目管理
#supervisorctl status processname    # 查看指定进程的状态
#supervisorctl start all             # 启动所有进程
#supervisorctl start processname     # 启动指定进程
#supervisorctl stop all              # 关闭所有进程
#supervisorctl stop processname      # 关闭指定进程
#supervisorctl restart processname   # 重启指定进程
#supervisorctl shutdown              # 关闭supervisord
#supervisorctl clear 进程名           # 清空进程日志
#supervisorctl                       # 进入到交互模式下。使用help查看所有命令
#supervisorctl reload # 载入最新的配置文件，停止原有进程并按新的配置启动、管理所有进程
#supervisorctl update # 根据最新的配置文件，启动新配置或有改动的进程，配置没有改动的进程不会受影响而重启
# ------------------------------
import os,time
from configparser import ConfigParser
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import GetSoftList,get_parameter_dic,current_os,RunCommand,WriteFile,ReadFile
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.install.supervisor import get_supervisor_path_info,is_supervisor_running,Reload_Supervisor
from utils.install.install_soft import Ry_Reload_Soft
from apps.syslogs.logutil import RuyiAddOpLog
from utils.server.system import system

class RYSupervisorManageView(CustomAPIView):
    """
    get:
    获取Supervisor项目信息
    post:
    设置Supervisor项目
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        status = str(reqData.get("status","")).lower()
        search = str(reqData.get("search","")).lower()
        is_windows = True if current_os == 'windows' else False
        data = Get_Supervisor_Process_List(is_windows=is_windows)
        datas = []
        if status:
            for d in data:
                if status == str(d['status']).lower():
                    datas.append(d)
            data = datas
        datasr = []
        if search:
            for d in data:
                if search in str(d['name']).lower():
                    datasr.append(d)
            data = datasr
        return DetailResponse(data=data)
        
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "add_process":
            name = reqData.get("name","")
            if not name or name in ["all","ERROR"]:return ErrorResponse(msg="名称不能为空或[all、ERROR]")
            command = reqData.get("command","")
            if not command:return ErrorResponse(msg="启动命令不能为空")
            path = reqData.get("path","")
            user = reqData.get("user","root")
            if not os.path.exists(path) or not os.path.isdir(path):
                return ErrorResponse(msg='项目目录不存在')
            if not is_windows:
                if not user:user="root"
            else:
                user = ""
            process_ini_name = name+".ini"
            inis = Get_Supervisor_INIS()
            if process_ini_name in inis:return ErrorResponse(msg=f"【{name}】进程名已存在，请更换！")
            Create_Process_Daemon(ini_name=process_ini_name,cont=reqData)
            RuyiAddOpLog(request,msg=f"【软件商店】-【添加守护进程】=> {name}",module="softmg")
            Reload_Supervisor(is_windows=is_windows,update=True)
            return DetailResponse(msg="添加成功")
        elif action == "edit_process":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="名称不能为空")
            command = reqData.get("command","")
            if not command:return ErrorResponse(msg="启动命令不能为空")
            path = reqData.get("path","")
            user = reqData.get("user","root")
            if not os.path.exists(path) or not os.path.isdir(path):
                return ErrorResponse(msg='项目目录不存在')
            if not is_windows:
                if not user:user="root"
            else:
                user = ""
            process_ini_name = name+".ini"
            inis = Get_Supervisor_INIS()
            if process_ini_name not in inis:return ErrorResponse(msg=f"【{name}】名称不存在")
            isok = Edit_Process_Daemon(ini_name=process_ini_name,cont=reqData)
            if not isok:return ErrorResponse(msg="修改错误")
            RuyiAddOpLog(request,msg=f"【软件商店】-【编辑守护进程】=> {name}",module="softmg")
            Reload_Supervisor(is_windows=is_windows,update=True)
            return DetailResponse(msg="修改成功")
        elif action == "del_process":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="名称不能为空")
            process_ini_name = name+".ini"
            inis = Get_Supervisor_INIS()
            if process_ini_name not in inis:return ErrorResponse(msg=f"【{name}】名称不存在")
            isok = Del_Process_Daemon(name=name,is_windows=is_windows)
            if not isok:return ErrorResponse(msg="删除错误")
            RuyiAddOpLog(request,msg=f"【软件商店】-【删除守护进程】=> {name}",module="softmg")
            Reload_Supervisor(is_windows=is_windows,update=True)
            return DetailResponse(msg="删除成功")
        elif action == "set_status":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="参数错误")
            status = reqData.get("status","")
            if status not in ["start","stop","restart"]:return ErrorResponse(msg="状态参数错误")
            isok,msg = Supervisor_Process_status_Operate(is_windows=is_windows,action=status,process_name=name)
            if not isok:return ErrorResponse(msg=msg)
            time.sleep(0.5)
            res = Get_Supervisor_Process_List(is_windows=is_windows,process_name=name)
            if not res:return ErrorResponse(msg=f"{status}失败")
            if res[0]['error']:return ErrorResponse(msg=f"{status}失败：{res[0]['error']}")
            RuyiAddOpLog(request,msg=f"【软件商店】-【守护进程】=> {status} 进程 {name}",module="softmg")
            return DetailResponse(msg="设置成功")
        elif action == "get_conf":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="参数错误")
            data = get_supervisor_process_conf(name=name)
            return DetailResponse(data=data,msg="success")
        elif action == "save_conf":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="参数错误")
            conf = reqData.get("conf","")
            if not conf:return ErrorResponse(msg="配置不能为空")
            data = save_supervisor_process_conf(name=name,conf=conf)
            RuyiAddOpLog(request,msg=f"【软件商店】-【守护进程】=> 修改 {name} 配置",module="softmg")
            Reload_Supervisor(is_windows=is_windows,update=True)
            return DetailResponse(data=data,msg="success")
        elif action == "get_process_log":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="参数错误")
            res = Get_Supervisor_Process_List(is_windows=is_windows,process_name=name)
            if not res:return DetailResponse(data="",msg="success")
            num = 2000
            data = system.GetFileLastNumsLines(res[0]['stdout_logfile'],num)
            return DetailResponse(data=data,msg="success")
        return ErrorResponse(msg="类型错误")

def Supervisor_Process_status_Operate(is_windows=True,action="stop",process_name=None):
    """
    @name 指定进程状态管理
    @author lybbn<2024-11-28>
    """
    if action not in ["stop","start","restart","reload","reread","update"]:return False,"类型错误"
    conf = get_supervisor_path_info()
    supervisorctl_path =conf['w_supervisorctl'] if is_windows else conf['l_supervisorctl']
    config_path = conf['w_config_path'] if is_windows else conf['l_config_path']
    if is_supervisor_running(is_windows=is_windows):
        res,err,code = RunCommand(f"{supervisorctl_path} -c {config_path} {action} {process_name}",returncode=True)
        if not err or code == 0:
            return True,"ok"
        else:
            return False,err
    return False,"supervisor服务未运行"
    
def Get_Supervisor_Process_List(is_windows=True,process_name=""):
    """
    @name 取系统守护进程列表
    @param process_name 如果指定则获取指定的进程信息，不指定则获取所有的
    @author lybbn<2024-11-28>
    正常
    ruyitest:ruyitest_00         RUNNING   pid 87098, uptime 20 days, 22:10:08
    异常
    ruyitest:ruyitest_00         FATAL     Exited too quickly (process log may have details)
    """
    conf = get_supervisor_path_info()
    supervisorctl_path =conf['w_supervisorctl'] if is_windows else conf['l_supervisorctl']
    config_path = conf['w_config_path'] if is_windows else conf['l_config_path']
    configs_path = conf['configs_path']
    data = []
    process_name_list = []
    if is_supervisor_running(is_windows=is_windows):
        if process_name:process_name=process_name+":"
        res,err,code = RunCommand(f"{supervisorctl_path} -c {config_path} status {process_name}",returncode=True)
        if not err or code == 0:
            if process_name and "ERROR" in res:return []
            p_list = res.split("\n")
            for p in p_list:
                if p:
                    p_l = p.strip().split()
                    if p_l:
                        p_info = {}
                        program_name = p_l[0].split(':')[0].strip()
                        if program_name in process_name_list: continue
                        process_name_list.append(program_name)
                        p_info["name"] = program_name
                        status_name = p_l[1].strip()#RUNNING表示运行中，FATAL 表示运行失败，STARTING表示正在启动, STOPED表示任务已停止
                        p_info["status_name"] = status_name
                        p_info["error"] = ""
                        if status_name == "RUNNING":
                            p_info["status"] = True
                            p_info["pid"] = p_l[3][:-1]
                        else:
                            if status_name == "FATAL":p_info["error"]=" ".join(p_l[2:])
                            p_info["status"] = False
                            p_info["pid"] = ""
                        cfg_path = os.path.join(configs_path,program_name + ".ini")
                        if not os.path.exists(cfg_path): continue
                        config = ConfigParser()
                        # 读取配置文件
                        config.read(cfg_path)
                        Section = f"program:{program_name}"
                        p_info['path'] = config.get(Section, 'directory', fallback='')
                        p_info['command'] = config.get(Section, 'command', fallback='')
                        p_info['user'] = config.get(Section, 'user', fallback='')
                        p_info['priority'] = config.get(Section, 'priority', fallback='')
                        p_info['stdout_logfile'] = config.get(Section, 'stdout_logfile', fallback='')
                        p_info['nums'] = int(config.get(Section, 'numprocs', fallback=1))
                        data.append(p_info)
    return data

def Get_Supervisor_INIS():
    """
    @name 取ini配置
    @author lybbn<2024-11-28>
    """
    conf = get_supervisor_path_info()
    configs_path = conf['configs_path']
    if not os.path.exists(configs_path):
        os.makedirs(configs_path)
    config_inis = os.listdir(configs_path)
    data = []
    for f in config_inis:
        ini_path = os.path.join(configs_path,f)
        if os.path.isfile(ini_path) and ".ini" in f:
            data.append(f)
    return data
  
def Create_Process_Daemon(ini_name=None,cont={}):
    """
    @name 新建进程守护
    @author lybbn<2024-11-28>
    """
    conf = get_supervisor_path_info()
    logs_path = conf['logs_path']
    if not os.path.exists(logs_path):
        os.makedirs(logs_path)
    name = cont.get("name","")
    command = cont.get("command","")
    path = cont.get("path","")
    user = cont.get("user","")
    nums = int(cont.get("nums",1))
    stdout_logfile = os.path.join(logs_path,f"{name}.out.log")
    user_cfg =f"user={user}" if user else ""
    default_config = f"""[program:{name}]
directory={path}
command={command}
autostart=true
autorestart=true
startsecs=3
redirect_stderr=true
stdout_logfile={stdout_logfile}
stdout_logfile_maxbytes=5MB
stdout_logfile_backups=3
priority=999
numprocs={nums}
process_name=%(program_name)s_%(process_num)02d
{user_cfg}"""
    configs_path = conf['configs_path']
    WriteFile(os.path.join(configs_path,ini_name),default_config)
    
def Edit_Process_Daemon(ini_name=None,cont={}):
    """
    @name 编辑进程守护
    @author lybbn<2024-11-28>
    """
    conf = get_supervisor_path_info()
    configs_path = conf['configs_path']
    conf_path = os.path.join(configs_path,ini_name)
    name = cont.get("name","")
    command = cont.get("command","")
    path = cont.get("path","")
    user = cont.get("user","")
    nums = int(cont.get("nums",1))
    if not os.path.exists(conf_path):return False
    # 创建 configparser 对象
    config = ConfigParser()
    # 读取配置文件
    config.read(conf_path)
    Section = f"program:{name}"
    config.set(Section, 'directory', path)
    config.set(Section, 'command', command)
    config.set(Section, 'numprocs', str(nums))
    config.set(Section, 'directory', path)
    if user:
        config.set(Section, 'user', user)
    with open(conf_path, 'w',encoding="utf-8") as configfile:
        config.write(configfile)
    return True

def Del_Process_Daemon(name=None,is_windows=True):
    """
    @name 删除进程守护
    @author lybbn<2024-11-28>
    """
    Supervisor_Process_status_Operate(is_windows=is_windows,action="stop",process_name=name)
    conf = get_supervisor_path_info()
    configs_path = conf['configs_path']
    conf_path = os.path.join(configs_path,name+".ini")
    logs_path = conf['logs_path']
    stdout_logfile = os.path.join(logs_path,f"{name}.out.log")
    if os.path.isfile(stdout_logfile):
        os.remove(stdout_logfile)
    if os.path.isfile(conf_path):
        os.remove(conf_path)
    return True

def get_supervisor_process_conf(name=None):
    conf = get_supervisor_path_info()
    configs_path = conf['configs_path']
    conf_path = os.path.join(configs_path,name+".ini")
    return ReadFile(conf_path)

def save_supervisor_process_conf(name=None,conf=None):
    conft = get_supervisor_path_info()
    configs_path = conft['configs_path']
    conf_path = os.path.join(configs_path,name+".ini")
    WriteFile(conf_path,content=conf)