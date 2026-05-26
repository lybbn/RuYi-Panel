from apps.sysai.tools.base import register_tool
from utils.server.system import system


@register_tool(id='get_service_status', category='service', name_cn='服务状态', risk_level='low')
def get_service_status(service_name: str):
    """获取指定系统服务的运行状态，包括是否运行、PID、内存占用等。当用户询问某个服务是否正常运行时使用。

    Args:
        service_name: 服务名称，如 nginx、mysql、redis、docker 等
    """
    try:
        return system.GetServiceStatus(service_name)
    except Exception as e:
        return {'error': f'获取服务状态失败: {str(e)}'}


@register_tool(id='list_services', category='service', name_cn='服务列表', risk_level='low')
def list_services(service_type: str = 'running'):
    """列出系统服务，可筛选运行中、已停止或全部服务。当用户需要查看服务器上运行了哪些服务时使用。

    Args:
        service_type: 服务类型筛选，running(运行中)、stopped(已停止)、all(全部)，默认running
    """
    try:
        return system.ListServices(service_type)
    except Exception as e:
        return {'error': f'获取服务列表失败: {str(e)}'}


@register_tool(id='manage_service', category='service', name_cn='服务管理', risk_level='high')
def manage_service(service_name: str, action: str):
    """管理系统服务，支持启动、停止、重启、重载等操作。⚠️此为高危操作，会影响服务运行状态，请确认后再执行。

    Args:
        service_name: 服务名称，如 nginx、mysql、redis、docker
        action: 操作类型，start(启动)、stop(停止)、restart(重启)、reload(重载)、enable(开机自启)、disable(禁用开机自启)
    """
    try:
        success, msg = system.SetServiceStatus(service_name, action)
        return {
            'service_name': service_name,
            'action': action,
            'success': success,
            'message': msg,
        }
    except Exception as e:
        return {'error': f'服务操作失败: {str(e)}'}


@register_tool(id='get_service_logs', category='service', name_cn='服务日志', risk_level='low')
def get_service_logs(service_name: str, lines: int = 50, since: str = '1 hour ago'):
    """获取指定服务的最近日志。当用户需要排查服务问题时使用。

    Args:
        service_name: 服务名称
        lines: 返回的日志行数，默认50
        since: 查看多久以来的日志，如 '1 hour ago'、'30 min ago'、'1 day ago'，默认1小时
    """
    try:
        return system.GetServiceLogs(service_name, lines, since)
    except Exception as e:
        return {'error': f'获取服务日志失败: {str(e)}'}