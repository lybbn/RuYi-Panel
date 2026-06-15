import json
from apps.sysai.tools.base import register_tool
from apps.system.models import Databases
from utils.install.mysql import (
    Mysql_Connect, RY_CHECK_MYSQL_DATANAME_EXISTS,
    RY_CREATE_MYSQL_DATANAME, RY_CREATE_MYSQL_USER,
    RY_DELETE_MYSQL_DATABASE, RY_RESET_MYSQL_USER_PASS,
    RY_GET_MYSQL_ROOT_PASS,
)
from utils.security.safe_filter import is_validate_db_passwd


def _create_database_via_docker_mysql(db_name, db_user, db_pass, format='utf8mb4', accept='localhost', accept_ips=''):
    """当本地MySQL不可用时，尝试通过Docker容器中的MySQL创建数据库和用户"""
    try:
        from apps.sysdocker.models import RyDockerApps as DockerApps
        from utils.common import RunCommand
        from apps.sysai.tools.base import AIToolRegistry
        import time

        registry = AIToolRegistry()
        registry.emit_progress('panel_database_create', 'tool.log', 0, '正在查找Docker MySQL容器...')

        # 查找MySQL容器应用
        mysql_apps = DockerApps.objects.filter(appname='mysql')
        if not mysql_apps:
            return {'error': '未找到Docker MySQL应用，请先通过Docker广场安装MySQL'}

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
            return {'error': '未找到Docker MySQL root密码'}

        mysql_container = f"{mysql_name}-{mysql_name}-1"
        registry.emit_progress('panel_database_create', 'tool.log', 0, f'找到MySQL容器: {mysql_container}，等待MySQL就绪...')

        # 等待MySQL就绪（最多120秒）
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
            registry.emit_progress('panel_database_create', 'tool.log', 0, f'等待MySQL就绪... ({elapsed}s/120s)')
            time.sleep(5)

        if not ready:
            return {'error': f'Docker MySQL容器({mysql_container})未就绪，已等待120秒'}

        registry.emit_progress('panel_database_create', 'tool.log', 0, 'MySQL已就绪，检查数据库是否已存在...')

        # 检查数据库是否已存在
        out, err, rc = RunCommand(
            f'docker exec {mysql_container} mysql -uroot -p"{mysql_root_password}" -e "SHOW DATABASES" 2>/dev/null',
            timeout=10, returncode=True
        )
        if db_name in (out or ''):
            return {'error': f'Docker MySQL中已存在数据库: {db_name}'}

        registry.emit_progress('panel_database_create', 'tool.log', 0, f'正在创建数据库 {db_name} 和用户 {db_user}...')

        # 创建数据库和用户
        host_clause = '%' if accept == 'all' else ('localhost' if accept == 'localhost' else accept_ips)
        db_collate_dic = {
            'utf8': 'utf8_general_ci',
            'utf8mb4': 'utf8mb4_unicode_ci',
        }
        db_collate = db_collate_dic.get(format, 'utf8mb4_unicode_ci')

        sql = (
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET {format} COLLATE {db_collate}; "
            f"CREATE USER IF NOT EXISTS '{db_user}'@'{host_clause}' IDENTIFIED WITH mysql_native_password BY '{db_pass}'; "
            f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'{host_clause}'; "
            f"FLUSH PRIVILEGES;"
        )
        out, err, rc = RunCommand(
            f'docker exec -i {mysql_container} mysql -uroot -p"{mysql_root_password}" <<\'EOSQL\'\n{sql}\nEOSQL',
            timeout=15, returncode=True
        )

        # MySQL命令行密码警告可能导致rc!=0，但SQL可能已执行成功
        if rc != 0:
            registry.emit_progress('panel_database_create', 'tool.log', 0, '验证数据库是否创建成功...')
            out2, err2, rc2 = RunCommand(
                f'docker exec {mysql_container} mysql -uroot -p"{mysql_root_password}" -e "SHOW DATABASES" 2>/dev/null',
                timeout=10, returncode=True
            )
            if db_name not in (out2 or ''):
                return {'error': f'在Docker MySQL中创建数据库失败: {err}'}

        registry.emit_progress('panel_database_create', 'tool.log', 0, f'数据库 {db_name} 创建成功')

        return {
            'success': True,
            'database': db_name,
            'user': db_user,
            'container': mysql_container,
            'message': f'已在Docker MySQL容器({mysql_container})中创建数据库 {db_name} 和用户 {db_user}'
        }
    except Exception as e:
        return {'error': f'Docker MySQL创建数据库异常: {str(e)}'}


