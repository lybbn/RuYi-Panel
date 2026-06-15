"""
如意面板AI助手 - 环境探测工具
探测服务器当前环境状态，为部署决策提供依据
"""
import os
import re
import socket
import psutil
from apps.sysai.tools.base import register_tool
from apps.sysai.tools.common import run_cmd, check_port_occupied
from utils.common import current_os, RunCommand, GetWebRootPath
from utils.install.install_soft import Check_Soft_Installed


def _get_server_ips() -> dict:
    """获取服务器内网IP和外网IP"""
    result = {'internal_ip': '', 'external_ip': ''}
    
    # 获取内网IP（从网络接口）
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            if iface in ('lo', 'Loopback Pseudo-Interface 1'):
                continue
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    ip = addr.address
                    # 优先选择私有地址
                    if ip.startswith(('10.', '172.', '192.168.')):
                        result['internal_ip'] = ip
                        break
                    elif not result['internal_ip']:
                        result['internal_ip'] = ip
            if result['internal_ip']:
                break
    except Exception:
        pass
    
    # 获取外网IP（从data/public_ip.ry文件读取）
    try:
        from django.conf import settings
        public_ip_file = os.path.join(settings.BASE_DIR, 'data', 'public_ip.ry')
        if os.path.exists(public_ip_file):
            with open(public_ip_file, 'r') as f:
                ip = f.read().strip()
                if ip:
                    result['external_ip'] = ip
    except Exception:
        pass
    
    # 如果外网IP获取失败，使用内网IP
    if not result['external_ip']:
        result['external_ip'] = result['internal_ip']
    
    return result


def _get_docker_status() -> dict:
    """获取Docker安装和运行状态"""
    result = {'installed': False, 'running': False, 'version': '', 'compose': False}
    try:
        # 先通过应用商店检测Docker
        from apps.sysshop.models import RySoftShop
        docker_shop = RySoftShop.objects.filter(name='docker').first()
        if docker_shop and docker_shop.installed:
            result['installed'] = True
            result['version'] = docker_shop.version or ''
            result['running'] = docker_shop.status if isinstance(docker_shop.status, bool) else bool(docker_shop.status)
    except Exception:
        pass
    # 补充检测：通过命令行验证
    try:
        ret = RunCommand('docker --version')
        if ret and 'Docker version' in ret:
            result['installed'] = True
            ver_match = re.search(r'version\s+([\d.]+)', ret)
            if ver_match:
                result['version'] = ver_match.group(1)
    except Exception:
        pass
    try:
        # 检查Docker是否运行
        ret2 = RunCommand('docker info --format "{{.ServerVersion}}"')
        if ret2 and ret2.strip() and 'error' not in ret2.lower():
            result['running'] = True
    except Exception:
        pass
    try:
        # 检查docker compose
        ret3 = RunCommand('docker compose version')
        if ret3 and 'Docker Compose version' in ret3:
            result['compose'] = True
    except Exception:
        pass
    return result


def _get_webserver_status() -> dict:
    """获取Web服务器状态"""
    result = {'installed': False, 'name': '', 'version': ''}
    try:
        from apps.sysshop.models import RySoftShop
        web_ins = RySoftShop.objects.filter(type=3).first()
        if web_ins:
            installed, version, status, install_path = Check_Soft_Installed(
                name=web_ins.name, is_windows=current_os == 'windows', get_status=False
            )
            if installed:
                result['installed'] = True
                result['name'] = web_ins.name
                result['version'] = version or ''
    except Exception:
        pass
    return result


def _get_databases_status() -> list:
    """获取数据库安装状态（包括本地安装和Docker广场安装）"""
    databases = []
    db_softs = [
        {'name': 'mysql', 'title': 'MySQL', 'default_port': 3306},
        {'name': 'mariadb', 'title': 'MariaDB', 'default_port': 3306},
        {'name': 'postgresql', 'title': 'PostgreSQL', 'default_port': 5432},
        {'name': 'redis', 'title': 'Redis', 'default_port': 6379},
        {'name': 'mongodb', 'title': 'MongoDB', 'default_port': 27017},
    ]
    for db in db_softs:
        try:
            installed, version, status, install_path = Check_Soft_Installed(
                name=db['name'], is_windows=current_os == 'windows', get_status=True
            )
            # 补充检测Docker广场安装的数据库
            if not installed:
                try:
                    from apps.sysdocker.models import RyDockerApps
                    dk_db = RyDockerApps.objects.filter(appname=db['name']).first()
                    if dk_db:
                        installed = True
                        version = dk_db.version or ''
                        status = dk_db.status or ''
                except Exception:
                    pass
            databases.append({
                'name': db['name'],
                'title': db['title'],
                'installed': installed,
                'version': version or '',
                'status': status if installed else '',
                'default_port': db['default_port'],
                'port_occupied': check_port_occupied(db['default_port']) if installed else False,
            })
        except Exception:
            databases.append({
                'name': db['name'],
                'title': db['title'],
                'installed': False,
                'version': '',
                'status': '',
                'default_port': db['default_port'],
                'port_occupied': False,
            })
    return databases


