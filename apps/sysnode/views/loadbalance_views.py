import os
import json
import shutil
import tempfile
import platform
from django.conf import settings
from rest_framework import serializers
from rest_framework.decorators import action
from utils.customView import CustomAPIView
from utils.viewset import CustomModelViewSet
from utils.serializers import CustomModelSerializer
from utils.jsonResponse import SuccessResponse, ErrorResponse, DetailResponse
from utils.common import get_parameter_dic, ReadFile, WriteFile
from rest_framework.permissions import IsAuthenticated
from apps.sysnode.models import UpstreamResource, UpstreamServer, LoadBalanceSite, ClusterNode
from apps.system.models import Sites
from apps.syslogs.logutil import RuyiAddOpLog
from utils.ruyiclass.nginxClass import NginxClient
from utils.ruyiclass.webClass import WebClient


def _is_windows():
    return platform.system().lower() == 'windows'


def _check_nginx_config_safe():
    """安全检查Nginx配置，返回True表示配置正确"""
    try:
        from utils.install.nginx import get_nginx_path_info, check_nginx_config
        nginx_info = get_nginx_path_info()
        nginx_conf = nginx_info.get('abspath_conf_path', '')
        if not nginx_conf:
            return True
        return check_nginx_config(conf_path=nginx_conf, is_windows=_is_windows())
    except Exception:
        return False


def _notify_lb_progress(message, progress, data=None):
    """通过Channel Layer推送负载均衡配置进度"""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            payload = {
                "type": "config_progress",
                "data": {
                    "message": message,
                    "progress": progress,
                }
            }
            if data:
                payload["data"].update(data)
            async_to_sync(channel_layer.group_send)("loadbalance", payload)
    except Exception:
        pass


def _get_upstream_base_path():
    vhost_path = settings.RUYI_VHOST_PATH.replace("\\", "/")
    upstream_path = os.path.join(vhost_path, "nginx", "upstream")
    if not os.path.exists(upstream_path):
        os.makedirs(upstream_path)
    return upstream_path


def _get_upstream_basestream_path():
    vhost_path = settings.RUYI_VHOST_PATH.replace("\\", "/")
    stream_path = os.path.join(vhost_path, "nginx", "stream")
    if not os.path.exists(stream_path):
        os.makedirs(stream_path)
    return stream_path


class UpstreamServerSerializer(CustomModelSerializer):
    class Meta:
        model = UpstreamServer
        fields = "__all__"
        read_only_fields = ["id"]


class UpstreamResourceSerializer(CustomModelSerializer):
    server_count = serializers.SerializerMethodField()
    servers = serializers.SerializerMethodField()

    class Meta:
        model = UpstreamResource
        fields = "__all__"
        read_only_fields = ["id"]

    def get_server_count(self, obj):
        return obj.servers.count()

    def get_servers(self, obj):
        servers = obj.servers.all().order_by('create_at')
        return UpstreamServerSerializer(servers, many=True).data


class UpstreamResourceDetailSerializer(CustomModelSerializer):
    servers = UpstreamServerSerializer(many=True, read_only=True)
    server_count = serializers.SerializerMethodField()

    class Meta:
        model = UpstreamResource
        fields = "__all__"
        read_only_fields = ["id"]

    def get_server_count(self, obj):
        return obj.servers.count()


class LoadBalanceSiteSerializer(CustomModelSerializer):
    site_name = serializers.SerializerMethodField()
    upstream_name = serializers.SerializerMethodField()

    class Meta:
        model = LoadBalanceSite
        fields = "__all__"
        read_only_fields = ["id"]

    def get_site_name(self, obj):
        return obj.site.name if obj.site else ""

    def get_upstream_name(self, obj):
        return obj.upstream.name if obj.upstream else ""


class LoadBalanceSiteDetailSerializer(CustomModelSerializer):
    site_name = serializers.SerializerMethodField()
    upstream_name = serializers.SerializerMethodField()
    servers = serializers.SerializerMethodField()

    class Meta:
        model = LoadBalanceSite
        fields = "__all__"
        read_only_fields = ["id"]

    def get_site_name(self, obj):
        return obj.site.name if obj.site else ""

    def get_upstream_name(self, obj):
        return obj.upstream.name if obj.upstream else ""

    def get_servers(self, obj):
        servers = UpstreamServer.objects.filter(resource=obj.upstream)
        return UpstreamServerSerializer(servers, many=True).data


