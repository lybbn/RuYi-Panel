import os
from django.conf import settings
from django.db.models import Q
from apps.syslogs.models import OperationLog
from rest_framework.views import APIView
from utils.customView import CustomAPIView
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import get_parameter_dic,formatdatetime
from utils.pagination import CustomPagination
from apps.syslogs.logutil import RuyiDelOpLog
from utils.server.system import system
from apps.syslogs.logutil import RuyiAddOpLog

class RYOPLogsManageView(CustomAPIView):
    """
    get:
    操作日志管理
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        reqData = get_parameter_dic(request)
        search = reqData.get("search",None)
        module = reqData.get("module",None)
        status = int(reqData.get("status",-1))
        queryset = OperationLog.objects.all().order_by("-id")
        if module:
            queryset = queryset.filter(module = module)
        if not status == -1:
            queryset = queryset.filter(status = status)
        if search:
            queryset = queryset.filter(Q(ip__icontains=search) | Q(msg__icontains=search))
        # # 1. 实例化分页器对象
        page_obj = CustomPagination()
        # # 2. 使用自己配置的分页器调用分页方法进行分页
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        for m in page_data:
            data.append({
                'id':m.id,
                'username':m.username,
                'ip':m.ip,
                'ip_area':m.ip_area,
                'path':m.path,
                'body':m.body,
                'request_os': m.request_os,
                'browser': m.browser,
                'msg':m.msg,
                'status':m.status,
                'module':m.get_module_display(),
                'create_at':formatdatetime(m.create_at)
            })
        return page_obj.get_paginated_response(data)
    
    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action",None)
        
        if action == "op_del_all":
            RuyiDelOpLog(request)
            return DetailResponse(msg="操作成功")
        elif action == "del_given_log":
            type = reqData.get("type","")
            if type == "syslogServer":
                name = 'server.log'
            elif type == "syslogError":
                name = 'error.log'
            elif type == "syslogTask":
                name = 'task.log'
            elif type == "syslogAccess":
                name = 'ry_access.log'
            else:
                return ErrorResponse(msg="类型错误")
            log_path = os.path.join(settings.BASE_DIR,'logs',name)
            with open(log_path, 'r+') as f:
                f.truncate(0)
            RuyiAddOpLog(request,msg="【清空日志】-【%s】"%name,module="dellog")
            return DetailResponse(msg="清空成功")
        elif action == "get_runserver_log":
            log_path = os.path.join(settings.BASE_DIR,'logs','server.log')
            num = 5000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_runerror_log":
            log_path = os.path.join(settings.BASE_DIR,'logs','error.log')
            num = 5000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_runtask_log":
            log_path = os.path.join(settings.BASE_DIR,'logs','task.log')
            num = 5000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_runaccess_log":
            log_path = os.path.join(settings.BASE_DIR,'logs','ry_access.log')
            num = 5000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        return ErrorResponse(msg="类型错误")