import json
import threading
import re
from apps.sysai.tools.base import register_tool
from apps.system.models import Sites, SiteDomains
from apps.sysshop.models import RySoftShop
from utils.ruyiclass.webClass import WebClient
from utils.common import current_os
from apps.system.views.site_manage import ruyiPathDirHandle, ruyiCheckPortInBlack


def _get_webserver():
    webServerIns = RySoftShop.objects.filter(type=3).first()
    if webServerIns:
        return webServerIns.name
    return ''


@register_tool(id='panel_site_list', category='panel', name_cn='网站列表', risk_level='low')
def panel_site_list(search: str = ''):
    """获取如意面板管理的网站站点列表。这是面板内置的网站管理功能，包含静态站点、Python站点、Node站点、PHP站点、Go站点等。当用户需要查看网站、了解站点状态时，必须优先使用此工具而不是扫描配置文件。

    Args:
        search: 搜索关键词，按站点名称或备注搜索
    """
    try:
        queryset = Sites.objects.all().order_by('-id')
        if search:
            from django.db.models import Q
            queryset = queryset.filter(Q(name__icontains=search) | Q(remark__icontains=search))

        webserver = _get_webserver()
        type_map = {0: '静态', 1: 'Python', 2: 'Node', 3: 'PHP', 4: 'Go'}

        result = []
        for site in queryset:
            domains = SiteDomains.objects.filter(site=site)
            domain_list = [f'{d.name}:{d.port}' for d in domains]

            result.append({
                'id': site.id,
                'name': site.name,
                'path': site.path,
                'status': site.status,
                'type': site.type,
                'typename': type_map.get(site.type, '未知'),
                'remark': site.remark or '',
                'domains': domain_list,
                'is_default': site.is_default,
                'is_expired': site.is_expired(),
                'create_at': str(site.create_at),
            })

        return {
            'sites': result,
            'total': len(result),
            'webserver': webserver or '未安装',
        }
    except Exception as e:
        return {'error': f'获取网站列表失败: {str(e)}'}


@register_tool(id='panel_site_create', category='panel', name_cn='创建网站', risk_level='high')
def panel_site_create(name: str, domains: list, path: str = '', remark: str = ''):
    """在如意面板中创建网站站点。⚠️此为高危操作，会修改Web服务器配置。创建前请确保已通过应用商店安装了Web服务器（如Nginx）。

    Args:
        name: 站点名称，通常使用域名，如 example.com、blog.example.com
        domains: 域名列表，每个元素格式为 "域名:端口"，如 ["example.com:80", "www.example.com:80"]
        path: 站点根目录，为空则自动生成默认路径
        remark: 备注信息
    """
    try:
        webserver = _get_webserver()
        if not webserver:
            return {'error': '未安装Web服务器，请先使用panel_shop_install安装Nginx'}

        if Sites.objects.filter(name=name).exists():
            return {'error': f'已存在同名站点: {name}'}

        if not domains:
            return {'error': '域名列表不能为空'}

        domain_list = []
        for dm in domains:
            dm = str(dm).strip()
            if ':' in dm:
                domain, port = dm.rsplit(':', 1)
            else:
                domain = dm
                port = '80'
            domain_list.append({'domain': domain, 'port': port})

        if not path:
            is_windows = current_os == 'windows'
            if is_windows:
                path = f'C:/wwwroot/{name}'
            else:
                path = f'/wwwroot/{name}'

        isok, msg = WebClient.create_site(
            webserver=webserver,
            domainList=domain_list,
            siteName=name,
            sitePath=path,
        )
        if not isok:
            return {'error': f'创建站点失败: {msg}'}

        s_ins = Sites.objects.create(
            name=name, remark=remark, path=path, type=0,
        )

        for dm in domain_list:
            SiteDomains.objects.create(
                name=dm['domain'], port=int(dm['port']), site=s_ins,
            )

        WebClient.reload_service(webserver=webserver)

        return {
            'success': True,
            'message': f'站点 {name} 创建成功',
            'site_id': s_ins.id,
            'path': path,
            'domains': domains,
        }
    except Exception as e:
        return {'error': f'创建网站失败: {str(e)}'}