class UpstreamResourceViewSet(CustomModelViewSet):
    queryset = UpstreamResource.objects.all().order_by('-create_at')
    serializer_class = UpstreamResourceSerializer
    list_serializer_class = UpstreamResourceSerializer
    retrieve_serializer_class = UpstreamResourceDetailSerializer
    search_fields = ('name',)
    filterset_fields = ('load_type', 'algorithm', 'status')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = UpstreamResourceDetailSerializer(instance)
        return DetailResponse(data=serializer.data, msg="获取成功")

    def create(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        name = reqData.get("name", "")
        if not name:
            return ErrorResponse(msg="资源名称不能为空")
        if UpstreamResource.objects.filter(name=name).exists():
            return ErrorResponse(msg="资源名称已存在")

        servers_data = reqData.pop("servers", [])
        if isinstance(servers_data, str):
            try:
                servers_data = json.loads(servers_data)
            except Exception:
                servers_data = []

        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        resource = UpstreamResource.objects.get(id=serializer.data.get("id"))
        for s in servers_data:
            UpstreamServer.objects.create(
                resource=resource,
                server=s.get("server", ""),
                weight=s.get("weight", 1),
                max_fails=s.get("max_fails", 2),
                fail_timeout=s.get("fail_timeout", "10s"),
                max_conns=s.get("max_conns", 0),
                flag=s.get("flag", ""),
                ps=s.get("ps", ""),
            )

        self._write_upstream_config(resource)
        _notify_lb_progress("正在验证Nginx配置...", 60)
        if not _check_nginx_config_safe():
            self._delete_upstream_config(resource)
            _notify_lb_progress("Nginx配置验证失败", 0, {"error": True})
            return ErrorResponse(msg="Nginx配置验证失败，请检查Upstream配置是否正确")
        _notify_lb_progress("正在重载Nginx...", 80)
        WebClient.reload_service(webserver='nginx')
        _notify_lb_progress("创建完成", 100)
        RuyiAddOpLog(request, msg=f"【Upstream资源】=>【创建】=>{name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="创建成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        reqData = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)

        servers_data = reqData.pop("servers", [])
        if isinstance(servers_data, str):
            try:
                servers_data = json.loads(servers_data)
            except Exception:
                servers_data = []

        serializer = self.get_serializer(instance, data=reqData, request=request, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if servers_data is not None:
            UpstreamServer.objects.filter(resource=instance).delete()
            for s in servers_data:
                UpstreamServer.objects.create(
                    resource=instance,
                    server=s.get("server", ""),
                    weight=s.get("weight", 1),
                    max_fails=s.get("max_fails", 2),
                    fail_timeout=s.get("fail_timeout", "10s"),
                    max_conns=s.get("max_conns", 0),
                    flag=s.get("flag", ""),
                    ps=s.get("ps", ""),
                )

        instance = UpstreamResource.objects.get(id=instance.id)
        # 备份配置再写入
        backup_dir = self._backup_upstream_configs(instance)
        self._write_upstream_config(instance)
        if not _check_nginx_config_safe():
            self._restore_upstream_configs(backup_dir)
            return ErrorResponse(msg="Nginx配置验证失败，已自动回滚配置")
        WebClient.reload_service(webserver='nginx')
        RuyiAddOpLog(request, msg=f"【Upstream资源】=>【修改】=>{instance.name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="更新成功")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            name = ins.name
            self._delete_upstream_config(ins)
            UpstreamServer.objects.filter(resource=ins).delete()
            LoadBalanceSite.objects.filter(upstream=ins).delete()
            ins.delete()
            RuyiAddOpLog(request, msg=f"【Upstream资源】=>【删除】=>{name}", module="nodemg")
        if not _check_nginx_config_safe():
            return DetailResponse(data=[], msg="删除成功，但Nginx配置验证失败，请手动检查")
        WebClient.reload_service(webserver='nginx')
        return DetailResponse(data=[], msg="删除成功")

    @action(methods=['POST'], detail=False)
    def batch_delete(self, request, *args, **kwargs):
        """批量删除Upstream资源"""
        reqData = get_parameter_dic(request)
        ids = reqData.get("ids", [])
        if not ids:
            return ErrorResponse(msg="请选择要删除的资源")
        if isinstance(ids, str):
            try:
                ids = json.loads(ids)
            except Exception:
                ids = [ids]
        try:
            resources = UpstreamResource.objects.filter(id__in=ids)
            deleted_count = 0
            for ins in resources:
                self._delete_upstream_config(ins)
                UpstreamServer.objects.filter(resource=ins).delete()
                LoadBalanceSite.objects.filter(upstream=ins).delete()
                ins.delete()
                deleted_count += 1
                RuyiAddOpLog(request, msg=f"【Upstream资源】=>【批量删除】=>{ins.name}", module="nodemg")
            if deleted_count == 0:
                return ErrorResponse(msg="未找到要删除的资源")
            if not _check_nginx_config_safe():
                return DetailResponse(data=[], msg="批量删除完成，但Nginx配置验证失败，请手动检查")
            WebClient.reload_service(webserver='nginx')
            return DetailResponse(data=[], msg=f"批量删除成功，共删除{deleted_count}个资源")
        except Exception as e:
            return ErrorResponse(msg=f"批量删除失败: {str(e)}")

    def _backup_upstream_configs(self, resource):
        """备份受影响的配置文件"""
        backup_dir = tempfile.mkdtemp(prefix='ruyi_lb_backup_')
        base_path = _get_upstream_base_path()
        config_name = resource.name.replace(' ', '_').replace('.', '_')
        # 备份upstream conf
        conf_file = os.path.join(base_path, f"{config_name}.conf")
        if os.path.exists(conf_file):
            shutil.copy2(conf_file, os.path.join(backup_dir, f"{config_name}.conf"))
        # 备份stream conf
        stream_base_path = _get_upstream_basestream_path()
        stream_conf = os.path.join(stream_base_path, "stream.conf")
        if os.path.exists(stream_conf):
            shutil.copy2(stream_conf, os.path.join(backup_dir, "stream.conf"))
        # 备份nginx.conf
        try:
            from utils.install.nginx import get_nginx_path_info
            nginx_info = get_nginx_path_info()
            nginx_conf_path = nginx_info.get('abspath_conf_path', '')
            if nginx_conf_path and os.path.exists(nginx_conf_path):
                shutil.copy2(nginx_conf_path, os.path.join(backup_dir, "nginx.conf"))
        except Exception:
            pass
        return backup_dir

    def _restore_upstream_configs(self, backup_dir):
        """从备份恢复配置文件"""
        if not backup_dir or not os.path.exists(backup_dir):
            return
        base_path = _get_upstream_base_path()
        stream_base_path = _get_upstream_basestream_path()
        for fname in os.listdir(backup_dir):
            src = os.path.join(backup_dir, fname)
            if fname == "nginx.conf":
                try:
                    from utils.install.nginx import get_nginx_path_info
                    nginx_info = get_nginx_path_info()
                    nginx_conf_path = nginx_info.get('abspath_conf_path', '')
                    if nginx_conf_path:
                        shutil.copy2(src, nginx_conf_path)
                except Exception:
                    pass
            elif fname == "stream.conf":
                shutil.copy2(src, os.path.join(stream_base_path, "stream.conf"))
            elif fname.endswith(".conf"):
                shutil.copy2(src, os.path.join(base_path, fname))
        try:
            shutil.rmtree(backup_dir)
        except Exception:
            pass

    def _build_upstream_block(self, resource):
        upstream_name = resource.name.replace(' ', '_').replace('.', '_')
        lines = [f"upstream {upstream_name} {{"]
        if resource.algorithm == "ip_hash":
            lines.append("    ip_hash;")
        elif resource.algorithm == "least_conn":
            lines.append("    least_conn;")
        if resource.keepalive > 0 and resource.load_type == "http":
            lines.append(f"    keepalive {resource.keepalive};")
        servers = UpstreamServer.objects.filter(resource=resource)
        for s in servers:
            if s.flag == "down":
                lines.append(f"    server {s.server} down;")
                continue
            params = []
            if s.weight != 1:
                params.append(f"weight={s.weight}")
            if s.max_fails != 2:
                params.append(f"max_fails={s.max_fails}")
            if s.fail_timeout != "10s":
                params.append(f"fail_timeout={s.fail_timeout}")
            if s.max_conns > 0:
                params.append(f"max_conns={s.max_conns}")
            if s.flag == "backup":
                params.append("backup")
            param_str = " ".join(params)
            if param_str:
                lines.append(f"    server {s.server} {param_str};")
            else:
                lines.append(f"    server {s.server};")
        lines.append("}")
        return "\n".join(lines)

    def _build_stream_upstream_block(self, resource):
        """生成stream类型的upstream块（不含stream{}外层包裹）"""
        upstream_name = resource.name.replace(' ', '_').replace('.', '_')
        lines = [f"upstream {upstream_name} {{"]
        if resource.algorithm == "least_conn":
            lines.append("    least_conn;")
        servers = UpstreamServer.objects.filter(resource=resource)
        for s in servers:
            if s.flag == "down":
                lines.append(f"    server {s.server} down;")
                continue
            params = []
            if s.weight != 1:
                params.append(f"weight={s.weight}")
            if s.flag == "backup":
                params.append("backup")
            param_str = " ".join(params)
            if param_str:
                lines.append(f"    server {s.server} {param_str};")
            else:
                lines.append(f"    server {s.server};")
        lines.append("}")
        return "\n".join(lines)

    def _rebuild_stream_config(self):
        """重新生成完整的stream配置文件，合并所有stream类型的upstream"""
        base_path = _get_upstream_basestream_path()
        stream_resources = UpstreamResource.objects.filter(load_type__in=["tcp", "udp"], status=True)
        if not stream_resources.exists():
            config_path = os.path.join(base_path, "stream.conf")
            if os.path.exists(config_path):
                os.remove(config_path)
            return
        lines = ["stream {"]
        for resource in stream_resources:
            lines.append(f"    {self._build_stream_upstream_block(resource)}".replace("\n", "\n    "))
        lines.append("}")
        config_content = "\n".join(lines)
        config_path = os.path.join(base_path, "stream.conf")
        WriteFile(config_path, config_content + "\n")

    def _write_upstream_config(self, resource):
        self._notify_lb_progress("正在生成Upstream配置...", 20)
        base_path = _get_upstream_base_path()
        config_name = resource.name.replace(' ', '_').replace('.', '_')
        if resource.load_type == "http":
            config_content = self._build_upstream_block(resource)
            config_path = os.path.join(base_path, f"{config_name}.conf")
            WriteFile(config_path, config_content + "\n")
        else:
            # stream类型：删除旧的独立conf文件，重新生成合并的stream配置
            old_conf = os.path.join(base_path, f"{config_name}_stream.conf")
            if os.path.exists(old_conf):
                os.remove(old_conf)
            self._rebuild_stream_config()
            self._ensure_nginx_include_stream()
        self._ensure_nginx_include_upstream()
        # 确保缓存区域定义存在（如果有启用缓存的lb_site）
        self._ensure_nginx_cache_zone()

    def _delete_upstream_config(self, resource):
        base_path = _get_upstream_base_path()
        config_name = resource.name.replace(' ', '_').replace('.', '_')
        # 删除http类型的conf文件
        conf_file = os.path.join(base_path, f"{config_name}.conf")
        if os.path.exists(conf_file):
            os.remove(conf_file)
        # 删除旧的stream独立conf文件（兼容旧数据）
        stream_conf = os.path.join(base_path, f"{config_name}_stream.conf")
        if os.path.exists(stream_conf):
            os.remove(stream_conf)
        # stream类型需要重新生成合并配置
        if resource.load_type != "http":
            self._rebuild_stream_config()

    def _ensure_nginx_include_upstream(self):
        from utils.install.nginx import get_nginx_path_info
        nginx_info = get_nginx_path_info()
        nginx_conf_path = nginx_info.get('abspath_conf_path', '')
        if not nginx_conf_path or not os.path.exists(nginx_conf_path):
            return
        base_path = _get_upstream_base_path()
        upstream_include = f"include {base_path}/*.conf;"
        content = ReadFile(nginx_conf_path)
        if not content:
            return
        if upstream_include in content:
            return
        import re
        vhost_pattern = r'(include\s+[^\n]*vhost[^\n]*;)'
        match = re.search(vhost_pattern, content)
        if match:
            content = content.replace(
                match.group(1),
                f"{upstream_include}\n    {match.group(1)}"
            )
            WriteFile(nginx_conf_path, content)

    def _ensure_nginx_include_stream(self):
        """确保nginx.conf中包含stream配置文件的include指令"""
        from utils.install.nginx import get_nginx_path_info
        nginx_info = get_nginx_path_info()
        nginx_conf_path = nginx_info.get('abspath_conf_path', '')
        if not nginx_conf_path or not os.path.exists(nginx_conf_path):
            return
        stream_base_path = _get_upstream_basestream_path()
        stream_include = f"include {stream_base_path}/stream.conf;"
        content = ReadFile(nginx_conf_path)
        if not content:
            return
        if stream_include in content:
            return
        # stream.conf自带stream{}包裹，include放在nginx.conf末尾（主上下文，与http{}同级）
        content = content.rstrip() + "\n\n" + stream_include + "\n"
        WriteFile(nginx_conf_path, content)

    def _ensure_nginx_cache_zone(self):
        """确保Nginx主配置中定义了负载均衡缓存区域"""
        has_cache_enabled = LoadBalanceSite.objects.filter(enable_cache=True, status=True).exists()
        if not has_cache_enabled:
            return
        from utils.install.nginx import get_nginx_path_info
        nginx_info = get_nginx_path_info()
        nginx_conf_path = nginx_info.get('abspath_conf_path', '')
        if not nginx_conf_path or not os.path.exists(nginx_conf_path):
            return
        content = ReadFile(nginx_conf_path)
        if not content:
            return
        if 'proxy_cache_path' in content and 'cache_one' in content:
            return  # 已定义
        # 确定缓存目录（跨平台）
        if _is_windows():
            cache_path = os.path.join(tempfile.gettempdir(), 'nginx_lb_cache').replace("\\", "/")
        else:
            cache_path = '/tmp/nginx_lb_cache'
        # 确保缓存目录存在
        if not os.path.exists(cache_path):
            try:
                os.makedirs(cache_path, exist_ok=True)
            except Exception:
                pass
        cache_conf = (
            "\n    # RUYI-LB-CACHE-START\n"
            f"    proxy_cache_path {cache_path} levels=1:2 keys_zone=cache_one:10m max_size=1g inactive=60m use_temp_path=off;\n"
            "    # RUYI-LB-CACHE-END\n"
        )
        import re
        # 在 http { 块内添加缓存区域定义
        content = re.sub(
            r'(http\s*\{)',
            r'\1' + cache_conf,
            content,
            count=1
        )
        WriteFile(nginx_conf_path, content)


class LoadBalanceSiteViewSet(CustomModelViewSet):
    queryset = LoadBalanceSite.objects.all().order_by('-create_at')
    serializer_class = LoadBalanceSiteSerializer
    list_serializer_class = LoadBalanceSiteSerializer
    retrieve_serializer_class = LoadBalanceSiteDetailSerializer
    search_fields = ('site__name', 'upstream__name')
    filterset_fields = ('site', 'upstream', 'status')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = LoadBalanceSiteDetailSerializer(instance)
        return DetailResponse(data=serializer.data, msg="获取成功")

    def create(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        site_id = reqData.get("site")
        upstream_id = reqData.get("upstream")
        if not site_id:
            return ErrorResponse(msg="请选择关联站点")
        if not upstream_id:
            return ErrorResponse(msg="请选择Upstream资源")

        try:
            site = Sites.objects.get(id=site_id)
        except Sites.DoesNotExist:
            return ErrorResponse(msg="站点不存在")
        try:
            upstream = UpstreamResource.objects.get(id=upstream_id)
        except UpstreamResource.DoesNotExist:
            return ErrorResponse(msg="Upstream资源不存在")

        serializer = self.get_serializer(data=reqData, request=request)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        lb_site = LoadBalanceSite.objects.get(id=serializer.data.get("id"))
        self._write_lb_proxy_config(lb_site)
        if not _check_nginx_config_safe():
            self._delete_lb_proxy_config(lb_site)
            lb_site.delete()
            return ErrorResponse(msg="Nginx配置验证失败，请检查站点代理配置是否正确")
        WebClient.reload_service(webserver='nginx')
        RuyiAddOpLog(request, msg=f"【负载均衡站点】=>【创建】=>{site.name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="创建成功")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, request=request, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        instance = LoadBalanceSite.objects.get(id=instance.id)
        # 备份配置再写入
        backup_dir = self._backup_lb_configs(instance)
        self._write_lb_proxy_config(instance)
        if not _check_nginx_config_safe():
            self._restore_lb_configs(backup_dir)
            return ErrorResponse(msg="Nginx配置验证失败，已自动回滚配置")
        WebClient.reload_service(webserver='nginx')
        RuyiAddOpLog(request, msg=f"【负载均衡站点】=>【修改】=>{instance.site.name}", module="nodemg")
        return DetailResponse(data=serializer.data, msg="更新成功")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            self._delete_lb_proxy_config(ins)
            ins.delete()
        if not _check_nginx_config_safe():
            return DetailResponse(data=[], msg="删除成功，但Nginx配置验证失败，请手动检查")
        WebClient.reload_service(webserver='nginx')
        RuyiAddOpLog(request, msg=f"【负载均衡站点】=>【删除】", module="nodemg")
        return DetailResponse(data=[], msg="删除成功")

    def _backup_lb_configs(self, lb_site):
        """备份负载均衡站点相关配置文件"""
        backup_dir = tempfile.mkdtemp(prefix='ruyi_lb_site_backup_')
        try:
            ng = NginxClient(siteName=lb_site.site.name)
            # 备份站点配置
            if os.path.exists(ng.confPath):
                shutil.copy2(ng.confPath, os.path.join(backup_dir, "site.conf"))
            # 备份proxy配置
            proxy_dir = ng.proxyBasePath
            config_name = f"lb_{lb_site.upstream.name.replace(' ', '_')}_{lb_site.site.name}"
            proxy_conf = os.path.join(proxy_dir, f"{config_name}.conf")
            if os.path.exists(proxy_conf):
                shutil.copy2(proxy_conf, os.path.join(backup_dir, "proxy.conf"))
        except Exception:
            pass
        return backup_dir

    def _restore_lb_configs(self, backup_dir):
        """从备份恢复负载均衡站点配置"""
        if not backup_dir or not os.path.exists(backup_dir):
            return
        try:
            for fname in os.listdir(backup_dir):
                src = os.path.join(backup_dir, fname)
                if fname == "site.conf":
                    # 需要知道站点名才能恢复，从备份文件内容推断
                    pass
                elif fname == "proxy.conf":
                    # proxy.conf恢复需要知道目标路径，暂时跳过
                    pass
            # 简单恢复：重新读取备份的site.conf写回
            site_conf_backup = os.path.join(backup_dir, "site.conf")
            if os.path.exists(site_conf_backup):
                # 查找当前所有站点配置，用备份内容覆盖
                content = ReadFile(site_conf_backup)
                if content:
                    # 尝试从备份内容中找到站点名（通过server_name行）
                    import re
                    match = re.search(r'server_name\s+(\S+);', content)
                    if match:
                        site_name = match.group(1)
                        try:
                            ng = NginxClient(siteName=site_name)
                            WriteFile(ng.confPath, content)
                        except Exception:
                            pass
        except Exception:
            pass
        try:
            shutil.rmtree(backup_dir)
        except Exception:
            pass

    def _build_location_block(self, lb_site):
        upstream_name = lb_site.upstream.name.replace(' ', '_').replace('.', '_')
        match_map = {
            "prefix": "",
            "exact": "= ",
            "regex_case": "~ ",
            "regex_nocase": "~* ",
        }
        match_prefix = match_map.get(lb_site.location_match, "")
        path = lb_site.location_path if lb_site.location_path else "/"

        lines = [f"    location {match_prefix}{path} {{"]
        lines.append(f"        proxy_pass http://{upstream_name};")
        lines.append(f"        proxy_set_header Host {lb_site.proxy_host};")
        lines.append("        proxy_set_header X-Real-IP $remote_addr;")
        lines.append("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
        lines.append("        proxy_set_header X-Forwarded-Proto $scheme;")

        if lb_site.upstream.proxy_connect_timeout:
            lines.append(f"        proxy_connect_timeout {lb_site.upstream.proxy_connect_timeout};")
        if lb_site.upstream.proxy_read_timeout:
            lines.append(f"        proxy_read_timeout {lb_site.upstream.proxy_read_timeout};")
        if lb_site.upstream.proxy_send_timeout:
            lines.append(f"        proxy_send_timeout {lb_site.upstream.proxy_send_timeout};")
        if lb_site.upstream.proxy_next_upstream:
            lines.append(f"        proxy_next_upstream {lb_site.upstream.proxy_next_upstream};")

        if lb_site.enable_websocket:
            lines.append("        proxy_http_version 1.1;")
            lines.append("        proxy_set_header Upgrade $http_upgrade;")
            lines.append("        proxy_set_header Connection $proxy_connection;")
            lines.append("        proxy_read_timeout 3600s;")
            lines.append("        proxy_send_timeout 3600s;")

        if lb_site.enable_cache:
            suffixes = lb_site.cache_suffix.replace(",", "|")
            lines.append(f"        location ~ .*\\.({suffixes})$ {{")
            lines.append(f"            proxy_cache_valid 200 304 {lb_site.cache_time};")
            lines.append("            proxy_cache cache_one;")
            lines.append("            proxy_cache_key $host$uri$is_args$args;")
            lines.append("            add_header Nginx-Cache $upstream_cache_status;")
            lines.append("        }}")

        if lb_site.custom_conf:
            for line in lb_site.custom_conf.strip().split("\n"):
                lines.append(f"        {line.strip()}")

        lines.append("    }")
        return "\n".join(lines)

    def _write_lb_proxy_config(self, lb_site):
        ng = NginxClient(siteName=lb_site.site.name)
        proxy_dir = ng.proxyBasePath
        if not os.path.exists(proxy_dir):
            os.makedirs(proxy_dir)
        config_name = f"lb_{lb_site.upstream.name.replace(' ', '_')}_{lb_site.site.name}"
        config_path = os.path.join(proxy_dir, f"{config_name}.conf")
        location_block = self._build_location_block(lb_site)
        config_content = f"#RUYI-LB-PROXY-START\n{location_block}\n#RUYI-LB-PROXY-END\n"
        WriteFile(config_path, config_content)
        site_conf = ReadFile(ng.confPath)
        if site_conf and f"include {proxy_dir}/{config_name}.conf" not in site_conf:
            import re
            replace_line = ng.replaceLine1Key
            if replace_line in site_conf:
                site_conf = site_conf.replace(
                    replace_line,
                    f"include {proxy_dir}/{config_name}.conf;\n    {replace_line}"
                )
                WriteFile(ng.confPath, site_conf)

    def _delete_lb_proxy_config(self, lb_site):
        ng = NginxClient(siteName=lb_site.site.name)
        proxy_dir = ng.proxyBasePath
        config_name = f"lb_{lb_site.upstream.name.replace(' ', '_')}_{lb_site.site.name}"
        config_path = os.path.join(proxy_dir, f"{config_name}.conf")
        if os.path.exists(config_path):
            os.remove(config_path)
        site_conf = ReadFile(ng.confPath)
        if site_conf:
            include_line = f"include {proxy_dir}/{config_name}.conf;"
            site_conf = site_conf.replace(include_line + "\n", "").replace(include_line, "")
            WriteFile(ng.confPath, site_conf)


class LoadBalanceManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        if action == "preview_config":
            return self.preview_config(request, reqData)
        elif action == "get_sites":
            return self.get_sites(request)
        elif action == "get_nodes":
            return self.get_nodes(request)
        elif action == "test_upstream":
            return self.test_upstream(request, reqData)
        return ErrorResponse(msg="无效的操作")

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        if action == "toggle_upstream_status":
            return self.toggle_upstream_status(request, reqData)
        elif action == "toggle_lb_site_status":
            return self.toggle_lb_site_status(request, reqData)
        elif action == "reload_nginx":
            return self.reload_nginx(request)
        elif action == "analyze_log":
            return self.analyze_log(request, reqData)
        return ErrorResponse(msg="无效的操作")

    def preview_config(self, request, reqData):
        upstream_id = reqData.get("upstream_id")
        if not upstream_id:
            return ErrorResponse(msg="缺少资源ID")
        try:
            resource = UpstreamResource.objects.get(id=upstream_id)
            viewset = UpstreamResourceViewSet()
            if resource.load_type == "http":
                config = viewset._build_upstream_block(resource)
            else:
                config = viewset._build_stream_upstream_block(resource)
            lb_sites = LoadBalanceSite.objects.filter(upstream=resource)
            lb_configs = []
            for lb_site in lb_sites:
                lb_viewset = LoadBalanceSiteViewSet()
                lb_configs.append({
                    "site_name": lb_site.site.name,
                    "location": lb_viewset._build_location_block(lb_site)
                })
            return DetailResponse(data={
                "upstream_config": config,
                "lb_configs": lb_configs
            }, msg="获取成功")
        except UpstreamResource.DoesNotExist:
            return ErrorResponse(msg="资源不存在")

    def toggle_upstream_status(self, request, reqData):
        upstream_id = reqData.get("id")
        if not upstream_id:
            return ErrorResponse(msg="缺少资源ID")
        try:
            resource = UpstreamResource.objects.get(id=upstream_id)
            resource.status = not resource.status
            resource.save(update_fields=["status"])
            viewset = UpstreamResourceViewSet()
            if resource.status:
                viewset._write_upstream_config(resource)
            else:
                viewset._delete_upstream_config(resource)
            WebClient.reload_service(webserver='nginx')
            status_text = "启用" if resource.status else "停用"
            RuyiAddOpLog(request, msg=f"【Upstream资源】=>【{status_text}】=>{resource.name}", module="nodemg")
            return DetailResponse(data={"status": resource.status}, msg=f"已{status_text}")
        except UpstreamResource.DoesNotExist:
            return ErrorResponse(msg="资源不存在")

    def toggle_lb_site_status(self, request, reqData):
        lb_id = reqData.get("id")
        if not lb_id:
            return ErrorResponse(msg="缺少负载均衡站点ID")
        try:
            lb_site = LoadBalanceSite.objects.get(id=lb_id)
            lb_site.status = not lb_site.status
            lb_site.save(update_fields=["status"])
            viewset = LoadBalanceSiteViewSet()
            if lb_site.status:
                viewset._write_lb_proxy_config(lb_site)
            else:
                viewset._delete_lb_proxy_config(lb_site)
            WebClient.reload_service(webserver='nginx')
            status_text = "启用" if lb_site.status else "停用"
            RuyiAddOpLog(request, msg=f"【负载均衡站点】=>【{status_text}】=>{lb_site.site.name}", module="nodemg")
            return DetailResponse(data={"status": lb_site.status}, msg=f"已{status_text}")
        except LoadBalanceSite.DoesNotExist:
            return ErrorResponse(msg="负载均衡站点不存在")

    def get_sites(self, request):
        sites = Sites.objects.filter(status=True).values("id", "name")
        return DetailResponse(data=list(sites), msg="获取成功")

    def get_nodes(self, request):
        nodes = ClusterNode.objects.filter(status=0).values("id", "name", "server_ip")
        return DetailResponse(data=list(nodes), msg="获取成功")

    def reload_nginx(self, request):
        WebClient.reload_service(webserver='nginx')
        return DetailResponse(data={}, msg="Nginx已重载")

    def analyze_log(self, request, reqData):
        """负载均衡日志分析"""
        from apps.sysnode.load_log_analyze import analyze_access_log, analyze_error_log
        log_type = reqData.get("log_type", "access")
        minutes = int(reqData.get("minutes", 30))
        site_name = reqData.get("site_name", "")
        if log_type == "error":
            data = analyze_error_log(lines=100)
        else:
            data = analyze_access_log(minutes=minutes, site_name=site_name)
        if "error" in data:
            return ErrorResponse(msg=data["error"])
        return DetailResponse(data=data, msg="分析完成")

    def test_upstream(self, request, reqData):
        upstream_id = reqData.get("upstream_id")
        if not upstream_id:
            return ErrorResponse(msg="缺少资源ID")
        try:
            resource = UpstreamResource.objects.get(id=upstream_id)
            servers = UpstreamServer.objects.filter(resource=resource)
            results = []
            import socket
            import time
            for s in servers:
                host_port = s.server.split(":")
                host = host_port[0] if len(host_port) >= 1 else ""
                port = int(host_port[1]) if len(host_port) >= 2 else 80
                start_time = time.time()
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    result = sock.connect_ex((host, port))
                    elapsed = round((time.time() - start_time) * 1000, 1)
                    sock.close()
                    item = {
                        "server": s.server,
                        "reachable": result == 0,
                        "latency_ms": elapsed if result == 0 else None,
                        "flag": s.flag,
                    }
                    # HTTP类型增加HTTP请求检测
                    if resource.load_type == "http" and result == 0:
                        try:
                            import requests as req_lib
                            url = f"http://{host}:{port}/"
                            resp = req_lib.get(url, timeout=5, allow_redirects=False, verify=False)
                            item["http_status"] = resp.status_code
                            item["http_reachable"] = resp.status_code < 500
                        except Exception as e:
                            item["http_reachable"] = False
                            item["http_error"] = str(e)[:100]
                    results.append(item)
                except socket.timeout:
                    elapsed = round((time.time() - start_time) * 1000, 1)
                    results.append({
                        "server": s.server,
                        "reachable": False,
                        "latency_ms": elapsed,
                        "error": "连接超时",
                        "flag": s.flag,
                    })
                except Exception as e:
                    results.append({
                        "server": s.server,
                        "reachable": False,
                        "error": str(e),
                        "flag": s.flag,
                    })
            return DetailResponse(data=results, msg="检测完成")
        except UpstreamResource.DoesNotExist:
            return ErrorResponse(msg="资源不存在")
