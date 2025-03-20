#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-11-18
# +-------------------------------------------------------------------
# | EditDate: 2024-11-18
# +-------------------------------------------------------------------

# ------------------------------
# go项目管理
# ------------------------------
import os,re
import threading
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import GetSoftList,get_parameter_dic,current_os,WriteFile,DeleteDir,ast_convert,formatdatetime,is_service_running,check_is_port
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.install.install_soft import Check_Soft_Installed
from apps.sysshop.models import RySoftShop
from apps.syslogs.logutil import RuyiAddOpLog
from apps.system.models import Sites
from django.db.models import Q
from utils.ruyiclass.goClass import GoClient
from apps.sysbak.models import RuyiBackup
from utils.ruyiclass.webClass import WebClient
from apps.system.views.site_manage import ruyiPathDirHandle,ruyiCheckPortInBlack
from utils.install.go import create_default_env
from utils.server.system import system

def create_go_site(webServer,siteName,sitePath,cont):
    """
    创建go项目
    """
    WebClient.create_site(webserver=webServer,siteName=siteName,sitePath=sitePath,cont=cont)
    
class RYGoManageView(CustomAPIView):
    """
    get:
    获取Go项目信息
    post:
    设置Go项目
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "list_version":
            data = []
            soft_list = GetSoftList()
            for s in soft_list:
                if s['name'] == 'go':
                    detail_version =s['versions'][0]['c_version']
                    s_installed,s_version,s_status,s_install_path = Check_Soft_Installed(name=s['name'],is_windows=is_windows,version=detail_version,get_status=False)
                    if s_installed:
                        data.append({
                            'id':s['id'],
                            'name':s['name'],
                            'version':detail_version,
                            'is_default':False
                        })
            queryset = RySoftShop.objects.filter(name='go')
            for q in queryset:
                for d in data:
                    if d['version'] == q.install_version:
                        d['is_default'] = q.is_default
            return DetailResponse(data=data)
        return ErrorResponse(msg="类型错误") 
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "set_default":
            version = reqData.get("version","")
            if not version:return ErrorResponse(msg="参数错误")
            ins = RySoftShop.objects.filter(name='go',install_version=version).first()
            if not ins:return ErrorResponse(msg="该版本不存在")
            install_path = ins.install_path
            version_path = install_path.replace("\\","/")+'/version.ry'
            if not os.path.exists(version_path):return ErrorResponse(msg="该版本未安装")
            create_default_env(version,install_path,is_windows=is_windows)
            RySoftShop.objects.filter(name='go').exclude(install_version=version).update(is_default=False)
            ins.is_default = True
            ins.save()
            RuyiAddOpLog(request,msg=f"【软件商店】-【设置】=>go-{version}为默认版本",module="softmg")
            return DetailResponse(msg="设置成功")
        return ErrorResponse(msg="类型错误")

class RYGoProjectManageView(CustomAPIView):
    """
    get:
    获取Go项目列表
    post:
    设置Go项目
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        search = reqData.get("search",None)
        group = int(reqData.get("group",-1))
        is_simple = reqData.get("is_simple","")#简化显示列表，加快显示速度
        id = int(reqData.get("id",0))
        queryset = Sites.objects.filter(type=4).order_by("-id")
        if group >= 0:
            queryset = queryset.filter(group_id = group)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(remark__icontains=search))
        if id:queryset=queryset.filter(id=id)
        # # 1. 实例化分页器对象
        page_obj = CustomPagination()
        # # 2. 使用自己配置的分页器调用分页方法进行分页
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        if is_simple:
            for m in page_data:
                project_cfg = ast_convert(m.project_cfg)
                runstatus = GoClient(siteName=m.name,sitePath=m.path,cont=project_cfg).is_project_running()
                runstatus =True if runstatus else False
                data.append({
                    'id':m.id,
                    'name':m.name,
                    'path':m.path,
                    'status':runstatus,
                })
        else:
            for m in page_data:
                group_name = ""
                if m.group_id == 0:
                    group_name = "默认分组"
                else:
                    group_name = m.get_group_display()
                project_cfg = ast_convert(m.project_cfg)
                runstatus = GoClient(siteName=m.name,sitePath=m.path,cont=project_cfg).is_project_running()
                runstatus =True if runstatus else False
                data.append({
                    'id':m.id,
                    'name':m.name,
                    'path':m.path,
                    'status':runstatus,
                    'group':m.group_id,
                    'group_name': group_name,
                    'remark':m.remark,
                    'project_cfg':project_cfg,
                    'bakNums': RuyiBackup.objects.filter(type=2,fid=str(m.id)).count(),
                    'endTime': formatdatetime(m.endTime) if m.endTime else "",
                    'create_at':formatdatetime(m.create_at)
                })
        return page_obj.get_paginated_response(data)
    
    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        webServer = "go"
        if action == "create_site":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="请输入项目名称")
            if Sites.objects.filter(name=name).exists():
                return ErrorResponse("已存在同名站点：%s，请更换项目名称！"%name)
            project_cfg = ast_convert(reqData.get("project_cfg",{}))
            port = project_cfg.get("port")
            start_method = 'command'
            if not re.match(r"^\d+$", port):
                return ErrorResponse(msg="端口不合法：%s"%port)
            if ruyiCheckPortInBlack(port):
                return ErrorResponse(msg="端口在黑名单中：%s"%port)
            if not check_is_port(int(port)):
                return ErrorResponse(msg="端口范围不合法：%s"%port)
            if is_service_running(port=int(port)):return ErrorResponse(msg="端口被占用，请更换：%s"%port)
            start_command = project_cfg.get("start_command","")
            bin = project_cfg.get("bin","")
            if not start_method in ['command']:return ErrorResponse(msg="启动方式错误")
            if start_method in ['command'] and not start_command:return ErrorResponse(msg="缺少启动命令")
            if not bin:return ErrorResponse(msg="缺少命令路径")
            
            remark = reqData.get("remark","")
            path = reqData.get("path","")
            isok,msg = ruyiPathDirHandle(path,is_windows=is_windows)
            if not isok:return ErrorResponse(msg=msg)
            group = int(reqData.get("group",0))
            s_ins = Sites.objects.create(name=name,remark=remark,path=path,group_id=group,type=4,project_cfg=project_cfg)
            t = threading.Thread(
                target=create_go_site,
                args=(
                    webServer,
                    name,
                    path,
                    project_cfg
                ))
            t.start()
            RuyiAddOpLog(request,msg="【网站管理】-【添加Go项目】 名称：%s ，位置：%s"%(name,path),module="sitemg")
            return DetailResponse(data={'id':s_ins.id,'name':name},msg="创建成功")
        elif action == "edit_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            new_project_cfg = ast_convert(reqData.get("project_cfg",{}))
            if not new_project_cfg:return ErrorResponse(msg="配置不能为空")
            old_project_cfg = ast_convert(s_ins.project_cfg)
            old_instance = GoClient(siteName=s_ins.name,sitePath=s_ins.path,cont=old_project_cfg)
            old_instance.stop_site()
            is_need_time = True
            py_instance = GoClient(siteName=s_ins.name,sitePath=s_ins.path,cont=new_project_cfg)
            res = py_instance.edit_site(is_need_time=is_need_time)
            if not res:return ErrorResponse(msg="修改失败")
            s_ins.project_cfg = new_project_cfg
            s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【修改Go项目】 名称：%s"%s_ins.name,module="sitemg")
            return DetailResponse(msg="修改成功")
        elif action == "del_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(s_ins.project_cfg)
            isok,msg = WebClient.del_site(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【删除Go项目】 名称：%s"%s_ins.name,module="sitemg")
            return DetailResponse(msg="删除成功")
        elif action == "set_status":
            op = reqData.get("op","")
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            oldstatus = s_ins.status
            cont = ast_convert(s_ins.project_cfg)
            op_msg = "启动"
            status = True
            py_instance = GoClient(siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if op == "start":
                op_msg = "启动"
                res_status = py_instance.start_site()
                status = True if res_status else oldstatus
            elif op == "stop":
                op_msg = "停止"
                res_status = py_instance.stop_site()
                status = False if res_status else oldstatus
            elif op == "restart":
                op_msg = "重启"
                res_status = py_instance.restart_site()
                status = True if res_status else oldstatus
            else:
                return ErrorResponse(msg="类型错误")
            if not res_status:return ErrorResponse(msg=f"{op_msg}失败")
            if not oldstatus == status:
                s_ins.status = status
                s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【Go项目】=> %s【%s】"%(op_msg,s_ins.name),module="sitemg")
            return DetailResponse(msg="%s成功"%op_msg)
        elif action == "get_project_log":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=4).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = GoClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            conf_info = py_instance.get_conf_path()
            start_method = "command"
            log_path = conf_info[f'log_{start_method}']
            data = system.GetFileLastNumsLines(log_path,2000)
            return DetailResponse(data=data,msg="success")
        elif action in ["get_loadstatus"]:
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=4).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = GoClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            if action == "get_loadstatus":
                data = py_instance.get_loadstatus()
                return DetailResponse(data=data,msg="success")
            else:
                return ErrorResponse(msg="类型错误")
        return ErrorResponse(msg="类型错误")