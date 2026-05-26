import platform
from apps.sysai.tools.base import register_tool
from utils.common import RunCommand
from utils.server.system import system


def _run_cmd(cmd: str, timeout: int = 15) -> dict:
    try:
        stdout, stderr = RunCommand(cmd, timeout=timeout)
        if stderr:
            return {'error': stderr.strip()[:2000]}
        return {'output': stdout.strip()[:15000]}
    except Exception as e:
        return {'error': str(e)}


@register_tool(id='get_firewall_status', category='security', name_cn='防火墙状态', risk_level='low')
def get_firewall_status():
    """获取防火墙状态和规则列表。当用户需要检查服务器防火墙配置时使用。"""
    try:
        is_running = system.GetFirewallStatus()
        rules = system.GetFirewallRules()
        info = system.GetFirewallInfo()
        return {
            'firewall_running': is_running,
            'rules': rules,
            'info': info,
        }
    except Exception as e:
        return {'error': f'获取防火墙状态失败: {str(e)}'}


@register_tool(id='get_ssh_config', category='security', name_cn='SSH配置', risk_level='low')
def get_ssh_config():
    """获取SSH服务配置信息，包括端口、认证方式、root登录等安全设置。当用户需要检查SSH安全配置时使用。"""
    is_windows = platform.system().lower() == 'windows'

    if is_windows:
        result = _run_cmd('where sshd 2>nul')
        if 'error' in result or not result.get('output', '').strip():
            return {'message': 'Windows 系统未安装 OpenSSH Server'}

        config_result = _run_cmd('type "%ProgramData%\\ssh\\sshd_config" 2>nul')
        if 'error' in config_result:
            return {'error': '无法读取 SSH 配置文件'}

        config_content = config_result.get('output', '')
        config_path = '%ProgramData%\\ssh\\sshd_config'
    else:
        sshd_config_path = '/etc/ssh/sshd_config'
        result = _run_cmd(f'cat {sshd_config_path} 2>/dev/null')

        if 'error' in result:
            return {'error': '无法读取SSH配置文件'}

        config_content = result.get('output', '')
        config_path = sshd_config_path

    config_items = {}
    for line in config_content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if ' ' in stripped:
            key, value = stripped.split(' ', 1)
            config_items[key] = value

    return {
        'config_path': config_path,
        'port': config_items.get('Port', '22'),
        'permit_root_login': config_items.get('PermitRootLogin', 'yes'),
        'password_authentication': config_items.get('PasswordAuthentication', 'yes'),
        'pubkey_authentication': config_items.get('PubkeyAuthentication', 'yes'),
        'max_auth_tries': config_items.get('MaxAuthTries', '6'),
        'config_items': config_items,
    }


@register_tool(id='get_login_history', category='security', name_cn='登录历史', risk_level='low')
def get_login_history(lines: int = 20):
    """获取系统登录历史记录，包括成功和失败的登录尝试。当用户需要检查服务器安全审计时使用。

    Args:
        lines: 返回的记录行数，默认20
    """
    is_windows = platform.system().lower() == 'windows'

    if is_windows:
        success_result = _run_cmd(
            f'wevtutil qe Security /c:{lines} /rd:true /f:text /q:"*[System[EventID=4624]]" 2>nul'
        )
        fail_result = _run_cmd(
            f'wevtutil qe Security /c:{lines} /rd:true /f:text /q:"*[System[EventID=4625]]" 2>nul'
        )

        if 'error' in success_result and 'error' in fail_result:
            return {'message': '无法获取 Windows 登录历史，可能需要管理员权限'}

        return {
            'successful_logins': success_result.get('output', '无法获取成功登录记录'),
            'failed_logins': fail_result.get('output', '无法获取失败登录记录') if 'error' not in fail_result else '无法获取失败登录记录',
        }
    else:
        last_result = _run_cmd(f'last -n {lines} 2>/dev/null')
        lastb_result = _run_cmd(f'lastb -n {lines} 2>/dev/null')

        return {
            'successful_logins': last_result.get('output', ''),
            'failed_logins': lastb_result.get('output', '') if 'error' not in lastb_result else '无法获取失败登录记录',
        }


