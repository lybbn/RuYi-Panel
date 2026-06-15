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
import os,json,re
from math import ceil
from utils.customView import CustomAPIView
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic,ast_convert,DeleteDir,DeleteFile,RunCommand,formatdatetime,pip_install_package
from utils.jsonResponse import ErrorResponse,DetailResponse,SuccessResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.dockerInclude.ry_dk_square import main as dksquare
from apps.sysdocker.models import RyDockerApps


def _build_softlist_dict(softlist):
    """构建 softlist 字典，用于快速查找"""
    return {item['appname']: item for item in softlist}


def _parse_compose_json(stdout):
    """解析 docker-compose ls 的 JSON 输出，兼容 JSON 数组和 JSONL 格式"""
    if not stdout or not stdout.strip():
        return []
    try:
        result = json.loads(stdout)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    # 兼容 JSONL 格式（每行一个 JSON 对象）
    compose_list = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                compose_list.append(obj)
        except (json.JSONDecodeError, ValueError):
            continue
    return compose_list


def _build_compose_dict(compose_json):
    """构建 compose 字典，用于快速查找（key 为小写名称）"""
    return {c['Name'].lower(): c for c in compose_json}


def _get_compose_status(name, compose_dict):
    """从字典中获取 compose 状态"""
    compose_info = compose_dict.get(name.lower())
    if not compose_info:
        return None, None
    compose_status = compose_info.get('Status', '')
    status = re.sub(r'[\d()]+', '', compose_status).strip() or compose_status
    if not status:
        return None, None
    path = os.path.dirname(compose_info.get('ConfigFiles', ''))
    return status, path

class RYDockerSquareAppTagsListManageView(CustomAPIView):
    """
    get:
    获取广场标签列表
    """
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
        data = dksquare().get_apptags_list()
        return DetailResponse(data=data)
    
class RYUpdateDockerSquareAppsTagsManageView(CustomAPIView):
    """
    post:
    更新应用/标签列表
    """
    permission_classes = [IsAuthenticated]
    
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
    
    def get(self,request):
        reqData = get_parameter_dic(request)
        page = int(reqData.get("page",1))
        limit = int(reqData.get("limit",10))
        type = str(reqData.get("type","0"))
        searchContent = reqData.get("searchContent","")
        newsq = dksquare()
        
        # 获取 softlist 并构建字典
        softlist = newsq.get_apps_list()
        softlist_dict = _build_softlist_dict(softlist)
        
        # 使用集合存储已安装的应用名，用于快速判断
        soft_names_set = set(RyDockerApps.objects.all().values_list("appname", flat=True))
        
        if type == "1":
                queryset = RyDockerApps.objects.all().order_by('-id')
                if searchContent:
                    queryset = queryset.filter(name__icontains=searchContent)
                page_obj = CustomPagination()
                page_data = page_obj.paginate_queryset(queryset, request)
                data = []
                
                # 获取 compose 列表并构建字典
                stdout, stderr = RunCommand("docker-compose ls --format json")
                compose_json = _parse_compose_json(stdout)
                compose_dict = _build_compose_dict(compose_json)
                
                for m in page_data:
                    # 只对安装中的应用调用 sync_app_install_status
                    if m.status in ("install", "install_failed"):
                        newsq.sync_app_install_status(m)
                    
                    appid = m.appid
                    name = m.name
                    appname = m.appname
                    icon = f"{appname}.png"
                    status = m.status
                    path = ""
                    
                    # 使用字典查找替代循环
                    compose_status, compose_path = _get_compose_status(name, compose_dict)
                    if compose_status is not None:
                        status = compose_status
                        path = compose_path or ""
                    elif status not in ["install", "install_failed"]:
                        status = "exited"
                    
                    if not path:
                        path = newsq.get_dkapp_path({"appname":appname,"name":name})
                    
                    params = ast_convert(m.params)
                    ports = [value for key, value in params.items() if "_port" in key.lower()]
                    
                    # 使用字典查找替代循环
                    appinfo = softlist_dict.get(appname, {})
                    
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
            # 使用集合判断，替代列表遍历
            for st in softlist:
                if st.get("appname") in soft_names_set:
                    st["installed"] = 1
                    st["installedCount"] = int(st.get("installedCount", 0)) + 1
            
            softlist = [item for item in softlist if item.get("show", 1) != 0]
            softlist = sorted(softlist, key=lambda x: x.get("sort", 0))
            
            if searchContent:
                search_lower = searchContent.lower()
                softlist = [item for item in softlist 
                           if search_lower in item.get("appname", "").lower() 
                           or search_lower in item.get("desc", "").lower()]
            
            if type != "0":
                softlist = [item for item in softlist if str(item.get("type")) == type]
            
            # 一次最大条数限制
            limit = min(limit, 99)
            total_nums = len(softlist)
            total_pages = ceil(total_nums / limit) if total_nums > 0 else 1
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
            DB_PIP_MAP = {
                'pgsql': 'psycopg2-binary',
                'postgresql': 'psycopg2-binary',
                'mongodb': 'pymongo',
            }
            if appname in DB_PIP_MAP:
                pip_install_package(DB_PIP_MAP[appname])
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
            elif status == "rebuild":
                install_log_path = newsq.get_dkapp_install_logpath({"appname":appname,"name":name})
                if os.path.exists(install_log_path):
                    DeleteFile(install_log_path)
                ins.status = "install"
                ins.save()
            elif status in ["restart","start"]:
                ins.status = "running"
                ins.save()
            elif status in ["stop"]:
                ins.status = "exited"
                ins.save()
            RuyiAddOpLog(request,msg=f"【容器】-【广场APP】- {status} => {name}",module="dockermg")
            return DetailResponse(msg=msg)
        return ErrorResponse(msg="类型错误")
