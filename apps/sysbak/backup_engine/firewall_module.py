import os
import json
import time
from utils.common import ReadFile, WriteFile, current_os
from utils.server.system import system
from apps.sysbak.backup_engine.base import BaseBackupModule


class FirewallBackupModule(BaseBackupModule):
    """防火墙备份模块 - 使用 system.GetFirewallRules / system.SetFirewallRuleAction"""

    def get_data_list(self):
        return [
            {'id': 'firewall_rules', 'name': '防火墙规则'},
            {'id': 'ssh_config', 'name': 'SSH配置'},
        ]

    def backup(self, item_ids=None):
        results = {}
        firewall_dir = os.path.join(self.backup_dir, 'firewall')
        os.makedirs(firewall_dir, exist_ok=True)

        try:
            self.report_progress('firewall', 'rules', 1, '正在备份防火墙规则')
            is_windows = current_os == 'windows'

            # 1. 使用 system.GetFirewallRules 获取防火墙规则（跨平台）
            if is_windows:
                try:
                    in_rules = system.GetFirewallRules({'dir': 'in', 'search': '', 'status': ''})
                    WriteFile(os.path.join(firewall_dir, 'win_in_rules.json'), json.dumps(in_rules, default=str))
                except Exception:
                    pass
                try:
                    out_rules = system.GetFirewallRules({'dir': 'out', 'search': '', 'status': ''})
                    WriteFile(os.path.join(firewall_dir, 'win_out_rules.json'), json.dumps(out_rules, default=str))
                except Exception:
                    pass
            else:
                try:
                    port_rules = system.GetFirewallRules({'dir': 'all', 'search': '', 'status': ''})
                    WriteFile(os.path.join(firewall_dir, 'linux_port_rules.json'), json.dumps(port_rules, default=str))
                except Exception:
                    pass

            # 2. 获取防火墙状态信息
            try:
                firewall_info = system.GetFirewallInfo()
                WriteFile(os.path.join(firewall_dir, 'firewall_info.json'), json.dumps(firewall_info, default=str))
            except Exception:
                pass

            # 3. 获取端口转发规则
            try:
                proxy_rules = system.GetPortProxyRules({'search': ''})
                WriteFile(os.path.join(firewall_dir, 'port_proxy_rules.json'), json.dumps(proxy_rules, default=str))
            except Exception:
                pass

            # 4. 备份面板防火墙数据库记录（如果存在）
            try:
                from apps.system.models import FirewallRules
                rules = FirewallRules.objects.all()
                rules_data = []
                for r in rules:
                    rules_data.append({
                        'type': r.type, 'port': r.port, 'protocol': r.protocol,
                        'strategy': r.strategy, 'address': r.address,
                        'status': r.status, 'remark': r.remark,
                    })
                WriteFile(os.path.join(firewall_dir, 'panel_rules.json'), json.dumps(rules_data))
            except ImportError:
                # FirewallRules模型不存在时跳过
                self.log('面板防火墙模型不存在，跳过面板规则备份')
            except Exception as e:
                self.log(f'备份面板防火墙记录失败: {str(e)}')

            # 5. 记录平台信息
            platform_info = {'os': current_os, 'timestamp': int(time.time())}
            WriteFile(os.path.join(firewall_dir, 'platform.json'), json.dumps(platform_info))

            self.report_progress('firewall', 'rules', 2, '防火墙规则备份完成')
            self.log('防火墙规则备份完成')
            results['firewall'] = {'status': 2, 'error_msg': ''}
        except Exception as e:
            self.report_progress('firewall', 'rules', 3, f'防火墙规则备份失败: {str(e)}')
            self.log(f'防火墙规则备份失败: {str(e)}')
            results['firewall'] = {'status': 3, 'error_msg': str(e)}

        return results

    def restore(self, backup_dir, items_config, conflict_strategy='skip'):
        firewall_dir = os.path.join(backup_dir, 'firewall')
        if not os.path.exists(firewall_dir):
            self.log('未找到防火墙备份文件')
            return

        # 读取备份来源平台
        source_os = 'linux'
        platform_file = os.path.join(firewall_dir, 'platform.json')
        if os.path.exists(platform_file):
            try:
                source_os = json.loads(ReadFile(platform_file)).get('os', 'linux')
            except Exception:
                pass

        if source_os != current_os:
            self.log(f'警告：备份来源({source_os})≠当前平台({current_os})，系统级防火墙规则不兼容，仅还原面板记录')

        # 还原防火墙状态
        info_file = os.path.join(firewall_dir, 'firewall_info.json')
        if os.path.exists(info_file):
            try:
                firewall_info = json.loads(ReadFile(info_file))
                if firewall_info.get('status'):
                    system.SetFirewallStatus(status='start')
            except Exception as e:
                self.log(f'还原防火墙状态失败: {str(e)}')

        # 还原面板防火墙规则 - 使用 system.SetFirewallRuleAction
        rules_file = os.path.join(firewall_dir, 'panel_rules.json')
        if os.path.exists(rules_file):
            try:
                rules_data = json.loads(ReadFile(rules_file))
                for r in rules_data:
                    # 使用 system.SetFirewallRuleAction 添加规则
                    system.SetFirewallRuleAction({
                        'type': r.get('type'),
                        'port': r.get('port'),
                        'protocol': r.get('protocol', 'tcp'),
                        'strategy': r.get('strategy', 'accept'),
                        'address': r.get('address', ''),
                        'remark': r.get('remark', ''),
                    })
                self.log('面板防火墙规则还原完成')
            except Exception as e:
                self.log(f'还原面板防火墙规则失败: {str(e)}')

        self.report_progress('firewall', 'rules', 2, '防火墙规则还原完成')
