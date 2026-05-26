#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-05-21
# +-------------------------------------------------------------------
# | EditDate: 2025-05-21
# +-------------------------------------------------------------------

# ------------------------------
# Node.js项目管理
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
from utils.ruyiclass.nodejsClass import NodeClient
from apps.sysbak.models import RuyiBackup
from utils.ruyiclass.webClass import WebClient
from apps.system.views.site_manage import ruyiPathDirHandle,ruyiCheckPortInBlack
from utils.install.nodejs import create_default_env
from utils.server.system import system

def create_node_site(webServer,siteName,sitePath,cont):
    WebClient.create_site(webserver=webServer,siteName=siteName,sitePath=sitePath,cont=cont)

class RYNodejsManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "list_version":
            data = []
            soft_list = GetSoftList()
            for s in soft_list:
                if s['name'] == 'nodejs':
                    detail_version =s['versions'][0]['c_version']
                    s_installed,s_version,s_status,s_install_path = Check_Soft_Installed(name=s['name'],is_windows=is_windows,version=detail_version,get_status=False)
                    if s_installed:
                        data.append({
                            'id':s['id'],
                            'name':s['name'],
                            'version':detail_version,
                            'is_default':False
                        })
            queryset = RySoftShop.objects.filter(name='nodejs')
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
            ins = RySoftShop.objects.filter(name='nodejs',install_version=version).first()
            if not ins:return ErrorResponse(msg="该版本不存在")
            install_path = ins.install_path
            version_path = install_path.replace("\\","/")+'/version.ry'
            if not os.path.exists(version_path):return ErrorResponse(msg="该版本未安装")
            create_default_env(version,install_path,is_windows=is_windows)
            RySoftShop.objects.filter(name='nodejs').exclude(install_version=version).update(is_default=False)
            ins.is_default = True
            ins.save()
            RuyiAddOpLog(request,msg=f"【软件商店】-【设置】=>nodejs-{version}为默认版本",module="softmg")
            return DetailResponse(msg="设置成功")
        return ErrorResponse(msg="类型错误")

class RYNodejsProjectManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        reqData = get_parameter_dic(request)
        search = reqData.get("search",None)
        group = int(reqData.get("group",-1))
        is_simple = reqData.get("is_simple","")
        id = int(reqData.get("id",0))
        queryset = Sites.objects.filter(type=2).order_by("-id")
        if group >= 0:
            queryset = queryset.filter(group_id = group)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(remark__icontains=search))
        if id:queryset=queryset.filter(id=id)
        page_obj = CustomPagination()
        page_data = page_obj.paginate_queryset(queryset, request)
        data = []
        if is_simple:
            for m in page_data:
                project_cfg = ast_convert(m.project_cfg)
                runstatus = NodeClient(siteName=m.name,sitePath=m.path,cont=project_cfg).is_project_running()
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
                runstatus = NodeClient(siteName=m.name,sitePath=m.path,cont=project_cfg).is_project_running()
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
        webServer = "node"
        if action == "create_site":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="请输入项目名称")
            if Sites.objects.filter(name=name).exists():
                return ErrorResponse("已存在同名站点：%s，请更换项目名称！"%name)
            project_cfg = ast_convert(reqData.get("project_cfg",{}))
            port = project_cfg.get("port")
            start_method = project_cfg.get("start_method","command")
            if not re.match(r"^\d+$", str(port)):
                return ErrorResponse(msg="端口不合法：%s"%port)
            if ruyiCheckPortInBlack(port):
                return ErrorResponse(msg="端口在黑名单中：%s"%port)
            if not check_is_port(int(port)):
                return ErrorResponse(msg="端口范围不合法：%s"%port)
            if is_service_running(port=int(port)):return ErrorResponse(msg="端口被占用，请更换：%s"%port)
            start_command = project_cfg.get("start_command","")
            if not start_method in ['command','pm2']:return ErrorResponse(msg="启动方式错误")
            if not start_command:return ErrorResponse(msg="缺少启动命令")

            remark = reqData.get("remark","")
            path = reqData.get("path","")
            isok,msg = ruyiPathDirHandle(path,is_windows=is_windows)
            if not isok:return ErrorResponse(msg=msg)
            group = int(reqData.get("group",0))
            s_ins = Sites.objects.create(name=name,remark=remark,path=path,group_id=group,type=2,project_cfg=project_cfg)
            t = threading.Thread(
                target=create_node_site,
                args=(
                    webServer,
                    name,
                    path,
                    project_cfg
                ))
            t.start()
            RuyiAddOpLog(request,msg="【网站管理】-【添加Node项目】 名称：%s ，位置：%s"%(name,path),module="sitemg")
            return DetailResponse(data={'id':s_ins.id,'name':name},msg="创建成功")
        elif action == "edit_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id,type=2).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            new_project_cfg = ast_convert(reqData.get("project_cfg",{}))
            if not new_project_cfg:return ErrorResponse(msg="配置不能为空")
            old_project_cfg = ast_convert(s_ins.project_cfg)
            old_instance = NodeClient(siteName=s_ins.name,sitePath=s_ins.path,cont=old_project_cfg)
            old_instance.stop_site()
            is_need_time = True
            node_instance = NodeClient(siteName=s_ins.name,sitePath=s_ins.path,cont=new_project_cfg)
            res = node_instance.edit_site(is_need_time=is_need_time)
            if not res:return ErrorResponse(msg="修改失败")
            s_ins.project_cfg = new_project_cfg
            s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【修改Node项目】 名称：%s"%s_ins.name,module="sitemg")
            return DetailResponse(msg="修改成功")
        elif action == "del_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id,type=2).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(s_ins.project_cfg)
            isok,msg = WebClient.del_site(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【删除Node项目】 名称：%s"%s_ins.name,module="sitemg")
            return DetailResponse(msg="删除成功")
        elif action == "set_status":
            op = reqData.get("op","")
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id,type=2).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            oldstatus = s_ins.status
            cont = ast_convert(s_ins.project_cfg)
            op_msg = "启动"
            status = True
            node_instance = NodeClient(siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if op == "start":
                op_msg = "启动"
                res_status = node_instance.start_site()
                status = True if res_status else oldstatus
            elif op == "stop":
                op_msg = "停止"
                res_status = node_instance.stop_site()
                status = False if res_status else oldstatus
            elif op == "restart":
                op_msg = "重启"
                res_status = node_instance.restart_site()
                status = True if res_status else oldstatus
            else:
                return ErrorResponse(msg="类型错误")
            if not res_status:return ErrorResponse(msg=f"{op_msg}失败")
            if not oldstatus == status:
                s_ins.status = status
                s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【Node项目】=> %s【%s】"%(op_msg,s_ins.name),module="sitemg")
            return DetailResponse(msg="%s成功"%op_msg)
        elif action == "get_project_log":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=2).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            node_instance = NodeClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            conf_info = node_instance.get_conf_path()
            log_type = reqData.get("log_type","access")
            start_method = cont.get("start_method","command")
            if log_type == "error":
                log_path = conf_info['log_base_path']+'/error.log'
            else:
                log_path = conf_info[f'log_{start_method}']
            data = system.GetFileLastNumsLines(log_path,2000)
            return DetailResponse(data=data,msg="success")
        elif action in ["get_loadstatus","get_conf","save_conf"]:
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=2).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            node_instance = NodeClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            if action == "get_loadstatus":
                data = node_instance.get_loadstatus()
                return DetailResponse(data=data,msg="success")
            elif action == "get_conf":
                conf_info = node_instance.get_conf_path()
                start_method = cont.get("start_method","command")
                script_path = node_instance.get_run_script_path()
                data = ""
                if os.path.exists(script_path):
                    data = open(script_path,'r',encoding='utf-8').read()
                return DetailResponse(data=data,msg="success")
            elif action == "save_conf":
                conf = reqData.get("conf","")
                if not conf:return ErrorResponse(msg="配置不能为空")
                script_path = node_instance.get_run_script_path()
                WriteFile(script_path,conf)
                node_instance.restart_site()
                return DetailResponse(msg="保存成功")
        return ErrorResponse(msg="类型错误")
