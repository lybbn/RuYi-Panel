import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ruyi.settings')
django.setup()

import platform
from apps.system.models import Users,Config,SiteGroup
from apps.sysdocker.models import RyDockerRepo
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
        
        # 注意：监控和告警任务不由初始化自动注册
        # - 监控任务：由用户在监控配置页面开启后自动注册
        # - 告警任务：由用户创建具体告警任务后自动注册
        
        # 初始化系统默认计划任务
        from apps.systask.init_data import init_crontab_tasks
        print(f"正在初始化【计划任务表】")
        created_count, skipped_count = init_crontab_tasks(force=self.delete)
        print(f"初始化完成【计划任务表】: 新建 {created_count} 个, 跳过 {skipped_count} 个")
        
    def init_dockers_repo(self):
        """
        初始化容器仓库表
        """
        data = [{
            "id": 1,
            "name":"Docker Hub",
            "url":"docker.io",
            "protocol":"https"
        }]
        self.save(RyDockerRepo, data, "初始化容器仓库表")

    def init_alert_notify_config(self):
        """
        初始化告警通知渠道配置
        预制6种通知渠道，默认禁用，需要用户配置后启用
        """
        from apps.sysalert.init_data import init_alert_notify_config
        
        print(f"正在初始化【告警通知渠道配置】")
        created_count, skipped_count = init_alert_notify_config(force=self.delete)
        print(f"初始化完成【告警通知渠道配置】: 新建 {created_count} 个, 跳过 {skipped_count} 个")

    def init_waf(self):
        """
        初始化WAF数据
        """
        from apps.syswaf.init_data import init_waf_data
        
        print(f"正在初始化【WAF数据】")
        categories, rules, config, ip_group, from_remote = init_waf_data(force=self.delete)
        print(f"初始化完成【WAF数据】: 分类{categories}个, 规则{rules}条, 配置{config}, IP组{ip_group}")

    def run(self):
        self.init_users()
        self.init_config()
        self.init_site_group()
        self.init_task()
        self.init_dockers_repo()
        self.init_alert_notify_config()
        self.init_waf()

def main(delete=True,username=None,password=None):
    Initialize(delete=delete,username=username,password=password).run()

if __name__ == '__main__':
    main()