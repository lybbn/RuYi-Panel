import json
from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from utils.common import get_parameter_dic
from apps.syscloud.models import CloudStorageAccount, CloudSdkRecord
from apps.syscloud.serializers import (
    CloudStorageAccountSerializer,
    CloudStorageAccountCreateSerializer,
    CloudStorageAccountUpdateSerializer,
)
from apps.syscloud.cloud_providers.factory import (
    get_provider, get_provider_info, get_all_providers, PROVIDER_REGISTRY,
)
from apps.syscloud.cloud_providers.sdk_manager import SDKManager, SDK_DEPS, get_sdk_for_provider
from django.utils import timezone


class CloudProviderListView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        providers = get_all_providers()
        for p in providers:
            sdk_name = p['sdk']
            p['sdk_installed'] = SDKManager.check_installed(sdk_name)
            sdk_info = SDK_DEPS.get(sdk_name, {})
            p['sdk_display_name'] = sdk_info.get('display_name', sdk_name)
            p['sdk_size_mb'] = sdk_info.get('size_mb', '')
            p['sdk_description'] = sdk_info.get('description', '')
        return DetailResponse(data=providers)


class CloudAccountListView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = CloudStorageAccount.objects.all().order_by('-create_at')
        from utils.pagination import CustomPagination
        page_obj = CustomPagination()
        page_data = page_obj.paginate_queryset(accounts, request)
        serializer = CloudStorageAccountSerializer(page_data, many=True)
        return page_obj.get_paginated_response(serializer.data)


