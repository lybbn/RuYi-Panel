#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-09-13
# +-------------------------------------------------------------------
# | EditDate: 2024-09-13
# +-------------------------------------------------------------------

# ------------------------------
# 安全 进程管理
# ------------------------------

import re
import psutil
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic,current_os,formatdatetime,RunCommand,ast_convert
from apps.syslogs.logutil import RuyiAddOpLog
from utils.process import ProcessMonitor

def get_all_processes_info(pid_filter=None,name_filter=None,user_filter=None):
    processes_info = []

    for proc in psutil.process_iter(['pid', 'ppid', 'name','exe', 'cmdline', 'num_threads', 'cpu_percent', 'memory_info', 'create_time', 'status', 'username']):
        try:
            memory_info_ps = proc.memory_info()
            memory_full_info_ps = proc.memory_full_info()
            memory_info = {}
            memory_info['rss'] = memory_info_ps.rss
            memory_info['vms'] = memory_info_ps.vms
            memory_info['shared'] = memory_info_ps.shared
            memory_info['text'] = memory_info_ps.text
            memory_info['data'] = memory_info_ps.data
            memory_info['lib'] = memory_info_ps.lib
            memory_info['dirty'] = memory_info_ps.dirty
            memory_info['pss'] = memory_full_info_ps().pss
            memory_info['swap'] = memory_full_info_ps.swap
            
            p_cpus = proc.cpu_times()
            
            # 获取进程信息
            process_info = {
                'pid': proc.info['pid'],  # 进程ID
                'ppid': proc.info['ppid'],  # 父进程ID
                'name': proc.info['name'],  # 进程名称
                'num_threads': proc.info['num_threads'],  # 线程数量
                'cpu_percent': proc['cpu_percent'],
                'memory_info': memory_info,
                'create_time': proc.info['create_time'],  # 启动时间（时间戳）
                'status': proc.info['status'],  # 进程状态
                'connections': proc.net_connections(),
                'username': proc.info['username'],  # 所属用户
                'io_read':proc.io_counters()[0],
                'io_write':proc.io_counters()[1],
                'exe':proc['exe'],
                'cmdline':proc['cmdline'],
            }
            # 过滤条件
            if pid_filter and str(process_info['pid']) != str(pid_filter):
                continue  # 跳过不符合 PID 过滤条件的进程
            if name_filter and name_filter.lower() not in process_info['name'].lower():
                continue  # 跳过不符合名称过滤条件的进程
            if user_filter and user_filter.lower() != process_info['username'].lower():
                continue  # 跳过不符合用户过滤条件的进程
            processes_info.append(process_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 忽略无法访问或已终止的进程
            continue
    return processes_info

def terminate_process(pid):
    """
    终止指定 PID 的进程。
    
    :param pid: 进程ID
    :return: 是否成功终止进程
    """
    try:
        process = psutil.Process(pid)
        process.terminate()  # 发送 SIGTERM 信号
        return True,"终止成功"
    except psutil.NoSuchProcess:
        return False,f"进程 {pid} 不存在"
    except psutil.AccessDenied:
        return False,f"无权限终止进程 {pid}"

def kill_process(pid):
    """
    强制终止指定 PID 的进程。
    
    :param pid: 进程ID
    :return: 是否成功终止进程
    """
    try:
        process = psutil.Process(pid)
        process.kill()  # 发送 SIGKILL 信号
        return True,"终止成功"
    except psutil.NoSuchProcess:
        return False,f"进程 {pid} 不存在"
    except psutil.AccessDenied:
        return False,f"无权限终止进程 {pid}"

class RYSysProcessListView(CustomAPIView):
    """
    get:
    系统进程列表
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        pid_filter = reqData.get("pid_filter",None)
        name_filter = reqData.get("name_filter",None)
        user_filter = reqData.get("user_filter",None)
        process_monitor = ProcessMonitor()
        data = process_monitor.get_processes_list(pid_filter=pid_filter,name_filter=name_filter,user_filter=user_filter)
        return DetailResponse(data=data)
    
class RYSysProcessDetailView(CustomAPIView):
    """
    get:
    系统进程详情
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        pid = reqData.get("pid",None)
        if not pid and str(pid) != '0':return ErrorResponse(msg="缺少参数")
        process_monitor = ProcessMonitor()
        data = process_monitor.get_pid_detail_info(int(pid))
        return DetailResponse(data=data)

class RYSysProcessOperateView(CustomAPIView):
    """
    post:
    系统进程操作
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        pid = reqData.get("pid","")
        if not pid:return ErrorResponse(msg="参数错误")
        if str(pid) == '1':return ErrorResponse(msg="无法终止初始进程")
        pid == int(pid)
        if action == "kill":
            isok,msg = kill_process(pid)
            if isok:
                RuyiAddOpLog(request,msg="【安全】-【进程管理】-【结束】 => %s"%pid,module="safe")
                return DetailResponse(msg=msg)
            else:
                return ErrorResponse(msg=msg)
        
        return ErrorResponse(msg="类型错误")