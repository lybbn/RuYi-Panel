from django.core.management.base import BaseCommand
from utils.upgrade_panel import update_ruyi_panel

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2025-01-03
    @EditData:2025-01-03
    @Email:1042594286@qq.com
    @name:升级面板: python manage.py upgrade
    """

    def handle(self, *args, **options):
        update_ruyi_panel()