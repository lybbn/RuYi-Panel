import platform
from utils.common import RunCommand
from .base import BaseCheck, register_check, RISK_LEVEL_MEDIUM

_is_windows = platform.system().lower() == 'windows'


@register_check
class CheckDockerExpose(BaseCheck):
    check_id = 'docker_expose'
    title = 'Docker安全检查'
    description = '检查Docker容器端口是否对外暴露'
    level = RISK_LEVEL_MEDIUM
    category = 'docker'

    def run(self):
        if _is_windows:
            result = RunCommand('docker ps --format "{{.Names}}:{{.Ports}}" 2>nul')
            output = result[0] if result else ''
            if not output.strip():
                return True, 'Docker Desktop未运行或无Windows容器', []
        else:
            output, _ = RunCommand('docker ps --format "{{.Names}}:{{.Ports}}" 2>/dev/null')
            if not output.strip():
                return True, 'Docker未运行或无容器', []
        warnings = []
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            if '0.0.0.0:' in line:
                name = line.split(':')[0] if ':' in line else line
                warnings.append(name)
        if warnings:
            return False, f'发现 {len(warnings)} 个容器端口对外暴露: {", ".join(warnings)}', [
                '检查容器端口映射，避免绑定 0.0.0.0',
                '使用 127.0.0.1:port:port 仅允许本机访问',
                '通过反向代理统一管理外部访问'
            ]
        return True, 'Docker容器端口配置正常', []
