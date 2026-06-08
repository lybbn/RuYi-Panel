from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from utils.common import get_parameter_dic
from apps.syscloud.models import CloudMountRecord, CloudStorageAccount
from apps.syscloud.serializers import (
    CloudMountRecordSerializer,
    CloudMountRecordCreateSerializer,
)
from apps.syscloud.mount.mount_manager import (
    mount_cloud_storage, unmount_cloud_storage, get_mount_status,
    check_rclone_installed, check_fuse_available, get_mount_base_path,
)
import platform


class CloudMountListView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        records = CloudMountRecord.objects.all().order_by('-create_at')
        data = []
        for record in records:
            item = CloudMountRecordSerializer(record).data
            status_str = get_mount_status(record.mount_path)
            if status_str == 'mounted':
                item['actual_status'] = 1
            elif status_str == 'error':
                item['actual_status'] = 2
            else:
                item['actual_status'] = 0
            data.append(item)
        return SuccessResponse(data=data)


class CloudMountCreateView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CloudMountRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account_id = serializer.validated_data.get('account')
        mount_path = serializer.validated_data.get('mount_path')

        try:
            account = CloudStorageAccount.objects.get(pk=account_id)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="云存储账号不存在")

        if not mount_path:
            base = get_mount_base_path()
            mount_path = "{}/{}_{}".format(base, account.provider, account.id)

        existing = CloudMountRecord.objects.filter(
            account=account, mount_path=mount_path
        ).first()
        if existing:
            return ErrorResponse(msg="该账号已存在相同的挂载记录")

        mount_options = serializer.validated_data.get('mount_options', '')
        success, msg = mount_cloud_storage(account, mount_path, options=mount_options or None)
        mount_status = 1 if success else 2

        record = CloudMountRecord.objects.create(
            account=account,
            mount_path=mount_path,
            mount_status=mount_status,
            mount_options=mount_options,
            auto_mount=serializer.validated_data.get('auto_mount', False),
        )
        if success:
            return DetailResponse(
                data=CloudMountRecordSerializer(record).data,
                msg="挂载成功，路径：{}".format(mount_path),
            )
        return DetailResponse(
            data=CloudMountRecordSerializer(record).data,
            msg="挂载记录已创建，但挂载失败：{}".format(msg),
        )


class CloudMountMountView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            record = CloudMountRecord.objects.get(pk=pk)
        except CloudMountRecord.DoesNotExist:
            return ErrorResponse(msg="挂载记录不存在")

        account = record.account
        success, msg = mount_cloud_storage(account, record.mount_path, options=record.mount_options or None)
        if success:
            record.mount_status = 1
            record.save(update_fields=['mount_status'])
            return DetailResponse(msg="挂载成功，路径：{}".format(record.mount_path))
        record.mount_status = 2
        record.save(update_fields=['mount_status'])
        return ErrorResponse(msg="挂载失败：{}".format(msg))


class CloudMountUnmountView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            record = CloudMountRecord.objects.get(pk=pk)
        except CloudMountRecord.DoesNotExist:
            return ErrorResponse(msg="挂载记录不存在")

        success, msg = unmount_cloud_storage(record.mount_path)
        if success:
            record.mount_status = 0
            record.save(update_fields=['mount_status'])
            return DetailResponse(msg="卸载成功")
        return ErrorResponse(msg="卸载失败：{}".format(msg))


class CloudMountDeleteView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            record = CloudMountRecord.objects.get(pk=pk)
        except CloudMountRecord.DoesNotExist:
            return ErrorResponse(msg="挂载记录不存在")

        mount_path = request.data.get('mount_path', '')
        mount_options = request.data.get('mount_options', '')
        auto_mount = request.data.get('auto_mount', False)
        account_id = request.data.get('account', None)

        if mount_path:
            record.mount_path = mount_path
        if mount_options is not None:
            record.mount_options = mount_options
        record.auto_mount = auto_mount

        if account_id:
            try:
                account = CloudStorageAccount.objects.get(pk=account_id)
                record.account = account
            except CloudStorageAccount.DoesNotExist:
                return ErrorResponse(msg="云存储账号不存在")

        record.save()
        return DetailResponse(data=CloudMountRecordSerializer(record).data, msg="更新成功")

    def delete(self, request, pk):
        try:
            record = CloudMountRecord.objects.get(pk=pk)
        except CloudMountRecord.DoesNotExist:
            return ErrorResponse(msg="挂载记录不存在")

        actual_status_str = get_mount_status(record.mount_path)
        if actual_status_str == 'mounted':
            return ErrorResponse(msg="请先卸载后再删除")

        record.delete()
        return DetailResponse(msg="删除成功")


class CloudMountCheckEnvView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            'os': platform.system(),
            'rclone_installed': check_rclone_installed(),
            'fuse_available': check_fuse_available(),
            'mount_base_path': get_mount_base_path(),
        }
        if not data['rclone_installed']:
            data['install_guide'] = (
                "rclone未安装。请前往「SDK管理」页面一键安装rclone，"
                "或手动安装：\n"
                "Linux: curl https://rclone.org/install.sh | sudo bash\n"
                "Windows: 访问 https://rclone.org/downloads/ 下载安装\n"
                "或执行: winget install Rclone.Rclone"
            )
        if not data['fuse_available']:
            if platform.system() == 'Windows':
                data['fuse_guide'] = (
                    "WinFSP未安装。Windows挂载需要WinFSP支持。\n"
                    "下载地址: https://winfsp.dev/rel/\n"
                    "安装后重启面板服务即可。"
                )
            else:
                data['fuse_guide'] = (
                    "FUSE未安装。Linux挂载需要FUSE支持。\n"
                    "Ubuntu/Debian: apt install fuse3\n"
                    "CentOS/RHEL: yum install fuse3"
                )
        return DetailResponse(data=data)
