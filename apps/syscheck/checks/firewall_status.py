import platform
from utils.common import RunCommand
from .base import BaseCheck, register_check, RISK_LEVEL_MEDIUM

_is_windows = platform.system().lower() == 'windows'


@register_check
class CheckFirewallStatus(BaseCheck):
    check_id = 'firewall_status'
    title = '系统防火墙检查'
    description = '检查系统防火墙是否开启'
    level = RISK_LEVEL_MEDIUM
    category = 'network'

    def run(self):
        if _is_windows:
            output, err = RunCommand('netsh advfirewall show allprofiles state')
            if 'ON' in output:
                return True, 'Windows防火墙已开启', []
            return False, 'Windows防火墙未开启', [
                '打开 控制面板 → 系统和安全 → Windows Defender 防火墙',
                '启用所有网络配置文件的防火墙'
            ]
        else:
            for cmd in [
                'systemctl is-active firewalld 2>/dev/null',
                'systemctl is-active ufw 2>/dev/null',
                'ufw status 2>/dev/null | grep -i active',
                'iptables -L -n 2>/dev/null | head -5',
            ]:
                output, _ = RunCommand(cmd)
                if 'active' in output.lower() or 'active' in output.lower():
                    return True, '系统防火墙已开启', []
            return False, '系统防火墙未开启，所有端口暴露在网络上', [
                '建议开启系统防火墙，仅放行必要端口',
                'CentOS: systemctl start firewalld && systemctl enable firewalld',
                'Ubuntu: ufw enable'
            ]
