#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-26
# +-------------------------------------------------------------------
# | EditDate: 2025-02-26
# +-------------------------------------------------------------------

# ------------------------------
# docker 广场管理
# ------------------------------
import os,json
from math import ceil
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic,ast_convert,DeleteDir,RunCommand,formatdatetime
from utils.jsonResponse import ErrorResponse,DetailResponse,SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.dockerInclude.ry_dk_gpu import GPUMain

class RYAIGgpuInfoManageView(CustomAPIView):
    """
    get:
    获取GPU信息
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        data = GPUMain().get_gpu_info()
        return DetailResponse(data=data)