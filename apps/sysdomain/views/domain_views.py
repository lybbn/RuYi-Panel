import json
from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db.models import F
from utils.viewset import CustomModelViewSet
from utils.customView import CustomAPIView
from utils.jsonResponse import SuccessResponse, DetailResponse, ErrorResponse
from utils.common import get_parameter_dic
from apps.sysdomain.models import DnsAccount, DomainHosting
from apps.sysdomain.serializers import (
    DnsAccountSerializer, DnsAccountCreateSerializer, DnsAccountUpdateSerializer,
    DomainHostingSerializer, DomainHostingCreateSerializer,
)
from apps.sysdomain.dns_providers.factory import get_provider, get_provider_params, PROVIDER_MAP, get_provider_line_ttl
from apps.sysdomain.cdn_providers.factory import get_cdn_provider, get_cdn_provider_info, get_all_cdn_providers


class DnsAccountViewSet(CustomModelViewSet):
    queryset = DnsAccount.objects.all()
    serializer_class = DnsAccountSerializer
    create_serializer_class = DnsAccountCreateSerializer
    update_serializer_class = DnsAccountUpdateSerializer
    search_fields = ('name', 'provider')
    ordering_fields = ('create_at',)

    @action(methods=['GET'], detail=False)
    def provider_list(self, request):
        data = get_provider_params()
        return DetailResponse(data=data)

    @action(methods=['POST'], detail=True)
    def test_connection(self, request, pk=None):
        instance = self.get_object()
        try:
            provider = get_provider(instance.provider, instance.credentials)
            result = provider.get_domain_list()
            if result.get("status"):
                return DetailResponse(msg="Connection successful")
            return ErrorResponse(msg=result.get("msg", "Connection failed"))
        except Exception as e:
            return ErrorResponse(msg=str(e))

    @action(methods=['POST'], detail=True)
    def sync_domains(self, request, pk=None):
        instance = self.get_object()
        try:
            provider = get_provider(instance.provider, instance.credentials)
            result = provider.get_domain_list()
            if not result.get("status"):
                return ErrorResponse(msg=result.get("msg", "Failed to get domain list"))
            synced = 0
            for item in result.get("data", []):
                obj, created = DomainHosting.objects.update_or_create(
                    dns_account=instance,
                    domain=item["name"],
                    defaults={
                        "domain_id": item.get("id", ""),
                        "remark": item.get("remark", ""),
                        "record_count": item.get("record_count", 0),
                    }
                )
                synced += 1
            return DetailResponse(msg="Synced {} domains".format(synced))
        except Exception as e:
            return ErrorResponse(msg=str(e))


