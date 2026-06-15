import platform
from apps.sysai.tools.base import register_tool
from apps.sysai.tools.common import run_cmd
from utils.server.system import system
from utils.ruyiclass.mysqlClass import MysqlClient
from utils.ruyiclass.redisClass import RedisClient


def _get_mysql_client(db_name: str = ''):
    try:
        client = MysqlClient.get_client(
            db_host='127.0.0.1',
            db_port=3306,
            db_user='root',
            db_password='',
            db_name=db_name,
            connect_timeout=5,
        )
        if client:
            return client
    except Exception:
        pass
    return None


def _get_redis_client():
    try:
        client = RedisClient.get_client(
            db_host='127.0.0.1',
            db_port=6379,
            db_password='',
            db=0,
        )
        if client:
            return client
    except Exception:
        pass
    return None


@register_tool(id='mysql_status', category='database', name_cn='MySQL状态', risk_level='low')
def mysql_status():
    """获取MySQL/MariaDB服务状态和基本运行信息，包括连接数、查询数、缓冲池状态等。当用户需要检查数据库运行状态时使用。"""
    status_info = {}

    for svc_name in ['mysql', 'mariadb', 'mysqld']:
        try:
            svc_status = system.GetServiceStatus(svc_name)
            if not svc_status.get('error') and svc_status.get('is_active') is not None:
                status_info['service_name'] = svc_name
                status_info['service_active'] = svc_status.get('is_active', False)
                status_info['service_status'] = svc_status
                break
        except Exception:
            continue

    if 'service_active' not in status_info:
        status_info['service_active'] = False
        status_info['message'] = '未检测到 MySQL/MariaDB 服务'

    metrics_result = run_cmd(
        'mysqladmin status 2>/dev/null || echo "需要MySQL root密码才能获取详细状态"'
    )
    if 'output' in metrics_result:
        status_info['metrics'] = metrics_result['output']

    return status_info


@register_tool(id='mysql_execute', category='database', name_cn='MySQL查询', risk_level='high')
def mysql_execute(query: str, database: str = ''):
    """执行MySQL/MariaDB SQL查询语句。⚠️此为高危操作，可能修改或删除数据，请确认SQL语句安全后再执行。

    Args:
        query: SQL查询语句
        database: 数据库名，为空则不指定
    """
    if any(kw in query.upper() for kw in ['DROP', 'TRUNCATE', 'DELETE FROM', 'GRANT', 'REVOKE']):
        return {'warning': '检测到危险SQL操作，请确认是否真的要执行此操作', 'query': query}

    db_arg = f'-D {database}' if database else ''
    cmd = f'mysql {db_arg} -e "{query}" 2>&1'

    result = run_cmd(cmd)
    if 'error' in result:
        return result

    return {
        'query': query,
        'database': database or 'default',
        'result': result.get('output', ''),
    }


@register_tool(id='mysql_list_databases', category='database', name_cn='MySQL数据库列表', risk_level='low')
def mysql_list_databases():
    """列出MySQL/MariaDB中的所有数据库。当用户需要查看有哪些数据库时使用。"""
    client = _get_mysql_client()
    if client:
        try:
            result = client.query('SHOW DATABASES')
            databases = [
                row[0] for row in result
                if row[0] not in ('information_schema', 'performance_schema', 'mysql', 'sys')
            ]
            return {
                'databases': databases,
                'total': len(databases),
            }
        except Exception:
            pass

    result = run_cmd('mysql -e "SHOW DATABASES;" 2>&1')
    if 'error' in result:
        return result

    databases = []
    lines = result.get('output', '').split('\n')
    for line in lines[1:]:
        db_name = line.strip()
        if db_name and db_name not in ('Database', 'information_schema', 'performance_schema', 'sys'):
            databases.append(db_name)

    return {
        'databases': databases,
        'total': len(databases),
    }


@register_tool(id='redis_status', category='database', name_cn='Redis状态', risk_level='low')
def redis_status():
    """获取Redis服务状态和基本运行信息，包括内存使用、连接数、命中率等。当用户需要检查Redis运行状态时使用。"""
    status_info = {}

    for svc_name in ['redis', 'redis-server']:
        try:
            svc_status = system.GetServiceStatus(svc_name)
            if not svc_status.get('error') and svc_status.get('is_active') is not None:
                status_info['service_name'] = svc_name
                status_info['service_active'] = svc_status.get('is_active', False)
                status_info['service_status'] = svc_status
                break
        except Exception:
            continue

    if 'service_active' not in status_info:
        status_info['service_active'] = False
        status_info['message'] = '未检测到 Redis 服务'

    client = _get_redis_client()
    if client:
        try:
            info = client.info()
            status_info['redis_info'] = str(info)[:3000]
            return status_info
        except Exception:
            pass

    info_result = run_cmd('redis-cli info 2>/dev/null | head -n 50')
    if 'output' in info_result:
        status_info['redis_info'] = info_result['output']

    return status_info


@register_tool(id='redis_execute', category='database', name_cn='Redis命令', risk_level='high')
def redis_execute(command: str):
    """执行Redis命令。⚠️此为高危操作，可能修改或删除数据，请确认命令安全后再执行。

    Args:
        command: Redis命令，如 INFO、DBSIZE、GET key、SET key value 等
    """
    if any(cmd in command.upper() for cmd in ['FLUSHALL', 'FLUSHDB', 'SHUTDOWN', 'DEBUG']):
        return {'warning': '检测到危险Redis操作，请确认是否真的要执行此操作', 'command': command}

    result = run_cmd(f'redis-cli {command} 2>&1')
    if 'error' in result:
        return result

    return {
        'command': command,
        'result': result.get('output', ''),
    }