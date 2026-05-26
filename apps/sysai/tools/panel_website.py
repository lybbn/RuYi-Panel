import json
from apps.sysai.tools.base import register_tool
from apps.system.models import Sites, SiteDomains
from apps.sysshop.models import RySoftShop
from utils.ruyiclass.webClass import WebClient
from utils.common import current_os


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
