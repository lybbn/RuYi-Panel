import json as json_module
from apps.sysai.tools.base import register_tool
from utils.common import RunCommand
from utils.ruyiclass.dockerClass import DockerClient


def _get_docker_client():
    try:
        client = DockerClient()
        if client.client:
            return client
    except Exception:
        pass
    return None


def _run_docker_command(cmd: str, timeout: int = 30) -> dict:
    try:
        stdout, stderr = RunCommand(cmd, timeout=timeout)
        if stderr:
            return {'error': stderr.strip()[:2000]}
        return {'output': stdout.strip()[:15000]}
    except Exception as e:
        return {'error': str(e)}


@register_tool(id='docker_list_containers', category='docker', name_cn='容器列表', risk_level='low')
def docker_list_containers(all: bool = False):
    """列出Docker容器，包括运行中和停止的容器。当用户需要查看服务器上的Docker容器时使用。

    Args:
        all: 是否显示所有容器（包括停止的），默认只显示运行中的
    """
    client = _get_docker_client()
    if client:
        try:
            containers = client.local_containers_list(all=all)
            result = []
            for c in containers:
                result.append({
                    'id': c.short_id.replace('sha256:', ''),
                    'name': c.name,
                    'image': c.attrs.get('Config', {}).get('Image', ''),
                    'status': c.status,
                    'ports': str(c.attrs.get('NetworkSettings', {}).get('Ports', '')),
                    'size': '',
                })
            return {
                'containers': result,
                'total': len(result),
                'show_all': all,
            }
        except Exception as e:
            pass

    cmd = f'docker ps {"-a" if all else ""} --format "{{{{.ID}}}}|{{{{.Names}}}}|{{{{.Image}}}}|{{{{.Status}}}}|{{{{.Ports}}}}|{{{{.Size}}}}"'
    result = _run_docker_command(cmd)

    if 'error' in result:
        return result

    containers = []
    for line in result.get('output', '').split('\n'):
        if not line.strip():
            continue
        parts = line.split('|')
        containers.append({
            'id': parts[0] if len(parts) > 0 else '',
            'name': parts[1] if len(parts) > 1 else '',
            'image': parts[2] if len(parts) > 2 else '',
            'status': parts[3] if len(parts) > 3 else '',
            'ports': parts[4] if len(parts) > 4 else '',
            'size': parts[5] if len(parts) > 5 else '',
        })

    return {
        'containers': containers,
        'total': len(containers),
        'show_all': all,
    }


@register_tool(id='docker_container_info', category='docker', name_cn='容器详情', risk_level='low')
def docker_container_info(container: str):
    """获取Docker容器的详细信息，包括配置、网络、挂载等。当用户需要了解某个容器的详细配置时使用。

    Args:
        container: 容器名称或ID
    """
    result = _run_docker_command(f'docker inspect {container}')
    if 'error' in result:
        return result

    try:
        inspect_data = json_module.loads(result.get('output', '[]'))
        if not inspect_data:
            return {'error': f'容器不存在: {container}'}

        info = inspect_data[0]
        config = info.get('Config', {})
        network_settings = info.get('NetworkSettings', {})

        return {
            'id': info.get('Id', '')[:12],
            'name': info.get('Name', '').lstrip('/'),
            'image': config.get('Image', ''),
            'status': info.get('State', {}).get('Status', ''),
            'running': info.get('State', {}).get('Running', False),
            'created': info.get('Created', ''),
            'restart_policy': info.get('HostConfig', {}).get('RestartPolicy', {}).get('Name', ''),
            'ip_address': network_settings.get('IPAddress', ''),
            'port_bindings': [
                f'{k} -> {v}' for k, v in network_settings.get('Ports', {}).items() if v
            ][:10],
            'mounts': [
                f'{m.get("Source", "")} -> {m.get("Destination", "")}'
                for m in info.get('Mounts', [])
            ][:10],
            'env': config.get('Env', [])[:15],
        }
    except json_module.JSONDecodeError:
        return {'error': '解析容器信息失败'}


