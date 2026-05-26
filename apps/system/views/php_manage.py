#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-05-06
# +-------------------------------------------------------------------
# | EditDate: 2025-05-06
# +-------------------------------------------------------------------

# ------------------------------
# PHP项目管理
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
from utils.ruyiclass.phpClass import PhpClient
from apps.sysbak.models import RuyiBackup
from utils.ruyiclass.webClass import WebClient
from apps.system.views.site_manage import ruyiPathDirHandle,ruyiCheckPortInBlack
from utils.server.system import system

def create_php_site(webServer,siteName,sitePath,cont):
    WebClient.create_site(webserver=webServer,siteName=siteName,sitePath=sitePath,cont=cont)

class RYPhpManageView(CustomAPIView):
    """
    get:
    获取PHP版本信息
    post:
    设置PHP项目
    """
    permission_classes = [IsAuthenticated]

    def get(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "list_version":
            data = []
            php_list = RySoftShop.objects.filter(name='php',installed=True).order_by('-is_default','install_version')
            for item in php_list:
                version = item.install_version
                from utils.install.php import is_php_running
                running = False
                try:
                    running = is_php_running(version,is_windows=is_windows)
                except:
                    pass
                data.append({
                    'id':item.id,
                    'name':'php',
                    'version':version,
                    'is_default':item.is_default,
                    'running':running,
                })
            return DetailResponse(data=data)
        return ErrorResponse(msg="类型错误")

    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "set_default":
            version = reqData.get("version","")
            if not version:return ErrorResponse(msg="参数错误")
            ins = RySoftShop.objects.filter(name='php',install_version=version).first()
            if not ins:return ErrorResponse(msg="该版本不存在")
            RySoftShop.objects.filter(name='php').exclude(install_version=version).update(is_default=False)
            ins.is_default = True
            ins.save()
            RuyiAddOpLog(request,msg=f"【软件商店】-【设置】=>php-{version}为默认版本",module="softmg")
            return DetailResponse(msg="设置成功")
        return ErrorResponse(msg="类型错误")

class RYPhpProjectManageView(CustomAPIView):
    """
    get:
    获取PHP项目列表
    post:
    设置PHP项目
    """
    permission_classes = [IsAuthenticated]

    def get(self,request):
        reqData = get_parameter_dic(request)
        search = reqData.get("search",None)
        group = int(reqData.get("group",-1))
        is_simple = reqData.get("is_simple","")
        id = int(reqData.get("id",0))
        queryset = Sites.objects.filter(type=3).order_by("-id")
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
                runstatus = PhpClient(siteName=m.name,sitePath=m.path,cont=project_cfg).is_project_running()
                runstatus = True if runstatus else False
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
                runstatus = PhpClient(siteName=m.name,sitePath=m.path,cont=project_cfg).is_project_running()
                runstatus = True if runstatus else False
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
        webServer = "php"
        if action == "create_site":
            name = reqData.get("name","")
            if not name:return ErrorResponse(msg="请输入项目名称")
            if Sites.objects.filter(name=name).exists():
                return ErrorResponse("已存在同名站点：%s，请更换项目名称！"%name)
            project_cfg = ast_convert(reqData.get("project_cfg",{}))
            php_version = project_cfg.get("php_version","")
            if not php_version:return ErrorResponse(msg="请选择PHP版本")
            port = project_cfg.get("port","")
            if not re.match(r"^\d+$", port):
                return ErrorResponse(msg="端口不合法：%s"%port)
            if ruyiCheckPortInBlack(port):
                return ErrorResponse(msg="端口在黑名单中：%s"%port)
            if not check_is_port(int(port)):
                return ErrorResponse(msg="端口范围不合法：%s"%port)
            if is_service_running(port=int(port)):return ErrorResponse(msg="端口被占用，请更换：%s"%port)
            remark = reqData.get("remark","")
            path = reqData.get("path","")
            isok,msg = ruyiPathDirHandle(path,is_windows=is_windows)
            if not isok:return ErrorResponse(msg=msg)
            group = int(reqData.get("group",0))
            s_ins = Sites.objects.create(name=name,remark=remark,path=path,group_id=group,type=3,project_cfg=project_cfg)
            t = threading.Thread(
                target=create_php_site,
                args=(
                    webServer,
                    name,
                    path,
                    project_cfg
                ))
            t.start()
            RuyiAddOpLog(request,msg="【网站管理】-【添加PHP项目】 名称：%s ，位置：%s"%(name,path),module="sitemg")
            return DetailResponse(data={'id':s_ins.id,'name':name},msg="创建成功")
        elif action == "edit_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            new_project_cfg = ast_convert(reqData.get("project_cfg",{}))
            if not new_project_cfg:return ErrorResponse(msg="配置不能为空")
            old_project_cfg = ast_convert(s_ins.project_cfg)
            old_instance = PhpClient(siteName=s_ins.name,sitePath=s_ins.path,cont=old_project_cfg)
            old_instance.stop_site()
            py_instance = PhpClient(siteName=s_ins.name,sitePath=s_ins.path,cont=new_project_cfg)
            try:
                res = py_instance.edit_site()
                if not res:
                    raise Exception("edit_site failed")
            except Exception as e:
                old_instance = PhpClient(siteName=s_ins.name,sitePath=s_ins.path,cont=old_project_cfg)
                try:
                    old_instance.edit_site()
                    old_instance.start_site()
                except:
                    pass
                return ErrorResponse(msg=f"修改失败：{e}")
            s_ins.project_cfg = new_project_cfg
            s_ins.save()
            RuyiAddOpLog(request,msg="【网站管理】-【修改PHP项目】 名称：%s"%s_ins.name,module="sitemg")
            return DetailResponse(msg="修改成功")
        elif action == "del_site":
            id = reqData.get("id","")
            if not id:return ErrorResponse(msg="参数错误")
            s_ins = Sites.objects.filter(id=id).first()
            if not s_ins:return ErrorResponse(msg="无此站点")
            cont = ast_convert(s_ins.project_cfg)
            isok,msg = WebClient.del_site(webserver=webServer,siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【删除PHP项目】 名称：%s"%s_ins.name,module="sitemg")
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
            py_instance = PhpClient(siteName=s_ins.name,sitePath=s_ins.path,cont=cont)
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
            RuyiAddOpLog(request,msg="【网站管理】-【PHP项目】=> %s【%s】"%(op_msg,s_ins.name),module="sitemg")
            return DetailResponse(msg="%s成功"%op_msg)
        elif action == "get_project_log":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=3).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = PhpClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            conf_info = py_instance.get_conf_path()
            log_path = conf_info['log_command']
            data = system.GetFileLastNumsLines(log_path,2000)
            return DetailResponse(data=data,msg="success")
        elif action == "get_loadstatus":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=3).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = PhpClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            data = py_instance.get_loadstatus()
            return DetailResponse(data=data,msg="success")
        elif action == "check_composer":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=3).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = PhpClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            installed = py_instance.is_composer_installed()
            return DetailResponse(data={'installed':installed},msg="success")
        elif action == "install_composer":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=3).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            py_instance = PhpClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            isok,msg = py_instance.install_composer()
            if not isok:return ErrorResponse(msg=msg)
            RuyiAddOpLog(request,msg="【网站管理】-【PHP项目】-【安装Composer】=> %s"%ins.name,module="sitemg")
            return DetailResponse(msg=msg)
        elif action == "run_composer":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=3).first()
            if not ins:return ErrorResponse(msg="参数错误")
            command = reqData.get("command","")
            packages = reqData.get("packages","")
            if not command:return ErrorResponse(msg="请输入Composer命令")
            allowed_commands = ['install','update','require','remove','dump-autoload','show','self-update','create-project','init','status','outdated','clear-cache']
            cmd_parts = command.strip().split()
            base_cmd = cmd_parts[0] if cmd_parts else ""
            if base_cmd not in allowed_commands:
                return ErrorResponse(msg=f"不允许执行的命令：{base_cmd}，仅支持：{', '.join(allowed_commands)}")
            cont = ast_convert(ins.project_cfg)
            py_instance = PhpClient(siteName=ins.name,sitePath=ins.path,cont=cont)
            isok,msg = py_instance.run_composer(command,packages)
            RuyiAddOpLog(request,msg="【网站管理】-【PHP项目】-【执行Composer %s】=> %s"%(command,ins.name),module="sitemg")
            if not isok:
                return DetailResponse(data={'output':msg,'success':False},msg="执行完成（有错误）")
            return DetailResponse(data={'output':msg,'success':True},msg="执行成功")
        elif action == "get_fpm_pool":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=3).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            php_version = cont.get("php_version","")
            if not php_version:return ErrorResponse(msg="未配置PHP版本")
            from utils.install.php import get_php_fpm_pool_conf, get_php_fpm_pool_port, RY_GET_PHP_FPM_POOL_PARAMS, RY_GET_PHP_FPM_PRESETS
            pool_conf = get_php_fpm_pool_conf(ins.name, php_version, is_windows=is_windows)
            pool_port = get_php_fpm_pool_port(ins.name, php_version)
            pool_params = {}
            if pool_conf:
                pool_params = RY_GET_PHP_FPM_POOL_PARAMS(php_version, is_windows=is_windows)
            data = {
                'pool_conf': pool_conf or '',
                'pool_port': pool_port,
                'pool_params': pool_params,
                'presets': RY_GET_PHP_FPM_PRESETS(),
                'pool_name': ins.name.replace('.', '_').replace('-', '_'),
            }
            return DetailResponse(data=data, msg="success")
        elif action == "save_fpm_pool":
            id = int(reqData.get("id",0))
            if not id:return ErrorResponse(msg="参数错误")
            ins = Sites.objects.filter(id=id,type=3).first()
            if not ins:return ErrorResponse(msg="参数错误")
            cont = ast_convert(ins.project_cfg)
            php_version = cont.get("php_version","")
            if not php_version:return ErrorResponse(msg="未配置PHP版本")
            pool_params = ast_convert(reqData.get("pool_params",{}))
            if not pool_params:return ErrorResponse(msg="参数错误")
            from utils.install.php import create_php_fpm_pool_conf
            isok, result = create_php_fpm_pool_conf(
                site_name=ins.name,
                site_path=ins.path,
                php_version=php_version,
                pool_params=pool_params,
                is_windows=is_windows
            )
            if not isok:
                return ErrorResponse(msg=result if isinstance(result, str) else "保存失败")
            if isinstance(result, dict):
                cont['pool_port'] = result.get('pool_port','')
                cont['pool_name'] = result.get('pool_name','')
                cont['listen_addr'] = result.get('listen_addr','')
                ins.project_cfg = cont
                ins.save()
            from utils.install.php import Reload_PHP, is_php_running
            if not is_windows and is_php_running(php_version, is_windows=is_windows):
                Reload_PHP(version=php_version, is_windows=is_windows)
            RuyiAddOpLog(request, msg="【网站管理】-【PHP项目】-【保存FPM Pool配置】=> %s"%ins.name, module="sitemg")
            return DetailResponse(msg="保存成功")
