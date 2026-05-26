import platform
from utils.common import RunCommand
from .base import BaseCheck, register_check, RISK_LEVEL_HIGH

_is_windows = platform.system().lower() == 'windows'


@register_check
class CheckEmptyPasswd(BaseCheck):
    check_id = 'empty_passwd'
    title = '空密码用户检查'
    description = '检查系统是否存在空密码用户'
    level = RISK_LEVEL_HIGH
    category = 'system'

    def run(self):
        if _is_windows:
            result = RunCommand('net user 2>nul')
            output = result[0] if result else ''
            if not output.strip():
                return True, '无法检查空密码用户', []
            users = []
            for line in output.split('\n'):
                stripped = line.strip()
                if not stripped or stripped.startswith('\\') or stripped.startswith('-') or stripped.startswith('命令')\
                        or stripped.startswith('帐户') or stripped.startswith('User'):
                    continue
                for user in stripped.split():
                    if user and user != '----------':
                        users.append(user)
            return True, 'Windows系统不适用空密码直接检查（建议检查用户密码策略）', [
                '使用 net user <用户名> 检查各用户密码状态',
                '通过 控制面板 → 管理工具 → 本地安全策略 设置密码策略'
            ]
        output, err = RunCommand("awk -F: 'NF && $2 == \"\" {print $1}' /etc/shadow")
        if err:
            return True, '无法检查空密码用户', []
        users = [u.strip() for u in output.strip().split('\n') if u.strip()]
        if users:
            return False, f'发现空密码用户: {", ".join(users)}', [
                '使用 passwd <用户名> 为用户设置密码',
                '或使用 passwd -l <用户名> 锁定不需要的用户'
            ]
        return True, '未发现空密码用户', []
