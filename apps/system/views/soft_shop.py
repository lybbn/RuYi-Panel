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
from utils.install.php import RY_GET_PHP_INFO,RY_GET_PHP_FPM_CONF,RY_SAVE_PHP_FPM_CONF,RY_GET_PHP_EXTENSIONS,get_php_path_info,RY_GET_PHP_CONFIG_PARAMS,RY_SAVE_PHP_CONFIG_PARAMS,RY_GET_PHP_DISABLED_FUNCTIONS,RY_SAVE_PHP_DISABLED_FUNCTIONS,RY_GET_PHP_DANGEROUS_FUNCTIONS,RY_GET_PHP_FPM_POOL_PARAMS,RY_SAVE_PHP_FPM_POOL_PARAMS,RY_GET_PHP_FPM_PRESETS,RY_VALIDATE_PHP_CONFIG,RY_CLEAR_PHP_OPCACHE,RY_GET_PHP_SLOWLOG,RY_CLEAR_PHP_ERROR_LOG,RY_CLEAR_PHP_SLOWLOG,RY_GET_PHP_EXTENSION_LIST,RY_TOGGLE_PHP_EXTENSION,RY_GET_PHPINFO,RY_GET_PECL_EXTENSIONS,RY_INSTALL_PECL_EXTENSION,RY_UNINSTALL_PECL_EXTENSION,RY_GET_PHP_FPM_STATUS
from utils.install.mysql import RY_GET_MYSQL_INFO,RY_SET_MYSQL_PORT,RY_SET_MYSQL_DATADIR
from utils.install.pgsql import RY_GET_PGSQL_INFO,RY_SET_PGSQL_PORT,RY_GET_PGSQL_EXTENSIONS,RY_INSTALL_PGSQL_EXTENSION,RY_UNINSTALL_PGSQL_EXTENSION
from utils.install.mongodb import RY_GET_MONGODB_INFO,RY_SET_MONGODB_PORT
from apps.systask.models import SysTaskCenter
import datetime
from utils.server.system import system
from django.db import transaction
from apps.sysshop.models import RySoftShop
from utils.install.redis import Redis_Connect,RY_GET_REDIS_CONF_OPTIONS,RY_GET_REDIS_PERSISTENCE,RY_SET_REDIS_PERSISTENCE
from concurrent.futures import ThreadPoolExecutor
from apps.syslogs.logutil import RuyiAddOpLog
from utils.customView import CustomAPIView
from apps.system.views.common import executeNextTask
from apps.system.models import Databases, RemoteRedis
from apps.systask.scheduler import scheduler

def _get_redis_conn_by_sid(sid, db=0):
    if sid and int(sid) > 0:
        remote = RemoteRedis.objects.filter(id=int(sid)).first()
        if not remote:
            return None, "远程Redis服务器不存在"
        db_conn = Redis_Connect(
            db_host=remote.db_host,
            db_port=int(remote.db_port),
            db_password=remote.db_password or "",
            db=db,
            local=False,
        )
        if not db_conn:
            return None, "远程Redis连接失败"
        return db_conn, None
    return None, "local"

