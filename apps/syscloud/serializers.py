from rest_framework import serializers
from .models import CloudStorageAccount, CloudMountRecord, CloudSdkRecord


class CloudStorageAccountSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    protocol_display = serializers.CharField(source='get_protocol_display', read_only=True)
    secret_key = serializers.SerializerMethodField()

    class Meta:
        model = CloudStorageAccount
        fields = [
            'id', 'name', 'provider', 'provider_display', 'protocol', 'protocol_display',
            'access_key', 'secret_key', 'endpoint', 'region', 'bucket',
            'backup_path', 'extra_config', 'is_default', 'status',
            'last_test_time', 'sdk_installed', 'remark', 'storage_quota',
            'create_at', 'update_at',
        ]
        read_only_fields = ['id', 'create_at', 'update_at', 'last_test_time', 'sdk_installed']

    def get_secret_key(self, obj):
        if obj.secret_key:
            length = len(obj.secret_key)
            if length <= 8:
                return '*' * length
            return obj.secret_key[:4] + '*' * (length - 8) + obj.secret_key[-4:]
        return ''


class CloudStorageAccountCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudStorageAccount
        fields = [
            'name', 'provider', 'access_key', 'secret_key',
            'endpoint', 'region', 'bucket', 'backup_path',
            'extra_config', 'is_default', 'remark', 'storage_quota',
        ]

    def validate_provider(self, value):
        from .cloud_providers.factory import PROVIDER_REGISTRY
        if value not in PROVIDER_REGISTRY:
            raise serializers.ValidationError("不支持的云厂商: {}".format(value))
        return value

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("账号名称不能为空")
        return value.strip()

    def validate_endpoint(self, value):
        if value:
            value = value.strip().strip('`').strip()
        return value

    def validate_region(self, value):
        if value:
            value = value.strip()
        return value

    def validate_bucket(self, value):
        if value:
            value = value.strip()
        return value

    def validate_access_key(self, value):
        if value:
            value = value.strip()
        return value


class CloudStorageAccountUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudStorageAccount
        fields = [
            'name', 'access_key', 'secret_key', 'endpoint', 'region',
            'bucket', 'backup_path', 'extra_config', 'is_default', 'remark', 'storage_quota',
        ]

    def validate_endpoint(self, value):
        if value:
            value = value.strip().strip('`').strip()
        return value

    def validate_region(self, value):
        if value:
            value = value.strip()
        return value

    def validate_bucket(self, value):
        if value:
            value = value.strip()
        return value

    def validate_access_key(self, value):
        if value:
            value = value.strip()
        return value

    def update(self, instance, validated_data):
        if not validated_data.get('secret_key'):
            validated_data.pop('secret_key', None)
        return super().update(instance, validated_data)


class CloudMountRecordSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    provider_display = serializers.CharField(source='account.get_provider_display', read_only=True)
    provider = serializers.CharField(source='account.provider', read_only=True)
    mount_status_display = serializers.CharField(source='get_mount_status_display', read_only=True)

    class Meta:
        model = CloudMountRecord
        fields = [
            'id', 'account', 'account_name', 'provider_display', 'provider',
            'mount_path', 'mount_status', 'mount_status_display',
            'mount_options', 'auto_mount', 'create_at', 'update_at',
        ]
        read_only_fields = ['id', 'create_at', 'update_at']


class CloudMountRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudMountRecord
        fields = ['account', 'mount_path', 'mount_options', 'auto_mount']


class CloudSdkRecordSerializer(serializers.ModelSerializer):
    sdk_display = serializers.CharField(source='get_sdk_name_display', read_only=True)
    install_status_display = serializers.CharField(source='get_install_status_display', read_only=True)

    class Meta:
        model = CloudSdkRecord
        fields = [
            'id', 'sdk_name', 'sdk_display', 'sdk_version',
            'install_status', 'install_status_display',
            'install_time', 'provider_keys', 'error_msg',
            'create_at', 'update_at',
        ]
