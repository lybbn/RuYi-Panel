import json
import os
import random
import re
import string
from apps.sysai.tools.base import register_tool
from apps.sysdocker.models import RyDockerApps
from utils.ruyiclass.dockerInclude.ry_dk_square import main as dksquare


# 弱密码黑名单，这些值会被自动替换为强密码
_WEAK_PASSWORDS = {'ry', 'mysql', '123456', 'password', 'admin', 'root', 'test', '12345678',
                   '123456789', '1234567890', 'qwerty', 'abc123', '111111', '000000', 'pass',
                   'passwd', '123123', 'admin123', 'root123', 'test123', '1234', '12345',
                   'mongodb', 'postgres', 'redis', 'ollama', 'hermes', 'allinssl', 'rabbitmq'}

# 不稳定的服务地址模式（Docker网关IP），需要替换为 host.docker.internal
_UNSTABLE_HOST_PATTERNS = re.compile(r'^172\.\d+\.\d+\.1(?::\d+)?$')

# 依赖服务名称映射：容器广场appname → 应用商店name的别名映射
# 用于解决容器广场和应用商店中同一服务名称不一致的问题
# key: 容器广场中的appname, value: 应用商店中可能的name列表（按优先级排序）
_DEPENDENCY_NAME_MAP = {
    'mysql': ['mysql'],
    'postgresql': ['pgsql', 'postgresql', 'postgres'],
    'mongodb': ['mongodb', 'mongo'],
    'redis': ['redis'],
    'mariadb': ['mariadb', 'mysql'],
}

# 反向映射：应用商店name → 容器广场appname
_SHOP_TO_SQUARE_MAP = {}
for _sq_name, _shop_names in _DEPENDENCY_NAME_MAP.items():
    for _shop_name in _shop_names:
        if _shop_name not in _SHOP_TO_SQUARE_MAP:
            _SHOP_TO_SQUARE_MAP[_shop_name] = _sq_name


def _find_installed_dependency(sa_appname):
    """查找依赖服务是否已安装。

    按优先级查找：1.容器广场已安装 → 2.应用商店已安装
    返回: (found, source, service_info)
        found: 是否找到
        source: 'square' 或 'shop'
        service_info: 服务信息dict（包含port等），未找到时为None
    """
    # 获取可能的别名列表
    shop_names = _DEPENDENCY_NAME_MAP.get(sa_appname, [sa_appname])

    # 1. 优先查找容器广场中已安装的（精确匹配appname）
    dk_app = RyDockerApps.objects.filter(appname=sa_appname).first()
    if dk_app:
        # 同步最新状态
        try:
            sq_tmp = _get_square()
            sq_tmp.sync_app_install_status(dk_app)
        except Exception:
            pass
        # 只有running状态才算已安装可用，install/install_failed状态不算
        if dk_app.status == 'running':
            dk_params = {}
            if dk_app.params:
                try:
                    dk_params = json.loads(dk_app.params) if isinstance(dk_app.params, str) else dk_app.params
                except Exception:
                    dk_params = {}
            dk_port = ''
            for key, value in dk_params.items():
                if '_port' in key.lower():
                    dk_port = str(value)
                    break
            return True, 'square', {
                'name': dk_app.name,
                'appname': dk_app.appname,
                'port': dk_port,
                'status': dk_app.status,
                'host_value': f"host.docker.internal:{dk_port}" if dk_port else '',
            }
        elif dk_app.status == 'install':
            # 依赖服务正在安装中，返回特殊状态让调用方知道
            dk_params = {}
            if dk_app.params:
                try:
                    dk_params = json.loads(dk_app.params) if isinstance(dk_app.params, str) else dk_app.params
                except Exception:
                    dk_params = {}
            dk_port = ''
            for key, value in dk_params.items():
                if '_port' in key.lower():
                    dk_port = str(value)
                    break
            return True, 'square_installing', {
                'name': dk_app.name,
                'appname': dk_app.appname,
                'port': dk_port,
                'status': dk_app.status,
                'host_value': f"host.docker.internal:{dk_port}" if dk_port else '',
            }
        # install_failed 或其他异常状态，视为未安装

    # 2. 查找应用商店中已安装的（模糊匹配name）
    from apps.sysshop.models import RySoftShop
    for shop_name in shop_names:
        shop_app = RySoftShop.objects.filter(name=shop_name, installed=True).first()
        if shop_app:
            from utils.common import current_os as cur_os
            from apps.system.management.commands.panelcli import Ry_Get_Soft_Port
            lport = Ry_Get_Soft_Port(name=shop_name, is_windows=(cur_os == 'windows'))
            return True, 'shop', {
                'name': shop_app.name,
                'port': lport,
                'status': shop_app.status,
                'host_value': f"host.docker.internal:{lport}" if lport else '',
            }

    return False, None, None


