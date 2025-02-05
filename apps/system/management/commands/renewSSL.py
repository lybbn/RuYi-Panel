import json
from datetime import datetime
from django.core.management.base import BaseCommand
from apps.system.models import Sites
from utils.ruyiclass.webClass import WebClient
from apps.sysshop.models import RySoftShop
from utils.security.letsencrypt_cert import letsencryptTool
from utils.common import GetLetsencryptPath,ReadFile

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.0
    @Data:2024-11-03
    @EditData:2024-11-03
    @Email:1042594286@qq.com
    @name:续签SSL证书(Let's Encrypt): python manage.py renewSSL
    """

    def handle(self, *args, **options):
        c_path = GetLetsencryptPath()
        c_content = ReadFile(c_path)
        nowtime = datetime.now()
        if c_content:
            j_content = json.loads(c_content)
            orders = j_content.get("orders",{})
            if orders:
                result_list = []
                fail_list = []
                for order,value in orders.items():
                    order_no = order
                    site_name = value['site_name']
                    cert_timeout_old = j_content['orders'][order_no]['cert_timeout']
                    cert_timeout = datetime.strptime(cert_timeout_old, "%Y-%m-%d %H:%M:%S")
                    sy_days = (cert_timeout - nowtime).days
                    if sy_days<=30:
                        print(f"【{site_name}】Let's Encrypt证书过期时间:{cert_timeout_old}，小于30天，开始续签...")
                        result_list.append(site_name)
                        try:
                            renew_acmetools = letsencryptTool(is_log=False)
                            renew_acmetools.renew_certificate(order_no=order_no)
                            print(f"【{site_name}】续签成功 !!!")
                        except Exception as e:
                            fail_list.append(site_name)
                            print(f"【{site_name}】续签失败：\n {e}")
                print(f'任务处理完毕，共{len(result_list)}个证书需要续签，成功{len(result_list)-len(fail_list)}个，失败{len(fail_list)}个')
            else:
                print("没有需要续签的Let's Encrypt证书")
        else:
            print("没有需要续签的Let's Encrypt证书")
                