@register_tool(id='panel_site_manage', category='panel', name_cn='网站管理', risk_level='high')
def panel_site_manage(site_id: int, action: str):
    """管理如意面板中的网站站点，支持启动、停止、删除等操作。⚠️此为高危操作，删除站点会清除Web服务器配置。

    Args:
        site_id: 站点ID（从panel_site_list返回的id获取）
        action: 操作类型，start(启动)、stop(停止)、delete(删除)
    """
    try:
        valid_actions = ['start', 'stop', 'delete']
        if action not in valid_actions:
            return {'error': f'不支持的操作: {action}，可用: {", ".join(valid_actions)}'}

        webserver = _get_webserver()
        if not webserver:
            return {'error': '未安装Web服务器'}

        site = Sites.objects.filter(id=site_id).first()
        if not site:
            return {'error': f'站点ID {site_id} 不存在，请先用panel_site_list查询'}

        if action == 'start':
            if site.is_expired():
                return {'error': '站点已过期，无法启动'}
            WebClient.start_site(
                webserver=webserver, siteName=site.name, sitePath=site.path,
            )
            site.status = True
            site.save()
            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'站点 {site.name} 启动成功'}

        elif action == 'stop':
            WebClient.stop_site(
                webserver=webserver, siteName=site.name, sitePath=site.path,
            )
            site.status = False
            site.save()
            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'站点 {site.name} 停止成功'}

        elif action == 'delete':
            isok, msg = WebClient.del_site(
                webserver=webserver, siteName=site.name,
                sitePath=site.path, id=str(site.id),
            )
            if not isok:
                return {'error': f'删除站点失败: {msg}'}
            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'站点 {site.name} 删除成功'}

    except Exception as e:
        return {'error': f'操作失败: {str(e)}'}


@register_tool(id='panel_site_domains', category='panel', name_cn='网站域名管理', risk_level='high')
def panel_site_domains(site_id: int, action: str = 'list', domain: str = '', port: int = 80):
    """管理如意面板中网站站点的域名绑定。⚠️添加/删除域名会修改Web服务器配置。

    Args:
        site_id: 站点ID（从panel_site_list返回的id获取）
        action: 操作类型，list(查看域名列表)、add(添加域名)、delete(删除域名)，默认list
        domain: 域名，如 example.com 或 www.example.com（add/delete时必填）
        port: 端口，默认80
    """
    try:
        site = Sites.objects.filter(id=site_id).first()
        if not site:
            return {'error': f'站点ID {site_id} 不存在'}

        if action == 'list':
            domains = SiteDomains.objects.filter(site=site)
            result = []
            for d in domains:
                result.append({
                    'id': d.id,
                    'name': d.name,
                    'port': d.port,
                })
            return {
                'site_name': site.name,
                'domains': result,
                'total': len(result),
            }

        elif action == 'add':
            if not domain:
                return {'error': '域名不能为空'}
            webserver = _get_webserver()
            if not webserver:
                return {'error': '未安装Web服务器'}

            if SiteDomains.objects.filter(name=domain, port=port).exists():
                return {'error': f'域名 {domain}:{port} 已被其他站点绑定'}

            from utils.ruyiclass.nginxClass import NginxClient
            nc = NginxClient(siteName=site.name, sitePath=site.path)
            isok, msg = nc.add_domain(domain=domain, port=port)
            if not isok:
                return {'error': f'添加域名失败: {msg}'}

            SiteDomains.objects.create(name=domain, port=port, site=site)
            WebClient.reload_service(webserver=webserver)

            return {'success': True, 'message': f'域名 {domain}:{port} 添加成功'}

        elif action == 'delete':
            if not domain:
                return {'error': '域名不能为空'}
            webserver = _get_webserver()
            if not webserver:
                return {'error': '未安装Web服务器'}

            domain_ins = SiteDomains.objects.filter(name=domain, port=port, site=site).first()
            if not domain_ins:
                return {'error': f'域名 {domain}:{port} 不属于此站点'}

            all_domains = SiteDomains.objects.filter(site=site)
            if all_domains.count() <= 1:
                return {'error': '站点至少需要保留一个域名，不能全部删除'}

            isok, msg = WebClient.del_site_domain(
                webserver=webserver, siteName=site.name,
                sitePath=site.path, domain=domain, port=port,
            )
            if not isok:
                return {'error': f'删除域名失败: {msg}'}

            domain_ins.delete()
            WebClient.reload_service(webserver=webserver)

            return {'success': True, 'message': f'域名 {domain}:{port} 删除成功'}

        else:
            return {'error': f'不支持的操作: {action}'}

    except Exception as e:
        return {'error': f'操作失败: {str(e)}'}


def _validate_python_application(project_cfg):
    framework = project_cfg.get("framework", "")
    application = project_cfg.get("application", "")
    if framework == "django":
        if not application:
            return False, "Django项目需要填写application，格式：模块名.wsgi:application名 或 模块名.asgi:application名"
        pattern = r'^[\w]+\.((wsgi)|(asgi)):[\w]+$'
        if not re.match(pattern, application):
            return False, "Django application格式错误，正确格式如：myproject.wsgi:application"
    elif framework == "flask":
        if not application:
            return False, "Flask项目需要填写application，格式：模块名:Flask实例名"
        pattern = r'^[\w]+:[\w]+$'
        if not re.match(pattern, application):
            return False, "Flask application格式错误，正确格式如：app:app"
    return True, ""


