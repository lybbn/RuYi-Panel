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
# docker项目管理
# ------------------------------
import os
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic,current_os,check_is_url
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.install.install_soft import Check_Soft_Installed
from apps.sysshop.models import RySoftShop
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.dockerClass import DockerClient

class RYDockerManageView(CustomAPIView):
    """
    get:
    获取docker信息
    post:
    设置docker项目
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "get_settings":
            docker_client = DockerClient(conn=False)
            data = docker_client.get_registry_mirrors()
            return DetailResponse(data=data)
        return ErrorResponse(msg="类型错误")
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "set_registry_mirrors":
            cont = reqData.get("cont",[])
            if not cont:
                cont=[]
            else:
                cont = cont.split("\n")
                for ul in cont:
                    if not check_is_url(ul):
                        return ErrorResponse(msg=f"非url地址：{ul}")
            docker_client = DockerClient(conn=False)
            conf_data = docker_client.get_daemon_config()
            conf_data["registry-mirrors"] = cont
            docker_client.save_daemon_config({"content":conf_data})
            RuyiAddOpLog(request,msg=f"【容器】-【设置】=>加速地址",module="dockermg")
            return DetailResponse(msg="设置成功")
        return ErrorResponse(msg="类型错误")