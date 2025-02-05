import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruyi.settings')
django.setup()

import platform
from apps.system.models import Users,Config,SiteGroup
from apps.systask.models import CrontabTask
from django.contrib.auth.hashers import make_password
from utils.common import GetRandomSet

class Initialize:

    def __init__(self, delete=True,username=None,password=None):
        """
        delete 是否删除已初始化数据
        username 用户名
        password 密码
        """
        self.delete = delete
        self.username = username if username else "admin"
        self.password = make_password(password if username else "123456")

    def save(self, obj, data: list, name):
        print(f"正在初始化【{name}】")
        if self.delete:
            try:
                obj.objects.filter(id__in=[ele.get('id') for ele in data]).delete()
            except Exception:
                pass
        for ele in data:
            m2m_dict = {}
            new_data = {}
            for key, value in ele.items():
                # 判断传的 value 为 list 的多对多进行抽离，使用set 进行更新
                if isinstance(value, list):
                    m2m_dict[key] = value
                else:
                    new_data[key] = value
            object, _ = obj.objects.get_or_create(id=ele.get("id"), defaults=new_data)
            for key, m2m in m2m_dict.items():
                m2m = list(set(m2m))
                if m2m and len(m2m) > 0 and m2m[0]:
                    exec(f"""
if object.{key}:
    object.{key}.set({m2m})
""")
        print(f"初始化完成【{name}】")


    def init_users(self):
        """
        初始化用户表
        """
        data = [
            {
                "id": 1,
                "username":self.username,
                "password": self.password,
                "is_superuser": 1, 
                "is_staff": 1,
            },
        ]
        self.save(Users, data, "用户表")

    def init_config(self):
        """
        初始化配置表
        """
        plat = platform.system().lower()
        if plat == 'windows':
            backup_path = "C:\\ruyi\\backup"
            sites_path = "C:\\ruyi\\wwwroot"
        else:
            backup_path = "/ruyi/backup"
            sites_path = "/ruyi/wwwroot"
        mysql_root_pass = GetRandomSet(16).lower()
        config = {
            "backup_path":backup_path,
            "sites_path":sites_path,
            "mysql_root_pass":mysql_root_pass,
        }
        data = [{
            "id": 1,
            "config":config
        }]
        self.save(Config, data, "配置表")

    def init_site_group(self):
        """
        初始化站点分组
        """
        data = [{
            "id": 0,
            "name":"默认分组",
            "is_default":True
        }]
        self.save(SiteGroup, data, "站点分组表")
        
    def init_task(self):
        """
        初始化计划任务表
        """
        from apps.systask.scheduler import scheduler
        from django_apscheduler.jobstores import DjangoJobStore
        scheduler.add_jobstore(DjangoJobStore(), 'default')
        scheduler.start()
        from apps.systask.tasks import cronTask
        from django.conf import settings
        root_path = settings.BASE_DIR
        job_id1 = "sys_job_check_sites_end_001"
        job_id2 = "sys_job_check_letsencrypt_001"
        shell_body1 = ""
        shell_body2 = ""
        plat = platform.system().lower()
        if plat == 'windows':
            shell_body1 = f"cd {root_path}\npython manage.py checkSitesEnd"
            shell_body2 = f"cd {root_path}\npython manage.py renewSSL"
        else:
            shell_body1 = f"cd {root_path}\n/usr/local/ruyi/python/bin/python3 manage.py checkSitesEnd"
            shell_body2 = f"cd {root_path}\n/usr/local/ruyi/python/bin/python3 manage.py renewSSL"
        reqData1 = {"type":0,"name":"检查网站过期","shell_body":shell_body1}
        reqData2 = {"type":0,"name":"续签Let's Encrypt证书","shell_body":shell_body2}
        django_job1 = scheduler.add_job(cronTask,'cron',id=job_id1,second=0, minute=10, hour=1, day="*", month="*", week="*", year="*",args=[reqData1,job_id1],max_instances=1,replace_existing=True,misfire_grace_time=1,coalesce=True)
        django_job2 = scheduler.add_job(cronTask,'cron',id=job_id2,second=0, minute=10, hour=1, day="*", month="*", week="*", year="*",args=[reqData2,job_id2],max_instances=1,replace_existing=True,misfire_grace_time=1,coalesce=True)
        data = [
            {
                "id": 1,
                "job_id":job_id1,
                "name": "检查网站过期",
                "is_sys": 0, 
                "status": 1,
                "period_type": 1,
                "year": 0,
                "month": 0,
                "week": 0,
                "day": 0,
                "hour": 1,
                "minute": 10,
                "second": 0,
                "shell_body": shell_body1,
            },
            {
                "id": 2,
                "job_id":job_id2,
                "name": "续签Let's Encrypt证书",
                "is_sys": 0, 
                "status": 1,
                "period_type": 1,
                "year": 0,
                "month": 0,
                "week": 0,
                "day": 0,
                "hour": 1,
                "minute": 10,
                "second": 0,
                "shell_body": shell_body2,
            },
        ]
        self.save(CrontabTask, data, "计划任务表")

    def run(self):
        self.init_users()
        self.init_config()
        self.init_site_group()
        self.init_task()


def main(delete=True,username=None,password=None):
    Initialize(delete=delete,username=username,password=password).run()

if __name__ == '__main__':
    main()