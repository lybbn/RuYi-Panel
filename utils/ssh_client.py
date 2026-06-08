# -*- coding: utf-8 -*-

"""
@Remark: 统一的SSH客户端和API请求头封装
@author lybbn<2026-06-03>
"""
import json
import paramiko


class RuyiSSHClient:
    """统一的SSH客户端封装，支持上下文管理器复用连接"""

    def __init__(self, node, timeout=10):
        self.node = node
        self.timeout = timeout
        self._client = None

    def connect(self):
        ssh_conf = self.node.ssh_conf
        if not ssh_conf:
            raise Exception("该远程节点尚未配置SSH认证信息，请先在节点管理中配置SSH登录凭证")
        if isinstance(ssh_conf, str):
            try:
                ssh_conf = json.loads(ssh_conf)
            except Exception:
                raise Exception("该远程节点的SSH配置信息格式错误，请重新配置")

        host = self.node.server_ip
        port = int(ssh_conf.get("port", 22))
        username = ssh_conf.get("username", "root")
        password = ssh_conf.get("password", "")
        auth_type = ssh_conf.get("auth_type", "password")

        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": self.timeout,
        }
        if auth_type == "password":
            if not password:
                raise Exception("该远程节点SSH密码未设置，请先在节点管理中配置SSH密码")
            connect_kwargs["password"] = password
        elif auth_type == "key":
            private_key = ssh_conf.get("private_key", "")
            if not private_key:
                raise Exception("该远程节点SSH私钥未设置，请先在节点管理中配置SSH私钥")
            pkey = paramiko.RSAKey.from_private_key_string(private_key)
            connect_kwargs["pkey"] = pkey
        else:
            if password:
                connect_kwargs["password"] = password

        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(**connect_kwargs)
        return self._client

    def exec_command(self, command, timeout=30):
        if not self._client:
            self.connect()
        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        err = stderr.read().decode('utf-8', errors='ignore').strip()
        return out, err

    def open_sftp(self):
        if not self._client:
            self.connect()
        return self._client.open_sftp()

    def close(self):
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


def build_api_headers(node):
    """统一的API请求头构建"""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Ruyi-Node-Client/1.0",
    }
    if node.api_key:
        headers["RY-API-KEY"] = node.api_key
    return headers
