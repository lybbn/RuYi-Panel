from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-05-03
    @EditData:2024-05-03
    @Email:1042594286@qq.com
    @name:同步models到数据库命令: python manage.py syncdb
    @使用场景：新增models字段，需要做同步到数据库
    """

    def handle(self, *args, **options):
        print(f"正在同步models到【数据库】")
        call_command('makemigrations')
        call_command('migrate', database='default')
        call_command('migrate', database='logs')
        call_command('migrate', database='tasks')
        call_command('migrate', database='shop')
        call_command('migrate', database='backup')
        call_command('migrate', database='docker')
        print("同步models到数据库完成！")