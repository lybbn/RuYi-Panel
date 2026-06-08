from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from utils.common import get_parameter_dic
from apps.syscloud.cloud_providers.sdk_manager import SDKManager, SDK_DEPS
import platform


class CloudSdkListView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = SDKManager.get_all_sdk_status()
        for item in data:
            item['install_status'] = 1 if item.get('installed') else 0
            item['provider_keys'] = ','.join(item.get('providers', []))
            if item.get('sdk_type') == 'tool' and item['sdk_name'] == 'rclone':
                item['fuse_available'] = SDKManager._check_fuse_available()
        return SuccessResponse(data=data)


class CloudSdkInstallView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        sdk_name = reqData.get('sdk_name', '')

        if not sdk_name:
            return ErrorResponse(msg="请指定SDK名称")

        if sdk_name not in SDK_DEPS:
            return ErrorResponse(msg="未知的SDK: {}".format(sdk_name))

        if SDKManager.check_installed(sdk_name):
            return DetailResponse(msg="SDK已安装，无需重复安装")

        sdk_info = SDK_DEPS.get(sdk_name, {})
        success, msg = SDKManager.install_sdk(sdk_name)
        if success:
            return DetailResponse(msg="安装成功：{}".format(msg))
        return ErrorResponse(msg="安装失败：{}".format(msg))


class CloudSdkUninstallView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reqData = get_parameter_dic(request)
        sdk_name = reqData.get('sdk_name', '')

        if not sdk_name:
            return ErrorResponse(msg="请指定SDK名称")

        if sdk_name not in SDK_DEPS:
            return ErrorResponse(msg="未知的SDK: {}".format(sdk_name))

        if not SDKManager.check_installed(sdk_name):
            return DetailResponse(msg="SDK未安装")

        success, msg = SDKManager.uninstall_sdk(sdk_name)
        if success:
            return DetailResponse(msg="卸载成功")
        return ErrorResponse(msg="卸载失败：{}".format(msg))


class CloudSdkCheckView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sdk_name = request.query_params.get('sdk_name', '')
        if not sdk_name:
            return ErrorResponse(msg="请指定SDK名称")

        installed = SDKManager.check_installed(sdk_name)
        version = SDKManager.get_installed_version(sdk_name) if installed else ''
        sdk_info = SDK_DEPS.get(sdk_name, {})

        data = {
            'sdk_name': sdk_name,
            'installed': installed,
            'version': version,
            'display_name': sdk_info.get('display_name', sdk_name),
            'description': sdk_info.get('description', ''),
            'size_mb': sdk_info.get('size_mb', ''),
            'providers': sdk_info.get('providers', []),
            'sdk_type': sdk_info.get('sdk_type', 'pip'),
        }
        if sdk_info.get('sdk_type') == 'tool' and sdk_name == 'rclone':
            data['fuse_available'] = SDKManager._check_fuse_available()
            data['os'] = platform.system()
        return DetailResponse(data=data)
