import json
import os
import datetime
from apps.sysai.tools.base import register_tool
from utils.common import GetSoftList, current_os, GetLogsPath
from utils.install.install_soft import Check_Soft_Installed, Ry_Start_Soft, Ry_Stop_Soft, Ry_Restart_Soft, Ry_Reload_Soft, Ry_Uninstall_Soft
from apps.sysshop.models import RySoftShop
from apps.systask.models import SysTaskCenter


@register_tool(id='panel_shop_list', category='panel', name_cn='应用商店列表', risk_level='low')
def panel_shop_list(soft_type: str = '0', search: str = ''):
    """获取如意面板应用商店的软件列表。这是面板内置的应用商店，包含Nginx、MySQL、Redis、PHP、Python、Go等可一键安装的软件。当用户需要安装软件、查看已安装软件、或询问某个软件是否可用时，必须优先使用此工具而不是execute_command。

    Args:
        soft_type: 软件类型筛选，0=全部、1=已安装、2=数据库、3=Web服务器、4=运行环境、5=安全防护，默认0
        search: 搜索关键词，按软件名称或描述搜索
    """
    try:
        softlist = GetSoftList()
        is_windows = current_os == 'windows'

        if search:
            softlist = [
                item for item in softlist
                if search.lower() in item.get('title', '').lower()
                or search.lower() in item.get('name', '').lower()
                or search.lower() in item.get('desc', '').lower()
            ]

        if soft_type != '0':
            if soft_type == '1':
                # 已安装类型在后续循环中通过 Check_Soft_Installed 真实检测后再过滤
                pass
            else:
                softlist = [item for item in softlist if str(item.get('type')) == soft_type]

        result = []
        for item in softlist:
            detail_version = None
            get_status = True
            if item['name'] in ['python', 'go']:
                if item.get('versions'):
                    detail_version = item['versions'][0]['c_version']
                get_status = False
            elif item['name'] == 'php':
                if item.get('versions'):
                    detail_version = item['versions'][0]['c_version']
                get_status = False

            installed, version, status, install_path = Check_Soft_Installed(
                name=item['name'], is_windows=is_windows,
                version=detail_version, get_status=get_status
            )

            version_list = []
            for v in item.get('versions', []):
                version_list.append(f'{v.get("c_version", v.get("version", ""))}(id:{v.get("id")})')

            result.append({
                'name': item.get('name'),
                'title': item.get('title'),
                'type': item.get('type'),
                'typename': item.get('typename', ''),
                'installed': installed,
                'version': version,
                'status': status,
                'available_versions': ', '.join(version_list),
            })

        if soft_type == '1':
            result = [item for item in result if item.get('installed')]

        return {
            'soft_list': result,
            'total': len(result),
            'filter_type': soft_type,
        }
    except Exception as e:
        return {'error': f'获取应用商店列表失败: {str(e)}'}