def _check_port_available(port):
    from utils.common import check_is_port, is_service_running
    port = int(port)
    if ruyiCheckPortInBlack(str(port)):
        return False, f"端口 {port} 在黑名单中"
    if not check_is_port(port):
        return False, f"端口 {port} 范围不合法"
    if is_service_running(port=port):
        return False, f"端口 {port} 被占用"
    return True, ""


@register_tool(id='panel_runtime_site_create', category='panel', name_cn='创建运行时项目站点', risk_level='high')
def panel_runtime_site_create(
    name: str,
    project_type: str,
    project_cfg: dict,
    domains: list = None,
    path: str = '',
    remark: str = ''
):
    """在如意面板中创建运行时项目站点（Python/Node/Go/PHP）。⚠️此为高危操作，会创建项目运行环境并配置Web服务器。

    部署项目时，先用此工具创建运行时站点，再用panel_site_create创建静态站点做反向代理，或用panel_site_proxy添加反向代理。

    project_cfg各类型说明：
    - Python: {"version":"3.10","framework":"django","application":"myproject.wsgi:application","start_method":"gunicorn","port":8000,"rukou":"myproject/wsgi.py","install_reqs":true,"requirements":"requirements.txt","protocol":"http"}
      - framework: python/django/flask/fastapi，纯python用"python"
      - start_method: command/gunicorn/uwsgi/daphne
      - application: Django格式"模块.wsgi:application名"，Flask格式"模块:实例名"
      - rukou: 入口文件路径（非command启动方式必填）
      - install_reqs: 是否安装依赖
      - requirements: 依赖文件名，如requirements.txt
      - protocol: http或socket
    - Node: {"version":"18","start_method":"command","start_command":"npm start","port":3000,"install_reqs":true,"package_json":"package.json"}
      - start_method: command/pm2
      - start_command: 启动命令
    - Go: {"version":"1.21","start_method":"command","start_command":"./main","port":8080,"bin":"main"}
      - start_method: command
      - bin: 编译后的二进制文件名
    - PHP: {"php_version":"8.1","port":9000,"start_method":"php-fpm"}
      - start_method: php-fpm

    Args:
        name: 项目名称，如 myblog、api-server
        project_type: 项目类型：python/node/go/php
        project_cfg: 项目配置字典，格式见上方说明
        domains: 域名列表，每个元素格式为 "域名:端口"，如 ["example.com:80"]。为空则不绑定域名（仅创建运行环境）
        path: 项目根目录，为空则自动生成默认路径
        remark: 备注信息
    """
    try:
        type_map = {'python': 1, 'node': 2, 'php': 3, 'go': 4}
        webserver_map = {'python': 'python', 'node': 'node', 'php': 'php', 'go': 'go'}

        if project_type not in type_map:
            return {'error': f'不支持的项目类型: {project_type}，可用: python, node, go, php'}

        site_type = type_map[project_type]
        runtime_webserver = webserver_map[project_type]

        if Sites.objects.filter(name=name).exists():
            return {'error': f'已存在同名站点: {name}'}

        start_method = project_cfg.get('start_method', '')
        port = project_cfg.get('port', '')

        if start_method != 'command' and port:
            port_ok, port_msg = _check_port_available(port)
            if not port_ok:
                return {'error': port_msg}

        if project_type == 'python':
            app_ok, app_msg = _validate_python_application(project_cfg)
            if not app_ok:
                return {'error': app_msg}
            rukou = project_cfg.get('rukou', '')
            framework = project_cfg.get('framework', '')
            if start_method not in ['command', 'daphne', 'uwsgi', 'gunicorn']:
                return {'error': f'Python启动方式错误: {start_method}，可用: command, gunicorn, uwsgi, daphne'}
            if start_method == 'command' and not project_cfg.get('start_command'):
                return {'error': 'command启动方式需要填写start_command'}
            if framework not in ['python'] and not rukou:
                return {'error': '非纯python项目需要填写入口文件(rukou)'}

        elif project_type == 'node':
            if start_method not in ['command', 'pm2']:
                return {'error': f'Node启动方式错误: {start_method}，可用: command, pm2'}
            if start_method == 'command' and not project_cfg.get('start_command'):
                return {'error': 'command启动方式需要填写start_command'}

        elif project_type == 'go':
            if start_method not in ['command']:
                return {'error': f'Go启动方式错误: {start_method}，可用: command'}
            if not project_cfg.get('start_command') and not project_cfg.get('bin'):
                return {'error': 'Go项目需要填写start_command或bin'}

        elif project_type == 'php':
            if not project_cfg.get('php_version'):
                return {'error': 'PHP项目需要填写php_version'}

        if not path:
            is_windows = current_os == 'windows'
            if is_windows:
                path = f'C:/wwwroot/{name}'
            else:
                path = f'/wwwroot/{name}'

        isok, msg = ruyiPathDirHandle(path, is_windows=(current_os == 'windows'))
        if not isok:
            return {'error': msg}

        domain_list = []
        if domains:
            for dm in domains:
                dm = str(dm).strip()
                if ':' in dm:
                    domain, port_str = dm.rsplit(':', 1)
                else:
                    domain = dm
                    port_str = '80'
                domain_list.append({'domain': domain, 'port': port_str})

        s_ins = Sites.objects.create(
            name=name,
            remark=remark,
            path=path,
            type=site_type,
            project_cfg=project_cfg,
        )

        if domain_list:
            for dm in domain_list:
                SiteDomains.objects.create(
                    name=dm['domain'], port=int(dm['port']), site=s_ins,
                )

        t = threading.Thread(
            target=WebClient.create_site,
            kwargs={
                'webserver': runtime_webserver,
                'siteName': name,
                'sitePath': path,
                'cont': project_cfg,
            }
        )
        t.start()

        return {
            'success': True,
            'message': f'{project_type.upper()}项目 {name} 开始创建，后台执行中',
            'site_id': s_ins.id,
            'name': name,
            'path': path,
            'type': site_type,
            'project_type': project_type,
            'project_cfg': project_cfg,
            'domains': domains or [],
        }
    except Exception as e:
        return {'error': f'创建运行时项目失败: {str(e)}'}


