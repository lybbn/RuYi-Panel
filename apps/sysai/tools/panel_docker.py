import json
from apps.sysai.tools.base import register_tool
from apps.sysdocker.models import RyDockerApps
from utils.ruyiclass.dockerInclude.ry_dk_square import main as dksquare


def _get_square():
    return dksquare()


def _get_installed_apps():
    apps = RyDockerApps.objects.all().order_by('-create_at')
    sq = _get_square()
    result = []
    for m in apps:
        appname = m.appname or ''
        name = m.name or ''
        appid = m.appid or 0
        icon = ''
        status = m.status
        if status in ('install', 'install_failed'):
            status = sq.sync_app_install_status(m)

        params = {}
        if m.params:
            try:
                params = json.loads(m.params) if isinstance(m.params, str) else m.params
            except Exception:
                params = {}

        ports = []
        for key, value in params.items():
            if '_port' in key.lower():
                ports.append(str(value))

        result.append({
            'id': m.id,
            'name': name,
            'appid': appid,
            'appname': appname,
            'version': m.version,
            'status': status,
            'allowport': m.allowport,
            'ports': ports,
            'create_at': str(m.create_at),
        })
    return result


@register_tool(id='panel_docker_square_list', category='panel', name_cn='Docker广场应用列表', risk_level='low')
def panel_docker_square_list(search: str = ''):
    """获取如意面板Docker广场中已安装的应用列表。Docker广场是面板内置的应用市场，提供WordPress、Nextcloud、GitLab、Jenkins等常用Docker应用的一键部署。当用户需要查看已部署的Docker应用、或询问某个Docker应用状态时，必须优先使用此工具。

    Args:
        search: 搜索关键词，按应用名称搜索
    """
    try:
        apps = _get_installed_apps()
        if search:
            apps = [
                item for item in apps
                if search.lower() in item.get('name', '').lower()
                or search.lower() in item.get('appname', '').lower()
            ]

        status_count = {'running': 0, 'exited': 0, 'paused': 0, 'install': 0, 'install_failed': 0}
        for item in apps:
            s = item.get('status', '')
            if s in status_count:
                status_count[s] += 1

        return {
            'installed_apps': apps,
            'total': len(apps),
            'status_summary': status_count,
        }
    except Exception as e:
        return {'error': f'获取Docker广场应用列表失败: {str(e)}'}


@register_tool(id='panel_docker_square_catalog', category='panel', name_cn='Docker广场应用目录', risk_level='low')
def panel_docker_square_catalog(search: str = '', app_type: str = ''):
    """获取如意面板Docker广场的应用目录（可安装的应用列表）。当用户需要了解广场中有哪些应用可以安装时使用此工具。

    Args:
        search: 搜索关键词，按应用名称或描述搜索
        app_type: 应用类型筛选，如 website、database、devtool、media 等
    """
    try:
        sq = _get_square()
        softlist = sq.get_apps_list()

        installed_names = set(
            RyDockerApps.objects.values_list('appname', flat=True)
        )

        if search:
            softlist = [
                item for item in softlist
                if search.lower() in item.get('appname', '').lower()
                or search.lower() in item.get('desc', '').lower()
                or search.lower() in item.get('title', '').lower()
            ]

        if app_type:
            softlist = [
                item for item in softlist
                if app_type.lower() in item.get('type', '').lower()
            ]

        softlist = [item for item in softlist if item.get('show', 1) != 0]

        result = []
        for item in softlist:
            appname = item.get('appname', '')
            installed_count = RyDockerApps.objects.filter(appname=appname).count()
            result.append({
                'appid': item.get('appid'),
                'appname': appname,
                'title': item.get('title', appname),
                'desc': item.get('desc', ''),
                'type': item.get('type', ''),
                'icon': item.get('icon', ''),
                'version': item.get('version', ''),
                'installed': installed_count > 0,
                'installed_count': installed_count,
            })

        return {
            'catalog': result,
            'total': len(result),
        }
    except Exception as e:
        return {'error': f'获取Docker广场目录失败: {str(e)}'}


