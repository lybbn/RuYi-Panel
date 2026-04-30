#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-04-13
# +-------------------------------------------------------------------
# | EditDate: 2025-04-13
# +-------------------------------------------------------------------

# ------------------------------
# 图片工具接口
# ------------------------------

import base64
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ctools.ImageConverter import ImageConverter
from django.views.decorators.csrf import csrf_exempt

class RYSysImageToolsView(CustomAPIView):
    """
    post:
    图片工具
    """
    permission_classes = [IsAuthenticated]
    
    @csrf_exempt
    def post(self,request):
        try:
            if not request.FILES.get('file',None):
                return ErrorResponse(msg="请提供图片")
            uploaded_file = request.FILES['file']
            image_bytes = uploaded_file.read()

            if image_bytes is None:
                return ErrorResponse(msg="请提供图片")

            data = request.data
            enableQuality = data.get('enableQuality', False)
            enableFormat = data.get('enableFormat', False)
            enableSize = data.get('enableSize', False)
            width = int(data.get('width', 0))
            height = int(data.get('height', 0))
            format = data.get('format', "")
            quality = int(data.get('quality', 100))

            maintain_size = False if enableSize else True
            imgbytes = ImageConverter().convert_image_in_memory(image_bytes,output_format=format,quality=quality,maintain_size=maintain_size,size=(width,height))
            base64_str = base64.b64encode(imgbytes).decode('utf-8')
            
            tmp_mime = format
            if format.lower() == "ico":
                tmp_mime = "x-icon"

            mime_type = f"image/{tmp_mime}"
            base64_data_url = f"data:{mime_type};base64,{base64_str}"
            return DetailResponse(data={'content':base64_data_url,'size':len(imgbytes)})
        except Exception as e:
            return ErrorResponse(msg=f"错误：{str(e)}")
