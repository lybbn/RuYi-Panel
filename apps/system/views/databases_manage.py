import re,os
from rest_framework.views import APIView
from rest_framework import serializers
from utils.serializers import CustomModelSerializer
from utils.viewset import CustomModelViewSet
from apps.system.models import Databases
from utils.common import get_parameter_dic,current_os,ast_convert,check_is_ipv4,DeleteFile
from utils.jsonResponse import SuccessResponse,ErrorResponse,DetailResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from utils.install.mysql import RY_GET_MYSQL_ROOT_PASS,RY_SET_MYSQL_ROOT_PASS
from apps.sysshop.models import RySoftShop
from django.db import transaction
from utils.install.mysql import RY_IMPORT_MYSQL_SQL,RY_GET_MYSQL_CONF,Mysql_Connect,RY_CHECK_MYSQL_DATANAME_EXISTS,RY_CREATE_MYSQL_DATANAME,RY_CREATE_MYSQL_USER,RY_RESET_MYSQL_USER_PASS,RY_DELETE_MYSQL_DATABASE,RY_BACKUP_MYSQL_DATABASE
from utils.security.safe_filter import is_validate_db_passwd
from apps.syslogs.logutil import RuyiAddOpLog
from apps.sysbak.models import RuyiBackup
from django.http import FileResponse
from django.utils.encoding import escape_uri_path

# ================================================= #
# ************** 数据库管理 view  ************** #
# ================================================= #

class DatabasesSimpleSerializer(CustomModelSerializer):
    """
    数据库 简化序列化器
    """

    class Meta:
        model = Databases
        fields = ["id","db_name"]
        read_only_fields = ["id"]

class DatabasesSerializer(CustomModelSerializer):
    """
    数据库 简单序列化器
    """

    class Meta:
        model = Databases
        fields = "__all__"
        read_only_fields = ["id"]

class DatabasesCreateUpdateServerSerializer(CustomModelSerializer):
    """
    数据库 简单序列化器
    """

    class Meta:
        model = Databases
        fields = "__all__"
        read_only_fields = ["id"]

