import os
import json
import datetime
import threading
from django.conf import settings
from django.http import FileResponse
from django.utils.encoding import escape_uri_path
from cryptography.hazmat.primitives.serialization import Encoding as CertEncoding
from rest_framework.permissions import IsAuthenticated
from utils.customView import CustomAPIView
from utils.jsonResponse import DetailResponse, ErrorResponse
from utils.common import (
    get_parameter_dic, ReadFile, WriteFile, md5, ast_convert,
    check_is_email, GetLetsencryptPath, GetLetsencryptLogPath,
    GetLetsencryptRootPath, DeleteDir
)
from utils.security.letsencrypt_cert import letsencryptTool
from utils.sslPem import getCertInfo, create_root_certificate, create_signed_certificate, load_pfx_file
from utils.ruyiclass.webClass import WebClient
from apps.system.models import Sites, SiteDomains
from apps.sysshop.models import RySoftShop
from apps.syslogs.logutil import RuyiAddOpLog


def _get_provider_config_path(provider):
    if provider == 'litessl':
        return GetLetsencryptPath().replace('letsencrypt.json', 'litessl.json')
    return GetLetsencryptPath()


def _get_provider_log_path(provider):
    if provider == 'litessl':
        return GetLetsencryptLogPath().replace('letsencrypt.log', 'litessl.log')
    return GetLetsencryptLogPath()


def _get_provider_cert_root(provider):
    if provider == 'litessl':
        return os.path.join(os.path.dirname(GetLetsencryptRootPath()), 'litessl')
    return GetLetsencryptRootPath()


def _get_current_webserver_name():
    webServerIns = RySoftShop.objects.filter(type=3).first()
    if webServerIns is None:
        return ""
    return webServerIns.name


def _collect_all_certificates():
    result = []
    current_time = datetime.datetime.now()
    for provider in ['letsencrypt', 'litessl']:
        c_path = _get_provider_config_path(provider)
        c_content = ReadFile(c_path)
        if not c_content:
            continue
        try:
            j_content = json.loads(c_content)
        except Exception:
            continue
        orders = j_content.get("orders", {})
        email = j_content.get("email", "")
        for order_no, value in orders.items():
            cert_timeout_str = value.get('cert_timeout', '')
            expire_days = 0
            if cert_timeout_str:
                try:
                    cert_timeout = datetime.datetime.strptime(cert_timeout_str, "%Y-%m-%d %H:%M:%S")
                    expire_days = (cert_timeout - current_time).days
                    if expire_days < 0:
                        expire_days = 0
                except Exception:
                    pass
            cert_path = os.path.join(value.get('save_path', ''), "fullchain.pem")
            certinfo = {}
            if os.path.exists(cert_path):
                certinfo = getCertInfo(cert_path)
            site_name = value.get('site_name', '')
            site_id = value.get('site_id', '')
            site_ins = Sites.objects.filter(id=site_id).first()
            order_provider = value.get('provider', provider)
            result.append({
                'order_no': order_no,
                'provider': order_provider,
                'provider_name': letsencryptTool.ACME_PROVIDERS.get(order_provider, {}).get('name', order_provider),
                'email': email,
                'site_name': site_name,
                'site_id': site_id,
                'site_path': value.get('site_path', ''),
                'domain_list': value.get('domain_list', []),
                'identifiers': value.get('identifiers', []),
                'verifyType': value.get('verifyType', 'file'),
                'cert_timeout': cert_timeout_str,
                'expire_days': expire_days,
                'deploy': value.get('deploy', False),
                'over': value.get('over', False),
                'renew_time': value.get('renew_time', ''),
                'renew_status': value.get('renew_status', ''),
                'create_time': value.get('create_time', ''),
                'save_path': value.get('save_path', ''),
                'certinfo': certinfo,
                'site_exists': site_ins is not None,
            })
    return result


def _apply_litessl_certificate(domains, site_info, verifyType, order_no, eab_kid, eab_hmac_key):
    acmetools = letsencryptTool(provider='litessl', eab_kid=eab_kid, eab_hmac_key=eab_hmac_key)
    acmetools.apply_certificate(domain_list=domains, site_info=site_info, verifyType=verifyType, order_no=order_no)


def _renew_certificate(order_no, provider):
    acmetools = letsencryptTool(provider=provider)
    acmetools.renew_certificate(order_no=order_no)


