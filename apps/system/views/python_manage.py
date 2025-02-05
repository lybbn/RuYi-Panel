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
# Python项目管理
# ------------------------------

import re,time
import threading
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import ReadFile,WriteFile,GetSoftList,get_parameter_dic,current_os,formatdatetime,ast_convert,check_is_port,is_service_running
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.install.install_soft import Check_Soft_Installed
from utils.ruyiclass.pythonClass import PythonClient
from apps.system.models import Sites
from django.db.models import Q
from apps.sysbak.models import RuyiBackup
from utils.ruyiclass.webClass import WebClient
from apps.syslogs.logutil import RuyiAddOpLog
from apps.system.views.site_manage import ruyiPathDirHandle,ruyiCheckPortInBlack
from utils.server.system import system

def create_python_site(webServer,siteName,sitePath,cont):
    """
    创建python项目
    """
    WebClient.create_site(webserver=webServer,siteName=siteName,sitePath=sitePath,cont=cont)
    
def isRightApplication(cont):
    framework = cont.get("framework","")
    application = cont.get("application","")
    if framework == "django":
        if not application:return False
        pattern = r'^[\w]+\.((wsgi)|(asgi)):[\w]+$'
        return bool(re.match(pattern, application))
    elif framework == "flask":
        if not application:return False
        pattern = r'^[\w]+:[\w]+$'
        return bool(re.match(pattern, application))
    return True

