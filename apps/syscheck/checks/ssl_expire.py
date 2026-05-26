import os
import ssl
import socket
import datetime
from django.conf import settings
from .base import BaseCheck, register_check, RISK_LEVEL_MEDIUM

WARN_DAYS = 30


@register_check
class CheckSSLExpire(BaseCheck):
    check_id = 'ssl_expire'
    title = 'SSL证书过期检查'
    description = '检查托管网站的SSL证书是否即将过期'
    level = RISK_LEVEL_MEDIUM
    category = 'panel'

    def run(self):
        cert_dir = os.path.join(settings.BASE_DIR, 'data', 'vhost', 'cert')
        if not os.path.exists(cert_dir):
            return True, '未发现SSL证书目录', []
        expiring = []
        now = datetime.datetime.now()
        for domain in os.listdir(cert_dir):
            cert_path = os.path.join(cert_dir, domain)
            if not os.path.isdir(cert_path):
                continue
            for fname in ['fullchain.pem', 'cert.pem', 'server.crt']:
                cert_file = os.path.join(cert_path, fname)
                if not os.path.exists(cert_file):
                    continue
                try:
                    with open(cert_file, 'r') as f:
                        cert_data = f.read()
                    cert = ssl.PEM_cert_to_DER_cert(cert_data)
                    x509 = ssl._ssl._test_decode_cert(cert_file) if hasattr(ssl._ssl, '_test_decode_cert') else None
                except:
                    continue
                try:
                    from cryptography import x509 as crypto_x509
                    from cryptography.hazmat.backends import default_backend
                    with open(cert_file, 'rb') as f:
                        cert_obj = crypto_x509.load_pem_x509_certificate(f.read(), default_backend())
                    expire_date = cert_obj.not_valid_after_utc.replace(tzinfo=None)
                    days_left = (expire_date - now).days
                    if days_left <= WARN_DAYS:
                        status_text = '已过期' if days_left < 0 else f'{days_left}天后过期'
                        expiring.append(f'{domain}({status_text})')
                except ImportError:
                    return True, 'cryptography库未安装，无法检查证书', ['pip install cryptography']
                except Exception as e:
                    continue
                break
        if expiring:
            return False, f'发现证书即将过期: {", ".join(expiring)}', [
                '续签即将过期的SSL证书',
                '建议开启自动续签功能'
            ]
        return True, '所有SSL证书状态正常', []
