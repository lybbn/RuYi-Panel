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
# docker 存储卷管理
# ------------------------------
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic
from utils.jsonResponse import ErrorResponse,DetailResponse,SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.dockerClass import DockerClient

class RYDockerVolumesManageView(CustomAPIView):
    """
    get:
    获取存储卷
    post:
    设置存储卷
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        docker_client = DockerClient()
        page_obj,total_nums,limit,page_number = docker_client.get_volumes_list(cont=reqData)
        return SuccessResponse(data=page_obj,total=total_nums,page=page_number,limit=limit)
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        docker_client = DockerClient()
        reqData['action_type']="volumes"
        if action == "delete":
            id = reqData.get('id',"")
            name = reqData.get('name',"")
            isok,msg = docker_client.delete(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】-【存储卷】=> 删除：{name}:{id}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "add":
            name = reqData.get('name',"")
            isok,msg = docker_client.add(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】-【存储卷】=> 添加：{name}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "prune":
            isok,msg = docker_client.prune(reqData)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg=f"【容器】-【存储卷】=> 清除未使用存储卷",module="dockermg")
            return DetailResponse(msg=msg)
        return ErrorResponse(msg="类型错误")