@register_tool(id='panel_shop_install', category='panel', name_cn='安装应用', risk_level='high')
def panel_shop_install(soft_name: str, version_id: int = 0):
    """从如意面板应用商店安装软件。安装过程是异步的，会创建安装任务。⚠️此为高危操作，会修改系统环境，请确认后再执行。

    安装前应先用panel_shop_list查询该软件是否已安装及可用的版本。如果软件已安装则不要重复安装。

    ⚠️重要规则：
    1. Nginx仅支持安装OpenResty版本（version字段为"openresty"的版本），不支持安装标准Nginx版本。安装Nginx时无需指定version_id，系统会自动选择OpenResty版本。
    2. Linux下Nginx OpenResty支持两种安装方式：编译安装（支持任意版本+WAF模块）和快速安装（通过系统包管理器apt/yum，秒级完成，OpenResty自带WAF/Lua支持）。如果用户未明确指定安装方式，优先推荐快速安装（需选择版本中带有"(快速)"标记的版本）。
    3. 如果之前的安装任务失败了，不要自动重新安装。应先告知用户失败原因，等用户明确表示要重试后再调用此工具。
    4. 每次只应安装一个软件，不要在一次回复中连续调用多次panel_shop_install。
    5. 任务提交后返回的note中会提示不要立即查询状态。安装是异步的，任务刚提交时状态为等待中，此时查询状态没有意义。应告知用户安装已提交，等用户主动询问进度时再调用panel_shop_task_status查询。

    Args:
        soft_name: 软件名称，如 nginx、mysql、redis、php、python、go 等（必须是应用商店中存在的名称）
        version_id: 版本ID，从panel_shop_list的versions中获取，默认0表示自动选择（Nginx会自动选择OpenResty版本）
    """
    try:
        softlist = GetSoftList()
        is_windows = current_os == 'windows'

        soft = None
        for item in softlist:
            if item.get('name') == soft_name:
                soft = item
                break

        if not soft:
            available = ', '.join([s.get('name', '') for s in softlist])
            return {'error': f'应用商店中不存在 {soft_name}，可用软件: {available}'}

        if version_id == 0 and soft.get('versions'):
            if soft_name == 'nginx':
                for v in soft['versions']:
                    if v.get('version') == 'openresty':
                        version_id = v.get('id', 0)
                        break
                else:
                    return {'error': 'Nginx仅支持安装OpenResty版本，当前应用商店未提供OpenResty版本'}
            else:
                version_id = soft['versions'][0].get('id', 0)

        version = None
        for v in soft.get('versions', []):
            if v.get('id') == version_id:
                version = v
                break

        if not version:
            return {'error': f'版本ID {version_id} 不存在，可用版本: {json.dumps([v.get("id") for v in soft.get("versions", [])], ensure_ascii=False)}'}

        if soft_name == 'nginx' and version.get('version') != 'openresty':
            openresty_versions = [v for v in soft.get('versions', []) if v.get('version') == 'openresty']
            if openresty_versions:
                return {'error': f'Nginx仅支持安装OpenResty版本，请使用version_id={openresty_versions[0]["id"]}安装OpenResty {openresty_versions[0]["c_version"]}'}
            return {'error': 'Nginx仅支持安装OpenResty版本，当前应用商店未提供OpenResty版本'}

        detail_version = version['c_version'] if soft['name'] in ['python', 'go', 'php'] else None
        s_installed, _, _, _ = Check_Soft_Installed(
            name=soft['name'], is_windows=is_windows, version=detail_version
        )
        if s_installed:
            return {'error': f'{soft_name} {version["c_version"]} 已安装，请勿重复安装'}

        existing_task = SysTaskCenter.objects.filter(
            name__icontains=f'安装{soft_name}', status__in=[0, 1]
        ).exists()
        if existing_task:
            return {'error': f'{soft_name} 正在安装中，请勿重复提交'}

        import datetime
        from apps.system.views.common import executeNextTask

        if detail_version:
            RySoftShop.objects.filter(name=soft['name'], install_version=detail_version).delete()
        else:
            RySoftShop.objects.filter(name=soft['name']).delete()

        taskname = f'安装{soft_name}-{version["c_version"]}'
        job_id = f'{soft_name}-{version["c_version"]}_{int(datetime.datetime.now().timestamp())}'
        version_data = dict(version)
        version_data['job_id'] = job_id
        version_data['log'] = f'{job_id}.log'
        version_data['name'] = soft['name']
        version_data['type'] = soft['type']

        params = {
            'type': 2,
            'name': soft['name'],
            'version': version_data,
            'is_windows': is_windows,
            'call_back': 'apps.system.views.soft_shop.soft_install_callback',
        }

        task = SysTaskCenter.objects.create(
            name=taskname, type=0, log=version_data['log'], status=0,
            func_path='utils.install.install_soft.Ry_Install_Soft',
            params=json.dumps(params),
        )
        executeNextTask()

        return {
            'success': True,
            'message': f'{soft_name}-{version["c_version"]} 安装任务已提交',
            'task_id': task.id,
            'job_id': job_id,
            'note': '安装是异步执行的，任务刚提交时状态为等待中。请勿立即调用panel_shop_task_status查询状态，应告知用户安装已提交并在后台执行。等用户主动询问进度时再查询。',
        }
    except Exception as e:
        return {'error': f'安装失败: {str(e)}'}


