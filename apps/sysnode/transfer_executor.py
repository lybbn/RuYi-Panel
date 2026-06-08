# -*- coding: utf-8 -*-

"""
@Remark: 文件传输执行器 - 实现实际的文件传输逻辑
@author lybbn<2026-06-03>
"""
import os
import json
import time
import tempfile
from apps.sysnode.models import FileTransferTask, FileTransferRecord, ClusterNode
from utils.ssh_client import RuyiSSHClient, build_api_headers
from utils.common import format_size


class SkipException(Exception):
    """文件跳过异常"""
    pass


class TransferExecutor:
    """文件传输执行器"""

    def __init__(self, task_id):
        self.task = FileTransferTask.objects.get(id=task_id)
        self.source_node = self.task.source_node
        self.target_node = self.task.target_node

    def execute(self):
        """执行传输任务"""
        try:
            self.task.status = "running"
            self.task.save(update_fields=["status"])

            records = FileTransferRecord.objects.filter(task=self.task, status="pending")
            total_files = records.count()
            completed = 0
            failed_count = 0

            for record in records:
                # 每次循环前检查任务是否被取消
                self.task.refresh_from_db()
                if self.task.status == "cancelled":
                    break

                try:
                    record.status = "transferring"
                    record.save(update_fields=["status"])

                    # 冲突检测
                    self._check_conflict(record)

                    start_time = time.time()
                    self._transfer_single_file(record)
                    elapsed = time.time() - start_time

                    record.status = "complete"
                    record.progress = 100
                    if record.file_size > 0:
                        record.speed = round(record.file_size / elapsed) if elapsed > 0 else 0
                    completed += 1
                except SkipException:
                    completed += 1  # 跳过的也算完成
                except Exception as e:
                    record.status = "failed"
                    record.error_msg = str(e)
                    failed_count += 1

                record.save(update_fields=["status", "progress", "speed", "error_msg"])

                # 更新任务进度
                self.task.transferred_files = completed
                self.task.progress = round(completed / total_files * 100, 1) if total_files > 0 else 0
                self.task.save(update_fields=["transferred_files", "progress"])

                # 推送进度
                self._notify_progress(record)

            # 全部完成（检查是否被取消）
            self.task.refresh_from_db()
            if self.task.status == "cancelled":
                pass  # 已取消，不修改状态
            elif FileTransferRecord.objects.filter(task=self.task, status="failed").exists():
                self.task.status = "failed"
                self.task.progress = 100
            else:
                self.task.status = "complete"
                self.task.progress = 100
            self.task.speed = 0
            self.task.save(update_fields=["status", "progress", "speed"])

        except Exception as e:
            self.task.status = "failed"
            self.task.error_msg = str(e)
            self.task.save(update_fields=["status", "error_msg"])

    def _transfer_single_file(self, record):
        """传输单个文件，根据源/目标节点类型选择传输方式"""
        src_is_local = self.source_node.is_local
        dst_is_local = self.target_node.is_local

        if src_is_local and not dst_is_local:
            self._local_to_remote(record)
        elif not src_is_local and dst_is_local:
            self._remote_to_local(record)
        elif not src_is_local and not dst_is_local:
            self._remote_to_remote_via_local(record)

    def _local_to_remote(self, record):
        """本地文件上传到远程节点"""
        if self.target_node.node_type == "api" and self.target_node.api_key:
            self._upload_by_api(record)
        else:
            self._upload_by_sftp(record)

    def _upload_by_api(self, record):
        """通过API上传文件到远程节点"""
        import requests as req_lib
        url = f"{self.target_node.address.rstrip('/')}/api/sys/fileManage/upload/"
        headers = build_api_headers(self.target_node)
        # multipart上传时不能手动设置Content-Type，由requests自动设置
        headers.pop('Content-Type', None)
        data = {"path": os.path.dirname(record.dst_file)}
        with open(record.src_file, 'rb') as f:
            files = {'lyfile': (os.path.basename(record.src_file), f)}
            resp = req_lib.post(url, headers=headers, data=data, files=files, timeout=300, verify=False)
            if resp.status_code != 200 or resp.json().get("code") != 2000:
                raise Exception(f"API上传失败: {resp.text[:200]}")

    def _upload_by_sftp(self, record):
        """通过SFTP上传文件到远程节点（支持断点续传）"""
        with RuyiSSHClient(self.target_node) as ssh:
            sftp = ssh.open_sftp()
            try:
                if record.is_dir:
                    self._sftp_mkdir_recursive(sftp, record.dst_file.rstrip("/"))
                else:
                    dst_dir = os.path.dirname(record.dst_file)
                    if dst_dir:
                        self._sftp_mkdir_recursive(sftp, dst_dir)
                    # 断点续传：检查远程文件已存在的大小
                    offset = 0
                    if record.transferred_size > 0:
                        try:
                            remote_stat = sftp.stat(record.dst_file)
                            offset = min(remote_stat.st_size, record.transferred_size)
                        except IOError:
                            offset = 0
                    if offset > 0 and offset < record.file_size:
                        # 追加模式续传：通过SFTP open('a')追加写入
                        with open(record.src_file, 'rb') as local_f:
                            local_f.seek(offset)
                            with sftp.open(record.dst_file, 'a') as remote_f:
                                while True:
                                    chunk = local_f.read(65536)
                                    if not chunk:
                                        break
                                    remote_f.write(chunk)
                                    offset += len(chunk)
                                    self._update_record_progress(record, offset, record.file_size)
                    else:
                        sftp.put(record.src_file, record.dst_file)
            finally:
                sftp.close()

    def _remote_to_local(self, record):
        """从远程节点下载文件到本地"""
        if self.source_node.node_type == "api" and self.source_node.api_key:
            self._download_by_api(record)
        else:
            self._download_by_sftp(record)

    def _download_by_api(self, record):
        """通过API从远程节点下载文件"""
        import requests as req_lib
        url = f"{self.source_node.address.rstrip('/')}/api/sys/fileManage/"
        headers = build_api_headers(self.source_node)
        data = {
            "action": "download",
            "path": record.src_file,
        }
        resp = req_lib.post(url, headers=headers, json=data, timeout=300, verify=False)
        if resp.status_code != 200 or resp.json().get("code") != 2000:
            raise Exception(f"API下载失败: {resp.text[:200]}")
        # 确保本地目标目录存在
        dst_dir = os.path.dirname(record.dst_file)
        if dst_dir:
            os.makedirs(dst_dir, exist_ok=True)
        with open(record.dst_file, 'wb') as f:
            f.write(resp.content)

    def _download_by_sftp(self, record):
        """通过SFTP从远程节点下载文件（支持断点续传）"""
        with RuyiSSHClient(self.source_node) as ssh:
            sftp = ssh.open_sftp()
            try:
                if record.is_dir:
                    self._sftp_download_dir(sftp, record.src_file, record.dst_file)
                else:
                    # 确保本地目标目录存在
                    dst_dir = os.path.dirname(record.dst_file)
                    if dst_dir:
                        os.makedirs(dst_dir, exist_ok=True)
                    # 断点续传：检查本地文件已存在的大小
                    offset = 0
                    if record.transferred_size > 0:
                        try:
                            local_size = os.path.getsize(record.dst_file)
                            offset = min(local_size, record.transferred_size)
                        except OSError:
                            offset = 0
                    if offset > 0 and offset < record.file_size:
                        # 追加模式续传：从远程offset位置读取追加到本地
                        with sftp.open(record.src_file, 'r') as remote_f:
                            remote_f.seek(offset)
                            with open(record.dst_file, 'ab') as local_f:
                                while True:
                                    chunk = remote_f.read(65536)
                                    if not chunk:
                                        break
                                    local_f.write(chunk)
                                    offset += len(chunk)
                                    self._update_record_progress(record, offset, record.file_size)
                    else:
                        sftp.get(record.src_file, record.dst_file)
            finally:
                sftp.close()

    def _remote_to_remote_via_local(self, record):
        """远程→远程：优先尝试API直传，失败则通过本机中转"""
        # 优先尝试API直传（两个节点都是API类型且有api_key）
        if (self.source_node.node_type == "api" and self.source_node.api_key
                and self.target_node.node_type == "api" and self.target_node.api_key):
            try:
                self._remote_to_remote_direct(record)
                return
            except Exception:
                pass  # 直传失败，回退到中转模式

        # 中转模式：下载到临时目录再上传
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = os.path.join(tmp_dir, os.path.basename(record.src_file))
            # 1. 下载到临时目录
            old_src = record.src_file
            old_dst = record.dst_file
            record.dst_file = tmp_file
            self._remote_to_local(record)
            # 2. 从临时目录上传
            record.src_file = tmp_file
            record.dst_file = old_dst
            self._local_to_remote(record)
            # 3. 恢复原始路径
            record.src_file = old_src

    def _remote_to_remote_direct(self, record):
        """远程→远程：通过API在两个节点间直接传输（无需中转）"""
        import requests as req_lib
        # 通知目标节点从源节点拉取文件
        dst_headers = build_api_headers(self.target_node)
        pull_data = {
            "action": "pull_file",
            "source_url": f"{self.source_node.address.rstrip('/')}/api/sys/fileManage/",
            "source_api_key": self.source_node.api_key,
            "source_path": record.src_file,
            "target_path": record.dst_file,
            "is_dir": record.is_dir,
        }
        resp = req_lib.post(
            f"{self.target_node.address.rstrip('/')}/api/sys/fileManage/",
            headers=dst_headers, json=pull_data, timeout=300, verify=False
        )
        if resp.status_code != 200 or resp.json().get("code") != 2000:
            raise Exception(f"远程直传失败: {resp.text[:200]}")

    def _sftp_mkdir_recursive(self, sftp, remote_path):
        """递归创建SFTP远程目录"""
        dirs = remote_path.split("/")
        current = ""
        for d in dirs:
            if not d:
                continue
            current = current + "/" + d
            try:
                sftp.stat(current)
            except FileNotFoundError:
                sftp.mkdir(current)

    def _sftp_download_dir(self, sftp, remote_path, local_path):
        """递归下载SFTP远程目录"""
        if not os.path.exists(local_path):
            os.makedirs(local_path, exist_ok=True)
        for item in sftp.listdir(remote_path):
            full_remote = remote_path + "/" + item
            full_local = os.path.join(local_path, item).replace("\\", "/")
            try:
                attr = sftp.stat(full_remote)
                from stat import S_ISDIR
                if S_ISDIR(attr.st_mode):
                    self._sftp_download_dir(sftp, full_remote, full_local)
                else:
                    sftp.get(full_remote, full_local)
            except Exception:
                pass

    def _update_record_progress(self, record, transferred, total):
        """更新传输记录的进度"""
        try:
            record.transferred_size = transferred
            record.progress = round(transferred / total * 100, 1) if total > 0 else 0
            record.save(update_fields=["transferred_size", "progress"])
        except Exception:
            pass

    def _check_conflict(self, record):
        """检查目标路径是否已存在文件，按冲突策略处理"""
        dst_is_local = self.target_node.is_local
        exists = False

        if dst_is_local:
            exists = os.path.exists(record.dst_file)
        else:
            exists = self._remote_file_exists(record.dst_file)

        if not exists:
            return  # 无冲突

        mode = self.task.default_mode
        if mode == "cover":
            return  # 直接覆盖
        elif mode == "ignore":
            record.status = "skipped"
            record.error_msg = "目标文件已存在，已跳过"
            record.save(update_fields=["status", "error_msg"])
            raise SkipException("文件已跳过")
        elif mode == "rename":
            record.dst_file = self._auto_rename(record.dst_file, dst_is_local)

    def _auto_rename(self, path, is_local):
        """自动重命名避免冲突"""
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            new_path = f"{base}_{counter}{ext}"
            if is_local:
                if not os.path.exists(new_path):
                    return new_path
            else:
                if not self._remote_file_exists(new_path):
                    return new_path
            counter += 1

    def _remote_file_exists(self, path):
        """检查远程节点文件是否存在"""
        try:
            if self.target_node.node_type == "api" and self.target_node.api_key:
                import requests as req_lib
                url = f"{self.target_node.address.rstrip('/')}/api/sys/fileManage/"
                headers = build_api_headers(self.target_node)
                data = {"action": "list_dir", "path": path}
                resp = req_lib.post(url, headers=headers, json=data, timeout=10, verify=False)
                return resp.status_code == 200
            else:
                with RuyiSSHClient(self.target_node) as ssh:
                    out, err = ssh.exec_command(f"test -e '{path}' && echo EXISTS || echo NOT_EXISTS", timeout=5)
                    return out.strip() == "EXISTS"
        except Exception:
            return False

    def _notify_progress(self, record):
        """通过Channel Layer推送进度"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    "file_transfer",
                    {
                        "type": "transfer_progress",
                        "data": {
                            "task_id": self.task.id,
                            "record_id": record.id,
                            "src_file": record.src_file,
                            "dst_file": record.dst_file,
                            "status": record.status,
                            "progress": self.task.progress,
                            "transferred_files": self.task.transferred_files,
                            "total_files": self.task.total_files,
                            "error_msg": record.error_msg or "",
                        }
                    }
                )
        except Exception:
            pass  # 非关键路径，不影响传输


def expand_directory(node, path, is_local):
    """递归展开目录，返回所有子文件列表"""
    files = []
    if is_local:
        for root, dirs, filenames in os.walk(path):
            for d in dirs:
                dir_path = os.path.join(root, d).replace("\\", "/") + "/"
                files.append({"path": dir_path, "is_dir": True, "size": 0})
            for f in filenames:
                file_path = os.path.join(root, f).replace("\\", "/")
                try:
                    size = os.path.getsize(file_path)
                except Exception:
                    size = 0
                files.append({"path": file_path, "is_dir": False, "size": size})
    else:
        # 远程目录展开
        if node.node_type == "api" and node.api_key:
            files = _expand_remote_directory_by_api(node, path)
        else:
            files = _expand_remote_directory_by_ssh(node, path)
    return files


def _expand_remote_directory_by_api(node, path):
    """通过API递归获取远程目录"""
    import requests as req_lib
    url = f"{node.address.rstrip('/')}/api/sys/fileManage/"
    headers = build_api_headers(node)
    data = {"action": "list_dir", "path": path, "sort": "name", "order": "asc"}
    try:
        resp = req_lib.post(url, headers=headers, json=data, timeout=30, verify=False)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 2000:
                page_data = result.get("data", {})
                raw_data = page_data.get("data", {})
                items = raw_data.get("data", [])
                files = []
                for item in items:
                    p = item.get("path", "")
                    is_dir = item.get("type") == "dir"
                    files.append({
                        "path": p,
                        "is_dir": is_dir,
                        "size": item.get("size", 0) if not is_dir else 0,
                    })
                    # 如果是目录，递归展开
                    if is_dir:
                        sub_files = _expand_remote_directory_by_api(node, p)
                        files.extend(sub_files)
                return files
    except Exception:
        pass
    return []


def _expand_remote_directory_by_ssh(node, path):
    """通过SSH递归获取远程目录"""
    files = []
    try:
        with RuyiSSHClient(node) as ssh:
            encoded_path = __import__('base64').b64encode(path.encode()).decode()
            script = """
import json,os,time,base64
files=[]
path=base64.b64decode('%s').decode()
for root,dirs,filenames in os.walk(path):
    for d in dirs:
        dp=os.path.join(root,d).replace('\\\\\\\\','/')+'/'
        files.append({'path':dp,'is_dir':True,'size':0})
    for f in filenames:
        fp=os.path.join(root,f).replace('\\\\\\\\','/')
        try:sz=os.path.getsize(fp)
        except:sz=0
        files.append({'path':fp,'is_dir':False,'size':sz})
print(json.dumps(files))
""" % encoded_path
            out, err = ssh.exec_command("python3 -c '%s'" % script, timeout=60)
            if out:
                files = json.loads(out.strip())
    except Exception:
        pass
    return files
