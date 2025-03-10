#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-04-26
# +-------------------------------------------------------------------
# | EditDate: 2024-04-26
# +-------------------------------------------------------------------

# ------------------------------
# 应用商店
# ------------------------------
import os
import time
import json
from math import ceil
from rest_framework.views import APIView
from utils.jsonResponse import ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.common import get_parameter_dic,GetSoftList,current_os,GetLogsPath,ast_convert
from utils.install.install_soft import Ry_Get_Soft_Performance,Ry_Set_Soft_Performance,Ry_Uninstall_Soft,Check_Soft_Installed,Ry_Restart_Soft,Ry_Stop_Soft,Ry_Reload_Soft,Ry_Get_Soft_Info_Path,Ry_Get_Soft_LoadStatus,Ry_Get_Soft_Conf,Ry_Save_Soft_Conf
from apps.systask.models import SysTaskCenter
import datetime
from utils.server.system import system
from django.db import transaction
from apps.sysshop.models import RySoftShop
from utils.install.redis import Redis_Connect,RY_GET_REDIS_CONF_OPTIONS
from concurrent.futures import ThreadPoolExecutor
from apps.syslogs.logutil import RuyiAddOpLog
from utils.customView import CustomAPIView
from apps.system.views.common import executeNextTask
from apps.system.models import Databases

def soft_install_callback(job_id="",version={},ok=True):
    try:
        task= SysTaskCenter.objects.get(job_id=job_id)
        if ok:
            task.status = 3
            name = version['name']
            password = version.get('password',"")
            info = {}
            for m in GetSoftList():
                if m['name'] == name:
                    info = m
                    break
            info = json.dumps(info)
            if name in ["python","go"]:
                if name == "go":
                    RySoftShop.objects.filter(name=name).update(is_default=False)
                if RySoftShop.objects.filter(name=name,install_version=version['c_version']).exists():
                    RySoftShop.objects.filter(name=name,install_version=version['c_version']).update(install_path=version['install_path'],installed=True,status=1,info=info,is_default=True)
                else:
                    RySoftShop.objects.create(name=name,install_version=version['c_version'],install_path=version['install_path'],installed=True,status=1,password=password,info=info,type=int(version.get('type',0)))
            else:
                RySoftShop.objects.create(name=name,install_version=version['c_version'],install_path=version['install_path'],installed=True,status=2,password=password,info=info,type=int(version.get('type',0)))
        else:
            task.status = 2
        end_time = datetime.datetime.now()  # 记录任务结束时间
        if task.exec_at:
            task.duration = (end_time - task.exec_at).total_seconds()
        task.save()
        #执行下一个任务
        executeNextTask()
    except:
        pass

#类型：
#0 全部、1 已安装、2 数据库 3、Web服务器、4 运行环境、5 安全防护

