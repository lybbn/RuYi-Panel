#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-09-15
# +-------------------------------------------------------------------
# | EditDate: 2024-09-15
# +-------------------------------------------------------------------

# ------------------------------
# 静态网站配置
# ------------------------------
import os,re,json,time
import datetime
from rest_framework.views import APIView
from django.conf import settings
from apps.system.models import Sites,SiteDomains
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import GetRandomSet,GetBackupPath,check_is_domain,check_is_port,md5,current_os,DeleteFile,ReadFile,get_parameter_dic,ast_convert,isSSLEnable,WriteFile,GetLetsencryptLogPath,formatdatetime,check_is_email,GetLetsencryptPath
from apps.syslogs.logutil import RuyiAddOpLog
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from django.db.models import Q
from utils.security.no_delete_list import check_in_black_list
from apps.sysshop.models import RySoftShop
from utils.ruyiclass.webClass import WebClient
from utils.server.system import system
from utils.security.letsencrypt_cert import letsencryptTool
from utils.sslPem import getCertInfo
from apps.sysbak.models import RuyiBackup
from django.http import FileResponse
from django.utils.encoding import escape_uri_path
from apps.systask.tasks import backup_directory
import threading

def has_duplicates(lst):
    """
    列表是否存在重复项
    """
    return len(lst) != len(set(lst))

def ruyiPathDirHandle(p,is_windows=False):
    """
    处理目录路径
    返回： 处理状态,错误消息（处理后路径）
    """
    try:
        if not p:return False,"目录不能为空"
        if check_in_black_list(p,is_windows=is_windows):
            return False,"目录不合法"
        if p[-1] == '.': return False, '目录结尾不能是 "."'
        if p[-1] == '/':
            p = p[:-1]
        p = p.replace("\\","/")
        return True,p
    except Exception as e:
        return False,e
    
def ruyiCheckPortInBlack(p):
    """
    检查端口是否再黑名单中
    """
    p = str(p)
    black_list = ["21","25","3306","6789"]
    if p in black_list:
        return True
    return False