def _get_languages_status() -> list:
    """获取运行环境状态"""
    languages = []
    lang_softs = [
        {'name': 'php', 'title': 'PHP'},
        {'name': 'python', 'title': 'Python'},
        {'name': 'go', 'title': 'Go'},
        {'name': 'node', 'title': 'Node.js'},
        {'name': 'java', 'title': 'Java'},
    ]
    for lang in lang_softs:
        try:
            installed, version, status, install_path = Check_Soft_Installed(
                name=lang['name'], is_windows=current_os == 'windows', get_status=False
            )
            languages.append({
                'name': lang['name'],
                'title': lang['title'],
                'installed': installed,
                'version': version or '',
            })
        except Exception:
            languages.append({
                'name': lang['name'],
                'title': lang['title'],
                'installed': False,
                'version': '',
            })
    return languages


def _get_common_ports_status() -> dict:
    """获取常用端口占用情况"""
    ports_to_check = [80, 443, 3306, 5432, 6379, 8080, 8443, 9000, 27017]
    occupied = []
    free = []
    for port in ports_to_check:
        if check_port_occupied(port):
            occupied.append(port)
        else:
            free.append(port)
    return {'occupied': occupied, 'free': free}


def _get_disk_free() -> float:
    """获取根分区可用空间(GB)"""
    try:
        if current_os == 'windows':
            import shutil
            total, used, free = shutil.disk_usage('C:\\')
        else:
            stat = os.statvfs('/')
            free = stat.f_bavail * stat.f_frsize
        return round(free / (1024 ** 3), 1)
    except Exception:
        return 0.0


@register_tool(id='panel_environment_probe', category='panel', name_cn='环境探测', risk_level='low')
def panel_environment_probe():
    """探测服务器当前环境状态，包括已安装的软件、Docker状态、数据库、运行环境、端口占用、磁盘空间等。
    在部署任何应用前必须先调用此工具了解环境状态，以便做出正确的部署决策。

    返回内容：
    - docker: Docker安装状态、版本、是否运行
    - webserver: Web服务器（Nginx/OpenResty）安装状态
    - databases: 已安装的数据库列表及状态
    - languages: 已安装的运行环境（PHP/Python/Go/Node等）
    - ports: 常用端口占用情况
    - disk_free_gb: 根分区可用空间
    - wwwroot_path: 网站根目录路径（用于部署项目）
    - platform: 操作系统信息
    - server_ips: 服务器IP信息（internal_ip内网IP, external_ip外网IP）

    典型用途：
    - 部署WordPress前检查Docker和MySQL状态
    - 部署Django项目前检查Python和Nginx状态
    - 安装软件前检查端口是否被占用
    - 获取网站根目录路径用于部署项目
    - 获取服务器IP用于配置站点域名
    """
    try:
        return {
            'docker': _get_docker_status(),
            'webserver': _get_webserver_status(),
            'databases': _get_databases_status(),
            'languages': _get_languages_status(),
            'ports': _get_common_ports_status(),
            'disk_free_gb': _get_disk_free(),
            'wwwroot_path': GetWebRootPath(),
            'platform': {
                'os': current_os,
                'arch': os.environ.get('PROCESSOR_ARCHITECTURE', 'unknown') if current_os == 'windows' else '',
            },
            'server_ips': _get_server_ips(),
        }
    except Exception as e:
        return {'error': f'环境探测失败: {str(e)}'}


