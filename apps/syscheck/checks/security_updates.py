import platform
from utils.common import RunCommand
from .base import BaseCheck, register_check, RISK_LEVEL_LOW

_is_windows = platform.system().lower() == 'windows'


@register_check
class CheckSecurityUpdates(BaseCheck):
    check_id = 'security_updates'
    title = '系统安全更新检查'
    description = '检查是否有待安装的安全更新'
    level = RISK_LEVEL_LOW
    category = 'system'

    def run(self):
        if _is_windows:
            result = RunCommand('wmic qfe list brief 2>nul | findstr /v "HotFixID"')
            output = result[0] if result else ''
            lines = [l.strip() for l in output.split('\n') if l.strip()]
            if lines:
                return True, f'已安装 {len(lines)} 个安全更新', [
                    '建议开启 Windows 自动更新',
                    '定期检查 Windows Update 以确保系统安全'
                ]
            return False, '未查询到已安装的安全更新记录', [
                '打开 设置 → 更新和安全 → Windows 更新',
                '点击"检查更新"安装最新安全补丁'
            ]
        output, _ = RunCommand('apt list --upgradable 2>/dev/null | grep -i security | head -20')
        if not output.strip():
            output, _ = RunCommand('yum check-update --security 2>/dev/null | head -20')
        if not output.strip():
            return True, '系统已安装最新安全更新', []
        lines = [l.strip() for l in output.strip().split('\n') if l.strip() and 'Listing' not in l]
        if lines:
            return False, f'发现 {len(lines)} 个待安装的安全更新', [
                '执行 apt update && apt upgrade (Debian/Ubuntu)',
                '执行 yum update --security (CentOS/RHEL)',
                '建议定期检查并安装安全更新'
            ]
        return True, '系统已安装最新安全更新', []