class RYSiteManageView(CustomAPIView):
    """
    get:
    获取网站站点列表
    post:
    网站站点设置
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        is_windows = True if current_os == 'windows' else False
        webServerIns = RySoftShop.objects.filter(type=3).first()
        webServer = ""
        if webServerIns is not None:
            webServer = webServerIns.name
        reqData = get_parameter_dic(request)
        search = reqData.get("search",None)
        module = int(reqData.get("type",0))
        group = int(reqData.get("group",-1))
        is_simple = reqData.get("is_simple","")#简化显示列表，加快显示速度
        queryset = Sites.objects.filter(type=0).order_by("-id")
        # if module:
        #     queryset = queryset.filter(type = module)
        if group >= 0:
            queryset = queryset.filter(group_id = group)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(remark__icontains=search))
        # # 1. 实例化分页器对象
        page_obj = CustomPagination()
        # # 2. 使用自己配置的分页器调用分页方法进行分页
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        if is_simple:
            for m in page_data:
                data.append({
                    'id':m.id,
                    'name':m.name,
                    'path':m.path,
                    'status':m.status,
                })
        else:
            for m in page_data:
                group_name = ""
                if m.group_id == 0:
                    group_name = "默认分组"
                else:
                    group_name = m.get_group_display()
                ssldata,null = WebClient.get_site_cert(webserver=webServer,siteName=m.name,sitePath=m.path,is_simple=True)
                data.append({
                    'id':m.id,
                    'name':m.name,
                    'path':m.path,
                    'status':m.status,
                    'group':m.group_id,
                    'group_name': group_name,
                    'remark':m.remark,
                    'bakNums': RuyiBackup.objects.filter(type=2,fid=str(m.id)).count(),
                    'sslinfo': ssldata,
                    'endTime': formatdatetime(m.endTime) if m.endTime else "",
                    'is_default':m.is_default,
                    'access_log':m.access_log,
                    'error_log':m.error_log,
                    'create_at':formatdatetime(m.create_at),
                })
        return page_obj.get_paginated_response(data)

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        webServerIns = RySoftShop.objects.filter(type=3).first()
        webServer = ""
        if webServerIns is not None:
            webServer = webServerIns.name
        if not webServer:return ErrorResponse(msg="无Web环境，请先安装")
        if action == "save_static_site":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="请输入网站域名/ip")
            if Sites.objects.filter(type=0,name=name).exists():
                return ErrorResponse("已存在同名站点：%s"%name)
            domainList = ast_convert(reqData.get("domainList",[]))
            if len(domainList)<1:return ErrorResponse(msg="请输入网站域名/ip")
            if has_duplicates(domainList):return ErrorResponse(msg="存在重复项")
            SiteDomain_objs = []
            new_domain_list = []
            for dm in domainList:
                if not dm:return ErrorResponse(msg="域名不能为空")
                p_str = dm.strip().split(":")
                domain = p_str[0]
                if domain.find('*') != -1 and domain.find('*.') == -1:
                    return ErrorResponse(msg='域名格式不正确1：%s'%dm)
                if not check_is_domain(domain):
                    return ErrorResponse(msg='域名格式不正确2：%s'%dm)
                p = p_str[1] if len(p_str) == 2 else "80"
                if not re.match(r"^\d+$", p):
                    return ErrorResponse(msg="端口不合法：%s"%dm)
                if ruyiCheckPortInBlack(p):
                    return ErrorResponse(msg="端口在黑名单中：%s"%dm)
                if not check_is_port(int(p)):
                    return ErrorResponse(msg="端口范围不合法：%s"%dm)
                sitedm_ins = SiteDomains.objects.filter(name=domain,port=int(p)).first()
                if sitedm_ins is not None:
                    return ErrorResponse(msg="域名[%s]已被[%s]绑定，请更换!!!"%(dm,sitedm_ins.site.name))
                new_domain_list.append({'domain':domain,"port":p})
                SiteDomain_objs.append(SiteDomains(name=domain,port=int(p),site=None))
            remark = reqData.get("remark","")
            path = reqData.get("path","")
            isok,msg = ruyiPathDirHandle(path,is_windows=is_windows)
            if not isok:return ErrorResponse(msg=msg)
            isok,msg = WebClient.create_site(webserver=webServer,domainList = new_domain_list,siteName=name,sitePath=path)
            if not isok:return ErrorResponse(msg=msg)
            group = int(reqData.get("group",0))
            s_ins = Sites.objects.create(name=name,remark=remark,path=path,group_id=group,type=0)
            for s in SiteDomain_objs:
                s.site = s_ins
            SiteDomains.objects.bulk_create(SiteDomain_objs)
            RuyiAddOpLog(request,msg="【网站管理】-【添加静态网站】 名称：%s ，位置：%s"%(name,path),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "set_site_endtime":
            id = reqData.get("id","")
            endtime = reqData.get("endTime",None)
            endTime_name = endtime
            if not endtime:
                endtime = None
                endTime_name = "永不过期"
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            s_ins.endTime = endtime
            s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【修改到期时间】%s => %s"%(s_ins.name,endTime_name),module="sitemg")
            return DetailResponse(msg="设置成功")
        elif action == "set_site_path":
            id = reqData.get("id","")
            path = reqData.get("path","")
            if not path:return ErrorResponse(msg="路径不能为空")
            if not id:return ErrorResponse(msg="参数错误")
            isok,msg = ruyiPathDirHandle(path,is_windows=is_windows)
            if not isok:return ErrorResponse(msg=msg)
            if not os.path.exists(path):return ErrorResponse(msg="指定网站目录不存在")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            if s_ins.path == path:return ErrorResponse(msg="要修改的目录与原始目录相同，无需修改")
            isok,msg = WebClient.set_site_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,path=path)
            if not isok:return ErrorResponse(msg=msg)
            s_ins.path = path
            s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【修改根目录】%s => %s"%(s_ins.name,path),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "set_site_default":
            id = str(reqData.get("id",""))
            if not id:return ErrorResponse(msg="参数错误")
            isok,msg = WebClient.set_site_default(webserver=webServer,id=id)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【设置默认站点】%s"%(msg),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "del_static_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            isok,msg = WebClient.del_site(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,id=id)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【删除网站】 名称：%s"%s_ins.name,module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="删除成功")
        elif action == "status_static_site":
            op = reqData.get("op","")
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            op_msg = "启动"
            status = True
            if op == "start":
                op_msg = "启动"
                status = True
                if s_ins.is_expired():
                    return ErrorResponse(msg="站点已过期")
                WebClient.start_site(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            elif op == "stop":
                op_msg = "停止"
                status = False
                WebClient.stop_site(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            else:
                return ErrorResponse(msg="类型错误")
            s_ins.status = status
            s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【%s网站】 名称：%s"%(op_msg,s_ins.name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="%s成功"%op_msg)
        elif action == "get_site_conf":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            conf_path,null = WebClient.get_conf_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            data = ReadFile(conf_path['conf_path'])
            return DetailResponse(data=data,msg="success")
        elif action == "get_site_base":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            conf_path,null = WebClient.get_conf_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            if not conf_path:return ErrorResponse(msg="站点错误")
            conf_path['id'] = id
            conf_path['name'] = s_ins.name
            conf_path['path'] = s_ins.path
            conf_path['endTime'] = formatdatetime(s_ins.endTime)
            conf_path['access_log'] = s_ins.access_log
            conf_path['error_log'] = s_ins.error_log
            return DetailResponse(data=conf_path,msg="success")
        elif action == "get_site_antichain":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            isok,data = WebClient.get_site_antichain(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,id=id)
            if not isok:return ErrorResponse(msg=data)
            return DetailResponse(data=data,msg="success")
        elif action == "set_site_antichain":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(reqData.get("cont",{}))
            if not cont:return ErrorResponse(msg="参数错误2")
            status = cont.get("status",False)
            status_name ="开启" if status else "关闭"
            isok,msg = WebClient.set_site_antichain(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【防盗链设置】%s => %s"%(s_ins.name,status_name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "get_site_ratelimit":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            isok,data = WebClient.get_site_ratelimit(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            if not isok:return ErrorResponse(msg=data)
            return DetailResponse(data=data,msg="success")
        elif action == "set_site_ratelimit":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(reqData.get("cont",{}))
            if not cont:return ErrorResponse(msg="参数错误2")
            status = cont.get("status",False)
            status_name ="开启" if status else "关闭"
            isok,msg = WebClient.set_site_ratelimit(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【流量限制】%s => %s"%(s_ins.name,status_name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "set_site_indexdoc":
            id = reqData.get("id","")
            indexdoc = reqData.get("indexdoc","") #"index.html,index.php"
            if not indexdoc:return ErrorResponse(msg="默认文档不能为空")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            isok,msg = WebClient.set_site_indexdoc(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,index=indexdoc)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【修改默认文档】%s => %s"%(s_ins.name,indexdoc),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="修改成功")
        elif action == "get_site_redirect":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            conf_path,null = WebClient.get_conf_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            data = ReadFile(conf_path['redirect_path'])
            if not data:
                data = []
            else:
                data = json.loads(data)
            return DetailResponse(data=data,msg="success")
        elif action == "set_site_redirect":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(reqData.get("cont",{}))
            if not cont:return ErrorResponse(msg="参数错误2")
            status = cont.get("status",False)
            operate = cont.get('operate',"add")#操作动作：add、edit、del
            redirectId = cont.get('redirectId',"")
            if operate == "add":
                status_name = "新增"
            elif operate == "edit":
                editStatus = cont.get("editStatus",False)
                if editStatus:
                    status_name ="开启" if status else "停止"
                else:
                    status_name ="编辑"
            else:
                status_name = "删除"
            isok,msg = WebClient.set_site_redirect(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【重定向】%s => %s => %s"%(s_ins.name,status_name,redirectId),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "set_site_proxy":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(reqData.get("cont",{}))
            if not cont:return ErrorResponse(msg="参数错误2")
            status = cont.get("status",False)
            operate = cont.get('operate',"add")#操作动作：add、edit、del
            name = cont.get('name',"")
            if operate == "add":
                status_name = "新增"
            elif operate == "edit":
                editStatus = cont.get("editStatus",False)
                if editStatus:
                    status_name ="开启" if status else "停止"
                else:
                    status_name ="编辑"
            else:
                status_name = "删除"
            isok,msg = WebClient.set_site_proxy(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【反向代理】%s => %s => %s"%(s_ins.name,status_name,name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "get_site_proxy":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            conf_path,null = WebClient.get_conf_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            data = ReadFile(conf_path['proxy_path'])
            if not data:
                data = []
            else:
                data = json.loads(data)
            return DetailResponse(data=data,msg="success")
        elif action == "get_site_proxy_conf":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="代理名称不能为空")
            conf_path,null = WebClient.get_conf_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            proxy_conf_path = conf_path['proxy_base_path']+ "/" + name + "_" + s_ins.name + ".conf"
            if not os.path.exists(proxy_conf_path):return ErrorResponse(msg="无此配置文件")
            data = ReadFile(proxy_conf_path)
            if not data:
                data = ""
            return DetailResponse(data=data,msg="success")
        elif action == "set_site_proxy_conf":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="代理名称不能为空")
            confcontent = reqData.get("conf","")
            conf_path,null = WebClient.get_conf_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            proxy_conf_path = conf_path['proxy_base_path']+ "/" + name + "_" + s_ins.name + ".conf"
            if not os.path.exists(proxy_conf_path):return ErrorResponse(msg="无此配置文件")
            WriteFile(proxy_conf_path,confcontent)
            RuyiAddOpLog(request,msg="【网站管理】-【反向代理】-【修改代理配置文件】=> 站点：%s => 代理名称：%s"%(s_ins.name,name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="保存成功")
        elif action == "save_site_conf":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            conf_path,null = WebClient.get_conf_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            conf = reqData.get('conf',"")
            if not conf:
                return ErrorResponse(msg="配置文件格式错误")
            WriteFile(conf_path['conf_path'],conf)
            RuyiAddOpLog(request,msg="【网站管理】-【修改配置文件】%s"%(s_ins.name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="修改成功")
        elif action == "get_site_cert":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            data,null = WebClient.get_site_cert(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            return DetailResponse(data=data,msg="success")
        elif action == "set_site_ssl_status":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(reqData.get("cont",{}))
            if not cont:return ErrorResponse(msg="参数错误2")
            status = cont.get("status",False)
            status_name = "开启" if status else "关闭"
            isok,msg = WebClient.set_site_ssl_status(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【SSL】%s => %sSSL"%(s_ins.name,status_name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "set_site_ssl_forcehttps":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(reqData.get("cont",{}))
            if not cont:return ErrorResponse(msg="参数错误2")
            status = cont.get("status",False)
            status_name = "开启" if status else "关闭"
            isok,msg = WebClient.set_site_ssl_forcehttps(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【SSL】%s => %s强制HTTPS"%(s_ins.name,status_name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "save_site_ssl_cert":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(reqData.get("cont",{}))
            if not cont:return ErrorResponse(msg="参数错误2")
            isok,msg = WebClient.save_site_ssl_cert(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【SSL】%s => 保存证书"%(s_ins.name),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        elif action == "get_site_log":
            op = reqData.get("op","")
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            conf_path,null = WebClient.get_conf_path(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path)
            log_path = None
            if op == "access_log":
                log_path = conf_path['access_log_path']
            elif op == "error_log":
                log_path = conf_path['error_log_path']
            else:
                return ErrorResponse(msg="类型错误")
            num = 2000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "site_log_open":
            op = reqData.get("op","")
            id = reqData.get("id","")
            status = reqData.get("status",False)
            status_name ="start" if status else "stop"
            status_name2 ="开启" if status else "关闭"
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            if op not in ["access_log","error_log"]:return ErrorResponse(msg="类型错误")
            isok,null = WebClient.site_log_open(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,action=status_name,type=op)
            if op == "access_log":
                s_ins.access_log = status
                s_ins.save()
            else:
                s_ins.error_log = status
                s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【日志开关】%s => %s %s"%(s_ins.name,status_name2,op),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="设置成功")
        return ErrorResponse(msg="类型错误")

class RYSiteDomainManageView(CustomAPIView):
    """
    get:
    获取网站域名列表
    post:
    网站域名列表设置
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        site_id = int(reqData.get("site",0))
        if site_id < 1:return ErrorResponse(msg="参数错误")
        queryset = SiteDomains.objects.filter(site_id=site_id).order_by("-id")
        # # 1. 实例化分页器对象
        page_obj = CustomPagination()
        # # 2. 使用自己配置的分页器调用分页方法进行分页
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        for m in page_data:
            data.append({
                'id':m.id,
                'name':m.name,
                'port':m.port,
                'site':m.site_id,
                'create_at':formatdatetime(m.create_at)
            })
        return page_obj.get_paginated_response(data)

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        webServerIns = RySoftShop.objects.filter(type=3).first()
        webServer = ""
        if webServerIns is not None:
            webServer = webServerIns.name
        if not webServer:return ErrorResponse(msg="无Web环境，请先安装")
        if action == "add_site_domain":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            domainList = ast_convert(reqData.get("domainList",[]))
            if len(domainList)<1:return ErrorResponse(msg="请输入网站域名/ip")
            if has_duplicates(domainList):return ErrorResponse(msg="存在重复项")
            SiteDomain_objs = []
            new_domain_list = []
            for dm in domainList:
                if not dm:return ErrorResponse(msg="域名不能为空")
                p_str = dm.strip().split(":")
                domain = p_str[0]
                if domain.find('*') != -1 and domain.find('*.') == -1:
                    return ErrorResponse(msg='域名格式不正确1：%s'%dm)
                if not check_is_domain(domain):
                    return ErrorResponse(msg='域名格式不正确2：%s'%dm)
                p = p_str[1] if len(p_str) == 2 else "80"
                if not re.match(r"^\d+$", p):
                    return ErrorResponse(msg="端口不合法：%s"%dm)
                if ruyiCheckPortInBlack(p):
                    return ErrorResponse(msg="端口在黑名单中：%s"%dm)
                if not check_is_port(int(p)):
                    return ErrorResponse(msg="端口范围不合法：%s"%dm)
                sitedm_ins = SiteDomains.objects.filter(name=domain,port=int(p)).first()
                if sitedm_ins is not None:
                    return ErrorResponse(msg="域名[%s]已被[%s]绑定，请更换!!!"%(dm,sitedm_ins.site.name))
                new_domain_list.append({'domain':domain,"port":p})
                SiteDomain_objs.append(SiteDomains(name=domain,port=int(p),site=s_ins))
            error_list = []
            for d in new_domain_list:
                isok,msg = WebClient.add_site_domain(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,domain=d['domain'],port=d['port'])
                if not isok:
                    error_list.append(d['domain']+":"+d['port'])
            er_nums = len(error_list)
            if er_nums<1:
                d_e_msg = "添加成功"
            else:
                suc_nums = len(domainList) - er_nums
                error_dm = ",".join(error_list)
                d_e_msg = f"成功{suc_nums}个，失败{er_nums}个，失败域名：【{error_dm}】"
                SiteDomain_objs = [obj for obj in SiteDomain_objs if not any(
                    obj.name == target['domain'] and obj.port == target['port'] for target in error_list
                )]
            SiteDomains.objects.bulk_create(SiteDomain_objs)
            RuyiAddOpLog(request,msg="【网站管理】-【添加域名】%s => 添加：%s => %s"%(s_ins.name,",".join(domainList),d_e_msg),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg=d_e_msg)
        elif action == "del_site_domain":
            id = reqData.get("id","")
            sid = reqData.get("sid","")
            domain = reqData.get("domain","")
            port = reqData.get("port","")
            if not all([id,sid,domain,port]):return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=sid).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            if SiteDomains.objects.filter(site=s_ins).count() < 2:
                return ErrorResponse(msg="无法删除，剩余一个域名!!!")
            isok,msg = WebClient.del_site_domain(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,id=id)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【删除域名】%s => %s:%s"%(s_ins.name,domain,port),module="sitemg")
            WebClient.reload_service(webserver=webServer)
            return DetailResponse(msg="删除成功")
        return ErrorResponse(msg="类型错误")
    
