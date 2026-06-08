import json
from datetime import datetime
from rest_framework import serializers
from utils.customView import CustomAPIView
from utils.viewset import CustomModelViewSet
from utils.serializers import CustomModelSerializer
from utils.jsonResponse import SuccessResponse, ErrorResponse, DetailResponse
from utils.common import get_parameter_dic
from rest_framework.permissions import IsAuthenticated
from apps.sysnode.models import MysqlReplication, RedisReplication, RedisReplicationSlave, ClusterNode
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ssh_client import RuyiSSHClient, build_api_headers


def _ssh_exec_command(node, command, timeout=30):
    """使用统一SSH客户端执行命令"""
    try:
        with RuyiSSHClient(node) as ssh:
            out, err = ssh.exec_command(command, timeout=timeout)
            return out, err, 0
    except Exception as e:
        return "", str(e), 1


def _mysql_exec_sql(host, port, user, password, sql, db=None):
    import MySQLdb
    try:
        conn = MySQLdb.connect(
            host=host, port=int(port), user=user, passwd=password,
            db=db or '', charset='utf8mb4', connect_timeout=5
        )
        cursor = conn.cursor()
        cursor.execute(sql)
        if sql.strip().upper().startswith("SELECT") or sql.strip().upper().startswith("SHOW"):
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            result = []
            for row in rows:
                item = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if isinstance(val, bytes):
                        val = val.decode('utf-8', errors='ignore')
                    elif isinstance(val, datetime):
                        val = val.strftime('%Y-%m-%d %H:%M:%S')
                    item[col] = val
                result.append(item)
            cursor.close()
            conn.close()
            return result, None
        else:
            conn.commit()
            affected = cursor.rowcount
            cursor.close()
            conn.close()
            return affected, None
    except Exception as e:
        return None, str(e)


class MysqlReplicationSerializer(CustomModelSerializer):
    master_node_name = serializers.SerializerMethodField()
    slave_node_name = serializers.SerializerMethodField()

    class Meta:
        model = MysqlReplication
        fields = "__all__"
        read_only_fields = ["id"]

    def get_master_node_name(self, obj):
        return obj.master_node.name if obj.master_node else ""

    def get_slave_node_name(self, obj):
        return obj.slave_node.name if obj.slave_node else ""