@register_tool(id='panel_database_list', category='panel', name_cn='数据库列表', risk_level='low')
def panel_database_list(db_type: int = -1, search: str = ''):
    """获取如意面板管理的数据库列表。这是面板内置的数据库管理功能，支持MySQL、SqlServer、MongoDB、PgSql、Redis等。当用户需要查看数据库、了解数据库状态时，必须优先使用此工具而不是直接命令行查询。

    Args:
        db_type: 数据库类型筛选，-1=全部、0=MySQL、1=SqlServer、2=MongoDB、3=PgSql、4=Redis，默认-1
        search: 搜索关键词，按数据库名、用户名、主机地址搜索
    """
    try:
        queryset = Databases.objects.all().order_by('-create_at')
        if db_type >= 0:
            queryset = queryset.filter(db_type=db_type)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(db_name__icontains=search)
                | Q(db_user__icontains=search)
                | Q(db_host__icontains=search)
            )

        type_map = {0: 'MySQL', 1: 'SqlServer', 2: 'MongoDB', 3: 'PgSql', 4: 'Redis'}
        accept_map = {'all': '所有人', 'localhost': '本地服务器', 'ip': '指定IP'}

        result = []
        for db in queryset:
            result.append({
                'id': db.id,
                'db_name': db.db_name,
                'db_user': db.db_user,
                'db_host': db.db_host or 'localhost',
                'db_port': db.db_port,
                'db_type': db.db_type,
                'typename': type_map.get(db.db_type, '未知'),
                'format': db.format,
                'accept': db.accept,
                'accept_display': accept_map.get(db.accept, db.accept or ''),
                'is_remote': db.is_remote,
                'remark': db.remark or '',
                'create_at': str(db.create_at),
            })

        type_count = {}
        for item in result:
            tn = item['typename']
            type_count[tn] = type_count.get(tn, 0) + 1

        return {
            'databases': result,
            'total': len(result),
            'type_summary': type_count,
        }
    except Exception as e:
        return {'error': f'获取数据库列表失败: {str(e)}'}