class RYSiteBackupManageView(CustomAPIView):
    """
    post:
    网站站点备份工具
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        id = reqData.get("id","")
        if not id:return ErrorResponse(msg="参数错误")
        s_ins = Sites.objects.filter(id=id).first()
        if not s_ins:return ErrorResponse(msg="参数错误")
        
        if action == "backup_site":
            site_path = s_ins.path
            site_name = s_ins.name
            if not os.path.exists(site_path):return False,f"【{site_name}】站点路径不存在，已跳过"
            backup_base_path = os.path.join(GetBackupPath(),"sites",site_name)
            if not os.path.exists(backup_base_path):
                os.makedirs(backup_base_path)
            zip_filename = f"site_{site_name}_{time.strftime('%Y%m%d_%H%M%S',time.localtime())}_{GetRandomSet(5)}.zip"
            zip_filename_path = os.path.join(backup_base_path, zip_filename)
            backup_directory(source_dir=site_path,backup_dir=backup_base_path,zip_filename=zip_filename_path,exclude_patterns=[])
            if not os.path.exists(zip_filename_path):
                RuyiAddOpLog(request,msg="【网站管理】-【备份】-【%s】=> 备份失败"%(s_ins.name),module="sitemg")
                return ErrorResponse(msg=f"备份失败")
            else:
                dst_file_size = os.path.getsize(zip_filename_path)
                bak_ins = RuyiBackup.objects.create(name=zip_filename,filename=zip_filename_path,size=dst_file_size,type=2,fid=id)
            RuyiAddOpLog(request,msg="【网站管理】-【备份】-【%s】=> %s"%(s_ins.name,zip_filename_path),module="sitemg")
            return DetailResponse(msg="操作成功")
        elif action == "download_backup_site":
            bid = reqData.get("bid","")
            bk_ins = RuyiBackup.objects.filter(type=2,id=bid).first()
            if not bk_ins:
                return ErrorResponse(msg="没有发现备份文件")
            filename = bk_ins.filename
            if not os.path.exists(filename):
                return ErrorResponse(msg="文件不存在")
            if not os.path.isfile(filename):
                return ErrorResponse(msg="参数错误")
            # file_size = os.path.getsize(filename)
            file_size = bk_ins.size
            response = FileResponse(open(filename, 'rb'))
            response['content_type'] = "application/octet-stream"
            response['Content-Disposition'] = f'attachment;filename="{escape_uri_path(os.path.basename(filename))}"'
            response['Content-Length'] = file_size  # 设置文件大小
            RuyiAddOpLog(request,msg="【网站管理】-【下载备份】-【%s】=> %s"%(s_ins.name,bk_ins.filename),module="sitemg")
            return response
        elif action == "del_backup_site":
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="参数错误")
            bid = reqData.get("bid","")
            bk_ins = RuyiBackup.objects.filter(type=2,fid=id,id=bid).first()
            if bk_ins:
                DeleteFile(bk_ins.filename,empty_tips=False)
                bk_ins.delete()
            else:#无关联网站id的场景删除
                bk_ins = RuyiBackup.objects.filter(type=2,id=bid).first()
                if bk_ins:
                    DeleteFile(bk_ins.filename,empty_tips=False)
                    bk_ins.delete()
            RuyiAddOpLog(request,msg="【网站管理】-【删除备份】-【%s】=> %s"%(s_ins.name,bk_ins.filename),module="sitemg")
            return DetailResponse(msg="删除成功")
        return ErrorResponse(msg="类型错误")

class RYSSLManageView(CustomAPIView):
    """
    get:
    获取网站SSL信息
    post:
    网站SSL设置
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        if action == "get_acme_account":
            type = reqData.get("type","")
            if type == "letsencrypt":
                c_path = GetLetsencryptPath()
                c_content = ReadFile(c_path)
                status = False
                email = ""
                if c_content:
                    j_content=json.loads(c_content)
                    email = j_content.get('email','')
                    status = True if email else False
                return DetailResponse(data={'email':email,'status':status})
            else:
                return ErrorResponse(msg="参数错误")
        elif action == "get_cert_list":
            type = reqData.get("type","")
            site_id = int(reqData.get("site_id",0))
            if type == "letsencrypt":
                c_path = GetLetsencryptPath()
                c_content = ReadFile(c_path)
                if not c_content:return DetailResponse(data=[])
                j_content = json.loads(c_content)
                orders = j_content.get("orders",{})
                if not orders:return DetailResponse(data=[])
                data = []
                current_time = datetime.datetime.now()
                for key, value in orders.items():
                    if value['deploy'] and site_id == value['site_id']:
                        cert_path = os.path.join(value['save_path'],"fullchain.pem")
                        key_path = os.path.join(value['save_path'],"private_key.pem")
                        certinfo = getCertInfo(cert_path)
                        expiration_time = datetime.datetime.strptime(value['cert_timeout'], "%Y-%m-%d %H:%M:%S")
                        days_remaining = (expiration_time - current_time).days
                        if days_remaining<0:days_remaining=0
                        certcontent = ReadFile(cert_path)
                        keycontent = ReadFile(key_path)
                        data.append({
                            'order_no':key,
                            'key':keycontent,
                            'cert':certcontent,
                            'identifiers':value['identifiers'],
                            'domain_list':value['domain_list'],
                            'expire_days':days_remaining,
                            'verifyType':value['verifyType'],
                            'certinfo':certinfo,
                        })
                return DetailResponse(data=data)
            return ErrorResponse(msg="类型错误")
        elif action == "get_letsencrypt_log":
            error = False
            orderover = False
            is_renew = reqData.get("is_renew",False)
            if is_renew == "false":is_renew = False
            if is_renew == "true":is_renew = True
            order_no = reqData.get("order_no","")
            if not order_no:return DetailResponse(data={'data':"",'done': True,'error':error},msg="参数错误")
            c_path = GetLetsencryptPath()
            c_content = ReadFile(c_path)
            if not c_content:return DetailResponse(data={'data':"",'done': True,'error':error},msg="参数错误")
            j_content = json.loads(c_content)
            orders = j_content.get("orders",{})
            # if not orders:return DetailResponse(data={'data':"",'done': True,'error':error})
            orderinfo = None
            if orders:
                orderinfo = orders[order_no] if order_no in orders else None
                if orderinfo:
                    orderover = orderinfo.get("over",True)
            done = orderover
            if is_renew:
                renew_status =orderinfo.get("renew_status","") if orderinfo else ""
                if renew_status == "success":
                    done = True
                else:
                    done = False
            log_path = GetLetsencryptLogPath()
            data = system.GetFileLastNumsLines(log_path,2000)
            if (isinstance(data,bytes) and b"x"*20 in data) or (isinstance(data,str) and "x"*20 in data):
                done = True
                error = True
            return DetailResponse(data={'data':data,'done': done,'error':error},msg="success")
        return ErrorResponse(msg="类型错误")
            
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        if action == "create_acme_account":
            type = reqData.get("type","")
            email = reqData.get("email","")
            if not check_is_email(email):
                return ErrorResponse(msg="邮箱格式错误")
            if type == "letsencrypt":
                acmetools = letsencryptTool()
                acmetools.register_account({'email':email})
                RuyiAddOpLog(request,msg="【网站管理】-【SSL】申请letsencrypt账号：%s"%(email),module="sitemg")
                return DetailResponse(msg="创建成功")
            else:
                return ErrorResponse(msg="参数错误")
        elif action == "apply_cert_letsencrypt":
            domains = ast_convert(reqData.get("domains",[]))
            site_id = reqData.get("site_id","")
            verifyType = reqData.get("verifyType","file")
            #if verifyType not in ['file','dns','tls']:return ErrorResponse(msg="验证类型错误")
            if not verifyType == 'file':return ErrorResponse(msg="验证类型错误")#目前仅支持file
            if not domains:return ErrorResponse(msg="请选择需要申请的域名")
            if not site_id:return ErrorResponse(msg="参数错误")
            if verifyType == "file":
                for dm in domains:
                    if "*" in dm:
                        return ErrorResponse(msg="不支持*泛域名证书")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            site_info = {"id":s_ins.id,"name":s_ins.name,"path":s_ins.path}
            order_no = md5(json.dumps(domains)+str(site_id)+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            log_path = GetLetsencryptLogPath()
            WriteFile(log_path,b"",mode="wb")
            t = threading.Thread(
                target=apply_letsencrypt_certificate,
                args=(
                    domains,
                    site_info,
                    verifyType,
                    order_no
                ))
            t.start()
            RuyiAddOpLog(request,msg="【网站管理】-【SSL】站点：%s,申请letsencrypt证书"%(s_ins.name),module="sitemg")
            return DetailResponse(data=order_no,msg="申请中...")
        elif action == "renew_cert_letsencrypt":
            order_no = ""
            site_id = reqData.get("site_id","")
            c_path = GetLetsencryptPath()
            c_content = ReadFile(c_path)
            if not c_content:return ErrorResponse(msg="无此站点订单信息")
            j_content = json.loads(c_content)
            orders = j_content.get("orders",{})
            if not orders:return ErrorResponse(msg="无此站点订单信息")
            for order,value in orders.items():
                if str(value['site_id']) == str(site_id):
                    order_no = order
            if not order_no:return ErrorResponse(msg="无此站点订单信息")
            cert_timeout = j_content['orders'][order_no]['cert_timeout']
            cert_timeout = datetime.datetime.strptime(cert_timeout, "%Y-%m-%d %H:%M:%S")
            nowtime = datetime.datetime.now()
            sy_days = (cert_timeout - nowtime).days
            if sy_days>30:
                return ErrorResponse(msg="证书有效期大于30天，暂时忽略续签")
            log_path = GetLetsencryptLogPath()
            WriteFile(log_path,b"",mode="wb")
            j_content['orders'][order_no]['renew_status'] = ""
            WriteFile(c_path,json.dumps(j_content))
            t = threading.Thread(
                target=renew_letsencrypt_certificate,
                args=(order_no,)# 注意逗号是必须得
                )
            t.start()
            RuyiAddOpLog(request,msg="【网站管理】-【SSL】站点：%s,续签letsencrypt证书"%(orders[order_no]['site_name']),module="sitemg")
            return DetailResponse(data=order_no,msg="续签中...")
        return ErrorResponse(msg="类型错误")
    
def apply_letsencrypt_certificate(domains,site_info,verifyType,order_no):
    """
    站点证书申请
    """
    acmetools = letsencryptTool()
    acmetools.apply_certificate(domain_list=domains,site_info=site_info,verifyType=verifyType,order_no=order_no)
    
def renew_letsencrypt_certificate(order_no):
    """
    续签站点证书
    """
    renew_acmetools = letsencryptTool()
    renew_acmetools.renew_certificate(order_no=order_no)
    