class CloudAccountDetailView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            account = CloudStorageAccount.objects.get(pk=pk)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")
        serializer = CloudStorageAccountSerializer(account)
        return DetailResponse(data=serializer.data)

    def put(self, request, pk):
        try:
            account = CloudStorageAccount.objects.get(pk=pk)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")
        serializer = CloudStorageAccountUpdateSerializer(account, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if account.is_default:
            CloudStorageAccount.objects.filter(
                is_default=True
            ).exclude(id=account.id).update(is_default=False)
        return DetailResponse(data=CloudStorageAccountSerializer(account).data, msg="更新成功")

    def delete(self, request, pk):
        try:
            account = CloudStorageAccount.objects.get(pk=pk)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")
        account.delete()
        return DetailResponse(msg="删除成功")


class CloudAccountCreateView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CloudStorageAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider_key = serializer.validated_data.get('provider')
        provider_info = get_provider_info(provider_key)
        if not provider_info:
            return ErrorResponse(msg="不支持的云厂商: {}".format(provider_key))

        protocol = provider_info.get('protocol', 's3')
        sdk_name = provider_info.get('sdk')
        sdk_installed = SDKManager.check_installed(sdk_name)

        account = serializer.save(protocol=protocol, sdk_installed=sdk_installed)

        if not sdk_installed:
            from utils.common import pip_install_package
            sdk_info = SDK_DEPS.get(sdk_name, {})
            package_name = sdk_info.get('package', sdk_name)
            success, _ = pip_install_package(package_name)
            if success:
                account.sdk_installed = True
                account.save(update_fields=['sdk_installed'])
                SDKManager.install_sdk(sdk_name)

        if account.is_default:
            CloudStorageAccount.objects.filter(
                is_default=True
            ).exclude(id=account.id).update(is_default=False)

        return DetailResponse(
            data=CloudStorageAccountSerializer(account).data,
            msg="创建成功",
        )


class CloudAccountTestConnectionView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            account = CloudStorageAccount.objects.get(pk=pk)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")

        sdk_name = get_sdk_for_provider(account.provider)
        if not SDKManager.check_installed(sdk_name):
            sdk_info = SDK_DEPS.get(sdk_name, {})
            return ErrorResponse(msg=(
                "无法测试连接：缺少必要的SDK模块。\n\n"
                "📋 需要安装：{display_name}\n"
                "📦 包名：{package}\n"
                "💾 大小：约 {size}\n"
                "📝 说明：{desc}\n\n"
                "请先前往「SDK管理」安装对应模块后再测试连接。"
            ).format(
                display_name=sdk_info.get('display_name', sdk_name),
                package=sdk_info.get('package', sdk_name),
                size=sdk_info.get('size_mb', '未知'),
                desc=sdk_info.get('description', ''),
            ))

        try:
            provider = get_provider(account)
            success, msg = provider.test_connection()
            account.last_test_time = timezone.now()
            account.status = 0 if success else 1
            account.save(update_fields=['last_test_time', 'status'])
            if success:
                return DetailResponse(msg="连接测试成功：{}".format(msg))
            return ErrorResponse(msg="连接测试失败：{}".format(msg))
        except Exception as e:
            return ErrorResponse(msg="连接测试异常：{}".format(str(e)[:200]))


class CloudAccountCheckSdkView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        provider_key = request.query_params.get('provider', '')
        if not provider_key:
            return ErrorResponse(msg="请指定云厂商")
        provider_info = get_provider_info(provider_key)
        if not provider_info:
            return ErrorResponse(msg="不支持的云厂商: {}".format(provider_key))

        sdk_name = provider_info.get('sdk')
        installed = SDKManager.check_installed(sdk_name)
        sdk_info = SDK_DEPS.get(sdk_name, {})

        data = {
            'provider': provider_key,
            'provider_name': provider_info.get('name', ''),
            'sdk_name': sdk_name,
            'sdk_installed': installed,
            'sdk_display_name': sdk_info.get('display_name', sdk_name),
            'sdk_package': sdk_info.get('package', sdk_name),
            'sdk_size_mb': sdk_info.get('size_mb', ''),
            'sdk_description': sdk_info.get('description', ''),
            'need_install': not installed,
        }
        return DetailResponse(data=data)


class CloudAccountSetDefaultView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            account = CloudStorageAccount.objects.get(pk=pk)
        except CloudStorageAccount.DoesNotExist:
            return ErrorResponse(msg="账号不存在")
        CloudStorageAccount.objects.filter(is_default=True).update(is_default=False)
        account.is_default = True
        account.save(update_fields=['is_default'])
        return DetailResponse(msg="已设为默认备份账号")


EXPORT_FIELDS = [
    'name', 'provider', 'protocol', 'access_key', 'secret_key',
    'endpoint', 'region', 'bucket', 'backup_path', 'extra_config',
    'is_default', 'remark', 'storage_quota',
]


class CloudAccountExportView(CustomAPIView):
    """导出云存储账号配置为JSON文件"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = CloudStorageAccount.objects.all().order_by('-create_at')
        export_data = []
        for account in accounts:
            item = {}
            for field in EXPORT_FIELDS:
                value = getattr(account, field, '')
                if isinstance(value, bool):
                    item[field] = value
                elif value is None:
                    item[field] = ''
                else:
                    item[field] = str(value)
            export_data.append(item)

        content = json.dumps({
            'version': '1.0',
            'type': 'ruyi_cloud_accounts',
            'data': export_data,
        }, ensure_ascii=False, indent=2)

        response = HttpResponse(content, content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="ruyi_cloud_accounts.json"'
        return response


class CloudAccountImportView(CustomAPIView):
    """从JSON文件导入云存储账号配置"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return ErrorResponse(msg="请上传配置文件")

        if file_obj.size > 5 * 1024 * 1024:
            return ErrorResponse(msg="文件大小不能超过5MB")

        try:
            content = file_obj.read().decode('utf-8')
            data = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ErrorResponse(msg="文件格式错误，请上传有效的JSON配置文件")

        if isinstance(data, dict):
            file_type = data.get('type', '')
            items = data.get('data', [])
            if file_type != 'ruyi_cloud_accounts' or not isinstance(items, list):
                return ErrorResponse(msg="配置文件格式不正确，请上传如意面板云账号配置文件")
        elif isinstance(data, list):
            items = data
        else:
            return ErrorResponse(msg="配置文件格式不正确")

        if not items:
            return ErrorResponse(msg="配置文件中没有账号数据")

        import_mode = request.data.get('import_mode') or request.POST.get('import_mode', 'skip')
        success_count = 0
        skip_count = 0
        error_list = []

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                error_list.append("第{}条数据格式错误".format(idx + 1))
                continue

            provider = item.get('provider', '')
            if provider not in PROVIDER_REGISTRY:
                error_list.append("第{}条：不支持的云厂商「{}」".format(idx + 1, provider))
                continue

            name = item.get('name', '').strip()
            if not name:
                error_list.append("第{}条：账号名称为空".format(idx + 1))
                continue

            access_key = item.get('access_key', '').strip()
            secret_key = item.get('secret_key', '').strip()
            if not access_key or not secret_key:
                error_list.append("第{}条「{}」：AccessKey或SecretKey为空".format(idx + 1, name))
                continue

            existing = CloudStorageAccount.objects.filter(
                provider=provider, access_key=access_key
            ).first()

            if existing:
                if import_mode == 'skip':
                    skip_count += 1
                    continue
                elif import_mode == 'overwrite':
                    for field in EXPORT_FIELDS:
                        if field in ('provider', 'access_key'):
                            continue
                        value = item.get(field, '')
                        if field == 'secret_key' and not value:
                            continue
                        setattr(existing, field, value)
                    provider_info = get_provider_info(provider)
                    if provider_info:
                        sdk_name = provider_info.get('sdk')
                        existing.sdk_installed = SDKManager.check_installed(sdk_name)
                        existing.protocol = provider_info.get('protocol', 's3')
                    existing.save()
                    success_count += 1
                    continue

            provider_info = get_provider_info(provider)
            protocol = provider_info.get('protocol', 's3') if provider_info else 's3'
            sdk_name = provider_info.get('sdk') if provider_info else ''
            sdk_installed = SDKManager.check_installed(sdk_name) if sdk_name else False

            create_data = {}
            for field in EXPORT_FIELDS:
                value = item.get(field, '')
                if value != '':
                    create_data[field] = value

            try:
                serializer = CloudStorageAccountCreateSerializer(data=create_data)
                serializer.is_valid(raise_exception=True)
                serializer.save(protocol=protocol, sdk_installed=sdk_installed)
                success_count += 1
            except Exception as e:
                error_list.append("第{}条「{}」：{}".format(idx + 1, name, str(e)[:100]))

        msg_parts = []
        if success_count > 0:
            msg_parts.append("成功导入{}个账号".format(success_count))
        if skip_count > 0:
            msg_parts.append("跳过{}个已存在账号".format(skip_count))
        if error_list:
            msg_parts.append("{}条失败".format(len(error_list)))

        result_data = {
            'success_count': success_count,
            'skip_count': skip_count,
            'error_count': len(error_list),
            'errors': error_list[:20],
        }

        if success_count == 0 and skip_count == 0 and error_list:
            return ErrorResponse(msg="导入失败：" + "；".join(error_list[:5]), data=result_data)

        return DetailResponse(data=result_data, msg="，".join(msg_parts) if msg_parts else "导入完成")