@register_tool(id='panel_site_ssl', category='panel', name_cn='网站SSL管理', risk_level='high')
def panel_site_ssl(site_id: int, action: str, ssl_type: str = 'letsencrypt', email: str = '', cert_content: str = '', key_content: str = '', force_https: bool = False):
    """管理如意面板中网站站点的SSL证书。⚠️此为高危操作，会修改Web服务器SSL配置。

    Args:
        site_id: 站点ID（从panel_site_list返回的id获取）
        action: 操作类型：
            - apply_letsencrypt: 申请Let's Encrypt免费证书（需先创建ACME账号）
            - apply_selfsigned: 生成自建SSL证书
            - save_custom: 保存自定义证书（需提供cert_content和key_content）
            - enable: 启用SSL
            - disable: 关闭SSL
            - force_https: 开启强制HTTPS跳转
            - cancel_force: 关闭强制HTTPS跳转
            - status: 查看SSL状态
        ssl_type: 证书类型，letsencrypt/self/custom
        email: 申请Let's Encrypt证书的邮箱（首次申请需先注册ACME账号）
        cert_content: 自定义证书PEM内容（save_custom时必填）
        key_content: 自定义私钥PEM内容（save_custom时必填）
        force_https: 是否开启强制HTTPS
    """
    try:
        webserver = _get_webserver()
        if not webserver:
            return {'error': '未安装Web服务器'}

        site = Sites.objects.filter(id=site_id).first()
        if not site:
            return {'error': f'站点ID {site_id} 不存在，请先用panel_site_list查询'}

        from utils.ruyiclass.nginxClass import NginxClient
        nc = NginxClient(siteName=site.name, sitePath=site.path)

        if action == 'status':
            import os
            cert_path = nc.sslBasePath + "/certificate.pem"
            key_path = nc.sslBasePath + "/privateKey.pem"
            has_cert = os.path.exists(cert_path) and os.path.exists(key_path)
            local_conf = ''
            try:
                from utils.common import ReadFile
                local_conf = ReadFile(nc.confPath) or ''
            except Exception:
                pass
            ssl_enabled = 'ssl_certificate' in local_conf
            force_enabled = 'RUYI_FORCE_HTTPS_START' in local_conf
            return {
                'site_name': site.name,
                'has_cert': has_cert,
                'ssl_enabled': ssl_enabled,
                'force_https': force_enabled,
                'cert_path': cert_path if has_cert else '',
            }

        elif action == 'apply_letsencrypt':
            if not email:
                return {'error': '申请Let\'s Encrypt证书需要提供email参数'}
            domains = SiteDomains.objects.filter(site=site)
            domain_names = [d.name for d in domains]
            if not domain_names:
                return {'error': '该站点没有绑定域名，请先添加域名'}
            for dm in domain_names:
                if '*' in dm:
                    return {'error': f'Let\'s Encrypt文件验证不支持泛域名: {dm}'}

            from utils.common import md5
            import datetime
            order_no = md5(json.dumps(domain_names) + str(site_id) + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            from apps.system.views.site_manage import apply_letsencrypt_certificate
            site_info = {"id": site.id, "name": site.name, "path": site.path}
            t = threading.Thread(
                target=apply_letsencrypt_certificate,
                args=(domain_names, site_info, 'file', order_no)
            )
            t.start()
            return {
                'success': True,
                'message': f'Let\'s Encrypt证书申请已启动，域名: {", ".join(domain_names)}',
                'order_no': order_no,
                'tip': '证书申请需要一定时间，可稍后使用status查看结果',
            }

        elif action == 'apply_selfsigned':
            domains = SiteDomains.objects.filter(site=site)
            domain_names = [d.name for d in domains]
            if not domain_names:
                domain_names = [site.name]

            from apps.system.views.site_manage import normalize_selfsigned_hosts, ensure_ruyi_root_certificate, create_signed_certificate
            ok, hosts_or_msg = normalize_selfsigned_hosts(domain_names)
            if not ok:
                return {'error': hosts_or_msg}
            root_ok, root_data = ensure_ruyi_root_certificate()
            if not root_ok:
                return {'error': root_data}
            cert_pem, key_pem = create_signed_certificate(
                root_cert=root_data['root_cert'],
                root_key=root_data['root_key'],
                hosts=hosts_or_msg,
            )
            isok, msg = WebClient.save_site_ssl_cert(
                webserver=webserver,
                siteName=site.name,
                sitePath=site.path,
                cont={
                    "cert": cert_pem.decode("utf-8"),
                    "key": key_pem.decode("utf-8"),
                    "root_password": root_data['root_password'],
                }
            )
            if not isok:
                return {'error': f'保存自建证书失败: {msg}'}

            isok2, msg2 = nc.set_site_ssl_status({'status': True})
            if not isok2:
                return {'error': f'启用SSL失败: {msg2}'}

            WebClient.reload_service(webserver=webserver)
            return {
                'success': True,
                'message': f'自建SSL证书已生成并启用，域名: {", ".join(domain_names)}',
                'tip': '自建证书浏览器会提示不安全，建议生产环境使用Let\'s Encrypt证书',
            }

        elif action == 'save_custom':
            if not cert_content or not key_content:
                return {'error': '自定义证书需要提供cert_content和key_content'}
            isok, msg = WebClient.save_site_ssl_cert(
                webserver=webserver,
                siteName=site.name,
                sitePath=site.path,
                cont={"cert": cert_content, "key": key_content}
            )
            if not isok:
                return {'error': f'保存自定义证书失败: {msg}'}
            isok2, msg2 = nc.set_site_ssl_status({'status': True})
            if not isok2:
                return {'error': f'启用SSL失败: {msg2}'}
            if force_https:
                nc.set_site_ssl_forcehttps({'status': True})
            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'自定义证书已保存并启用'}

        elif action == 'enable':
            isok, msg = nc.set_site_ssl_status({'status': True})
            if not isok:
                return {'error': f'启用SSL失败: {msg}'}
            if force_https:
                nc.set_site_ssl_forcehttps({'status': True})
            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'站点 {site.name} SSL已启用'}

        elif action == 'disable':
            nc.set_site_ssl_forcehttps({'status': False})
            isok, msg = nc.set_site_ssl_status({'status': False})
            if not isok:
                return {'error': f'关闭SSL失败: {msg}'}
            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'站点 {site.name} SSL已关闭'}

        elif action == 'force_https':
            isok, msg = nc.set_site_ssl_forcehttps({'status': True})
            if not isok:
                return {'error': f'开启强制HTTPS失败: {msg}'}
            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'站点 {site.name} 强制HTTPS已开启'}

        elif action == 'cancel_force':
            nc.set_site_ssl_forcehttps({'status': False})
            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'站点 {site.name} 强制HTTPS已关闭'}

        else:
            return {'error': f'不支持的操作: {action}'}

    except Exception as e:
        return {'error': f'SSL操作失败: {str(e)}'}