class RYSoftShopListView(CustomAPIView):
    """
    post:
    获取应用列表
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        reqData = get_parameter_dic(request)
        softlist = GetSoftList()
        is_windows = True if current_os == 'windows' else False
        type = str(reqData.get("type","0"))
        searchContent = reqData.get("searchContent","")
        if searchContent:
            softlist = [item for item in softlist if (searchContent.lower() in item.get("title").lower()) or (searchContent.lower() in item.get("desc").lower())]
        if type == "0":
            pass
        else:
            if type == "1":
                soft_names = list(RySoftShop.objects.filter(installed=True).values_list("name",flat=True).order_by('id'))
                softlist = [item for item in softlist if item.get("name") in soft_names]
            else: 
                softlist = [item for item in softlist if str(item.get("type")) == type]
        page = int(reqData.get("page",1))
        limit = int(reqData.get("limit",10))
        #一次最大条数限制
        limit = 30 if limit > 30 else limit
        total_nums = len(softlist)
        total_pages = ceil(total_nums / limit)
        if page > total_pages:
            page = total_pages
        # 根据分页参数对结果进行切片
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_data = softlist[start_idx:end_idx]
        #单线程
        # for p in paginated_data:
        #     p['installed'],p['version'],p['status'],p['install_path'] = Check_Soft_Installed(name=p['name'],is_windows=is_windows)
        #     if p['versions']:
        #         for v in p['versions']:
        #             v['url'] = None
        
        #并行处理
        data_nums = len(paginated_data)
        if data_nums>0:
            def process_item(p):
                get_status = True
                c_version = None
                p['is_default'] = True
                if p['name'] in ["python","go"]:
                    c_version = p['versions'][0]['c_version']
                    get_status = False
                p['installed'], p['version'], p['status'], p['install_path'] = Check_Soft_Installed(name=p['name'], is_windows=is_windows,version=c_version,get_status=get_status)
                if p['versions']:
                    for v in p['versions']:
                        v['url'] = None
                        hidev = v.get("hide",None)
                        v['hide'] = True if hidev else False
                if p['name'] in ["python","go"]:
                    p['status']=True
                    if p['name'] == "go":
                        if not RySoftShop.objects.filter(name=p['name'],install_version=p['version'],is_default=True).exists():
                            p['is_default'] = False
                return p
            with ThreadPoolExecutor(max_workers=data_nums) as executor:
                paginated_data = list(executor.map(process_item, paginated_data))

        data = {
            "soft":{
                "list":paginated_data,
                "page":page,
                "limit":limit,
                "total":total_nums
            },
            "is_windows":True if current_os == 'windows' else False,
        }
        return DetailResponse(data=data)
    
class RYSoftShopManageView(CustomAPIView):
    """
    post:
    应用管理
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        id = int(reqData.get("id",0))
        type = int(reqData.get("type",2))
        softlist = GetSoftList()
        soft = [item for item in softlist if id == item.get("id")]
        if not soft:
            return ErrorResponse(msg="此应用不存在")
        soft = soft[0]
        if action == "install":
            version_id = int(reqData.get("version_id",0))
            version = [item for item in soft["versions"] if version_id == item.get("id")]
            if not version:
                return ErrorResponse(msg="应用版本错误")
            version = version[0]
            if SysTaskCenter.objects.filter(name__icontains="安装"+soft['name']+"-"+version['c_version'],status__in=[0,1]).exists():
                return ErrorResponse(msg="该应用正在安装中，无需重复安装!!!")
            detail_version =version['c_version'] if soft['name'] in ['python','go'] else None
            s_installed,s_version,s_status,s_install_path = Check_Soft_Installed(name=soft['name'],is_windows=is_windows,version=detail_version)
            if s_installed:
                return ErrorResponse(msg="该应用已安装，请勿重复安装!!!")
            else:
                if detail_version:
                    RySoftShop.objects.filter(name=soft['name'],install_version=detail_version).delete()
                else:
                    RySoftShop.objects.filter(name=soft['name']).delete()
            taskname = "安装"+soft['name']+"-"+version['c_version']
            job_id = soft['name']+"-"+version['c_version']+"_"+str(int(datetime.datetime.now().timestamp()))
            version['job_id'] = job_id
            version['log'] = job_id+".log"
            version['name'] = soft['name']
            version['type'] = soft['type']
            parmas = {'type':type,'name':soft['name'],'version':version,'is_windows':is_windows,'call_back':'apps.system.views.soft_shop.soft_install_callback'}
            task = SysTaskCenter.objects.create(name=taskname,type=0,log=version['log'],status=0,func_path='utils.install.install_soft.Ry_Install_Soft',params=json.dumps(parmas))
            # task.execute_task()
            executeNextTask()
            #直接执行
            #installTask(job_id,Ry_Install_Soft,func_args=[type,soft['name'],version,is_windows])
            # Ry_Install_Soft(type=type,name=soft['name'],version=version,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【安装】=>"+soft['name']+"-"+version['c_version'],module="softmg")
            return DetailResponse(data={'id':task.id},msg="安装成功")
        elif action == "uninstall":
            if soft['name'] == "mysql":
                if Databases.objects.filter(db_type=0).exists():
                    return ErrorResponse(msg="当前已有数据库，请先删除再卸载！！！")
            if soft['name'] in ["python","go"]:#允许多个版本存在
                version_post = reqData.get("version",None)#如果提供了版本（c_version），就卸载指定，没提供取第一个
                version = version_post if version_post else soft["versions"][0]['c_version']
                Ry_Uninstall_Soft(name=soft['name'],is_windows=is_windows,version=version)
                RySoftShop.objects.filter(name=soft['name'],install_version=version).delete()
                RuyiAddOpLog(request,msg="【软件商店】-【卸载】=>"+soft['name']+version,module="softmg")
            else:
                Ry_Uninstall_Soft(name=soft['name'],is_windows=is_windows)
                RySoftShop.objects.filter(name=soft['name']).delete()
                RuyiAddOpLog(request,msg="【软件商店】-【卸载】=>"+soft['name'],module="softmg")
            return DetailResponse(msg="卸载成功")
        elif action == "status":
            status = reqData.get("status",None)
            t_msg = "启动成功"
            s_status = False
            if status == "stop":
                Ry_Stop_Soft(name=soft['name'],is_windows=is_windows)
                s_status = False
                t_msg = "停止成功"
            elif status == 'restart':
                Ry_Restart_Soft(name=soft['name'],is_windows=is_windows)
                s_status = True
                t_msg = "重启成功"
            elif status == 'reload':
                Ry_Reload_Soft(name=soft['name'],is_windows=is_windows)
                s_status = True
                t_msg = "重载成功"
            else:
                return ErrorResponse(msg="类型错误")
            RySoftShop.objects.filter(name=soft['name']).update(status=s_status)
            RuyiAddOpLog(request,msg="【软件商店】=>【"+soft['name']+"】"+t_msg[:2],module="softmg")
            return DetailResponse(msg=t_msg)
        elif action == "get_error_log":
            soft_ins = RySoftShop.objects.filter(name=soft['name'],installed=True).first()
            if not soft_ins:
                return ErrorResponse(msg="软件未安装")
            error_log_path = Ry_Get_Soft_Info_Path(name=soft['name'],type="error",is_windows=is_windows)
            num = 2000
            data = system.GetFileLastNumsLines(error_log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_access_log":
            soft_ins = RySoftShop.objects.filter(name=soft['name'],installed=True).first()
            if not soft_ins:
                return ErrorResponse(msg="软件未安装")
            access_log_path = Ry_Get_Soft_Info_Path(name=soft['name'],type="access",is_windows=is_windows)
            num = 2000
            data = system.GetFileLastNumsLines(access_log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_slow_log":
            soft_ins = RySoftShop.objects.filter(name=soft['name'],installed=True).first()
            if not soft_ins:
                return ErrorResponse(msg="软件未安装")
            slow_log_path = Ry_Get_Soft_Info_Path(name=soft['name'],type="slow",is_windows=is_windows)
            num = 2000
            data = system.GetFileLastNumsLines(slow_log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_loadstatus":
            data = Ry_Get_Soft_LoadStatus(name=soft['name'],is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "get_performance":
            data = Ry_Get_Soft_Performance(name=soft['name'],is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "set_performance":
            cont = ast_convert(reqData.get("cont",{}))
            data = Ry_Set_Soft_Performance(name=soft['name'],cont=cont,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【调整性能】=>"+soft['name'],module="softmg")
            Ry_Reload_Soft(name=soft['name'],is_windows=is_windows)
            return DetailResponse(msg="设置成功")
        elif action == "get_conf":
            data = Ry_Get_Soft_Conf(name=soft['name'],is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "save_conf":
            conf = reqData.get('conf',"")
            if not conf:
                return ErrorResponse(msg="配置文件格式错误")
            data = Ry_Save_Soft_Conf(name=soft['name'],conf=conf,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【修改配置】=>"+soft['name'],module="softmg")
            Ry_Reload_Soft(name=soft['name'],is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        return ErrorResponse(msg="类型错误")
    
class RYSoftInstallLogsView(CustomAPIView):
    """
    post:
    应用管理
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","all")
        id = int(reqData.get("id",0))
        if not id:
            return ErrorResponse(msg="参数错误")
        task = SysTaskCenter.objects.filter(id=id).first()
        if not task:
            return ErrorResponse(msg="参数错误")
        params = task.get_params()
        name = ""
        if task.type == 0:
            name = params.get("name","")
        else:
            return ErrorResponse(msg="暂未开放")
        log_path = os.path.join(os.path.abspath(GetLogsPath()),name,task.log)
        if not os.path.exists(log_path):
            # return ErrorResponse(msg="日志文件不存在")
            return DetailResponse(data={'data':"暂无日志信息",'done': False},msg="success")
        if action == 'all':#读取文件所有内容（限定超过范围则返回最新指定行数）
            num = 4000
            data = system.GetFileLastNumsLines(log_path,num)
            return DetailResponse(data={'data':data,'done': True},msg="success")
        elif action == 'new_lines':
            done =True if task.status in [2,3] else False
            data = system.GetFileLastNumsLines(log_path,4000)
            return DetailResponse(data={'data':data,'done': done},msg="success")
        else:
            return ErrorResponse(msg="类型错误")
        
class RYSoftInfoManageView(CustomAPIView):
    """
    post:
    应用信息管理
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        is_windows = True if current_os == 'windows' else False
        if action == "get_soft_info":
            name = reqData.get("name","")
            softlist = GetSoftList()
            if not softlist:
                return ErrorResponse(msg="应用错误")
            id = ""
            for item in softlist:
                if item['name'] == name:
                    id = item['id']
                    break
            if not id:
                return ErrorResponse(msg="参数错误")
            s_installed,s_version,s_status,s_install_path = Check_Soft_Installed(name=name,is_windows=is_windows)
            data = {
                "id":id,
                "installed":s_installed,
                "version":s_version,
                "status":s_status,
                "install_path":s_install_path,
                "name":name,
            }
            return DetailResponse(data=data)
        elif action == "get_redis_dblist":
            conf_options = RY_GET_REDIS_CONF_OPTIONS()
            db_nums = int(conf_options.get('databases',16))
            data = []
            preload = True
            for i in range(0, db_nums):
                tmp = {}
                tmp['id'] = i
                tmp['name'] = 'DB{}'.format(i)
                try:
                    db_conn = Redis_Connect(preload=preload,db_nums=db_nums,db=i)
                    tmp['keynum'] = db_conn.dbsize() if db_conn else 0 
                    data.append(tmp)
                except Exception as e:
                    tmp['keynum'] = 0
                preload = False
            return DetailResponse(data=data)
        elif action == "redis_flashdb":
            ids = ast_convert(reqData.get("ids",[]))
            msg_db=""
            if not ids:
                msg_db="所有数据库"
                ids = []
                conf_options = RY_GET_REDIS_CONF_OPTIONS()
                db_nums = int(conf_options.get('databases',16))
                for i in range(0,db_nums):
                    ids.append(i)
            else:
                msg_db=','.join(ids)
            db_conn = Redis_Connect(db=0)
            if not db_conn:
                return ErrorResponse(msg="redis连接错误")
            for x in ids:
                db_conn = Redis_Connect(db=x)
                db_conn.flushdb()
            RuyiAddOpLog(request,msg="redis数据库->清空数据库："+msg_db,module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "redis_set_val":
            key = ast_convert(reqData.get("key",""))
            value = ast_convert(reqData.get("value",""))
            db = int(reqData.get("db",0))
            exptime = reqData.get("exptime", None)
            if not key or not value:
                return ErrorResponse(msg="缺少参数")
            db_conn = Redis_Connect(db=db)
            if not db_conn:
                return ErrorResponse(msg="redis连接错误")
            if exptime is not None and exptime:
                db_conn.set(key, value, int(exptime))
            else:
                exptime = "永久"
                db_conn.set(key, value)
            RuyiAddOpLog(request,msg="redis数据库->设置/修改键值：(key=%s,value=%s,db=%s,exptime=%s)"%(key,value,db,exptime),module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "redis_del_val":
            key = ast_convert(reqData.get("key",""))
            db = int(reqData.get("db",0))
            if not key:
                return ErrorResponse(msg="缺少参数")
            db_conn = Redis_Connect(db=db)
            if not db_conn:
                return ErrorResponse(msg="redis连接错误")
            db_conn.delete(key)
            RuyiAddOpLog(request,msg="redis数据库->删除键值：(key=%s,db=%s)"%(key,db),module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "get_redis_keylist":
            search = reqData.get("search","*")
            if search:
                search = "*" + search + "*"
            else:
                search = "*"
            db_inx = int(reqData.get("db",0))
            db_conn = Redis_Connect(db=db_inx)
            if not db_conn:
                return ErrorResponse(msg="redis连接错误")
            total_nums = 0
            try:
                total_nums = db_conn.dbsize()
            except Exception as e:
                return ErrorResponse(msg=e)
            page = int(reqData.get("page",1))
            limit = int(reqData.get("limit",10))
            #一次最大条数限制
            limit = min(limit, 999)
            total_pages = ceil(total_nums / limit)
            page = 1 if page<1 else page 
            if page > total_pages:
                page = total_pages
            page = 1 if page<1 else page 
            # 根据分页参数对结果进行切片
            cursor = 0
            all_keys = []
            while True:
                cursor, keys = db_conn.scan(cursor=cursor, match=search, count=page*limit)
                all_keys.extend(keys)
                if cursor == 0:
                    break
            paginated_keys = all_keys[(page - 1) * limit: page * limit]
            paginated_data = []
            indexs = 0
            for key in paginated_keys:
                item = {}
                try:
                    item['key'] = key.decode()
                except:
                    item['key'] = str(key)

                item['exptime'] = db_conn.ttl(key)
                if item['exptime'] == -1: item['exptime'] = 0
                item['type'] = db_conn.type(key)

                if item['type'] == 'string':
                    try:
                        item['value'] = db_conn.get(key).decode()
                    except:
                        item['value'] = str(db_conn.get(key))
                elif item['type'] == 'hash':
                    if db_conn.hlen(key) > 300:
                        item['value'] = "超过最大条数限制，共 {} 条".format(db_conn.hlen(key))
                    else:
                        item['value'] = str(db_conn.hgetall(key))
                elif item['type'] == 'list':
                    if db_conn.llen(key) > 300:
                        item['value'] = "超过最大条数限制，共 {} 条".format(db_conn.llen(key))
                    else:
                        item['value'] = str(db_conn.lrange(key, 0, -1))
                elif item['type'] == 'set':
                    if db_conn.scard(key) > 300:
                        item['value'] = "超过最大条数限制，共 {} 条".format(db_conn.scard(key))
                    else:
                        item['value'] = str(db_conn.smembers(key))
                elif item['type'] == 'zset':
                    if db_conn.zcard(key) > 300:
                        item['value'] = "超过最大条数限制，共 {} 条".format(db_conn.zcard(key))
                    else:
                        item['value'] = str(db_conn.zrange(key, 0, -1, withscores=True))
                else:
                    item['value'] = ''
                try:
                    item['len'] = db_conn.strlen(key)
                except:
                    item['len'] = len(item['value'])
                paginated_data.append(item)
                indexs += 1
            data = {
                "list":paginated_data,
                "page":page,
                "limit":limit,
                "total":total_nums
            }
            return DetailResponse(data=data)
        return ErrorResponse(msg="类型错误")