def soft_install_callback(job_id="",version={},ok=True):
    try:
        task= SysTaskCenter.objects.get(job_id=job_id)
        if ok:
            task.status = 3
            name = version['name']
            password = version.get('password',"")
            info = {}
            soft_list = GetSoftList()
            for m in soft_list:
                if m['name'] == name:
                    info = m
                    break
            del soft_list
            info = json.dumps(info)
            if name in ["python","go","php","nodejs"]:
                if name == "go":
                    RySoftShop.objects.filter(name=name).update(is_default=False)
                if name == "nodejs":
                    RySoftShop.objects.filter(name=name).update(is_default=False)
                if RySoftShop.objects.filter(name=name,install_version=version['c_version']).exists():
                    RySoftShop.objects.filter(name=name,install_version=version['c_version']).update(install_path=version['install_path'],installed=True,status=1,info=info,is_default=True)
                else:
                    RySoftShop.objects.create(name=name,install_version=version['c_version'],install_path=version['install_path'],installed=True,status=1,password=password,info=info,type=int(version.get('type',0)))
            else:
                RySoftShop.objects.create(name=name,install_version=version['c_version'],install_path=version['install_path'],installed=True,status=2,password=password,info=info,type=int(version.get('type',0)))
        else:
            task.status = 2
            name = version.get('name', '')
            if name:
                detail_version = version.get('c_version') if name in ['python', 'go', 'php', 'nodejs'] else None
                if detail_version:
                    RySoftShop.objects.filter(name=name, install_version=detail_version).delete()
                else:
                    RySoftShop.objects.filter(name=name).delete()
        end_time = datetime.datetime.now()  # 记录任务结束时间
        if task.exec_at:
            task.duration = (end_time - task.exec_at).total_seconds()
        task.save()
        try:
            scheduler.remove_job(job_id)
        except:
            pass
        #执行下一个任务
        executeNextTask()
    except:
        pass
    finally:
        try:
            from django.db import connections
            connections.close_all()
        except:
            pass
        try:
            from utils.common import ReleaseMemory
            ReleaseMemory()
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
        elif type == "1":
            # 对于已安装列表，我们需要真实检测安装状态以进行准确过滤
            def check_installed(p):
                get_status = False  # 过滤阶段不需要获取运行状态，提升速度
                c_version = None
                if p['name'] in ["python", "go", "php", "nodejs"]:
                    if p.get('versions'):
                        c_version = p['versions'][0]['c_version']
                installed, _, _, _ = Check_Soft_Installed(name=p['name'], is_windows=is_windows, version=c_version, get_status=get_status)
                p['_is_installed_real'] = installed
                return p

            with ThreadPoolExecutor(max_workers=min(len(softlist), 20)) as executor:
                softlist = list(executor.map(check_installed, softlist))
            
            softlist = [item for item in softlist if item.get('_is_installed_real')]
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
                if p['name'] in ["python","go","nodejs"]:
                    c_version = p['versions'][0]['c_version']
                    get_status = False
                elif p['name'] == "php":
                    c_version = p['versions'][0]['c_version']
                    get_status = False
                p['installed'], p['version'], p['status'], p['install_path'] = Check_Soft_Installed(name=p['name'], is_windows=is_windows,version=c_version,get_status=get_status)
                if p['versions']:
                    for v in p['versions']:
                        v['url'] = None
                        hidev = v.get("hide",None)
                        v['hide'] = True if hidev else False
                if p['name'] in ["python","go","nodejs"]:
                    p['status']=True
                    if p['name'] == "go":
                        if not RySoftShop.objects.filter(name=p['name'],install_version=p['version'],is_default=True).exists():
                            p['is_default'] = False
                    if p['name'] == "nodejs":
                        if not RySoftShop.objects.filter(name=p['name'],install_version=p['version'],is_default=True).exists():
                            p['is_default'] = False
                elif p['name'] == "php":
                    p['status'] = RySoftShop.objects.filter(name=p['name'],installed=True,status=True).exists()
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
            if soft['name'] == 'nginx' and version.get('version') != 'openresty':
                return ErrorResponse(msg="Nginx仅支持安装OpenResty版本，请选择OpenResty版本安装")
            if SysTaskCenter.objects.filter(name__icontains="安装"+soft['name']+"-"+version['c_version'],status__in=[0,1]).exists():
                return ErrorResponse(msg="该应用正在安装中，无需重复安装!!!")
            detail_version =version['c_version'] if soft['name'] in ['python','go','php','nodejs'] else None
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
            if soft['name'] == "pgsql":
                if Databases.objects.filter(db_type=3).exists():
                    return ErrorResponse(msg="当前已有数据库，请先删除再卸载！！！")
            if soft['name'] == "mongodb":
                if Databases.objects.filter(db_type=2).exists():
                    return ErrorResponse(msg="当前已有MongoDB数据库，请先删除再卸载！！！")
            if soft['name'] in ["python","go","php","nodejs"]:#允许多个版本存在
                version_post = reqData.get("version",None)#如果提供了版本（c_version），就卸载指定，没提供取第一个
                version = version_post if version_post else soft["versions"][0]['c_version']
                try:
                    Ry_Uninstall_Soft(name=soft['name'],is_windows=is_windows,version=version)
                except Exception as e:
                    detail_version = version
                    s_installed, s_version, s_status, s_install_path = Check_Soft_Installed(name=soft['name'],is_windows=is_windows,version=detail_version)
                    if not s_installed:
                        RySoftShop.objects.filter(name=soft['name'],install_version=version).delete()
                        RuyiAddOpLog(request,msg="【软件商店】-【卸载】=>"+soft['name']+version,module="softmg")
                        return DetailResponse(msg="卸载成功")
                    return ErrorResponse(msg=str(e))
                RySoftShop.objects.filter(name=soft['name'],install_version=version).delete()
                RuyiAddOpLog(request,msg="【软件商店】-【卸载】=>"+soft['name']+version,module="softmg")
            else:
                try:
                    Ry_Uninstall_Soft(name=soft['name'],is_windows=is_windows)
                except Exception as e:
                    s_installed, s_version, s_status, s_install_path = Check_Soft_Installed(name=soft['name'],is_windows=is_windows)
                    if not s_installed:
                        RySoftShop.objects.filter(name=soft['name']).delete()
                        RuyiAddOpLog(request,msg="【软件商店】-【卸载】=>"+soft['name'],module="softmg")
                        return DetailResponse(msg="卸载成功")
                    return ErrorResponse(msg=str(e))
                RySoftShop.objects.filter(name=soft['name']).delete()
                RuyiAddOpLog(request,msg="【软件商店】-【卸载】=>"+soft['name'],module="softmg")
            return DetailResponse(msg="卸载成功")
        elif action == "status":
            status = reqData.get("status",None)
            t_msg = "启动成功"
            s_status = 2
            soft_version = reqData.get("version",None) if soft['name'] in ['python','go','php','nodejs'] else None
            if status == "start":
                Ry_Start_Soft(name=soft['name'],is_windows=is_windows,version=soft_version)
                s_status = 1
                t_msg = "启动成功"
            elif status == "stop":
                Ry_Stop_Soft(name=soft['name'],is_windows=is_windows,version=soft_version)
                s_status = 2
                t_msg = "停止成功"
            elif status == 'restart':
                Ry_Restart_Soft(name=soft['name'],is_windows=is_windows,version=soft_version)
                s_status = 1
                t_msg = "重启成功"
            elif status == 'reload':
                Ry_Reload_Soft(name=soft['name'],is_windows=is_windows,version=soft_version)
                s_status = 1
                t_msg = "重载成功"
            else:
                return ErrorResponse(msg="类型错误")
            if soft['name'] in ['python','go','php','nodejs'] and soft_version:
                RySoftShop.objects.filter(name=soft['name'],install_version=soft_version).update(status=s_status)
            else:
                RySoftShop.objects.filter(name=soft['name']).update(status=s_status)
            RuyiAddOpLog(request,msg="【软件商店】=>【"+soft['name']+"】"+t_msg[:2],module="softmg")
            return DetailResponse(msg=t_msg)
        elif action == "get_error_log":
            soft_ins = RySoftShop.objects.filter(name=soft['name'],installed=True).first()
            if not soft_ins:
                return ErrorResponse(msg="软件未安装")
            soft_version = reqData.get("version",None) if soft['name'] in ['python','go','php','nodejs'] else None
            error_log_path = Ry_Get_Soft_Info_Path(name=soft['name'],type="error",is_windows=is_windows,version=soft_version)
            num = 3000
            data = system.GetFileLastNumsLines(error_log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_access_log":
            soft_ins = RySoftShop.objects.filter(name=soft['name'],installed=True).first()
            if not soft_ins:
                return ErrorResponse(msg="软件未安装")
            access_log_path = Ry_Get_Soft_Info_Path(name=soft['name'],type="access",is_windows=is_windows)
            num = 3000
            data = system.GetFileLastNumsLines(access_log_path,num)
            return DetailResponse(data=data,msg="success")
        elif action == "get_slow_log":
            soft_ins = RySoftShop.objects.filter(name=soft['name'],installed=True).first()
            if not soft_ins:
                return ErrorResponse(msg="软件未安装")
            slow_log_path = Ry_Get_Soft_Info_Path(name=soft['name'],type="slow",is_windows=is_windows)
            num = 3000
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
            return DetailResponse(msg="保存成功")
        elif action == "get_persistence":
            if soft['name'] != 'redis':
                return ErrorResponse(msg="仅支持Redis")
            data = RY_GET_REDIS_PERSISTENCE(is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "set_persistence":
            if soft['name'] != 'redis':
                return ErrorResponse(msg="仅支持Redis")
            cont = ast_convert(reqData.get("cont",{}))
            data = RY_SET_REDIS_PERSISTENCE(cont=cont,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【持久化配置】=>redis",module="softmg")
            return DetailResponse(msg="保存成功")
        elif action == "get_conf":
            soft_version = reqData.get("version",None) if soft['name'] in ['python','go','php','nodejs'] else None
            data = Ry_Get_Soft_Conf(name=soft['name'],is_windows=is_windows,version=soft_version)
            return DetailResponse(data=data,msg="success")
        elif action == "save_conf":
            conf = reqData.get('conf',"")
            if not conf:
                return ErrorResponse(msg="配置文件格式错误")
            soft_version = reqData.get("version",None) if soft['name'] in ['python','go','php','nodejs'] else None
            data = Ry_Save_Soft_Conf(name=soft['name'],conf=conf,is_windows=is_windows,version=soft_version)
            RuyiAddOpLog(request,msg="【软件商店】-【修改配置】=>"+soft['name'],module="softmg")
            Ry_Reload_Soft(name=soft['name'],is_windows=is_windows,version=soft_version)
            return DetailResponse(data=data,msg="保存成功")
        elif action == "get_mysql_info":
            if soft['name'] != 'mysql':
                return ErrorResponse(msg="仅支持MySQL")
            try:
                data = RY_GET_MYSQL_INFO(is_windows=is_windows)
                return DetailResponse(data=data,msg="success")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "set_mysql_port":
            if soft['name'] != 'mysql':
                return ErrorResponse(msg="仅支持MySQL")
            port = reqData.get("port","")
            if not port:
                return ErrorResponse(msg="端口不能为空")
            try:
                RY_SET_MYSQL_PORT(port=port,is_windows=is_windows)
                RuyiAddOpLog(request,msg=f"【软件商店】-【修改MySQL端口】=>{port}",module="softmg")
                Ry_Restart_Soft(name='mysql',is_windows=is_windows)
                return DetailResponse(msg="端口修改成功，MySQL正在重启")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "set_mysql_datadir":
            if soft['name'] != 'mysql':
                return ErrorResponse(msg="仅支持MySQL")
            datadir = reqData.get("datadir","")
            if not datadir:
                return ErrorResponse(msg="数据目录不能为空")
            try:
                RY_SET_MYSQL_DATADIR(datadir=datadir,is_windows=is_windows)
                RuyiAddOpLog(request,msg=f"【软件商店】-【迁移MySQL数据目录】=>{datadir}",module="softmg")
                return DetailResponse(msg="数据目录迁移成功")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "get_pgsql_info":
            if soft['name'] != 'pgsql':
                return ErrorResponse(msg="仅支持PostgreSQL")
            try:
                data = RY_GET_PGSQL_INFO(is_windows=is_windows)
                return DetailResponse(data=data,msg="success")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "set_pgsql_port":
            if soft['name'] != 'pgsql':
                return ErrorResponse(msg="仅支持PostgreSQL")
            port = reqData.get("port","")
            if not port:
                return ErrorResponse(msg="端口不能为空")
            try:
                RY_SET_PGSQL_PORT(port=port,is_windows=is_windows)
                RuyiAddOpLog(request,msg=f"【软件商店】-【修改PostgreSQL端口】=>{port}",module="softmg")
                Ry_Restart_Soft(name='pgsql',is_windows=is_windows)
                return DetailResponse(msg="端口修改成功，PostgreSQL正在重启")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "get_pgsql_extensions":
            if soft['name'] != 'pgsql':
                return ErrorResponse(msg="仅支持PostgreSQL")
            try:
                from utils.common import pip_install_package
                pip_install_package('psycopg2-binary')
            except Exception:
                pass
            try:
                data = RY_GET_PGSQL_EXTENSIONS(is_windows=is_windows)
                return DetailResponse(data=data, msg="success")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "install_pgsql_extension":
            if soft['name'] != 'pgsql':
                return ErrorResponse(msg="仅支持PostgreSQL")
            ext_name = reqData.get("ext_name", "")
            if not ext_name:
                return ErrorResponse(msg="扩展名称不能为空")
            try:
                from utils.common import pip_install_package
                pip_install_package('psycopg2-binary')
            except Exception:
                pass
            try:
                RY_INSTALL_PGSQL_EXTENSION(ext_name=ext_name, is_windows=is_windows)
                RuyiAddOpLog(request, msg=f"【软件商店】-【安装PostgreSQL扩展】=>{ext_name}", module="softmg")
                return DetailResponse(msg=f"扩展 {ext_name} 安装成功")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "uninstall_pgsql_extension":
            if soft['name'] != 'pgsql':
                return ErrorResponse(msg="仅支持PostgreSQL")
            ext_name = reqData.get("ext_name", "")
            if not ext_name:
                return ErrorResponse(msg="扩展名称不能为空")
            try:
                from utils.common import pip_install_package
                pip_install_package('psycopg2-binary')
            except Exception:
                pass
            try:
                RY_UNINSTALL_PGSQL_EXTENSION(ext_name=ext_name, is_windows=is_windows)
                RuyiAddOpLog(request, msg=f"【软件商店】-【卸载PostgreSQL扩展】=>{ext_name}", module="softmg")
                return DetailResponse(msg=f"扩展 {ext_name} 卸载成功")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "get_mongodb_info":
            if soft['name'] != 'mongodb':
                return ErrorResponse(msg="仅支持MongoDB")
            try:
                data = RY_GET_MONGODB_INFO(is_windows=is_windows)
                return DetailResponse(data=data,msg="success")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "set_mongodb_port":
            if soft['name'] != 'mongodb':
                return ErrorResponse(msg="仅支持MongoDB")
            port = reqData.get("port","")
            if not port:
                return ErrorResponse(msg="端口不能为空")
            try:
                RY_SET_MONGODB_PORT(port=port,is_windows=is_windows)
                RuyiAddOpLog(request,msg=f"【软件商店】-【修改MongoDB端口】=>{port}",module="softmg")
                Ry_Restart_Soft(name='mongodb',is_windows=is_windows)
                return DetailResponse(msg="端口修改成功，MongoDB正在重启")
            except Exception as e:
                return ErrorResponse(msg=str(e))
        elif action == "get_php_info":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PHP_INFO(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "get_php_fpm_conf":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PHP_FPM_CONF(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "save_php_fpm_conf":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            conf = reqData.get('conf',"")
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            if not conf:
                return ErrorResponse(msg="配置文件格式错误")
            data = RY_SAVE_PHP_FPM_CONF(version=soft_version,conf=conf,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【修改PHP-FPM配置】=>"+soft_version,module="softmg")
            Ry_Reload_Soft(name='php',is_windows=is_windows,version=soft_version)
            return DetailResponse(data=data,msg="保存成功")
        elif action == "get_php_extensions":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PHP_EXTENSIONS(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "get_php_installed_versions":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            php_list = RySoftShop.objects.filter(name='php',installed=True).order_by('-is_default','install_version')
            data = []
            for item in php_list:
                version = item.install_version
                running = False
                try:
                    from utils.install.php import is_php_running
                    running = is_php_running(version,is_windows=is_windows)
                except:
                    pass
                data.append({
                    'version':version,
                    'install_path':item.install_path,
                    'is_default':item.is_default,
                    'status':item.status,
                    'running':running,
                })
            return DetailResponse(data=data,msg="success")
        elif action == "get_php_config_params":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PHP_CONFIG_PARAMS(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "save_php_config_params":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            params = ast_convert(reqData.get("params",{}))
            if not params:
                return ErrorResponse(msg="参数不能为空")
            validate = RY_VALIDATE_PHP_CONFIG(version=soft_version,is_windows=is_windows)
            data = RY_SAVE_PHP_CONFIG_PARAMS(version=soft_version,params=params,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【修改PHP配置参数】=>"+soft_version,module="softmg")
            Ry_Reload_Soft(name='php',is_windows=is_windows,version=soft_version)
            return DetailResponse(data=data,msg="保存成功")
        elif action == "get_php_disabled_functions":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            disabled = RY_GET_PHP_DISABLED_FUNCTIONS(version=soft_version,is_windows=is_windows)
            dangerous = RY_GET_PHP_DANGEROUS_FUNCTIONS()
            data = {
                'disabled': disabled,
                'dangerous': dangerous,
            }
            return DetailResponse(data=data,msg="success")
        elif action == "save_php_disabled_functions":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            functions = reqData.get("functions",[])
            if isinstance(functions, str):
                functions = [f.strip() for f in functions.split(',') if f.strip()]
            data = RY_SAVE_PHP_DISABLED_FUNCTIONS(version=soft_version,functions=functions,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【修改PHP禁用函数】=>"+soft_version,module="softmg")
            Ry_Reload_Soft(name='php',is_windows=is_windows,version=soft_version)
            return DetailResponse(data=data,msg="保存成功")
        elif action == "get_php_fpm_pool_params":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            params = RY_GET_PHP_FPM_POOL_PARAMS(version=soft_version,is_windows=is_windows)
            presets = RY_GET_PHP_FPM_PRESETS()
            data = {
                'params': params,
                'presets': presets,
            }
            return DetailResponse(data=data,msg="success")
        elif action == "save_php_fpm_pool_params":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            params = ast_convert(reqData.get("params",{}))
            if not params:
                return ErrorResponse(msg="参数不能为空")
            data = RY_SAVE_PHP_FPM_POOL_PARAMS(version=soft_version,params=params,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【修改PHP-FPM进程池参数】=>"+soft_version,module="softmg")
            Ry_Reload_Soft(name='php',is_windows=is_windows,version=soft_version)
            return DetailResponse(data=data,msg="保存成功")
        elif action == "validate_php_config":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_VALIDATE_PHP_CONFIG(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "clear_php_opcache":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_CLEAR_PHP_OPCACHE(version=soft_version,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【清空PHP OPcache】=>"+soft_version,module="softmg")
            return DetailResponse(data=data,msg="操作成功" if data else "OPcache不可用")
        elif action == "get_php_slowlog":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PHP_SLOWLOG(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "get_php_fpm_status":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PHP_FPM_STATUS(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "clear_php_error_log":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_CLEAR_PHP_ERROR_LOG(version=soft_version,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【清空PHP错误日志】=>"+soft_version,module="softmg")
            return DetailResponse(data=data,msg="清空成功")
        elif action == "clear_php_slowlog":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_CLEAR_PHP_SLOWLOG(version=soft_version,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【清空PHP慢日志】=>"+soft_version,module="softmg")
            return DetailResponse(data=data,msg="清空成功")
        elif action == "get_php_extension_list":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PHP_EXTENSION_LIST(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "toggle_php_extension":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            ext_name = reqData.get("ext_name","")
            enable = reqData.get("enable",True)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            if not ext_name:
                return ErrorResponse(msg="请指定扩展名")
            data = RY_TOGGLE_PHP_EXTENSION(version=soft_version,ext_name=ext_name,enable=enable,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【" + ("启用" if enable else "禁用") + "PHP扩展】=>"+soft_version+" "+ext_name,module="softmg")
            Ry_Reload_Soft(name='php',is_windows=is_windows,version=soft_version)
            return DetailResponse(data=data,msg="操作成功")
        elif action == "get_phpinfo":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PHPINFO(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "get_pecl_extensions":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            data = RY_GET_PECL_EXTENSIONS(version=soft_version,is_windows=is_windows)
            return DetailResponse(data=data,msg="success")
        elif action == "install_pecl_extension":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            ext_name = reqData.get("ext_name","")
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            if not ext_name:
                return ErrorResponse(msg="请指定扩展名")
            data = RY_INSTALL_PECL_EXTENSION(version=soft_version,ext_name=ext_name,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【安装PHP扩展】=>"+soft_version+" "+ext_name,module="softmg")
            if data.get('success'):
                Ry_Reload_Soft(name='php',is_windows=is_windows,version=soft_version)
                return DetailResponse(data=data,msg=data.get('msg','操作成功'))
            else:
                return ErrorResponse(msg=data.get('msg','操作失败'))
        elif action == "uninstall_pecl_extension":
            if soft['name'] != 'php':
                return ErrorResponse(msg="仅支持PHP")
            soft_version = reqData.get("version",None)
            ext_name = reqData.get("ext_name","")
            if not soft_version:
                return ErrorResponse(msg="请指定PHP版本")
            if not ext_name:
                return ErrorResponse(msg="请指定扩展名")
            data = RY_UNINSTALL_PECL_EXTENSION(version=soft_version,ext_name=ext_name,is_windows=is_windows)
            RuyiAddOpLog(request,msg="【软件商店】-【卸载PHP扩展】=>"+soft_version+" "+ext_name,module="softmg")
            if data.get('success'):
                Ry_Reload_Soft(name='php',is_windows=is_windows,version=soft_version)
                return DetailResponse(data=data,msg=data.get('msg','操作成功'))
            else:
                return ErrorResponse(msg=data.get('msg','操作失败'))
        return ErrorResponse(msg="类型错误")
    
class RYSoftInstallLogsView(CustomAPIView):
    """
    post:
    应用管理
    """
    permission_classes = [IsAuthenticated]

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
            sid = reqData.get("sid", 0)
            if sid and int(sid) > 0:
                remote = RemoteRedis.objects.filter(id=int(sid)).first()
                if not remote:
                    return DetailResponse(data=[])
                db_conn = Redis_Connect(
                    db_host=remote.db_host,
                    db_port=int(remote.db_port),
                    db_password=remote.db_password or "",
                    db=0,
                    local=False,
                )
                if not db_conn:
                    return DetailResponse(data=[])
                try:
                    redis_info = db_conn.info()
                    db_nums = 16
                    if 'db0' in redis_info:
                        for key in redis_info:
                            if key.startswith('db'):
                                db_idx = int(key[2:])
                                if db_idx + 1 > db_nums:
                                    db_nums = db_idx + 1
                    data = []
                    for i in range(0, db_nums):
                        tmp = {}
                        tmp['id'] = i
                        tmp['name'] = 'DB{}'.format(i)
                        try:
                            r_conn = Redis_Connect(
                                db_host=remote.db_host,
                                db_port=int(remote.db_port),
                                db_password=remote.db_password or "",
                                db=i,
                                local=False,
                            )
                            tmp['keynum'] = r_conn.dbsize() if r_conn else 0
                        except:
                            tmp['keynum'] = 0
                        data.append(tmp)
                except:
                    data = []
                return DetailResponse(data=data)
            conf_options = RY_GET_REDIS_CONF_OPTIONS()
            if not conf_options:return DetailResponse(data=[])
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
            sid = reqData.get("sid", 0)
            ids = ast_convert(reqData.get("ids",[]))
            msg_db=""
            if sid and int(sid) > 0:
                remote = RemoteRedis.objects.filter(id=int(sid)).first()
                if not remote:
                    return ErrorResponse(msg="远程Redis服务器不存在")
                db_conn_0 = Redis_Connect(
                    db_host=remote.db_host,
                    db_port=int(remote.db_port),
                    db_password=remote.db_password or "",
                    db=0,
                    local=False,
                )
                if not db_conn_0:
                    return ErrorResponse(msg="远程Redis连接失败")
                if not ids:
                    msg_db = "所有数据库"
                    try:
                        redis_info = db_conn_0.info()
                        db_nums = 16
                        if 'db0' in redis_info:
                            for key in redis_info:
                                if key.startswith('db'):
                                    db_idx = int(key[2:])
                                    if db_idx + 1 > db_nums:
                                        db_nums = db_idx + 1
                        ids = list(range(0, db_nums))
                    except:
                        ids = list(range(0, 16))
                else:
                    msg_db = ','.join(str(x) for x in ids)
                for x in ids:
                    db_conn = Redis_Connect(
                        db_host=remote.db_host,
                        db_port=int(remote.db_port),
                        db_password=remote.db_password or "",
                        db=int(x),
                        local=False,
                    )
                    if db_conn:
                        db_conn.flushdb()
                RuyiAddOpLog(request,msg="远程redis数据库->清空数据库："+msg_db,module="dbmg")
                return DetailResponse(msg="操作成功")
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
            sid = reqData.get("sid", 0)
            exptime = reqData.get("exptime", None)
            if not key or not value:
                return ErrorResponse(msg="缺少参数")
            db_conn, conn_err = _get_redis_conn_by_sid(sid, db)
            if conn_err == "local":
                db_conn = Redis_Connect(db=db)
            elif conn_err:
                return ErrorResponse(msg=conn_err)
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
            sid = reqData.get("sid", 0)
            if not key:
                return ErrorResponse(msg="缺少参数")
            db_conn, conn_err = _get_redis_conn_by_sid(sid, db)
            if conn_err == "local":
                db_conn = Redis_Connect(db=db)
            elif conn_err:
                return ErrorResponse(msg=conn_err)
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
            sid = reqData.get("sid", 0)
            db_conn, conn_err = _get_redis_conn_by_sid(sid, db_inx)
            if conn_err == "local":
                db_conn = Redis_Connect(db=db_inx)
            elif conn_err:
                return DetailResponse(data=[])
            if not db_conn:
                return DetailResponse(data=[])
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