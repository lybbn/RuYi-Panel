import platform
from utils.common import RunCommand
from .base import BaseCheck, register_check, RISK_LEVEL_MEDIUM

_is_windows = platform.system().lower() == 'windows'


@register_check
class CheckWindowsDefender(BaseCheck):
    check_id = 'windows_defender'
    title = 'Windows Defender状态检查'
    description = '检查Windows Defender实时保护是否开启'
    level = RISK_LEVEL_MEDIUM
    category = 'system'
    platform = 'windows'

    def run(self):
        result = RunCommand('powershell "Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled, AntivirusEnabled" 2>nul')
        output = result[0] if result else ''
        if 'True' in output:
            return True, 'Windows Defender实时保护已开启', []
        if 'False' in output:
            return False, 'Windows Defender实时保护未开启，系统面临恶意软件风险', [
                '打开 设置 → 更新和安全 → Windows安全中心',
                '点击"病毒和威胁防护"→"管理设置"',
                '开启"实时保护"'
            ]
        return True, 'Windows Defender状态无法确定', []
