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
from utils.common import get_parameter_dic,DeleteFile
from utils.jsonResponse import ErrorResponse,DetailResponse,SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from apps.sysdocker.models import RyDockerApps
from apps.sysbak.models import RuyiBackup
from utils.ruyiclass.dockerInclude.ry_dk_square import main as dksquare
from django.http import FileResponse
from django.utils.encoding import escape_uri_path

class RYDockerBackupAppManageView(CustomAPIView):
    """
    post:
    备份应用
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        reqData = get_parameter_dic(request)
        id = reqData.get("id","")
        if not id:return ErrorResponse(msg="参数错误")
        ins = RyDockerApps.objects.filter(id=id).first()
        if not ins:return ErrorResponse(msg="无此应用")
        name = ins.name
        appname = ins.appname
        cont = {
            "id":id,
            "name":name,
            "appname":appname
        }
        newsq = dksquare()
        isok,msg,dst_path = newsq.backup_app(cont=cont)
        if not isok:return ErrorResponse(msg=msg)
        RuyiAddOpLog(request,msg=f"【容器】-【应用广场】-【备份应用】-【{name}】=> {dst_path}",module="dockermg")
        return DetailResponse(msg="操作成功")
    
class RYDockerRestoreAppManageView(CustomAPIView):
    """
    post:
    恢复应用
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        reqData = get_parameter_dic(request)
        id = reqData.get("id","")
        bid = reqData.get("bid","")
        if not id:return ErrorResponse(msg="参数错误")
        ins = RyDockerApps.objects.filter(id=id).first()
        if not ins:return ErrorResponse(msg="无此应用")
        bk_ins = RuyiBackup.objects.filter(type=4,id=bid).first()
        if not bk_ins:return ErrorResponse(msg="无此应用备份")
        backup_file = bk_ins.filename
        
        name = ins.name
        appname = ins.appname
        newsq = dksquare()
        app_path = newsq.get_dkapp_path(cont={"name":name,"appname":appname})
        
        cont = {
            "backup_file":backup_file,
            "app_path":app_path
        }
        isok,msg = newsq.restore_app(cont=cont)
        if not isok:return ErrorResponse(msg=msg)
        RuyiAddOpLog(request,msg=f"【容器】-【应用广场】-【恢复应用】-【{name}】=> {backup_file}",module="dockermg")
        return DetailResponse(msg="操作成功")
    
class RYDockerBackupDelManageView(CustomAPIView):
    """
    post:
    删除应用备份
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        reqData = get_parameter_dic(request)
        id = reqData.get("id","")
        if not id:return ErrorResponse(msg="参数错误")
        ins = RyDockerApps.objects.filter(id=id).first()
        if not ins:return ErrorResponse(msg="无此应用")
        bid = reqData.get("bid","")
        bk_ins = RuyiBackup.objects.filter(type=4,fid=id,id=bid).first()
        if bk_ins:
            DeleteFile(bk_ins.filename,empty_tips=False)
            bk_ins.delete()
        else:#无关联数据库id的场景删除
            bk_ins = RuyiBackup.objects.filter(type=4,id=bid).first()
            if bk_ins:
                DeleteFile(bk_ins.filename,empty_tips=False)
                bk_ins.delete()
        RuyiAddOpLog(request,msg="【容器】-【应用广场】-【删除备份】-【%s】=> %s"%(ins.name,bk_ins.filename),module="dockermg")
        return DetailResponse(msg="删除成功")
    
class RYDockerBackupDownloadManageView(CustomAPIView):
    """
    post:
    下载应用备份
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        reqData = get_parameter_dic(request)
        id = reqData.get("id","")
        if not id:return ErrorResponse(msg="参数错误")
        ins = RyDockerApps.objects.filter(id=id).first()
        if not ins:return ErrorResponse(msg="无此应用")
        bid = reqData.get("bid","")
        bk_ins = RuyiBackup.objects.filter(type=4,id=bid).first()
        if not bk_ins:
            return ErrorResponse(msg="没有发现备份文件")
        filename = bk_ins.filename
        if not os.path.exists(filename):
            return ErrorResponse(msg="文件不存在")
        if not os.path.isfile(filename):
            return ErrorResponse(msg="文件不存在2")
        file_size = os.path.getsize(filename)
        response = FileResponse(open(filename, 'rb'))
        response['content_type'] = "application/octet-stream"
        response['Content-Disposition'] = f'attachment;filename="{escape_uri_path(os.path.basename(filename))}"'
        response['Content-Length'] = file_size  # 设置文件大小
        RuyiAddOpLog(request,msg="【容器】-【应用广场】-【下载备份】-【%s】=> %s"%(ins.name,filename),module="dbmg")
        return response