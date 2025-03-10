#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-26
# +-------------------------------------------------------------------
# | EditDate: 2025-02-26
# +-------------------------------------------------------------------

# ------------------------------
# docker 广场管理
# ------------------------------
import os,json
from math import ceil
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic,ast_convert,DeleteDir,RunCommand,formatdatetime
from utils.jsonResponse import ErrorResponse,DetailResponse,SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.dockerClass import DockerClient
from utils.ruyiclass.dockerInclude.ry_dk_square import main as dksquare
from concurrent.futures import ThreadPoolExecutor
from apps.sysdocker.models import RyDockerApps

class RYDockerSquareAppTagsListManageView(CustomAPIView):
    """
    get:
    获取广场标签列表
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        data = dksquare().get_apptags_list()
        return DetailResponse(data=data)
    
class RYUpdateDockerSquareAppsTagsManageView(CustomAPIView):
    """
    post:
    更新应用/标签列表
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        isok,msg = dksquare().update_dk_apps_and_tags()
        if not isok:
            return ErrorResponse(msg=msg)
        return DetailResponse(msg=msg)

class RYGetDockerSquareAppsListManageView(CustomAPIView):
    """
    get:
    获取广场列表
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        page = int(reqData.get("page",1))
        limit = int(reqData.get("limit",10))
        type = str(reqData.get("type","0"))
        searchContent = reqData.get("searchContent","")
        newsq = dksquare()
        softlist = newsq.get_apps_list()
        soft_names = list(RyDockerApps.objects.all().values_list("appname",flat=True).order_by('id'))
        if type == "1":
                # softlist = [item for item in softlist if item.get("appname") in soft_names]
                queryset = RyDockerApps.objects.all().order_by('-id')
                if searchContent:
                    queryset = queryset.filter(name__icontains=searchContent)
                # # 1. 实例化分页器对象
                page_obj = CustomPagination()
                # # 2. 使用自己配置的分页器调用分页方法进行分页
                page_data = page_obj.paginate_queryset(queryset, request)
                data = []
                stdout, stderr = RunCommand("docker-compose ls --format json")
                compose_json = []
                try:
                    compose_json = json.loads(stdout)
                except:
                    pass
                for m in page_data:
                    appid = m.appid
                    name = m.name
                    appname = m.appname
                    icon=f"{appname}.png"
                    status = m.status
                    path = ""
                    has_name_ps = False
                    for c in compose_json:
                        if c['Name'] == name.lower():
                            has_name_ps = True
                            status = ''.join([char for char in c['Status'] if not char.isdigit() and char != '(' and char != ')'])
                            path = os.path.dirname(c['ConfigFiles'])
                    if not has_name_ps and not status in ["install"]:status="exited"
                    if not path:path=newsq.get_dkapp_path({"appname":appname,"name":name})
                    params = ast_convert(m.params)
                    ports= [] 
                    for key, value in params.items():
                        if "_port" in key.lower():
                            ports.append(value)
                    appinfo={}
                    for s in softlist:
                        if s['appname'] == appname:
                            appinfo = s
                            break 
                    data.append({
                        'id':m.id,
                        'name':name,
                        'appid':appid,
                        'appname':appname,
                        'icon':icon,
                        'version':m.version,
                        'allowport':m.allowport,
                        "params":params,
                        "ports":ports,
                        'status':status,
                        'path':path,
                        'appinfo':appinfo,
                        'create_at':formatdatetime(m.create_at)
                    })
                return page_obj.get_paginated_response(data=data)
        else:
            for st in softlist:
                if st.get("appname") in soft_names:
                    st["installed"] = 1
                    st["installedCount"] = int(st["installedCount"]) + 1
            softlist = [item for item in softlist if item.get("show", 1) != 0]
            softlist = sorted(softlist, key=lambda x: x.get("sort", 0))
            if searchContent:
                softlist = [item for item in softlist if (searchContent.lower() in item.get("appname").lower()) or (searchContent.lower() in item.get("desc").lower())]
            if type == "0":
                pass
            else:
                softlist = [item for item in softlist if str(item.get("type")) == type]
            
            #一次最大条数限制
            limit = 99 if limit > 99 else limit
            total_nums = len(softlist)
            total_pages = ceil(total_nums / limit)
            if page > total_pages:
                page = total_pages
            # 根据分页参数对结果进行切片
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_data = softlist[start_idx:end_idx]
            return SuccessResponse(data=paginated_data,total=total_nums,page=page,limit=limit)
    
    
class RYGetDockerSquareAppsManageView(CustomAPIView):
    """
    post:
    获取广场APP操作
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self,request):
        reqData = get_parameter_dic(request)
        action = reqData.pop("action","")
        newsq = dksquare()
        if action == "add":
            appname = reqData.get('appname',"")
            name = reqData.get('name',"")
            if not name:return ErrorResponse(msg="参数错误")
            if RyDockerApps.objects.filter(name=name).exists():return ErrorResponse(msg="存在同名应用，请更换")
            isok,msg = newsq.generate_app(cont=reqData)
            if not isok:
                app_path = newsq.get_dkapp_path(cont={"appname":appname,"name":name})
                DeleteDir(app_path)
                return ErrorResponse(msg=msg)
            RyDockerApps.objects.create(**reqData)
            RuyiAddOpLog(request,msg=f"【容器】-【广场APP】=> 添加：{appname}=>{name}",module="dockermg")
            return DetailResponse(msg=msg)
        elif action == "set_status":
            status = reqData.get("status","")
            id = reqData.get('id',"")
            if not id or not status:return DetailResponse(msg="缺少参数")
            ins = RyDockerApps.objects.filter(id=id).first()
            if not ins:return ErrorResponse(msg="未查询此应用")
            appname = ins.appname
            name = ins.name
            app_path = newsq.get_dkapp_path(cont={"appname":appname,"name":name})
            compose_conf_path = f"{app_path}/docker-compose.yml"
            isok,msg = newsq.set_status(compose_conf_path,status)
            if not isok:return ErrorResponse(msg=msg)
            if status == "remove":
                ins.delete()
                DeleteDir(app_path)
            elif status in ["restart","rebuild","start"]:
                ins.status = "running"
                ins.save()
            elif status in ["stop"]:
                ins.status = "exited"
                ins.save()
            RuyiAddOpLog(request,msg=f"【容器】-【广场APP】- {status} => {name}",module="dockermg")
            return DetailResponse(msg=msg)
        return ErrorResponse(msg="类型错误")