@register_tool(id='panel_shop_manage', category='panel', name_cn='应用管理', risk_level='high')
def panel_shop_manage(soft_name: str, action: str, version: str = ''):
    """管理如意面板应用商店中已安装的软件，支持启动、停止、重启、重载、卸载等操作。⚠️启动/停止/重启/卸载为高危操作。

    Args:
        soft_name: 软件名称，如 nginx、mysql、redis、php、python、go
        action: 操作类型，start(启动)、stop(停止)、restart(重启)、reload(重载)、uninstall(卸载)
        version: 软件完整版本号（仅php/python/go需要指定）。必须使用panel_shop_list返回的完整版本号，如 8.2.30、3.12.0、1.22.0。也支持短版本号如 8.2、3.12，会自动匹配已安装的完整版本号
    """
    try:
        is_windows = current_os == 'windows'

        soft_ins = RySoftShop.objects.filter(name=soft_name, installed=True).first()
        if not soft_ins and action != 'uninstall':
            return {'error': f'{soft_name} 未安装，请先使用panel_shop_install安装'}

        def _resolve_version(soft_name, version):
            if soft_name not in ['python', 'go', 'php'] or not version:
                return version
            exact = RySoftShop.objects.filter(name=soft_name, installed=True, install_version=version).first()
            if exact:
                return exact.install_version
            matched = RySoftShop.objects.filter(name=soft_name, installed=True, install_version__startswith=version).first()
            if matched:
                return matched.install_version
            if not version:
                first = RySoftShop.objects.filter(name=soft_name, installed=True).first()
                if first:
                    return first.install_version
            return version

        resolved_version = _resolve_version(soft_name, version)

        if action in ('start', 'stop', 'restart', 'reload'):
            soft_version = resolved_version if soft_name in ['python', 'go', 'php'] else None
            status_map = {'start': 1, 'stop': 2, 'restart': 1, 'reload': 1}
            func_map = {
                'start': Ry_Start_Soft,
                'stop': Ry_Stop_Soft,
                'restart': Ry_Restart_Soft,
                'reload': Ry_Reload_Soft,
            }

            func = func_map.get(action)
            if not func:
                return {'error': f'不支持的操作: {action}'}

            func(name=soft_name, is_windows=is_windows, version=soft_version)

            if soft_name in ['python', 'go', 'php'] and soft_version:
                RySoftShop.objects.filter(name=soft_name, install_version=soft_version).update(
                    status=status_map[action]
                )
            else:
                RySoftShop.objects.filter(name=soft_name).update(status=status_map[action])

            return {
                'success': True,
                'message': f'{soft_name} {action} 操作成功',
            }

        elif action == 'uninstall':
            if soft_name in ['python', 'go', 'php']:
                uninstall_version = resolved_version if resolved_version else None
                if not uninstall_version:
                    soft_ins = RySoftShop.objects.filter(name=soft_name, installed=True).first()
                    if soft_ins:
                        uninstall_version = soft_ins.install_version
                    else:
                        return {'error': f'请指定要卸载的{soft_name}版本'}
                try:
                    Ry_Uninstall_Soft(name=soft_name, is_windows=is_windows, version=uninstall_version)
                except Exception as e:
                    s_installed, _, _, _ = Check_Soft_Installed(
                        name=soft_name, is_windows=is_windows, version=uninstall_version
                    )
                    if not s_installed:
                        RySoftShop.objects.filter(name=soft_name, install_version=uninstall_version).delete()
                        return {'success': True, 'message': f'{soft_name} {uninstall_version} 卸载成功'}
                    return {'error': f'卸载失败: {str(e)}'}
                RySoftShop.objects.filter(name=soft_name, install_version=uninstall_version).delete()
            else:
                try:
                    Ry_Uninstall_Soft(name=soft_name, is_windows=is_windows)
                except Exception as e:
                    s_installed, _, _, _ = Check_Soft_Installed(name=soft_name, is_windows=is_windows)
                    if not s_installed:
                        RySoftShop.objects.filter(name=soft_name).delete()
                        return {'success': True, 'message': f'{soft_name} 卸载成功'}
                    return {'error': f'卸载失败: {str(e)}'}
                RySoftShop.objects.filter(name=soft_name).delete()

            return {'success': True, 'message': f'{soft_name} 卸载成功'}

        else:
            return {'error': f'不支持的操作: {action}，可用: start, stop, restart, reload, uninstall'}
    except Exception as e:
        return {'error': f'操作失败: {str(e)}'}


def _read_log_tail(log_path: str, max_lines: int = 30) -> str:
    if not log_path or not os.path.exists(log_path):
        return ''
    try:
        with open(log_path, 'rb') as f:
            f.seek(0, 2)
            file_size = f.tell()
            if file_size == 0:
                return ''
            block_size = 8192
            lines = []
            pos = file_size
            while pos > 0 and len(lines) < max_lines + 1:
                read_size = min(block_size, pos)
                pos -= read_size
                f.seek(pos)
                block = f.read(read_size)
                block_lines = block.split(b'\n')
                lines = block_lines + lines
            tail_lines = [l.decode('utf-8', errors='replace') for l in lines[-max_lines:]]
            return '\n'.join(tail_lines).strip()
    except Exception:
        return ''


