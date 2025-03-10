from django.core.management.base import BaseCommand
from apps.system.models import Sites
from utils.ruyiclass.webClass import WebClient
from apps.sysshop.models import RySoftShop
from utils.common import ast_convert

current_static_webServer = ""

def get_type_name(type):
    if type == 0:
        if not current_static_webServer:
            webServerIns = RySoftShop.objects.filter(type=3).first()
            webServer = "nginx"
            if webServerIns is not None:
                webServer = webServerIns.name
                current_static_webServer = webServer
        else:
            webServer = current_static_webServer
        return webServer
    elif type == 1:
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
    @Data:2024-11-03
    @EditData:2024-11-03
    @Email:1042594286@qq.com
    @name:检查网站过期: python manage.py checkSitesEnd
    """

    def handle(self, *args, **options):
        site_queryset = Sites.objects.all().order_by("-id")
        webServer_0 = get_type_name(0)
        expire_list = []
        for s in site_queryset:
            if not s.is_expired():
                continue
            type = s.type
            if s.status:
                expire_list.append(s.name)
                webServer = webServer_0 if type == 0 else get_type_name(type)
                if type == 0:
                    WebClient.stop_site(webserver=webServer,siteName=s.name,sitePath=s.path)
                else:
                    cont = ast_convert(s.project_cfg)
                    WebClient.stop_site(webserver=webServer,siteName=s.name,sitePath=s.path,cont=cont)
                s.status = False
                s.save()
                print(f'【{s.name}】网站过期，已处理')
        print(f'任务处理完毕，共{len(expire_list)}个过期站点')