@register_tool(id='panel_database_create', category='panel', name_cn='创建数据库', risk_level='high')
def panel_database_create(db_name: str, db_user: str, db_pass: str, db_type: int = 0,
                          format: str = 'utf8mb4', accept: str = 'localhost',
                          accept_ips: str = ''):
    """在如意面板中创建数据库。⚠️此为高危操作，会直接在数据库服务器上创建数据库和用户。创建前请确保已通过应用商店安装了对应的数据库软件（如MySQL）。

    Args:
        db_name: 数据库名称，只能包含字母、数字、下划线、点、横线
        db_user: 数据库用户名，不能使用root、mysql、test等保留名
        db_pass: 数据库密码
        db_type: 数据库类型，0=MySQL、1=SqlServer、2=MongoDB、3=PgSql、4=Redis，默认0（也支持传入字符串如"mysql"、"0"等，会自动转换）
        format: 数据库编码，utf8、utf8mb4、gbk、big5，默认utf8mb4
        accept: 访问权限，all=所有人、localhost=本地服务器、ip=指定IP，默认localhost
        accept_ips: 允许访问的IP地址，多个用逗号分隔（仅accept=ip时需要）
    """
    try:
        # 兼容AI传入字符串类型的db_type（如"mysql"、"0"、"1"等）
        _DB_TYPE_MAP = {
            'mysql': 0, 'mssql': 1, 'sqlserver': 1, 'mongodb': 2, 'pgsql': 3, 'postgres': 3, 'postgresql': 3, 'redis': 4,
        }
        if isinstance(db_type, str):
            if db_type.lower() in _DB_TYPE_MAP:
                db_type = _DB_TYPE_MAP[db_type.lower()]
            else:
                try:
                    db_type = int(db_type)
                except (ValueError, TypeError):
                    return {'error': f'不支持的数据库类型: {db_type}，可用值: 0=MySQL、1=SqlServer、2=MongoDB、3=PgSql、4=Redis，或传入字符串如"mysql"'}

        import re
        reg = r"^[\w\.-]+$"
        checks_list = ['root', 'mysql', 'test', 'sys', 'mysql.sys', 'mysql.session', 'mysql.infoschema']

        if not re.match(reg, db_user):
            return {'error': '数据库用户名不合法，只能包含字母、数字、下划线、点、横线'}
        if not re.match(reg, db_name):
            return {'error': '数据库名不合法，只能包含字母、数字、下划线、点、横线'}
        if db_user in checks_list:
            return {'error': f'数据库用户名不合法，不能使用保留名: {db_user}'}
        if db_name in checks_list:
            return {'error': f'数据库名不合法，不能使用保留名: {db_name}'}
        if len(db_user) > 32:
            return {'error': '数据库用户名不能超过32位'}

        pass_ok, pass_msg = is_validate_db_passwd(db_pass)
        if not pass_ok:
            return {'error': pass_msg}

        if Databases.objects.filter(db_name=db_name, db_type=db_type, is_remote=False).exists():
            return {'error': f'已存在同名数据库: {db_name}'}

        if accept == 'ip' and not accept_ips:
            return {'error': '指定IP访问权限时，必须填写允许的IP地址'}

        if db_type == 0:
            db_conn = Mysql_Connect()
            if not db_conn:
                # 本地MySQL连接失败，尝试通过Docker容器中的MySQL创建
                docker_result = _create_database_via_docker_mysql(db_name, db_user, db_pass, format, accept, accept_ips)
                if docker_result.get('success'):
                    db_ins = Databases.objects.create(
                        db_name=db_name, db_user=db_user, db_pass=db_pass,
                        db_type=db_type, format=format, accept=accept,
                        accept_ips=accept_ips, is_remote=False,
                    )
                    docker_result['db_id'] = db_ins.id
                    docker_result['message'] = f'数据库 {db_name} 创建成功（通过Docker MySQL容器）'
                    return docker_result
                else:
                    return {'error': f'MySQL连接失败，本地MySQL未运行且Docker MySQL创建也失败: {docker_result.get("error", "未知错误")}'}

            if RY_CHECK_MYSQL_DATANAME_EXISTS(db_conn, db_name):
                return {'error': f'MySQL中已存在数据库: {db_name}'}

            db_collate_dic = {
                'utf8': 'utf8_general_ci',
                'utf8mb4': 'utf8mb4_unicode_ci',
                'gbk': 'gbk_chinese_ci',
                'big5': 'big5_chinese_ci',
            }
            db_collate = db_collate_dic.get(format, 'utf8mb4_unicode_ci')

            RY_CREATE_MYSQL_DATANAME(db_conn, {
                'db_name': db_name, 'charset': format, 'db_collate': db_collate,
            })
            RY_CREATE_MYSQL_USER(db_conn, {
                'db_name': db_name, 'db_user': db_user,
                'db_pass': db_pass, 'accept': accept, 'accept_ips': accept_ips,
            })

        db_ins = Databases.objects.create(
            db_name=db_name, db_user=db_user, db_pass=db_pass,
            db_type=db_type, format=format, accept=accept,
            accept_ips=accept_ips, is_remote=False,
        )

        return {
            'success': True,
            'message': f'数据库 {db_name} 创建成功',
            'db_id': db_ins.id,
        }
    except Exception as e:
        return {'error': f'创建数据库失败: {str(e)}'}