@register_tool(id='docker_container_logs', category='docker', name_cn='容器日志', risk_level='low')
def docker_container_logs(container: str, lines: int = 50, since: str = ''):
    """获取Docker容器的日志。当用户需要查看容器运行日志排查问题时使用。

    Args:
        container: 容器名称或ID
        lines: 返回的日志行数，默认50
        since: 查看多久以来的日志，如 '1h'、'30m'，为空则查看全部
    """
    cmd = f'docker logs --tail {lines}'
    if since:
        cmd += f' --since {since}'
    cmd += f' {container} 2>&1'

    result = _run_docker_command(cmd)
    if 'error' in result:
        return result

    return {
        'container': container,
        'lines': lines,
        'content': result.get('output', '')[:15000],
        'truncated': len(result.get('output', '')) > 15000,
    }


@register_tool(id='docker_manage_container', category='docker', name_cn='容器管理', risk_level='high')
def docker_manage_container(container: str, action: str):
    """管理Docker容器，支持启动、停止、重启、删除等操作。⚠️此为高危操作，请确认后再执行。

    Args:
        container: 容器名称或ID
        action: 操作类型，start(启动)、stop(停止)、restart(重启)、remove(删除)、pause(暂停)、unpause(恢复)
    """
    valid_actions = {
        'start': 'start',
        'stop': 'stop',
        'restart': 'restart',
        'remove': 'rm -f',
        'pause': 'pause',
        'unpause': 'unpause',
    }

    if action not in valid_actions:
        return {'error': f'无效操作: {action}，可用操作: {", ".join(valid_actions.keys())}'}

    cmd = f'docker {valid_actions[action]} {container}'
    result = _run_docker_command(cmd, timeout=60)

    if 'error' in result:
        return result

    return {
        'container': container,
        'action': action,
        'success': True,
        'message': f'容器 {container} {action} 操作成功',
    }


@register_tool(id='docker_list_images', category='docker', name_cn='镜像列表', risk_level='low')
def docker_list_images():
    """列出Docker镜像。当用户需要查看服务器上的Docker镜像时使用。"""
    client = _get_docker_client()
    if client:
        try:
            images = client.local_images_list()
            result = []
            for img in images:
                tags = img.attrs.get('RepoTags', [])
                result.append({
                    'repository': tags[0].split(':')[0] if tags else '',
                    'tag': tags[0].split(':')[1] if tags and ':' in tags[0] else 'latest',
                    'id': img.short_id.replace('sha256:', ''),
                    'size': str(img.attrs.get('Size', '')),
                    'created': img.attrs.get('Created', ''),
                })
            return {
                'images': result,
                'total': len(result),
            }
        except Exception:
            pass

    result = _run_docker_command(
        'docker images --format "{{.Repository}}|{{.Tag}}|{{.ID}}|{{.Size}}|{{.CreatedSince}}"'
    )

    if 'error' in result:
        return result

    images = []
    for line in result.get('output', '').split('\n'):
        if not line.strip():
            continue
        parts = line.split('|')
        images.append({
            'repository': parts[0] if len(parts) > 0 else '',
            'tag': parts[1] if len(parts) > 1 else '',
            'id': parts[2] if len(parts) > 2 else '',
            'size': parts[3] if len(parts) > 3 else '',
            'created': parts[4] if len(parts) > 4 else '',
        })

    return {
        'images': images,
        'total': len(images),
    }


@register_tool(id='docker_stats', category='docker', name_cn='容器资源', risk_level='low')
def docker_stats(container: str = ''):
    """获取Docker容器的资源使用情况（CPU、内存、网络、磁盘IO）。当用户需要监控容器资源消耗时使用。

    Args:
        container: 容器名称或ID，为空则显示所有运行中容器的资源使用
    """
    cmd = f'docker stats --no-stream --format "{{{{.Name}}}}|{{{{.CPUPerc}}}}|{{{{.MemUsage}}}}|{{{{.MemPerc}}}}|{{{{.NetIO}}}}|{{{{.BlockIO}}}}"'
    if container:
        cmd += f' {container}'

    result = _run_docker_command(cmd)
    if 'error' in result:
        return result

    stats = []
    for line in result.get('output', '').split('\n'):
        if not line.strip():
            continue
        parts = line.split('|')
        stats.append({
            'name': parts[0] if len(parts) > 0 else '',
            'cpu_percent': parts[1] if len(parts) > 1 else '',
            'mem_usage': parts[2] if len(parts) > 2 else '',
            'mem_percent': parts[3] if len(parts) > 3 else '',
            'net_io': parts[4] if len(parts) > 4 else '',
            'block_io': parts[5] if len(parts) > 5 else '',
        })

    return {
        'stats': stats,
        'container': container or 'all',
    }