@register_tool(id='panel_find_free_port', category='panel', name_cn='查找可用端口', risk_level='low')
def panel_find_free_port(start_port: int = 3000, end_port: int = 65535, count: int = 1):
    """查找服务器上可用的端口号。在部署项目时如果默认端口被占用，调用此工具寻找可用端口。

    Args:
        start_port: 起始端口号，默认3000
        end_port: 结束端口号，默认65535（实际最多扫描到start_port+500）
        count: 需要查找的可用端口数量，默认1
    """
    try:
        free_ports = []
        # 限制扫描范围，避免耗时过长
        actual_end = min(end_port, start_port + 500)
        for port in range(start_port, actual_end + 1):
            if not check_port_occupied(port):
                free_ports.append(port)
                if len(free_ports) >= count:
                    break
        if not free_ports:
            return {'error': f'在 {start_port}-{actual_end} 范围内未找到可用端口'}
        return {
            'free_ports': free_ports,
            'first_free': free_ports[0],
        }
    except Exception as e:
        return {'error': f'查找端口失败: {str(e)}'}


@register_tool(id='panel_deploy_verify', category='panel', name_cn='部署验证', risk_level='low')
def panel_deploy_verify(url: str = '', port: int = 0, host: str = '127.0.0.1', timeout: int = 10, retry: int = 3):
    """验证部署的服务是否正常运行。部署完成后必须调用此工具确认服务可访问。

    验证方式：
    1. 如果提供url，发起HTTP请求检查响应状态码
    2. 如果提供port，检查端口是否有服务监听
    3. 两者都提供时同时验证

    Args:
        url: 要验证的URL地址，如 http://example.com 或 http://127.0.0.1:8000
        port: 要验证的端口号
        host: 端口验证的主机地址，默认127.0.0.1
        timeout: 请求超时时间（秒），默认10
        retry: 重试次数，默认3（服务启动可能需要几秒）
    """
    import time
    import http.client

    result = {
        'success': False,
        'url_check': None,
        'port_check': None,
        'errors': [],
    }

    # 如果只传了port没传url，自动构造HTTP URL进行检查
    if port and not url:
        url = f'http://{host}:{port}'

    # 端口检查（带重试）
    if port:
        for attempt in range(retry):
            if check_port_occupied(port):
                result['port_check'] = {'port': port, 'listening': True}
                break
            if attempt < retry - 1:
                time.sleep(2)
        else:
            result['port_check'] = {'port': port, 'listening': False}
            result['errors'].append(f'端口 {port} 无服务监听（已重试{retry}次）')

    # URL检查（带重试）
    if url:
        for attempt in range(retry):
            try:
                import ssl
                from urllib.parse import urlparse
                parsed = urlparse(url)
                is_https = parsed.scheme == 'https'
                url_port = parsed.port or (443 if is_https else 80)
                hostname = parsed.hostname or host
                if is_https:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    conn = http.client.HTTPSConnection(hostname, url_port, timeout=timeout, context=ctx)
                else:
                    conn = http.client.HTTPConnection(hostname, url_port, timeout=timeout)
                path = parsed.path or '/'
                if parsed.query:
                    path += '?' + parsed.query
                conn.request('GET', path, headers={'Host': hostname})
                resp = conn.getresponse()
                result['url_check'] = {
                    'url': url,
                    'status_code': resp.status,
                    'reachable': True,
                }
                conn.close()
                break
            except Exception as e:
                if attempt < retry - 1:
                    time.sleep(3)
                else:
                    result['url_check'] = {
                        'url': url,
                        'status_code': 0,
                        'reachable': False,
                        'error': str(e),
                    }
                    result['errors'].append(f'URL {url} 不可访问: {str(e)}')

    # 综合判断
    if url and port:
        result['success'] = (result['url_check'] or {}).get('reachable', False) and (result['port_check'] or {}).get('listening', False)
    elif url:
        result['success'] = (result['url_check'] or {}).get('reachable', False)
    elif port:
        result['success'] = (result['port_check'] or {}).get('listening', False)

    # 检查HTTP状态码，4xx/5xx视为失败
    status_code = (result.get('url_check') or {}).get('status_code', 0)
    if result['success'] and status_code >= 400:
        result['success'] = False
        result['errors'].append(f'HTTP状态码 {status_code}，服务可能未正常启动，请检查应用日志和数据库配置')

    # 验证失败时，提供排查指引
    if not result['success']:
        result['troubleshooting'] = {
            'message': '⚠️ 部署验证失败！禁止标记任务为completed，必须先排查原因',
            'steps': [
                '1. 检查依赖服务是否启动（如MySQL容器是否running）',
                '2. 检查数据库是否已创建（使用 panel_database_list）',
                '3. 查看容器日志（使用 docker_container_logs）',
                '4. 排查修复后，重新调用 panel_deploy_verify 验证',
            ],
            'common_causes': {
                '500': '数据库未创建或连接失败，使用 panel_database_create 创建数据库',
                '502': '依赖服务未启动，等待或重启依赖服务',
                'connection_refused': '服务未启动，等待容器启动后重试',
            },
        }

    # 部署后推荐配置
    if result['success']:
        result['post_deploy_recommendation'] = {
            'message': '部署成功！建议继续配置以下选项以提升安全性和访问体验：',
            'recommended_actions': [
                {'action': '域名绑定 + Nginx反向代理', 'reason': '支持域名访问，可申请SSL证书'},
                {'action': '防火墙端口放通', 'reason': '允许外部网络访问服务'},
                {'action': 'WAF防护', 'reason': '防护SQL注入、XSS等Web攻击'},
                {'action': 'SSL证书', 'reason': 'HTTPS加密访问，提升安全性'},
            ],
            'hint': '使用 panel_deploy_finalize 工具可一站式完成以上配置',
        }

    return result


