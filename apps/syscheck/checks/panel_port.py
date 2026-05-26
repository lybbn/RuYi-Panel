import os
from django.conf import settings
from .base import BaseCheck, register_check, RISK_LEVEL_MEDIUM


@register_check
class CheckPanelPort(BaseCheck):
    check_id = 'panel_port'
    title = '面板端口设置检查'
    description = '检查如意面板是否使用了易被扫描的默认端口'
    level = RISK_LEVEL_MEDIUM
    category = 'panel'

    def run(self):
        port_file = settings.RUYI_PORT_FILE
        port = 6789
        if os.path.exists(port_file):
            try:
                with open(port_file, 'r') as f:
                    port = int(f.read().strip())
            except:
                pass
        if port == 6789:
            return False, '面板使用默认端口 6789，建议修改为自定义端口以防扫描', [
                '进入 面板设置 → 面板端口，修改为非标准端口（如 30000-40000 范围）',
                '修改后重启如意面板生效'
            ]
        if port in {80, 443, 888, 8888, 9000}:
            return False, f'面板使用常用端口 {port}，建议避免使用常见端口', [
                '进入 面板设置 → 面板端口，修改为高位端口',
                '修改后重启如意面板生效'
            ]
        return True, f'面板端口 {port} 安全', []
