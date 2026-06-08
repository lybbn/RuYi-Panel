from rest_framework import serializers
from apps.sysdomain.models import DnsAccount, DomainHosting


class DnsAccountSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)

    class Meta:
        model = DnsAccount
        fields = '__all__'
        read_only_fields = ('create_at', 'update_at')


class DnsAccountCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DnsAccount
        fields = ('name', 'provider', 'credentials', 'remark')


class DnsAccountUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DnsAccount
        fields = ('name', 'provider', 'credentials', 'remark')


class DomainHostingSerializer(serializers.ModelSerializer):
    dns_account_name = serializers.CharField(source='dns_account.name', read_only=True, default='')
    provider_display = serializers.CharField(source='dns_account.get_provider_display', read_only=True, default='')
    record_count = serializers.SerializerMethodField()

    class Meta:
        model = DomainHosting
        fields = '__all__'
        read_only_fields = ('create_at', 'update_at')

    def get_record_count(self, obj):
        if not obj.dns_account:
            return obj.record_count or 0
        try:
            from apps.sysdomain.dns_providers.factory import get_provider
            provider = get_provider(obj.dns_account.provider, obj.dns_account.credentials)
            data = provider.get_dns_record(obj.domain, limit=1)
            total = data.get("info", {}).get("record_total", 0)
            if total != obj.record_count:
                DomainHosting.objects.filter(pk=obj.pk).update(record_count=total)
            return total
        except Exception:
            return obj.record_count or 0


class DomainHostingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DomainHosting
        fields = ('dns_account', 'domain', 'domain_id', 'remark')


class DnsRecordSerializer(serializers.Serializer):
    RecordId = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField()
    value = serializers.CharField()
    line = serializers.CharField(required=False, default='默认')
    ttl = serializers.IntegerField(required=False, default=600)
    type = serializers.CharField()
    status = serializers.CharField(required=False, default='enable')
    mx = serializers.IntegerField(required=False, default=0)
    updated_on = serializers.CharField(required=False, allow_blank=True)
    remark = serializers.CharField(required=False, allow_blank=True)
