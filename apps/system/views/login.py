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
# 登录视图
# ------------------------------
import os
import base64
import hashlib
import time
from datetime import datetime, timedelta
from apps.system.models import Users
from utils.customView import CustomAPIView
from captcha.views import CaptchaStore, captcha_image
from utils.jsonResponse import DetailResponse,ErrorResponse
from django.http import HttpResponse
from django.conf import settings
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.syslogs.logutil import RuyiAddOpLog
from utils.security.safe_filter import filter_xss1,filter_xss2
from utils.security.login_protection import check_login_allowed, record_login_success, record_login_failure, get_login_ban_status
from utils.security.otp import is_otp_enabled, get_otp_config, verify_otp_code, save_otp_temp_token, get_otp_temp_token, delete_otp_temp_token, clean_expired_otp_tokens

base_dir = settings.BASE_DIR
confit_path = os.path.join(base_dir, 'web','dist','ruyi.config.js')

class CaptchaView(CustomAPIView):
    """
    获取图片验证码
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        ban_status = get_login_ban_status(request)
        if ban_status:
            return ErrorResponse(msg='登录失败次数过多，请稍后重试', data={'ban_status': ban_status})

        hashkey = CaptchaStore.generate_key()
        id = CaptchaStore.objects.filter(hashkey=hashkey).first().id
        imgage = captcha_image(request, hashkey)
        image_base = base64.b64encode(imgage.content)
        json_data = {"key": id, "image_base": "data:image/png;base64," + image_base.decode('utf-8')}
        return DetailResponse(data=json_data)


class LoginSerializer(TokenObtainPairSerializer):
    """
    登录的序列化器:
    重写djangorestframework-simplejwt的序列化器
    """

    @classmethod
    def get_token(cls, user):
        refresh = super(LoginSerializer,cls).get_token(user)
        data = {}
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        return data
        

class LoginView(CustomAPIView):
    """
    登录接口
    """
    authentication_classes = []
    permission_classes = []

    #删除验证码
    def delete_expire_captcha(self):
        five_minute_ago = datetime.now() - timedelta(hours=0, minutes=5, seconds=0)
        CaptchaStore.objects.filter(expiration__lte = five_minute_ago).delete()

    def post(self, request):
        allowed, ban_msg, remaining = check_login_allowed(request)
        if not allowed:
            RuyiAddOpLog(request, msg=ban_msg, module="login", status=False)
            return ErrorResponse(msg=ban_msg, data={'remaining_seconds': remaining, 'banned': True})

        username = filter_xss2(filter_xss1(request.data.get('username',None)))
        password = filter_xss2(filter_xss1(request.data.get('password',None)))
        captchaKey = request.data.get('captchaKey',None)
        captcha = request.data.get('captcha',None)

        image_code = CaptchaStore.objects.filter(id=captchaKey).first()
        five_minute_ago = datetime.now() - timedelta(hours=0, minutes=5, seconds=0)
        if image_code and five_minute_ago > image_code.expiration:
            self.delete_expire_captcha()
            banned, fail_msg, remaining = record_login_failure(request)
            msg="验证码过期"
            RuyiAddOpLog(request,msg=msg,module="login",status=False)
            return ErrorResponse(msg=fail_msg if banned else msg, data={'remaining_seconds': remaining, 'banned': banned})
        else:
            if image_code and (image_code.response == captcha or image_code.challenge == captcha):
                image_code and image_code.delete()
            else:
                self.delete_expire_captcha()
                banned, fail_msg, remaining = record_login_failure(request)
                msg="图片验证码错误"
                RuyiAddOpLog(request,msg=msg,module="login",status=False)
                return ErrorResponse(msg=fail_msg if banned else msg, data={'remaining_seconds': remaining, 'banned': banned})
            
        user = Users.objects.filter(username=username).first()

        if not user:
            banned, fail_msg, remaining = record_login_failure(request)
            return ErrorResponse(msg=fail_msg, data={'remaining_seconds': remaining, 'banned': banned})

        if user and not user.is_staff:
            msg="您没有权限登录"
            RuyiAddOpLog(request,msg=msg,module="login",status=False)
            return ErrorResponse(msg=msg)
        
        if user and user.check_password(password):
            if is_otp_enabled():
                otp_code = request.data.get('otp_code', None)
                if not otp_code:
                    temp_str = f"{user.id}:{user.username}:{time.time()}:{settings.SECRET_KEY}"
                    temp_token = hashlib.sha256(temp_str.encode()).hexdigest()
                    save_otp_temp_token(temp_token, user.id, username)
                    clean_expired_otp_tokens()
                    return DetailResponse(data={
                        'otp_required': True,
                        'temp_token': temp_token,
                    }, msg="需要动态口令验证")
                else:
                    otp_config = get_otp_config()
                    if not verify_otp_code(otp_config.get('otp_secret', ''), otp_code):
                        banned, fail_msg, remaining = record_login_failure(request)
                        RuyiAddOpLog(request, msg=f'【{username}】动态口令错误', module="login", status=False)
                        return ErrorResponse(msg=fail_msg if banned else "动态口令错误", data={'remaining_seconds': remaining, 'banned': banned})
            record_login_success(request)
            data = LoginSerializer.get_token(user)
            msg="登录成功"
            RuyiAddOpLog(request,msg=f'【{username}】{msg}',module="login",status=True)
            return DetailResponse(data=data,msg=msg)
        else:
            banned, fail_msg, remaining = record_login_failure(request)
            RuyiAddOpLog(request,msg=f'【{username}】账号/密码错误',module="login",status=False)
            return ErrorResponse(msg=fail_msg, data={'remaining_seconds': remaining, 'banned': banned})

def AdminConfigResponse(request):
    
    with open(confit_path, 'r') as f:
        js_content = f.read()
    response = HttpResponse(js_content, content_type='application/javascript')
    return response


class OTPVerifyView(CustomAPIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        temp_token = request.data.get('temp_token', None)
        otp_code = request.data.get('otp_code', None)
        if not temp_token or not otp_code:
            return ErrorResponse(msg="参数错误")
        temp_data = get_otp_temp_token(temp_token)
        if not temp_data:
            return ErrorResponse(msg="临时令牌无效或已过期，请重新登录")
        otp_config = get_otp_config()
        if not verify_otp_code(otp_config.get('otp_secret', ''), otp_code):
            banned, fail_msg, remaining = record_login_failure(request)
            username = temp_data.get('username', '')
            RuyiAddOpLog(request, msg=f'【{username}】动态口令错误', module="login", status=False)
            return ErrorResponse(msg=fail_msg if banned else "动态口令错误", data={'remaining_seconds': remaining, 'banned': banned})
        user_id = temp_data.get('user_id')
        user = Users.objects.filter(id=user_id, is_staff=True).first()
        if not user:
            return ErrorResponse(msg="用户无效")
        delete_otp_temp_token(temp_token)
        record_login_success(request)
        data = LoginSerializer.get_token(user)
        username = temp_data.get('username', '')
        RuyiAddOpLog(request, msg=f'【{username}】OTP验证登录成功', module="login", status=True)
        return DetailResponse(data=data, msg="登录成功")