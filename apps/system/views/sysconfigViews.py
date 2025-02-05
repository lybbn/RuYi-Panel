#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-03-15
# +-------------------------------------------------------------------
# | EditDate: 2024-03-15
# +-------------------------------------------------------------------

# ------------------------------
# 系统配置
# ------------------------------
import os,re
import requests
import socket
import datetime
from math import ceil
from rest_framework.views import APIView
from django.conf import settings
from django.contrib.auth.hashers import make_password
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import compare_versions,current_os,DeleteFile,ReadFile,GetSecurityPath,GetPanelBindAddress,get_parameter_dic,ast_convert,GetPanelPort,isSSLEnable,WriteFile,GetWebRootPath,GetBackupPath,formatdatetime
from apps.system.models import Users,Sites,Databases
from apps.sysshop.models import RySoftShop
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ip_util import is_valid_ipv4
from utils.security.security_path import security_path_authed_key
from utils.customView import CustomAPIView
from utils.sslPem import getCertInfo,getDefaultRuyiSSLPem
from django.http import FileResponse
from django.utils.encoding import escape_uri_path
from utils.upgrade_panel import update_ruyi_panel
from utils_pro.proFuncLoader import proFuncLoader

def ruyiPathDirHandle(p):
    """
    处理目录路径
    返回： 处理状态,错误消息（处理后路径）
    """
    try:
        if not os.path.exists(p):
            return False,"目录路径不存在"
        if not os.path.isdir(p):
            return False,"非目录路径"
        if p[-1] == '/':
            p = p[:-1]
        p = p.replace("\\","/")
        return True,p
    except Exception as e:
        return False,e

