from django.core.management.base import BaseCommand
from apps.system.models import Sites
from utils.common import ast_convert
from utils.ruyiclass.webClass import WebClient

def get_type_name(type):
    if type == 1:
        return "python"
    elif type == 2:
        return "node"
    elif type == 3:
        return "php"
    elif type == 4:
        return "go"
    return ""

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-12-01
    @EditData:2024-12-01
    @Version:1.0
    @Email:1042594286@qq.com
    @name:开启启动服务(如python等项目需开启启动的场景): python manage.py autostart
    """

    def handle(self, *args, **options):
        site_queryset = Sites.objects.exclude(type=0).order_by("-id")
        s_list = []
        for s in site_queryset:
            type = s.type
            cont = ast_convert(s.project_cfg)
            autostart = cont.get("autostart",False)
            webServer = get_type_name(type)
            if autostart and s.status:
                s_list.append(s.name)
                res = WebClient.autoStart(webserver=webServer,siteName=s.name,sitePath=s.path,cont=cont)
                print(f'【{s.name}】项目已尝试启动，启动结果：{res}')
        print(f'任务处理完毕，共{len(s_list)}个开机启动项目')