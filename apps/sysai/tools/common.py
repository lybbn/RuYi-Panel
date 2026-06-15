"""
如意面板AI助手 - 公共工具模块
"""
import socket
from utils.common import RunCommand, is_service_running, check_is_port


def run_cmd(cmd: str, timeout: int = 15) -> dict:
    """
    统一的命令执行函数
    返回: {'output': str} 或 {'error': str}
    """
    try:
        stdout, stderr = RunCommand(cmd, timeout=timeout)
        if stderr:
            return {'error': stderr.strip()[:2000]}
        return {'output': stdout.strip()[:15000]}
    except Exception as e:
        return {'error': str(e)}


def check_port_occupied(port: int) -> bool:
    """
    检查端口是否被占用
    复用 utils/common.py 的 is_service_running
    """
    try:
        return is_service_running(port=port)
    except Exception:
        # 降级到 socket 检测
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(('127.0.0.1', port)) == 0
        except Exception:
            return False


def check_port_valid(port) -> bool:
    """
    检查端口是否有效
    复用 utils/common.py 的 check_is_port
    """
    return check_is_port(port)
