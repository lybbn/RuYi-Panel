import platform
from utils.common import RunCommand
from .base import BaseCheck, register_check, RISK_LEVEL_MEDIUM

_is_windows = platform.system().lower() == 'windows'


@register_check
class CheckWindowsRDP(BaseCheck):
    check_id = 'windows_rdp'
    title = 'Windows RDP安全检查'
    description = '检查远程桌面是否启用网络级认证(NLA)'
    level = RISK_LEVEL_MEDIUM
    category = 'network'
    platform = 'windows'

    def run(self):
        result = RunCommand('reg query "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp" /v UserAuthentication 2>nul')
        output = result[0] if result else ''
        if 'UserAuthentication' in output:
            for line in output.split('\n'):
                if 'UserAuthentication' in line:
                    val = line.strip().split()[-1]
                    if val == '0x1':
                        return True, '远程桌面已启用网络级认证(NLA)', []
                    return False, '远程桌面未启用网络级认证(NLA)，存在暴力破解风险', [
                        '打开 系统属性 → 远程 → 远程桌面',
                        '勾选"仅允许运行使用网络级别身份验证的远程桌面的计算机连接"',
                        '或执行: reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp" /v UserAuthentication /t REG_DWORD /d 1 /f'
                    ]
        return True, '远程桌面服务未启用或无法检查', []
