from django.apps import AppConfig

class SystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system'
    
    def ready(self):
        import os
        from django.conf import settings
        QQWRY_FILE_PATH = os.path.join(settings.BASE_DIR,'qqwry.dat')
        if not os.path.exists(QQWRY_FILE_PATH):
            from apps.systask.tasks import installTask
            from utils.common import GetRandomSet
            installTask("ruyi_qqwrt_init_%s"%GetRandomSet(6),initQQwary,func_args={})

def initQQwary():
    from utils.ip_util import IPQQwry
    IPQQwry()