def _generate_strong_password(length=16):
    """生成强密码：大小写字母+数字+特殊字符"""
    if length < 12:
        length = 12
    chars = string.ascii_letters + string.digits + '!@#$%&*'
    while True:
        pwd = ''.join(random.choices(chars, k=length))
        # 确保包含大写、小写、数字、特殊字符各至少1个
        if (any(c in string.ascii_uppercase for c in pwd) and
            any(c in string.ascii_lowercase for c in pwd) and
            any(c in string.digits for c in pwd) and
            any(c in '!@#$%&*' for c in pwd)):
            return pwd


def _get_square():
    return dksquare()


def _auto_init_mysql_database(params, selectapps_fields, app_instance_name):
    """当应用依赖MySQL时，自动在MySQL容器中创建数据库和用户。

    仅在以下条件同时满足时执行：
    1. selectapps_fields中有type=selectapps且依赖mysql的应用
    2. params中包含mysql_database和mysql_user参数
    3. MySQL容器正在运行
    """
    import time
    import logging
    logger = logging.getLogger(__name__)

    from apps.sysai.tools.base import AIToolRegistry
    registry = AIToolRegistry()

    # 检查是否依赖MySQL
    has_mysql_dep = False
    for sa_field in selectapps_fields:
        sa_values = sa_field.get('values', [])
        for v in sa_values:
            if v.get('value', '') == 'mysql':
                has_mysql_dep = True
                break
        sa_appname = sa_field.get('default', '')
        if sa_appname == 'mysql':
            has_mysql_dep = True
        if has_mysql_dep:
            break

    if not has_mysql_dep:
        return None

    mysql_database = params.get('mysql_database', '')
    mysql_user = params.get('mysql_user', '')
    mysql_password = params.get('mysql_password', '')

    if not mysql_database or not mysql_user:
        return None

    registry.emit_progress('panel_docker_square_install', 'tool.log', 0, '检测到MySQL依赖，正在查找MySQL容器...')

    # 查找MySQL容器
    try:
        from apps.sysdocker.models import RyDockerApps as DockerApps
        # 不限status，因为MySQL可能刚安装状态还是install
        mysql_apps = DockerApps.objects.filter(appname='mysql')
        if not mysql_apps:
            return {'status': 'skipped', 'reason': '未找到MySQL应用，请手动创建数据库'}

        mysql_app = mysql_apps.first()
        mysql_name = mysql_app.name

        # 获取MySQL root密码
        mysql_params = {}
        if mysql_app.params:
            try:
                mysql_params = json.loads(mysql_app.params) if isinstance(mysql_app.params, str) else mysql_app.params
            except Exception:
                mysql_params = {}

        mysql_root_password = mysql_params.get('mysql_root_password', '')
        if not mysql_root_password:
            return {'status': 'skipped', 'reason': '未找到MySQL root密码，请手动创建数据库'}

        # 等待MySQL就绪（最多等120秒，给容器更多启动时间）
        from utils.common import RunCommand
        mysql_container = f"{mysql_name}-{mysql_name}-1"
        registry.emit_progress('panel_docker_square_install', 'tool.log', 0, f'找到MySQL容器: {mysql_container}，等待MySQL就绪...')
        ready = False
        for attempt in range(24):
            out, err, rc = RunCommand(
                f'docker exec {mysql_container} mysql -uroot -p"{mysql_root_password}" -e "SELECT 1" 2>/dev/null',
                timeout=10, returncode=True
            )
            if rc == 0:
                ready = True
                break
            elapsed = (attempt + 1) * 5
            registry.emit_progress('panel_docker_square_install', 'tool.log', 0, f'等待MySQL就绪... ({elapsed}s/120s)')
            time.sleep(5)

        if not ready:
            return {'status': 'skipped', 'reason': 'MySQL容器未就绪（已等待120秒），请手动创建数据库或使用 panel_database_create 工具'}

        registry.emit_progress('panel_docker_square_install', 'tool.log', 0, f'MySQL已就绪，正在创建数据库 {mysql_database}...')

        # 执行创建数据库和用户
        # 注意：使用 docker exec -i 通过 stdin 传入 SQL，避免 shell 解析反引号等特殊字符
        # 使用 heredoc 方式传入 SQL，避免引号嵌套问题
        sql = (
            f"CREATE DATABASE IF NOT EXISTS `{mysql_database}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; "
            f"CREATE USER IF NOT EXISTS '{mysql_user}'@'%' IDENTIFIED WITH mysql_native_password BY '{mysql_password}'; "
            f"GRANT ALL PRIVILEGES ON `{mysql_database}`.* TO '{mysql_user}'@'%'; "
            f"FLUSH PRIVILEGES;"
        )
        out, err, rc = RunCommand(
            f'docker exec -i {mysql_container} mysql -uroot -p"{mysql_root_password}" <<\'EOSQL\'\n{sql}\nEOSQL',
            timeout=15, returncode=True
        )

        if rc == 0:
            registry.emit_progress('panel_docker_square_install', 'tool.log', 0, f'数据库 {mysql_database} 创建成功')
            return {
                'status': 'success',
                'database': mysql_database,
                'user': mysql_user,
                'message': f'已在MySQL容器({mysql_container})中自动创建数据库 {mysql_database} 和用户 {mysql_user}'
            }
        else:
            # MySQL命令行密码警告会导致returncode!=0，但SQL可能已执行成功
            # 验证数据库是否已存在
            registry.emit_progress('panel_docker_square_install', 'tool.log', 0, '验证数据库是否创建成功...')
            out2, err2, rc2 = RunCommand(
                f'docker exec {mysql_container} mysql -uroot -p"{mysql_root_password}" -e "SHOW DATABASES" 2>/dev/null',
                timeout=10, returncode=True
            )
            if mysql_database in (out2 or ''):
                return {
                    'status': 'success',
                    'database': mysql_database,
                    'user': mysql_user,
                    'message': f'已在MySQL容器({mysql_container})中自动创建数据库 {mysql_database} 和用户 {mysql_user}'
                }
            return {'status': 'failed', 'reason': f'数据库创建失败: {err}', 'hint': '请手动在MySQL中创建数据库和用户'}

    except Exception as e:
        logger.warning(f'自动初始化MySQL数据库异常: {e}')
        return {'status': 'error', 'reason': str(e), 'hint': '请手动在MySQL中创建数据库和用户'}


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
    3. 依赖服务的child.envkey值会由系统自动填充为"host.docker.internal:{port}"格式，无需手动指定
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
            - 版本类：{"mysql_version": "8.0"}（选择字段，影响安装的镜像版本）
            - 数据库类：{"mysql_database": "ry", "mysql_user": "ry", "mysql_password": "xxx"}
            ⚠️ 重要：依赖服务相关参数的处理规则：
            1. panel_service_type字段：必须传入依赖服务的【实例名称】（如"my-mysql"），而不是应用名称（如"mysql"）
               - ❌ 错误：{"panel_service_type": "mysql"}
               - ✅ 正确：{"panel_service_type": "my-mysql"}
            2. 依赖服务连接地址（如wordpress_db_host）不要手动指定！系统会自动填充为host.docker.internal:端口格式
            3. 不要传入空字符串如 {"wordpress_db_host": ""}，这些值会被忽略，由系统自动解析

            完整示例（安装WordPress依赖MySQL）：
            先安装MySQL：panel_docker_square_install(appname="mysql", name="my-mysql", params={"mysql_port": 13306, "mysql_root_password": "yourpassword"})
            再安装WordPress：panel_docker_square_install(appname="wordpress", name="my-wordpress", params={"wordpress_port": 18080, "mysql_database": "ry", "mysql_user": "ry", "mysql_password": "xxx", "panel_service_type": "my-mysql"})
    """
    try:
        if not appname or not name:
            return {'error': 'appname和name不能为空'}

        from apps.sysai.tools.base import AIToolRegistry
        registry = AIToolRegistry()
        registry.emit_progress('panel_docker_square_install', 'tool.log', 0, f'正在查找应用 {appname}...')

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

        registry.emit_progress('panel_docker_square_install', 'tool.log', 0, f'找到应用 {appname}，正在解析参数和依赖...')

        appid = app_info.get('appid', '')
        version = app_info.get('version', '') or 'latest'
        app_type = app_info.get('type', '')

        form_fields = app_info.get('formFields', [])
        default_params = {}
        selectapps_fields = []
        password_fields = []  # 记录密码字段，后续自动生成强密码
        version_select_fields = []  # 记录版本选择字段
        for field in form_fields:
            envkey = field.get('envkey', '')
            default_val = field.get('default', '')
            if envkey and default_val:
                default_params[envkey] = default_val
            if field.get('type') == 'selectapps':
                selectapps_fields.append(field)
            if field.get('type') == 'password' and envkey:
                password_fields.append(envkey)
            # 收集版本选择字段（type=select且envkey包含version）
            if field.get('type') == 'select' and envkey and 'version' in envkey.lower():
                version_select_fields.append(field)

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
                    # 强制转为字符串，防止AI传入整数等非字符串类型
                    child_value = str(child_value) if child_value is not None else ''
                    # 如果AI传入的值不是host:port格式（如传入了服务ID），忽略该值让系统自动填充
                    if child_value and ':' not in child_value:
                        child_value = ''
                    # 如果AI传入了不稳定的Docker网关IP（如172.18.0.1），替换为host.docker.internal
                    if child_value and _UNSTABLE_HOST_PATTERNS.match(child_value.split(':')[0]):
                        port_part = child_value.split(':')[1] if ':' in child_value else ''
                        child_value = f"host.docker.internal:{port_part}" if port_part else "host.docker.internal"

                if not child_value:
                    # 使用统一的依赖查找函数，支持名称模糊匹配
                    found, dep_source, dep_info = _find_installed_dependency(sa_appname)
                    if found and dep_source == 'square_installing':
                        # 依赖服务正在安装中，需要等待其完成
                        dep_name = dep_info.get('name', sa_appname)
                        registry.emit_progress('panel_docker_square_install', 'tool.log', 0,
                            f'依赖服务 {sa_appname}({dep_name}) 正在安装中，等待其完成...')
                        import time
                        for _wait in range(24):  # 最多等待120秒
                            time.sleep(5)
                            found2, dep_source2, dep_info2 = _find_installed_dependency(sa_appname)
                            if found2 and dep_source2 == 'square':
                                child_value = dep_info2.get('host_value', '')
                                registry.emit_progress('panel_docker_square_install', 'tool.log', 0,
                                    f'依赖服务 {sa_appname}({dep_name}) 已安装完成，自动关联')
                                break
                            elif not found2 or dep_source2 not in ('square', 'square_installing'):
                                # 安装失败或状态异常
                                return {
                                    'need_dependency': True,
                                    'error': f'依赖服务 {sa_appname}({dep_name}) 安装似乎失败，请检查后重试',
                                    'dependency_appname': sa_appname,
                                    'child_envkey': child_envkey,
                                    'dependency_in_square': True,
                                    'install_options': [
                                        f'1. 重新从容器广场安装 {sa_appname}',
                                        f'2. 使用Docker原生方式安装 {sa_appname}',
                                    ],
                                    'suggestion': f'依赖服务安装失败，请先使用 panel_docker_square_list 检查状态，或重新安装依赖服务。',
                                }
                        else:
                            # 等待超时，依赖仍在安装中
                            return {
                                'need_dependency': True,
                                'error': f'依赖服务 {sa_appname}({dep_name}) 安装时间较长，尚未完成',
                                'dependency_appname': sa_appname,
                                'child_envkey': child_envkey,
                                'dependency_in_square': True,
                                'install_options': [
                                    f'1. 等待 {sa_appname} 安装完成后重新安装 {appname}',
                                    f'2. 使用Docker原生方式安装 {sa_appname}',
                                ],
                                'suggestion': f'依赖服务 {sa_appname} 正在安装中（镜像拉取可能需要几分钟），请稍后使用 panel_docker_square_list 检查状态，确认running后再重新安装 {appname}。',
                            }
                    elif found:
                        child_value = dep_info.get('host_value', '')
                        registry.emit_progress('panel_docker_square_install', 'tool.log', 0,
                            f'依赖服务 {sa_appname} 已安装（来源: {"容器广场" if dep_source == "square" else "应用商店"}，实例: {dep_info.get("name", "")}），自动关联')
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

        # 从版本选择字段中提取版本号，覆盖默认version
        for vs_field in version_select_fields:
            vs_envkey = vs_field.get('envkey', '')
            vs_value = default_params.get(vs_envkey, '')
            if vs_value:
                version = vs_value

        # 自动为密码字段生成强密码：如果用户未提供或提供的是弱密码，则自动替换
        generated_passwords = {}
        for pwd_field in password_fields:
            current_val = default_params.get(pwd_field, '')
            if not current_val or str(current_val).lower() in _WEAK_PASSWORDS:
                new_pwd = _generate_strong_password()
                default_params[pwd_field] = new_pwd
                generated_passwords[pwd_field] = new_pwd

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

        # 检查镜像是否已在本地，用于预估安装时间
        image_needs_pull = True
        try:
            from utils.ruyiclass.dockerClass import DockerClient
            dc = DockerClient()
            if dc.client:
                # 读取模板docker-compose.yml获取镜像名
                tp_compose_path = f"{sq.templates_path}/{appname}/docker-compose.yml"
                if os.path.exists(tp_compose_path):
                    import yaml
                    with open(tp_compose_path, 'r', encoding='utf-8') as f:
                        compose_data = yaml.safe_load(f) or {}
                    services = compose_data.get('services', {})
                    all_images_exist = True
                    for svc_name, svc_conf in services.items():
                        img = svc_conf.get('image', '')
                        if img:
                            # 镜像名可能包含${VERSION}变量，用默认版本替换
                            if '${VERSION}' in img or '$VERSION' in img:
                                img = img.replace('${VERSION}', version).replace('$VERSION', version)
                            try:
                                dc.client.images.get(img)
                            except Exception:
                                all_images_exist = False
                                break
                    if all_images_exist and services:
                        image_needs_pull = False
        except Exception:
            pass  # 镜像检查失败不影响安装流程

        # 依赖MySQL的应用：先在MySQL容器中创建数据库和用户，再启动主应用
        # 这样主应用启动时数据库已就绪，避免连接失败
        registry.emit_progress('panel_docker_square_install', 'tool.log', 0, '正在检查数据库依赖...')
        db_init_result = _auto_init_mysql_database(default_params, selectapps_fields, name)

        isok, msg = sq.generate_app(cont=cont)
        if not isok:
            app_path = sq.get_dkapp_path(cont={'appname': appname, 'name': name})
            from utils.common import DeleteDir
            DeleteDir(app_path)
            return {'error': f'安装失败: {msg}'}

        registry.emit_progress('panel_docker_square_install', 'tool.log', 0, f'Docker Compose配置已生成，正在创建应用记录...')

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

        # 等待安装完成（轮询安装状态）
        # 策略：统一等待最多90秒，每5秒轮询一次，容器启动后立即返回
        # 无论镜像是否需要拉取，都尽量等待完成，避免AI需要额外调用检查状态
        import time
        install_wait_timeout = 90
        registry.emit_progress('panel_docker_square_install', 'tool.log', 0,
            f'{appname}({name}) 安装任务已提交，{"镜像拉取中" if image_needs_pull else "容器启动中"}，请耐心等待...')

        install_status = 'install'
        for wait_attempt in range(install_wait_timeout // 5):
            time.sleep(5)
            app_obj = RyDockerApps.objects.filter(name=name).first()
            if not app_obj:
                break
            install_status = sq.sync_app_install_status(app_obj)
            if install_status == 'running':
                registry.emit_progress('panel_docker_square_install', 'tool.log', 0,
                    f'{appname}({name}) 安装成功，容器已运行')
                break
            elif install_status == 'install_failed':
                registry.emit_progress('panel_docker_square_install', 'tool.log', 0,
                    f'{appname}({name}) 安装失败')
                break

        if install_status == 'install':
            if image_needs_pull:
                registry.emit_progress('panel_docker_square_install', 'tool.log', 0,
                    f'{appname}({name}) 镜像拉取中，安装仍在后台进行。请稍后使用 panel_docker_square_list 查看安装状态')
            else:
                registry.emit_progress('panel_docker_square_install', 'tool.log', 0,
                    f'{appname}({name}) 安装仍在进行中，请稍后使用 panel_docker_square_list 查看状态')

        result = {
            'success': install_status != 'install_failed',
            'message': f'{appname}({name}) 安装任务已提交，{msg}',
            'appname': appname,
            'name': name,
            'params': default_params,
            'install_status': install_status,
            'image_needs_pull': image_needs_pull,
        }
        if install_status == 'install_failed':
            result['error'] = f'{appname}({name}) 安装失败，请使用 panel_docker_square_list 查看状态，或使用 panel_diagnose_install 诊断问题'
        elif install_status == 'install' and image_needs_pull:
            result['hint'] = '镜像正在拉取中，安装可能需要几分钟。请稍后使用 panel_docker_square_list 检查安装状态，确认状态变为running后再进行验证。'
        elif install_status == 'install':
            result['hint'] = '安装仍在进行中，请稍后使用 panel_docker_square_list 检查安装状态。'
        if generated_passwords:
            result['generated_passwords'] = generated_passwords
            result['password_notice'] = '已自动生成强密码，请妥善保存以下密码信息'
        if db_init_result:
            result['database_init'] = db_init_result

        # 部署后推荐配置
        result['post_deploy_recommendation'] = {
            'message': '安装任务已提交！部署完成后建议继续配置以下选项：',
            'recommended_actions': [
                {'action': '域名绑定 + Nginx反向代理', 'reason': '支持域名访问，可申请SSL证书'},
                {'action': '防火墙端口放通', 'reason': '允许外部网络访问服务'},
                {'action': 'WAF防护', 'reason': '防护SQL注入、XSS等Web攻击'},
            ],
            'hint': '使用 panel_deploy_finalize 工具可一站式完成以上配置',
        }

        return result
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