@register_tool(id='panel_database_delete', category='panel', name_cn='删除数据库', risk_level='high')
def panel_database_delete(db_id: int):
    """删除如意面板中的数据库。⚠️此为高危操作，会同时删除数据库和数据库用户，数据不可恢复！

    Args:
        db_id: 数据库ID（从panel_database_list返回的id获取）
    """
    try:
        db_ins = Databases.objects.filter(id=db_id).first()
        if not db_ins:
            return {'error': f'数据库ID {db_id} 不存在，请先用panel_database_list查询'}

        db_name = db_ins.db_name
        db_user = db_ins.db_user
        db_type = db_ins.db_type

        if db_type == 0 and not db_ins.is_remote:
            db_conn = Mysql_Connect()
            if db_conn:
                RY_DELETE_MYSQL_DATABASE(db_conn, {
                    'db_name': db_name, 'db_user': db_user,
                })

        from apps.sysbak.models import RuyiBackup
        bk_qy = RuyiBackup.objects.filter(type=1, fid=db_id)
        for b in bk_qy:
            from utils.common import DeleteFile
            DeleteFile(b.filename, empty_tips=False)
            b.delete()

        db_ins.delete()

        return {
            'success': True,
            'message': f'数据库 {db_name} 删除成功',
        }
    except Exception as e:
        return {'error': f'删除数据库失败: {str(e)}'}


@register_tool(id='panel_database_reset_pass', category='panel', name_cn='重置数据库密码', risk_level='high')
def panel_database_reset_pass(db_id: int, new_pass: str):
    """重置如意面板中数据库用户的密码。⚠️此为高危操作，修改密码后使用旧密码的应用将无法连接数据库。

    Args:
        db_id: 数据库ID（从panel_database_list返回的id获取）
        new_pass: 新密码
    """
    try:
        db_ins = Databases.objects.filter(id=db_id).first()
        if not db_ins:
            return {'error': f'数据库ID {db_id} 不存在'}

        pass_ok, pass_msg = is_validate_db_passwd(new_pass)
        if not pass_ok:
            return {'error': pass_msg}

        if db_ins.db_type == 0 and not db_ins.is_remote:
            db_conn = Mysql_Connect()
            if not db_conn:
                return {'error': 'MySQL连接失败'}
            RY_RESET_MYSQL_USER_PASS(db_conn, {
                'db_name': db_ins.db_name, 'db_user': db_ins.db_user,
                'db_pass': new_pass, 'accept': db_ins.accept or 'localhost',
                'accept_ips': db_ins.accept_ips or '',
            })

        db_ins.db_pass = new_pass
        db_ins.save()

        return {
            'success': True,
            'message': f'数据库 {db_ins.db_name} 用户 {db_ins.db_user} 密码重置成功',
        }
    except Exception as e:
        return {'error': f'重置密码失败: {str(e)}'}


@register_tool(id='panel_database_root_pass', category='panel', name_cn='获取数据库Root密码', risk_level='low')
def panel_database_root_pass(db_type: str = 'mysql'):
    """获取如意面板管理的数据库Root密码。当用户需要获取数据库管理员密码时使用。
    支持两种MySQL安装方式：应用商店安装和Docker广场安装。

    Args:
        db_type: 数据库类型，目前仅支持 mysql
    """
    try:
        if db_type == 'mysql':
            # 1. 先尝试应用商店安装的MySQL
            passwd = RY_GET_MYSQL_ROOT_PASS()
            if passwd:
                return {
                    'db_type': 'mysql',
                    'root_password': passwd,
                    'install_method': '应用商店',
                    'note': '请妥善保管此密码，不要泄露给他人',
                }

            # 2. 尝试Docker广场安装的MySQL
            from apps.sysdocker.models import RyDockerApps
            mysql_apps = RyDockerApps.objects.filter(appname='mysql')
            for app in mysql_apps:
                params = {}
                if app.params:
                    try:
                        params = json.loads(app.params) if isinstance(app.params, str) else app.params
                    except Exception:
                        params = {}
                root_pwd = params.get('mysql_root_password', '')
                if root_pwd:
                    return {
                        'db_type': 'mysql',
                        'root_password': root_pwd,
                        'install_method': 'Docker广场',
                        'container_name': f"{app.name}-{app.name}-1",
                        'app_name': app.name,
                        'app_status': app.status,
                        'note': '请妥善保管此密码，不要泄露给他人',
                    }

            return {'error': '获取MySQL Root密码失败，未找到已安装的MySQL（应用商店和Docker广场均未检测到）'}
        return {'error': f'暂不支持获取 {db_type} 的Root密码'}
    except Exception as e:
        return {'error': f'获取密码失败: {str(e)}'}
