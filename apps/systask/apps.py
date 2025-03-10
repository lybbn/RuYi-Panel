from django.apps import AppConfig


class SystaskConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.systask'

    # def ready(self):
    #     from apps.systask import tasks
    #     tasks.start_scheduler()  # 启动调度器

    # def shutdown(self):
    #     from apps.systask import tasks
    #     tasks.stop_scheduler()  # 关闭调度器
