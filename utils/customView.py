from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle,AnonRateThrottle
from utils.security.security_path import security_path_authed_key,ResponseNginx404
from django.conf import settings
from functools import wraps

class CustomAPIView(APIView):
    throttle_classes = [UserRateThrottle,AnonRateThrottle]
    check_security_path = True
    
    def dispatch(self, request, *args, **kwargs):
        if self.check_security_path:
            response = self.check_security_path_authed(request)
            if response:return response
        return super().dispatch(request, *args, **kwargs)
    
    def check_security_path_authed(self, request):
        # 检查 安全入口
        if settings.RUYI_SECURITY_PATH != '/ry' and not request.session.get(security_path_authed_key,False):
            return ResponseNginx404(state=404)
        return None
    
def check_security_path_authed(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 检查 安全入口
        if settings.RUYI_SECURITY_PATH != '/ry' and not request.session.get(security_path_authed_key,False):
            return ResponseNginx404(state=404)
        return view_func(request, *args, **kwargs)
    return _wrapped_view