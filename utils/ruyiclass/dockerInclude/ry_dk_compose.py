#!/usr/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-06-02
# +-------------------------------------------------------------------
# | EditDate: 2025-06-02
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Docker 容器编排类
# ------------------------------
import os
import json
import docker
from utils.common import ReadFile, WriteFile, DeleteDir, RunCommand, GetDataPath, current_os
import logging
logger = logging.getLogger()


class RyDockerCompose:

    docker_url = "unix:///var/run/docker.sock"
    dk_compose_base_path = GetDataPath().replace("\\", "/") + "/dkcompose"
    is_windows = True if current_os == "windows" else False
    compose_bin = "/usr/local/bin/docker-compose"

    def __init__(self):
        if self.is_windows:
            self.docker_url = "npipe:////./pipe/dockerDesktopLinuxEngine"
            self.compose_bin = "docker-compose"
        else:
            if not os.path.exists(self.compose_bin):
                self.compose_bin = "/usr/bin/docker-compose"
        if not os.path.exists(self.dk_compose_base_path):
            os.makedirs(self.dk_compose_base_path)

    def connect(self):
        try:
            return docker.DockerClient(base_url=self.docker_url)
        except:
            return None

    def is_docker_running(self):
        client = self.connect()
        return client is not None

    def get_compose_list(self):
        """
        获取所有 Compose 编排项目列表
        """
        result = []
        stdout, stderr = RunCommand(f"{self.compose_bin} ls --format json")
        compose_info = []
        if stdout:
            try:
                for line in stdout.strip().split('\n'):
                    if line.strip():
                        parsed = json.loads(line)
                        if isinstance(parsed, list):
                            compose_info.extend(parsed)
                        elif isinstance(parsed, dict):
                            compose_info.append(parsed)
            except:
                try:
                    parsed = json.loads(stdout)
                    if isinstance(parsed, list):
                        compose_info = parsed
                    elif isinstance(parsed, dict):
                        compose_info = [parsed]
                except:
                    pass

        client = self.connect()
        if not client:
            return result

        all_containers = []
        try:
            all_containers = client.containers.list(all=True)
        except:
            pass

        for c in compose_info:
            name = c.get('Name', '')
            status = c.get('Status', '')
            config_files = c.get('ConfigFiles', '')

            project_containers = []
            for ct in all_containers:
                labels = ct.attrs.get('Config', {}).get('Labels', {})
                if labels.get('com.docker.compose.project', '').lower() == name.lower():
                    ports_list = []
                    ports = ct.attrs.get('NetworkSettings', {}).get('Ports', {})
                    for container_port, host_bindings in ports.items():
                        if host_bindings:
                            for hb in host_bindings:
                                host_ip = hb.get('HostIp', '0.0.0.0')
                                host_port = hb.get('HostPort', '')
                                if host_port:
                                    ports_list.append(f"{host_ip}:{host_port}->{container_port}")

                    project_containers.append({
                        'name': ct.name,
                        'status': ct.status,
                        'image': ct.attrs.get('Config', {}).get('Image', ''),
                        'ports': ports_list,
                    })

            running_count = sum(1 for pc in project_containers if pc['status'] == 'running')
            compose_status = 'running' if running_count > 0 else 'exited'

            config_path = ''
            if config_files:
                config_path = config_files.split(',')[0].strip()

            env_content = ''
            env_path = ''
            if config_path:
                compose_dir = os.path.dirname(config_path)
                env_path = os.path.join(compose_dir, '.env')
                if os.path.exists(env_path):
                    env_content = ReadFile(env_path) or ''

            yml_content = ''
            if config_path and os.path.exists(config_path):
                yml_content = ReadFile(config_path) or ''

            result.append({
                'name': name,
                'status': compose_status,
                'status_text': status,
                'config_files': config_files,
                'config_path': config_path,
                'container_count': len(project_containers),
                'running_count': running_count,
                'containers': project_containers,
                'yml_content': yml_content,
                'env_content': env_content,
                'env_path': env_path,
            })

        return result

    def get_compose_detail(self, name):
        """
        获取指定 Compose 编排项目详情
        """
        compose_list = self.get_compose_list()
        for c in compose_list:
            if c['name'].lower() == name.lower():
                return True, c
        return False, "未找到该编排项目"

    def create_compose(self, name, yml_content, env_content=''):
        """
        创建 Compose 编排项目
        """
        if not name:
            return False, "编排名称不能为空"
        if not yml_content:
            return False, "编排内容不能为空"

        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return False, "编排名称只能包含字母、数字、下划线和横线"

        compose_list = self.get_compose_list()
        for c in compose_list:
            if c['name'].lower() == name.lower():
                return False, "已存在同名编排项目"

        project_dir = os.path.join(self.dk_compose_base_path, name)
        if os.path.exists(project_dir):
            return False, "项目目录已存在"
        os.makedirs(project_dir)

        compose_file = os.path.join(project_dir, "docker-compose.yml")
        WriteFile(compose_file, yml_content)

        if env_content:
            env_file = os.path.join(project_dir, ".env")
            WriteFile(env_file, env_content)

        isok, msg = self._check_compose_config(compose_file)
        if not isok:
            DeleteDir(project_dir)
            return False, msg

        return True, {"name": name, "config_path": compose_file}

    def _run_compose(self, *args):
        """
        统一执行 compose 命令，自动处理路径空格
        """
        quoted_args = [f'"{a}"' if " " in a or "&" in a else a for a in args]
        return RunCommand(f"{self.compose_bin} {' '.join(quoted_args)}")

    def start_compose(self, config_path):
        """
        启动 Compose 编排
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        isok, msg = self._check_compose_config(config_path)
        if not isok:
            return False, msg
        _, e = self._run_compose("-f", config_path, "start")
        if e:
            if "Started" in e or "Running" in e:
                return True, "启动成功"
            if "create failed" in e:
                _, e2 = self._run_compose("-f", config_path, "up", "-d")
                if e2 and "Started" not in e2 and "Creating" not in e2 and "Created" not in e2:
                    return False, f"启动失败: {e2}"
                return True, "启动成功"
            return False, f"启动失败: {e}"
        return True, "启动成功"

    def stop_compose(self, config_path):
        """
        停止 Compose 编排
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        isok, msg = self._check_compose_config(config_path)
        if not isok:
            return False, msg
        _, e = self._run_compose("-f", config_path, "stop")
        if e:
            if "Stopped" in e:
                return True, "停止成功"
            return False, f"停止失败: {e}"
        return True, "停止成功"

    def restart_compose(self, config_path):
        """
        重启 Compose 编排
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        isok, msg = self._check_compose_config(config_path)
        if not isok:
            return False, msg
        _, e = self._run_compose("-f", config_path, "restart")
        if e and "Restarting" not in e and "Started" not in e:
            return False, f"重启失败: {e}"
        return True, "重启成功"

    def down_compose(self, config_path):
        """
        停止并删除 Compose 编排容器
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        isok, msg = self._check_compose_config(config_path)
        if not isok:
            return False, msg
        _, e = self._run_compose("-f", config_path, "down", "--remove-orphans")
        if e:
            if "Removed" in e or "Stopping" in e or "Stopped" in e:
                return True, "删除成功"
            return False, f"删除失败: {e}"
        return True, "删除成功"

    def remove_compose(self, name, config_path):
        """
        删除 Compose 编排项目（停止容器 + 删除目录）
        """
        if config_path and os.path.exists(config_path):
            self.down_compose(config_path)
            project_dir = os.path.dirname(config_path)
            if os.path.exists(project_dir):
                DeleteDir(project_dir)
        else:
            RunCommand(f"{self.compose_bin} -p \"{name}\" down --volumes --remove-orphans")
            project_dir = os.path.join(self.dk_compose_base_path, name)
            if os.path.exists(project_dir):
                DeleteDir(project_dir)
        return True, "删除成功"

    def up_compose(self, config_path):
        """
        创建并启动 Compose 编排（up -d）
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        isok, msg = self._check_compose_config(config_path)
        if not isok:
            return False, msg
        _, e = self._run_compose("-f", config_path, "up", "-d", "--remove-orphans")
        if e:
            if "Started" in e or "Creating" in e or "Created" in e:
                return True, "启动成功"
            if "Pulling" in e or "Downloading" in e:
                return True, "正在拉取镜像并启动..."
            return False, f"启动失败: {e}"
        return True, "启动成功"

    def rebuild_compose(self, config_path):
        """
        重建 Compose 编排（先 down 再 up）
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        self.down_compose(config_path)
        return self.up_compose(config_path)

    def pull_compose(self, config_path):
        """
        拉取 Compose 编排的最新镜像
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        isok, msg = self._check_compose_config(config_path)
        if not isok:
            return False, msg
        _, e = self._run_compose("-f", config_path, "pull")
        if e and "Pulling" not in e and "Downloaded" not in e and "Image is up to date" not in e and "Pulled" not in e:
            return False, f"拉取镜像失败: {e}"
        return True, "镜像拉取成功"

    def update_compose_yml(self, config_path, yml_content):
        """
        更新 Compose 编排的 yml 配置文件
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        if not yml_content:
            return False, "配置内容不能为空"
        WriteFile(config_path, yml_content)
        isok, msg = self._check_compose_config(config_path)
        if not isok:
            return False, msg
        return True, "配置更新成功"

    def update_compose_env(self, env_path, env_content):
        """
        更新 Compose 编排的 .env 文件
        """
        if not env_path:
            return False, "环境变量文件路径不能为空"
        if env_content:
            WriteFile(env_path, env_content)
        else:
            if os.path.exists(env_path):
                os.remove(env_path)
        return True, "环境变量更新成功"

    def get_compose_logs(self, config_path, tail=200):
        """
        获取 Compose 编排日志
        """
        if not config_path or not os.path.exists(config_path):
            return False, "配置文件不存在"
        o, e = self._run_compose("-f", config_path, "logs", f"--tail={tail}")
        return True, o or e or ""

    def _check_compose_config(self, filename):
        """
        验证配置文件
        """
        o, e = self._run_compose("-f", filename, "config")
        if e and "setlocale: LC_ALL: cannot change locale" not in e:
            return False, f"配置文件检测失败: {e}"
        return True, "ok"
