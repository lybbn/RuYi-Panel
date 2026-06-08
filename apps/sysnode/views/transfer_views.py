import os
import json
import time
import platform
import shlex
import requests
from math import ceil
from django.utils import timezone
from rest_framework import serializers
from utils.customView import CustomAPIView
from utils.viewset import CustomModelViewSet
from utils.serializers import CustomModelSerializer
from utils.jsonResponse import SuccessResponse, ErrorResponse, DetailResponse
from utils.common import get_parameter_dic, GetWebRootPath
from rest_framework.permissions import IsAuthenticated
from apps.sysnode.models import FileTransferTask, FileTransferRecord, ClusterNode
from apps.syslogs.logutil import RuyiAddOpLog
from utils.security.files import list_files_in_directory, get_directory_size, delete_file, delete_dir, create_dir
from utils.ssh_client import RuyiSSHClient, build_api_headers

try:
    import psutil
except ImportError:
    psutil = None


def _run_file_transfer(task_id):
    """模块级函数，供APScheduler序列化引用"""
    from apps.sysnode.transfer_executor import TransferExecutor
    executor = TransferExecutor(task_id)
    executor.execute()


class FileTransferRecordSerializer(CustomModelSerializer):
    class Meta:
        model = FileTransferRecord
        fields = "__all__"
        read_only_fields = ["id"]


class FileTransferTaskSerializer(CustomModelSerializer):
    source_node_name = serializers.SerializerMethodField()
    target_node_name = serializers.SerializerMethodField()

    class Meta:
        model = FileTransferTask
        fields = "__all__"
        read_only_fields = ["id"]

    def get_source_node_name(self, obj):
        return obj.source_node.name if obj.source_node else ""

    def get_target_node_name(self, obj):
        return obj.target_node.name if obj.target_node else ""


class FileTransferTaskDetailSerializer(CustomModelSerializer):
    source_node_name = serializers.SerializerMethodField()
    target_node_name = serializers.SerializerMethodField()
    records = FileTransferRecordSerializer(many=True, read_only=True)

    class Meta:
        model = FileTransferTask
        fields = "__all__"
        read_only_fields = ["id"]

    def get_source_node_name(self, obj):
        return obj.source_node.name if obj.source_node else ""

    def get_target_node_name(self, obj):
        return obj.target_node.name if obj.target_node else ""


class FileTransferTaskViewSet(CustomModelViewSet):
    queryset = FileTransferTask.objects.all().order_by('-create_at')
    serializer_class = FileTransferTaskSerializer
    list_serializer_class = FileTransferTaskSerializer
    retrieve_serializer_class = FileTransferTaskDetailSerializer
    search_fields = ('source_path_list', 'target_path')
    filterset_fields = ('status', 'task_action', 'source_node', 'target_node')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = FileTransferTaskDetailSerializer(instance)
        return DetailResponse(data=serializer.data, msg="获取成功")

    def create(self, request, *args, **kwargs):
        reqData = get_parameter_dic(request)
        source_node_id = reqData.get("source_node")
        target_node_id = reqData.get("target_node")
        source_path_list = reqData.get("source_path_list", "[]")
        target_path = reqData.get("target_path", "")
        task_action = reqData.get("task_action", "upload")
        default_mode = reqData.get("default_mode", "cover")

        if not source_node_id or not target_node_id:
            return ErrorResponse(msg="请选择源节点和目标节点")
        if not target_path:
            return ErrorResponse(msg="请填写目标路径")

        if isinstance(source_path_list, str):
            try:
                source_path_list = json.loads(source_path_list)
            except Exception:
                return ErrorResponse(msg="源文件路径格式错误")
        if not source_path_list:
            return ErrorResponse(msg="请选择要传输的文件")

        running_task = FileTransferTask.objects.filter(status__in=["pending", "running"]).first()
        if running_task:
            return ErrorResponse(msg="当前存在正在执行的任务，请等待完成后再提交")

        try:
            source_node = ClusterNode.objects.get(id=source_node_id)
            target_node = ClusterNode.objects.get(id=target_node_id)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

        task = FileTransferTask(
            source_node=source_node,
            target_node=target_node,
            task_action=task_action,
            status="pending",
            source_path_list=json.dumps(source_path_list) if isinstance(source_path_list, list) else source_path_list,
            target_path=target_path,
            default_mode=default_mode,
            total_files=len(source_path_list),
            created_by=request.user.username if request.user else "",
        )
        task.save()

        for src_file in source_path_list:
            FileTransferRecord.objects.create(
                task=task,
                src_file=src_file,
                dst_file=os.path.join(target_path, os.path.basename(src_file.rstrip("/"))),
                is_dir=src_file.endswith("/"),
                status="pending",
            )

        RuyiAddOpLog(request, msg=f"【文件互传】=>【创建任务】=>{source_node.name} -> {target_node.name}", module="nodemg")
        return DetailResponse(data={"id": task.id}, msg="任务创建成功")

    def destroy(self, request, *args, **kwargs):
        instance_list = self.get_object_list()
        for ins in instance_list:
            if ins.status == "running":
                ins.status = "cancelled"
                ins.save(update_fields=["status"])
                FileTransferRecord.objects.filter(task=ins, status__in=["pending", "transferring"]).update(status="skipped")
            FileTransferRecord.objects.filter(task=ins).delete()
            ins.delete()
            RuyiAddOpLog(request, msg=f"【文件互传】=>【删除任务】=>{ins.id}", module="nodemg")
        return DetailResponse(data=[], msg="删除成功")


class FileTransferManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        if action == "get_nodes":
            return self.get_nodes(request)
        elif action == "get_node_files":
            return self.get_node_files(request, reqData)
        elif action == "get_task_progress":
            return self.get_task_progress(request, reqData)
        elif action == "get_detail":
            return self.get_detail(request, reqData)
        elif action == "calc_size":
            return self.calc_size(request, reqData)
        return ErrorResponse(msg="无效的操作")

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")
        if action == "start_transfer":
            return self.start_transfer(request, reqData)
        elif action == "cancel_transfer":
            return self.cancel_transfer(request, reqData)
        elif action == "retry_transfer":
            return self.retry_transfer(request, reqData)
        elif action == "delete_file":
            return self.delete_file(request, reqData)
        elif action == "create_dir":
            return self.create_dir(request, reqData)
        elif action == "batch_transfer":
            return self.batch_transfer(request, reqData)
        elif action == "upload_remote_file":
            return self.upload_remote_file(request, reqData)
        return ErrorResponse(msg="无效的操作")

    def get_nodes(self, request):
        local_node, created = ClusterNode.objects.get_or_create(
            is_local=True,
            defaults={"name": "本机", "server_ip": "127.0.0.1", "status": 0}
        )
        if created:
            self._init_local_monitor(local_node)
        elif local_node.status != 0:
            try:
                self._init_local_monitor(local_node)
            except Exception:
                pass
        nodes = ClusterNode.objects.all().values("id", "name", "server_ip", "is_local", "status")
        return DetailResponse(data=list(nodes), msg="获取成功")

    def _init_local_monitor(self, node):
        if psutil is None:
            return
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            if platform.system() == 'Windows':
                disk = psutil.disk_usage('C:\\')
            else:
                disk = psutil.disk_usage('/')
            boot_time = psutil.boot_time()
            from datetime import datetime
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

    def get_node_files(self, request, reqData):
        node_id = reqData.get("node_id")
        path = reqData.get("path", "/")
        page = int(reqData.get("page", 1))
        limit = int(reqData.get("limit", 100))
        # 一次最大条数限制
        limit = 3000 if limit > 3000 else limit
        if not node_id:
            return ErrorResponse(msg="缺少节点ID")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return self._get_local_files(path, page, limit)
            else:
                return self._get_remote_files(node, path, page, limit)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def _get_local_files(self, path, page=1, limit=100):
        is_windows = True if platform.system() == 'Windows' else False
        if is_windows:
            path = path.replace("\\", "/")
        if not path:
            path = GetWebRootPath() if is_windows else "/"
        data_info = list_files_in_directory(dst_path=path, sort="name", is_windows=is_windows)
        data_dirs = data_info.get('data', [])
        total_nums = data_info['total_nums']
        file_nums = data_info['file_nums']
        dir_nums = data_info['dir_nums']
        # 分页处理
        total_pages = ceil(total_nums / limit) if limit > 0 else 1
        if page > total_pages:
            page = total_pages
        page = 1 if page < 1 else page
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_data = data_dirs[start_idx:end_idx]
        if not is_windows:
            if path == "/":
                directory_dict_list = []
            else:
                directory_list = path.split(os.path.sep)
                directory_dict_list = [
                    {'name': directory_list[i - 1], 'url': os.sep.join(directory_list[:i])}
                    for i in range(1, len(directory_list) + 1)
                ]
        else:
            drive_name = path.split(':')[0].lower() if path else ''
            try:
                path_without_drive = path.split(':')[1] if drive_name else None
            except Exception:
                return ErrorResponse(msg="路径错误：%s" % path)
            if not path_without_drive or path_without_drive in ("/", "\\"):
                directory_list = []
                directory_dict_list = []
            else:
                directory_list = path_without_drive.strip('/').strip('\\').split('/')
                path_list = ['/'.join(directory_list[:i + 1]) for i in range(len(directory_list))]
                directory_dict_list = [
                    {'name': name, 'url': drive_name + ":/" + path_list[i]}
                    for i, name in enumerate(directory_list)
                ]
            if drive_name:
                directory_dict_list.insert(0, {'name': drive_name + "盘", 'url': drive_name + ":/"})
            else:
                directory_dict_list.insert(0, {'name': drive_name, 'url': ""})
        data = {
            'data': paginated_data,
            'path': path,
            'paths': directory_dict_list,
            'file_nums': file_nums,
            'dir_nums': dir_nums,
            'is_windows': is_windows,
        }
        return SuccessResponse(data=data, total=total_nums, page=page, limit=limit)

    def _build_api_headers(self, node):
        """构建API请求头"""
        return build_api_headers(node)

    def _get_remote_files_by_api(self, node, path, page=1, limit=100):
        """通过API获取远程节点文件列表"""
        try:
            url = f"{node.address.rstrip('/')}/api/sys/fileManage/"
            headers = self._build_api_headers(node)
            data = {
                "action": "list_dir",
                "path": path,
                "sort": "name",
                "order": "asc",
                "page": page,
                "limit": limit,
            }
            resp = requests.post(url, headers=headers, json=data, timeout=30, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 2000:
                    page_data = result.get("data", {})
                    raw_data = page_data.get("data", {})
                    files_data = raw_data.get("data", [])
                    # 转换为前端需要的格式，保留面包屑导航等完整信息
                    files = []
                    for item in files_data:
                        files.append({
                            "name": item.get("name", ""),
                            "path": item.get("path", ""),
                            "is_dir": item.get("type") == "dir",
                            "size": item.get("size") if item.get("type") != "dir" else None,
                            "modify_time": item.get("modified", ""),
                        })
                    remote_data = {
                        "data": files,
                        "path": raw_data.get("path", path),
                        "paths": raw_data.get("paths", []),
                        "file_nums": raw_data.get("file_nums", 0),
                        "dir_nums": raw_data.get("dir_nums", 0),
                        "is_windows": raw_data.get("is_windows", False),
                    }
                    return SuccessResponse(data=remote_data, total=page_data.get("total", len(files)), page=page_data.get("page", page), limit=page_data.get("limit", limit))
                else:
                    return ErrorResponse(msg=result.get("msg", "获取远程文件失败"))
            elif resp.status_code == 401:
                return ErrorResponse(msg="API认证失败，请检查API密钥是否正确")
            else:
                return ErrorResponse(msg=f"API请求失败，状态码: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            return ErrorResponse(msg=f"无法连接到远程节点: {node.address}")
        except requests.exceptions.Timeout:
            return ErrorResponse(msg="API请求超时")
        except Exception as e:
            return ErrorResponse(msg=f"API获取远程文件失败: {str(e)}")

    def _get_remote_files(self, node, path, page=1, limit=100):
        """获取远程节点文件列表，支持SSH和API两种方式"""
        # 如果是API节点，优先使用API方式
        if node.node_type == "api" and node.api_key:
            return self._get_remote_files_by_api(node, path, page, limit)
        
        # 否则使用SSH方式
        try:
            with RuyiSSHClient(node) as client:
                encoded_path = __import__('base64').b64encode(path.encode()).decode()
                script = """
import json,os,time,base64,platform
files=[]
path=base64.b64decode('%s').decode()
is_windows=False
dir_nums=0
file_nums=0
try:
    for item in os.listdir(path):
        full_path=os.path.join(path,item)
        try:
            is_dir=os.path.isdir(full_path)
            st=os.stat(full_path)
            files.append({"name":item,"path":full_path.replace("\\\\","/"),"is_dir":is_dir,"size":st.st_size if not is_dir else None,"modify_time":time.strftime("%%Y-%%m-%%d %%H:%%M:%%S",time.localtime(st.st_mtime))})
            if is_dir:
                dir_nums+=1
            else:
                file_nums+=1
        except:pass
except:pass
print(json.dumps({"data":files,"path":path,"dir_nums":dir_nums,"file_nums":file_nums,"is_windows":is_windows}))
""" % encoded_path
                output, err = client.exec_command("python3 -c '%s'" % script, timeout=30)
            if output:
                result = json.loads(output)
                files_data = result.get("data", [])
                total_nums = len(files_data)
                # 分页处理
                total_pages = ceil(total_nums / limit) if limit > 0 else 1
                if page > total_pages:
                    page = total_pages
                page = 1 if page < 1 else page
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                paginated_data = files_data[start_idx:end_idx]
                remote_data = {
                    "data": paginated_data,
                    "path": result.get("path", path),
                    "paths": [],
                    "file_nums": result.get("file_nums", 0),
                    "dir_nums": result.get("dir_nums", 0),
                    "is_windows": result.get("is_windows", False),
                }
                return SuccessResponse(data=remote_data, total=total_nums, page=page, limit=limit)
            return SuccessResponse(data={"data": [], "path": path, "paths": [], "file_nums": 0, "dir_nums": 0, "is_windows": False}, total=0, page=1, limit=limit)
        except Exception as e:
            return ErrorResponse(msg=f"获取远程文件失败: {str(e)}")

    def start_transfer(self, request, reqData):
        task_id = reqData.get("id")
        if not task_id:
            return ErrorResponse(msg="缺少任务ID")
        try:
            task = FileTransferTask.objects.get(id=task_id)
            if task.status == "running":
                return ErrorResponse(msg="任务已在执行中")

            # 使用APScheduler后台执行传输
            from apps.systask.tasks import installTask

            task.status = "running"
            task.save(update_fields=["status"])
            try:
                installTask(
                    job_id=f"file_transfer_{task_id}",
                    job_func=_run_file_transfer,
                    func_args=[task_id]
                )
            except Exception as schedule_err:
                task.status = "pending"
                task.error_msg = f"调度失败: {str(schedule_err)}"
                task.save(update_fields=["status", "error_msg"])
                return ErrorResponse(msg=f"任务调度失败: {str(schedule_err)}")
            RuyiAddOpLog(request, msg=f"【文件互传】=>【开始传输】=>任务{task_id}", module="nodemg")
            return DetailResponse(data={"status": task.status}, msg="传输已开始")
        except FileTransferTask.DoesNotExist:
            return ErrorResponse(msg="任务不存在")

    def cancel_transfer(self, request, reqData):
        task_id = reqData.get("id")
        if not task_id:
            return ErrorResponse(msg="缺少任务ID")
        try:
            task = FileTransferTask.objects.get(id=task_id)
            if task.status not in ["running", "pending"]:
                return ErrorResponse(msg="任务未在执行中或等待中")
            task.status = "cancelled"
            task.speed = 0
            task.save(update_fields=["status", "speed"])
            FileTransferRecord.objects.filter(task=task, status__in=["pending", "transferring"]).update(status="skipped")
            RuyiAddOpLog(request, msg=f"【文件互传】=>【取消传输】=>任务{task_id}", module="nodemg")
            return DetailResponse(data={"status": task.status}, msg="传输已取消")
        except FileTransferTask.DoesNotExist:
            return ErrorResponse(msg="任务不存在")

    def retry_transfer(self, request, reqData):
        task_id = reqData.get("id")
        if not task_id:
            return ErrorResponse(msg="缺少任务ID")
        try:
            task = FileTransferTask.objects.get(id=task_id)
            if task.status not in ["failed", "cancelled"]:
                return ErrorResponse(msg="只能重试失败或已取消的任务")
            task.status = "pending"
            task.progress = 0
            task.error_msg = ""
            task.save(update_fields=["status", "progress", "error_msg"])
            FileTransferRecord.objects.filter(task=task).update(status="pending", progress=0, error_msg="")
            RuyiAddOpLog(request, msg=f"【文件互传】=>【重试传输】=>任务{task_id}", module="nodemg")
            return DetailResponse(data={"status": task.status}, msg="已重新开始")
        except FileTransferTask.DoesNotExist:
            return ErrorResponse(msg="任务不存在")

    def get_task_progress(self, request, reqData):
        task_id = reqData.get("id")
        if not task_id:
            return ErrorResponse(msg="缺少任务ID")
        try:
            task = FileTransferTask.objects.get(id=task_id)
            data = {
                "id": task.id,
                "status": task.status,
                "total_files": task.total_files,
                "transferred_files": task.transferred_files,
                "total_size": task.total_size,
                "transferred_size": task.transferred_size,
                "progress": task.progress,
                "speed": task.speed,
                "error_msg": task.error_msg,
            }
            return DetailResponse(data=data, msg="获取成功")
        except FileTransferTask.DoesNotExist:
            return ErrorResponse(msg="任务不存在")

    def get_detail(self, request, reqData):
        task_id = reqData.get("id")
        if not task_id:
            return ErrorResponse(msg="缺少任务ID")
        try:
            task = FileTransferTask.objects.get(id=task_id)
            serializer = FileTransferTaskDetailSerializer(task)
            records = FileTransferRecord.objects.filter(task=task)
            record_serializer = FileTransferRecordSerializer(records, many=True)
            return DetailResponse(data={"task": serializer.data, "records": record_serializer.data}, msg="获取成功")
        except FileTransferTask.DoesNotExist:
            return ErrorResponse(msg="任务不存在")

    def calc_size(self, request, reqData):
        node_id = reqData.get("node_id")
        path = reqData.get("path", "")
        if not node_id or not path:
            return ErrorResponse(msg="缺少节点ID或路径")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return self._calc_local_size(path)
            else:
                return self._calc_remote_size(node, path)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def _calc_local_size(self, path):
        try:
            size = get_directory_size(path)
            return DetailResponse(data={"size": size}, msg="计算成功")
        except Exception as e:
            return ErrorResponse(msg=f"计算大小失败: {str(e)}")

    def _calc_remote_size_by_api(self, node, path):
        """通过API计算远程目录大小"""
        try:
            url = f"{node.address.rstrip('/')}/api/sys/fileManage/"
            headers = self._build_api_headers(node)
            data = {
                "action": "calc_size",
                "path": path,
            }
            resp = requests.post(url, headers=headers, json=data, timeout=60, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 2000:
                    data = result.get("data", {})
                    return DetailResponse(data={"size": data.get("size", 0)}, msg="计算成功")
                else:
                    return ErrorResponse(msg=result.get("msg", "计算大小失败"))
            elif resp.status_code == 401:
                return ErrorResponse(msg="API认证失败，请检查API密钥是否正确")
            else:
                return ErrorResponse(msg=f"API请求失败，状态码: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            return ErrorResponse(msg=f"无法连接到远程节点: {node.address}")
        except requests.exceptions.Timeout:
            return ErrorResponse(msg="API请求超时")
        except Exception as e:
            return ErrorResponse(msg=f"API计算远程大小失败: {str(e)}")

    def _calc_remote_size(self, node, path):
        """计算远程目录大小，支持SSH和API两种方式"""
        # 如果是API节点，优先使用API方式
        if node.node_type == "api" and node.api_key:
            return self._calc_remote_size_by_api(node, path)
        
        # 否则使用SSH方式
        try:
            with RuyiSSHClient(node) as client:
                encoded_path = __import__('base64').b64encode(path.encode()).decode()
                script = """
import os,base64
total_size=0
path=base64.b64decode('%s').decode()
if os.path.isfile(path):
    total_size=os.path.getsize(path)
elif os.path.isdir(path):
    for dirpath,dirnames,filenames in os.walk(path):
        for f in filenames:
            try:
                total_size+=os.path.getsize(os.path.join(dirpath,f))
            except:pass
print(total_size)
""" % encoded_path
                output, err = client.exec_command("python3 -c '%s'" % script, timeout=60)
            total_size = int(output) if output.isdigit() else 0
            return DetailResponse(data={"size": total_size}, msg="计算成功")
        except Exception as e:
            return ErrorResponse(msg=f"计算远程大小失败: {str(e)}")

    def delete_file(self, request, reqData):
        node_id = reqData.get("node_id")
        path = reqData.get("path", "")
        if not node_id or not path:
            return ErrorResponse(msg="缺少节点ID或路径")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return self._delete_local_file(request, path)
            else:
                return self._delete_remote_file(request, node, path)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def _delete_local_file(self, request, path):
        is_windows = True if platform.system() == 'Windows' else False
        try:
            if os.path.isfile(path):
                delete_file(path=path, is_windows=is_windows)
            elif os.path.isdir(path):
                delete_dir(path=path, is_windows=is_windows)
            else:
                return ErrorResponse(msg="文件或目录不存在")
            RuyiAddOpLog(request, msg=f"【文件互传】=>【删除文件】=>{path}", module="nodemg")
            return DetailResponse(data=[], msg="删除成功")
        except Exception as e:
            return ErrorResponse(msg=f"删除失败: {str(e)}")

    def _delete_remote_file_by_api(self, request, node, path):
        """通过API删除远程文件"""
        try:
            url = f"{node.address.rstrip('/')}/api/sys/fileManage/"
            headers = self._build_api_headers(node)
            # 根据路径末尾是否为/判断是文件还是目录，或通过is_dir参数
            is_dir = path.endswith("/")
            action = "delete_dir" if is_dir else "delete_file"
            params = {
                "action": action,
                "path": path.rstrip("/"),
            }
            resp = requests.post(url, headers=headers, json=params, timeout=30, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 2000:
                    RuyiAddOpLog(request, msg=f"【文件互传】=>【删除远程文件】=>{node.name}:{path}", module="nodemg")
                    return DetailResponse(data=[], msg="删除成功")
                else:
                    return ErrorResponse(msg=result.get("msg", "删除失败"))
            elif resp.status_code == 401:
                return ErrorResponse(msg="API认证失败，请检查API密钥是否正确")
            else:
                return ErrorResponse(msg=f"API请求失败，状态码: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            return ErrorResponse(msg=f"无法连接到远程节点: {node.address}")
        except requests.exceptions.Timeout:
            return ErrorResponse(msg="API请求超时")
        except Exception as e:
            return ErrorResponse(msg=f"API删除远程文件失败: {str(e)}")

    def _delete_remote_file(self, request, node, path):
        """删除远程文件，支持SSH和API两种方式"""
        # 如果是API节点，优先使用API方式
        if node.node_type == "api" and node.api_key:
            return self._delete_remote_file_by_api(request, node, path)
        
        # 否则使用SSH方式
        try:
            with RuyiSSHClient(node) as client:
                encoded_path = __import__('base64').b64encode(path.encode()).decode()
                script = """
import os,shutil,base64
path=base64.b64decode('%s').decode()
if os.path.isfile(path):
    os.remove(path)
elif os.path.isdir(path):
    shutil.rmtree(path)
print("ok")
""" % encoded_path
                output, err = client.exec_command("python3 -c '%s'" % script, timeout=30)
            if err:
                return ErrorResponse(msg=f"删除远程文件失败: {err[:200]}")
            RuyiAddOpLog(request, msg=f"【文件互传】=>【删除远程文件】=>{node.name}:{path}", module="nodemg")
            return DetailResponse(data=[], msg="删除成功")
        except Exception as e:
            return ErrorResponse(msg=f"删除远程文件失败: {str(e)}")

    def create_dir(self, request, reqData):
        node_id = reqData.get("node_id")
        path = reqData.get("path", "")
        if not node_id or not path:
            return ErrorResponse(msg="缺少节点ID或路径")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return self._create_local_dir(request, path)
            else:
                return self._create_remote_dir(request, node, path)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

    def _create_local_dir(self, request, path):
        is_windows = True if platform.system() == 'Windows' else False
        try:
            create_dir(path=path, is_windows=is_windows)
            RuyiAddOpLog(request, msg=f"【文件互传】=>【创建目录】=>{path}", module="nodemg")
            return DetailResponse(data=[], msg="创建成功")
        except Exception as e:
            return ErrorResponse(msg=f"创建目录失败: {str(e)}")

    def _create_remote_dir_by_api(self, request, node, path):
        """通过API创建远程目录"""
        try:
            url = f"{node.address.rstrip('/')}/api/sys/fileManage/"
            headers = self._build_api_headers(node)
            params = {
                "action": "create_dir",
                "path": path,
            }
            resp = requests.post(url, headers=headers, json=params, timeout=30, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 2000:
                    RuyiAddOpLog(request, msg=f"【文件互传】=>【创建远程目录】=>{node.name}:{path}", module="nodemg")
                    return DetailResponse(data=[], msg="创建成功")
                else:
                    return ErrorResponse(msg=result.get("msg", "创建目录失败"))
            elif resp.status_code == 401:
                return ErrorResponse(msg="API认证失败，请检查API密钥是否正确")
            else:
                return ErrorResponse(msg=f"API请求失败，状态码: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            return ErrorResponse(msg=f"无法连接到远程节点: {node.address}")
        except requests.exceptions.Timeout:
            return ErrorResponse(msg="API请求超时")
        except Exception as e:
            return ErrorResponse(msg=f"API创建远程目录失败: {str(e)}")

    def _create_remote_dir(self, request, node, path):
        """创建远程目录，支持SSH和API两种方式"""
        # 如果是API节点，优先使用API方式
        if node.node_type == "api" and node.api_key:
            return self._create_remote_dir_by_api(request, node, path)
        
        # 否则使用SSH方式
        try:
            with RuyiSSHClient(node) as client:
                safe_path = shlex.quote(path)
                out, err = client.exec_command(f"mkdir -p {safe_path}", timeout=10)
            if err:
                return ErrorResponse(msg=f"创建远程文件夹失败: {err[:200]}")
            RuyiAddOpLog(request, msg=f"【文件互传】=>【创建远程目录】=>{node.name}:{path}", module="nodemg")
            return DetailResponse(data=[], msg="创建成功")
        except Exception as e:
            return ErrorResponse(msg=f"创建远程文件夹失败: {str(e)}")

    def upload_remote_file(self, request, reqData):
        node_id = reqData.get("node_id")
        path = reqData.get("path", "")
        file = request.FILES.get('lyfile', None)
        if not node_id or not path or not file:
            return ErrorResponse(msg="缺少节点ID、路径或文件")
        try:
            node = ClusterNode.objects.get(id=node_id)
            if node.is_local:
                return ErrorResponse(msg="本机节点请使用文件管理上传接口")
            # API节点优先使用API方式上传
            if node.node_type == "api" and node.api_key:
                return self._upload_remote_file_by_api(request, node, path, file)
            # SSH方式上传
            return self._upload_remote_file_by_ssh(request, node, path, file)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")
        except Exception as e:
            return ErrorResponse(msg=f"上传失败: {str(e)}")

    def _upload_remote_file_by_api(self, request, node, path, file):
        """通过API上传文件到远程节点"""
        try:
            url = f"{node.address.rstrip('/')}/api/sys/fileManage/upload/"
            headers = self._build_api_headers(node)
            # 使用multipart/form-data上传，移除Content-Type让requests自动设置boundary
            headers.pop("Content-Type", None)
            files = {"lyfile": (file.name, file.read(), file.content_type)}
            data = {
                "path": path,
            }
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=120, verify=False)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 2000:
                    RuyiAddOpLog(request, msg=f"【文件互传】=>【上传远程文件(API)】=>{node.name}:{path}/{file.name}", module="nodemg")
                    return DetailResponse(data=None, msg="上传成功")
                else:
                    return ErrorResponse(msg=result.get("msg", "上传失败"))
            elif resp.status_code == 401:
                return ErrorResponse(msg="API认证失败，请检查API密钥是否正确")
            else:
                return ErrorResponse(msg=f"API请求失败，状态码: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            return ErrorResponse(msg=f"无法连接到远程节点: {node.address}")
        except requests.exceptions.Timeout:
            return ErrorResponse(msg="API请求超时")
        except Exception as e:
            return ErrorResponse(msg=f"API上传远程文件失败: {str(e)}")

    def _upload_remote_file_by_ssh(self, request, node, path, file):
        """通过SSH/SFTP上传文件到远程节点"""
        with RuyiSSHClient(node) as client:
            sftp = client.open_sftp()
            remote_path = path.rstrip('/') + '/' + file.name
            try:
                sftp.stat(path)
            except FileNotFoundError:
                safe_path = shlex.quote(path)
                client.exec_command(f"mkdir -p {safe_path}", timeout=10)
            file_data = file.read()
            with sftp.open(remote_path, 'wb') as remote_file:
                remote_file.write(file_data)
            sftp.close()
        RuyiAddOpLog(request, msg=f"【文件互传】=>【上传远程文件(SSH)】=>{node.name}:{remote_path}", module="nodemg")
        return DetailResponse(data=None, msg="上传成功")

    def batch_transfer(self, request, reqData):
        source_node_id = reqData.get("source_node")
        target_node_id = reqData.get("target_node")
        source_path_list = reqData.get("source_path_list", [])
        target_path = reqData.get("target_path", "")
        task_action = reqData.get("task_action", "upload")
        default_mode = reqData.get("default_mode", "cover")

        if not source_node_id or not target_node_id:
            return ErrorResponse(msg="请选择源节点和目标节点")
        if not target_path:
            return ErrorResponse(msg="请填写目标路径")
        if isinstance(source_path_list, str):
            try:
                source_path_list = json.loads(source_path_list)
            except Exception:
                return ErrorResponse(msg="源文件路径格式错误")
        if not source_path_list:
            return ErrorResponse(msg="请选择要传输的文件")

        running_task = FileTransferTask.objects.filter(status__in=["pending", "running"]).first()
        if running_task:
            return ErrorResponse(msg="当前存在正在执行的任务，请等待完成后再提交")

        try:
            source_node = ClusterNode.objects.get(id=source_node_id)
            target_node = ClusterNode.objects.get(id=target_node_id)
        except ClusterNode.DoesNotExist:
            return ErrorResponse(msg="节点不存在")

        task = FileTransferTask(
            source_node=source_node,
            target_node=target_node,
            task_action=task_action,
            status="pending",
            source_path_list=json.dumps(source_path_list) if isinstance(source_path_list, list) else source_path_list,
            target_path=target_path,
            default_mode=default_mode,
            total_files=len(source_path_list),
            created_by=request.user.username if request.user else "",
        )
        task.save()

        for src_file in source_path_list:
            FileTransferRecord.objects.create(
                task=task,
                src_file=src_file,
                dst_file=os.path.join(target_path, os.path.basename(src_file.rstrip("/"))),
                is_dir=src_file.endswith("/"),
                status="pending",
            )

        RuyiAddOpLog(request, msg=f"【文件互传】=>【批量传输】=>{source_node.name} -> {target_node.name}, {len(source_path_list)}个文件", module="nodemg")

        # 自动开始传输
        from apps.systask.tasks import installTask

        task.status = "running"
        task.save(update_fields=["status"])
        try:
            installTask(
                job_id=f"file_transfer_{task.id}",
                job_func=_run_file_transfer,
                func_args=[task.id]
            )
        except Exception as schedule_err:
            task.status = "pending"
            task.error_msg = f"调度失败: {str(schedule_err)}"
            task.save(update_fields=["status", "error_msg"])
            return ErrorResponse(msg=f"任务调度失败: {str(schedule_err)}")

        return DetailResponse(data={"id": task.id}, msg="传输任务创建成功")