class RYSSLCertManageView(CustomAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")

        if action == "get_cert_list":
            data = _collect_all_certificates()
            return DetailResponse(data=data)

        elif action == "get_acme_accounts":
            accounts = []
            for provider in ['letsencrypt', 'litessl']:
                c_path = _get_provider_config_path(provider)
                c_content = ReadFile(c_path)
                email = ""
                status = False
                eab_kid = ""
                has_eab = False
                if c_content:
                    try:
                        j_content = json.loads(c_content)
                        email = j_content.get('email', '')
                        status = bool(email)
                        eab_kid = j_content.get('eab_kid', '')
                        eab_hmac_key = j_content.get('eab_hmac_key', '')
                        has_eab = bool(eab_kid and eab_hmac_key)
                    except Exception:
                        pass
                accounts.append({
                    'provider': provider,
                    'provider_name': letsencryptTool.ACME_PROVIDERS[provider]['name'],
                    'email': email,
                    'status': status,
                    'requires_eab': letsencryptTool.ACME_PROVIDERS[provider]['requires_eab'],
                    'has_eab': has_eab,
                    'eab_kid': eab_kid,
                })
            return DetailResponse(data=accounts)

        elif action == "get_static_sites":
            sites = Sites.objects.filter(type=0).values('id', 'name', 'path')
            site_list = []
            for s in sites:
                domains = SiteDomains.objects.filter(site_id=s['id']).values_list('name', flat=True)
                site_list.append({
                    'id': s['id'],
                    'name': s['name'],
                    'path': s['path'],
                    'domains': list(domains),
                })
            return DetailResponse(data=site_list)

        elif action == "get_apply_log":
            provider = reqData.get("provider", "letsencrypt")
            log_path = _get_provider_log_path(provider)
            error = False
            orderover = False
            is_renew = reqData.get("is_renew", False)
            if is_renew == "false":
                is_renew = False
            if is_renew == "true":
                is_renew = True
            order_no = reqData.get("order_no", "")
            if not order_no:
                return DetailResponse(data={'data': '', 'done': True, 'error': error})
            c_path = _get_provider_config_path(provider)
            c_content = ReadFile(c_path)
            if not c_content:
                return DetailResponse(data={'data': '', 'done': True, 'error': error})
            j_content = json.loads(c_content)
            orders = j_content.get("orders", {})
            orderinfo = orders.get(order_no) if order_no in orders else None
            if orderinfo:
                orderover = orderinfo.get("over", True)
            done = orderover
            if is_renew:
                renew_status = orderinfo.get("renew_status", "") if orderinfo else ""
                if renew_status == "success":
                    done = True
                elif renew_status == "failed":
                    done = True
                    error = True
                else:
                    done = False
            use_order_log = False
            if orderinfo and orderinfo.get("over", False):
                save_path = orderinfo.get("save_path", "")
                if save_path:
                    log_filename = 'renew.log' if is_renew else 'apply.log'
                    order_log_path = os.path.join(save_path, log_filename)
                    if os.path.exists(order_log_path):
                        log_path = order_log_path
                        use_order_log = True
            from utils.server.system import system
            data = system.GetFileLastNumsLines(log_path, 2000)
            if not use_order_log:
                if (isinstance(data, bytes) and b"x" * 20 in data) or (isinstance(data, str) and "x" * 20 in data):
                    done = True
                    error = True
            return DetailResponse(data={'data': data, 'done': done, 'error': error})

        elif action == "get_selfsigned_info":
            root_ok, root_data = _ensure_root_certificate()
            if not root_ok:
                return DetailResponse(data={
                    "root_password": "",
                    "has_root_cert": False,
                    "root_certinfo": {},
                })
            root_password = root_data['root_password']
            root_cert = root_data.get('root_cert')
            root_certinfo = {}
            if root_cert:
                root_certinfo = getCertInfo(cert_content=root_cert.public_bytes(
                    encoding=CertEncoding.PEM
                ), mode="content")
            return DetailResponse(data={
                "root_password": root_password or "",
                "has_root_cert": True,
                "root_certinfo": root_certinfo,
            })

        elif action == "get_selfsigned_sites":
            webServer = _get_current_webserver_name()
            sites = Sites.objects.filter(type=0).order_by("-id")
            site_list = []
            for s in sites:
                domains = list(SiteDomains.objects.filter(site_id=s.id).values_list('name', flat=True))
                certinfo = {}
                has_selfsigned = False
                enable_https = False
                expire_days = 0
                if webServer:
                    ssl_data, _ = WebClient.get_site_cert(
                        webserver=webServer, siteName=s.name, sitePath=s.path, is_simple=True
                    )
                    if ssl_data:
                        certinfo = ssl_data.get('certinfo', {})
                        enable_https = ssl_data.get('enableHttps', False)
                        expire_days = ssl_data.get('expire_days', 0)
                        if certinfo and certinfo.get('type') == '自签证书':
                            has_selfsigned = True
                site_list.append({
                    'id': s.id,
                    'name': s.name,
                    'path': s.path,
                    'domains': domains,
                    'has_selfsigned': has_selfsigned,
                    'enable_https': enable_https,
                    'certinfo': certinfo,
                    'expire_days': expire_days,
                })
            return DetailResponse(data=site_list)

        elif action == "download_selfsigned_root_pfx":
            filename = settings.RUYI_ROOTPFX_PATH_FILE
            if not os.path.exists(filename):
                return ErrorResponse(msg="根证书文件不存在")
            file_size = os.path.getsize(filename)
            response = FileResponse(open(filename, 'rb'))
            response['content_type'] = "application/octet-stream"
            response['Content-Disposition'] = f'attachment;filename="{escape_uri_path(os.path.basename(filename))}"'
            response['Content-Length'] = file_size
            RuyiAddOpLog(request, msg="【SSL证书】- 下载自签名根证书", module="sslcert")
            return response

        return ErrorResponse(msg="参数错误")

    def post(self, request):
        reqData = get_parameter_dic(request)
        action = reqData.get("action", "")

        if action == "create_acme_account":
            provider = reqData.get("provider", "letsencrypt")
            email = reqData.get("email", "")
            if not check_is_email(email):
                return ErrorResponse(msg="邮箱格式错误")
            if provider not in letsencryptTool.ACME_PROVIDERS:
                return ErrorResponse(msg="不支持的提供商")
            eab_kid = reqData.get("eab_kid", "")
            eab_hmac_key = reqData.get("eab_hmac_key", "")
            if letsencryptTool.ACME_PROVIDERS[provider]['requires_eab']:
                if not eab_kid or not eab_hmac_key:
                    return ErrorResponse(msg="当前提供商需要EAB凭证(kid和hmacKey)")
            try:
                acmetools = letsencryptTool(provider=provider, eab_kid=eab_kid, eab_hmac_key=eab_hmac_key)
                acmetools.register_account({'email': email, 'eab_kid': eab_kid, 'eab_hmac_key': eab_hmac_key})
            except Exception as e:
                return ErrorResponse(msg=str(e))
            provider_name = letsencryptTool.ACME_PROVIDERS[provider]['name']
            RuyiAddOpLog(request, msg=f"【SSL证书】- 创建{provider_name}账号：{email}", module="sslcert")
            return DetailResponse(msg="创建成功")

        elif action == "apply_cert":
            provider = reqData.get("provider", "letsencrypt")
            domains = ast_convert(reqData.get("domains", []))
            site_id = reqData.get("site_id", "")
            verifyType = reqData.get("verifyType", "file")
            if not verifyType == 'file':
                return ErrorResponse(msg="验证类型错误")
            if not domains:
                return ErrorResponse(msg="请选择需要申请的域名")
            if not site_id:
                return ErrorResponse(msg="参数错误")
            if verifyType == "file":
                for dm in domains:
                    if "*" in dm:
                        return ErrorResponse(msg="不支持*泛域名证书")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="无此站点")
            if provider not in letsencryptTool.ACME_PROVIDERS:
                return ErrorResponse(msg="不支持的提供商")
            c_path = _get_provider_config_path(provider)
            c_content = ReadFile(c_path)
            if c_content:
                try:
                    j_content = json.loads(c_content)
                    if not j_content.get('email', ''):
                        return ErrorResponse(msg="请先创建ACME账号")
                except Exception:
                    return ErrorResponse(msg="请先创建ACME账号")
            else:
                return ErrorResponse(msg="请先创建ACME账号")
            site_info = {"id": s_ins.id, "name": s_ins.name, "path": s_ins.path}
            order_no = md5(json.dumps(domains) + str(site_id) + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            log_path = _get_provider_log_path(provider)
            WriteFile(log_path, b"", mode="wb")
            if provider == 'litessl':
                eab_kid = reqData.get("eab_kid", "")
                eab_hmac_key = reqData.get("eab_hmac_key", "")
                if not eab_kid or not eab_hmac_key:
                    try:
                        j_content = json.loads(ReadFile(c_path))
                        eab_kid = j_content.get('eab_kid', '')
                        eab_hmac_key = j_content.get('eab_hmac_key', '')
                    except Exception:
                        pass
                    if not eab_kid or not eab_hmac_key:
                        return ErrorResponse(msg="LiteSSL需要EAB凭证")
                t = threading.Thread(
                    target=_apply_litessl_certificate,
                    args=(domains, site_info, verifyType, order_no, eab_kid, eab_hmac_key)
                )
                t.start()
            else:
                t = threading.Thread(
                    target=_apply_letsencrypt_certificate,
                    args=(domains, site_info, verifyType, order_no)
                )
                t.start()
            provider_name = letsencryptTool.ACME_PROVIDERS[provider]['name']
            RuyiAddOpLog(request, msg=f"【SSL证书】- 站点：{s_ins.name},申请{provider_name}证书", module="sslcert")
            return DetailResponse(data={'order_no': order_no, 'provider': provider}, msg="申请中...")

        elif action == "renew_cert":
            order_no = reqData.get("order_no", "")
            provider = reqData.get("provider", "letsencrypt")
            if not order_no:
                return ErrorResponse(msg="参数错误")
            c_path = _get_provider_config_path(provider)
            c_content = ReadFile(c_path)
            if not c_content:
                return ErrorResponse(msg="无此订单信息")
            j_content = json.loads(c_content)
            orders = j_content.get("orders", {})
            if order_no not in orders:
                return ErrorResponse(msg="无此订单信息")
            cert_timeout = j_content['orders'][order_no].get('cert_timeout', '')
            if cert_timeout:
                try:
                    cert_timeout_dt = datetime.datetime.strptime(cert_timeout, "%Y-%m-%d %H:%M:%S")
                    sy_days = (cert_timeout_dt - datetime.datetime.now()).days
                    if sy_days > 30:
                        return ErrorResponse(msg="证书有效期大于30天，暂时忽略续签")
                except Exception:
                    pass
            log_path = _get_provider_log_path(provider)
            WriteFile(log_path, b"", mode="wb")
            j_content['orders'][order_no]['renew_status'] = ""
            WriteFile(c_path, json.dumps(j_content))
            t = threading.Thread(
                target=_renew_certificate,
                args=(order_no, provider)
            )
            t.start()
            site_name = orders[order_no].get('site_name', '')
            provider_name = letsencryptTool.ACME_PROVIDERS.get(provider, {}).get('name', provider)
            RuyiAddOpLog(request, msg=f"【SSL证书】- 站点：{site_name},续签{provider_name}证书", module="sslcert")
            return DetailResponse(data=order_no, msg="续签中...")

        elif action == "delete_cert":
            order_no = reqData.get("order_no", "")
            provider = reqData.get("provider", "letsencrypt")
            if not order_no:
                return ErrorResponse(msg="参数错误")
            c_path = _get_provider_config_path(provider)
            c_content = ReadFile(c_path)
            if not c_content:
                return ErrorResponse(msg="无此订单信息")
            j_content = json.loads(c_content)
            orders = j_content.get("orders", {})
            if order_no not in orders:
                return ErrorResponse(msg="无此订单信息")
            save_path = orders[order_no].get('save_path', '')
            if save_path and os.path.exists(save_path):
                DeleteDir(save_path)
            del j_content['orders'][order_no]
            WriteFile(c_path, json.dumps(j_content))
            RuyiAddOpLog(request, msg=f"【SSL证书】- 删除证书订单：{order_no}", module="sslcert")
            return DetailResponse(msg="删除成功")

        elif action == "deploy_cert":
            order_no = reqData.get("order_no", "")
            provider = reqData.get("provider", "letsencrypt")
            site_id = reqData.get("site_id", "")
            if not order_no or not site_id:
                return ErrorResponse(msg="参数错误")
            c_path = _get_provider_config_path(provider)
            c_content = ReadFile(c_path)
            if not c_content:
                return ErrorResponse(msg="无此订单信息")
            j_content = json.loads(c_content)
            orders = j_content.get("orders", {})
            if order_no not in orders:
                return ErrorResponse(msg="无此订单信息")
            order = orders[order_no]
            save_path = order.get('save_path', '')
            src_pem_file = os.path.join(save_path, "fullchain.pem")
            src_key_file = os.path.join(save_path, "private_key.pem")
            if not os.path.exists(src_pem_file) or not os.path.exists(src_key_file):
                return ErrorResponse(msg="证书文件不存在")
            src_pem_content = ReadFile(src_pem_file)
            src_key_content = ReadFile(src_key_file)
            webServer = _get_current_webserver_name()
            if not webServer:
                return ErrorResponse(msg="无Web环境，请先安装")
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="站点不存在")
            cont = {'cert': src_pem_content, 'key': src_key_content}
            isok, msg = WebClient.save_site_ssl_cert(
                webserver=webServer, siteName=s_ins.name, sitePath=s_ins.path, cont=cont
            )
            if not isok:
                return ErrorResponse(msg=msg)
            WebClient.reload_service(webserver=webServer)
            RuyiAddOpLog(request, msg=f"【SSL证书】- 部署证书到站点：{s_ins.name}", module="sslcert")
            return DetailResponse(msg="部署成功")

        elif action == "apply_selfsigned_cert":
            domains = ast_convert(reqData.get("domains", []))
            site_id = reqData.get("site_id", "")
            if not site_id:
                return ErrorResponse(msg="参数错误")
            ok, hosts_or_msg = _normalize_selfsigned_hosts(domains)
            if not ok:
                return ErrorResponse(msg=hosts_or_msg)
            s_ins = Sites.objects.filter(id=site_id).first()
            if not s_ins:
                return ErrorResponse(msg="无此站点")
            webServer = _get_current_webserver_name()
            if not webServer:
                return ErrorResponse(msg="无Web环境，请先安装")
            root_ok, root_data = _ensure_root_certificate()
            if not root_ok:
                return ErrorResponse(msg=root_data)
            cert_pem, key_pem = create_signed_certificate(
                root_cert=root_data['root_cert'],
                root_key=root_data['root_key'],
                hosts=hosts_or_msg
            )
            isok, msg = WebClient.save_site_ssl_cert(
                webserver=webServer,
                siteName=s_ins.name,
                sitePath=s_ins.path,
                cont={
                    "cert": cert_pem.decode("utf-8"),
                    "key": key_pem.decode("utf-8"),
                    "root_password": root_data['root_password']
                }
            )
            if not isok:
                return ErrorResponse(msg=msg)
            WebClient.reload_service(webserver=webServer)
            RuyiAddOpLog(request, msg=f"【SSL证书】- 站点：{s_ins.name},生成自签名证书", module="sslcert")
            return DetailResponse(msg="自签名证书生成成功")

        elif action == "regenerate_root_cert":
            root_password = ReadFile(settings.RUYI_ROOTPFX_PASSWORD_PATH_FILE) or "ruyi.lybbn.cn"
            pfx_data, root_key, root_cert = create_root_certificate(password=root_password)
            WriteFile(settings.RUYI_ROOTPFX_PASSWORD_PATH_FILE, root_password)
            WriteFile(settings.RUYI_ROOTPFX_PATH_FILE, pfx_data, mode="wb")
            RuyiAddOpLog(request, msg="【SSL证书】- 重新生成自签名根证书", module="sslcert")
            return DetailResponse(msg="根证书重新生成成功")

        return ErrorResponse(msg="参数错误")