class RYSysLicenseView(CustomAPIView):
    """
    get:
    获取系统license
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        data = proFuncLoader(settings=settings).get_license()
        return DetailResponse(data=data)

class RYSysconfigManageView(CustomAPIView):
    """
    get:
    获取系统配置
    post:
    更新系统配置
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        u_ins = Users.objects.filter(is_superuser=True,is_staff=True).first()
        data = {}
        username = ""
        email = ""
        mobile = ""
        if u_ins is not None:
            username = u_ins.username
            email = u_ins.email
            mobile = u_ins.mobile
        webServerIns = RySoftShop.objects.filter(type=3).first()
        webServer = ""
        if webServerIns is not None:
            webServer = webServerIns.name
        data['username'] =  username
        data['password'] = "******"
        data['email'] = email
        data['mobile'] = mobile
        data['panelPort'] = GetPanelPort()
        data['panelBindAddress'] = GetPanelBindAddress()
        data['sslEnable'] = isSSLEnable()
        data['securityPath'] = GetSecurityPath()
        data['wwwrootPath'] = GetWebRootPath()
        data['backupPath'] = GetBackupPath()
        data['localTime'] = formatdatetime(datetime.datetime.now())
        data['timeZone'] = settings.TIME_ZONE
        data['sysVersion'] = ReadFile(settings.RUYI_SYSVERSION_FILE)
        data['serverIp'] = ReadFile(settings.RUYI_PUBLICIP_FILE)
        data['currentOs'] = current_os
        data['webServer'] = webServer
        data['siteNums'] = Sites.objects.count()
        data['dbNums'] = Databases.objects.count()
        data['softNums'] = RySoftShop.objects.filter(installed=True).count()
        return DetailResponse(data=data)

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        if action == "save_username":
            username = reqData.get("username","")
            if not username or len(username)>60:
                return ErrorResponse(msg="用户名错误")
            u_ins = Users.objects.filter(is_superuser=True,is_staff=True).first()
            if not u_ins:
                return ErrorResponse(msg="内部错误")
            olduname = u_ins.username
            u_ins.username = username
            u_ins.save()
            RuyiAddOpLog(request,msg="【面板设置】-【修改用户名】把 %s 修改为 %s"%(olduname,username),module="panelst")
            return DetailResponse(msg="设置成功")
        elif action == "save_password":
            oldpass = reqData.get("oldpass","")
            newpass = reqData.get("newpass","")
            if not oldpass or not newpass:
                return ErrorResponse(msg="参数错误")
            u_ins = Users.objects.filter(is_superuser=True,is_staff=True).first()
            if not u_ins:
                return ErrorResponse(msg="内部错误")
            if not u_ins.check_password(oldpass):
                return ErrorResponse(msg="原密码错误")
            u_ins.password = make_password(newpass)
            u_ins.save()
            RuyiAddOpLog(request,msg="【面板设置】-【修改密码】修改为 %s"%(newpass),module="panelst")
            return DetailResponse(msg="设置成功")
        elif action == "save_panelport":
            port = int(reqData.get("port",6789))
            if not port or port >65535 or port < 1:
                return ErrorResponse(msg="端口错误")
            portpath = os.path.join(settings.BASE_DIR,"data",'port.ry')
            WriteFile(portpath,str(port))
            RuyiAddOpLog(request,msg="【面板设置】-【修改端口】修改为 %s"%(port),module="panelst")
            return DetailResponse(msg="设置成功")
        elif action == "save_wwwroot_path":
            path = reqData.get("path","")
            if not path:return ErrorResponse(msg="请选择目录路径")
            isok,res = ruyiPathDirHandle(path)
            if not isok:return ErrorResponse(msg=res)
            path = res
            wwwrootpath = os.path.join(settings.BASE_DIR,"data",'wwwroot.ry')
            WriteFile(wwwrootpath,path)
            RuyiAddOpLog(request,msg="【面板设置】-【修改网站目录】修改为 %s"%(path),module="panelst")
            return DetailResponse(msg="设置成功")
        elif action == "save_backup_path":
            path = reqData.get("path","")
            if not path:return ErrorResponse(msg="请选择目录路径")
            isok,res = ruyiPathDirHandle(path)
            if not isok:return ErrorResponse(msg=res)
            path = res
            backuppath = os.path.join(settings.BASE_DIR,"data",'backup.ry')
            WriteFile(backuppath,path)
            RuyiAddOpLog(request,msg="【面板设置】-【修改备份目录】修改为 %s"%(path),module="panelst")
            return DetailResponse(msg="设置成功")
        elif action =="save_panelbindaddress":
            host = str(reqData.get("host",""))
            if host not in ['127.0.0.1','0.0.0.0']:
                if not is_valid_ipv4(host):
                    return ErrorResponse(msg="监听ipv4地址无效")
            bindaddress_path = os.path.join(settings.BASE_DIR,"data",'bindaddress.ry')
            WriteFile(bindaddress_path,host)
            RuyiAddOpLog(request,msg="【面板设置】-【修改监听地址】修改为 %s"%(host),module="panelst")
        elif action == "save_panelsecuritypath":
            path = reqData.get("path","")
            pattern = r'^\/[a-zA-Z0-9_]+$'
            if not path:return ErrorResponse(msg="请选择目录路径")
            if not re.match(pattern, path):
                return ErrorResponse(msg='安全入口必须以 "/" 开头， 后面为数字、字母或下划线')
            if path in settings.RUYI_SYSTEM_PATH_LIST:
                return ErrorResponse(msg="该目录路径与系统冲突，请选择其他路径!!!")
            sec_file_path = settings.RUYI_SECURITY_PATH_FILE
            WriteFile(sec_file_path,path)
            RuyiAddOpLog(request,msg="【面板设置】-【修改安全入口】修改为 %s"%(path),module="panelst")
            settings.RUYI_SECURITY_PATH = path
            request.session[security_path_authed_key] = True
            return DetailResponse(msg="设置成功")
        elif action == "get_ruyi_sslinfo":
            certinfo = getCertInfo()
            ruyi_root_password,ruyi_root,private_key,certificate = getDefaultRuyiSSLPem(mode="r")
            data = {
                'certinfo':certinfo,
                'root_password':ruyi_root_password,
                'private_key':private_key,
                'certificate':certificate,
            }
            return DetailResponse(data=data,msg="获取成功")
        elif action == "download_ruyiroot_pfx":
            filename = settings.RUYI_ROOTPFX_PATH_FILE
            if not os.path.exists(filename):
                return ErrorResponse(msg="文件不存在")
            file_size = os.path.getsize(filename)
            response = FileResponse(open(filename, 'rb'))
            response['content_type'] = "application/octet-stream"
            response['Content-Disposition'] = f'attachment;filename="{escape_uri_path(os.path.basename(filename))}"'
            response['Content-Length'] = file_size  # 设置文件大小
            RuyiAddOpLog(request,msg="【面板设置】-【下载SSL根证书】%s"%(os.path.basename(filename)),module="panelst")
            return response
        elif action == "save_ruyi_ssl":
            enable = reqData.get('enable',False)
            private_key = reqData.get('private_key',None)
            certificate = reqData.get('certificate',None)
            if not private_key or not certificate:
                return ErrorResponse(msg="证书PEM信息不能为空")
            oldEnabled = isSSLEnable()
            en_msg = ""
            can_close = False
            can_open = False
            if oldEnabled and not enable:
                en_msg = "关闭SSL"
                can_close = True
            elif not oldEnabled and enable:
                en_msg = "启用SSL"
                can_open = True
            old_cert = ReadFile(settings.RUYI_CERTKEY_PATH_FILE,mode='r')
            if not old_cert == certificate:
                certinfo = getCertInfo(cert_content=certificate.encode('utf-8'),mode=None)
                if not certinfo:
                    return ErrorResponse(msg="证书解析错误")
                en_msg = en_msg+"=>保存证书cert"
                WriteFile(settings.RUYI_CERTKEY_PATH_FILE,certificate)
            old_key = ReadFile(settings.RUYI_PRIVATEKEY_PATH_FILE,mode='r')
            if not old_key == private_key:
                en_msg = en_msg+"=>保存证书key"
                WriteFile(settings.RUYI_PRIVATEKEY_PATH_FILE,private_key)
            if can_open:
                WriteFile(settings.RUYI_SSL_ENABLE_FILE,old_cert+old_key)
            if can_close:
                DeleteFile(settings.RUYI_SSL_ENABLE_FILE)
            RuyiAddOpLog(request,msg="【面板设置】-【面板SSL】%s"%(en_msg),module="panelst")
            return DetailResponse(msg="设置成功")
        return ErrorResponse(msg="参数错误")
    
