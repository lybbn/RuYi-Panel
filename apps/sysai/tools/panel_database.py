from apps.sysai.tools.base import register_tool
from apps.system.models import Databases
from utils.install.mysql import (
    Mysql_Connect, RY_CHECK_MYSQL_DATANAME_EXISTS,
    RY_CREATE_MYSQL_DATANAME, RY_CREATE_MYSQL_USER,
    RY_DELETE_MYSQL_DATABASE, RY_RESET_MYSQL_USER_PASS,
    RY_GET_MYSQL_ROOT_PASS,
)
from utils.security.safe_filter import is_validate_db_passwd


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
        db_type: 数据库类型，0=MySQL、1=SqlServer、2=MongoDB、3=PgSql、4=Redis，默认0
        format: 数据库编码，utf8、utf8mb4、gbk、big5，默认utf8mb4
        accept: 访问权限，all=所有人、localhost=本地服务器、ip=指定IP，默认localhost
        accept_ips: 允许访问的IP地址，多个用逗号分隔（仅accept=ip时需要）
    """
    try:
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
                return {'error': 'MySQL连接失败，请确保已安装MySQL并正在运行'}

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

    Args:
        db_type: 数据库类型，目前仅支持 mysql
    """
    try:
        if db_type == 'mysql':
            passwd = RY_GET_MYSQL_ROOT_PASS()
            if passwd:
                return {
                    'db_type': 'mysql',
                    'root_password': passwd,
                    'note': '请妥善保管此密码，不要泄露给他人',
                }
            return {'error': '获取MySQL Root密码失败，可能未安装MySQL'}
        return {'error': f'暂不支持获取 {db_type} 的Root密码'}
    except Exception as e:
        return {'error': f'获取密码失败: {str(e)}'}