class MysqlReplicationViewSet(CustomModelViewSet):
    queryset = MysqlReplication.objects.all().order_by('-create_at')
    serializer_class = MysqlReplicationSerializer
    search_fields = ('name', 'master_ip', 'slave_ip')
    filterset_fields = ('replicate_mode', 'binlog_mode', 'config_status', 'run_status')

    def create(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        name = reqData.get("name", "")
        master_node_id = reqData.get("master_node")
        slave_node_id = reqData.get("slave_node")
        master_ip = reqData.get("master_ip", "")
        slave_ip = reqData.get("slave_ip", "")

        if not name:
            return ErrorResponse(msg="复制名称不能为空")
        if not master_node_id or not slave_node_id:
            return ErrorResponse(msg="请选择主从节点")
        if not master_ip or not slave_ip:
            return ErrorResponse(msg="请填写主从IP")

        try:
            master_node = ClusterNode.objects.get(id=master_node_id)
            slave_node = ClusterNode.objects.get(id=slave_node_id)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        RuyiAddOpLog(request, msg=f"【MySQL主从】=>【创建】=>{name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="创建成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        name = instance.name
        serializer = self.get_serializer(instance, data=request.data, request=request, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        RuyiAddOpLog(request, msg=f"【MySQL主从】=>【修改】=>{name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="更新成功")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            name = ins.name
            ins.delete()
            RuyiAddOpLog(request, msg=f"【MySQL主从】=>【删除】=>{name}", module="nodemg")
        return DetailResponse(data=[], msg="删除成功")


class MysqlReplicationManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        if action == "config_replication":
            return self.config_replication(request, reqData)
        elif action == "check_status":
            return self.check_status(request, reqData)
        elif action == "start_replication":
            return self.start_replication(request, reqData)
        elif action == "stop_replication":
            return self.stop_replication(request, reqData)
        elif action == "skip_error":
            return self.skip_error(request, reqData)
        elif action == "reset_slave":
            return self.reset_slave(request, reqData)
        elif action == "switch_master":
            return self.switch_master(request, reqData)
        elif action == "get_nodes":
            return self.get_nodes(request)
        elif action == "test_connection":
            return self.test_connection(request, reqData)
        return ErrorResponse(msg="无效的操作")

    def test_connection(self, request, reqData):
        host = reqData.get("host", "")
        port = reqData.get("port", 3306)
        user = reqData.get("user", "root")
        password = reqData.get("password", "")
        if not host:
            return ErrorResponse(msg="请填写数据库地址")
        result, err = _mysql_exec_sql(host, port, user, password, "SELECT 1")
        if err:
            return ErrorResponse(msg=f"连接失败: {err}")
        return DetailResponse(data={"connected": True}, msg="连接成功")

    def config_replication(self, request, reqData):
        rep_id = reqData.get("id")
        sync_mode = reqData.get("sync_mode", "config_only")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = MysqlReplication.objects.get(id=rep_id)
        except MysqlReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

        rep.config_status = "configuring"
        rep.save(update_fields=["config_status"])

        try:
            from apps.sysnode.mysql_sync_service import MysqlSyncService
            from apps.systask.tasks import installTask

            def run_sync(rid, mode):
                rep_obj = MysqlReplication.objects.get(id=rid)
                service = MysqlSyncService(rep_obj)
                service.execute(sync_mode=mode)

            # 使用APScheduler后台执行，避免HTTP超时
            installTask(
                job_id=f"mysql_rep_sync_{rep_id}",
                job_func=run_sync,
                func_args=[rep_id, sync_mode]
            )

            RuyiAddOpLog(request, msg=f"【MySQL主从】=>【配置】=>{rep.name}(模式:{sync_mode})", module="nodemg")
            return DetailResponse(data={"config_status": "configuring"}, msg="配置任务已提交，请通过WebSocket查看进度")
        except Exception as e:
            rep.config_status = "failed"
            rep.error_msg = str(e)
            rep.save(update_fields=["config_status", "error_msg"])
            return ErrorResponse(msg=f"配置失败: {str(e)}")

    def get_config_log(self, request, reqData):
        """获取MySQL主从配置日志和步骤进度"""
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = MysqlReplication.objects.get(id=rep_id)
            return DetailResponse(data={
                "id": rep.id,
                "name": rep.name,
                "config_status": rep.config_status,
                "current_step": rep.current_step,
                "config_log": rep.config_log,
                "error_msg": rep.error_msg,
            }, msg="获取成功")
        except MysqlReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

    def check_status(self, request, reqData):
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = MysqlReplication.objects.get(id=rep_id)
        except MysqlReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

        if rep.config_status != "done":
            return DetailResponse(data={
                "id": rep.id,
                "name": rep.name,
                "config_status": rep.config_status,
                "run_status": rep.run_status,
                "error_msg": rep.error_msg,
            }, msg="获取成功")

        try:
            slave_status, err = _mysql_exec_sql(
                rep.slave_ip, rep.slave_port, rep.root_user, rep.root_pass,
                "SHOW SLAVE STATUS"
            )
            if err:
                rep.run_status = "error"
                rep.error_msg = f"查询从库状态失败: {err}"
                rep.save(update_fields=["run_status", "error_msg"])
                return DetailResponse(data={
                    "id": rep.id,
                    "name": rep.name,
                    "config_status": rep.config_status,
                    "run_status": rep.run_status,
                    "error_msg": rep.error_msg,
                }, msg="获取成功")

            if slave_status and len(slave_status) > 0:
                status = slave_status[0]
                io_running = status.get("Slave_IO_Running", "No")
                sql_running = status.get("Slave_SQL_Running", "No")
                seconds_behind = status.get("Seconds_Behind_Master", -1)
                master_log = status.get("Master_Log_File", "")
                read_log = status.get("Read_Master_Log_Pos", 0)
                executed_gtid = status.get("Executed_Gtid_Set", "")
                last_error = status.get("Last_Error", "")

                rep.io_status = io_running
                rep.sql_status = sql_running
                rep.master_log_file = master_log
                rep.master_log_pos = read_log
                rep.executed_gtid_set = executed_gtid or ""
                try:
                    rep.seconds_behind_master = int(seconds_behind) if seconds_behind is not None else -1
                except (ValueError, TypeError):
                    rep.seconds_behind_master = -1

                if io_running == "Yes" and sql_running == "Yes":
                    rep.run_status = "running"
                    rep.error_msg = ""
                elif last_error:
                    rep.run_status = "error"
                    rep.error_msg = last_error
                else:
                    rep.run_status = "stopped"

                from django.utils import timezone
                rep.last_check_time = timezone.now()
                rep.save(update_fields=[
                    "io_status", "sql_status", "master_log_file", "master_log_pos",
                    "executed_gtid_set", "seconds_behind_master", "run_status",
                    "error_msg", "last_check_time"
                ])

                return DetailResponse(data={
                    "id": rep.id,
                    "name": rep.name,
                    "config_status": rep.config_status,
                    "run_status": rep.run_status,
                    "io_status": io_running,
                    "sql_status": sql_running,
                    "master_log_file": master_log,
                    "master_log_pos": read_log,
                    "executed_gtid_set": executed_gtid,
                    "seconds_behind_master": rep.seconds_behind_master,
                    "last_error": last_error,
                    "last_check_time": rep.last_check_time,
                    "slave_io_running": io_running,
                    "slave_sql_running": sql_running,
                    "master_host": status.get("Master_Host", ""),
                    "master_port": status.get("Master_Port", ""),
                    "relay_log_file": status.get("Relay_Log_File", ""),
                    "relay_log_pos": status.get("Relay_Log_Pos", ""),
                    "replicate_do_db": status.get("Replicate_Do_DB", ""),
                    "replicate_ignore_db": status.get("Replicate_Ignore_DB", ""),
                    "last_io_error": status.get("Last_IO_Error", ""),
                    "last_sql_error": status.get("Last_SQL_Error", ""),
                }, msg="获取成功")
            else:
                rep.run_status = "stopped"
                rep.save(update_fields=["run_status"])
                return DetailResponse(data={
                    "id": rep.id,
                    "name": rep.name,
                    "config_status": rep.config_status,
                    "run_status": "stopped",
                    "error_msg": "无法获取从库状态",
                }, msg="获取成功")
        except Exception as e:
            return ErrorResponse(msg=f"查询失败: {str(e)}")

    def start_replication(self, request, reqData):
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = MysqlReplication.objects.get(id=rep_id)
            _, err = _mysql_exec_sql(
                rep.slave_ip, rep.slave_port, rep.root_user, rep.root_pass,
                "START SLAVE;"
            )
            if err:
                return ErrorResponse(msg=f"启动失败: {err}")
            rep.run_status = "running"
            rep.save(update_fields=["run_status"])
            RuyiAddOpLog(request, msg=f"【MySQL主从】=>【启动】=>{rep.name}", module="nodemg")
            return DetailResponse(data={"run_status": rep.run_status}, msg="启动成功")
        except MysqlReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

    def stop_replication(self, request, reqData):
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = MysqlReplication.objects.get(id=rep_id)
            _, err = _mysql_exec_sql(
                rep.slave_ip, rep.slave_port, rep.root_user, rep.root_pass,
                "STOP SLAVE;"
            )
            if err:
                return ErrorResponse(msg=f"停止失败: {err}")
            rep.run_status = "stopped"
            rep.save(update_fields=["run_status"])
            RuyiAddOpLog(request, msg=f"【MySQL主从】=>【停止】=>{rep.name}", module="nodemg")
            return DetailResponse(data={"run_status": rep.run_status}, msg="停止成功")
        except MysqlReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

    def skip_error(self, request, reqData):
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = MysqlReplication.objects.get(id=rep_id)
            skip_sql = "STOP SLAVE; SET GLOBAL SQL_SLAVE_SKIP_COUNTER = 1; START SLAVE;"
            _, err = _mysql_exec_sql(
                rep.slave_ip, rep.slave_port, rep.root_user, rep.root_pass,
                skip_sql
            )
            if err:
                return ErrorResponse(msg=f"跳过错误失败: {err}")
            RuyiAddOpLog(request, msg=f"【MySQL主从】=>【跳过错误】=>{rep.name}", module="nodemg")
            return DetailResponse(data={}, msg="跳过错误成功")
        except MysqlReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

    def reset_slave(self, request, reqData):
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = MysqlReplication.objects.get(id=rep_id)
            _, err = _mysql_exec_sql(
                rep.slave_ip, rep.slave_port, rep.root_user, rep.root_pass,
                "STOP SLAVE; RESET SLAVE ALL;"
            )
            if err:
                return ErrorResponse(msg=f"重置失败: {err}")
            rep.config_status = "pending"
            rep.run_status = "stopped"
            rep.io_status = ""
            rep.sql_status = ""
            rep.master_log_file = ""
            rep.master_log_pos = 0
            rep.seconds_behind_master = -1
            rep.error_msg = ""
            rep.save(update_fields=[
                "config_status", "run_status", "io_status", "sql_status",
                "master_log_file", "master_log_pos", "seconds_behind_master", "error_msg"
            ])
            RuyiAddOpLog(request, msg=f"【MySQL主从】=>【重置】=>{rep.name}", module="nodemg")
            return DetailResponse(data={}, msg="重置成功")
        except MysqlReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

    def switch_master(self, request, reqData):
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = MysqlReplication.objects.get(id=rep_id)
            _, err = _mysql_exec_sql(
                rep.slave_ip, rep.slave_port, rep.root_user, rep.root_pass,
                "STOP SLAVE;"
            )
            if err:
                return ErrorResponse(msg=f"停止从库失败: {err}")

            _, err = _mysql_exec_sql(
                rep.slave_ip, rep.slave_port, rep.root_user, rep.root_pass,
                "RESET MASTER;"
            )
            if err:
                return ErrorResponse(msg=f"重置主库失败: {err}")

            old_master_ip = rep.master_ip
            old_master_port = rep.master_port
            old_master_node_id = rep.master_node_id
            old_slave_ip = rep.slave_ip
            old_slave_port = rep.slave_port
            old_slave_node_id = rep.slave_node_id

            rep.master_ip = old_slave_ip
            rep.master_port = old_slave_port
            rep.master_node_id = old_slave_node_id
            rep.slave_ip = old_master_ip
            rep.slave_port = old_master_port
            rep.slave_node_id = old_master_node_id
            rep.config_status = "pending"
            rep.run_status = "stopped"
            rep.io_status = ""
            rep.sql_status = ""
            rep.error_msg = ""
            rep.save(update_fields=[
                "master_ip", "master_port", "master_node_id",
                "slave_ip", "slave_port", "slave_node_id",
                "config_status", "run_status", "io_status", "sql_status", "error_msg"
            ])

            RuyiAddOpLog(request, msg=f"【MySQL主从】=>【主从切换】=>{rep.name}", module="nodemg")
            return DetailResponse(data={}, msg="主从切换完成，请重新配置复制")
        except MysqlReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

    def get_nodes(self, request):
        nodes = ClusterNode.objects.filter(status=0).values("id", "name", "server_ip")
        return DetailResponse(data=list(nodes), msg="获取成功")


class RedisReplicationSlaveSerializer(CustomModelSerializer):
    slave_node_name = serializers.SerializerMethodField()

    class Meta:
        model = RedisReplicationSlave
        fields = "__all__"
        read_only_fields = ["id"]

    def get_slave_node_name(self, obj):
        return obj.slave_node.name if obj.slave_node else ""


class RedisReplicationSerializer(CustomModelSerializer):
    master_node_name = serializers.SerializerMethodField()
    slaves = RedisReplicationSlaveSerializer(many=True, read_only=True)

    class Meta:
        model = RedisReplication
        fields = "__all__"
        read_only_fields = ["id"]

    def get_master_node_name(self, obj):
        return obj.master_node.name if obj.master_node else ""


class RedisReplicationViewSet(CustomModelViewSet):
    queryset = RedisReplication.objects.all().order_by('-create_at')
    serializer_class = RedisReplicationSerializer
    search_fields = ('name', 'master_ip')
    filterset_fields = ('config_status', 'run_status')

    def create(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        name = reqData.get("name", "")
        master_node_id = reqData.get("master_node")
        master_ip = reqData.get("master_ip", "")

        if not name:
            return ErrorResponse(msg="复制组名称不能为空")
        if not master_node_id:
            return ErrorResponse(msg="请选择主库节点")
        if not master_ip:
            return ErrorResponse(msg="请填写主库IP")

        slaves_data = reqData.pop("slaves", [])
        if isinstance(slaves_data, str):
            try:
                slaves_data = json.loads(slaves_data)
            except Exception:
                slaves_data = []

        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        rep = RedisReplication.objects.get(id=serializer.data.get("id"))
        for s in slaves_data:
            RedisReplicationSlave.objects.create(
                replication=rep,
                slave_node_id=s.get("slave_node"),
                slave_ip=s.get("slave_ip", ""),
                slave_port=s.get("slave_port", 6379),
                slave_password=s.get("slave_password", ""),
            )
        rep.slave_count = len(slaves_data)
        rep.save(update_fields=["slave_count"])

        RuyiAddOpLog(request, msg=f"【Redis主从】=>【创建】=>{name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="创建成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        name = instance.name
        reqData = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)

        slaves_data = reqData.pop("slaves", [])
        if isinstance(slaves_data, str):
            try:
                slaves_data = json.loads(slaves_data)
            except Exception:
                slaves_data = []

        serializer = self.get_serializer(instance, data=reqData, request=request, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if slaves_data is not None:
            RedisReplicationSlave.objects.filter(replication=instance).delete()
            for s in slaves_data:
                RedisReplicationSlave.objects.create(
                    replication=instance,
                    slave_node_id=s.get("slave_node"),
                    slave_ip=s.get("slave_ip", ""),
                    slave_port=s.get("slave_port", 6379),
                    slave_password=s.get("slave_password", ""),
                )
            instance.slave_count = len(slaves_data)
            instance.save(update_fields=["slave_count"])

        RuyiAddOpLog(request, msg=f"【Redis主从】=>【修改】=>{name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="更新成功")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            name = ins.name
            RedisReplicationSlave.objects.filter(replication=ins).delete()
            ins.delete()
            RuyiAddOpLog(request, msg=f"【Redis主从】=>【删除】=>{name}", module="nodemg")
        return DetailResponse(data=[], msg="删除成功")


class RedisReplicationManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        if action == "config_replication":
            return self.config_replication(request, reqData)
        elif action == "check_status":
            return self.check_status(request, reqData)
        elif action == "get_nodes":
            return self.get_nodes(request)
        elif action == "test_connection":
            return self.test_connection(request, reqData)
        elif action == "redis_monitor":
            return self.redis_monitor(request, reqData)
        return ErrorResponse(msg="无效的操作")

    def test_connection(self, request, reqData):
        host = reqData.get("host", "127.0.0.1")
        port = reqData.get("port", 6379)
        password = reqData.get("password", "")
        try:
            import redis
            r = redis.Redis(host=host, port=int(port), password=password or None, socket_timeout=5)
            r.ping()
            return DetailResponse(data={"connected": True}, msg="连接成功")
        except Exception as e:
            return ErrorResponse(msg=f"连接失败: {str(e)}")

    def config_replication(self, request, reqData):
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = RedisReplication.objects.get(id=rep_id)
        except RedisReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

        rep.config_status = "configuring"
        rep.save(update_fields=["config_status"])

        try:
            import redis as redis_lib
            try:
                master_r = redis_lib.Redis(
                    host=rep.master_ip, port=rep.master_port,
                    password=rep.master_password or None, socket_timeout=5
                )
                master_r.ping()
            except Exception as e:
                rep.config_status = "failed"
                rep.error_msg = f"主库连接失败: {str(e)}"
                rep.save(update_fields=["config_status", "error_msg"])
                return ErrorResponse(msg=f"主库连接失败: {str(e)}")

            slave_objects = RedisReplicationSlave.objects.filter(replication=rep)
            success_count = 0
            for slave_obj in slave_objects:
                try:
                    slave_r = redis_lib.Redis(
                        host=slave_obj.slave_ip, port=slave_obj.slave_port,
                        password=slave_obj.slave_password or None, socket_timeout=5
                    )
                    slave_r.ping()
                    try:
                        slave_r.replicaof(rep.master_ip, rep.master_port)
                    except AttributeError:
                        slave_r.slaveof(rep.master_ip, rep.master_port)
                    slave_obj.link_status = "connected"
                    success_count += 1
                except Exception as e:
                    slave_obj.link_status = f"failed: {str(e)}"

            rep.normal_slaves = success_count
            rep.config_status = "done"
            rep.run_status = "running"
            rep.error_msg = ""
            rep.save(update_fields=["config_status", "run_status", "normal_slaves", "error_msg"])

            RuyiAddOpLog(request, msg=f"【Redis主从】=>【配置】=>{rep.name}", module="nodemg")
            return DetailResponse(data={"config_status": rep.config_status}, msg="配置完成")
        except Exception as e:
            rep.config_status = "failed"
            rep.error_msg = str(e)
            rep.save(update_fields=["config_status", "error_msg"])
            return ErrorResponse(msg=f"配置失败: {str(e)}")

    def check_status(self, request, reqData):
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = RedisReplication.objects.get(id=rep_id)
        except RedisReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

        if rep.config_status != "done":
            return DetailResponse(data={
                "id": rep.id,
                "name": rep.name,
                "config_status": rep.config_status,
                "run_status": rep.run_status,
                "error_msg": rep.error_msg,
            }, msg="获取成功")

        try:
            import redis as redis_lib
            master_r = redis_lib.Redis(
                host=rep.master_ip, port=rep.master_port,
                password=rep.master_password or None, socket_timeout=5
            )
            info = master_r.info("replication")

            rep.slave_count = info.get("connected_slaves", 0)
            normal = 0
            total_lag = 0

            slave_objects = RedisReplicationSlave.objects.filter(replication=rep)
            for i, slave_obj in enumerate(slave_objects):
                slave_key = f"slave{i}"
                if slave_key in info:
                    slave_info = info[slave_key]
                    slave_obj.link_status = slave_info.get("state", "unknown")
                    slave_obj.offset = slave_info.get("offset", 0)
                    slave_obj.lag = slave_info.get("lag", 0)
                    if slave_obj.link_status == "online":
                        normal += 1
                        total_lag += slave_obj.lag
                    slave_obj.save(update_fields=["link_status", "offset", "lag"])

            rep.normal_slaves = normal
            rep.avg_lag = round(total_lag / normal, 2) if normal > 0 else 0
            rep.run_status = "running" if normal > 0 else "error"
            from django.utils import timezone
            rep.last_check_time = timezone.now()
            rep.save(update_fields=["slave_count", "normal_slaves", "avg_lag", "run_status", "last_check_time"])

            master_role = info.get("role", "unknown")
            master_repl_offset = info.get("master_repl_offset", 0)

            slave_details = []
            for slave_obj in slave_objects:
                slave_details.append({
                    "id": slave_obj.id,
                    "slave_ip": slave_obj.slave_ip,
                    "slave_port": slave_obj.slave_port,
                    "link_status": slave_obj.link_status,
                    "offset": slave_obj.offset,
                    "lag": slave_obj.lag,
                })

            return DetailResponse(data={
                "id": rep.id,
                "name": rep.name,
                "config_status": rep.config_status,
                "run_status": rep.run_status,
                "master_role": master_role,
                "master_repl_offset": master_repl_offset,
                "connected_slaves": rep.slave_count,
                "normal_slaves": rep.normal_slaves,
                "avg_lag": rep.avg_lag,
                "slave_details": slave_details,
                "last_check_time": rep.last_check_time,
            }, msg="获取成功")
        except Exception as e:
            rep.run_status = "error"
            rep.error_msg = str(e)
            rep.save(update_fields=["run_status", "error_msg"])
            return ErrorResponse(msg=f"查询失败: {str(e)}")

    def redis_monitor(self, request, reqData):
        """Redis监控增强 - 内存/键/命令/连接统计"""
        rep_id = reqData.get("id")
        if not rep_id:
            return ErrorResponse(msg="缺少复制ID")
        try:
            rep = RedisReplication.objects.get(id=rep_id)
        except RedisReplication.DoesNotExist:
            return ErrorResponse(msg="复制记录不存在")

        try:
            import redis as redis_lib
            master_r = redis_lib.Redis(
                host=rep.master_ip, port=rep.master_port,
                password=rep.master_password or None, socket_timeout=5
            )
            master_r.ping()

            # 获取详细info
            info_all = master_r.info()
            info_memory = master_r.info("memory")
            info_stats = master_r.info("stats")
            info_clients = master_r.info("clients")
            info_keyspace = master_r.info("keyspace")

            # 内存统计
            used_memory = info_memory.get("used_memory", 0)
            used_memory_human = info_memory.get("used_memory_human", "0B")
            used_memory_peak = info_memory.get("used_memory_peak", 0)
            used_memory_peak_human = info_memory.get("used_memory_peak_human", "0B")
            maxmemory = info_memory.get("maxmemory", 0)
            mem_fragmentation_ratio = info_memory.get("mem_fragmentation_ratio", 0)

            # 键空间统计
            db_keys = {}
            for key, val in info_keyspace.items():
                if key.startswith("db"):
                    # Redis keyspace值可能是dict或字符串格式
                    if isinstance(val, dict):
                        db_keys[key] = val.get("keys", 0)
                    elif isinstance(val, str):
                        # 格式: "keys=100,expires=10,avg_ttl=0"
                        for part in val.split(","):
                            if part.startswith("keys="):
                                try:
                                    db_keys[key] = int(part.split("=")[1])
                                except (ValueError, IndexError):
                                    db_keys[key] = 0

            # 命令统计
            total_commands = info_stats.get("total_commands_processed", 0)
            instantaneous_ops = info_stats.get("instantaneous_ops_per_sec", 0)
            total_net_input = info_stats.get("total_net_input_bytes", 0)
            total_net_output = info_stats.get("total_net_output_bytes", 0)

            # 连接统计
            connected_clients = info_clients.get("connected_clients", 0)
            blocked_clients = info_clients.get("blocked_clients", 0)

            # 复制统计
            info_repl = master_r.info("replication")
            master_repl_offset = info_repl.get("master_repl_offset", 0)
            connected_slaves = info_repl.get("connected_slaves", 0)
            repl_backlog_size = info_repl.get("repl_backlog_size", 0)

            # 从库延迟统计
            slave_lags = []
            slave_objects = RedisReplicationSlave.objects.filter(replication=rep)
            for i, slave_obj in enumerate(slave_objects):
                slave_key = f"slave{i}"
                if slave_key in info_repl:
                    lag = info_repl[slave_key].get("lag", 0)
                    slave_lags.append({
                        "slave_ip": slave_obj.slave_ip,
                        "slave_port": slave_obj.slave_port,
                        "lag": lag,
                        "offset": info_repl[slave_key].get("offset", 0),
                    })

            # 慢查询
            slowlog = master_r.slowlog_get(10)
            slow_queries = []
            for entry in slowlog:
                slow_queries.append({
                    "id": entry.get("id", 0),
                    "duration_us": entry.get("duration", 0),
                    "command": " ".join(entry.get("command", []))[:200],
                    "time": entry.get("start_time", 0),
                })

            return DetailResponse(data={
                "memory": {
                    "used_memory": used_memory,
                    "used_memory_human": used_memory_human,
                    "used_memory_peak": used_memory_peak,
                    "used_memory_peak_human": used_memory_peak_human,
                    "maxmemory": maxmemory,
                    "mem_fragmentation_ratio": mem_fragmentation_ratio,
                },
                "keyspace": db_keys,
                "commands": {
                    "total_commands": total_commands,
                    "instantaneous_ops": instantaneous_ops,
                    "total_net_input": total_net_input,
                    "total_net_output": total_net_output,
                },
                "clients": {
                    "connected_clients": connected_clients,
                    "blocked_clients": blocked_clients,
                },
                "replication": {
                    "master_repl_offset": master_repl_offset,
                    "connected_slaves": connected_slaves,
                    "repl_backlog_size": repl_backlog_size,
                    "slave_lags": slave_lags,
                },
                "slow_queries": slow_queries,
                "uptime_in_seconds": info_all.get("uptime_in_seconds", 0),
                "version": info_all.get("redis_version", "unknown"),
            }, msg="获取成功")
        except Exception as e:
            return ErrorResponse(msg=f"获取Redis监控信息失败: {str(e)}")

    def get_nodes(self, request):
        nodes = ClusterNode.objects.filter(status=0).values("id", "name", "server_ip")
        return DetailResponse(data=list(nodes), msg="获取成功")
