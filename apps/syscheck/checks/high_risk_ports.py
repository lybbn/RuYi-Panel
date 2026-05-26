import socket
from .base import BaseCheck, register_check, RISK_LEVEL_HIGH

HIGH_RISK_PORTS = {
    3306: 'MySQL',
    6379: 'Redis',
    27017: 'MongoDB',
    9200: 'Elasticsearch',
    11211: 'Memcached',
    2375: 'Docker API',
    2376: 'Docker API TLS',
    5432: 'PostgreSQL',
    1521: 'Oracle',
    1433: 'MSSQL',
    9090: 'Prometheus',
    8500: 'Consul',
    2181: 'ZooKeeper',
    8848: 'Nacos',
}


def _check_port(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False


@register_check
class CheckHighRiskPorts(BaseCheck):
    check_id = 'high_risk_ports'
    title = '高危端口暴露检查'
    description = '检查数据库、缓存等高危服务端口是否暴露'
    level = RISK_LEVEL_HIGH
    category = 'network'

    def run(self):
        exposed = []
        for port, service in HIGH_RISK_PORTS.items():
            if _check_port(port):
                exposed.append(f'{port}({service})')
        if exposed:
            return False, f'发现 {len(exposed)} 个高危端口正在监听: {", ".join(exposed)}', [
                '确保高危端口仅监听 127.0.0.1',
                '通过防火墙禁止外网访问高危端口',
                'Redis/MongoDB等务必设置访问密码'
            ]
        return True, '未发现高危端口对外暴露', []
