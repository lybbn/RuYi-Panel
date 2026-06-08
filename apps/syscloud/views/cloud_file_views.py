import os
import time
import threading
import tempfile
from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from utils.common import get_parameter_dic
from apps.syscloud.models import CloudStorageAccount
from apps.syscloud.cloud_providers.factory import get_provider
from apps.syscloud.cloud_providers.sdk_manager import SDKManager, SDK_DEPS, get_sdk_for_provider

# 上传任务注册表：task_id -> threading.Event(取消标志)
_upload_cancel_events = {}


class CloudFileListView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        prefix = reqData.get('prefix', '')
        delimiter = reqData.get('delimiter', '/')
        max_keys = int(reqData.get('max_keys', 200))

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            sdk_info = SDK_DEPS.get(sdk_name, {})
            return ErrorResponse(msg=(
                "无法浏览文件：缺少必要的SDK模块。\n\n"
                "📋 需要安装：{display_name}\n"
                "📦 包名：{package}\n"
                "💾 大小：约 {size}\n"
                "📝 说明：{desc}\n\n"
                "请先前往「SDK管理」安装对应模块。"
            ).format(
                display_name=sdk_info.get('display_name', sdk_name),
                package=sdk_info.get('package', sdk_name),
                size=sdk_info.get('size_mb', '未知'),
                desc=sdk_info.get('description', ''),
            ))

        try:
            provider = get_provider(account)
            success, result = provider.list_objects(
                prefix=prefix, delimiter=delimiter, max_keys=max_keys,
            )
            if success:
                return SuccessResponse(data=result)
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="获取文件列表异常：{}".format(str(e)[:200]))


class CloudFileUploadView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        account_id = request.data.get('account_id')
        remote_path = request.data.get('remote_path', '')
        file = request.FILES.get('file', None)
        task_id = request.data.get('task_id', '')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")
        if not file:
            return ErrorResponse(msg="请选择要上传的文件")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            sdk_info = SDK_DEPS.get(sdk_name, {})
            return ErrorResponse(msg=(
                "无法上传文件：缺少必要的SDK模块。\n\n"
                "📋 需要安装：{display_name}\n"
                "📦 包名：{package}\n"
                "💾 大小：约 {size}\n\n"
                "请先前往「SDK管理」安装对应模块。"
            ).format(
                display_name=sdk_info.get('display_name', sdk_name),
                package=sdk_info.get('package', sdk_name),
                size=sdk_info.get('size_mb', '未知'),
            ))

        if not remote_path:
            remote_path = account.backup_path + file.name

        if not task_id:
            task_id = "cloud_{}_{}".format(int(time.time() * 1000), os.getpid())

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.name)
        try:
            with open(temp_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
        except Exception as e:
            return ErrorResponse(msg="保存临时文件失败：{}".format(str(e)[:200]))

        # 后台线程执行上传，API 立即返回
        import threading
        # 注册取消事件
        cancel_event = threading.Event()
        _upload_cancel_events[task_id] = cancel_event

        t = threading.Thread(
            target=self._do_upload,
            args=(account_id, temp_path, remote_path, task_id, file.name, cancel_event),
            daemon=True,
        )
        t.start()

        return DetailResponse(data={"task_id": task_id}, msg="上传任务已提交")

    @staticmethod
    def _do_upload(account_id, temp_path, remote_path, task_id, file_name, cancel_event):
        """后台线程执行云存储上传"""
        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
            provider = get_provider(account)

            def progress_callback(uploaded_bytes, total_bytes):
                # 检查是否已取消
                if cancel_event.is_set():
                    raise InterruptedError("上传已取消")
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        progress = round(uploaded_bytes / total_bytes * 100) if total_bytes > 0 else 0
                        async_to_sync(channel_layer.group_send)(
                            "cloud_upload",
                            {
                                "type": "upload_progress",
                                "data": {
                                    "task_id": task_id,
                                    "file_name": file_name,
                                    "status": "uploading",
                                    "progress": progress,
                                    "uploaded_bytes": uploaded_bytes,
                                    "total_bytes": total_bytes,
                                }
                            }
                        )
                except InterruptedError:
                    raise
                except Exception:
                    pass

            success, msg = provider.upload_file_with_progress(temp_path, remote_path, progress_callback)

            if success:
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            "cloud_upload",
                            {
                                "type": "upload_progress",
                                "data": {
                                    "task_id": task_id,
                                    "file_name": file_name,
                                    "status": "success",
                                    "progress": 100,
                                }
                            }
                        )
                except Exception:
                    pass
            else:
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            "cloud_upload",
                            {
                                "type": "upload_progress",
                                "data": {
                                    "task_id": task_id,
                                    "file_name": file_name,
                                    "status": "fail",
                                    "error_msg": str(msg)[:200],
                                }
                            }
                        )
                except Exception:
                    pass
        except InterruptedError:
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        "cloud_upload",
                        {
                            "type": "upload_progress",
                            "data": {
                                "task_id": task_id,
                                "file_name": file_name,
                                "status": "cancelled",
                            }
                        }
                    )
            except Exception:
                pass
        except Exception as e:
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        "cloud_upload",
                        {
                            "type": "upload_progress",
                            "data": {
                                "task_id": task_id,
                                "file_name": file_name,
                                "status": "fail",
                                "error_msg": str(e)[:200],
                            }
                        }
                    )
            except Exception:
                pass
        finally:
            _upload_cancel_events.pop(task_id, None)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass


class CloudFileUploadLocalView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        local_path = reqData.get('local_path', '')
        remote_path = reqData.get('remote_path', '')
        task_id = reqData.get('task_id', '')

        if not account_id or not local_path:
            return ErrorResponse(msg="参数不完整")

        if not os.path.exists(local_path):
            return ErrorResponse(msg="本地文件不存在：{}".format(local_path))

        if os.path.isdir(local_path):
            return ErrorResponse(msg="暂不支持上传目录，请选择文件")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            sdk_info = SDK_DEPS.get(sdk_name, {})
            return ErrorResponse(msg=(
                "无法上传文件：缺少必要的SDK模块。\n\n"
                "📋 需要安装：{display_name}\n"
                "📦 包名：{package}\n"
                "💾 大小：约 {size}\n\n"
                "请先前往「SDK管理」安装对应模块。"
            ).format(
                display_name=sdk_info.get('display_name', sdk_name),
                package=sdk_info.get('package', sdk_name),
                size=sdk_info.get('size_mb', '未知'),
            ))

        if not remote_path:
            filename = os.path.basename(local_path)
            remote_path = account.backup_path.rstrip('/') + '/' + filename

        if not task_id:
            task_id = "cloud_{}_{}".format(int(time.time() * 1000), os.getpid())

        # 后台线程执行上传，API 立即返回
        import threading
        # 注册取消事件
        cancel_event = threading.Event()
        _upload_cancel_events[task_id] = cancel_event

        t = threading.Thread(
            target=self._do_upload,
            args=(account_id, local_path, remote_path, task_id, cancel_event),
            daemon=True,
        )
        t.start()

        return DetailResponse(data={"task_id": task_id}, msg="上传任务已提交")

    @staticmethod
    def _do_upload(account_id, local_path, remote_path, task_id, cancel_event):
        """后台线程执行云存储上传"""
        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
            provider = get_provider(account)

            def progress_callback(uploaded_bytes, total_bytes):
                # 检查是否已取消
                if cancel_event.is_set():
                    raise InterruptedError("上传已取消")
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        progress = round(uploaded_bytes / total_bytes * 100) if total_bytes > 0 else 0
                        async_to_sync(channel_layer.group_send)(
                            "cloud_upload",
                            {
                                "type": "upload_progress",
                                "data": {
                                    "task_id": task_id,
                                    "file_name": os.path.basename(local_path),
                                    "status": "uploading",
                                    "progress": progress,
                                    "uploaded_bytes": uploaded_bytes,
                                    "total_bytes": total_bytes,
                                }
                            }
                        )
                except InterruptedError:
                    raise
                except Exception:
                    pass

            success, msg = provider.upload_file_with_progress(local_path, remote_path, progress_callback)

            if success:
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            "cloud_upload",
                            {
                                "type": "upload_progress",
                                "data": {
                                    "task_id": task_id,
                                    "file_name": os.path.basename(local_path),
                                    "status": "success",
                                    "progress": 100,
                                }
                            }
                        )
                except Exception:
                    pass
            else:
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            "cloud_upload",
                            {
                                "type": "upload_progress",
                                "data": {
                                    "task_id": task_id,
                                    "file_name": os.path.basename(local_path),
                                    "status": "fail",
                                    "error_msg": str(msg)[:200],
                                }
                            }
                        )
                except Exception:
                    pass
        except InterruptedError:
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        "cloud_upload",
                        {
                            "type": "upload_progress",
                            "data": {
                                "task_id": task_id,
                                "file_name": os.path.basename(local_path),
                                "status": "cancelled",
                            }
                        }
                    )
            except Exception:
                pass
        except Exception as e:
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        "cloud_upload",
                        {
                            "type": "upload_progress",
                            "data": {
                                "task_id": task_id,
                                "file_name": os.path.basename(local_path),
                                "status": "fail",
                                "error_msg": str(e)[:200],
                            }
                        }
                    )
            except Exception:
                pass
        finally:
            _upload_cancel_events.pop(task_id, None)