@register_tool(id='panel_deploy_finalize', category='panel', name_cn='部署后处理', risk_level='high')
def panel_deploy_finalize(
    app_name: str,
    app_port: int,
    domain: str = '',
    enable_nginx_proxy: bool = False,
    open_firewall: bool = True,
    waf_mode: str = '',
):
    """部署应用后的收尾处理，一站式完成：Nginx反向代理配置、防火墙端口放通、WAF防护设置。

    此工具在应用部署成功后调用，根据用户选择自动完成以下操作：
    1. 【Nginx反向代理】如果enable_nginx_proxy=True且提供了domain，创建网站站点并配置反向代理，使应用可通过域名访问并受WAF防护。Nginx未安装时会自动通过应用商店安装
    2. 【防火墙放通】如果open_firewall=True，自动放通应用端口（和Nginx的80/443端口）
    3. 【WAF防护】如果waf_mode非空且Nginx站点已创建，为站点设置WAF防护模式

    Args:
        app_name: 应用名称，用于创建Nginx站点名，如 wordpress、blog
        app_port: 应用服务端口，如 18080、13306
        domain: 访问域名，如 blog.example.com。为空则仅通过IP:端口访问（不配置Nginx）
        enable_nginx_proxy: 是否配置Nginx反向代理。True时需要domain，Nginx未安装会自动安装
        open_firewall: 是否放通防火墙端口，默认True
        waf_mode: WAF防护模式，off(关闭)、observe(观察模式-仅记录不拦截)、protect(拦截模式-记录并拦截)。为空则不设置WAF
    """
    result = {
        'app_name': app_name,
        'app_port': app_port,
        'domain': domain,
        'nginx_proxy': None,
        'firewall': None,
        'waf': None,
        'errors': [],
        'access_url': '',
    }

    from apps.sysai.tools.base import AIToolRegistry
    registry = AIToolRegistry()

    # ── 1. Nginx反向代理 ──
    if enable_nginx_proxy:
        if not domain:
            result['errors'].append('启用Nginx反向代理需要提供domain参数')
            result['nginx_proxy'] = {'configured': False, 'reason': '缺少域名'}
        else:
            # 检查Nginx是否已安装，未安装则自动安装
            registry.emit_progress('panel_deploy_finalize', 'tool.log', 0, '正在检查Nginx安装状态...')
            webserver_installed = _get_webserver_status().get('installed', False)
            if not webserver_installed:
                registry.emit_progress('panel_deploy_finalize', 'tool.log', 0, 'Nginx未安装，正在通过应用商店自动安装...')
                try:
                    from apps.sysai.tools.panel_shop import panel_shop_install
                    install_res = panel_shop_install(name='nginx')
                    if install_res.get('error'):
                        result['errors'].append(f'Nginx未安装且自动安装失败: {install_res["error"]}')
                        result['nginx_proxy'] = {'configured': False, 'reason': f'Nginx未安装，自动安装失败: {install_res["error"]}'}
                    else:
                        task_id = install_res.get('task_id', 0)
                        # 等待安装完成（最多5分钟）
                        import time
                        max_wait = 300
                        waited = 0
                        nginx_installed = False
                        while waited < max_wait:
                            time.sleep(10)
                            waited += 10
                            registry.emit_progress('panel_deploy_finalize', 'tool.log', 0, f'等待Nginx安装完成... ({waited}s/{max_wait}s)')
                            webserver_installed = _get_webserver_status().get('installed', False)
                            if webserver_installed:
                                nginx_installed = True
                                break
                            # 检查任务状态
                            if task_id:
                                try:
                                    from apps.sysai.tools.panel_shop import panel_shop_task_status
                                    task_res = panel_shop_task_status(task_id=task_id)
                                    status_code = task_res.get('status_code', -1)
                                    if status_code == 3:  # 成功
                                        nginx_installed = True
                                        break
                                    elif status_code == 2:  # 失败
                                        log_tail = task_res.get('log_tail', '')
                                        result['errors'].append(f'Nginx安装失败，日志: {log_tail[:500]}')
                                        break
                                except Exception:
                                    pass
                        if not nginx_installed:
                            result['errors'].append(f'Nginx自动安装超时（等待{waited}秒），请稍后手动检查安装状态')
                            result['nginx_proxy'] = {'configured': False, 'reason': 'Nginx安装超时'}
                except Exception as e:
                    result['errors'].append(f'Nginx自动安装异常: {str(e)}')
                    result['nginx_proxy'] = {'configured': False, 'reason': str(e)}

            # Nginx已安装（或刚安装成功），配置反向代理
            if webserver_installed or (result.get('nginx_proxy') is None and not result['errors']):
                registry.emit_progress('panel_deploy_finalize', 'tool.log', 0, f'正在配置Nginx反向代理 {domain} → 127.0.0.1:{app_port}...')
                try:
                    from apps.sysai.tools.panel_website import panel_site_create, panel_site_proxy

                    # 创建站点
                    create_res = panel_site_create(
                        name=domain,
                        domains=[f'{domain}:80'],
                        remark=f'{app_name}反向代理站点',
                    )
                    if create_res.get('error'):
                        result['errors'].append(f'创建站点失败: {create_res["error"]}')
                        result['nginx_proxy'] = {'configured': False, 'reason': create_res['error']}
                    else:
                        site_id = create_res.get('site_id')

                        # 添加反向代理
                        proxy_pass = f'http://127.0.0.1:{app_port}'
                        proxy_res = panel_site_proxy(
                            site_id=site_id,
                            action='add',
                            proxy_name=f'{app_name}_proxy',
                            proxy_path='/',
                            proxy_pass=proxy_pass,
                            proxy_host=domain,
                            websocket=True,
                        )
                        if proxy_res.get('error'):
                            result['errors'].append(f'配置反向代理失败: {proxy_res["error"]}')
                            result['nginx_proxy'] = {'configured': False, 'reason': proxy_res['error']}
                        else:
                            result['nginx_proxy'] = {
                                'configured': True,
                                'site_id': site_id,
                                'domain': domain,
                                'proxy_pass': proxy_pass,
                            }
                            result['access_url'] = f'http://{domain}'
                except Exception as e:
                    result['errors'].append(f'Nginx反向代理配置异常: {str(e)}')
                    result['nginx_proxy'] = {'configured': False, 'reason': str(e)}

    # ── 2. 防火墙端口放通 ──
    if open_firewall:
        registry.emit_progress('panel_deploy_finalize', 'tool.log', 0, '正在放通防火墙端口...')
        try:
            is_windows = current_os == 'windows'
            ports_to_open = [str(app_port)]
            # 如果配置了Nginx反向代理，还需要放通80/443
            nginx_proxy = result.get('nginx_proxy') or {}
            if nginx_proxy.get('configured'):
                ports_to_open.extend(['80', '443'])

            opened_ports = []
            firewall_available = True
            if not is_windows:
                # 检查Linux防火墙是否可用
                from utils.server.linux import isFirewalld, isUfW
                if not isFirewalld() and not isUfW():
                    firewall_available = False
                    result['errors'].append('服务器未安装防火墙(firewalld/ufw)，端口放通已跳过。如需外网访问请手动放通端口或安装防火墙')

            if firewall_available:
                for p in ports_to_open:
                    if is_windows:
                        from utils.server.windows import AddFirewallRule
                        isok = AddFirewallRule(param={
                            'name': f'{app_name}_port_{p}',
                            'protocol': 'tcp',
                            'localport': p,
                            'handle': 'allow',
                            'direction': 'in',
                        })
                        opened_ports.append({'port': p, 'success': bool(isok)})
                    else:
                        from utils.server.linux import AddFirewallRule
                        isok = AddFirewallRule(param={
                            'protocol': 'tcp',
                            'localport': p,
                            'address': '',
                            'handle': 'accept',
                        })
                        opened_ports.append({'port': p, 'success': bool(isok)})
                        if not isok:
                            result['errors'].append(f'防火墙放通端口 {p} 失败，可能防火墙服务未运行，请手动放通')

            result['firewall'] = {'opened_ports': opened_ports, 'firewall_available': firewall_available}
        except Exception as e:
            result['errors'].append(f'防火墙端口放通异常: {str(e)}')
            result['firewall'] = {'opened_ports': [], 'error': str(e)}

    # ── 3. WAF防护设置 ──
    if waf_mode:
        registry.emit_progress('panel_deploy_finalize', 'tool.log', 0, f'正在配置WAF防护({waf_mode})...')
        site_id = (result.get('nginx_proxy') or {}).get('site_id')
        if not site_id:
            result['errors'].append('WAF防护需要先配置Nginx反向代理（enable_nginx_proxy=True + domain）')
            result['waf'] = {'configured': False, 'reason': '无Nginx站点'}
        else:
            try:
                from apps.sysai.tools.waf import waf_set_site_status
                waf_res = waf_set_site_status(site_id=site_id, status=waf_mode)
                if waf_res.get('error'):
                    result['errors'].append(f'WAF配置失败: {waf_res["error"]}')
                    result['waf'] = {'configured': False, 'reason': waf_res['error']}
                else:
                    result['waf'] = {
                        'configured': True,
                        'site_id': site_id,
                        'mode': waf_mode,
                        'message': waf_res.get('message', ''),
                    }
            except Exception as e:
                result['errors'].append(f'WAF配置异常: {str(e)}')
                result['waf'] = {'configured': False, 'reason': str(e)}

    # 生成访问地址
    if not result['access_url']:
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = '服务器IP'
        result['access_url'] = f'http://{ip}:{app_port}'

    registry.emit_progress('panel_deploy_finalize', 'tool.log', 0, f'部署收尾完成，访问地址: {result["access_url"]}')

    return result


