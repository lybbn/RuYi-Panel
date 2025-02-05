from apps.sysbak.models import RuyiBackup
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import get_parameter_dic,formatdatetime
from utils.pagination import CustomPagination
from apps.syslogs.logutil import RuyiAddOpLog

class RuyiBackupManageView(CustomAPIView):
    """
    get:
    备份列表管理
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        reqData = get_parameter_dic(request)
        cron_id = reqData.get("cron_id",None)
        job_id = reqData.get("job_id",None)
        name = reqData.get("name",None)
        type = int(reqData.get("type",0))
        fid = str(reqData.get("fid",""))
        queryset = RuyiBackup.objects.all().order_by("-id")
        if type != 0:
            queryset = queryset.filter(type = type)
        if job_id:
            queryset = queryset.filter(job_id=job_id)
        if cron_id:
            queryset = queryset.filter(cron_id=cron_id)  
        if name:
            name = name + "_"
            queryset = queryset.filter(name__icontains=name)
        if fid:
            queryset = queryset.filter(fid=fid) 
        # # 1. 实例化分页器对象
        page_obj = CustomPagination()
        # # 2. 使用自己配置的分页器调用分页方法进行分页
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        for m in page_data:
            data.append({
                'id':m.id,
                'name':m.name,
                'filename':m.filename,
                'size':m.size,
                'remark':m.remark,
                'store_type':m.get_store_type_display(),
                'create_at':formatdatetime(m.create_at)
            })
        return page_obj.get_paginated_response(data)