@register_tool(id='panel_site_proxy', category='panel', name_cn='网站反向代理管理', risk_level='high')
def panel_site_proxy(
    site_id: int,
    action: str = 'list',
    proxy_name: str = '',
    proxy_path: str = '/',
    proxy_pass: str = '',
    proxy_host: str = '',
    websocket: bool = False,
    cache: bool = False,
    cache_time: int = 1,
    cache_unit: str = 'm',
):
    """管理如意面板中网站站点的反向代理配置。⚠️此为高危操作，会修改Web服务器配置。

    典型部署流程：先创建运行时项目站点(panel_runtime_site_create)启动项目，再创建静态站点(panel_site_create)绑定域名，最后用此工具添加反向代理将域名请求转发到项目端口。

    Args:
        site_id: 站点ID（从panel_site_list返回的id获取）
        action: 操作类型：list(查看代理列表)、add(添加反向代理)、delete(删除反向代理)
        proxy_name: 代理名称，2-30个字符，英文标识（add/delete时必填）
        proxy_path: 代理路径，如 / 或 /api（add时必填）
        proxy_pass: 转发目标URL，如 http://127.0.0.1:8000（add时必填）
        proxy_host: 发送给后端的Host头，通常与域名一致，如 example.com（add时必填）
        websocket: 是否启用WebSocket支持
        cache: 是否启用缓存
        cache_time: 缓存时间（cache为true时有效）
        cache_unit: 缓存时间单位，s(秒)/m(分)/h(时)/d(天)
    """
    try:
        webserver = _get_webserver()
        if not webserver:
            return {'error': '未安装Web服务器'}

        site = Sites.objects.filter(id=site_id).first()
        if not site:
            return {'error': f'站点ID {site_id} 不存在，请先用panel_site_list查询'}

        from utils.ruyiclass.nginxClass import NginxClient
        from utils.common import ReadFile, ast_convert
        nc = NginxClient(siteName=site.name, sitePath=site.path)

        if action == 'list':
            proxy_cont = []
            try:
                raw = ReadFile(nc.proxyPath)
                if raw:
                    proxy_cont = json.loads(raw)
            except Exception:
                pass
            return {
                'site_name': site.name,
                'proxies': proxy_cont,
                'total': len(proxy_cont),
            }

        elif action == 'add':
            if not proxy_name:
                return {'error': '代理名称不能为空'}
            if not proxy_path:
                return {'error': '代理路径不能为空'}
            if not proxy_pass:
                return {'error': '转发目标URL不能为空'}
            if not proxy_host:
                return {'error': '发送域名不能为空'}

            isok, msg = nc.set_site_proxy({
                'operate': 'add',
                'name': proxy_name,
                'proxyPath': proxy_path,
                'proxyPass': proxy_pass,
                'proxyHost': proxy_host,
                'websocket': websocket,
                'cache': cache,
                'cacheTime': cache_time,
                'cacheUnit': cache_unit,
                'sniEnable': False,
                'subFilters': [],
                'advanced': False,
                'status': True,
                'proxyType': 'http',
            })
            if not isok:
                return {'error': f'添加反向代理失败: {msg}'}

            WebClient.reload_service(webserver=webserver)
            return {
                'success': True,
                'message': f'反向代理 {proxy_name} 添加成功: {proxy_path} -> {proxy_pass}',
            }

        elif action == 'delete':
            if not proxy_name:
                return {'error': '代理名称不能为空'}

            isok, msg = nc.set_site_proxy({
                'operate': 'del',
                'name': proxy_name,
            })
            if not isok:
                return {'error': f'删除反向代理失败: {msg}'}

            WebClient.reload_service(webserver=webserver)
            return {'success': True, 'message': f'反向代理 {proxy_name} 删除成功'}

        else:
            return {'error': f'不支持的操作: {action}'}

    except Exception as e:
        return {'error': f'反向代理操作失败: {str(e)}'}


