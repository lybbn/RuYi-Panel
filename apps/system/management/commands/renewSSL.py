import json
import os
import warnings
from datetime import datetime
from django.core.management.base import BaseCommand
from apps.system.models import Sites
from utils.ruyiclass.webClass import WebClient
from apps.sysshop.models import RySoftShop
from utils.security.letsencrypt_cert import letsencryptTool
from utils.common import GetLetsencryptPath,ReadFile

warnings.filterwarnings("ignore", category=DeprecationWarning)

def _get_provider_config_path(provider):
    if provider == 'litessl':
        return GetLetsencryptPath().replace('letsencrypt.json','litessl.json')
    return GetLetsencryptPath()

class Command(BaseCommand):
    """
    @author:lybbn
    @version:1.1
    @Data:2024-11-03
    @EditData:2026-05-30
    @Email:1042594286@qq.com
    @name:续签SSL证书(Let's Encrypt/LiteSSL): python manage.py renewSSL
    """

    def handle(self, *args, **options):
        nowtime = datetime.now()
        total_result = []
        total_fail = []

        for provider in ['letsencrypt', 'litessl']:
            c_path = _get_provider_config_path(provider)
            provider_name = letsencryptTool.ACME_PROVIDERS.get(provider, {}).get('name', provider)
            if not os.path.exists(c_path):
                continue
            c_content = ReadFile(c_path)
            if not c_content:
                continue
            try:
                j_content = json.loads(c_content)
            except Exception:
                continue
            orders = j_content.get("orders", {})
            if not orders:
                continue
            result_list = []
            fail_list = []
            for order, value in orders.items():
                order_no = order
                site_name = value.get('site_name', '')
                cert_timeout_old = j_content['orders'][order_no].get('cert_timeout', '')
                if not cert_timeout_old:
                    continue
                try:
                    cert_timeout = datetime.strptime(cert_timeout_old, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
                sy_days = (cert_timeout - nowtime).days
                if sy_days <= 30:
                    print(f"【{site_name}】{provider_name}证书过期时间:{cert_timeout_old}，小于30天，开始续签...")
                    result_list.append(site_name)
                    try:
                        renew_acmetools = letsencryptTool(provider=provider, is_log=False)
                        renew_acmetools.renew_certificate(order_no=order_no)
                        print(f"【{site_name}】续签成功 !!!")
                    except Exception as e:
                        fail_list.append(site_name)
                        print(f"【{site_name}】续签失败：\n {e}")
            if result_list:
                print(f'{provider_name}任务处理完毕，共{len(result_list)}个证书需要续签，成功{len(result_list)-len(fail_list)}个，失败{len(fail_list)}个')
            else:
                print(f"没有需要续签的{provider_name}证书")
            total_result.extend(result_list)
            total_fail.extend(fail_list)

        if not total_result and not total_fail:
            print("没有需要续签的SSL证书")
        elif total_result:
            print(f'\n全部任务处理完毕，共{len(total_result)}个证书需要续签，成功{len(total_result)-len(total_fail)}个，失败{len(total_fail)}个')
