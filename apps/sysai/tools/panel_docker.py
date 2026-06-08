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

    返回结果中包含每个应用的formFields（安装参数表单），AI应根据formFields确定安装时需要提供哪些参数。
    特别注意selectapps类型的字段，表示该应用依赖其他服务（如WordPress依赖MySQL），需要先安装依赖服务。

    常见formFields字段说明：
    - type=number: 端口号，需确保端口未被占用
    - type=password: 密码，如未提供可自动生成
    - type=selectapps: 依赖服务选择，child.envkey为依赖服务的连接参数envkey
    - outport=true: 对外开放端口，需检查端口可用性

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

            form_fields = item.get('formFields', [])
            simplified_fields = []
            has_dependency = False
            for field in form_fields:
                field_info = {
                    'label': field.get('label', ''),
                    'envkey': field.get('envkey', ''),
                    'type': field.get('type', ''),
                    'default': field.get('default', ''),
                    'required': field.get('required', False),
                    'outport': field.get('outport', False),
                }
                if field.get('type') == 'selectapps':
                    has_dependency = True
                    field_info['values'] = field.get('values', [])
                    field_info['child'] = field.get('child', {})
                    field_info['tips'] = field.get('tips', '')
                simplified_fields.append(field_info)

            result.append({
                'appid': item.get('appid'),
                'appname': appname,
                'title': item.get('title', appname),
                'desc': item.get('desc', ''),
                'type': item.get('type', ''),
                'typename': item.get('typename', ''),
                'version': item.get('version', ''),
                'installed': installed_count > 0,
                'installed_count': installed_count,
                'has_dependency': has_dependency,
                'form_fields': simplified_fields,
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

    安装流程：
    1. 先用panel_docker_square_catalog查询该应用是否存在，并了解其formFields参数要求
    2. 如果应用有依赖服务（has_dependency=true，form_fields中有type=selectapps的字段），需先安装依赖服务
    3. 依赖服务的child.envkey值格式为"{gateway}:{port}"，如"172.18.0.1:13306"
    4. 调用此工具安装应用

    当依赖服务未安装时，此工具会返回need_dependency=true和install_options，此时必须询问用户选择安装方式：
    - 选项1：从容器广场一键安装（推荐，自动配置网络和依赖关系）
    - 选项2：使用Docker原生方式安装（手动配置，灵活度更高）
    不要自行决定安装方式，必须让用户选择。

    如果广场中不存在该应用，应告知用户该应用不在容器广场中，询问是否使用docker原生方式部署。

    Args:
        appname: 广场应用名称，如 wordpress、nextcloud、gitlab、mysql 等（必须是广场目录中存在的appname）
        name: 安装后的实例名称，需唯一标识，如 my-wordpress、my-mysql
        params: 应用参数字典，不同应用参数不同。参数envkey必须与formFields中的envkey一致。
            常见参数：
            - 端口类：{"wordpress_port": 18080, "mysql_port": 13306}
            - 密码类：{"mysql_password": "yourpassword", "mysql_root_password": "rootpwd"}
            - 依赖服务类：{"wordpress_db_host": "172.18.0.1:13306"}（selectapps的child.envkey）
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
            available = [a.get('appname', '') for a in apps_list if a.get('show', 1) != 0]
            return {
                'error': f'容器广场中不存在应用: {appname}',
                'suggestion': '该应用不在容器广场中，请询问用户是否使用Docker原生方式部署（docker run / docker compose）',
                'available_apps': available[:30],
            }

        appid = app_info.get('appid', '')
        version = app_info.get('version', 'latest')
        app_type = app_info.get('type', '')

        form_fields = app_info.get('formFields', [])
        default_params = {}
        selectapps_fields = []
        for field in form_fields:
            envkey = field.get('envkey', '')
            default_val = field.get('default', '')
            if envkey and default_val:
                default_params[envkey] = default_val
            if field.get('type') == 'selectapps':
                selectapps_fields.append(field)

        if selectapps_fields:
            from utils.ruyiclass.dockerClass import DockerClient
            dc = DockerClient()
            docker_ruyi_network_gateway = dc.get_network_gateway("ruyi-network")
            docker_ruyi_network_gateway = docker_ruyi_network_gateway or "127.0.0.1"

            for sa_field in selectapps_fields:
                sa_values = sa_field.get('values', [])
                sa_child = sa_field.get('child', {})
                child_envkey = sa_child.get('envkey', '')
                if not child_envkey:
                    continue

                sa_appname = default_params.get(sa_field.get('envkey', ''), '')
                if not sa_appname:
                    if sa_values:
                        sa_appname = sa_values[0].get('value', '')

                child_value = ''
                if params and child_envkey in params:
                    child_value = params[child_envkey]

                if not child_value:
                    from apps.system.models import RySoftShop
                    local_service = RySoftShop.objects.filter(name=sa_appname, installed=True).first()
                    if local_service:
                        from utils.common import current_os as cur_os
                        from apps.system.management.commands.panelcli import Ry_Get_Soft_Port
                        lport = Ry_Get_Soft_Port(name=sa_appname, is_windows=(cur_os == 'windows'))
                        if sa_appname == 'mysql':
                            child_value = f"{docker_ruyi_network_gateway}:{lport}"
                        else:
                            child_value = f"{docker_ruyi_network_gateway}:{lport}"
                    else:
                        dk_service = RyDockerApps.objects.filter(appname=sa_appname).first()
                        if dk_service:
                            dk_params = {}
                            if dk_service.params:
                                try:
                                    dk_params = json.loads(dk_service.params) if isinstance(dk_service.params, str) else dk_service.params
                                except Exception:
                                    dk_params = {}
                            dk_port = ''
                            for key, value in dk_params.items():
                                if '_port' in key.lower():
                                    dk_port = str(value)
                                    break
                            if dk_port:
                                if sa_appname == 'mysql':
                                    child_value = f"{docker_ruyi_network_gateway}:{dk_port}"
                                else:
                                    child_value = f"{docker_ruyi_network_gateway}:{dk_port}"
                        else:
                            dep_in_square = False
                            for a in apps_list:
                                if a.get('appname') == sa_appname and a.get('show', 1) != 0:
                                    dep_in_square = True
                                    break
                            options = []
                            if dep_in_square:
                                options.append(f'1. 从容器广场一键安装 {sa_appname}（推荐，自动配置网络和依赖）')
                            options.append(f'{"2" if dep_in_square else "1"}. 使用Docker原生方式安装 {sa_appname}（手动配置，灵活度更高）')
                            return {
                                'need_dependency': True,
                                'error': f'应用 {appname} 依赖 {sa_appname} 服务，但当前未安装。请询问用户选择安装方式：',
                                'dependency_appname': sa_appname,
                                'child_envkey': child_envkey,
                                'dependency_in_square': dep_in_square,
                                'install_options': options,
                                'suggestion': f'请询问用户选择安装方式后再继续。如果选择容器广场安装，使用 panel_docker_square_install(appname="{sa_appname}", name="自定义实例名")；如果选择Docker原生安装，使用 docker_run 或 docker_compose 工具。',
                            }

                default_params[child_envkey] = child_value

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
        DB_PIP_MAP = {
            'pgsql': 'psycopg2-binary',
            'mongodb': 'pymongo',
        }
        if appname in DB_PIP_MAP:
            from utils.common import pip_install_package
            pip_install_package(DB_PIP_MAP[appname])

        return {
            'success': True,
            'message': f'{appname}({name}) 安装任务已提交，{msg}',
            'appname': appname,
            'name': name,
            'params': default_params,
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