def _ensure_root_certificate():
    root_pfx_path = settings.RUYI_ROOTPFX_PATH_FILE
    root_password = ReadFile(settings.RUYI_ROOTPFX_PASSWORD_PATH_FILE)
    if os.path.exists(root_pfx_path):
        if not root_password:
            return False, "根证书密码文件不存在"
        root_cert, root_key = load_pfx_file(root_pfx_path, root_password)
        if not root_cert or not root_key:
            return False, "根证书加载失败"
        return True, {
            "root_password": root_password,
            "root_cert": root_cert,
            "root_key": root_key,
        }
    root_password = root_password or "ruyi.lybbn.cn"
    pfx_data, root_key, root_cert = create_root_certificate(password=root_password)
    WriteFile(settings.RUYI_ROOTPFX_PASSWORD_PATH_FILE, root_password)
    WriteFile(root_pfx_path, pfx_data, mode="wb")
    return True, {
        "root_password": root_password,
        "root_cert": root_cert,
        "root_key": root_key,
    }


def _normalize_selfsigned_hosts(domains):
    hosts = []
    for domain in domains:
        host = str(domain).strip()
        if not host:
            continue
        if "*" in host:
            return False, "自建证书暂不支持泛域名"
        if " " in host:
            return False, "证书域名格式错误"
        if host not in hosts:
            hosts.append(host)
    if not hosts:
        return False, "请选择至少一个域名或IP"
    return True, hosts


def _apply_letsencrypt_certificate(domains, site_info, verifyType, order_no):
    acmetools = letsencryptTool(provider='letsencrypt')
    acmetools.apply_certificate(domain_list=domains, site_info=site_info, verifyType=verifyType, order_no=order_no)