class RYGetInterfacesView(CustomAPIView):
    """
    get:
    获取系统配置
    post:
    更新系统配置
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        hostname = socket.gethostname()
        ip_addresses = socket.gethostbyname_ex(hostname)[2]
        hosts = [ip for ip in ip_addresses if not ip.startswith("127.")]
        data = [
            "0.0.0.0",
            "127.0.0.1",
        ]
        for h in hosts:
            data.append(h)
        return DetailResponse(data=data)
    
class RYUpdateSysManageView(CustomAPIView):
    """
    get:
    获取新版本
    post:
    更新系统
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        s_url = "https://download.lybbn.cn/ruyi/install/version.json"
        resp = requests.get(url=s_url,timeout=5)
        ver = ""
        if resp.status_code == 200:
            ver = resp.text
        c_ver = ReadFile(settings.RUYI_SYSVERSION_FILE)
        has_new_version = False
        if ver:
            res_v = compare_versions(ver,c_ver)
            if res_v >0:
                has_new_version = True
        else:
            ver = c_ver
        data = {
            'c_ver':c_ver,
            'can_update':has_new_version,
            'n_ver':ver
        }
        return DetailResponse(data=data)
    
    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        if action == "update":
            isok,msg = update_ruyi_panel()
            if not isok:
                return ErrorResponse(msg=msg)
            return DetailResponse(msg="更新成功，请重启面板！！！")
        elif action == "fix":
            pass
        return ErrorResponse(msg="类型错误")