@register_tool(id='get_open_ports', category='security', name_cn='开放端口', risk_level='low')
def get_open_ports():
    """获取服务器上开放的端口和对应的进程信息。当用户需要检查服务器端口安全时使用。"""
    is_windows = platform.system().lower() == 'windows'

    if is_windows:
        result = _run_cmd('netstat -ano | findstr LISTENING')
    else:
        result = _run_cmd('ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null')

    if 'error' in result:
        return result

    ports = []
    for line in result.get('output', '').split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('State') or stripped.startswith('Local') or stripped.startswith('Proto'):
            continue
        parts = stripped.split()
        if is_windows:
            if len(parts) >= 2:
                local_addr = parts[1]
                port = local_addr.split(':')[-1] if ':' in local_addr else ''
                pid = parts[-1] if len(parts) > 4 else ''
                ports.append({
                    'local_address': local_addr,
                    'port': port,
                    'state': 'LISTENING',
                    'process': f'PID:{pid}',
                })
        else:
            if len(parts) >= 4:
                local_addr = parts[3] if len(parts) > 3 else ''
                port = local_addr.split(':')[-1] if ':' in local_addr else ''
                process = parts[-1] if len(parts) > 4 else ''
                ports.append({
                    'local_address': local_addr,
                    'port': port,
                    'state': parts[0] if parts[0] in ('LISTEN', 'ESTAB') else parts[1] if len(parts) > 1 else '',
                    'process': process,
                })

    return {
        'ports': ports,
        'total': len(ports),
    }


@register_tool(id='get_security_updates', category='security', name_cn='安全更新', risk_level='low')
def get_security_updates():
    """检查系统中可用的安全更新。当用户需要检查服务器是否有安全漏洞需要修补时使用。"""
    is_windows = platform.system().lower() == 'windows'

    if is_windows:
        result = _run_cmd('wmic qfe list brief 2>nul | more +1')
        if 'error' in result:
            return {'message': '无法检查 Windows 更新，可能需要管理员权限'}
        return {
            'updates': result.get('output', ''),
            'note': '以上为已安装的更新列表，建议定期检查 Windows Update',
        }
    else:
        result = _run_cmd('apt list --upgradable 2>/dev/null | head -n 30')
        if 'error' in result:
            result = _run_cmd('yum check-update --security 2>/dev/null | head -n 30')
        if 'error' in result:
            return {'message': '无法检查安全更新，可能不是Debian/RedHat系系统'}
        return {
            'updates': result.get('output', ''),
            'note': '建议定期更新系统以修复安全漏洞',
        }


