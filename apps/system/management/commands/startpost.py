from django.core.management.base import BaseCommand
from django.core.management import call_command
from utils.common import current_os

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2025-02-01
    @EditData:2025-02-01
    @Version:1.0
    @Email:1042594286@qq.com
    @name:如意面板启动后需要执行的后续操作: python manage.py startpost
    """

    def handle(self, *args, **options):
        print("========如意面板启动后的初始化操作执行中...========")
        self._restore_soft_running_state()
        call_command('autostart')
        print("========如意面板启动后的初始化操作执行结束========")

    def _ensure_php_windows_service(self, version):
        from utils.install.php import get_php_path_info, SET_PHP_WINDOWS_SERVICE
        from utils.server.windows import get_service_status
        soft_paths = get_php_path_info(version)
        service_name = soft_paths['service_name']
        if get_service_status(service_name) == -1:
            try:
                SET_PHP_WINDOWS_SERVICE(version)
                print(f'  PHP {version} 已注册为Windows系统服务')
            except Exception as e:
                print(f'  PHP {version} 注册Windows服务失败: {e}')

    def _restore_soft_running_state(self):
        from apps.sysshop.models import RySoftShop
        from utils.install.install_soft import Ry_Start_Soft
        is_windows = current_os == 'windows'
        soft_list = RySoftShop.objects.filter(installed=True, status=1).exclude(name__in=['python', 'go', 'nodejs'])
        started = []
        for soft in soft_list:
            try:
                version = soft.install_version if soft.name == 'php' else None
                if is_windows and soft.name == 'php' and version:
                    self._ensure_php_windows_service(version)
                Ry_Start_Soft(name=soft.name, is_windows=is_windows, version=version)
                started.append(soft.name)
                print(f'  【{soft.name}】已恢复启动')
            except Exception as e:
                print(f'  【{soft.name}】恢复启动失败: {e}')
        print(f'应用状态恢复完毕，共{len(started)}个应用已启动')
