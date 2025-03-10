#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-17
# +-------------------------------------------------------------------
# | EditDate: 2025-02-17
# +-------------------------------------------------------------------

# ------------------------------
# docker 容器管理
# ------------------------------
import os
import psutil
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic
from utils.jsonResponse import ErrorResponse,DetailResponse,SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.dockerClass import DockerClient

class RYDockerLimitManageView(CustomAPIView):
    """
    get:
    获取系统信息（用于容器最大限制）
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        cpu_count = psutil.cpu_count(logical=False)  # 物理核心数
        logical_cpu_count = psutil.cpu_count(logical=True)  # 逻辑核心数（包括超线程）
        memory = psutil.virtual_memory()
        total_memory = memory.total  # 总内存（字节）
        available_memory = memory.available  # 可用内存（字节）
        data={
            "cpu_count":cpu_count,
            "logical_cpu_count":logical_cpu_count,
            "total_memory":total_memory,
            "available_memory":available_memory
        }
        return DetailResponse(data=data)

class RYDockerContainerManageView(CustomAPIView):
    """
    get:
    获取容器
    post:
    设置容器
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        docker_client = DockerClient()
        page_obj,total_nums,limit,page_number = docker_client.get_local_containers_list(cont=reqData)
        return SuccessResponse(data=page_obj,total=total_nums,page=page_number,limit=limit)
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        docker_client = DockerClient()
        if action == "delete":
            name = reqData.get('name',"")
            if not name:return DetailResponse(msg="缺少参数")
            reqData['action_type']="container"
            isok,msg = docker_client.delete(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】- 删除容器：{name}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "add":
            name = reqData.get('name',"")
            reqData['action_type']="container"
            isok,msg = docker_client.add(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】- 添加容器：{name}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "set_status":
            status = reqData.get("status","")
            name = reqData.get('name',"")
            if not name:return DetailResponse(msg="缺少参数")
            reqData['action_type']="container"
            isok,msg = docker_client.set_status(cont=reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】- {status} => {name}",module="dockermg")
            return DetailResponse(msg=msg)
        return ErrorResponse(msg="类型错误")