class DatabasesViewSet(CustomModelViewSet):
    """
    数据库接口
    """
    queryset = Databases.objects.all().order_by('-create_at')
    serializer_class = DatabasesSerializer
    create_serializer_class = DatabasesCreateUpdateServerSerializer
    update_serializer_class = DatabasesCreateUpdateServerSerializer
    search_fields = ('db_host','db_name','db_port','db_user')
    filterset_fields=("db_type",)
    
    def check_user_inputdata(self,request,create_mode=True):
        reqData = get_parameter_dic(request)
        db_name = reqData.get("db_name","")
        db_user = reqData.get("db_user","")
        db_type = int(reqData.get("db_type",0))
        db_pass = reqData.get("db_pass","")
        accept = reqData.get("accept","")
        accept_ips = reqData.get("accept_ips","")
        if not db_name: return False,"数据库名不能为空"
        if not db_user: return False,"数据用户名不能为空"
        if not db_pass: return False,"数据库密码不能为空"
        pass_ok,pass_msg = is_validate_db_passwd(db_pass)
        if not pass_ok: return pass_ok,pass_msg
        if len(db_user)>32: return False,"数据用户名不能超过32位"
        reg = r"^[\w\.-]+$"
        checks_list = ['root', 'mysql', 'test', 'sys','mysql.sys','mysql.session','mysql.infoschema']
        if not re.match(reg, db_user): return False,"数据库用户名不合法"
        if not re.match(reg, db_name): return False,"数据库名不合法"
        if db_user in checks_list: return False,"数据库用户名不合法"
        if db_name in checks_list: return False,"数据库名不合法"
        is_remote = ast_convert(reqData.get("is_remote",False))
        if not is_remote:
            if create_mode and Databases.objects.filter(db_name = db_name,db_type=db_type,is_remote=False).exists():
                return False,"存在同名数据库"
            elif not create_mode:
                id = reqData.get("id","")
                if Databases.objects.exclude(id=id).filter(db_name = db_name,db_type=db_type,is_remote=False).exists():
                    return False,"存在同名数据库"
        if accept in ['ip']:
            if not accept_ips: 
                return False,"需要填写访问权限中允许的IP地址"
            for a in accept_ips.split(','):
                if not check_is_ipv4(a):
                    return False,"访问权限中IP地址格式错误：%s"%a
        return True,"ok"

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        is_simple = get_parameter_dic(request).get("is_simple","")
        if page is not None:
            if is_simple:
                serializer = DatabasesSimpleSerializer(page, many=True, request=request)
                tmp_data = serializer.data
            else:
                serializer = self.get_serializer(page, many=True, request=request)
                tmp_data = serializer.data
                for d in tmp_data:
                    d['bak_nums'] = RuyiBackup.objects.filter(type=1,fid=d['id']).count()
            return self.get_paginated_response(tmp_data)
        else:  
            return SuccessResponse(data=[], msg="获取成功")
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        ok,msg = self.check_user_inputdata(request,create_mode=True)
        if not ok:
            return ErrorResponse(msg=msg)
        reqData = get_parameter_dic(request)
        db_name = reqData.get("db_name","")
        db_user = reqData.get("db_user","")
        db_type = int(reqData.get("db_type",0))
        db_pass = reqData.get("db_pass","")
        is_remote = ast_convert(reqData.get("is_remote",False))
        local = False if is_remote else True
        accept = reqData.get("accept","")
        accept_ips = reqData.get("accept_ips","")
        format = reqData.get("format","utf8mb4")
        db_collate_dic = {
            'utf8': 'utf8_general_ci',
            'utf8mb4': 'utf8mb4_unicode_ci',
            'gbk': 'gbk_chinese_ci',
            'big5': 'big5_chinese_ci'
        }
        db_collate = db_collate_dic[format]
        #创建数据库
        db_conn = Mysql_Connect()
        if not db_conn:
            RuyiAddOpLog(request,msg="【数据库管理】-【创建数据库】=>%s 失败：mysql连接失败"%db_name,module="dbmg",status=False)
            raise ValueError("mysql连接失败")
        if RY_CHECK_MYSQL_DATANAME_EXISTS(db_conn,db_name):
            RuyiAddOpLog(request,msg="【数据库管理】-【创建数据库】=>%s 失败：已存在同名数据库"%db_name,module="dbmg",status=False)
            return ErrorResponse(msg="数据库中已存在此【%s】数据库名称"%db_name)
        RY_CREATE_MYSQL_DATANAME(db_conn,{'db_name':db_name,'charset':format,'db_collate':db_collate})
        RY_CREATE_MYSQL_USER(db_conn,{'db_name':db_name,'db_user':db_user,'db_pass':db_pass,'accept':accept,'accept_ips':accept_ips})
        
        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        RuyiAddOpLog(request,msg="【数据库管理】-【创建数据库】=>%s 成功"%db_name,module="dbmg")
        return DetailResponse(data=serializer.data, msg="新增成功")
    
    def update(self, request, *args, **kwargs):
        return ErrorResponse(msg="接口禁用")
    
    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for sql_ins in instance_list:
            db_type = sql_ins.db_type
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            format = sql_ins.format
            if db_type == 0:
                if local:
                    db_conn = Mysql_Connect(local=local)
                else:
                    db_conn = Mysql_Connect(db_host=db_host,db_port=db_port,db_user=db_user,db_password=db_pass,charset=format,local=local)
                if not db_conn:
                    RuyiAddOpLog(request,msg="【数据库管理】-【删除数据库】=>%s 失败：mysql连接失败"%db_name,module="dbmg",status=False)
                    raise ValueError("mysql连接失败【%s】"%db_name)
            RY_DELETE_MYSQL_DATABASE(db_conn,db_info={'db_name':db_name,'db_user':db_user})
            #删除备份文件
            bk_qy = RuyiBackup.objects.filter(type = 1,fid=sql_ins.id)
            for b in bk_qy:
                DeleteFile(b.filename,empty_tips=False)
                b.delete()
            RuyiAddOpLog(request,msg="【数据库管理】-【删除数据库】=>%s 成功"%db_name,module="dbmg")
            sql_ins.delete()
        return DetailResponse(data=[], msg="删除成功")
    
    @transaction.atomic
    def databasePass(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        name = reqData.get("name","")
        is_windows = True if current_os == 'windows' else False
        if action == "get_db_pass":
            passwd = ""
            if name == 'mysql':
                passwd = RY_GET_MYSQL_ROOT_PASS()
            return DetailResponse(data=passwd)
        elif action == "set_db_pass":
            passwd = reqData.get("passwd","")
            if not passwd:
                return ErrorResponse(msg="密码不能为空")
            pass_ok,pass_msg = is_validate_db_passwd(passwd)
            if not pass_ok: return ErrorResponse(msg=pass_msg)
            if name == 'mysql':
                RY_SET_MYSQL_ROOT_PASS(passwd,first=False,is_windows=is_windows)
                RySoftShop.objects.filter(name = 'mysql').update(password=passwd)
                RuyiAddOpLog(request,msg="【数据库管理】-【设置root密码】=> %s 成功"%passwd,module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "set_db_user_pass":
            passwd = reqData.get("db_pass","")
            id = reqData.get("id","")
            if not passwd:return ErrorResponse(msg="密码不能为空")
            if not id:return ErrorResponse(msg="参数错误")
            pass_ok,pass_msg = is_validate_db_passwd(passwd)
            if not pass_ok: return ErrorResponse(msg=pass_msg)
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:return ErrorResponse(msg="参数错误")
            if sql_ins.is_remote and sql_ins.db_user in ['root']:return ErrorResponse(msg="不能修改远程数据库root密码")
            db_type = sql_ins.db_type
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            format = sql_ins.format
            if db_type == 0:
                if local:
                    db_conn = Mysql_Connect(local=local)
                else:
                    db_conn = Mysql_Connect(db_host=db_host,db_port=db_port,db_user=db_user,db_password=db_pass,charset=format,local=local)
                if not db_conn:
                    raise ValueError("mysql连接失败")
                RY_RESET_MYSQL_USER_PASS(db_conn,{'db_name':db_name,'db_user':db_user,'db_pass':db_pass})
            Databases.objects.filter(id=id).update(db_pass=passwd)
            RuyiAddOpLog(request,msg="【数据库管理】-【设置数据库密码】-【%s】=> %s 成功"%(db_name,passwd),module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "set_db_accept":
            accept = reqData.get("accept","")
            accept_ips = reqData.get("accept_ips","")
            id = reqData.get("id","")
            if not accept:return ErrorResponse(msg="访问权限不能为空")
            if accept in ['ip']:
                if not accept_ips: 
                    return ErrorResponse(msg="需要填写访问权限中允许的IP地址")
                for a in accept_ips.split(','):
                    if not check_is_ipv4(a):
                        return ErrorResponse(msg="访问权限中IP地址格式错误：%s"%a)
            else:
                accept_ips = ""
            if not id:return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:return ErrorResponse(msg="参数错误")
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_type = sql_ins.db_type
            local = False if sql_ins.is_remote else True
            if db_type == 0:
                if local:
                    db_conn = Mysql_Connect(local=local)
                else:
                    db_conn = Mysql_Connect(db_host=db_host,db_port=db_port,db_user=db_user,db_password=db_pass,charset=format,local=local)
                if not db_conn:
                    raise ValueError("mysql连接失败")
                RY_CREATE_MYSQL_USER(db_conn,{'db_name':db_name,'db_user':db_user,'db_pass':db_pass,'accept':accept,'accept_ips':accept_ips})
            Databases.objects.filter(id=id).update(accept=accept,accept_ips=accept_ips)
            RuyiAddOpLog(request,msg="【数据库管理】-【设置数据库访问权限】-【%s】=> %s %s"%(db_name,accept,accept_ips),module="dbmg")
            return DetailResponse(msg="操作成功")
        return ErrorResponse(msg="类型错误")
    
    def dbTools(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        action = reqData.get("action","")
        id = reqData.get("id","")
        is_windows = True if current_os == 'windows' else False
        if action == "backup_db":
            if not id:return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:return ErrorResponse(msg="参数错误")
            db_type = sql_ins.db_type
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            format = sql_ins.format
            dst_path = ""
            if db_type == 0:
                if local:
                    db_host = "127.0.0.1"
                    db_user = "root"
                    conf = RY_GET_MYSQL_CONF()
                    port_rep = r"port\s*=\s*([0-9]+)"
                    try:
                        db_port = int(re.search(port_rep,conf).groups()[0])
                    except:
                        pass
                    db_pass = RY_GET_MYSQL_ROOT_PASS()
                isok,dst_path, dst_size= RY_BACKUP_MYSQL_DATABASE(db_info={"id":id,"db_name":db_name,"db_user":db_user,"db_pass":db_pass,"db_host":db_host,"db_port":db_port,"format":format},is_windows=is_windows)
            else:
                return ErrorResponse(msg="类型错误")
            RuyiAddOpLog(request,msg="【数据库管理】-【备份数据库】-【%s】=> %s"%(db_name,dst_path),module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "download_backup_db":
            if not id:return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:return ErrorResponse(msg="参数错误")
            bid = reqData.get("bid","")
            #bk_ins = RuyiBackup.objects.filter(type=1,fid=id,id=bid).first()
            bk_ins = RuyiBackup.objects.filter(type=1,id=bid).first()
            if not bk_ins:
                return ErrorResponse(msg="没有发现备份文件")
            filename = bk_ins.filename
            if not os.path.exists(filename):
                return ErrorResponse(msg="文件不存在")
            if not os.path.isfile(filename):
                return ErrorResponse(msg="参数错误")
            file_size = os.path.getsize(filename)
            response = FileResponse(open(filename, 'rb'))
            response['content_type'] = "application/octet-stream"
            response['Content-Disposition'] = f'attachment;filename="{escape_uri_path(os.path.basename(filename))}"'
            response['Content-Length'] = file_size  # 设置文件大小
            RuyiAddOpLog(request,msg="【数据库管理】-【下载备份】-【%s】=> %s"%(sql_ins.db_name,bk_ins.filename),module="dbmg")
            return response
        elif action == "del_backup_db":
            if not id:return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:return ErrorResponse(msg="参数错误")
            bid = reqData.get("bid","")
            bk_ins = RuyiBackup.objects.filter(type=1,fid=id,id=bid).first()
            if bk_ins:
                DeleteFile(bk_ins.filename,empty_tips=False)
                bk_ins.delete()
            else:#无关联数据库id的场景删除
                bk_ins = RuyiBackup.objects.filter(type=1,id=bid).first()
                if bk_ins:
                    DeleteFile(bk_ins.filename,empty_tips=False)
                    bk_ins.delete()
            RuyiAddOpLog(request,msg="【数据库管理】-【删除备份】-【%s】=> %s"%(sql_ins.db_name,bk_ins.filename),module="dbmg")
            return DetailResponse(msg="删除成功")
        elif action == "recover_db_sql":
            if not id:return ErrorResponse(msg="参数错误[0]")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:return ErrorResponse(msg="参数错误[1]")
            bid = reqData.get("bid","")
            # bk_ins = RuyiBackup.objects.filter(type=1,fid=id,id=bid).first()
            bk_ins = RuyiBackup.objects.filter(type=1,id=bid).first()
            if not bk_ins:return ErrorResponse(msg="参数错误[2]")
            db_type = sql_ins.db_type
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            format = sql_ins.format
            if db_type == 0:
                if local:
                    db_host = "127.0.0.1"
                    db_user = "root"
                    conf = RY_GET_MYSQL_CONF()
                    port_rep = r"port\s*=\s*([0-9]+)"
                    try:
                        db_port = int(re.search(port_rep,conf).groups()[0])
                    except:
                        pass
                    db_pass = RY_GET_MYSQL_ROOT_PASS()
                RY_IMPORT_MYSQL_SQL(db_info={"id":id,"db_name":db_name,"db_user":db_user,"db_pass":db_pass,"db_host":db_host,"db_port":db_port,"format":format,"file_name":bk_ins.filename},is_windows=is_windows)
            else:
                return ErrorResponse(msg="类型错误")
            RuyiAddOpLog(request,msg="【数据库管理】-【备份恢复导入】-【%s】=> %s"%(sql_ins.db_name,bk_ins.filename),module="dbmg")
            return DetailResponse(msg="导入成功")
        return ErrorResponse(msg="类型错误")