class RYPythonSiteManageView(CustomAPIView):
    """
    get:
    获取Python 站点项目信息
    post:
    设置Python 站点项目
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        search = reqData.get("search",None)
        group = int(reqData.get("group",-1))
        is_simple = reqData.get("is_simple","")#简化显示列表，加快显示速度
        id = int(reqData.get("id",0))
        queryset = Sites.objects.filter(type=1).order_by("-id")
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
                runstatus = PythonClient(siteName=m.name,sitePath=m.path,cont=project_cfg).is_project_running()
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
                runstatus = PythonClient(siteName=m.name,sitePath=m.path,cont=project_cfg).is_project_running()
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
        webServer = "python"
        if action == "create_site":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="请输入项目名称")
            if Sites.objects.filter(type=0,name=name).exists():
                return ErrorResponse("已存在同名站点：%s，请更换项目名称！"%name)
            project_cfg = ast_convert(reqData.get("project_cfg",{}))
            port = project_cfg.get("port")
            start_method = project_cfg.get("start_method","")
            if start_method not in ["command"]:
                if not re.match(r"^\d+$", port):
                    return ErrorResponse(msg="端口不合法：%s"%port)
                if ruyiCheckPortInBlack(port):
                    return ErrorResponse(msg="端口在黑名单中：%s"%port)
                if not check_is_port(int(port)):
                    return ErrorResponse(msg="端口范围不合法：%s"%port)
                if is_service_running(port=int(port)):return ErrorResponse(msg="端口被占用，请更换：%s"%port)
            start_command = project_cfg.get("start_command","")
            framework = project_cfg.get("framework","")
            if not isRightApplication(project_cfg):return ErrorResponse(msg="应用参数格式错误")
            rukou = project_cfg.get("rukou","")
            if not start_method in ['command','daphne','uwsgi','gunicorn']:return ErrorResponse(msg="启动方式错误")
            if start_method in ['command'] and not start_command:return ErrorResponse(msg="缺少启动命令")
            if framework not in ['python'] and not rukou:return ErrorResponse(msg="缺少入口文件")
            protocol = project_cfg.get("protocol","http")
            if protocol not in ["http","socket"]:return ErrorResponse(msg="协议错误")
            
            remark = reqData.get("remark","")
            path = reqData.get("path","")
            isok,msg = ruyiPathDirHandle(path,is_windows=is_windows)
            if not isok:return ErrorResponse(msg=msg)
            group = int(reqData.get("group",0))
            s_ins = Sites.objects.create(name=name,remark=remark,path=path,group_id=group,type=1,project_cfg=project_cfg)
            t = threading.Thread(
                target=create_python_site,
                args=(
                    webServer,
                    name,
                    path,
                    project_cfg
                ))
            t.start()
            RuyiAddOpLog(request,msg="【网站管理】-【添加Python项目】 名称：%s ，位置：%s"%(name,path),module="sitemg")
            return DetailResponse(data={'id':s_ins.id,'name':name},msg="开始创建")
        elif action == "edit_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            new_project_cfg = ast_convert(reqData.get("project_cfg",{}))
            if not new_project_cfg:return ErrorResponse(msg="配置不能为空")
            if not isRightApplication(new_project_cfg):return ErrorResponse(msg="应用参数格式错误")
            new_install_req = new_project_cfg['install_reqs']
            new_requirements = new_project_cfg['requirements']
            if new_install_req and not new_requirements:return ErrorResponse(msg="请选择需安装的依赖文件")
            old_project_cfg = ast_convert(s_ins.project_cfg)
            old_instance = PythonClient(siteName=s_ins.name,sitePath=s_ins.path,cont=old_project_cfg)
            old_instance.stop_site()
            is_need_time = False
            new_start_method = new_project_cfg['start_method']
            old_install_req = old_project_cfg['install_reqs']
            if not new_start_method == old_project_cfg['start_method']:
                if not old_install_req and new_install_req:
                    is_need_time = True
                elif not new_start_method == "command":
                    is_need_time = True
            py_instance = PythonClient(siteName=s_ins.name,sitePath=s_ins.path,cont=new_project_cfg)
            res = py_instance.edit_site(is_need_time=is_need_time)
            if not res:return ErrorResponse(msg="修改失败")
            s_ins.project_cfg = new_project_cfg
            s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【修改Python项目】 名称：%s"%s_ins.name,module="sitemg")
            return DetailResponse(msg="修改成功")
        elif action == "del_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(s_ins.project_cfg)
            isok,msg = WebClient.del_site(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【删除Python项目】 名称：%s"%s_ins.name,module="sitemg")
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
            py_instance = PythonClient(siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
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
            RuyiAddOpLog(request,msg="【网站管理】-【Python项目】=> %s【%s】"%(op_msg,s_ins.name),module="sitemg")
            return DetailResponse(msg="%s成功"%op_msg)
        elif action == "get_project_log":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=1).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = PythonClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            conf_info = py_instance.get_conf_path()
            start_method = cont.get("start_method","")
            if start_method == "gunicorn":
                log_type = reqData.get("log_type","access")
                if log_type == "access":
                    log_path = conf_info['log_access_gunicorn']
                elif log_type == "error":
                    log_path = conf_info['log_error_gunicorn']
                else:
                    return ErrorResponse(msg="类型错误")
            else:
                log_path = conf_info[f'log_{start_method}']
            data = system.GetFileLastNumsLines(log_path,2000)
            return DetailResponse(data=data,msg="success")
        elif action == "get_create_log":
            error = False
            done = False
            id = int(reqData.get("id",0))
            if not id:
                return DetailResponse(data={'data':"",'done': True,'error':error},msg="参数错误")
            ins = Sites.objects.filter(id=id,type=1).first()
            if not ins:
                return DetailResponse(data={'data':"",'done': True,'error':error},msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            log_path = PythonClient(siteName=ins.name,sitePath=ins.path,cont=cont).get_conf_path()['log_create_path']
            data = system.GetFileLastNumsLines(log_path,2000)
            successkey = "create project success by ruyi"
            if (isinstance(data,bytes) and successkey.encode() in data) or (isinstance(data,str) and successkey in data):
                done = True
                error = False
            elif (isinstance(data,bytes) and b"x"*20 in data) or (isinstance(data,str) and "x"*20 in data):
                done = True
                error = True
            return DetailResponse(data={'data':data,'done': done,'error':error},msg="success")
        elif action in ["get_conf","save_conf"]:
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=1).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = PythonClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            conf_info = py_instance.get_conf_path()
            start_method = cont.get("start_method","")
            if not start_method in ["uwsgi","gunicorn"]:return ErrorResponse(msg="该启动类型无配置文件")
            conf_file_path = conf_info[f"{start_method}_conf_path"]
            if action == "get_conf":
                data = ReadFile(conf_file_path)
                return DetailResponse(data=data,msg="success")
            else:
                content = reqData.get('conf',"")
                if not content:
                    return ErrorResponse(msg="配置文件格式错误")
                WriteFile(conf_file_path,content)
                RuyiAddOpLog(request,msg="【网站管理】-【Python项目】=> 修改配置文件【%s】=>%s"%(ins.name,conf_file_path),module="sitemg")
                time.sleep(0.2)
                py_instance.sync_conf_to_db()
                py_instance.restart_site()
                return DetailResponse(data="",msg="保存成功")
        elif action in ["get_piplist","pip_install","pip_uninstall","get_loadstatus"]:
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=1).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = PythonClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            if action == "get_piplist":
                search = reqData.get("search","")
                data = py_instance.get_requirements_list()
                if search:
                    search=search.lower()
                    newdata = []
                    for d in data:
                        if search in (d['name']).lower():
                            newdata.append(d)
                    data = newdata
                return DetailResponse(data=data,msg="success")
            elif action == "pip_install":
                res = py_instance.requirements_install_module(cont=reqData)
                name = reqData.get("name","")
                version = reqData.get("version","")
                if version:name = f"{name}==version"
                if not res:return ErrorResponse(msg="安装失败")
                RuyiAddOpLog(request,msg="【网站管理】-【Python项目】=> 【%s】=>安装库 %s"%(ins.name,name),module="sitemg")
                return DetailResponse(data="",msg="安装成功")
            elif action == "pip_uninstall":
                res = py_instance.requirements_uninstall_module(cont=reqData)
                name = reqData.get("name","")
                if not res:return ErrorResponse(msg="卸载失败")
                RuyiAddOpLog(request,msg="【网站管理】-【Python项目】=> 【%s】=>卸载库 %s"%(ins.name,name),module="sitemg")
                return DetailResponse(data="",msg="卸载成功")
            elif action == "get_loadstatus":
                data = py_instance.get_loadstatus()
                return DetailResponse(data=data,msg="success")
            else:
                return ErrorResponse(msg="类型错误")
        return ErrorResponse(msg="类型错误")

class RYPythonManageView(CustomAPIView):
    """
    get:
    获取Python项目信息
    post:
    设置Python项目
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
                if s['name'] == 'python':
                    detail_version =s['versions'][0]['c_version']
                    s_installed,s_version,s_status,s_install_path = Check_Soft_Installed(name=s['name'],is_windows=is_windows,version=detail_version,get_status=False)
                    if s_installed:
                        data.append({
                            'id':s['id'],
                            'name':s['name'],
                            'version':detail_version
                        })
            return DetailResponse(data=data)
        elif action == "get_env_info":
            root_path = action = reqData.get("path","")
            rukou_path = action = reqData.get("rukou","")
            data = PythonClient.get_env_info(path=root_path,rukou=rukou_path)
            return DetailResponse(data=data)
        return ErrorResponse(msg="类型错误")