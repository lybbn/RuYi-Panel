#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-11-18
# +-------------------------------------------------------------------
# | EditDate: 2024-11-18
# +-------------------------------------------------------------------

# ------------------------------
# go项目管理
# ------------------------------
import os
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import GetSoftList,get_parameter_dic,current_os,DeleteDir
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.install.install_soft import Check_Soft_Installed
from apps.sysshop.models import RySoftShop
from utils.install.go import create_default_env
from apps.syslogs.logutil import RuyiAddOpLog

class RYGoManageView(CustomAPIView):
    """
    get:
    获取Go项目信息
    post:
    设置Go项目
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "list_version":
            data = []
            soft_list = GetSoftList()
            for s in soft_list:
                if s['name'] == 'go':
                    detail_version =s['versions'][0]['c_version']
                    s_installed,s_version,s_status,s_install_path = Check_Soft_Installed(name=s['name'],is_windows=is_windows,version=detail_version,get_status=False)
                    if s_installed:
                        data.append({
                            'id':s['id'],
                            'name':s['name'],
                            'version':detail_version,
                            'is_default':False
                        })
            queryset = RySoftShop.objects.filter(name='go')
            for q in queryset:
                for d in data:
                    if d['version'] == q.install_version:
                        d['is_default'] = q.is_default
            return DetailResponse(data=data)
        return ErrorResponse(msg="类型错误") 
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "set_default":
            version = reqData.get("version","")
            if not version:return ErrorResponse(msg="参数错误")
            ins = RySoftShop.objects.filter(name='go',install_version=version).first()
            if not ins:return ErrorResponse(msg="该版本不存在")
            install_path = ins.install_path
            version_path = install_path.replace("\\","/")+'/version.ry'
            if not os.path.exists(version_path):return ErrorResponse(msg="该版本未安装")
            create_default_env(version,install_path,is_windows=is_windows)
            RySoftShop.objects.filter(name='go').exclude(install_version=version).update(is_default=False)
            ins.is_default = True
            ins.save()
            RuyiAddOpLog(request,msg=f"【软件商店】-【设置】=>go-{version}为默认版本",module="softmg")
            return DetailResponse(msg="设置成功")
        return ErrorResponse(msg="类型错误")