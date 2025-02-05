from django.core.management.base import BaseCommand
from django.core.management import call_command

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
        call_command('autostart')
        print("========如意面板启动后的初始化操作执行结束========")