@register_tool(id='manage_firewall_rule', category='security', name_cn='防火墙规则管理', risk_level='high')
def manage_firewall_rule(action: str, port: str = '', protocol: str = 'tcp', source: str = ''):
    """管理防火墙规则，支持添加和删除规则。⚠️此为高危操作，错误的规则可能导致无法远程连接服务器。

    Args:
        action: 操作类型，allow(允许)、deny(拒绝)、delete(删除规则)
        port: 端口号或服务名，如 80、443、ssh
        protocol: 协议类型，tcp 或 udp，默认tcp
        source: 来源IP，为空则允许所有
    """
    valid_actions = ['allow', 'deny', 'delete']
    if action not in valid_actions:
        return {'error': f'无效操作: {action}，可用操作: {", ".join(valid_actions)}'}

    if not port:
        return {'error': '必须指定端口号'}

    is_windows = platform.system().lower() == 'windows'

    try:
        if is_windows:
            if action == 'allow':
                isok = system.AddFirewallRule({
                    'port': port,
                    'protocol': protocol,
                    'address': source or 'any',
                })
                return {
                    'action': action,
                    'port': port,
                    'protocol': protocol,
                    'source': source or 'any',
                    'success': isok,
                    'message': '规则添加成功' if isok else '规则添加失败',
                }
            elif action == 'delete':
                isok = system.DelFirewallRule({
                    'port': port,
                    'protocol': protocol,
                })
                return {
                    'action': action,
                    'port': port,
                    'protocol': protocol,
                    'success': isok,
                    'message': '规则删除成功' if isok else '规则删除失败',
                }
            else:
                return {'error': 'Windows 防火墙 deny 操作请使用 SetFirewallRuleAction'}
        else:
            source_arg = f'from {source}' if source else ''
            cmd = f'ufw {action} {source_arg} {port}/{protocol} 2>&1'
            result = _run_cmd(cmd)
            if 'error' in result:
                iptables_cmd = f'iptables -{"A" if action == "allow" else "D"} INPUT -p {protocol} --dport {port} -j {"ACCEPT" if action == "allow" else "DROP"} 2>&1'
                result = _run_cmd(iptables_cmd)

            return {
                'action': action,
                'port': port,
                'protocol': protocol,
                'source': source or 'any',
                'result': result.get('output', result.get('error', '')),
            }
    except Exception as e:
        return {'error': f'防火墙规则操作失败: {str(e)}'}


@register_tool(id='security_scan', category='security', name_cn='安全风险扫描', risk_level='low')
def security_scan():
    """启动服务器安全风险扫描。检查SSH安全、防火墙、端口暴露、密码安全、Docker配置等多个维度，返回安全评分和风险项。当用户需要检查服务器安全状况时使用。"""
    try:
        from apps.syscheck.scanner import run_scan_async, get_result, get_progress
        started = run_scan_async()
        if not started:
            progress = get_progress()
            if progress.get('status') == 'scanning':
                return {'message': '安全扫描正在进行中，请稍后查询结果', 'progress': progress}
            else:
                result = get_result()
                return {'message': '获取最近一次扫描结果', 'result': result}
        import time
        for _ in range(30):
            time.sleep(1)
            progress = get_progress()
            if progress.get('status') in ('done', 'error'):
                break
        result = get_result()
        return {
            'message': '安全扫描完成',
            'score': result.get('score', 0),
            'risk_count': len(result.get('risk', [])),
            'risks': result.get('risk', []),
            'security_count': len(result.get('security', [])),
            'ignore_count': len(result.get('ignore', [])),
            'check_time': result.get('check_time', ''),
        }
    except Exception as e:
        return {'error': f'安全扫描失败: {str(e)}'}


@register_tool(id='security_scan_result', category='security', name_cn='安全扫描结果', risk_level='low')
def security_scan_result():
    """获取最近一次安全风险扫描的结果。返回安全评分、风险项列表、安全项列表。当用户询问服务器安全评分、安全检查结果时使用。"""
    try:
        from apps.syscheck.scanner import get_result, get_summary
        result = get_result()
        summary = get_summary()
        if not result.get('check_time'):
            return {'message': '尚未进行过安全扫描，请先执行 security_scan'}
        return {
            'score': summary.get('score', 0),
            'risk_count': summary.get('risk_count', 0),
            'security_count': summary.get('security_count', 0),
            'ignore_count': summary.get('ignore_count', 0),
            'check_time': result.get('check_time', ''),
            'risks': [
                {
                    'title': r.get('title', ''),
                    'msg': r.get('msg', ''),
                    'level': r.get('level', 0),
                    'level_label': r.get('level_label', ''),
                    'tips': r.get('tips', []),
                }
                for r in result.get('risk', [])
            ],
            'security': [
                {
                    'title': s.get('title', ''),
                    'msg': s.get('msg', ''),
                }
                for s in result.get('security', [])
            ],
        }
    except Exception as e:
        return {'error': f'获取扫描结果失败: {str(e)}'}