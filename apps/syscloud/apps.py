from django.apps import AppConfig


class SyscloudConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.syscloud'
    verbose_name = '云存储管理'
    label = 'syscloud'
