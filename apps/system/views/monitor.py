#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Copyright (c) 如意面板 All rights reserved.
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------

# ------------------------------
# 系统监控类视图
# ------------------------------

from rest_framework.views import APIView
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.server.system import system
from utils.customView import CustomAPIView

class GetSystemMonitorAllView(CustomAPIView):
    """
    get
    获取主机cpu、内存、磁盘等实时信息
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        data = system().GetSystemAllInfo()
        return DetailResponse(data=data)