@register_tool(id='panel_deploy_project', category='panel', name_cn='一键部署项目', risk_level='high')
def panel_deploy_project(
    name: str,
    project_type: str,
    project_cfg: dict,
    domains: list,
    path: str = '',
    enable_ssl: bool = False,
    ssl_type: str = 'letsencrypt',
    ssl_email: str = '',
    force_https: bool = False,
    remark: str = '',
):
    """一键部署项目到如意面板，自动完成：创建运行时站点 → 创建Nginx静态站点绑定域名 → 配置反向代理 → 可选配置SSL。

    这是部署项目的推荐工具，会自动完成所有步骤。典型场景：
    - 部署Django/Flask/FastAPI项目：project_type="python"，framework填对应框架
    - 部署Express/Next.js项目：project_type="node"
    - 部署Go项目：project_type="go"
    - 部署PHP项目：project_type="php"

    部署原理：
    1. 创建运行时站点（Python/Node/Go/PHP），项目运行在本地端口（如127.0.0.1:8000）
    2. 创建Nginx静态站点，绑定域名，监听80/443端口
    3. 在Nginx站点上配置反向代理，将域名请求转发到运行时项目的本地端口
    4. 可选：配置SSL证书（Let's Encrypt/自建/自定义）

    project_cfg各类型说明：
    - Python: {"version":"3.10","framework":"django","application":"myproject.wsgi:application","start_method":"gunicorn","port":8000,"rukou":"myproject/wsgi.py","install_reqs":true,"requirements":"requirements.txt","protocol":"http"}
      - framework: python/django/flask/fastapi，纯python用"python"
      - start_method: command/gunicorn/uwsgi/daphne
      - application: Django格式"模块.wsgi:application名"，Flask格式"模块:实例名"
      - rukou: 入口文件路径（非command启动方式必填）
      - install_reqs: 是否安装依赖
      - requirements: 依赖文件名，如requirements.txt
    - Node: {"version":"18","start_method":"command","start_command":"npm start","port":3000,"install_reqs":true,"package_json":"package.json"}
    - Go: {"version":"1.21","start_method":"command","start_command":"./main","port":8080,"bin":"main"}
    - PHP: {"php_version":"8.1","port":9000,"start_method":"php-fpm"}

    Args:
        name: 项目名称，如 myblog、api-server（同时作为运行时站点和Nginx站点的名称）
        project_type: 项目类型：python/node/go/php
        project_cfg: 项目配置字典，格式见上方说明
        domains: 域名列表，每个元素格式为 "域名:端口"，如 ["example.com:80", "www.example.com:80"]
        path: 项目根目录，为空则自动生成默认路径
        enable_ssl: 是否启用SSL证书
        ssl_type: SSL证书类型：letsencrypt（需域名已解析）、selfsigned（自建证书，浏览器会提示不安全）、custom（自定义证书）
        ssl_email: 申请Let's Encrypt证书的邮箱
        force_https: 是否开启强制HTTPS跳转（需enable_ssl为true）
        remark: 备注信息
    """
    try:
        type_map = {'python': 1, 'node': 2, 'php': 3, 'go': 4}
        webserver_map = {'python': 'python', 'node': 'node', 'php': 'php', 'go': 'go'}

        if project_type not in type_map:
            return {'error': f'不支持的项目类型: {project_type}，可用: python, node, go, php'}

        if not domains:
            return {'error': '域名列表不能为空，部署项目需要绑定域名'}

        site_type = type_map[project_type]
        runtime_webserver = webserver_map[project_type]

        if Sites.objects.filter(name=name).exists():
            return {'error': f'已存在同名站点: {name}'}

        start_method = project_cfg.get('start_method', '')
        port = project_cfg.get('port', '')

        if start_method != 'command' and port:
            port_ok, port_msg = _check_port_available(port)
            if not port_ok:
                return {'error': port_msg}

        if project_type == 'python':
            app_ok, app_msg = _validate_python_application(project_cfg)
            if not app_ok:
                return {'error': app_msg}
            rukou = project_cfg.get('rukou', '')
            framework = project_cfg.get('framework', '')
            if start_method not in ['command', 'daphne', 'uwsgi', 'gunicorn']:
                return {'error': f'Python启动方式错误: {start_method}'}
            if start_method == 'command' and not project_cfg.get('start_command'):
                return {'error': 'command启动方式需要填写start_command'}
            if framework not in ['python'] and not rukou:
                return {'error': '非纯python项目需要填写入口文件(rukou)'}

        elif project_type == 'node':
            if start_method not in ['command', 'pm2']:
                return {'error': f'Node启动方式错误: {start_method}'}
            if start_method == 'command' and not project_cfg.get('start_command'):
                return {'error': 'command启动方式需要填写start_command'}

        elif project_type == 'go':
            if start_method not in ['command']:
                return {'error': f'Go启动方式错误: {start_method}'}
            if not project_cfg.get('start_command') and not project_cfg.get('bin'):
                return {'error': 'Go项目需要填写start_command或bin'}

        elif project_type == 'php':
            if not project_cfg.get('php_version'):
                return {'error': 'PHP项目需要填写php_version'}

        if not path:
            is_windows = current_os == 'windows'
            if is_windows:
                path = f'C:/wwwroot/{name}'
            else:
                path = f'/wwwroot/{name}'

        isok, msg = ruyiPathDirHandle(path, is_windows=(current_os == 'windows'))
        if not isok:
            return {'error': msg}

        nginx_webserver = _get_webserver()
        if not nginx_webserver:
            return {'error': '未安装Nginx，请先使用panel_shop_install安装Nginx'}

        domain_list = []
        for dm in domains:
            dm = str(dm).strip()
            if ':' in dm:
                domain, port_str = dm.rsplit(':', 1)
            else:
                domain = dm
                port_str = '80'
            domain_list.append({'domain': domain, 'port': port_str})

        steps_completed = []
        errors = []

        # Step 1: 创建运行时站点
        runtime_site_name = name
        runtime_site = Sites.objects.create(
            name=runtime_site_name,
            remark=remark,
            path=path,
            type=site_type,
            project_cfg=project_cfg,
        )
        for dm in domain_list:
            SiteDomains.objects.create(
                name=dm['domain'], port=int(dm['port']), site=runtime_site,
            )

        t = threading.Thread(
            target=WebClient.create_site,
            kwargs={
                'webserver': runtime_webserver,
                'siteName': runtime_site_name,
                'sitePath': path,
                'cont': project_cfg,
            }
        )
        t.start()
        steps_completed.append(f'1. 创建{project_type.upper()}运行时站点 {runtime_site_name}（后台执行中）')

        # Step 2: 创建Nginx静态站点（用于反向代理和SSL）
        # Nginx站点名称与运行时站点相同，因为不同type的站点配置文件在不同目录下不会冲突
        # 但数据库中name字段不唯一，前端按type分Tab显示，所以同名不会混淆
        nginx_site_name = name
        nginx_path = path
        nginx_site = Sites.objects.create(
            name=nginx_site_name,
            remark=f'[Nginx反向代理] {remark}',
            path=nginx_path,
            type=0,
        )
        for dm in domain_list:
            SiteDomains.objects.create(
                name=dm['domain'], port=int(dm['port']), site=nginx_site,
            )

        isok2, msg2 = WebClient.create_site(
            webserver=nginx_webserver,
            domainList=domain_list,
            siteName=nginx_site_name,
            sitePath=nginx_path,
        )
        if not isok2:
            errors.append(f'创建Nginx站点失败: {msg2}')
        else:
            steps_completed.append(f'2. 创建Nginx静态站点，绑定域名: {", ".join(d["domain"] for d in domain_list)}')

        # Step 3: 配置反向代理
        if isok2 and port:
            from utils.ruyiclass.nginxClass import NginxClient
            nc = NginxClient(siteName=nginx_site_name, sitePath=nginx_path)
            proxy_pass = f'http://127.0.0.1:{port}'
            proxy_host = domain_list[0]['domain'] if domain_list else name
            isok3, msg3 = nc.set_site_proxy({
                'operate': 'add',
                'name': f'proxy_to_{name}',
                'proxyPath': '/',
                'proxyPass': proxy_pass,
                'proxyHost': proxy_host,
                'websocket': True,
                'cache': False,
                'cacheTime': 1,
                'cacheUnit': 'm',
                'sniEnable': False,
                'subFilters': [],
                'advanced': False,
                'status': True,
                'proxyType': 'http',
            })
            if not isok3:
                errors.append(f'配置反向代理失败: {msg3}')
            else:
                steps_completed.append(f'3. 配置反向代理: / → {proxy_pass}')

        # Step 4: 配置SSL
        if enable_ssl and isok2 and not errors:
            from utils.ruyiclass.nginxClass import NginxClient
            nc = NginxClient(siteName=nginx_site_name, sitePath=nginx_path)

            if ssl_type == 'selfsigned':
                domain_names = [d['domain'] for d in domain_list]
                try:
                    from apps.system.views.site_manage import normalize_selfsigned_hosts, ensure_ruyi_root_certificate, create_signed_certificate
                    ok, hosts_or_msg = normalize_selfsigned_hosts(domain_names)
                    if ok:
                        root_ok, root_data = ensure_ruyi_root_certificate()
                        if root_ok:
                            cert_pem, key_pem = create_signed_certificate(
                                root_cert=root_data['root_cert'],
                                root_key=root_data['root_key'],
                                hosts=hosts_or_msg,
                            )
                            isok4, msg4 = WebClient.save_site_ssl_cert(
                                webserver=nginx_webserver,
                                siteName=nginx_site_name,
                                sitePath=nginx_path,
                                cont={
                                    "cert": cert_pem.decode("utf-8"),
                                    "key": key_pem.decode("utf-8"),
                                    "root_password": root_data['root_password'],
                                }
                            )
                            if isok4:
                                nc.set_site_ssl_status({'status': True})
                                if force_https:
                                    nc.set_site_ssl_forcehttps({'status': True})
                                steps_completed.append('4. 生成自建SSL证书并启用' + ('，强制HTTPS' if force_https else ''))
                            else:
                                errors.append(f'保存SSL证书失败: {msg4}')
                        else:
                            errors.append(f'创建根证书失败: {root_data}')
                    else:
                        errors.append(f'域名格式错误: {hosts_or_msg}')
                except Exception as e:
                    errors.append(f'自建SSL配置失败: {str(e)}')

            elif ssl_type == 'letsencrypt':
                if not ssl_email:
                    errors.append('Let\'s Encrypt证书需要提供ssl_email参数')
                else:
                    domain_names = [d['domain'] for d in domain_list]
                    has_wildcard = any('*' in dm for dm in domain_names)
                    if has_wildcard:
                        errors.append('Let\'s Encrypt文件验证不支持泛域名')
                    else:
                        try:
                            from utils.common import md5
                            import datetime
                            order_no = md5(json.dumps(domain_names) + str(nginx_site.id) + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            from apps.system.views.site_manage import apply_letsencrypt_certificate
                            site_info = {"id": nginx_site.id, "name": nginx_site_name, "path": nginx_path}
                            t2 = threading.Thread(
                                target=apply_letsencrypt_certificate,
                                args=(domain_names, site_info, 'file', order_no)
                            )
                            t2.start()
                            steps_completed.append(f'4. Let\'s Encrypt证书申请已启动（后台执行），域名: {", ".join(domain_names)}')
                        except Exception as e:
                            errors.append(f'Let\'s Encrypt申请失败: {str(e)}')

        WebClient.reload_service(webserver=nginx_webserver)

        result = {
            'success': len(errors) == 0,
            'message': f'项目 {name} 部署{"完成" if not errors else "部分完成"}',
            'steps_completed': steps_completed,
            'runtime_site_id': runtime_site.id,
            'nginx_site_id': nginx_site.id,
            'project_type': project_type,
            'project_port': port,
            'domains': [d['domain'] for d in domain_list],
        }
        if errors:
            result['errors'] = errors
        if enable_ssl:
            result['ssl_type'] = ssl_type

        return result

    except Exception as e:
        return {'error': f'一键部署失败: {str(e)}'}
