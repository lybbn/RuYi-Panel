import os
import json
from utils.common import ReadFile, WriteFile
from apps.sysbak.backup_engine.base import BaseBackupModule


class TerminalConfigBackupModule(BaseBackupModule):
    """终端桌面配置备份模块 - 终端服务器列表 + 常用命令"""

    def get_data_list(self):
        from apps.system.models import TerminalServer, CommonCommands
        result = []
        for ts in TerminalServer.objects.all().order_by('-id'):
            result.append({
                'id': ts.id,
                'name': ts.remark or f"{ts.host}:{ts.port}",
                'type': ts.get_connect_protocol_display(),
            })
        for cc in CommonCommands.objects.all().order_by('-id'):
            result.append({
                'id': f'cmd_{cc.id}',
                'name': cc.name or '未命名命令',
                'type': '常用命令',
            })
        return result

    def backup(self, item_ids=None):
        from apps.system.models import TerminalServer, CommonCommands

        config_dir = os.path.join(self.backup_dir, 'terminal_config')
        os.makedirs(config_dir, exist_ok=True)
        results = {}

        # 备份终端服务器列表
        terminal_ids = [i for i in (item_ids or []) if not str(i).startswith('cmd_')]
        if terminal_ids or not item_ids:
            try:
                self.report_progress('terminal_config', 'terminal_servers', 1, '正在备份终端服务器列表')
                self.log('开始备份终端服务器列表')
                terminals = TerminalServer.objects.filter(id__in=terminal_ids) if terminal_ids else TerminalServer.objects.all()
                terminal_data = []
                for t in terminals:
                    terminal_data.append({
                        'host': t.host, 'port': t.port, 'username': t.username,
                        'remark': t.remark, 'connect_protocol': t.connect_protocol,
                        'type': t.type, 'pkey': t.pkey, 'pkey_passwd': t.pkey_passwd,
                        'password': t.password,
                        'rdp_domain': t.rdp_domain, 'rdp_security': t.rdp_security,
                        'rdp_ignore_cert': t.rdp_ignore_cert, 'rdp_color_depth': t.rdp_color_depth,
                    })
                WriteFile(os.path.join(config_dir, 'terminal_servers.json'), json.dumps(terminal_data, ensure_ascii=False))
                self.report_progress('terminal_config', 'terminal_servers', 2, '终端服务器列表备份完成')
                self.log('终端服务器列表备份完成')
                results['terminal_servers'] = {'status': 2, 'error_msg': ''}
            except Exception as e:
                self.report_progress('terminal_config', 'terminal_servers', 3, f'终端服务器列表备份失败: {str(e)}')
                self.log(f'终端服务器列表备份失败: {str(e)}')
                results['terminal_servers'] = {'status': 3, 'error_msg': str(e)}

        # 备份常用命令
        cmd_ids = [int(str(i).replace('cmd_', '')) for i in (item_ids or []) if str(i).startswith('cmd_')]
        if cmd_ids or not item_ids:
            try:
                self.report_progress('terminal_config', 'common_commands', 1, '正在备份常用命令')
                self.log('开始备份常用命令')
                commands = CommonCommands.objects.filter(id__in=cmd_ids) if cmd_ids else CommonCommands.objects.all()
                cmd_data = []
                for c in commands:
                    cmd_data.append({'name': c.name, 'shell': c.shell})
                WriteFile(os.path.join(config_dir, 'common_commands.json'), json.dumps(cmd_data, ensure_ascii=False))
                self.report_progress('terminal_config', 'common_commands', 2, '常用命令备份完成')
                self.log('常用命令备份完成')
                results['common_commands'] = {'status': 2, 'error_msg': ''}
            except Exception as e:
                self.report_progress('terminal_config', 'common_commands', 3, f'常用命令备份失败: {str(e)}')
                self.log(f'常用命令备份失败: {str(e)}')
                results['common_commands'] = {'status': 3, 'error_msg': str(e)}

        return results

    def restore(self, backup_dir, items_config, conflict_strategy='skip'):
        config_dir = os.path.join(backup_dir, 'terminal_config')
        if not os.path.exists(config_dir):
            self.log('未找到终端配置备份文件')
            return

        # 还原终端服务器
        terminal_file = os.path.join(config_dir, 'terminal_servers.json')
        if os.path.exists(terminal_file):
            try:
                from apps.system.models import TerminalServer
                terminal_data = json.loads(ReadFile(terminal_file))
                for t in terminal_data:
                    existing = TerminalServer.objects.filter(host=t['host'], port=t['port']).first()
                    if existing:
                        if conflict_strategy == 'skip':
                            continue
                        elif conflict_strategy == 'overwrite':
                            existing.username = t.get('username', '')
                            existing.remark = t.get('remark', '')
                            existing.connect_protocol = t.get('connect_protocol', 'ssh')
                            existing.type = t.get('type', 0)
                            existing.save()
                            continue
                        elif conflict_strategy == 'rename':
                            t['remark'] = f"{t.get('remark', '')}_restored"
                    TerminalServer.objects.create(
                        host=t['host'],
                        port=t['port'],
                        username=t.get('username', ''),
                        remark=t.get('remark', ''),
                        connect_protocol=t.get('connect_protocol', 'ssh'),
                        type=t.get('type', 0),
                        password=t.get('password', ''),
                        pkey=t.get('pkey', ''),
                        pkey_passwd=t.get('pkey_passwd', ''),
                        rdp_domain=t.get('rdp_domain', ''),
                        rdp_security=t.get('rdp_security', ''),
                        rdp_ignore_cert=t.get('rdp_ignore_cert', True),
                        rdp_color_depth=t.get('rdp_color_depth', 32),
                    )
                self.log('终端服务器列表还原完成')
            except Exception as e:
                self.log(f'还原终端服务器失败: {str(e)}')

        # 还原常用命令
        commands_file = os.path.join(config_dir, 'common_commands.json')
        if os.path.exists(commands_file):
            try:
                from apps.system.models import CommonCommands
                cmd_data = json.loads(ReadFile(commands_file))
                for c in cmd_data:
                    existing = CommonCommands.objects.filter(name=c['name']).first()
                    if existing:
                        if conflict_strategy == 'skip':
                            continue
                        elif conflict_strategy == 'overwrite':
                            existing.shell = c['shell']
                            existing.save()
                            continue
                        elif conflict_strategy == 'rename':
                            c['name'] = f"{c['name']}_restored"
                    CommonCommands.objects.create(name=c['name'], shell=c['shell'])
                self.log('常用命令还原完成')
            except Exception as e:
                self.log(f'还原常用命令失败: {str(e)}')

        self.report_progress('terminal_config', 'all', 2, '终端桌面配置还原完成')