class CloudFileUploadCancelView(CustomAPIView):
    """取消上传任务"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        task_id = reqData.get('task_id', '')
        if not task_id:
            return ErrorResponse(msg="缺少task_id参数")
        cancel_event = _upload_cancel_events.get(task_id)
        if cancel_event:
            cancel_event.set()
            return DetailResponse(msg="已发送取消信号")
        return ErrorResponse(msg="任务不存在或已完成")


class CloudFileDownloadView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        remote_path = reqData.get('remote_path', '')
        local_path = reqData.get('local_path', '')

        if not account_id or not remote_path:
            return ErrorResponse(msg="参数不完整")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        if not local_path:
            local_path = os.path.join(tempfile.gettempdir(), remote_path.split('/')[-1])

        try:
            provider = get_provider(account)
            success, msg = provider.download_file(remote_path, local_path)
            if success:
                return DetailResponse(data={'local_path': local_path}, msg="下载成功")
            return ErrorResponse(msg="下载失败：{}".format(msg))
        except Exception as e:
            return ErrorResponse(msg="下载异常：{}".format(str(e)[:200]))


class CloudFileDeleteView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        remote_path = reqData.get('remote_path', '')

        if not account_id or not remote_path:
            return ErrorResponse(msg="参数不完整")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, msg = provider.delete_file(remote_path)
            if success:
                return DetailResponse(msg="删除成功")
            return ErrorResponse(msg="删除失败：{}".format(msg))
        except Exception as e:
            return ErrorResponse(msg="删除异常：{}".format(str(e)[:200]))


class CloudFileCreateDirView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        remote_path = reqData.get('remote_path', '')

        if not account_id or not remote_path:
            return ErrorResponse(msg="参数不完整")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, msg = provider.create_dir(remote_path)
            if success:
                return DetailResponse(msg="创建目录成功")
            return ErrorResponse(msg="创建目录失败：{}".format(msg))
        except Exception as e:
            return ErrorResponse(msg="创建目录异常：{}".format(str(e)[:200]))


class CloudFileGetUrlView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        remote_path = reqData.get('remote_path', '')
        expires = int(reqData.get('expires', 3600))

        if not account_id or not remote_path:
            return ErrorResponse(msg="参数不完整")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.get_file_url(remote_path, expires=expires)
            if success:
                return DetailResponse(data={'url': result}, msg="获取URL成功")
            return ErrorResponse(msg="获取URL失败：{}".format(result))
        except Exception as e:
            return ErrorResponse(msg="获取URL异常：{}".format(str(e)[:200]))


class CloudFileBucketUsageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.get_bucket_usage()
            if success:
                # 如果API返回的配额为0，使用账号手动设置的配额
                if result.get('total_quota', 0) == 0 and account.storage_quota > 0:
                    result['total_quota'] = account.storage_quota
                return DetailResponse(data=result)
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="获取用量异常：{}".format(str(e)[:200]))


class CloudFileBucketsView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.list_buckets()
            if success:
                return SuccessResponse(data=result)
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="获取存储桶列表异常：{}".format(str(e)[:200]))


class CloudFilePresignedUploadView(CustomAPIView):
    """获取前端直传的预签名上传URL"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        remote_path = reqData.get('remote_path', '')
        content_type = reqData.get('content_type', 'application/octet-stream')

        if not account_id or not remote_path:
            return ErrorResponse(msg="参数不完整")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.get_presigned_upload_url(remote_path, content_type)
            if success:
                return DetailResponse(data=result, msg="获取上传URL成功")
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="获取上传URL异常：{}".format(str(e)[:200]))