# ─────────────────────────────────────────────────────────
# 故障诊断工具
# ─────────────────────────────────────────────────────────

# 安装故障常见错误模式及解决方案
_INSTALL_ERROR_PATTERNS = [
    {
        'patterns': ['No space left on device', '磁盘空间不足', 'ENOSPC'],
        'cause': '磁盘空间不足',
        'solution': '清理磁盘空间：删除无用Docker镜像(docker image prune)、清理日志、卸载不需要的软件',
    },
    {
        'patterns': ['Connection refused', 'Could not resolve', 'Network is unreachable', '超时', 'timeout'],
        'cause': '网络连接失败',
        'solution': '检查服务器网络连接和DNS配置，确保能访问外网。可尝试更换镜像源',
    },
    {
        'patterns': ['Permission denied', '权限不够', 'Operation not permitted'],
        'cause': '权限不足',
        'solution': '使用管理员权限执行，或检查文件/目录权限设置',
    },
    {
        'patterns': ['Address already in use', '端口已被占用', 'bind: address already in use'],
        'cause': '端口冲突',
        'solution': '使用 panel_find_free_port 查找可用端口，或停止占用该端口的服务',
    },
    {
        'patterns': ['docker: not found', 'Cannot connect to the Docker daemon'],
        'cause': 'Docker未安装或未运行',
        'solution': '先通过 panel_shop_install 安装Docker，或启动Docker服务',
    },
    {
        'patterns': ['【错误】', '异常信息如下', 'Error:', 'ERROR:', 'FATAL'],
        'cause': '安装过程出错',
        'solution': '查看日志中的具体错误信息，根据错误类型采取对应措施',
    },
]