@register_tool(id='panel_docker_square_install', category='panel', name_cn='安装Docker广场应用', risk_level='high')
def panel_docker_square_install(appname: str, name: str, params: dict = None):
    """从如意面板Docker广场一键安装应用。⚠️此为高危操作，会创建Docker容器并可能开放端口。

    安装前应先用panel_docker_square_catalog查询该应用是否存在，并了解其参数要求。

    Args:
        appname: 广场应用名称，如 wordpress、nextcloud、gitlab 等（必须是广场目录中存在的appname）
        name: 安装后的实例名称，需唯一标识，如 my-wordpress、my-nextcloud
        params: 应用参数字典，不同应用参数不同，通常包含端口映射、密码等配置。常见参数如：{"PORT": "8080", "MYSQL_ROOT_PASSWORD": "123456"}
    """
    try:
        if not appname or not name:
            return {'error': 'appname和name不能为空'}

        if RyDockerApps.objects.filter(name=name).exists():
            return {'error': f'已存在同名应用实例: {name}，请更换名称'}

        sq = _get_square()
        apps_list = sq.get_apps_list()
        app_info = None
        for a in apps_list:
            if a.get('appname') == appname:
                app_info = a
                break

        if not app_info:
            available = ', '.join([a.get('appname', '') for a in apps_list[:20]])
            return {'error': f'广场中不存在应用: {appname}，部分可用应用: {available}'}

        appid = app_info.get('appid', '')
        version = app_info.get('version', 'latest')
        app_type = app_info.get('type', '')

        form_fields = app_info.get('formFields', [])
        default_params = {}
        for field in form_fields:
            envkey = field.get('envkey', '')
            default_val = field.get('default', '')
            if envkey and default_val:
                default_params[envkey] = default_val

        if params:
            default_params.update(params)

        cont = {
            'appid': appid,
            'appname': appname,
            'name': name,
            'version': version,
            'type': app_type,
            'params': json.dumps(default_params) if isinstance(default_params, dict) else default_params,
            'allowport': False,
            'advanced': False,
        }

        isok, msg = sq.generate_app(cont=cont)
        if not isok:
            app_path = sq.get_dkapp_path(cont={'appname': appname, 'name': name})
            from utils.common import DeleteDir
            DeleteDir(app_path)
            return {'error': f'安装失败: {msg}'}

        RyDockerApps.objects.create(
            appid=appid,
            appname=appname,
            type=app_type,
            name=name,
            version=version,
            params=json.dumps(default_params) if isinstance(default_params, dict) else default_params,
            status='install',
            allowport=False,
            advanced=False,
        )

        return {
            'success': True,
            'message': f'{appname}({name}) 安装任务已提交，{msg}',
            'appname': appname,
            'name': name,
        }
    except Exception as e:
        return {'error': f'安装Docker广场应用失败: {str(e)}'}


@register_tool(id='panel_docker_square_manage', category='panel', name_cn='管理Docker广场应用', risk_level='high')
def panel_docker_square_manage(app_id: int, action: str):
    """管理如意面板Docker广场中已安装的应用，支持启动、停止、重启、删除等操作。⚠️此为高危操作，请确认后再执行。

    Args:
        app_id: 已安装应用的ID（从panel_docker_square_list返回的id获取）
        action: 操作类型，start(启动)、stop(停止)、restart(重启)、remove(删除并清除数据)、rebuild(重建)
    """
    try:
        valid_actions = ['start', 'stop', 'restart', 'remove', 'rebuild']
        if action not in valid_actions:
            return {'error': f'不支持的操作: {action}，可用: {", ".join(valid_actions)}'}

        app = RyDockerApps.objects.filter(id=app_id).first()
        if not app:
            return {'error': f'应用ID {app_id} 不存在，请先用panel_docker_square_list查询'}

        sq = _get_square()
        appname = app.appname
        name = app.name
        app_path = sq.get_dkapp_path(cont={'appname': appname, 'name': name})
        compose_conf_path = f'{app_path}/docker-compose.yml'

        isok, msg = sq.set_status(compose_conf_path, action)
        if not isok:
            return {'error': f'{action}操作失败: {msg}'}

        if action == 'remove':
            app.delete()
            from utils.common import DeleteDir
            DeleteDir(app_path)
        elif action in ('restart', 'rebuild', 'start'):
            app.status = 'running'
            app.save()
        elif action == 'stop':
            app.status = 'exited'
            app.save()

        return {
            'success': True,
            'message': f'{appname}({name}) {action} 操作成功',
            'appname': appname,
            'name': name,
        }
    except Exception as e:
        return {'error': f'操作失败: {str(e)}'}
