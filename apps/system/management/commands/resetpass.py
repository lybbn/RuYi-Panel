from django.core.management.base import BaseCommand
from apps.system.models import Users
from django.contrib.auth.hashers import make_password

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-05-03
    @EditData:2024-05-03
    @Email:1042594286@qq.com
    @name:修改超级管理员密码: python manage.py resetpass -p password
    """
    
    def add_arguments(self, parser):
        parser.add_argument('-p', nargs='*')#管理员密码

    def handle(self, *args, **options):
        password = None
        if isinstance(options.get('p'), list):
            password = options.get('p')[0]
        if not password:
            raise ValueError("密码不能为空")
        
        us = Users.objects.filter(is_superuser=True).first()
        if not us:
            raise ValueError("无此用户")
        us.password=make_password(password)
        us.save()
        print("修改成功！！！")