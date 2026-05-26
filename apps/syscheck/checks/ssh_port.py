import re
from utils.common import ReadFile
from .base import BaseCheck, register_check, RISK_LEVEL_MEDIUM


@register_check
class CheckSSHPort(BaseCheck):
    check_id = 'ssh_port'
    title = 'SSH默认端口检查'
    description = '检查SSH是否使用默认22端口'
    level = RISK_LEVEL_MEDIUM
    category = 'ssh'
    platform = 'linux'

    def run(self):
        config = ReadFile('/etc/ssh/sshd_config')
        if not config:
            return True, '无法读取SSH配置文件', []
        match = re.search(r'(?m)^\s*Port\s+(\d+)', config)
        port = int(match.group(1)) if match else 22
        if port == 22:
            return False, 'SSH使用默认22端口，易受暴力破解攻击', [
                '编辑 /etc/ssh/sshd_config',
                '修改 Port 为非标准端口（如2222）',
                '执行 systemctl restart sshd 重启SSH服务',
                '确保新端口已在防火墙中放行'
            ]
        return True, f'SSH使用非默认端口 {port}', []
