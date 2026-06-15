import os
import platform
from apps.sysai.tools.base import register_tool
from apps.sysai.tools.common import run_cmd
from utils.server.system import system
from utils.ruyiclass.webClass import WebClient


def _parse_nginx_config(content: str) -> dict:
    server_names = []
    listen_ports = []
    root_dir = ''

    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('server_name'):
            names = stripped.replace('server_name', '').replace(';', '').strip().split()
            server_names.extend(names)
        elif stripped.startswith('listen'):
            port = stripped.replace('listen', '').replace(';', '').strip().split()[0] if stripped.replace('listen', '').replace(';', '').strip() else '80'
            listen_ports.append(port)
        elif stripped.startswith('root'):
            root_dir = stripped.replace('root', '').replace(';', '').strip()

    return {
        'server_names': server_names,
        'listen_ports': listen_ports,
        'root': root_dir,
    }


@register_tool(id='list_websites', category='website', name_cn='网站列表', risk_level='low')
def list_websites():
    """列出服务器上配置的网站，通过扫描Nginx/Apache配置文件获取。当用户需要查看服务器上有哪些网站时使用。"""
    websites = []
    is_windows = platform.system().lower() == 'windows'

    if is_windows:
        nginx_sites = [
            os.path.expandvars(r'%ProgramFiles%\nginx\conf\conf.d'),
            os.path.expandvars(r'%ProgramFiles%\nginx\conf\sites-enabled'),
            r'C:\nginx\conf\conf.d',
            r'C:\nginx\conf\sites-enabled',
        ]
    else:
        nginx_sites = ['/etc/nginx/sites-enabled', '/etc/nginx/conf.d']

    for sites_dir in nginx_sites:
        if os.path.exists(sites_dir):
            try:
                for f in os.listdir(sites_dir):
                    if f.endswith('.conf'):
                        filepath = os.path.join(sites_dir, f)
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
                                content = fh.read()
                            config = _parse_nginx_config(content)
                            websites.append({
                                'name': f.replace('.conf', ''),
                                'config_file': filepath,
                                'server_names': config['server_names'],
                                'listen_ports': config['listen_ports'],
                                'root': config['root'],
                                'web_server': 'nginx',
                            })
                        except Exception:
                            continue
            except PermissionError:
                continue

    if not is_windows:
        apache_sites = ['/etc/apache2/sites-enabled', '/etc/httpd/conf.d']
        for sites_dir in apache_sites:
            if os.path.exists(sites_dir):
                for f in os.listdir(sites_dir):
                    if f.endswith('.conf'):
                        filepath = os.path.join(sites_dir, f)
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
                                content = fh.read()
                            server_names = []
                            for line in content.split('\n'):
                                stripped = line.strip()
                                if stripped.startswith('ServerName'):
                                    server_names.append(stripped.replace('ServerName', '').strip())

                            websites.append({
                                'name': f.replace('.conf', ''),
                                'config_file': filepath,
                                'server_names': server_names,
                                'web_server': 'apache',
                            })
                        except Exception:
                            continue

    if is_windows and not websites:
        iis_result = run_cmd('%systemroot%\\system32\\inetsrv\\appcmd list sites 2>nul')
        if 'output' in iis_result and iis_result['output'].strip():
            websites.append({
                'name': 'IIS Sites',
                'web_server': 'iis',
                'note': '检测到 IIS 站点，使用 appcmd 可查看详情',
            })

    return {
        'websites': websites,
        'total': len(websites),
    }


@register_tool(id='get_website_config', category='website', name_cn='网站配置', risk_level='low')
def get_website_config(config_path: str):
    """读取网站配置文件内容。当用户需要查看或排查网站配置问题时使用。

    Args:
        config_path: 配置文件路径，如 /etc/nginx/sites-enabled/default
    """
    if not os.path.exists(config_path):
        return {'error': f'配置文件不存在: {config_path}'}

    try:
        with open(config_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        return {
            'path': config_path,
            'content': content[:20000],
            'size_bytes': os.path.getsize(config_path),
            'truncated': len(content) > 20000,
        }
    except PermissionError:
        return {'error': f'权限不足，无法读取: {config_path}'}
    except Exception as e:
        return {'error': str(e)}


@register_tool(id='check_website_status', category='website', name_cn='网站状态', risk_level='low')
def check_website_status(domain: str, port: int = 80, path: str = '/'):
    """检查网站是否可以正常访问，返回HTTP状态码和响应时间。当用户需要验证网站是否正常运行时使用。

    Args:
        domain: 网站域名或IP地址
        port: 端口号，默认80
        path: 检查路径，默认 /
    """
    url = f'http://{domain}:{port}{path}'

    result = run_cmd(
        f'curl -o /dev/null -s -w "%{{http_code}}|%{{time_total}}|%{{size_download}}|%{{redirect_url}}" '
        f'--max-time 10 {url} 2>&1'
    )

    if 'error' in result:
        https_url = f'https://{domain}:{port}{path}'
        result = run_cmd(
            f'curl -o /dev/null -s -k -w "%{{http_code}}|%{{time_total}}|%{{size_download}}|%{{redirect_url}}" '
            f'--max-time 10 {https_url} 2>&1'
        )

    if 'error' in result:
        return {'error': f'无法连接到 {url}', 'domain': domain}

    parts = result.get('output', '').split('|')
    http_code = parts[0] if len(parts) > 0 else '000'
    time_total = parts[1] if len(parts) > 1 else '0'
    size_download = parts[2] if len(parts) > 2 else '0'
    redirect_url = parts[3] if len(parts) > 3 else ''

    return {
        'domain': domain,
        'url': url,
        'http_code': http_code,
        'response_time_s': time_total,
        'response_size_bytes': size_download,
        'redirect_url': redirect_url,
        'is_accessible': http_code.startswith('2') or http_code.startswith('3'),
    }


@register_tool(id='get_nginx_status', category='website', name_cn='Nginx状态', risk_level='low')
def get_nginx_status():
    """获取Nginx服务状态和配置信息，包括版本、运行状态、配置文件路径等。"""
    is_windows = platform.system().lower() == 'windows'

    svc_status = system.GetServiceStatus('nginx')
    is_active = svc_status.get('is_active', False)

    version_result = run_cmd('nginx -v 2>&1')
    version = version_result.get('output', '').replace('nginx version: ', '').strip()

    test_result = run_cmd('nginx -t 2>&1')

    return {
        'is_active': is_active,
        'version': version,
        'config_test': test_result.get('output', ''),
        'service_status': svc_status,
    }


@register_tool(id='reload_nginx', category='website', name_cn='重载Nginx', risk_level='high')
def reload_nginx():
    """重载Nginx配置，使配置变更生效而不中断服务。⚠️此操作会影响所有网站，请确认配置正确后再执行。"""
    try:
        is_ok, msg = WebClient.reload_service(webserver='nginx')
        if is_ok:
            return {'success': True, 'message': 'Nginx 配置重载成功'}
        return {'error': str(msg)}
    except Exception as e:
        return {'error': str(e)}


@register_tool(id='restart_nginx', category='website', name_cn='重启Nginx', risk_level='high')
def restart_nginx():
    """重启Nginx服务。⚠️此操作会短暂中断所有网站服务，请谨慎执行。"""
    try:
        is_ok, msg = WebClient.restart_service(webserver='nginx')
        if is_ok:
            return {'success': True, 'message': 'Nginx 重启成功'}
        return {'error': str(msg)}
    except Exception as e:
        return {'error': str(e)}