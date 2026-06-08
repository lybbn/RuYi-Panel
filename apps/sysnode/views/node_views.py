import json
import paramiko
import platform
import psutil
import socket
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework import serializers
from utils.customView import CustomAPIView
from utils.viewset import CustomModelViewSet
from utils.serializers import CustomModelSerializer
from utils.jsonResponse import SuccessResponse, ErrorResponse, DetailResponse
from utils.pagination import CustomPagination
from utils.common import get_parameter_dic
from rest_framework.permissions import IsAuthenticated
from apps.sysnode.models import ClusterNode, NodeCategory
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ssh_client import RuyiSSHClient, build_api_headers


def _is_windows():
    return platform.system().lower() == 'windows'


class NodeCategorySerializer(CustomModelSerializer):
    class Meta:
        model = NodeCategory
        fields = "__all__"
        read_only_fields = ["id"]


class ClusterNodeSerializer(CustomModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = ClusterNode
        fields = "__all__"
        read_only_fields = ["id"]

    def get_category_name(self, obj):
        if obj.category:
            return obj.category.name
        return ""


class ClusterNodeListSerializer(CustomModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = ClusterNode
        fields = [
            "id", "name", "address", "server_ip", "node_type", "status",
            "remarks", "is_local", "os_info", "cpu_count", "cpu_usage",
            "mem_total", "mem_used", "mem_usage", "disk_total", "disk_used",
            "disk_usage", "uptime", "last_monitor_time", "error_msg",
            "category", "category_name", "create_at"
        ]
        read_only_fields = ["id"]

    def get_category_name(self, obj):
        if obj.category:
            return obj.category.name
        return ""


class NodeCategoryViewSet(CustomModelViewSet):
    queryset = NodeCategory.objects.all().order_by('sort', '-create_at')
    serializer_class = NodeCategorySerializer
    search_fields = ('name',)
    filterset_fields = ('name',)


class ClusterNodeViewSet(CustomModelViewSet):
    queryset = ClusterNode.objects.all().order_by('-create_at')
    serializer_class = ClusterNodeSerializer
    list_serializer_class = ClusterNodeListSerializer
    search_fields = ('name', 'server_ip', 'address')
    filterset_fields = ('node_type', 'status', 'category')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ClusterNodeListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = ClusterNodeListSerializer(queryset, many=True, context={'request': request})
        return SuccessResponse(data=serializer.data, msg="获取成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        name = instance.name
        serializer = self.get_serializer(instance, data=request.data, request=request, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        RuyiAddOpLog(request, msg=f"【节点管理】=>【修改节点】=>{name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="更新成功")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            name = ins.name
            ins.delete()
            RuyiAddOpLog(request, msg=f"【节点管理】=>【删除节点】=>{name}", module="nodemg")
        return DetailResponse(data=[], msg="删除成功")


class ClusterNodeManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        if action == "get_node_info":
            return self.get_node_info(request, reqData)
        elif action == "get_node_monitor":
            return self.get_node_monitor(request, reqData)
        elif action == "test_connection":
            return self.test_connection(request, reqData)
        elif action == "get_local_info":
            return self.get_local_info(request)
        elif action == "get_panel_url":
            return self.get_panel_url(request, reqData)
        elif action == "get_node_sites":
            return self.get_node_sites(request, reqData)
        return ErrorResponse(msg="无效的操作")

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        if action == "add_node":
            return self.add_node(request, reqData)
        elif action == "sync_node_status":
            return self.sync_node_status(request, reqData)
        elif action == "batch_sync_status":
            return self.batch_sync_status(request)
        elif action == "restart_panel":
            return self.restart_panel(request, reqData)
        elif action == "server_reboot":
            return self.server_reboot(request, reqData)
        elif action == "generate_sso_token":
            return self.generate_sso_token(request, reqData)
        elif action == "test_ssh_conf":
            return self.test_ssh_conf(request, reqData)
        return ErrorResponse(msg="无效的操作")

    def add_node(self, request, reqData):
        name = reqData.get("name", "")
        server_ip = reqData.get("server_ip", "")
        address = reqData.get("address", "")
        node_type = reqData.get("node_type", "api")
        api_key = reqData.get("api_key", "")
        ssh_conf = reqData.get("ssh_conf", "{}")
        category_id = reqData.get("category", None)
        remarks = reqData.get("remarks", "")

        if not name:
            return ErrorResponse(msg="节点名称不能为空")
        if not server_ip:
            return ErrorResponse(msg="服务器IP不能为空")

        if ClusterNode.objects.filter(server_ip=server_ip).exists():
            return ErrorResponse(msg="该IP节点已存在")

        if isinstance(ssh_conf, str):
            try:
                ssh_conf = json.loads(ssh_conf)
            except Exception:
                return ErrorResponse(msg="SSH配置数据格式错误")

        # 添加节点前验证连通性
        if node_type == "api" and api_key and address:
            test_result = self._test_api_connection_for_add(address, api_key)
            if not test_result["connected"]:
                return ErrorResponse(msg=f"节点连接验证失败: {test_result['msg']}")
        elif node_type == "ssh" and server_ip:
            test_result = self._test_ssh_connection_for_add(ssh_conf, server_ip)
            if not test_result["connected"]:
                return ErrorResponse(msg=f"SSH连接验证失败: {test_result['msg']}")

        node = ClusterNode(
            name=name,
            server_ip=server_ip,
            address=address,
            node_type=node_type,
            api_key=api_key,
            ssh_conf=json.dumps(ssh_conf) if isinstance(ssh_conf, dict) else ssh_conf,
            remarks=remarks,
            status=3,
        )
        if category_id:
            try:
                node.category = NodeCategory.objects.get(id=category_id)
            except NodeCategory.DoesNotExist:
                pass
        node.save()
        RuyiAddOpLog(request, msg=f"【节点管理】=>【添加节点】=>{name}", module="nodemg")
        return DetailResponse(data={"id": node.id}, msg="添加成功")

    def get_node_info(self, request, reqData):
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            serializer = ClusterNodeSerializer(node)
            return DetailResponse(data=serializer.data, msg="获取成功")
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def get_node_monitor(self, request, reqData):
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            data = {
                "id": node.id,
                "name": node.name,
                "status": node.status,
                "os_info": node.os_info,
                "cpu_count": node.cpu_count,
                "cpu_usage": node.cpu_usage,
                "mem_total": node.mem_total,
                "mem_used": node.mem_used,
                "mem_usage": node.mem_usage,
                "disk_total": node.disk_total,
                "disk_used": node.disk_used,
                "disk_usage": node.disk_usage,
                "uptime": node.uptime,
                "last_monitor_time": node.last_monitor_time.strftime("%Y-%m-%d %H:%M:%S") if node.last_monitor_time else "",
            }
            return DetailResponse(data=data, msg="获取成功")
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def test_connection(self, request, reqData):
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return DetailResponse(data={"connected": True}, msg="本机节点连接正常")
            if node.node_type == "ssh":
                return self._test_ssh_connection(node)
            else:
                return self._test_api_connection(node)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def _test_ssh_connection(self, node):
        try:
            with RuyiSSHClient(node, timeout=10) as ssh:
                ssh.exec_command("echo OK", timeout=5)
            node.status = 0
            node.error_msg = ""
            node.error_num = 0
            node.save(update_fields=["status", "error_msg", "error_num"])
            return DetailResponse(data={"connected": True}, msg="SSH连接成功")
        except Exception as e:
            node.status = 1
            node.error_msg = str(e)
            node.error_num += 1
            node.save(update_fields=["status", "error_msg", "error_num"])
            return ErrorResponse(msg=f"SSH连接失败: {str(e)}")

    def _test_ssh_connection_for_add(self, ssh_conf, server_ip):
        """添加节点时验证SSH连通性（不依赖已保存的节点）"""
        try:
            from utils.ssh_client import RuyiSSHClient
            # 创建临时节点对象用于SSH连接
            temp_node = ClusterNode(
                server_ip=server_ip,
                ssh_conf=json.dumps(ssh_conf) if isinstance(ssh_conf, dict) else ssh_conf,
            )
            with RuyiSSHClient(temp_node, timeout=10) as ssh:
                ssh.exec_command("echo OK", timeout=5)
            return {"connected": True, "msg": "SSH连接成功"}
        except Exception as e:
            return {"connected": False, "msg": str(e)}

    def _test_api_connection_for_add(self, address, api_key):
        """添加节点时验证API连通性（不依赖已保存的节点）"""
        import requests
        try:
            url = f"{address.rstrip('/')}/api/sys/getSysMonitor/"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Ruyi-Node-Client/1.0",
                "RY-API-KEY": api_key,
            }
            resp = requests.get(url, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 2000:
                    return {"connected": True, "msg": "API连接成功"}
                else:
                    return {"connected": False, "msg": result.get("msg", "未知错误")}
            elif resp.status_code == 401:
                return {"connected": False, "msg": "认证失败(401)，请检查API密钥"}
            elif resp.status_code == 403:
                return {"connected": False, "msg": "访问被拒绝(403)，请检查IP白名单"}
            else:
                return {"connected": False, "msg": f"HTTP {resp.status_code}"}
        except requests.exceptions.ConnectTimeout:
            return {"connected": False, "msg": "连接超时，请检查地址和端口"}
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e)
            if "Connection refused" in error_msg:
                return {"connected": False, "msg": "连接被拒绝，请检查远程面板是否运行"}
            return {"connected": False, "msg": f"连接失败: {error_msg[:100]}"}
        except Exception as e:
            return {"connected": False, "msg": str(e)[:100]}

    def _build_api_headers(self, node):
        return build_api_headers(node)

    def _test_api_connection(self, node):
        import requests
        try:
            url = f"{node.address.rstrip('/')}/api/sys/getSysMonitor/"
            headers = self._build_api_headers(node)
            resp = requests.get(url, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                try:
                    result = resp.json()
                    if result.get("code") == 2000:
                        node.status = 0
                        node.error_msg = ""
                        node.error_num = 0
                        node.save(update_fields=["status", "error_msg", "error_num"])
                        return DetailResponse(data={"connected": True}, msg="API连接成功")
                    else:
                        msg = result.get("msg", "未知错误")
                        node.status = 1
                        node.error_msg = msg
                        node.error_num += 1
                        node.save(update_fields=["status", "error_msg", "error_num"])
                        return ErrorResponse(msg=f"API连接失败: {msg}")
                except Exception:
                    node.status = 1
                    node.error_msg = "响应格式异常"
                    node.error_num += 1
                    node.save(update_fields=["status", "error_msg", "error_num"])
                    return ErrorResponse(msg="API连接失败: 远程节点响应格式异常，可能不是如意面板服务")
            elif resp.status_code == 401:
                node.status = 1
                node.error_msg = "认证失败"
                node.error_num += 1
                node.save(update_fields=["status", "error_msg", "error_num"])
                return ErrorResponse(msg="API连接失败: 认证失败(401)，请检查API密钥是否正确，以及远程面板是否已启用API接口")
            elif resp.status_code == 403:
                node.status = 1
                node.error_msg = "访问被拒绝"
                node.error_num += 1
                node.save(update_fields=["status", "error_msg", "error_num"])
                return ErrorResponse(msg="API连接失败: 访问被拒绝(403)，请检查远程面板的API接口IP白名单设置")
            elif resp.status_code == 404:
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    node.status = 1
                    node.error_msg = "API端点不存在"
                    node.error_num += 1
                    node.save(update_fields=["status", "error_msg", "error_num"])
                    return ErrorResponse(msg="API连接失败: 远程节点返回404页面，请检查: 1)地址和端口是否正确 2)远程面板是否正常运行 3)远程面板版本是否支持API接口")
                else:
                    node.status = 1
                    node.error_msg = "HTTP 404"
                    node.error_num += 1
                    node.save(update_fields=["status", "error_msg", "error_num"])
                    return ErrorResponse(msg="API连接失败: 接口不存在(404)，请检查远程面板版本是否支持API接口")
            else:
                node.status = 1
                node.error_msg = f"HTTP {resp.status_code}"
                node.error_num += 1
                node.save(update_fields=["status", "error_msg", "error_num"])
                return ErrorResponse(msg=f"API连接失败: HTTP {resp.status_code}")
        except requests.exceptions.ConnectTimeout:
            node.status = 1
            node.error_msg = "连接超时"
            node.error_num += 1
            node.save(update_fields=["status", "error_msg", "error_num"])
            return ErrorResponse(msg="API连接失败: 连接超时，请检查远程服务器地址和端口是否正确")
        except requests.exceptions.ConnectionError as e:
            node.status = 1
            node.error_msg = str(e)
            node.error_num += 1
            node.save(update_fields=["status", "error_msg", "error_num"])
            error_msg = str(e)
            if "Connection refused" in error_msg:
                return ErrorResponse(msg="API连接失败: 连接被拒绝，请检查远程面板是否正常运行以及端口是否正确")
            elif "Name or service not known" in error_msg or "getaddrinfo failed" in error_msg:
                return ErrorResponse(msg="API连接失败: 无法解析主机名，请检查服务器IP地址是否正确")
            elif "SSL" in error_msg or "certificate" in error_msg.lower():
                return ErrorResponse(msg="API连接失败: SSL证书错误，请检查HTTPS配置")
            return ErrorResponse(msg=f"API连接失败: {error_msg[:200]}")
        except Exception as e:
            node.status = 1
            node.error_msg = str(e)
            node.error_num += 1
            node.save(update_fields=["status", "error_msg", "error_num"])
            return ErrorResponse(msg=f"API连接失败: {str(e)[:200]}")

    def sync_node_status(self, request, reqData):
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                self._update_local_monitor(node)
            elif node.node_type == "ssh":
                self._update_ssh_monitor(node)
            else:
                self._update_api_monitor(node)
            return DetailResponse(data={"id": node.id}, msg="同步成功")
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def batch_sync_status(self, request):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        nodes = ClusterNode.objects.filter(is_local=False)
        success_count = 0
        fail_count = 0

        def sync_one(node):
            try:
                if node.node_type == "ssh":
                    self._update_ssh_monitor(node)
                else:
                    self._update_api_monitor(node)
                return True
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(sync_one, node): node for node in nodes}
            for future in as_completed(futures, timeout=30):
                if future.result():
                    success_count += 1
                else:
                    fail_count += 1

        local_node, _ = ClusterNode.objects.get_or_create(
            is_local=True,
            defaults={"name": "本机", "server_ip": "127.0.0.1", "status": 0}
        )
        self._update_local_monitor(local_node)
        return DetailResponse(data={"success": success_count, "fail": fail_count}, msg="批量同步完成")

    def _update_local_monitor(self, node):
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            if platform.system() == 'Windows':
                disk = psutil.disk_usage('C:\\')
            else:
                disk = psutil.disk_usage('/')
            boot_time = psutil.boot_time()
            uptime = int(datetime.now().timestamp() - boot_time)
            plat = platform.system()
            node.os_info = f"{plat} {platform.release()}"
            node.cpu_info = platform.processor()
            node.cpu_count = psutil.cpu_count()
            node.cpu_usage = cpu_usage
            node.mem_total = int(mem.total / (1024 * 1024))
            node.mem_used = int(mem.used / (1024 * 1024))
            node.mem_usage = round(mem.percent, 1)
            node.disk_total = int(disk.total / (1024 * 1024 * 1024))
            node.disk_used = int(disk.used / (1024 * 1024 * 1024))
            node.disk_usage = round(disk.percent, 1)
            node.uptime = uptime
            node.status = 0
            node.error_msg = ""
            node.last_monitor_time = timezone.now()
            node.save()
        except Exception as e:
            node.status = 2
            node.error_msg = str(e)
            node.save(update_fields=["status", "error_msg"])

    def _update_ssh_monitor(self, node):
        try:
            ssh_conf = json.loads(node.ssh_conf) if isinstance(node.ssh_conf, str) else node.ssh_conf
            host = node.server_ip
            port = ssh_conf.get("port", 22)
            username = ssh_conf.get("username", "root")
            password = ssh_conf.get("password", "")
            auth_type = ssh_conf.get("auth_type", "password")

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            connect_kwargs = {
                "hostname": host,
                "port": int(port),
                "username": username,
                "timeout": 10,
            }
            if auth_type == "password":
                connect_kwargs["password"] = password
            elif auth_type == "key":
                pkey = paramiko.RSAKey.from_private_key_string(ssh_conf.get("private_key", ""))
                connect_kwargs["pkey"] = pkey

            client.connect(**connect_kwargs)

            script = """
import json,psutil,platform
from datetime import datetime
cpu_usage=psutil.cpu_percent(interval=1)
mem=psutil.virtual_memory()
disk=psutil.disk_usage('/')
boot_time=psutil.boot_time()
uptime=int(datetime.now().timestamp()-boot_time)
print(json.dumps({
    "os_info":platform.system()+" "+platform.release(),
    "cpu_info":platform.processor(),
    "cpu_count":psutil.cpu_count(),
    "cpu_usage":cpu_usage,
    "mem_total":int(mem.total/(1024*1024)),
    "mem_used":int(mem.used/(1024*1024)),
    "mem_usage":round(mem.percent,1),
    "disk_total":int(disk.total/(1024*1024*1024)),
    "disk_used":int(disk.used/(1024*1024*1024)),
    "disk_usage":round(disk.percent,1),
    "uptime":uptime
}))
"""
            stdin, stdout, stderr = client.exec_command(f'python3 -c \"{script}\"', timeout=30)
            output = stdout.read().decode().strip()
            client.close()

            if output:
                data = json.loads(output)
                node.os_info = data.get("os_info", "")
                node.cpu_info = data.get("cpu_info", "")
                node.cpu_count = data.get("cpu_count", 0)
                node.cpu_usage = data.get("cpu_usage", 0)
                node.mem_total = data.get("mem_total", 0)
                node.mem_used = data.get("mem_used", 0)
                node.mem_usage = data.get("mem_usage", 0)
                node.disk_total = data.get("disk_total", 0)
                node.disk_used = data.get("disk_used", 0)
                node.disk_usage = data.get("disk_usage", 0)
                node.uptime = data.get("uptime", 0)
                node.status = 0
                node.error_msg = ""
                node.error_num = 0
            node.last_monitor_time = timezone.now()
            node.save()
        except Exception as e:
            node.status = 2
            node.error_msg = str(e)
            node.error_num += 1
            node.save(update_fields=["status", "error_msg", "error_num"])

    def _update_api_monitor(self, node):
        import requests
        try:
            url = f"{node.address.rstrip('/')}/api/sys/getSysMonitor/"
            headers = self._build_api_headers(node)
            resp = requests.get(url, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                data = result.get("data", {})

                cpu_data = data.get("cpu", [])
                if isinstance(cpu_data, list) and len(cpu_data) >= 4:
                    node.cpu_usage = round(float(cpu_data[0]), 1) if cpu_data[0] else 0
                    node.cpu_count = cpu_data[1] or 0
                    node.cpu_info = cpu_data[3] or ""

                mem_info = data.get("mem", {})
                if isinstance(mem_info, dict):
                    mem_total_gb = float(mem_info.get("total", 0))
                    mem_used_gb = float(mem_info.get("used", 0))
                    node.mem_total = int(mem_total_gb * 1024)
                    node.mem_used = int(mem_used_gb * 1024)
                    node.mem_usage = round(float(mem_info.get("percent", 0)), 1)

                sys_info = data.get("system", {})
                if isinstance(sys_info, dict):
                    node.os_info = sys_info.get("version", "") or data.get("system_simple", "")

                disk_info = data.get("disk", [])
                if isinstance(disk_info, list) and disk_info:
                    root_disk = None
                    for d in disk_info:
                        if isinstance(d, dict) and d.get("path") == "/":
                            root_disk = d
                            break
                    if not root_disk and disk_info:
                        root_disk = disk_info[0]
                    if isinstance(root_disk, dict):
                        size_list = root_disk.get("size", [])
                        if isinstance(size_list, list) and len(size_list) >= 4:
                            try:
                                node.disk_total = int(float(str(size_list[0]).replace("GB", "").replace("G", "").strip()))
                            except (ValueError, TypeError):
                                node.disk_total = 0
                            try:
                                node.disk_used = int(float(str(size_list[1]).replace("GB", "").replace("G", "").strip()))
                            except (ValueError, TypeError):
                                node.disk_used = 0
                            try:
                                node.disk_usage = round(float(size_list[3]), 1)
                            except (ValueError, TypeError):
                                node.disk_usage = 0

                node.status = 0
                node.error_msg = ""
                node.error_num = 0
            node.last_monitor_time = timezone.now()
            node.save()
        except Exception as e:
            node.status = 2
            node.error_msg = str(e)
            node.error_num += 1
            node.save(update_fields=["status", "error_msg", "error_num"])

    def get_local_info(self, request):
        local_node, created = ClusterNode.objects.get_or_create(
            is_local=True,
            defaults={"name": "本机", "server_ip": "127.0.0.1", "status": 0}
        )
        if created or local_node.status != 0:
            self._update_local_monitor(local_node)
        serializer = ClusterNodeSerializer(local_node)
        return DetailResponse(data=serializer.data, msg="获取成功")

    def restart_panel(self, request, reqData):
        """重启远程节点面板服务"""
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return ErrorResponse(msg="本机节点不支持远程重启面板")
            if node.node_type == "ssh":
                with RuyiSSHClient(node) as ssh:
                    if _is_windows():
                        ssh.exec_command('net stop RuyiPanel && net start RuyiPanel', timeout=10)
                    else:
                        ssh.exec_command('systemctl restart ruyi', timeout=10)
                return DetailResponse(msg="重启面板命令已发送")
            else:
                headers = build_api_headers(node)
                import requests
                resp = requests.post(
                    f"{node.address}/api/system/service/restart/",
                    headers=headers, json={"service": "panel"}, timeout=10
                )
                if resp.status_code == 200:
                    return DetailResponse(msg="重启面板命令已发送")
                return ErrorResponse(msg=f"重启面板失败: HTTP {resp.status_code}")
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")
        except Exception as e:
            return ErrorResponse(msg=f"操作失败: {str(e)}")

    def server_reboot(self, request, reqData):
        """重启远程服务器"""
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return ErrorResponse(msg="本机节点不支持远程重启服务器")
            if node.node_type == "ssh":
                with RuyiSSHClient(node) as ssh:
                    if _is_windows():
                        ssh.exec_command('shutdown /r /t 5', timeout=10)
                    else:
                        ssh.exec_command('shutdown -r +1 "Ruyi Panel: 服务器将在1分钟后重启"', timeout=10)
                return DetailResponse(msg="服务器重启命令已发送，预计1分钟后生效")
            else:
                headers = build_api_headers(node)
                import requests
                resp = requests.post(
                    f"{node.address}/api/system/service/restart/",
                    headers=headers, json={"service": "server"}, timeout=10
                )
                if resp.status_code == 200:
                    return DetailResponse(msg="服务器重启命令已发送")
                return ErrorResponse(msg=f"重启服务器失败: HTTP {resp.status_code}")
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")
        except Exception as e:
            return ErrorResponse(msg=f"操作失败: {str(e)}")

    def get_panel_url(self, request, reqData):
        """获取节点面板访问URL"""
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return DetailResponse(data={"url": f"http://127.0.0.1"}, msg="获取成功")
            if node.node_type == "ssh":
                address = f"http://{node.server_ip}"
            else:
                address = node.address or f"http://{node.server_ip}"
            return DetailResponse(data={"url": address}, msg="获取成功")
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def generate_sso_token(self, request, reqData):
        """生成免密跳转临时Token（5分钟有效）"""
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return ErrorResponse(msg="本机节点无需跳转")
            # 生成临时JWT Token
            from rest_framework_simplejwt.tokens import RefreshToken
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                return ErrorResponse(msg="未找到管理员用户")
            refresh = RefreshToken.for_user(admin_user)
            # 设置5分钟过期
            refresh.set_exp(lifetime=timedelta(minutes=5))
            access_token = str(refresh.access_token)

            if node.node_type == "ssh":
                base_url = f"http://{node.server_ip}"
            else:
                base_url = node.address or f"http://{node.server_ip}"

            # 拼接免密跳转URL
            sso_url = f"{base_url}/#/sso?token={access_token}"
            return DetailResponse(data={"url": sso_url, "token": access_token}, msg="获取成功")
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")
        except Exception as e:
            return ErrorResponse(msg=f"生成失败: {str(e)}")

    def get_node_sites(self, request, reqData):
        """查询远程节点的网站列表"""
        node_id = reqData.get("id")
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return ErrorResponse(msg="本机节点请直接访问网站管理")
            if node.node_type == "ssh":
                with RuyiSSHClient(node) as ssh:
                    stdout = ssh.exec_command(
                        "cat /www/sites/*/nginx.conf 2>/dev/null | grep server_name || ls /www/sites/ 2>/dev/null",
                        timeout=10
                    )
                    sites = [s.strip() for s in stdout.split('\n') if s.strip()]
                return DetailResponse(data={"sites": sites, "source": "ssh"}, msg="获取成功")
            else:
                headers = build_api_headers(node)
                import requests
                resp = requests.get(
                    f"{node.address}/api/system/site_manage/",
                    headers=headers, params={"limit": 100}, timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    sites = []
                    for item in data.get("data", {}).get("data", []):
                        sites.append({
                            "id": item.get("id"),
                            "name": item.get("name", ""),
                            "domains": item.get("domains", ""),
                            "status": item.get("status", ""),
                        })
                    return DetailResponse(data={"sites": sites, "source": "api"}, msg="获取成功")
                return ErrorResponse(msg=f"获取站点列表失败: HTTP {resp.status_code}")
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")
        except Exception as e:
            return ErrorResponse(msg=f"获取失败: {str(e)}")

    def test_ssh_conf(self, request, reqData):
        """独立测试SSH配置（不依赖已保存的节点）"""
        ssh_conf = reqData.get("ssh_conf", {})
        server_ip = reqData.get("server_ip", "")
        if not ssh_conf or not server_ip:
            return ErrorResponse(msg="缺少SSH配置或服务器IP")
        result = self._test_ssh_connection_for_add(ssh_conf, server_ip)
        if result.get("connected"):
            return DetailResponse(data=result, msg="SSH连接测试成功")
        return ErrorResponse(msg=f"SSH连接测试失败: {result.get('msg', '')}")
