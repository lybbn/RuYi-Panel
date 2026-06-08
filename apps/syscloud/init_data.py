def init_cloud_sdk_data(force=False):
    from apps.syscloud.models import CloudSdkRecord
    from apps.syscloud.cloud_providers.sdk_manager import SDK_DEPS, SDKManager

    if force:
        CloudSdkRecord.objects.filter(
            sdk_name__in=[k for k in SDK_DEPS.keys()]
        ).delete()

    created_count = 0
    skipped_count = 0

    for sdk_name, sdk_info in SDK_DEPS.items():
        installed = SDKManager.check_installed(sdk_name)
        version = SDKManager.get_installed_version(sdk_name) if installed else ''
        defaults = {
            'install_status': 1 if installed else 0,
            'sdk_version': version,
            'provider_keys': ','.join(sdk_info.get('providers', [])),
        }
        obj, created = CloudSdkRecord.objects.get_or_create(
            sdk_name=sdk_name,
            defaults=defaults,
        )
        if created:
            created_count += 1
        else:
            if not installed:
                obj.install_status = 0
                obj.sdk_version = ''
                obj.save(update_fields=['install_status', 'sdk_version'])
            skipped_count += 1

    return created_count, skipped_count
