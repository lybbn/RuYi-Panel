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
# 安全 网络连接
# ------------------------------

import re
import psutil
import socket
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic
from apps.syslogs.logutil import RuyiAddOpLog

def safe_get_ip(addr):
    """安全获取地址信息，兼容新旧版本 psutil"""
    if hasattr(addr, 'ip'):  # 新版本
        return f"{addr.ip}"
    elif isinstance(addr, tuple) and len(addr) >0:  # 旧版本
        return f"{addr[0]}"
    return "N/A"

def safe_get_port(addr):
    """安全获取端口信息，兼容新旧版本 psutil"""
    if hasattr(addr, 'port'):  # 新版本
        return f"{addr.port}"
    elif isinstance(addr, tuple) and len(addr) == 2:  # 旧版本
        return f"{addr[1]}"
    return ""

def get_all_network_info(pid_filter=None,name_filter=None,port_filter=None):
    data = []
    connections = psutil.net_connections(kind='inet')
    for conn in connections:
        l_port = ""
        r_port = ""
        laddr = ""
        raddr = ""
        # 解析地址信息
        if conn.laddr:
            l_port = safe_get_port(conn.laddr)
            r_port = safe_get_port(conn.raddr)
            laddr = f"{safe_get_ip(conn.laddr)}:{l_port}" if l_port else safe_get_ip(conn.laddr)
            raddr = f"{safe_get_ip(conn.raddr)}:{r_port}" if r_port else safe_get_ip(conn.raddr)
        
        # 获取进程信息
        pid = conn.pid
        pname = psutil.Process(pid).name() if pid else ""
        simplified_proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
        # 过滤条件
        if pid_filter and str(pid) != str(pid_filter):
            continue
        if name_filter and name_filter.lower() not in pname.lower():
            continue
        if port_filter and str(port_filter) not in [str(l_port),str(r_port)]:
            continue
        
        data.append({
            "protocol":simplified_proto,
            "laddr":laddr,
            "raddr":raddr,
            "status":conn.status if hasattr(conn, 'status') else "",
            "pid":pid,
            "name":pname
        })
    return data

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

class RYSysNetworkListView(CustomAPIView):
    """
    get:
    系统网络连接列表
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        pid_filter = reqData.get("pid_filter",None)
        name_filter = reqData.get("name_filter",None)
        port_filter = reqData.get("port_filter",None)
        data = get_all_network_info(pid_filter=pid_filter,name_filter=name_filter,port_filter=port_filter)
        return DetailResponse(data=data)

class RYSysNetworkOperateView(CustomAPIView):
    """
    post:
    系统网络连接操作
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
                RuyiAddOpLog(request,msg="【安全】-【网络连接】-【结束进程】 => %s"%pid,module="safe")
                return DetailResponse(msg=msg)
            else:
                return ErrorResponse(msg=msg)
        elif action == "block":
            isok,msg = kill_process(pid)
            if isok:
                RuyiAddOpLog(request,msg="【安全】-【网络连接】-【阻断连接】 => %s"%pid,module="safe")
                return DetailResponse(msg=msg)
            else:
                return ErrorResponse(msg=msg)
        return ErrorResponse(msg="类型错误")