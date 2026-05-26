import re
from utils.common import ReadFile
from .base import BaseCheck, register_check, RISK_LEVEL_MEDIUM


@register_check
class CheckSSHMaxAuthTries(BaseCheck):
    check_id = 'ssh_max_auth'
    title = 'SSH最大重试次数检查'
    description = '检查SSH最大认证重试次数是否过高'
    level = RISK_LEVEL_MEDIUM
    category = 'ssh'
    platform = 'linux'

    def run(self):
        config = ReadFile('/etc/ssh/sshd_config')
        if not config:
            return True, '无法读取SSH配置文件', []
        match = re.search(r'(?m)^\s*MaxAuthTries\s+(\d+)', config)
        max_tries = int(match.group(1)) if match else 6
        if max_tries > 5:
            return False, f'SSH最大认证重试次数为 {max_tries}，建议降低', [
                '编辑 /etc/ssh/sshd_config',
                '设置 MaxAuthTries 3',
                '执行 systemctl restart sshd 重启SSH服务'
            ]
        return True, f'SSH最大认证重试次数为 {max_tries}，配置合理', []