class DomainHostingViewSet(CustomModelViewSet):
    queryset = DomainHosting.objects.all()
    serializer_class = DomainHostingSerializer
    create_serializer_class = DomainHostingCreateSerializer
    search_fields = ('domain',)
    ordering_fields = ('create_at',)
    filterset_fields = ('dns_account',)

    @action(methods=['GET'], detail=True)
    def record_config(self, request, pk=None):
        instance = self.get_object()
        if not instance.dns_account:
            return DetailResponse(data={'lines': [{'value': '默认', 'label': '默认'}], 'ttl': [{'value': 600, 'label': '10 分钟'}]})
        data = get_provider_line_ttl(instance.dns_account.provider)
        return DetailResponse(data=data)

    @action(methods=['GET'], detail=True)
    def records(self, request, pk=None):
        instance = self.get_object()
        if not instance.dns_account:
            return ErrorResponse(msg="No DNS account configured")
        try:
            provider = get_provider(instance.dns_account.provider, instance.dns_account.credentials)
            kwargs = {}
            if request.query_params.get("limit"):
                kwargs["limit"] = request.query_params["limit"]
            if request.query_params.get("page"):
                kwargs["page"] = request.query_params["page"]
            if request.query_params.get("search"):
                kwargs["search"] = request.query_params["search"]
            data = provider.get_dns_record(instance.domain, **kwargs)
            return DetailResponse(data=data)
        except Exception as e:
            return ErrorResponse(msg=str(e))

    @action(methods=['POST'], detail=True)
    def add_record(self, request, pk=None):
        instance = self.get_object()
        if not instance.dns_account:
            return ErrorResponse(msg="No DNS account configured")
        record_type = request.data.get("type")
        value = request.data.get("value")
        name = request.data.get("name", instance.domain)
        if not record_type or not value:
            return ErrorResponse(msg="type and value are required")
        try:
            provider = get_provider(instance.dns_account.provider, instance.dns_account.credentials)
            kwargs = {
                "remark": request.data.get("remark", ""),
                "mx": request.data.get("mx", 0),
                "ttl": request.data.get("ttl", 600),
                "record_line": request.data.get("line", "默认"),
            }
            result = provider.create_dns_record(name, record_type, value, **kwargs)
            if result.get("status"):
                DomainHosting.objects.filter(pk=instance.pk).update(record_count=F('record_count') + 1)
                return DetailResponse(msg="Record created")
            return ErrorResponse(msg=result.get("msg", "Failed to create record"))
        except Exception as e:
            return ErrorResponse(msg=str(e))

    @action(methods=['POST'], detail=True)
    def delete_record(self, request, pk=None):
        instance = self.get_object()
        if not instance.dns_account:
            return ErrorResponse(msg="No DNS account configured")
        record_id = request.data.get("record_id")
        if not record_id:
            return ErrorResponse(msg="record_id is required")
        try:
            provider = get_provider(instance.dns_account.provider, instance.dns_account.credentials)
            result = provider.delete_dns_record(instance.domain, record_id)
            if result.get("status"):
                DomainHosting.objects.filter(pk=instance.pk, record_count__gt=0).update(record_count=F('record_count') - 1)
                return DetailResponse(msg="Record deleted")
            return ErrorResponse(msg=result.get("msg", "Failed to delete record"))
        except Exception as e:
            return ErrorResponse(msg=str(e))

    @action(methods=['POST'], detail=True)
    def update_record(self, request, pk=None):
        instance = self.get_object()
        if not instance.dns_account:
            return ErrorResponse(msg="No DNS account configured")
        record_id = request.data.get("record_id")
        record_type = request.data.get("type")
        value = request.data.get("value")
        name = request.data.get("name", instance.domain)
        if not record_id or not record_type or not value:
            return ErrorResponse(msg="record_id, type and value are required")
        try:
            provider = get_provider(instance.dns_account.provider, instance.dns_account.credentials)
            kwargs = {
                "remark": request.data.get("remark", ""),
                "mx": request.data.get("mx", 0),
                "ttl": request.data.get("ttl", 600),
                "record_line": request.data.get("line", "默认"),
                "old_value": request.data.get("old_value", ""),
            }
            result = provider.update_dns_record(name, record_id, record_type, value, **kwargs)
            if result.get("status"):
                return DetailResponse(msg="Record updated")
            return ErrorResponse(msg=result.get("msg", "Failed to update record"))
        except Exception as e:
            return ErrorResponse(msg=str(e))

    @action(methods=['POST'], detail=True)
    def toggle_record(self, request, pk=None):
        instance = self.get_object()
        if not instance.dns_account:
            return ErrorResponse(msg="No DNS account configured")
        record_id = request.data.get("record_id")
        status = request.data.get("status", 0)
        if not record_id:
            return ErrorResponse(msg="record_id is required")
        try:
            provider = get_provider(instance.dns_account.provider, instance.dns_account.credentials)
            result = provider.set_dns_record_status(instance.domain, record_id, status)
            if result.get("status"):
                return DetailResponse(msg="Record status updated")
            return ErrorResponse(msg=result.get("msg", "Failed to update record status"))
        except Exception as e:
            return ErrorResponse(msg=str(e))

    def _get_cdn_provider(self, instance):
        """获取域名对应的CDN管理实例"""
        if not instance.dns_account:
            return None, ErrorResponse(msg="该域名未关联DNS账号")
        cdn = get_cdn_provider(
            instance.dns_account,
            zone_id=instance.domain_id,
            domain_name=instance.domain
        )
        if not cdn:
            return None, ErrorResponse(msg="该DNS服务商暂不支持CDN缓存管理")
        return cdn, None

    @action(methods=['GET'], detail=True)
    def cdn_info(self, request, pk=None):
        """获取域名CDN缓存功能信息"""
        instance = self.get_object()
        if not instance.dns_account:
            return DetailResponse(data={'supported': False, 'msg': '未关联DNS账号'})
        provider_info = get_cdn_provider_info(instance.dns_account.provider)
        if not provider_info:
            return DetailResponse(data={'supported': False, 'msg': '该DNS服务商暂不支持CDN缓存管理'})
        provider_info['supported'] = True
        return DetailResponse(data=provider_info)

    @action(methods=['POST'], detail=True)
    def cdn_purge(self, request, pk=None):
        """CDN缓存刷新"""
        instance = self.get_object()
        cdn, err = self._get_cdn_provider(instance)
        if err:
            return err

        req_data = get_parameter_dic(request)
        purge_type = req_data.get('purge_type', 'url')  # url / all / tag

        if purge_type == 'all':
            if not cdn.supports_purge_all:
                return ErrorResponse(msg="该厂商不支持全量刷新")
            result = cdn.purge_all()
        elif purge_type == 'tag':
            if not cdn.supports_purge_tag:
                return ErrorResponse(msg="该厂商不支持按标签刷新")
            tags = req_data.get('tags', [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',') if t.strip()]
            if not tags:
                return ErrorResponse(msg="请输入Cache-Tag")
            result = cdn.purge_tags(tags)
        else:
            if not cdn.supports_purge_url:
                return ErrorResponse(msg="该厂商不支持按URL刷新")
            urls = req_data.get('urls', [])
            if isinstance(urls, str):
                urls = [u.strip() for u in urls.split('\n') if u.strip()]
            if not urls:
                return ErrorResponse(msg="请输入URL列表")
            result = cdn.purge_urls(urls)

        if result.get("status"):
            return DetailResponse(msg=result.get("msg", "缓存刷新提交成功"))
        return ErrorResponse(msg=result.get("msg", "缓存刷新失败"))

    @action(methods=['POST'], detail=True)
    def cdn_preload(self, request, pk=None):
        """CDN缓存预热"""
        instance = self.get_object()
        cdn, err = self._get_cdn_provider(instance)
        if err:
            return err

        if not cdn.supports_preload:
            return ErrorResponse(msg="该厂商不支持缓存预热")

        req_data = get_parameter_dic(request)
        urls = req_data.get('urls', [])
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split('\n') if u.strip()]
        if not urls:
            return ErrorResponse(msg="请输入预热URL列表")

        result = cdn.preload_urls(urls)
        if result.get("status"):
            return DetailResponse(msg=result.get("msg", "缓存预热提交成功"))
        return ErrorResponse(msg=result.get("msg", "缓存预热失败"))

    @action(methods=['GET'], detail=True)
    def cdn_quota(self, request, pk=None):
        """查询CDN刷新配额"""
        instance = self.get_object()
        cdn, err = self._get_cdn_provider(instance)
        if err:
            return err

        if not cdn.supports_quota:
            return ErrorResponse(msg="该厂商不支持查询刷新配额")

        result = cdn.get_purge_quota()
        if result.get("status"):
            return DetailResponse(data=result.get("data", {}))
        return ErrorResponse(msg=result.get("msg", "查询配额失败"))

    @action(methods=['GET'], detail=True)
    def cdn_zone_info(self, request, pk=None):
        """获取CDN Zone信息"""
        instance = self.get_object()
        cdn, err = self._get_cdn_provider(instance)
        if err:
            return err

        result = cdn.get_zone_info()
        if result.get("status"):
            return DetailResponse(data=result.get("data", {}))
        return ErrorResponse(msg=result.get("msg", "获取Zone信息失败"))


