from apps.syslogs.models import OperationLog
from utils.request_util import get_client_info
from asgiref.sync import sync_to_async

@sync_to_async
def asyncRuyiAddOpLog(request,msg="",module="",status=True):
    RuyiAddOpLog(request,msg=msg,module=module,status=status)

def RuyiAddOpLog(request,msg="",module="",status=True):
    c_info = get_client_info(request)
    r_info = {
        'username':c_info['username'],
        'ip':c_info['ip'],
        'ip_area':c_info['ip_area'],
        'path':c_info['path'],
        'body':c_info['body'],
        'request_os': c_info['request_os'],
        'browser': c_info['browser'],
        'msg':msg,
        'status':status,
        'module':module
    }
    OperationLog.objects.create(**r_info)
    
def RuyiDelOpLog(request,msg="清空日志",module="dellog",status=True):
    c_info = get_client_info(request)
    r_info = {
        'username':c_info['username'],
        'ip':c_info['ip'],
        'ip_area':c_info['ip_area'],
        'path':c_info['path'],
        'body':c_info['body'],
        'request_os': c_info['request_os'],
        'browser': c_info['browser'],
        'msg':msg,
        'status':status,
        'module':module
    }
    OperationLog.objects.all().delete()
    OperationLog.objects.create(**r_info)