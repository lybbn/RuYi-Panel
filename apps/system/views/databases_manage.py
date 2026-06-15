import re,os,shutil,time,hashlib
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.decorators import action
from utils.serializers import CustomModelSerializer
from utils.viewset import CustomModelViewSet
from apps.system.models import Databases, RemoteRedis, RemoteMysql, RemotePgsql, RemoteMongodb, SqliteDatabase
from utils.common import get_parameter_dic,current_os,ast_convert,check_is_ipv4,parse_accept_ips,DeleteFile,GetBackupPath,pip_install_package
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
from utils.install.redis import Redis_Connect
from utils.install.pgsql import Pgsql_Connect, RY_GET_PGSQL_ROOT_PASS, RY_SET_PGSQL_ROOT_PASS, RY_CHECK_PGSQL_DATANAME_EXISTS, RY_CREATE_PGSQL_DATANAME, RY_CREATE_PGSQL_USER, RY_DELETE_PGSQL_DATABASE, RY_RESET_PGSQL_USER_PASS, RY_BACKUP_PGSQL_DATABASE, RY_IMPORT_PGSQL_SQL, RY_GET_PGSQL_PORT
from utils.install.mongodb import Mongodb_Connect, RY_GET_MONGODB_ROOT_PASS, RY_SET_MONGODB_ROOT_PASS, RY_GET_MONGODB_PORT, RY_CHECK_MONGODB_DATANAME_EXISTS, RY_CREATE_MONGODB_DATANAME, RY_DELETE_MONGODB_DATABASE, RY_RESET_MONGODB_USER_PASS, RY_BACKUP_MONGODB_DATABASE, RY_IMPORT_MONGODB_SQL

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
            for a in parse_accept_ips(accept_ips):
                if not check_is_ipv4(a):
                    return False,"访问权限中IP地址格式错误：%s"%a
        return True,"ok"

    def list(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", 0)
        queryset = self.filter_queryset(self.get_queryset())
        if sid and int(sid) > 0:
            remote = RemoteMysql.objects.filter(id=int(sid)).first()
            if remote:
                queryset = queryset.filter(db_host=remote.db_host, db_port=remote.db_port, is_remote=True)
            else:
                queryset = queryset.none()
        else:
            queryset = queryset.filter(is_remote=False)
        page = self.paginate_queryset(queryset)
        is_simple = reqData.get("is_simple","")
        if page is not None:
            if is_simple:
                serializer = DatabasesSimpleSerializer(page, many=True, context={'request': request})
                tmp_data = serializer.data
            else:
                serializer = self.get_serializer(page, many=True, request=request)
                tmp_data = serializer.data
                for d in tmp_data:
                    d['bak_nums'] = RuyiBackup.objects.filter(type=1,fid=d['id']).count()
            return self.get_paginated_response(tmp_data)
        else:
            return SuccessResponse(data=[], msg="获取成功")
    
    def _get_mysql_conn_by_sid(self, sid, db_name="", charset="utf8mb4"):
        if sid and int(sid) > 0:
            remote = RemoteMysql.objects.filter(id=int(sid)).first()
            if not remote:
                return None, "远程MySQL服务器不存在"
            db_conn = Mysql_Connect(
                db_host=remote.db_host,
                db_port=int(remote.db_port),
                db_user=remote.db_user,
                db_password=remote.db_password or "",
                db_name=db_name,
                charset=charset,
                local=False,
            )
            if not db_conn:
                return None, "远程MySQL连接失败"
            return db_conn, None
        return None, "local"

    def _get_mysql_conn_by_db(self, db_ins, db_name=""):
        """通过 Databases 实例反查 RemoteMysql 获取连接（用于远程数据库操作）"""
        if not db_ins.is_remote:
            db_conn = Mysql_Connect()
            if not db_conn:
                return None, "本地MySQL连接失败"
            return db_conn, None
        remote = RemoteMysql.objects.filter(db_host=db_ins.db_host, db_port=int(db_ins.db_port)).first()
        if not remote:
            return None, "未找到对应的远程MySQL服务器配置"
        db_conn = Mysql_Connect(
            db_host=remote.db_host,
            db_port=int(remote.db_port),
            db_user=remote.db_user,
            db_password=remote.db_password or "",
            db_name=db_name,
            local=False,
        )
        if not db_conn:
            return None, "远程MySQL连接失败"
        return db_conn, None

    @action(methods=['POST'], detail=False)
    def sync_remote_databases(self, request, *args, **kwargs):
        """从远程MySQL服务器同步数据库列表到面板"""
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", 0)
        if not sid or int(sid) <= 0:
            return ErrorResponse(msg="请选择远程MySQL服务器")
        remote = RemoteMysql.objects.filter(id=int(sid)).first()
        if not remote:
            return ErrorResponse(msg="远程MySQL服务器不存在")
        db_conn, conn_err = self._get_mysql_conn_by_sid(sid)
        if conn_err:
            return ErrorResponse(msg=conn_err)
        try:
            result = db_conn.filter("SHOW DATABASES")
            if not result or isinstance(result, Exception):
                return ErrorResponse(msg="查询远程数据库列表失败")
            db_conn.close()
        except Exception as e:
            return ErrorResponse(msg="查询远程数据库列表失败：%s" % str(e))
        nameArr = ['information_schema', 'performance_schema', 'mysql', 'sys']
        n = 0
        for row in result:
            db_name = row[0]
            if db_name in nameArr:
                continue
            if not re.match(r"^[\w\.-]+$", db_name):
                continue
            if Databases.objects.filter(db_name=db_name, db_type=0, db_host=remote.db_host, db_port=remote.db_port, is_remote=True).exists():
                continue
            Databases.objects.create(
                db_name=db_name,
                db_user="",
                db_pass="",
                db_host=remote.db_host,
                db_port=remote.db_port,
                db_type=0,
                format="utf8mb4",
                accept="all",
                is_remote=True,
                remark=db_name,
            )
            n += 1
        if n > 0:
            RuyiAddOpLog(request, msg="【数据库管理】-【同步远程数据库】从 %s:%s 同步了 %s 个数据库" % (remote.db_host, remote.db_port, n), module="dbmg")
            return DetailResponse(data={"sync_count": n}, msg="同步成功，新增 %s 个数据库" % n)
        return DetailResponse(data={"sync_count": 0}, msg="数据库已是最新，无需同步")

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
        sid = reqData.get("sid", 0)
        db_collate_dic = {
            'utf8': 'utf8_general_ci',
            'utf8mb4': 'utf8mb4_unicode_ci',
            'gbk': 'gbk_chinese_ci',
            'big5': 'big5_chinese_ci'
        }
        db_collate = db_collate_dic[format]
        db_conn, conn_err = self._get_mysql_conn_by_sid(sid, charset=format)
        if conn_err == "local":
            db_conn = Mysql_Connect()
        elif conn_err:
            return ErrorResponse(msg=conn_err)
        if not db_conn:
            RuyiAddOpLog(request,msg="【数据库管理】-【创建数据库】=>%s 失败：mysql连接失败"%db_name,module="dbmg",status=False)
            raise ValueError("mysql连接失败")
        if RY_CHECK_MYSQL_DATANAME_EXISTS(db_conn,db_name):
            RuyiAddOpLog(request,msg="【数据库管理】-【创建数据库】=>%s 失败：已存在同名数据库"%db_name,module="dbmg",status=False)
            return ErrorResponse(msg="数据库中已存在此【%s】数据库名称"%db_name)
        RY_CREATE_MYSQL_DATANAME(db_conn,{'db_name':db_name,'charset':format,'db_collate':db_collate})
        RY_CREATE_MYSQL_USER(db_conn,{'db_name':db_name,'db_user':db_user,'db_pass':db_pass,'accept':accept,'accept_ips':accept_ips})
        if sid and int(sid) > 0:
            remote = RemoteMysql.objects.filter(id=int(sid)).first()
            if remote:
                reqData['db_host'] = remote.db_host
                reqData['db_port'] = remote.db_port
                reqData['is_remote'] = True
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
                db_conn, conn_err = self._get_mysql_conn_by_db(sql_ins)
                if conn_err:
                    RuyiAddOpLog(request,msg="【数据库管理】-【删除数据库】=>%s 失败：%s"%(db_name, conn_err),module="dbmg",status=False)
                    raise ValueError(conn_err + "【%s】"%db_name)
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
                db_conn, conn_err = self._get_mysql_conn_by_db(sql_ins)
                if conn_err:
                    raise ValueError(conn_err)
                RY_RESET_MYSQL_USER_PASS(db_conn,{'db_name':db_name,'db_user':db_user,'db_pass':passwd})
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
                for a in parse_accept_ips(accept_ips):
                    if not check_is_ipv4(a):
                        return ErrorResponse(msg="访问权限中IP地址格式错误：%s"%a)
                accept_ips = ",".join(parse_accept_ips(accept_ips))
            else:
                accept_ips = ""
            if not id:return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:return ErrorResponse(msg="参数错误")
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            db_type = sql_ins.db_type
            format = sql_ins.format
            local = False if sql_ins.is_remote else True
            if db_type == 0:
                db_conn, conn_err = self._get_mysql_conn_by_db(sql_ins)
                if conn_err:
                    raise ValueError(conn_err)
                RY_CREATE_MYSQL_USER(db_conn,{'db_name':db_name,'db_user':db_user,'db_pass':db_pass,'accept':accept,'accept_ips':accept_ips})
            Databases.objects.filter(id=id).update(accept=accept,accept_ips=accept_ips)
            RuyiAddOpLog(request,msg="【数据库管理】-【设置数据库访问权限】-【%s】=> %s %s"%(db_name,accept,accept_ips),module="dbmg")
            return DetailResponse(msg="操作成功")
        return ErrorResponse(msg="类型错误")


# ================================================= #
# ************** MongoDB数据库管理 view  ************** #
# ================================================= #

class RemoteMongodbSerializer(CustomModelSerializer):

    class Meta:
        model = RemoteMongodb
        fields = "__all__"
        read_only_fields = ["id"]


class RemoteMongodbCreateUpdateSerializer(CustomModelSerializer):

    class Meta:
        model = RemoteMongodb
        fields = "__all__"
        read_only_fields = ["id"]


class RemoteMongodbViewSet(CustomModelViewSet):
    queryset = RemoteMongodb.objects.all().order_by('-create_at')
    serializer_class = RemoteMongodbSerializer
    create_serializer_class = RemoteMongodbCreateUpdateSerializer
    update_serializer_class = RemoteMongodbCreateUpdateSerializer
    search_fields = ('db_host', 'remark')

    def create(self, request, *args, **kwargs):
        pip_install_package('pymongo')
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            Databases.objects.filter(db_host=ins.db_host, db_port=ins.db_port, db_type=2, is_remote=True).delete()
            ins.delete()
        return DetailResponse(data=[], msg="删除成功")

    @action(methods=['POST'], detail=False)
    def check_connection(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        db_host = reqData.get("db_host", "")
        db_port = int(reqData.get("db_port", 27017))
        db_user = reqData.get("db_user", "root")
        db_password = reqData.get("db_password", "")
        if not db_host:
            return ErrorResponse(msg="服务器地址不能为空")
        try:
            db_conn = Mongodb_Connect(
                db_host=db_host,
                db_port=db_port,
                db_user=db_user if db_user else None,
                db_password=db_password if db_password else None,
                local=False,
            )
            if not db_conn:
                return ErrorResponse(msg="连接失败，请检查地址、端口、用户名和密码是否正确")
            db_conn.close()
            return DetailResponse(msg="连接成功")
        except Exception as e:
            return ErrorResponse(msg="连接失败：%s" % str(e))


class MongodbDatabaseViewSet(CustomModelViewSet):
    queryset = Databases.objects.filter(db_type=2).order_by('-create_at')
    serializer_class = DatabasesSerializer
    create_serializer_class = DatabasesCreateUpdateServerSerializer
    update_serializer_class = DatabasesCreateUpdateServerSerializer
    search_fields = ('db_host', 'db_name', 'db_port', 'db_user')
    filterset_fields = ("db_type",)

    def check_user_inputdata(self, request, create_mode=True):
        reqData = get_parameter_dic(request)
        db_name = reqData.get("db_name", "")
        db_user = reqData.get("db_user", "")
        db_pass = reqData.get("db_pass", "")
        if not db_name:
            return False, "数据库名不能为空"
        if not db_user:
            return False, "数据用户名不能为空"
        if not db_pass:
            return False, "数据库密码不能为空"
        pass_ok, pass_msg = is_validate_db_passwd(db_pass)
        if not pass_ok:
            return pass_ok, pass_msg
        if len(db_user) > 32:
            return False, "数据用户名不能超过32位"
        reg = r"^[\w\.-]+$"
        checks_list = ['root', 'admin', 'local', 'config', 'mongosh']
        if not re.match(reg, db_user):
            return False, "数据库用户名不合法"
        if not re.match(reg, db_name):
            return False, "数据库名不合法"
        if db_user in checks_list:
            return False, "数据库用户名不合法"
        if db_name in checks_list:
            return False, "数据库名不合法"
        is_remote = ast_convert(reqData.get("is_remote", False))
        if not is_remote:
            if create_mode and Databases.objects.filter(db_name=db_name, db_type=2, is_remote=False).exists():
                return False, "存在同名数据库"
            elif not create_mode:
                id = reqData.get("id", "")
                if Databases.objects.exclude(id=id).filter(db_name=db_name, db_type=2, is_remote=False).exists():
                    return False, "存在同名数据库"
        return True, "ok"

    def list(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", 0)
        queryset = self.filter_queryset(self.get_queryset())
        if sid and int(sid) > 0:
            remote = RemoteMongodb.objects.filter(id=int(sid)).first()
            if remote:
                queryset = queryset.filter(db_host=remote.db_host, db_port=remote.db_port, is_remote=True)
            else:
                queryset = queryset.none()
        else:
            queryset = queryset.filter(is_remote=False)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, request=request)
            tmp_data = serializer.data
            for d in tmp_data:
                d['bak_nums'] = RuyiBackup.objects.filter(type=1, fid=d['id']).count()
            return self.get_paginated_response(tmp_data)
        else:
            return SuccessResponse(data=[], msg="获取成功")

    def _get_mongodb_conn_by_sid(self, sid, db_name="admin"):
        if sid and int(sid) > 0:
            remote = RemoteMongodb.objects.filter(id=int(sid)).first()
            if not remote:
                return None, "远程MongoDB服务器不存在"
            db_conn = Mongodb_Connect(
                db_host=remote.db_host,
                db_port=int(remote.db_port),
                db_user=remote.db_user if remote.db_user else None,
                db_password=remote.db_password if remote.db_password else None,
                db_name=db_name,
                local=False,
            )
            if not db_conn:
                return None, "远程MongoDB连接失败"
            return db_conn, None
        return None, "local"

    def _get_mongodb_conn_by_db(self, db_ins):
        """通过 Databases 实例反查 RemoteMongodb 获取连接"""
        if not db_ins.is_remote:
            db_conn = Mongodb_Connect(local=True)
            if not db_conn:
                return None, "本地MongoDB连接失败"
            return db_conn, None
        remote = RemoteMongodb.objects.filter(db_host=db_ins.db_host, db_port=int(db_ins.db_port)).first()
        if not remote:
            return None, "未找到对应的远程MongoDB服务器配置"
        db_conn = Mongodb_Connect(
            db_host=remote.db_host,
            db_port=int(remote.db_port),
            db_user=remote.db_user if remote.db_user else None,
            db_password=remote.db_password if remote.db_password else None,
            local=False,
        )
        if not db_conn:
            return None, "远程MongoDB连接失败"
        return db_conn, None

    @action(methods=['POST'], detail=False)
    def sync_remote_databases(self, request, *args, **kwargs):
        """从远程MongoDB服务器同步数据库列表到面板"""
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", 0)
        if not sid or int(sid) <= 0:
            return ErrorResponse(msg="请选择远程MongoDB服务器")
        remote = RemoteMongodb.objects.filter(id=int(sid)).first()
        if not remote:
            return ErrorResponse(msg="远程MongoDB服务器不存在")
        db_conn, conn_err = self._get_mongodb_conn_by_sid(sid)
        if conn_err:
            return ErrorResponse(msg=conn_err)
        try:
            result = db_conn.list_database_names()
            db_conn.close()
        except Exception as e:
            return ErrorResponse(msg="查询远程数据库列表失败：%s" % str(e))
        nameArr = ['admin', 'config', 'local']
        n = 0
        for db_name in result:
            if db_name in nameArr:
                continue
            if not re.match(r"^[\w\.-]+$", db_name):
                continue
            if Databases.objects.filter(db_name=db_name, db_type=2, db_host=remote.db_host, db_port=remote.db_port, is_remote=True).exists():
                continue
            Databases.objects.create(
                db_name=db_name,
                db_user="",
                db_pass="",
                db_host=remote.db_host,
                db_port=remote.db_port,
                db_type=2,
                format="utf8",
                accept="all",
                is_remote=True,
                remark=db_name,
            )
            n += 1
        if n > 0:
            RuyiAddOpLog(request, msg="【数据库管理】-【同步远程数据库】从 %s:%s 同步了 %s 个MongoDB数据库" % (remote.db_host, remote.db_port, n), module="dbmg")
            return DetailResponse(data={"sync_count": n}, msg="同步成功，新增 %s 个数据库" % n)
        return DetailResponse(data={"sync_count": 0}, msg="数据库已是最新，无需同步")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        ok, msg = self.check_user_inputdata(request, create_mode=True)
        if not ok:
            return ErrorResponse(msg=msg)
        reqData = get_parameter_dic(request)
        db_name = reqData.get("db_name", "")
        db_user = reqData.get("db_user", "")
        db_pass = reqData.get("db_pass", "")
        is_remote = ast_convert(reqData.get("is_remote", False))
        sid = reqData.get("sid", 0)
        db_conn, conn_err = self._get_mongodb_conn_by_sid(sid)
        if conn_err == "local":
            db_conn = Mongodb_Connect(local=True)
        elif conn_err:
            return ErrorResponse(msg=conn_err)
        if not db_conn:
            RuyiAddOpLog(request, msg="【数据库管理】-【创建MongoDB数据库】=>%s 失败：mongodb连接失败" % db_name, module="dbmg", status=False)
            raise ValueError("mongodb连接失败")
        if RY_CHECK_MONGODB_DATANAME_EXISTS(db_conn, db_name):
            RuyiAddOpLog(request, msg="【数据库管理】-【创建MongoDB数据库】=>%s 失败：已存在同名数据库" % db_name, module="dbmg", status=False)
            return ErrorResponse(msg="数据库中已存在此【%s】数据库名称" % db_name)
        RY_CREATE_MONGODB_DATANAME(db_conn, db_name, db_user, db_pass)
        reqData['db_type'] = 2
        reqData['format'] = 'UTF8'
        if sid and int(sid) > 0:
            remote = RemoteMongodb.objects.filter(id=int(sid)).first()
            if remote:
                reqData['db_host'] = remote.db_host
                reqData['db_port'] = remote.db_port
                reqData['is_remote'] = True
        else:
            reqData['db_host'] = '127.0.0.1'
            reqData['db_port'] = RY_GET_MONGODB_PORT()
            reqData['is_remote'] = False
        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        RuyiAddOpLog(request, msg="【数据库管理】-【创建MongoDB数据库】=>%s 成功" % db_name, module="dbmg")
        return DetailResponse(data=serializer.data, msg="新增成功")

    def update(self, request, *args, **kwargs):
        return ErrorResponse(msg="接口禁用")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for sql_ins in instance_list:
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_conn, conn_err = self._get_mongodb_conn_by_db(sql_ins)
            if conn_err:
                RuyiAddOpLog(request, msg="【数据库管理】-【删除MongoDB数据库】=>%s 失败：%s" % (db_name, conn_err), module="dbmg", status=False)
                raise ValueError(conn_err + "【%s】" % db_name)
            RY_DELETE_MONGODB_DATABASE(db_conn, db_name, db_user)
            bk_qy = RuyiBackup.objects.filter(type=1, fid=sql_ins.id)
            for b in bk_qy:
                DeleteFile(b.filename, empty_tips=False)
                b.delete()
            RuyiAddOpLog(request, msg="【数据库管理】-【删除MongoDB数据库】=>%s 成功" % db_name, module="dbmg")
            sql_ins.delete()
        return DetailResponse(data=[], msg="删除成功")

    @transaction.atomic
    def databasePass(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        name = reqData.get("name", "")
        is_windows = True if current_os == 'windows' else False
        if action == "get_db_pass":
            passwd = ""
            if name == 'mongodb':
                passwd = RY_GET_MONGODB_ROOT_PASS()
            return DetailResponse(data=passwd)
        elif action == "set_db_pass":
            passwd = reqData.get("passwd", "")
            if not passwd:
                return ErrorResponse(msg="密码不能为空")
            pass_ok, pass_msg = is_validate_db_passwd(passwd)
            if not pass_ok:
                return ErrorResponse(msg=pass_msg)
            if name == 'mongodb':
                RY_SET_MONGODB_ROOT_PASS(passwd, is_windows=is_windows)
                RySoftShop.objects.filter(name='mongodb').update(password=passwd)
                RuyiAddOpLog(request, msg="【数据库管理】-【设置MongoDB root密码】=> %s 成功" % passwd, module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "set_db_user_pass":
            passwd = reqData.get("db_pass", "")
            id = reqData.get("id", "")
            if not passwd:
                return ErrorResponse(msg="密码不能为空")
            if not id:
                return ErrorResponse(msg="参数错误")
            pass_ok, pass_msg = is_validate_db_passwd(passwd)
            if not pass_ok:
                return ErrorResponse(msg=pass_msg)
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            if sql_ins.is_remote and sql_ins.db_user in ['root']:
                return ErrorResponse(msg="不能修改远程数据库root密码")
            local = False if sql_ins.is_remote else True
            if local:
                db_conn = Mongodb_Connect(local=True)
            else:
                db_conn, conn_err = self._get_mongodb_conn_by_db(sql_ins)
                if conn_err:
                    raise ValueError(conn_err)
            if not db_conn:
                raise ValueError("mongodb连接失败")
            RY_RESET_MONGODB_USER_PASS(db_conn, sql_ins.db_name, sql_ins.db_user, passwd)
            Databases.objects.filter(id=id).update(db_pass=passwd)
            RuyiAddOpLog(request, msg="【数据库管理】-【设置MongoDB数据库密码】-【%s】=> %s 成功" % (sql_ins.db_name, passwd), module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "set_db_accept":
            accept = reqData.get("accept", "")
            accept_ips = reqData.get("accept_ips", "")
            id = reqData.get("id", "")
            if not accept:
                return ErrorResponse(msg="访问权限不能为空")
            if accept in ['ip']:
                if not accept_ips:
                    return ErrorResponse(msg="需要填写访问权限中允许的IP地址")
                for a in parse_accept_ips(accept_ips):
                    if not check_is_ipv4(a):
                        return ErrorResponse(msg="访问权限中IP地址格式错误：%s" % a)
                accept_ips = ",".join(parse_accept_ips(accept_ips))
            else:
                accept_ips = ""
            if not id:
                return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            Databases.objects.filter(id=id).update(accept=accept, accept_ips=accept_ips)
            RuyiAddOpLog(request, msg="【数据库管理】-【设置MongoDB数据库访问权限】-【%s】=> %s %s" % (sql_ins.db_name, accept, accept_ips), module="dbmg")
            return DetailResponse(msg="操作成功")
        return ErrorResponse(msg="类型错误")

    def dbTools(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        id = reqData.get("id", "")
        is_windows = True if current_os == 'windows' else False
        if action == "backup_db":
            if not id:
                return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            if local:
                db_host = "127.0.0.1"
                db_user = "root"
                db_pass = RY_GET_MONGODB_ROOT_PASS()
                db_port = RY_GET_MONGODB_PORT()
            else:
                remote = RemoteMongodb.objects.filter(db_host=sql_ins.db_host, db_port=int(sql_ins.db_port)).first()
                if remote:
                    db_user = remote.db_user or ""
                    db_pass = remote.db_password or ""
            isok, dst_path, dst_size = RY_BACKUP_MONGODB_DATABASE(
                db_info={"id": id, "db_name": db_name, "db_user": db_user, "db_pass": db_pass, "db_host": db_host, "db_port": db_port},
                is_windows=is_windows,
            )
            if isok and dst_path:
                RuyiBackup.objects.create(type=1, name=os.path.basename(dst_path), filename=dst_path, size=dst_size, fid=str(sql_ins.id))
                RuyiAddOpLog(request, msg="【数据库管理】-【备份MongoDB数据库】-【%s】=> %s" % (db_name, dst_path), module="dbmg")
                return DetailResponse(msg="备份成功")
            else:
                return ErrorResponse(msg="备份失败")
        elif action == "download_backup_db":
            if not id:
                return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            bid = reqData.get("bid", "")
            bk_ins = RuyiBackup.objects.filter(type=1, id=bid).first()
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
            response['Content-Length'] = file_size
            RuyiAddOpLog(request, msg="【数据库管理】-【下载MongoDB备份】-【%s】=> %s" % (sql_ins.db_name, bk_ins.filename), module="dbmg")
            return response
        elif action == "del_backup_db":
            if not id:
                return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            bid = reqData.get("bid", "")
            bk_ins = RuyiBackup.objects.filter(type=1, fid=id, id=bid).first()
            if bk_ins:
                DeleteFile(bk_ins.filename, empty_tips=False)
                bk_ins.delete()
            else:
                bk_ins = RuyiBackup.objects.filter(type=1, id=bid).first()
                if bk_ins:
                    DeleteFile(bk_ins.filename, empty_tips=False)
                    bk_ins.delete()
            RuyiAddOpLog(request, msg="【数据库管理】-【删除MongoDB备份】-【%s】=> %s" % (sql_ins.db_name, bk_ins.filename if bk_ins else ''), module="dbmg")
            return DetailResponse(msg="删除成功")
        elif action == "recover_db_sql":
            if not id:
                return ErrorResponse(msg="参数错误[0]")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误[1]")
            bid = reqData.get("bid", "")
            bk_ins = RuyiBackup.objects.filter(type=1, id=bid).first()
            if not bk_ins:
                return ErrorResponse(msg="参数错误[2]")
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            if local:
                db_host = "127.0.0.1"
                db_user = "root"
                db_pass = RY_GET_MONGODB_ROOT_PASS()
                db_port = RY_GET_MONGODB_PORT()
            else:
                remote = RemoteMongodb.objects.filter(db_host=sql_ins.db_host, db_port=int(sql_ins.db_port)).first()
                if remote:
                    db_user = remote.db_user or ""
                    db_pass = remote.db_password or ""
            try:
                RY_IMPORT_MONGODB_SQL(
                    db_info={"db_name": db_name, "db_user": db_user, "db_pass": db_pass, "db_host": db_host, "db_port": db_port},
                    backup_file=bk_ins.filename,
                    is_windows=is_windows,
                )
                RuyiAddOpLog(request, msg="【数据库管理】-【恢复MongoDB数据库】-【%s】=> %s" % (db_name, bk_ins.filename), module="dbmg")
                return DetailResponse(msg="恢复成功")
            except Exception as e:
                return ErrorResponse(msg="恢复失败：%s" % str(e))
        return ErrorResponse(msg="类型错误")


class RemoteRedisSerializer(CustomModelSerializer):

    class Meta:
        model = RemoteRedis
        fields = "__all__"
        read_only_fields = ["id"]


class RemoteRedisCreateUpdateSerializer(CustomModelSerializer):

    class Meta:
        model = RemoteRedis
        fields = "__all__"
        read_only_fields = ["id"]


class RemoteRedisViewSet(CustomModelViewSet):
    queryset = RemoteRedis.objects.all().order_by('-create_at')
    serializer_class = RemoteRedisSerializer
    create_serializer_class = RemoteRedisCreateUpdateSerializer
    update_serializer_class = RemoteRedisCreateUpdateSerializer
    search_fields = ('db_host', 'remark')

    @action(methods=['POST'], detail=False)
    def check_connection(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        db_host = reqData.get("db_host", "")
        db_port = int(reqData.get("db_port", 6379))
        db_password = reqData.get("db_password", "")
        if not db_host:
            return ErrorResponse(msg="服务器地址不能为空")
        try:
            db_conn = Redis_Connect(
                db_host=db_host,
                db_port=db_port,
                db_password=db_password,
                db=0,
                local=False,
            )
            if not db_conn:
                return ErrorResponse(msg="连接失败，请检查地址、端口和密码是否正确")
            db_conn.ping()
            return DetailResponse(msg="连接成功")
        except Exception as e:
            return ErrorResponse(msg="连接失败：%s" % str(e))


# ================================================= #
# ************** SQLite数据库管理 view  ************** #
# ================================================= #

def _sqlite_format_value(val):
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    return "'%s'" % str(val).replace("'", "''")


def _sqlite_connect(db_path):
    import sqlite3
    if not os.path.exists(db_path):
        return None, "数据库文件不存在"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return conn, None
    except Exception as e:
        return None, str(e)


def _get_sqlite_backup_dir(db_path):
    backup_base = os.path.join(GetBackupPath(), "database", "sqlite")
    path_hash = hashlib.md5(db_path.encode()).hexdigest()
    backup_dir = os.path.join(backup_base, path_hash)
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    return backup_dir


class SqliteDatabaseSerializer(CustomModelSerializer):

    class Meta:
        model = SqliteDatabase
        fields = "__all__"
        read_only_fields = ["id"]


class SqliteDatabaseCreateUpdateSerializer(CustomModelSerializer):

    class Meta:
        model = SqliteDatabase
        fields = "__all__"
        read_only_fields = ["id"]


class SqliteDatabaseViewSet(CustomModelViewSet):
    queryset = SqliteDatabase.objects.all().order_by('-create_at')
    serializer_class = SqliteDatabaseSerializer
    create_serializer_class = SqliteDatabaseCreateUpdateSerializer
    update_serializer_class = SqliteDatabaseCreateUpdateSerializer
    search_fields = ('name', 'path', 'remark')

    def list(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        queryset = self.filter_queryset(self.get_queryset())
        search = reqData.get("search", "")
        if search:
            queryset = queryset.filter(name__icontains=search) | queryset.filter(path__icontains=search) | queryset.filter(remark__icontains=search)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, request=request)
            tmp_data = serializer.data
            for d in tmp_data:
                db_path = d.get('path', '')
                if os.path.exists(db_path):
                    d['size'] = os.path.getsize(db_path)
                    d['st_time'] = int(os.path.getmtime(db_path))
                    d['file_exists'] = True
                else:
                    d['size'] = 0
                    d['st_time'] = 0
                    d['file_exists'] = False
                d['backup_count'] = RuyiBackup.objects.filter(type=1, fid=str(d['id'])).count()
            return self.get_paginated_response(tmp_data)
        return SuccessResponse(data=[], msg="获取成功")

    def create(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        name = reqData.get("name", "")
        path = reqData.get("path", "")
        remark = reqData.get("remark", "")
        if not path:
            return ErrorResponse(msg="数据库文件路径不能为空")
        path = path.strip()
        if SqliteDatabase.objects.filter(path=path).exists():
            return ErrorResponse(msg="该数据库文件已添加")
        if not os.path.exists(path):
            import sqlite3
            try:
                parent_dir = os.path.dirname(path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                conn = sqlite3.connect(path)
                conn.close()
            except Exception as e:
                return ErrorResponse(msg="创建数据库文件失败：%s" % str(e))
        else:
            conn, err = _sqlite_connect(path)
            if err:
                return ErrorResponse(msg="数据库文件错误，不是有效的SQLite数据库文件")
            conn.close()
        if not name:
            name = os.path.basename(path)
        serializer = self.get_serializer(data={'name': name, 'path': path, 'remark': remark}, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        RuyiAddOpLog(request, msg="【SQLite管理】-【添加数据库】=> %s" % name, module="dbmg")
        return DetailResponse(data=serializer.data, msg="添加成功")

    def update(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        pk = kwargs.get('pk')
        ins = SqliteDatabase.objects.filter(id=pk).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        name = reqData.get("name", ins.name)
        remark = reqData.get("remark", ins.remark)
        SqliteDatabase.objects.filter(id=pk).update(name=name, remark=remark)
        RuyiAddOpLog(request, msg="【SQLite管理】-【编辑数据库】=> %s" % name, module="dbmg")
        return DetailResponse(msg="修改成功")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            bk_list = RuyiBackup.objects.filter(type=1, fid=str(ins.id))
            for bk in bk_list:
                DeleteFile(bk.filename, empty_tips=False)
                bk.delete()
            RuyiAddOpLog(request, msg="【SQLite管理】-【删除数据库】=> %s" % ins.name, module="dbmg")
            ins.delete()
        return DetailResponse(data=[], msg="删除成功")

    @action(methods=['GET'], detail=False)
    def get_table_list(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        if not os.path.exists(ins.path):
            return ErrorResponse(msg="数据库文件不存在")
        conn, err = _sqlite_connect(ins.path)
        if err:
            return ErrorResponse(msg="数据库连接失败：%s" % err)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = cursor.fetchall()
            result = []
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute("SELECT COUNT(*) FROM \"%s\"" % table_name)
                    count = cursor.fetchone()[0]
                except:
                    count = 0
                result.append({'name': table_name, 'count': count})
            return DetailResponse(data=result, msg="获取成功")
        except Exception as e:
            return ErrorResponse(msg="获取表列表失败：%s" % str(e))
        finally:
            conn.close()

    @action(methods=['GET'], detail=False)
    def get_table_keys(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        table = reqData.get("table", "")
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        conn, err = _sqlite_connect(ins.path)
        if err:
            return ErrorResponse(msg="数据库连接失败")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(\"%s\")" % table)
            columns = cursor.fetchall()
            result = []
            for col in columns:
                result.append({
                    'name': col[1],
                    'type': col[2].lower(),
                    'notnull': col[3],
                    'default': col[4],
                    'pk': col[5],
                })
            return DetailResponse(data=result, msg="获取成功")
        except Exception as e:
            return ErrorResponse(msg="获取表字段失败：%s" % str(e))
        finally:
            conn.close()

    @action(methods=['GET'], detail=False)
    def get_table_data(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        table = reqData.get("table", "")
        page = int(reqData.get("page", 1))
        limit = int(reqData.get("limit", 20))
        search = reqData.get("search", "")
        order = reqData.get("order", "")
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        conn, err = _sqlite_connect(ins.path)
        if err:
            return ErrorResponse(msg="数据库连接失败")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(\"%s\")" % table)
            columns_info = cursor.fetchall()
            col_names = [col[1] for col in columns_info]
            where = "1=1"
            if search:
                safe_search = search.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
                w_list = []
                for col in columns_info:
                    w_list.append("\"%s\" LIKE '%%%s%%' ESCAPE '\\'" % (col[1], safe_search))
                where = " OR ".join(w_list)
            cursor.execute("SELECT COUNT(*) FROM \"%s\" WHERE %s" % (table, where))
            total = cursor.fetchone()[0]
            order_clause = ""
            if order:
                order_clause = " ORDER BY %s" % order
            offset = (page - 1) * limit
            cursor.execute("SELECT * FROM \"%s\" WHERE %s%s LIMIT %d OFFSET %d" % (table, where, order_clause, limit, offset))
            rows = cursor.fetchall()
            data = []
            for row in rows:
                item = {}
                for i, col_name in enumerate(col_names):
                    val = row[i] if i < len(row) else None
                    if isinstance(val, (bytes, bytearray)):
                        val = str(val)
                    item[col_name] = val
                data.append(item)
            return DetailResponse(data={
                'data': data,
                'columns': col_names,
                'total': total,
                'page': page,
                'limit': limit,
            }, msg="获取成功")
        except Exception as e:
            return ErrorResponse(msg="获取表数据失败：%s" % str(e))
        finally:
            conn.close()

    @action(methods=['POST'], detail=False)
    def update_table_data(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        table = reqData.get("table", "")
        where_data = reqData.get("where_data", {})
        new_data = reqData.get("new_data", {})
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        conn, err = _sqlite_connect(ins.path)
        if err:
            return ErrorResponse(msg="数据库连接失败")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(\"%s\")" % table)
            columns_info = cursor.fetchall()
            pk_cols = [col[1] for col in columns_info if col[5] == 1]
            if pk_cols:
                where_parts = []
                for pk in pk_cols:
                    if pk in where_data:
                        where_parts.append("\"%s\" = %s" % (pk, _sqlite_format_value(where_data[pk])))
                where_clause = " AND ".join(where_parts) if where_parts else "1=1"
            else:
                where_parts = []
                for key, val in where_data.items():
                    where_parts.append("\"%s\" = %s" % (key, _sqlite_format_value(val)))
                where_clause = " AND ".join(where_parts) if where_parts else "1=1"
            set_parts = []
            for key, val in new_data.items():
                set_parts.append("\"%s\" = %s" % (key, _sqlite_format_value(val)))
            if not set_parts:
                return ErrorResponse(msg="没有需要更新的数据")
            sql = "UPDATE \"%s\" SET %s WHERE %s" % (table, ", ".join(set_parts), where_clause)
            cursor.execute(sql)
            conn.commit()
            RuyiAddOpLog(request, msg="【SQLite管理】-【更新数据】=> %s.%s" % (ins.name, table), module="dbmg")
            return DetailResponse(msg="更新成功")
        except Exception as e:
            return ErrorResponse(msg="更新失败：%s" % str(e))
        finally:
            conn.close()

    @action(methods=['POST'], detail=False)
    def delete_table_data(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        table = reqData.get("table", "")
        where_data = reqData.get("where_data", {})
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        conn, err = _sqlite_connect(ins.path)
        if err:
            return ErrorResponse(msg="数据库连接失败")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(\"%s\")" % table)
            columns_info = cursor.fetchall()
            pk_cols = [col[1] for col in columns_info if col[5] == 1]
            if pk_cols:
                where_parts = []
                for pk in pk_cols:
                    if pk in where_data:
                        where_parts.append("\"%s\" = %s" % (pk, _sqlite_format_value(where_data[pk])))
                where_clause = " AND ".join(where_parts) if where_parts else "1=1"
            else:
                where_parts = []
                for key, val in where_data.items():
                    where_parts.append("\"%s\" = %s" % (key, _sqlite_format_value(val)))
                where_clause = " AND ".join(where_parts) if where_parts else "1=1"
            sql = "DELETE FROM \"%s\" WHERE %s" % (table, where_clause)
            cursor.execute(sql)
            conn.commit()
            RuyiAddOpLog(request, msg="【SQLite管理】-【删除数据】=> %s.%s" % (ins.name, table), module="dbmg")
            return DetailResponse(msg="删除成功")
        except Exception as e:
            return ErrorResponse(msg="删除失败：%s" % str(e))
        finally:
            conn.close()

    @action(methods=['POST'], detail=False)
    def insert_table_data(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        table = reqData.get("table", "")
        new_data = reqData.get("new_data", {})
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        conn, err = _sqlite_connect(ins.path)
        if err:
            return ErrorResponse(msg="数据库连接失败")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(\"%s\")" % table)
            columns_info = cursor.fetchall()
            auto_inc_cols = [col[1] for col in columns_info if col[5] == 1]
            for col_name in auto_inc_cols:
                if col_name in new_data and not new_data[col_name]:
                    del new_data[col_name]
            keys = list(new_data.keys())
            placeholders = [_sqlite_format_value(new_data[k]) for k in keys]
            sql = "INSERT INTO \"%s\" (\"%s\") VALUES (%s)" % (
                table,
                "\", \"".join(keys),
                ", ".join(placeholders)
            )
            cursor.execute(sql)
            conn.commit()
            RuyiAddOpLog(request, msg="【SQLite管理】-【插入数据】=> %s.%s" % (ins.name, table), module="dbmg")
            return DetailResponse(msg="添加成功")
        except Exception as e:
            return ErrorResponse(msg="添加失败：%s" % str(e))
        finally:
            conn.close()

    @action(methods=['POST'], detail=False)
    def execute_sql(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        sql_shell = reqData.get("sql_shell", "")
        if not sql_shell:
            return ErrorResponse(msg="SQL语句不能为空")
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        conn, err = _sqlite_connect(ins.path)
        if err:
            return ErrorResponse(msg="数据库连接失败")
        try:
            cursor = conn.cursor()
            cursor.execute(sql_shell)
            if sql_shell.strip().upper().startswith("SELECT") or sql_shell.strip().upper().startswith("PRAGMA"):
                rows = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description] if cursor.description else []
                data = []
                for row in rows:
                    item = {}
                    for i, col_name in enumerate(col_names):
                        val = row[i] if i < len(row) else None
                        if isinstance(val, (bytes, bytearray)):
                            val = str(val)
                        item[col_name] = val
                    data.append(item)
                RuyiAddOpLog(request, msg="【SQLite管理】-【执行SQL查询】=> %s" % ins.name, module="dbmg")
                return DetailResponse(data={'data': data, 'columns': col_names}, msg="执行成功")
            else:
                conn.commit()
                affected = cursor.rowcount
                RuyiAddOpLog(request, msg="【SQLite管理】-【执行SQL】=> %s" % ins.name, module="dbmg")
                return DetailResponse(data={'affected': affected}, msg="执行成功，受影响行数：%d" % affected)
        except Exception as e:
            return ErrorResponse(msg="执行失败：%s" % str(e))
        finally:
            conn.close()

    @action(methods=['POST'], detail=False)
    def backup_db(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        if not os.path.exists(ins.path):
            return ErrorResponse(msg="数据库文件不存在")
        try:
            backup_dir = _get_sqlite_backup_dir(ins.path)
            file_name = "%s_%s" % (time.strftime('%Y%m%d_%H%M%S', time.localtime()), os.path.basename(ins.path))
            backup_file = os.path.join(backup_dir, file_name)
            shutil.copy2(ins.path, backup_file)
            if os.path.exists(backup_file):
                file_size = os.path.getsize(backup_file)
                RuyiBackup.objects.create(type=1, name=file_name, filename=backup_file, size=file_size, fid=str(ins.id))
                RuyiAddOpLog(request, msg="【SQLite管理】-【备份数据库】=> %s" % ins.name, module="dbmg")
                return DetailResponse(msg="备份成功")
            return ErrorResponse(msg="备份失败")
        except Exception as e:
            return ErrorResponse(msg="备份失败：%s" % str(e))

    @action(methods=['GET'], detail=False)
    def get_backup_list(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        id = reqData.get("id", "")
        ins = SqliteDatabase.objects.filter(id=id).first()
        if not ins:
            return ErrorResponse(msg="数据库不存在")
        bk_list = RuyiBackup.objects.filter(type=1, fid=str(ins.id)).order_by('-create_at')
        result = []
        for bk in bk_list:
            result.append({
                'id': bk.id,
                'name': bk.name,
                'filepath': bk.filename,
                'size': bk.size,
                'mtime': int(bk.create_at.timestamp()) if bk.create_at else 0,
                'create_at': bk.create_at.strftime('%Y-%m-%d %H:%M:%S') if bk.create_at else '',
            })
        return DetailResponse(data=result, msg="获取成功")

    @action(methods=['POST'], detail=False)
    def del_backup(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        bid = reqData.get("bid", "")
        backup_name = reqData.get("backup_name", "")
        if backup_name and not bid:
            bk_ins = RuyiBackup.objects.filter(type=1, name=backup_name).first()
        else:
            bk_ins = RuyiBackup.objects.filter(type=1, id=bid).first()
        if bk_ins:
            DeleteFile(bk_ins.filename, empty_tips=False)
            bk_ins.delete()
            return DetailResponse(msg="删除成功")
        return ErrorResponse(msg="备份文件不存在")

    @action(methods=['POST'], detail=False)
    def download_backup(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        bid = reqData.get("bid", "")
        backup_name = reqData.get("backup_name", "")
        if backup_name and not bid:
            bk_ins = RuyiBackup.objects.filter(type=1, name=backup_name).first()
        else:
            bk_ins = RuyiBackup.objects.filter(type=1, id=bid).first()
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
        response['Content-Length'] = file_size
        return response

    @action(methods=['POST'], detail=False)
    def get_remote_dblist(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", "")
        remote_ins = RemoteRedis.objects.filter(id=sid).first()
        if not remote_ins:
            return ErrorResponse(msg="远程服务器不存在")
        try:
            db_conn = Redis_Connect(
                db_host=remote_ins.db_host,
                db_port=remote_ins.db_port,
                db_password=remote_ins.db_password or "",
                db=0,
                local=False,
            )
            if not db_conn:
                return ErrorResponse(msg="连接失败")
            redis_info = db_conn.info()
            db_nums = int(redis_info.get('db_nums', 16)) if redis_info else 16
            keyspace_info = db_conn.info('keyspace')
            data = []
            for i in range(db_nums):
                db_key = f"db{i}"
                keynum = 0
                if db_key in keyspace_info:
                    keynum = keyspace_info[db_key].get('keys', 0)
                data.append({
                    'id': i,
                    'name': f'db{i}',
                    'keynum': keynum,
                })
            return DetailResponse(data=data, msg="获取成功")
        except Exception as e:
            return ErrorResponse(msg="获取数据库列表失败：%s" % str(e))

    @action(methods=['POST'], detail=False)
    def get_remote_keylist(self, request, *args, **kwargs):
        from math import ceil
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", "")
        db_inx = int(reqData.get("db", 0))
        search = reqData.get("search", "")
        page = int(reqData.get("page", 1))
        limit = int(reqData.get("limit", 10))
        limit = min(limit, 999)
        remote_ins = RemoteRedis.objects.filter(id=sid).first()
        if not remote_ins:
            return ErrorResponse(msg="远程服务器不存在")
        try:
            db_conn = Redis_Connect(
                db_host=remote_ins.db_host,
                db_port=remote_ins.db_port,
                db_password=remote_ins.db_password or "",
                db=db_inx,
                local=False,
            )
            if not db_conn:
                return ErrorResponse(msg="连接失败")
            if search:
                search_pattern = "*" + search + "*"
            else:
                search_pattern = "*"
            total_nums = 0
            try:
                total_nums = db_conn.dbsize()
            except Exception as e:
                return ErrorResponse(msg=str(e))
            total_pages = ceil(total_nums / limit) if limit > 0 else 1
            page = max(1, min(page, total_pages))
            cursor = 0
            all_keys = []
            while True:
                cursor, keys = db_conn.scan(cursor=cursor, match=search_pattern, count=page * limit)
                all_keys.extend(keys)
                if cursor == 0:
                    break
            paginated_keys = all_keys[(page - 1) * limit: page * limit]
            paginated_data = []
            for key in paginated_keys:
                item = {}
                try:
                    item['key'] = key.decode()
                except Exception:
                    item['key'] = str(key)
                item['exptime'] = db_conn.ttl(key)
                if item['exptime'] == -1:
                    item['exptime'] = 0
                item['type'] = db_conn.type(key)
                if item['type'] == 'string':
                    try:
                        item['value'] = db_conn.get(key).decode()
                    except Exception:
                        item['value'] = str(db_conn.get(key))
                elif item['type'] == 'hash':
                    hlen = db_conn.hlen(key)
                    if hlen > 300:
                        item['value'] = "超过最大条数限制，共 %d 条" % hlen
                    else:
                        item['value'] = str(db_conn.hgetall(key))
                elif item['type'] == 'list':
                    llen = db_conn.llen(key)
                    if llen > 300:
                        item['value'] = "超过最大条数限制，共 %d 条" % llen
                    else:
                        item['value'] = str(db_conn.lrange(key, 0, -1))
                elif item['type'] == 'set':
                    scard = db_conn.scard(key)
                    if scard > 300:
                        item['value'] = "超过最大条数限制，共 %d 条" % scard
                    else:
                        item['value'] = str(db_conn.smembers(key))
                elif item['type'] == 'zset':
                    zcard = db_conn.zcard(key)
                    if zcard > 300:
                        item['value'] = "超过最大条数限制，共 %d 条" % zcard
                    else:
                        item['value'] = str(db_conn.zrange(key, 0, -1, withscores=True))
                else:
                    item['value'] = ''
                try:
                    item['len'] = db_conn.strlen(key)
                except Exception:
                    item['len'] = len(item['value'])
                paginated_data.append(item)
            data = {
                'list': paginated_data,
                'total': total_nums,
                'page': page,
                'limit': limit,
            }
            return DetailResponse(data=data, msg="获取成功")
        except Exception as e:
            return ErrorResponse(msg="获取远程Key列表失败：%s" % str(e))

    @action(methods=['POST'], detail=False)
    def remote_set_val(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", "")
        key = ast_convert(reqData.get("key", ""))
        value = ast_convert(reqData.get("value", ""))
        db = int(reqData.get("db", 0))
        exptime = reqData.get("exptime", None)
        if not key or not value:
            return ErrorResponse(msg="缺少参数")
        remote_ins = RemoteRedis.objects.filter(id=sid).first()
        if not remote_ins:
            return ErrorResponse(msg="远程服务器不存在")
        try:
            db_conn = Redis_Connect(
                db_host=remote_ins.db_host,
                db_port=remote_ins.db_port,
                db_password=remote_ins.db_password or "",
                db=db,
                local=False,
            )
            if not db_conn:
                return ErrorResponse(msg="连接失败")
            if exptime is not None and exptime:
                db_conn.set(key, value, int(exptime))
            else:
                exptime = "永久"
                db_conn.set(key, value)
            RuyiAddOpLog(request, msg="远程Redis->设置/修改键值：(host=%s,key=%s,value=%s,db=%s,exptime=%s)" % (remote_ins.db_host, key, value, db, exptime), module="dbmg")
            return DetailResponse(msg="操作成功")
        except Exception as e:
            return ErrorResponse(msg="操作失败：%s" % str(e))

    @action(methods=['POST'], detail=False)
    def remote_del_val(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", "")
        key = ast_convert(reqData.get("key", ""))
        db = int(reqData.get("db", 0))
        if not key:
            return ErrorResponse(msg="缺少参数")
        remote_ins = RemoteRedis.objects.filter(id=sid).first()
        if not remote_ins:
            return ErrorResponse(msg="远程服务器不存在")
        try:
            db_conn = Redis_Connect(
                db_host=remote_ins.db_host,
                db_port=remote_ins.db_port,
                db_password=remote_ins.db_password or "",
                db=db,
                local=False,
            )
            if not db_conn:
                return ErrorResponse(msg="连接失败")
            db_conn.delete(key)
            RuyiAddOpLog(request, msg="远程Redis->删除键值：(host=%s,key=%s,db=%s)" % (remote_ins.db_host, key, db), module="dbmg")
            return DetailResponse(msg="操作成功")
        except Exception as e:
            return ErrorResponse(msg="操作失败：%s" % str(e))

    @action(methods=['POST'], detail=False)
    def remote_flashdb(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", "")
        ids = ast_convert(reqData.get("ids", []))
        remote_ins = RemoteRedis.objects.filter(id=sid).first()
        if not remote_ins:
            return ErrorResponse(msg="远程服务器不存在")
        try:
            if not ids:
                ids = []
            msg_db = ','.join(str(x) for x in ids) if ids else "所有数据库"
            for x in ids:
                db_conn = Redis_Connect(
                    db_host=remote_ins.db_host,
                    db_port=remote_ins.db_port,
                    db_password=remote_ins.db_password or "",
                    db=x,
                    local=False,
                )
                if db_conn:
                    db_conn.flushdb()
            RuyiAddOpLog(request, msg="远程Redis->清空数据库：(host=%s,db=%s)" % (remote_ins.db_host, msg_db), module="dbmg")
            return DetailResponse(msg="操作成功")
        except Exception as e:
            return ErrorResponse(msg="操作失败：%s" % str(e))


class RemoteMysqlSerializer(CustomModelSerializer):

    class Meta:
        model = RemoteMysql
        fields = "__all__"
        read_only_fields = ["id"]


class RemoteMysqlCreateUpdateSerializer(CustomModelSerializer):

    class Meta:
        model = RemoteMysql
        fields = "__all__"
        read_only_fields = ["id"]


class RemoteMysqlViewSet(CustomModelViewSet):
    queryset = RemoteMysql.objects.all().order_by('-create_at')
    serializer_class = RemoteMysqlSerializer
    create_serializer_class = RemoteMysqlCreateUpdateSerializer
    update_serializer_class = RemoteMysqlCreateUpdateSerializer
    search_fields = ('db_host', 'remark')

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            Databases.objects.filter(db_host=ins.db_host, db_port=ins.db_port, is_remote=True).delete()
            ins.delete()
        return DetailResponse(data=[], msg="删除成功")

    @action(methods=['POST'], detail=False)
    def check_connection(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        db_host = reqData.get("db_host", "")
        db_port = int(reqData.get("db_port", 3306))
        db_user = reqData.get("db_user", "root")
        db_password = reqData.get("db_password", "")
        if not db_host:
            return ErrorResponse(msg="服务器地址不能为空")
        try:
            db_conn = Mysql_Connect(
                db_host=db_host,
                db_port=db_port,
                db_user=db_user,
                db_password=db_password,
                local=False,
            )
            if not db_conn:
                return ErrorResponse(msg="连接失败，请检查地址、端口、用户名和密码是否正确")
            db_conn.close()
            return DetailResponse(msg="连接成功")
        except Exception as e:
            return ErrorResponse(msg="连接失败：%s" % str(e))


# ================================================= #
# ************** PostgreSQL数据库管理 view  ************** #
# ================================================= #

class RemotePgsqlSerializer(CustomModelSerializer):

    class Meta:
        model = RemotePgsql
        fields = "__all__"
        read_only_fields = ["id"]


class RemotePgsqlCreateUpdateSerializer(CustomModelSerializer):

    class Meta:
        model = RemotePgsql
        fields = "__all__"
        read_only_fields = ["id"]


class RemotePgsqlViewSet(CustomModelViewSet):
    queryset = RemotePgsql.objects.all().order_by('-create_at')
    serializer_class = RemotePgsqlSerializer
    create_serializer_class = RemotePgsqlCreateUpdateSerializer
    update_serializer_class = RemotePgsqlCreateUpdateSerializer
    search_fields = ('db_host', 'remark')

    def create(self, request, *args, **kwargs):
        pip_install_package('psycopg2-binary')
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            Databases.objects.filter(db_host=ins.db_host, db_port=ins.db_port, db_type=3, is_remote=True).delete()
            ins.delete()
        return DetailResponse(data=[], msg="删除成功")

    @action(methods=['POST'], detail=False)
    def check_connection(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        db_host = reqData.get("db_host", "")
        db_port = int(reqData.get("db_port", 5432))
        db_user = reqData.get("db_user", "postgres")
        db_password = reqData.get("db_password", "")
        if not db_host:
            return ErrorResponse(msg="服务器地址不能为空")
        try:
            db_conn = Pgsql_Connect(
                db_host=db_host,
                db_port=db_port,
                db_user=db_user,
                db_password=db_password,
                local=False,
            )
            if not db_conn:
                return ErrorResponse(msg="连接失败，请检查地址、端口、用户名和密码是否正确")
            db_conn.close()
            return DetailResponse(msg="连接成功")
        except Exception as e:
            return ErrorResponse(msg="连接失败：%s" % str(e))


class PgsqlDatabaseViewSet(CustomModelViewSet):
    queryset = Databases.objects.filter(db_type=3).order_by('-create_at')
    serializer_class = DatabasesSerializer
    create_serializer_class = DatabasesCreateUpdateServerSerializer
    update_serializer_class = DatabasesCreateUpdateServerSerializer
    search_fields = ('db_host', 'db_name', 'db_port', 'db_user')
    filterset_fields = ("db_type",)

    def check_user_inputdata(self, request, create_mode=True):
        reqData = get_parameter_dic(request)
        db_name = reqData.get("db_name", "")
        db_user = reqData.get("db_user", "")
        db_pass = reqData.get("db_pass", "")
        accept = reqData.get("accept", "")
        accept_ips = reqData.get("accept_ips", "")
        if not db_name:
            return False, "数据库名不能为空"
        if not db_user:
            return False, "数据用户名不能为空"
        if not db_pass:
            return False, "数据库密码不能为空"
        pass_ok, pass_msg = is_validate_db_passwd(db_pass)
        if not pass_ok:
            return pass_ok, pass_msg
        if len(db_user) > 32:
            return False, "数据用户名不能超过32位"
        reg = r"^[\w\.-]+$"
        checks_list = ['root', 'postgres', 'template0', 'template1', 'pg_catalog']
        if not re.match(reg, db_user):
            return False, "数据库用户名不合法"
        if not re.match(reg, db_name):
            return False, "数据库名不合法"
        if db_user in checks_list:
            return False, "数据库用户名不合法"
        if db_name in checks_list:
            return False, "数据库名不合法"
        is_remote = ast_convert(reqData.get("is_remote", False))
        if not is_remote:
            if create_mode and Databases.objects.filter(db_name=db_name, db_type=3, is_remote=False).exists():
                return False, "存在同名数据库"
            elif not create_mode:
                id = reqData.get("id", "")
                if Databases.objects.exclude(id=id).filter(db_name=db_name, db_type=3, is_remote=False).exists():
                    return False, "存在同名数据库"
        if accept in ['ip']:
            if not accept_ips:
                return False, "需要填写访问权限中允许的IP地址"
            for a in parse_accept_ips(accept_ips):
                if not check_is_ipv4(a):
                    return False, "访问权限中IP地址格式错误：%s" % a
        return True, "ok"

    def list(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", 0)
        queryset = self.filter_queryset(self.get_queryset())
        if sid and int(sid) > 0:
            remote = RemotePgsql.objects.filter(id=int(sid)).first()
            if remote:
                queryset = queryset.filter(db_host=remote.db_host, db_port=remote.db_port, is_remote=True)
            else:
                queryset = queryset.none()
        else:
            queryset = queryset.filter(is_remote=False)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, request=request)
            tmp_data = serializer.data
            for d in tmp_data:
                d['bak_nums'] = RuyiBackup.objects.filter(type=1, fid=d['id']).count()
            return self.get_paginated_response(tmp_data)
        else:
            return SuccessResponse(data=[], msg="获取成功")

    def _get_pgsql_conn_by_sid(self, sid, db_name="postgres"):
        if sid and int(sid) > 0:
            remote = RemotePgsql.objects.filter(id=int(sid)).first()
            if not remote:
                return None, "远程PgSQL服务器不存在"
            db_conn = Pgsql_Connect(
                db_host=remote.db_host,
                db_port=int(remote.db_port),
                db_user=remote.db_user,
                db_password=remote.db_password or "",
                db_name=db_name,
                local=False,
            )
            if not db_conn:
                return None, "远程PgSQL连接失败"
            return db_conn, None
        return None, "local"

    def _get_pgsql_conn_by_db(self, db_ins):
        """通过 Databases 实例反查 RemotePgsql 获取连接"""
        if not db_ins.is_remote:
            db_conn = Pgsql_Connect(local=True)
            if not db_conn:
                return None, "本地PgSQL连接失败"
            return db_conn, None
        remote = RemotePgsql.objects.filter(db_host=db_ins.db_host, db_port=int(db_ins.db_port)).first()
        if not remote:
            return None, "未找到对应的远程PostgreSQL服务器配置"
        db_conn = Pgsql_Connect(
            db_host=remote.db_host,
            db_port=int(remote.db_port),
            db_user=remote.db_user,
            db_password=remote.db_password or "",
            local=False,
        )
        if not db_conn:
            return None, "远程PgSQL连接失败"
        return db_conn, None

    @action(methods=['POST'], detail=False)
    def sync_remote_databases(self, request, *args, **kwargs):
        """从远程PostgreSQL服务器同步数据库列表到面板"""
        reqData = get_parameter_dic(request)
        sid = reqData.get("sid", 0)
        if not sid or int(sid) <= 0:
            return ErrorResponse(msg="请选择远程PostgreSQL服务器")
        remote = RemotePgsql.objects.filter(id=int(sid)).first()
        if not remote:
            return ErrorResponse(msg="远程PostgreSQL服务器不存在")
        db_conn, conn_err = self._get_pgsql_conn_by_sid(sid)
        if conn_err:
            return ErrorResponse(msg=conn_err)
        try:
            cursor = db_conn.cursor()
            cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
            result = cursor.fetchall()
            db_conn.close()
        except Exception as e:
            return ErrorResponse(msg="查询远程数据库列表失败：%s" % str(e))
        nameArr = ['postgres']
        n = 0
        for row in result:
            db_name = row[0]
            if db_name in nameArr:
                continue
            if not re.match(r"^[\w\.-]+$", db_name):
                continue
            if Databases.objects.filter(db_name=db_name, db_type=3, db_host=remote.db_host, db_port=remote.db_port, is_remote=True).exists():
                continue
            Databases.objects.create(
                db_name=db_name,
                db_user="",
                db_pass="",
                db_host=remote.db_host,
                db_port=remote.db_port,
                db_type=3,
                format="utf8",
                accept="all",
                is_remote=True,
                remark=db_name,
            )
            n += 1
        if n > 0:
            RuyiAddOpLog(request, msg="【数据库管理】-【同步远程数据库】从 %s:%s 同步了 %s 个PgSQL数据库" % (remote.db_host, remote.db_port, n), module="dbmg")
            return DetailResponse(data={"sync_count": n}, msg="同步成功，新增 %s 个数据库" % n)
        return DetailResponse(data={"sync_count": 0}, msg="数据库已是最新，无需同步")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        ok, msg = self.check_user_inputdata(request, create_mode=True)
        if not ok:
            return ErrorResponse(msg=msg)
        reqData = get_parameter_dic(request)
        db_name = reqData.get("db_name", "")
        db_user = reqData.get("db_user", "")
        db_pass = reqData.get("db_pass", "")
        is_remote = ast_convert(reqData.get("is_remote", False))
        local = False if is_remote else True
        accept = reqData.get("accept", "")
        accept_ips = reqData.get("accept_ips", "")
        sid = reqData.get("sid", 0)
        db_conn, conn_err = self._get_pgsql_conn_by_sid(sid)
        if conn_err == "local":
            db_conn = Pgsql_Connect()
        elif conn_err:
            return ErrorResponse(msg=conn_err)
        if not db_conn:
            RuyiAddOpLog(request, msg="【数据库管理】-【创建PgSQL数据库】=>%s 失败：pgsql连接失败" % db_name, module="dbmg", status=False)
            raise ValueError("pgsql连接失败")
        if RY_CHECK_PGSQL_DATANAME_EXISTS(db_conn, db_name):
            RuyiAddOpLog(request, msg="【数据库管理】-【创建PgSQL数据库】=>%s 失败：已存在同名数据库" % db_name, module="dbmg", status=False)
            return ErrorResponse(msg="数据库中已存在此【%s】数据库名称" % db_name)
        RY_CREATE_PGSQL_DATANAME(db_conn, db_name)
        RY_CREATE_PGSQL_USER(db_conn, db_name, db_user, db_pass)
        reqData['db_type'] = 3
        reqData['format'] = 'UTF8'
        if sid and int(sid) > 0:
            remote = RemotePgsql.objects.filter(id=int(sid)).first()
            if remote:
                reqData['db_host'] = remote.db_host
                reqData['db_port'] = remote.db_port
                reqData['is_remote'] = True
        else:
            reqData['db_host'] = '127.0.0.1'
            reqData['db_port'] = RY_GET_PGSQL_PORT()
            reqData['is_remote'] = False
        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        RuyiAddOpLog(request, msg="【数据库管理】-【创建PgSQL数据库】=>%s 成功" % db_name, module="dbmg")
        return DetailResponse(data=serializer.data, msg="新增成功")

    def update(self, request, *args, **kwargs):
        return ErrorResponse(msg="接口禁用")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for sql_ins in instance_list:
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_conn, conn_err = self._get_pgsql_conn_by_db(sql_ins)
            if conn_err:
                RuyiAddOpLog(request, msg="【数据库管理】-【删除PgSQL数据库】=>%s 失败：%s" % (db_name, conn_err), module="dbmg", status=False)
                raise ValueError(conn_err + "【%s】" % db_name)
            if not db_conn:
                RuyiAddOpLog(request, msg="【数据库管理】-【删除PgSQL数据库】=>%s 失败：pgsql连接失败" % db_name, module="dbmg", status=False)
                raise ValueError("pgsql连接失败【%s】" % db_name)
            RY_DELETE_PGSQL_DATABASE(db_conn, db_name, db_user)
            bk_qy = RuyiBackup.objects.filter(type=1, fid=sql_ins.id)
            for b in bk_qy:
                DeleteFile(b.filename, empty_tips=False)
                b.delete()
            RuyiAddOpLog(request, msg="【数据库管理】-【删除PgSQL数据库】=>%s 成功" % db_name, module="dbmg")
            sql_ins.delete()
        return DetailResponse(data=[], msg="删除成功")

    @transaction.atomic
    def databasePass(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        name = reqData.get("name", "")
        is_windows = True if current_os == 'windows' else False
        if action == "get_db_pass":
            passwd = ""
            if name == 'pgsql':
                passwd = RY_GET_PGSQL_ROOT_PASS()
            return DetailResponse(data=passwd)
        elif action == "set_db_pass":
            passwd = reqData.get("passwd", "")
            if not passwd:
                return ErrorResponse(msg="密码不能为空")
            pass_ok, pass_msg = is_validate_db_passwd(passwd)
            if not pass_ok:
                return ErrorResponse(msg=pass_msg)
            if name == 'pgsql':
                RY_SET_PGSQL_ROOT_PASS(passwd, is_windows=is_windows)
                RySoftShop.objects.filter(name='pgsql').update(password=passwd)
                RuyiAddOpLog(request, msg="【数据库管理】-【设置PgSQL root密码】=> %s 成功" % passwd, module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "set_db_user_pass":
            passwd = reqData.get("db_pass", "")
            id = reqData.get("id", "")
            if not passwd:
                return ErrorResponse(msg="密码不能为空")
            if not id:
                return ErrorResponse(msg="参数错误")
            pass_ok, pass_msg = is_validate_db_passwd(passwd)
            if not pass_ok:
                return ErrorResponse(msg=pass_msg)
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            if sql_ins.is_remote and sql_ins.db_user in ['postgres']:
                return ErrorResponse(msg="不能修改远程数据库postgres密码")
            local = False if sql_ins.is_remote else True
            if local:
                db_conn = Pgsql_Connect(local=True)
            else:
                db_conn, conn_err = self._get_pgsql_conn_by_db(sql_ins)
                if conn_err:
                    raise ValueError(conn_err)
            if not db_conn:
                raise ValueError("pgsql连接失败")
            RY_RESET_PGSQL_USER_PASS(db_conn, sql_ins.db_user, passwd)
            Databases.objects.filter(id=id).update(db_pass=passwd)
            RuyiAddOpLog(request, msg="【数据库管理】-【设置PgSQL数据库密码】-【%s】=> %s 成功" % (sql_ins.db_name, passwd), module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "set_db_accept":
            accept = reqData.get("accept", "")
            accept_ips = reqData.get("accept_ips", "")
            id = reqData.get("id", "")
            if not accept:
                return ErrorResponse(msg="访问权限不能为空")
            if accept in ['ip']:
                if not accept_ips:
                    return ErrorResponse(msg="需要填写访问权限中允许的IP地址")
                for a in parse_accept_ips(accept_ips):
                    if not check_is_ipv4(a):
                        return ErrorResponse(msg="访问权限中IP地址格式错误：%s" % a)
                accept_ips = ",".join(parse_accept_ips(accept_ips))
            else:
                accept_ips = ""
            if not id:
                return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            Databases.objects.filter(id=id).update(accept=accept, accept_ips=accept_ips)
            RuyiAddOpLog(request, msg="【数据库管理】-【设置PgSQL数据库访问权限】-【%s】=> %s %s" % (sql_ins.db_name, accept, accept_ips), module="dbmg")
            return DetailResponse(msg="操作成功")
        return ErrorResponse(msg="类型错误")

    def dbTools(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        id = reqData.get("id", "")
        is_windows = True if current_os == 'windows' else False
        if action == "backup_db":
            if not id:
                return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            if local:
                db_host = "127.0.0.1"
                db_user = "postgres"
                db_port = RY_GET_PGSQL_PORT()
                db_pass = RY_GET_PGSQL_ROOT_PASS()
            else:
                remote = RemotePgsql.objects.filter(db_host=sql_ins.db_host, db_port=int(sql_ins.db_port)).first()
                if remote:
                    db_user = remote.db_user or ""
                    db_pass = remote.db_password or ""
            isok, dst_path, dst_size = RY_BACKUP_PGSQL_DATABASE(
                db_info={"id": id, "db_name": db_name, "db_user": db_user, "db_pass": db_pass, "db_host": db_host, "db_port": db_port},
                is_windows=is_windows
            )
            if isok:
                from apps.sysbak.models import RuyiBackup
                RuyiBackup.objects.create(
                    type=1,
                    fid=sql_ins.id,
                    filename=dst_path,
                    size=dst_size,
                )
            RuyiAddOpLog(request, msg="【数据库管理】-【备份PgSQL数据库】-【%s】=> %s" % (db_name, dst_path), module="dbmg")
            return DetailResponse(msg="操作成功")
        elif action == "download_backup_db":
            if not id:
                return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            bid = reqData.get("bid", "")
            bk_ins = RuyiBackup.objects.filter(type=1, id=bid).first()
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
            response['Content-Length'] = file_size
            RuyiAddOpLog(request, msg="【数据库管理】-【下载PgSQL备份】-【%s】=> %s" % (sql_ins.db_name, bk_ins.filename), module="dbmg")
            return response
        elif action == "del_backup_db":
            if not id:
                return ErrorResponse(msg="参数错误")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误")
            bid = reqData.get("bid", "")
            bk_ins = RuyiBackup.objects.filter(type=1, fid=id, id=bid).first()
            if bk_ins:
                DeleteFile(bk_ins.filename, empty_tips=False)
                bk_ins.delete()
            else:
                bk_ins = RuyiBackup.objects.filter(type=1, id=bid).first()
                if bk_ins:
                    DeleteFile(bk_ins.filename, empty_tips=False)
                    bk_ins.delete()
            RuyiAddOpLog(request, msg="【数据库管理】-【删除PgSQL备份】-【%s】=> %s" % (sql_ins.db_name, bk_ins.filename if bk_ins else ""), module="dbmg")
            return DetailResponse(msg="删除成功")
        elif action == "recover_db_sql":
            if not id:
                return ErrorResponse(msg="参数错误[0]")
            sql_ins = Databases.objects.filter(id=id).first()
            if not sql_ins:
                return ErrorResponse(msg="参数错误[1]")
            bid = reqData.get("bid", "")
            bk_ins = RuyiBackup.objects.filter(type=1, id=bid).first()
            if not bk_ins:
                return ErrorResponse(msg="参数错误[2]")
            local = False if sql_ins.is_remote else True
            db_name = sql_ins.db_name
            db_user = sql_ins.db_user
            db_pass = sql_ins.db_pass
            db_host = sql_ins.db_host
            db_port = int(sql_ins.db_port)
            if local:
                db_host = "127.0.0.1"
                db_user = "postgres"
                db_port = RY_GET_PGSQL_PORT()
                db_pass = RY_GET_PGSQL_ROOT_PASS()
            else:
                remote = RemotePgsql.objects.filter(db_host=sql_ins.db_host, db_port=int(sql_ins.db_port)).first()
                if remote:
                    db_user = remote.db_user or ""
                    db_pass = remote.db_password or ""
            isok, err_msg = RY_IMPORT_PGSQL_SQL(
                db_info={"db_name": db_name, "db_user": db_user, "db_pass": db_pass, "db_host": db_host, "db_port": db_port},
                sql_file=bk_ins.filename,
                is_windows=is_windows,
            )
            if not isok:
                return ErrorResponse(msg="恢复失败：%s" % err_msg)
            RuyiAddOpLog(request, msg="【数据库管理】-【恢复PgSQL数据库】-【%s】=> %s" % (db_name, bk_ins.filename), module="dbmg")
            return DetailResponse(msg="恢复成功")
        return ErrorResponse(msg="类型错误")