class CloudFileDirSizeView(CustomAPIView):
    """计算云存储目录大小"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        dir_path = reqData.get('dir_path', '')

        if not account_id or not dir_path:
            return ErrorResponse(msg="参数不完整")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            # 使用大的 max_keys 一次获取尽可能多的对象
            success, result = provider.list_objects(prefix=dir_path, delimiter='', max_keys=10000)
            if not success:
                return ErrorResponse(msg=result)

            total_size = 0
            file_count = 0
            items = result if isinstance(result, list) else result.get('objects', [])
            for obj in items:
                if not obj.get('is_dir', False):
                    total_size += obj.get('size', 0)
                    file_count += 1
            return DetailResponse(data={'size': total_size, 'file_count': file_count})
        except Exception as e:
            return ErrorResponse(msg="计算目录大小异常：{}".format(str(e)[:200]))


class CloudBucketCorsGetView(CustomAPIView):
    """获取存储桶CORS配置"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        bucket_name = reqData.get('bucket_name', '')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.get_bucket_cors(bucket_name=bucket_name or None)
            if success:
                return DetailResponse(data=result, msg="获取CORS配置成功")
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="获取CORS配置异常：{}".format(str(e)[:200]))


class CloudBucketCorsPutView(CustomAPIView):
    """设置存储桶CORS配置"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        bucket_name = reqData.get('bucket_name', '')
        cors_rules = reqData.get('cors_rules', [])

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")
        if not cors_rules:
            return ErrorResponse(msg="CORS规则不能为空")
        if not isinstance(cors_rules, list):
            try:
                import json
                cors_rules = json.loads(cors_rules) if isinstance(cors_rules, str) else []
            except Exception:
                return ErrorResponse(msg="CORS规则格式错误")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.put_bucket_cors(cors_rules, bucket_name=bucket_name or None)
            if success:
                return DetailResponse(msg=result)
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="设置CORS配置异常：{}".format(str(e)[:200]))


class CloudBucketCorsDeleteView(CustomAPIView):
    """删除存储桶CORS配置"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        bucket_name = reqData.get('bucket_name', '')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.delete_bucket_cors(bucket_name=bucket_name or None)
            if success:
                return DetailResponse(msg=result)
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="删除CORS配置异常：{}".format(str(e)[:200]))


class CloudBucketAclGetView(CustomAPIView):
    """获取存储桶访问权限"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        bucket_name = reqData.get('bucket_name', '')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.get_bucket_acl(bucket_name=bucket_name or None)
            if success:
                return DetailResponse(data=result, msg="获取ACL成功")
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="获取ACL异常：{}".format(str(e)[:200]))


class CloudBucketAclPutView(CustomAPIView):
    """设置存储桶访问权限"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        bucket_name = reqData.get('bucket_name', '')
        acl = reqData.get('acl', 'private')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.put_bucket_acl({'acl': acl}, bucket_name=bucket_name or None)
            if success:
                return DetailResponse(msg=result)
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="设置ACL异常：{}".format(str(e)[:200]))


class CloudMultipartUploadsListView(CustomAPIView):
    """列出存储桶中未完成的分片上传"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        bucket_name = reqData.get('bucket_name', '')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.list_multipart_uploads(bucket_name=bucket_name or None)
            if success:
                return DetailResponse(data=result)
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="获取分片上传列表异常：{}".format(str(e)[:200]))


class CloudMultipartUploadAbortView(CustomAPIView):
    """中止指定的分片上传"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        bucket_name = reqData.get('bucket_name', '')
        upload_id = reqData.get('upload_id', '')
        key = reqData.get('key', '')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")
        if not bucket_name:
            return ErrorResponse(msg="请指定存储桶名称")
        if not upload_id or not key:
            return ErrorResponse(msg="请指定要中止的分片上传ID和对象键")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.abort_multipart_upload(bucket_name, upload_id, key)
            if success:
                return DetailResponse(msg=result)
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="中止分片上传异常：{}".format(str(e)[:200]))


class CloudMultipartUploadAbortAllView(CustomAPIView):
    """中止存储桶中所有未完成的分片上传"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        account_id = reqData.get('account_id')
        bucket_name = reqData.get('bucket_name', '')

        if not account_id:
            return ErrorResponse(msg="请指定云存储账号")

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            return ErrorResponse(msg="缺少SDK模块，请先安装 {}".format(sdk_name))

        try:
            provider = get_provider(account)
            success, result = provider.abort_all_multipart_uploads(bucket_name=bucket_name or None)
            if success:
                return DetailResponse(data=result, msg="已清理{}个未完成的分片上传".format(result.get('aborted_count', 0)))
            return ErrorResponse(msg=result)
        except Exception as e:
            return ErrorResponse(msg="清理分片上传异常：{}".format(str(e)[:200]))