class DnsProviderInfoView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_provider_params()
        return DetailResponse(data=data)


class CdnProviderListView(CustomAPIView):
    """CDN厂商列表"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_all_cdn_providers()
        return DetailResponse(data=data)


DNS_EXPORT_FIELDS = ['name', 'provider', 'credentials', 'remark']


class DnsAccountExportView(CustomAPIView):
    """导出DNS账号配置为JSON文件"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        accounts = DnsAccount.objects.all().order_by('-create_at')
        export_data = []
        for account in accounts:
            item = {}
            for field in DNS_EXPORT_FIELDS:
                value = getattr(account, field, '')
                if value is None:
                    item[field] = ''
                elif isinstance(value, dict):
                    item[field] = value
                else:
                    item[field] = str(value)
            export_data.append(item)

        content = json.dumps({
            'version': '1.0',
            'type': 'ruyi_dns_accounts',
            'data': export_data,
        }, ensure_ascii=False, indent=2)

        response = HttpResponse(content, content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="ruyi_dns_accounts.json"'
        return response


class DnsAccountImportView(CustomAPIView):
    """从JSON文件导入DNS账号配置"""
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
            if file_type != 'ruyi_dns_accounts' or not isinstance(items, list):
                return ErrorResponse(msg="配置文件格式不正确，请上传如意面板DNS账号配置文件")
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
            if provider not in PROVIDER_MAP:
                error_list.append("第{}条：不支持的DNS服务商「{}」".format(idx + 1, provider))
                continue

            name = item.get('name', '').strip()
            if not name:
                error_list.append("第{}条：账号名称为空".format(idx + 1))
                continue

            credentials = item.get('credentials', {})
            if not credentials or not isinstance(credentials, dict):
                error_list.append("第{}条「{}」：认证凭据为空或格式错误".format(idx + 1, name))
                continue

            existing = DnsAccount.objects.filter(
                provider=provider, name=name
            ).first()

            if existing:
                if import_mode == 'skip':
                    skip_count += 1
                    continue
                elif import_mode == 'overwrite':
                    existing.credentials = credentials
                    existing.remark = item.get('remark', '') or existing.remark
                    existing.save()
                    success_count += 1
                    continue

            try:
                create_data = {
                    'name': name,
                    'provider': provider,
                    'credentials': credentials,
                    'remark': item.get('remark', ''),
                }
                serializer = DnsAccountCreateSerializer(data=create_data)
                serializer.is_valid(raise_exception=True)
                serializer.save()
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