# 服务故障常见错误模式及解决方案
_SERVICE_ERROR_PATTERNS = [
    {
        'patterns': ['Connection refused', 'ECONNREFUSED'],
        'cause': '服务未启动或端口未监听',
        'solution': '检查服务是否运行，使用 manage_service 启动服务',
    },
    {
        'patterns': ['Access denied', 'authentication failed', '密码错误', 'ER_ACCESS_DENIED_ERROR'],
        'cause': '认证失败/密码错误',
        'solution': '检查用户名密码是否正确，使用 panel_database_reset_pass 重置数据库密码',
    },
    {
        'patterns': ['Too many connections', 'max_connections'],
        'cause': '连接数超限',
        'solution': '优化应用连接池配置，或增加数据库最大连接数',
    },
    {
        'patterns': ['Out of memory', 'OOM', 'Cannot allocate memory'],
        'cause': '内存不足',
        'solution': '释放内存或增加swap，检查是否有内存泄漏',
    },
    {
        'patterns': ['No such file or directory', 'File not found'],
        'cause': '文件或目录不存在',
        'solution': '检查配置文件路径是否正确，确认文件是否被误删',
    },
    {
        'patterns': ['502 Bad Gateway'],
        'cause': '上游服务不可达',
        'solution': '检查反向代理指向的后端服务是否正常运行',
    },
    {
        'patterns': ['SSL', 'certificate', 'cert'],
        'cause': 'SSL证书问题',
        'solution': '检查证书是否过期，使用 panel_site_ssl 重新申请或更新证书',
    },
]


