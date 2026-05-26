import re
from utils.common import ReadFile
from .base import BaseCheck, register_check, RISK_LEVEL_HIGH


@register_check
class CheckSSHRootLogin(BaseCheck):
    check_id = 'ssh_root_login'
    title = 'SSH root登录检查'
    description = '检查SSH是否允许root用户直接登录'
    level = RISK_LEVEL_HIGH
    category = 'ssh'
    platform = 'linux'

    def run(self):
        config = ReadFile('/etc/ssh/sshd_config')
        if not config:
            return True, '无法读取SSH配置文件', ['检查 /etc/ssh/sshd_config 文件权限']
        if re.search(r'(?m)^\s*PermitRootLogin\s+yes', config):
            return False, 'SSH允许root直接登录，存在安全风险', [
                '编辑 /etc/ssh/sshd_config',
                '设置 PermitRootLogin no',
                '执行 systemctl restart sshd 重启SSH服务'
            ]
        return True, 'SSH已禁止root直接登录', []
