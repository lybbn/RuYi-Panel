#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-05-01
# +-------------------------------------------------------------------
# | EditDate: 2024-05-01
# +-------------------------------------------------------------------

# ------------------------------
# 服务器/面板管理
# ------------------------------

from rest_framework.views import APIView
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import get_parameter_dic
from utils.server.system import system
from utils.customView import CustomAPIView
from apps.syslogs.logutil import RuyiAddOpLog
    
class RYServManageView(CustomAPIView):
    """
    post:
    服务器/面板管理
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        if action == "restart":
            type = reqData.get("type","")
            if type == "server":
                RuyiAddOpLog(request,msg="【安全】 => 重启服务器",module="safe")
                system.RestartServer()
                return DetailResponse(msg="重启成功")
            elif type == "panel":
                RuyiAddOpLog(request,msg="【安全】 => 重启面板",module="safe")
                system.RestartRuyi()
                return DetailResponse(msg="重启成功")
            else:
                return ErrorResponse(msg="参数错误")
        return ErrorResponse(msg="参数错误")
                