def _analyze_log_errors(log_text: str, error_patterns: list) -> list:
    """分析日志文本，匹配已知错误模式"""
    if not log_text:
        return []
    findings = []
    log_lower = log_text.lower()
    for pattern_group in error_patterns:
        matched = False
        for pattern in pattern_group['patterns']:
            if pattern.lower() in log_lower:
                matched = True
                break
        if matched:
            findings.append({
                'cause': pattern_group['cause'],
                'solution': pattern_group['solution'],
            })
    return findings


@register_tool(id='panel_diagnose_install', category='panel', name_cn='安装故障诊断', risk_level='low')
def panel_diagnose_install(task_id: int, extra_log: str = ''):
    """诊断应用商店安装任务失败的原因，分析安装日志并给出解决方案。

    当安装任务失败时调用此工具，自动读取安装日志、匹配已知错误模式、给出诊断结果和修复建议。
    无需手动读取日志文件，此工具一站式完成诊断。

    Args:
        task_id: 失败的安装任务ID，从panel_shop_install或panel_shop_task_status获取
        extra_log: 额外的日志内容（可选），如果已有部分日志可直接传入分析
    """
    result = {
        'task_id': task_id,
        'diagnosis': [],
        'log_summary': '',
        'recommendations': [],
    }

    # 获取任务状态和日志
    try:
        from apps.sysai.tools.panel_shop import panel_shop_task_status
        task_res = panel_shop_task_status(task_id=task_id)
        result['task_status'] = task_res.get('status', '未知')
        result['task_name'] = task_res.get('name', '')

        log_text = task_res.get('log_tail', '') or ''
        if extra_log:
            log_text = log_text + '\n' + extra_log
        result['log_summary'] = log_text[-1000:] if len(log_text) > 1000 else log_text
    except Exception as e:
        result['task_status'] = '查询失败'
        result['log_summary'] = extra_log or ''
        result['error'] = f'查询任务状态失败: {str(e)}'

    # 分析错误模式
    findings = _analyze_log_errors(result['log_summary'], _INSTALL_ERROR_PATTERNS)
    if findings:
        result['diagnosis'] = findings
        for f in findings:
            result['recommendations'].append(f"原因: {f['cause']} → 解决方案: {f['solution']}")
    else:
        # 未匹配到已知模式，提取日志中的错误行
        error_lines = []
        for line in result['log_summary'].split('\n'):
            line_lower = line.lower()
            if any(kw in line_lower for kw in ['error', '错误', 'fail', '失败', 'exception', '异常']):
                error_lines.append(line.strip())
        if error_lines:
            result['diagnosis'] = [{'cause': '未知错误', 'solution': '请根据下方error_lines分析具体原因'}]
            result['error_lines'] = error_lines[-10:]  # 最多10行
            result['recommendations'].append('日志中发现错误行，请根据error_lines内容分析。如无法判断，建议搜索错误信息或重新安装')
        else:
            result['diagnosis'] = [{'cause': '未发现明确错误', 'solution': '安装失败但日志中无明确错误信息，可能是初始化阶段异常或超时'}]
            result['recommendations'].append('建议：1) 检查服务器资源（磁盘/内存） 2) 重新尝试安装 3) 查看完整日志文件')

    return result