@register_tool(id='panel_shop_task_status', category='panel', name_cn='安装任务状态', risk_level='low')
def panel_shop_task_status(task_id: int = 0):
    """查询如意面板应用商店的安装任务状态。当用户询问软件安装进度或安装失败原因时使用。

    返回结果包含log_tail字段（日志最后30行），可直接查看安装进度和错误信息，无需额外调用read_file读取日志文件。
    如果任务已完成（成功或失败），会直接返回结果，不需要再次查询。
    如果任务失败，请根据log_tail中的错误信息分析原因并告知用户，等待用户决定是否重试，不要自动重新安装。
    如果log_tail中没有明确的错误信息（如"【错误】"、"异常信息如下"等），不要猜测失败原因，如实告知用户"任务已失败，日志中未显示具体错误原因"。

    Args:
        task_id: 任务ID，从panel_shop_install返回的task_id获取。为0时查询所有进行中的任务
    """
    try:
        task_id = int(task_id) if task_id else 0
        if task_id > 0:
            task = SysTaskCenter.objects.filter(id=task_id).first()
            if not task:
                return {'error': f'任务 {task_id} 不存在'}
            status_map = {0: '等待中', 1: '执行中', 2: '失败', 3: '成功'}
            params = task.get_params() if task.params else {}
            name = params.get('name', '') if task.type == 0 else ''
            log_path = os.path.join(os.path.abspath(GetLogsPath()), name, task.log) if name and task.log else ''

            duration = task.duration
            elapsed = 0
            if task.status == 1 and task.exec_at:
                elapsed = int((datetime.datetime.now() - task.exec_at).total_seconds())

            if task.status == 1 and task.job_id:
                try:
                    from django_apscheduler.models import DjangoJob
                    if not DjangoJob.objects.filter(id=task.job_id).exists():
                        task.status = 2
                        task.save(update_fields=['status'])
                except Exception:
                    pass

            result = {
                'task_id': task.id,
                'name': task.name,
                'status': status_map.get(task.status, '未知'),
                'status_code': task.status,
                'duration': duration or elapsed,
                'log_path': log_path,
                'create_at': str(task.create_at),
            }

            if task.status == 1 and log_path:
                result['log_tail'] = _read_log_tail(log_path, 30)
                result['hint'] = '任务仍在执行中，log_tail为日志最后30行，可据此判断进度。如果log_tail为空说明日志尚未写入。请告知用户当前进度，等待用户后续指令。'
            elif task.status == 2:
                log_tail = _read_log_tail(log_path, 50)
                result['log_tail'] = log_tail
                has_end_marker = '---安装任务已结束---' in log_tail if log_tail else False
                if has_end_marker:
                    result['actual_status'] = '成功'
                    result['hint'] = '虽然任务状态显示失败，但日志中包含"安装任务已结束"标记，说明安装实际已成功完成。告知用户安装已成功。'
                else:
                    error_keywords = ['【错误】', '异常信息如下']
                    has_error_in_log = any(kw.lower() in log_tail.lower() for kw in error_keywords) if log_tail else False
                    result['has_error_in_log'] = has_error_in_log
                    if has_error_in_log:
                        result['hint'] = '任务已失败。log_tail中包含错误信息，请提取关键错误信息告知用户。不要使用read_file或execute_command重复读取日志。等待用户决定是否重试，不要自动重新安装。'
                    else:
                        result['hint'] = '任务已失败，但log_tail中没有明确的错误信息。如实告知用户"任务已失败，日志中未显示具体错误原因，可能是安装初始化阶段异常"。不要猜测失败原因（如网络问题等），不要使用read_file或execute_command读取日志。等待用户决定是否重试。'
            elif task.status == 3:
                result['hint'] = '任务已成功完成，告知用户安装结果。'

            return result
        else:
            tasks = SysTaskCenter.objects.filter(status__in=[0, 1]).order_by('-create_at')[:10]
            status_map = {0: '等待中', 1: '执行中', 2: '失败', 3: '成功'}
            result = []
            for task in tasks:
                elapsed = 0
                if task.status == 1 and task.exec_at:
                    elapsed = int((datetime.datetime.now() - task.exec_at).total_seconds())
                result.append({
                    'task_id': task.id,
                    'name': task.name,
                    'status': status_map.get(task.status, '未知'),
                    'status_code': task.status,
                    'duration': task.duration or elapsed,
                    'create_at': str(task.create_at),
                })
            return {
                'running_tasks': result,
                'total': len(result),
            }
    except Exception as e:
        return {'error': f'查询任务状态失败: {str(e)}'}
