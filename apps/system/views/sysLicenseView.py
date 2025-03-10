#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-01-15
# +-------------------------------------------------------------------
# | EditDate: 2025-01-15
# +-------------------------------------------------------------------

# ------------------------------
# license
# ------------------------------
from rest_framework.views import APIView
from django.conf import settings
from django.contrib.auth.hashers import make_password
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.customView import CustomAPIView
import zipfile
from utils_pro.RyProLoader import load_ryprofunc_extension as proFuncLoader

class RYSysImportLicenseView(CustomAPIView):
    """
    post:
    导入系统license
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        ALLOWED_MIME_TYPES = ['application/zip', 'application/x-zip-compressed']
        MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB

        zipf = request.FILES.get('license_zip')
        if not zipf:return ErrorResponse(msg='未收到文件')
        
        # 验证文件类型
        if not zipf.name.endswith('.zip'):
            return ErrorResponse(msg="仅支持ZIP文件")

        if zipf.size > MAX_FILE_SIZE:
            return ErrorResponse(msg='文件大小超过1MB限制')
        
        # 检查MIME类型
        if zipf.content_type not in ALLOWED_MIME_TYPES:
            return ErrorResponse(msg='仅支持ZIP文件')
        
        try:
            with zipfile.ZipFile(zipf, 'r') as zf:
                # 查找目标文件
                target_file = 'active_license.dat'
                if target_file not in zf.namelist():
                    return ErrorResponse(msg=f'ZIP文件中未找到 {target_file}')
                # 读取文件内容
                with zf.open(target_file) as f:
                    content = f.read().decode('utf-8')

                    # 这里可以添加业务逻辑验证
                    isok,msg = proFuncLoader().import_license(content)
                    if not isok:return ErrorResponse(msg=msg)
                    RuyiAddOpLog(request,msg="【面板设置】-【许可证】=> 导入授权",module="panelst")
                    return DetailResponse(msg="导入成功")

        except Exception as e:
            return ErrorResponse(msg="文件处理失败")
        
        
class RYSysUnBindLicenseView(CustomAPIView):
    """
    post:
    解除license绑定
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        isok,msg = proFuncLoader().unbind_license()
        if not isok:return ErrorResponse(msg=msg)
        RuyiAddOpLog(request,msg="【面板设置】-【许可证】=> 解除绑定",module="panelst")
        return DetailResponse(msg="解除成功")