@register_tool(id='panel_diagnose_service', category='panel', name_cn='服务故障诊断', risk_level='low')
def panel_diagnose_service(
    service_name: str,
    container_name: str = '',
    port: int = 0,
    check_database: bool = False,
):
    """诊断服务运行异常的原因，综合检查服务状态、日志、端口、数据库连接等，给出诊断结果和修复建议。

    当部署验证失败或服务异常时调用此工具，自动执行多项检查并汇总诊断结果。

    Args:
        service_name: 服务名称，如 nginx、mysql、docker、wordpress 等
        container_name: Docker容器名称（如果是Docker部署的服务），如 my-wordpress、my-mysql
        port: 服务端口（如果知道），用于检查端口监听状态
        check_database: 是否检查数据库连接，默认False。适用于需要数据库的服务
    """
    result = {
        'service_name': service_name,
        'checks': {},
        'diagnosis': [],
        'recommendations': [],
    }

    # 1. 检查服务状态
    try:
        from apps.sysai.tools.service import get_service_status
        status_res = get_service_status(service_name=service_name)
        result['checks']['service_status'] = status_res
    except Exception as e:
        result['checks']['service_status'] = {'error': str(e)}

    # 2. 检查端口监听
    if port:
        port_listening = check_port_occupied(port)
        result['checks']['port'] = {'port': port, 'listening': port_listening}
        if not port_listening:
            result['diagnosis'].append({'cause': f'端口 {port} 无服务监听', 'solution': '服务可能未启动，尝试重启服务'})

    # 3. 检查Docker容器状态（如果是容器部署）
    if container_name:
        try:
            from apps.sysai.tools.docker import docker_list_containers
            containers_res = docker_list_containers()
            container_info = None
            for c in (containers_res if isinstance(containers_res, list) else containers_res.get('containers', [])):
                if container_name in c.get('name', ''):
                    container_info = c
                    break
            result['checks']['container'] = container_info or {'found': False}
            if container_info and container_info.get('status') != 'running':
                result['diagnosis'].append({
                    'cause': f'容器 {container_name} 状态为 {container_info.get("status", "未知")}',
                    'solution': '使用 docker_manage_container 重启容器，或查看容器日志排查原因',
                })
        except Exception as e:
            result['checks']['container'] = {'error': str(e)}

    # 4. 获取服务/容器日志
    log_text = ''
    if container_name:
        try:
            from apps.sysai.tools.docker import docker_container_logs
            logs_res = docker_container_logs(container=container_name, lines=50)
            log_text = logs_res.get('logs', '') if isinstance(logs_res, dict) else str(logs_res)
            result['checks']['container_logs'] = log_text[-500:] if len(log_text) > 500 else log_text
        except Exception as e:
            result['checks']['container_logs'] = {'error': str(e)}
    else:
        try:
            from apps.sysai.tools.service import get_service_logs
            logs_res = get_service_logs(service_name=service_name, lines=50)
            log_text = logs_res.get('output', '') if isinstance(logs_res, dict) else str(logs_res)
            result['checks']['service_logs'] = log_text[-500:] if len(log_text) > 500 else log_text
        except Exception as e:
            result['checks']['service_logs'] = {'error': str(e)}

    # 5. 检查数据库连接
    if check_database:
        try:
            from apps.sysai.tools.panel_database import panel_database_list
            db_res = panel_database_list()
            result['checks']['databases'] = db_res
        except Exception as e:
            result['checks']['databases'] = {'error': str(e)}

    # 6. 分析日志错误模式
    if log_text:
        findings = _analyze_log_errors(log_text, _SERVICE_ERROR_PATTERNS)
        if findings:
            result['diagnosis'].extend(findings)

    # 7. 汇总建议
    if not result['diagnosis']:
        result['diagnosis'].append({'cause': '未发现明确故障', 'solution': '服务状态正常，问题可能出在应用层配置'})
        result['recommendations'].append('建议检查应用配置文件、环境变量、依赖服务等')
    else:
        for d in result['diagnosis']:
            result['recommendations'].append(f"原因: {d['cause']} → 解决方案: {d['solution']}")

    return result
