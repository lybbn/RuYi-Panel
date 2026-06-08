# -*- coding: utf-8 -*-

"""
@Remark: MySQL主从复制数据同步服务 - 支持步骤追踪和进度推送
@author lybbn<2026-06-03>
"""
import os
import time
import json
import tempfile
import subprocess
import platform

from utils.common import format_size


def _is_windows():
    return platform.system().lower() == 'windows'


def auto_allow_firewall_port(ip, port, protocol='tcp'):
    """自动在防火墙中放行指定端口（跨平台）"""
    try:
        from utils.server.system import system
        is_win = _is_windows()
        if is_win:
            rule_name = f"Ruyi-MySQL-Repl-{port}"
            system.AddFirewallRule(param={
                'name': rule_name,
                'protocol': protocol.upper(),
                'localport': str(port),
                'handle': 'allow',
                'direction': 'in',
            })
        else:
            system.AddFirewallRule(param={
                'protocol': protocol,
                'localport': str(port),
                'address': '',
                'handle': 'accept',
            })
        return True
    except Exception:
        return False


class MysqlSyncService:
    """MySQL主从复制数据同步服务"""

    # 同步步骤定义
    STEPS = [
        {"key": "check_connection", "name": "验证数据库连接"},
        {"key": "create_repl_user", "name": "创建复制用户"},
        {"key": "lock_tables", "name": "锁定主库表"},
        {"key": "export_data", "name": "导出主库数据"},
        {"key": "transfer_dump", "name": "传输数据文件"},
        {"key": "import_data", "name": "导入从库数据"},
        {"key": "config_replication", "name": "配置主从关系"},
        {"key": "unlock_tables", "name": "解锁主库表"},
        {"key": "verify", "name": "验证复制状态"},
    ]

    def __init__(self, rep):
        self.rep = rep
        self.dump_file = None
        self._log_lines = []

    def log(self, msg):
        """记录日志并更新模型"""
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        self._log_lines.append(line)
        self.rep.config_log = "\n".join(self._log_lines)
        self.rep.save(update_fields=["config_log"])

    def set_step(self, step_index):
        """设置当前步骤"""
        self.rep.current_step = step_index
        self.rep.save(update_fields=["current_step"])
        step_name = self.STEPS[step_index]["name"] if step_index < len(self.STEPS) else "未知"
        self.log(f"▶ 步骤 {step_index + 1}/{len(self.STEPS)}: {step_name}")
        self._notify_progress(step_name, round((step_index + 1) / len(self.STEPS) * 100))

    def _notify_progress(self, message, progress):
        """推送进度到Channel Layer"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    "loadbalance",
                    {
                        "type": "config_progress",
                        "data": {
                            "message": message,
                            "progress": progress,
                            "rep_id": self.rep.id,
                            "step": self.rep.current_step,
                        }
                    }
                )
        except Exception:
            pass

    def execute(self, sync_mode="auto"):
        """
        执行完整的主从复制配置和数据同步
        sync_mode:
          - auto: 自动完成所有步骤（含数据同步）
          - config_only: 仅配置主从关系，不同步数据
          - manual: 仅生成命令，不执行
        """
        try:
            self.rep.config_status = "configuring"
            self.rep.current_step = 0
            self.rep.config_log = ""
            self.rep.error_msg = ""
            self.rep.save(update_fields=["config_status", "current_step", "config_log", "error_msg"])

            if sync_mode == "config_only":
                self._step_check_connection()
                self._step_create_repl_user()
                self._step_config_replication()
                self._step_verify()
            elif sync_mode == "manual":
                self._step_check_connection()
                self._generate_manual_commands()
            else:
                # auto模式：完整执行所有步骤
                self._step_check_connection()
                self._step_create_repl_user()
                self._step_lock_tables()
                self._step_export_data()
                self._step_transfer_dump()
                self._step_import_data()
                self._step_config_replication()
                self._step_unlock_tables()
                self._step_verify()

            self.rep.config_status = "done"
            self.rep.run_status = "running"
            self.rep.error_msg = ""
            self.rep.save(update_fields=["config_status", "run_status", "error_msg"])
            self.log("✅ 主从复制配置完成")

        except Exception as e:
            self.rep.config_status = "failed"
            self.rep.error_msg = str(e)
            self.rep.save(update_fields=["config_status", "error_msg"])
            self.log(f"❌ 配置失败: {str(e)}")
            # 尝试解锁表
            try:
                self._unlock_tables_safe()
            except Exception:
                pass

    def _step_check_connection(self):
        """步骤1: 验证数据库连接"""
        self.set_step(0)
        from apps.sysnode.views.replication_views import _mysql_exec_sql

        _, err = _mysql_exec_sql(
            self.rep.master_ip, self.rep.master_port,
            self.rep.root_user, self.rep.root_pass, "SELECT 1"
        )
        if err:
            # 尝试自动放行防火墙端口后重试
            self.log(f"主库连接失败，尝试自动放行防火墙端口 {self.rep.master_port}...")
            if auto_allow_firewall_port(self.rep.master_ip, self.rep.master_port):
                import time as _t
                _t.sleep(2)
                _, err = _mysql_exec_sql(
                    self.rep.master_ip, self.rep.master_port,
                    self.rep.root_user, self.rep.root_pass, "SELECT 1"
                )
                if not err:
                    self.log(f"防火墙已自动放行端口 {self.rep.master_port}，主库连接成功")
        if err:
            raise Exception(f"主库连接失败: {err}")
        self.log("主库连接成功")

        _, err = _mysql_exec_sql(
            self.rep.slave_ip, self.rep.slave_port,
            self.rep.root_user, self.rep.root_pass, "SELECT 1"
        )
        if err:
            self.log(f"从库连接失败，尝试自动放行防火墙端口 {self.rep.slave_port}...")
            if auto_allow_firewall_port(self.rep.slave_ip, self.rep.slave_port):
                import time as _t
                _t.sleep(2)
                _, err = _mysql_exec_sql(
                    self.rep.slave_ip, self.rep.slave_port,
                    self.rep.root_user, self.rep.root_pass, "SELECT 1"
                )
                if not err:
                    self.log(f"防火墙已自动放行端口 {self.rep.slave_port}，从库连接成功")
        if err:
            raise Exception(f"从库连接失败: {err}")
        self.log("从库连接成功")

    def _step_create_repl_user(self):
        """步骤2: 创建复制用户"""
        self.set_step(1)
        from apps.sysnode.views.replication_views import _mysql_exec_sql

        sql = f"""
        CREATE USER IF NOT EXISTS '{self.rep.db_user}'@'%' IDENTIFIED BY '{self.rep.db_pass}';
        GRANT REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO '{self.rep.db_user}'@'%';
        FLUSH PRIVILEGES;
        """
        _, err = _mysql_exec_sql(
            self.rep.master_ip, self.rep.master_port,
            self.rep.root_user, self.rep.root_pass, sql
        )
        if err and "already exists" not in str(err):
            raise Exception(f"创建复制用户失败: {err}")
        self.log(f"复制用户 {self.rep.db_user} 已就绪")

        # 半同步插件
        if self.rep.replicate_mode == "semi_sync":
            master_plugin = """
            INSTALL PLUGIN IF NOT EXISTS rpl_semi_sync_master SONAME 'semisync_master.so';
            SET GLOBAL rpl_semi_sync_master_enabled = 1;
            SET GLOBAL rpl_semi_sync_master_timeout = 3000;
            """
            _mysql_exec_sql(
                self.rep.master_ip, self.rep.master_port,
                self.rep.root_user, self.rep.root_pass, master_plugin
            )
            slave_plugin = """
            INSTALL PLUGIN IF NOT EXISTS rpl_semi_sync_slave SONAME 'semisync_slave.so';
            SET GLOBAL rpl_semi_sync_slave_enabled = 1;
            """
            _mysql_exec_sql(
                self.rep.slave_ip, self.rep.slave_port,
                self.rep.root_user, self.rep.root_pass, slave_plugin
            )
            self.log("半同步插件已安装")

    def _step_lock_tables(self):
        """步骤3: 锁定主库表（导出前）"""
        self.set_step(2)
        from apps.sysnode.views.replication_views import _mysql_exec_sql

        _mysql_exec_sql(
            self.rep.master_ip, self.rep.master_port,
            self.rep.root_user, self.rep.root_pass,
            "FLUSH TABLES WITH READ LOCK"
        )
        self.log("主库表已锁定")

    def _step_export_data(self):
        """步骤4: 导出主库数据"""
        self.set_step(3)
        try:
            from utils.install.mysql import get_mysql_path_info
            soft_paths = get_mysql_path_info()
        except Exception:
            raise Exception("无法获取MySQL路径信息，请确认MySQL已安装")

        is_win = _is_windows()
        mysqldump = soft_paths.get(
            'windows_abspath_mysqldump_path' if is_win else 'linux_mysqldump_path', ''
        )
        if not mysqldump or not os.path.exists(mysqldump):
            raise Exception(f"mysqldump不存在: {mysqldump}")

        dump_dir = tempfile.gettempdir() if is_win else '/tmp'
        self.dump_file = os.path.join(
            dump_dir, f"ruyi_repl_dump_{self.rep.id}_{int(time.time())}.sql"
        ).replace("\\", "/")

        cmd = (
            f'"{mysqldump}" --opt --skip-lock-tables --single-transaction '
            f'--routines --events --default-character-set=utf8mb4 '
            f'-h{self.rep.master_ip} -P{self.rep.master_port} '
            f'-u{self.rep.root_user} --all-databases '
            f'> "{self.dump_file}"'
        )

        env = os.environ.copy()
        env['MYSQL_PWD'] = self.rep.root_pass

        if is_win:
            from utils.common import RunCommand
            stdout, stderr = RunCommand(cmd)
        else:
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, shell=True
            )
            stderr = result.stderr

        if stderr and "Warning" not in stderr:
            raise Exception(f"导出数据失败: {stderr}")

        file_size = os.path.getsize(self.dump_file) if os.path.exists(self.dump_file) else 0
        self.log(f"数据导出完成，文件大小: {format_size(file_size)}")

    def _step_transfer_dump(self):
        """步骤5: 传输数据文件到从库"""
        self.set_step(4)
        if not self.dump_file or not os.path.exists(self.dump_file):
            raise Exception("数据文件不存在")

        # 判断从库是否为远程节点
        slave_node = self._get_slave_node()
        if slave_node and not slave_node.is_local:
            self._transfer_to_remote(slave_node)
        else:
            self.log("从库为本机，无需传输文件")

    def _step_import_data(self):
        """步骤6: 导入数据到从库"""
        self.set_step(5)
        try:
            from utils.install.mysql import get_mysql_path_info
            soft_paths = get_mysql_path_info()
        except Exception:
            raise Exception("无法获取MySQL路径信息")

        is_win = _is_windows()
        mysql_bin = soft_paths.get(
            'windows_abspath_mysql_path' if is_win else 'linux_mysql_path', ''
        )
        if not mysql_bin or not os.path.exists(mysql_bin):
            raise Exception(f"mysql客户端不存在: {mysql_bin}")

        # 确定dump文件路径（本机或远程传输后的路径）
        dump_path = self.dump_file
        if not dump_path or not os.path.exists(dump_path):
            raise Exception("数据文件不存在，无法导入")

        cmd = (
            f'"{mysql_bin}" -h{self.rep.slave_ip} -P{self.rep.slave_port} '
            f'-u{self.rep.root_user} '
            f'< "{dump_path}"'
        )

        env = os.environ.copy()
        env['MYSQL_PWD'] = self.rep.root_pass

        if is_win:
            from utils.common import RunCommand
            stdout, stderr = RunCommand(cmd)
        else:
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, shell=True
            )
            stderr = result.stderr

        if stderr and "Warning" not in stderr:
            raise Exception(f"导入数据失败: {stderr}")

        self.log("数据导入完成")

        # 清理dump文件
        try:
            os.remove(dump_path)
        except Exception:
            pass

    def _step_config_replication(self):
        """步骤7: 配置主从关系"""
        self.set_step(6)
        from apps.sysnode.views.replication_views import _mysql_exec_sql

        # 获取master status
        master_status, _ = _mysql_exec_sql(
            self.rep.master_ip, self.rep.master_port,
            self.rep.root_user, self.rep.root_pass,
            "SHOW MASTER STATUS"
        )
        master_log_file = ""
        master_log_pos = 0
        if master_status and len(master_status) > 0:
            master_log_file = master_status[0].get("File", "")
            master_log_pos = master_status[0].get("Position", 0)

        if self.rep.binlog_mode == "gtid":
            change_master = f"""
            STOP SLAVE;
            CHANGE MASTER TO
                MASTER_HOST='{self.rep.master_ip}',
                MASTER_PORT={self.rep.master_port},
                MASTER_USER='{self.rep.db_user}',
                MASTER_PASSWORD='{self.rep.db_pass}',
                MASTER_AUTO_POSITION=1;
            """
        else:
            change_master = f"""
            STOP SLAVE;
            CHANGE MASTER TO
                MASTER_HOST='{self.rep.master_ip}',
                MASTER_PORT={self.rep.master_port},
                MASTER_USER='{self.rep.db_user}',
                MASTER_PASSWORD='{self.rep.db_pass}',
                MASTER_LOG_FILE='{master_log_file}',
                MASTER_LOG_POS={master_log_pos};
            """
        _, err = _mysql_exec_sql(
            self.rep.slave_ip, self.rep.slave_port,
            self.rep.root_user, self.rep.root_pass, change_master
        )
        if err:
            raise Exception(f"配置主从关系失败: {err}")

        _mysql_exec_sql(
            self.rep.slave_ip, self.rep.slave_port,
            self.rep.root_user, self.rep.root_pass, "START SLAVE;"
        )

        self.rep.master_log_file = master_log_file
        self.rep.master_log_pos = master_log_pos
        self.rep.save(update_fields=["master_log_file", "master_log_pos"])
        self.log("主从关系配置完成，已启动复制")

    def _step_unlock_tables(self):
        """步骤8: 解锁主库表"""
        self.set_step(7)
        from apps.sysnode.views.replication_views import _mysql_exec_sql

        _mysql_exec_sql(
            self.rep.master_ip, self.rep.master_port,
            self.rep.root_user, self.rep.root_pass,
            "UNLOCK TABLES"
        )
        self.log("主库表已解锁")

    def _step_verify(self):
        """步骤9: 验证复制状态"""
        self.set_step(8)
        from apps.sysnode.views.replication_views import _mysql_exec_sql

        slave_status, err = _mysql_exec_sql(
            self.rep.slave_ip, self.rep.slave_port,
            self.rep.root_user, self.rep.root_pass,
            "SHOW SLAVE STATUS"
        )
        if err:
            raise Exception(f"查询从库状态失败: {err}")

        if slave_status and len(slave_status) > 0:
            io_running = slave_status[0].get("Slave_IO_Running", "No")
            sql_running = slave_status[0].get("Slave_SQL_Running", "No")
            last_error = slave_status[0].get("Last_Error", "")
            if io_running == "Yes" and sql_running == "Yes":
                self.log(f"✅ 复制状态正常: IO={io_running}, SQL={sql_running}")
            else:
                self.log(f"⚠️ 复制状态异常: IO={io_running}, SQL={sql_running}, Error={last_error}")
        else:
            self.log("⚠️ 无法获取从库状态")

    def _unlock_tables_safe(self):
        """安全解锁（异常恢复用）"""
        try:
            from apps.sysnode.views.replication_views import _mysql_exec_sql
            _mysql_exec_sql(
                self.rep.master_ip, self.rep.master_port,
                self.rep.root_user, self.rep.root_pass,
                "UNLOCK TABLES"
            )
        except Exception:
            pass

    def _get_slave_node(self):
        """获取从库对应的ClusterNode"""
        from apps.sysnode.models import ClusterNode
        try:
            return ClusterNode.objects.filter(
                server_ip=self.rep.slave_ip, is_local=False
            ).first()
        except Exception:
            return None

    def _transfer_to_remote(self, node):
        """传输dump文件到远程节点"""
        from utils.ssh_client import RuyiSSHClient

        with RuyiSSHClient(node) as ssh:
            sftp = ssh.open_sftp()
            remote_path = f"/tmp/{os.path.basename(self.dump_file)}"
            self.log(f"正在传输文件到 {node.name}:{remote_path}...")
            sftp.put(self.dump_file, remote_path)
            sftp.close()
            # 更新dump_file路径为远程路径
            self.dump_file = remote_path
        self.log("文件传输完成")

    def _generate_manual_commands(self):
        """生成手动执行的命令（manual模式）"""
        self.log("=== 手动执行命令 ===")
        self.log("")
        self.log(f"# 1. 在主库创建复制用户:")
        self.log(f"CREATE USER '{self.rep.db_user}'@'%' IDENTIFIED BY '{self.rep.db_pass}';")
        self.log(f"GRANT REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO '{self.rep.db_user}'@'%';")
        self.log(f"FLUSH PRIVILEGES;")
        self.log("")
        self.log(f"# 2. 锁定主库表并导出数据:")
        self.log(f"FLUSH TABLES WITH READ LOCK;")
        self.log(f"mysqldump -h{self.rep.master_ip} -P{self.rep.master_port} -u{self.rep.root_user} --all-databases --opt --single-transaction --routines --events > /tmp/dump.sql")
        self.log("")
        self.log(f"# 3. 导入数据到从库:")
        self.log(f"mysql -h{self.rep.slave_ip} -P{self.rep.slave_port} -u{self.rep.root_user} < /tmp/dump.sql")
        self.log("")
        self.log(f"# 4. 配置主从关系:")
        self.log(f"STOP SLAVE;")
        if self.rep.binlog_mode == "gtid":
            self.log(f"CHANGE MASTER TO MASTER_HOST='{self.rep.master_ip}', MASTER_PORT={self.rep.master_port}, MASTER_USER='{self.rep.db_user}', MASTER_PASSWORD='{self.rep.db_pass}', MASTER_AUTO_POSITION=1;")
        else:
            self.log(f"CHANGE MASTER TO MASTER_HOST='{self.rep.master_ip}', MASTER_PORT={self.rep.master_port}, MASTER_USER='{self.rep.db_user}', MASTER_PASSWORD='{self.rep.db_pass}', MASTER_LOG_FILE='<从SHOW MASTER STATUS获取>', MASTER_LOG_POS=<从SHOW MASTER STATUS获取>;")
        self.log(f"START SLAVE;")
        self.log("")
        self.log(f"# 5. 解锁主库表:")
        self.log(f"UNLOCK TABLES;")
        self.log("")
        self.log(f"# 6. 验证复制状态:")
        self.log(f"SHOW SLAVE STATUS\\G")
        self.log("")
        self.log("=== 命令生成完成，请手动执行 ===")

        self.rep.config_status = "manual"
        self.rep.save(update_fields=["config_status"])
