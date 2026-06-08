import os
import json
import time
import shutil
import hashlib
import tarfile
import datetime
import psutil
from django.conf import settings
from utils.common import (
    GetBackupPath, ReadFile, WriteFile, DeleteDir, current_os,
    GetWebRootPath, GetRuyiSetupPath, GetWindowsRealPath, format_size
)
from apps.sysbak.models import PanelBackup, BackupItemDetail


def _get_panel_backup_base_path():
    backup_path = GetBackupPath()
    panel_backup_path = os.path.join(backup_path, 'panel_backup')
    if not os.path.exists(panel_backup_path):
        os.makedirs(panel_backup_path, exist_ok=True)
    return panel_backup_path


def _get_file_sha256(file_path):
    sha256_hash = hashlib.sha256()
    if not os.path.exists(file_path):
        return ''
    with open(file_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b''):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _get_disk_free_space(path):
    try:
        usage = psutil.disk_usage(path)
        return usage.free
    except Exception:
        return 0


class BackupOrchestrateManager:
    """备份编排管理器 - 统一调度各模块的备份和还原"""

    LOCK_FILE_NAME = 'backup.lock'

    def __init__(self):
        self._lock_file = None
        self._lock_path = os.path.join(settings.BASE_DIR, 'data', self.LOCK_FILE_NAME)
        self.modules = {}
        self._register_modules()

    def _register_modules(self):
        """注册备份模块"""
        from apps.sysbak.backup_engine.site_module import SiteBackupModule
        from apps.sysbak.backup_engine.database_module import DatabaseBackupModule
        from apps.sysbak.backup_engine.crontab_module import CrontabBackupModule
        from apps.sysbak.backup_engine.firewall_module import FirewallBackupModule
        from apps.sysbak.backup_engine.panel_config_module import PanelConfigBackupModule
        from apps.sysbak.backup_engine.terminal_config_module import TerminalConfigBackupModule
        from apps.sysbak.backup_engine.cluster_node_module import ClusterNodeBackupModule

        self.modules = {
            'site': SiteBackupModule,
            'database': DatabaseBackupModule,
            'crontab': CrontabBackupModule,
            'firewall': FirewallBackupModule,
            'panel_config': PanelConfigBackupModule,
            'terminal_config': TerminalConfigBackupModule,
            'cluster_nodes': ClusterNodeBackupModule,
        }

    # ==================== 进程互斥 ====================

    def acquire_lock(self):
        """获取进程锁 - 跨平台"""
        if current_os == 'windows':
            return self._acquire_lock_windows()
        else:
            return self._acquire_lock_linux()

    def release_lock(self):
        """释放进程锁"""
        if self._lock_file:
            try:
                self._lock_file.close()
            except Exception:
                pass
        try:
            if os.path.exists(self._lock_path):
                os.remove(self._lock_path)
        except Exception:
            pass

    def _acquire_lock_windows(self):
        """Windows: 使用文件存在性判断 + PID文件"""
        if os.path.exists(self._lock_path):
            try:
                with open(self._lock_path, 'r') as f:
                    pid = int(f.read().strip())
                if psutil.pid_exists(pid):
                    return False
            except Exception:
                pass
            try:
                os.remove(self._lock_path)
            except Exception:
                pass
        self._lock_file = open(self._lock_path, 'w')
        self._lock_file.write(str(os.getpid()))
        self._lock_file.flush()
        return True

    def _acquire_lock_linux(self):
        """Linux: 使用fcntl文件锁"""
        try:
            import fcntl
            self._lock_file = open(self._lock_path, 'w')
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            return True
        except (IOError, OSError):
            return False

    # ==================== 进度回调 ====================

    def _progress_callback(self, module, item_id, status, msg=''):
        """进度回调 - 更新数据库 + WebSocket推送"""
        from apps.sysbak.models import PanelBackup
        status_map = {0: '等待', 1: '进行中', 2: '成功', 3: '失败'}

        # 更新 BackupItemDetail
        backup_id = getattr(self, '_current_backup_id', None)
        if backup_id:
            BackupItemDetail.objects.filter(
                backup_id=backup_id, module=module, item_id=str(item_id)
            ).update(status=status, error_msg=msg if status == 3 else '')

        # WebSocket推送
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'backup_progress',
                    {
                        'type': 'backup_progress',
                        'module': module,
                        'item_id': str(item_id),
                        'item_name': '',
                        'status': status_map.get(status, ''),
                        'msg': msg,
                        'total_progress': getattr(self, '_total_progress', 0),
                    }
                )
        except Exception:
            pass

    # ==================== 备份执行 ====================

    def run_backup(self, backup_id):
        """执行备份（异步调用入口）"""
        from django.db import connections

        backup_ins = PanelBackup.objects.filter(id=backup_id).first()
        if not backup_ins:
            return

        if not self.acquire_lock():
            PanelBackup.objects.filter(id=backup_id).update(
                backup_status=3, error_msg='其他备份/还原任务正在执行中'
            )
            return

        self._current_backup_id = backup_id
        start_time = time.time()
        all_logs = []
        success_count = 0
        failed_count = 0

        try:
            PanelBackup.objects.filter(id=backup_id).update(backup_status=1)

            backup_config = json.loads(backup_ins.backup_config) if isinstance(backup_ins.backup_config, str) else backup_ins.backup_config
            base_path = _get_panel_backup_base_path()
            timestamp = int(time.time())
            backup_dir = os.path.join(base_path, f'{timestamp}_backup')
            os.makedirs(backup_dir, exist_ok=True)

            # 磁盘空间检查
            free_space = _get_disk_free_space(base_path)
            estimated_size = backup_ins.estimated_size or 0
            if estimated_size > 0 and free_space < estimated_size * 1.2:
                raise Exception(f'磁盘空间不足，需要 {format_size(estimated_size)}，剩余 {format_size(free_space)}')

            # 写入备份元数据
            self._write_backup_metadata(backup_dir, backup_ins, timestamp)

            # 创建 BackupItemDetail 记录
            self._create_item_details(backup_id, backup_config)

            # 逐模块执行备份
            module_map = {
                'site_ids': ('site', 'site'),
                'db_ids': ('database', 'database'),
                'crontab_ids': ('crontab', 'crontab'),
                'firewall_ids': ('firewall', 'firewall'),
                'panel_config_ids': ('panel_config', 'panel_config'),
                'terminal_config_ids': ('terminal_config', 'terminal_config'),
                'cluster_node_ids': ('cluster_nodes', 'cluster_nodes'),
            }

            backup_info_data_list = json.loads(backup_ins.backup_data) if isinstance(backup_ins.backup_data, str) else backup_ins.backup_data
            total_modules = len([k for k, v in module_map.items() if backup_config.get(k)])
            completed_modules = 0

            # 收集各模块数据记录用于还原
            data_list_for_restore = {
                'sites': [],
                'databases': [],
                'crontab_tasks': [],
                'firewall': [],
                'panel_config': [],
                'terminal_config': [],
                'cluster_nodes': [],
            }

            for config_key, (module_key, module_name) in module_map.items():
                item_ids = backup_config.get(config_key, [])
                if not item_ids:
                    continue

                module_class = self.modules.get(module_key)
                if not module_class:
                    continue

                module_instance = module_class(
                    backup_record=backup_ins,
                    backup_dir=backup_dir,
                    progress_callback=self._progress_callback,
                )

                try:
                    results = module_instance.backup(item_ids=item_ids)
                    for item_id, result in results.items():
                        if result.get('status') == 2:
                            success_count += 1
                        else:
                            failed_count += 1
                except Exception as e:
                    failed_count += len(item_ids)
                    module_instance.log(f'模块 {module_name} 备份异常: {str(e)}')

                # 收集模块数据用于还原
                self._collect_data_list(data_list_for_restore, module_key, item_ids)

                all_logs.append(module_instance.get_logs())
                completed_modules += 1
                self._total_progress = int(completed_modules / max(total_modules, 1) * 100)

            # 写入 backup.json
            backup_info = {
                'name': backup_ins.name,
                'timestamp': timestamp,
                'backup_data': backup_info_data_list,
                'backup_config': backup_config,
                'data_list': data_list_for_restore,
                'create_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'platform': {
                    'os': current_os,
                    'panel_version': '1.1.4',
                },
            }
            WriteFile(os.path.join(backup_dir, 'backup.json'), json.dumps(backup_info, ensure_ascii=False, default=str))

            # 打包 tar.gz
            dt_object = datetime.datetime.fromtimestamp(timestamp)
            file_time = dt_object.strftime('%Y%m%d-%H%M')
            tar_file_name = f"{file_time}_{timestamp}_backup.tar.gz"
            tar_file_path = os.path.join(base_path, tar_file_name)

            with tarfile.open(tar_file_path, 'w:gz') as tar:
                tar.add(backup_dir, arcname=f'{timestamp}_backup')

            file_size = os.path.getsize(tar_file_path) if os.path.exists(tar_file_path) else 0
            file_sha256 = _get_file_sha256(tar_file_path)

            # 清理临时目录
            if os.path.exists(backup_dir):
                DeleteDir(backup_dir)

            done_time = datetime.datetime.now()
            total_time = int(time.time()) - start_time

            PanelBackup.objects.filter(id=backup_id).update(
                backup_status=2,
                file_path=tar_file_path,
                file_size=file_size,
                file_sha256=file_sha256,
                done_time=done_time,
                total_time=total_time,
                backup_log='\n'.join(all_logs),
                backup_count_success=success_count,
                backup_count_failed=failed_count,
            )

            # 云存储上传
            if backup_ins.store_type == 'cloud' and backup_ins.cloud_account_id:
                self._upload_to_cloud(backup_ins.cloud_account_id, tar_file_path, tar_file_name)

        except Exception as e:
            PanelBackup.objects.filter(id=backup_id).update(
                backup_status=3,
                error_msg=str(e),
                backup_log='\n'.join(all_logs) + f'\n[ERROR] {str(e)}',
                backup_count_success=success_count,
                backup_count_failed=failed_count,
            )
        finally:
            self.release_lock()
            for conn in connections.all():
                conn.close_if_unusable()

    # ==================== 还原执行 ====================

    def run_restore(self, backup_id, restore_config, conflict_strategy='skip'):
        """执行还原（异步调用入口）"""
        from django.db import connections

        backup_ins = PanelBackup.objects.filter(id=backup_id).first()
        if not backup_ins:
            return

        if not self.acquire_lock():
            PanelBackup.objects.filter(id=backup_id).update(
                restore_status=3, restore_log='其他备份/还原任务正在执行中'
            )
            return

        self._current_backup_id = backup_id
        start_time = time.time()
        all_logs = []

        try:
            PanelBackup.objects.filter(id=backup_id).update(restore_status=1)

            if not backup_ins.file_path or not os.path.exists(backup_ins.file_path):
                raise Exception('备份文件不存在')

            backup_config = json.loads(backup_ins.backup_config) if backup_ins.backup_config else {}
            if isinstance(restore_config, str):
                restore_config = json.loads(restore_config)

            base_path = _get_panel_backup_base_path()
            extract_dir = os.path.join(base_path, f'restore_{backup_id}')

            # 解压备份文件
            with tarfile.open(backup_ins.file_path, 'r:gz') as tar:
                tar.extractall(extract_dir)

            backup_json_dirs = [d for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
            if not backup_json_dirs:
                raise Exception('备份文件格式错误')
            backup_dir = os.path.join(extract_dir, backup_json_dirs[0])

            backup_info_file = os.path.join(backup_dir, 'backup.json')
            if not os.path.exists(backup_info_file):
                raise Exception('备份信息文件不存在')
            backup_info = json.loads(ReadFile(backup_info_file))

            # 跨平台兼容性检查
            source_os = backup_info.get('platform', {}).get('os', 'linux')
            if source_os != current_os:
                all_logs.append(f'[WARN] 备份来源平台({source_os})≠当前平台({current_os})，部分数据需要适配')

            # 逐模块还原
            module_map = {
                'site_ids': ('site', 'site'),
                'db_ids': ('database', 'database'),
                'crontab_ids': ('crontab', 'crontab'),
                'firewall_ids': ('firewall', 'firewall'),
                'panel_config_ids': ('panel_config', 'panel_config'),
            }

            for config_key, (module_key, module_name) in module_map.items():
                item_ids = restore_config.get(config_key, backup_config.get(config_key, []))
                if not item_ids:
                    continue

                module_class = self.modules.get(module_key)
                if not module_class:
                    continue

                module_instance = module_class(
                    backup_record=backup_ins,
                    backup_dir=backup_dir,
                    progress_callback=self._progress_callback,
                )

                try:
                    items_config = self._get_items_config(backup_info, module_key, item_ids)
                    module_instance.restore(backup_dir, items_config, conflict_strategy=conflict_strategy)
                except Exception as e:
                    module_instance.log(f'模块 {module_name} 还原异常: {str(e)}')

                all_logs.append(module_instance.get_logs())

            done_time = datetime.datetime.now()
            total_time = int(time.time()) - start_time

            PanelBackup.objects.filter(id=backup_id).update(
                restore_status=2,
                restore_done_time=done_time,
                restore_total_time=total_time,
                restore_log='\n'.join(all_logs),
            )

        except Exception as e:
            PanelBackup.objects.filter(id=backup_id).update(
                restore_status=3,
                restore_log='\n'.join(all_logs) + f'\n[ERROR] {str(e)}',
            )
        finally:
            self.release_lock()
            # 清理解压目录
            if os.path.exists(extract_dir):
                DeleteDir(extract_dir)
            for conn in connections.all():
                conn.close_if_unusable()

    # ==================== 辅助方法 ====================

    def _write_backup_metadata(self, backup_dir, backup_record, timestamp):
        """写入备份元数据"""
        metadata = {
            'version': '1.0',
            'name': backup_record.name,
            'timestamp': timestamp,
            'platform': {
                'os': current_os,
                'panel_version': '1.1.4',
            },
            'paths': {
                'wwwroot': GetWebRootPath(),
                'backup': GetBackupPath(),
            },
        }
        WriteFile(os.path.join(backup_dir, 'metadata.json'), json.dumps(metadata, ensure_ascii=False))

    def _create_item_details(self, backup_id, backup_config):
        """创建 BackupItemDetail 记录"""
        # 网站
        from apps.system.models import Sites, Databases, TerminalServer, CommonCommands
        from apps.systask.models import CrontabTask
        from apps.sysnode.models import ClusterNode

        for sid in backup_config.get('site_ids', []):
            site = Sites.objects.filter(id=sid).first()
            if site:
                BackupItemDetail.objects.get_or_create(
                    backup_id=backup_id, module='site', item_id=str(sid),
                    defaults={'item_name': site.name, 'item_type': 'site'}
                )

        for did in backup_config.get('db_ids', []):
            db = Databases.objects.filter(id=did).first()
            if db:
                BackupItemDetail.objects.get_or_create(
                    backup_id=backup_id, module='database', item_id=str(did),
                    defaults={'item_name': db.db_name, 'item_type': db.get_db_type_display()}
                )

        for cid in backup_config.get('crontab_ids', []):
            task = CrontabTask.objects.filter(id=cid).first()
            if task:
                BackupItemDetail.objects.get_or_create(
                    backup_id=backup_id, module='crontab', item_id=str(cid),
                    defaults={'item_name': task.name, 'item_type': 'crontab'}
                )

        for fid in backup_config.get('firewall_ids', []):
            BackupItemDetail.objects.get_or_create(
                backup_id=backup_id, module='firewall', item_id=str(fid),
                defaults={'item_name': '防火墙规则', 'item_type': 'firewall'}
            )

        for pid in backup_config.get('panel_config_ids', []):
            BackupItemDetail.objects.get_or_create(
                backup_id=backup_id, module='panel_config', item_id=str(pid),
                defaults={'item_name': '面板配置', 'item_type': 'panel_config'}
            )

        for tid in backup_config.get('terminal_config_ids', []):
            tid_str = str(tid)
            if tid_str.startswith('cmd_'):
                cc = CommonCommands.objects.filter(id=int(tid_str.replace('cmd_', ''))).first()
                item_name = cc.name if cc else tid_str
                item_type = '常用命令'
            else:
                ts = TerminalServer.objects.filter(id=tid).first()
                item_name = ts.remark or f"{ts.host}:{ts.port}" if ts else tid_str
                item_type = ts.get_connect_protocol_display() if ts else 'terminal'
            BackupItemDetail.objects.get_or_create(
                backup_id=backup_id, module='terminal_config', item_id=tid_str,
                defaults={'item_name': item_name, 'item_type': item_type}
            )

        for nid in backup_config.get('cluster_node_ids', []):
            node = ClusterNode.objects.filter(id=nid).first()
            BackupItemDetail.objects.get_or_create(
                backup_id=backup_id, module='cluster_nodes', item_id=str(nid),
                defaults={'item_name': node.name if node else str(nid), 'item_type': node.get_node_type_display() if node else 'node'}
            )

    def _get_items_config(self, backup_info, module_key, item_ids):
        """从备份信息中提取指定模块的还原配置"""
        data_list = backup_info.get('data_list', {})
        key_map = {
            'site': 'sites',
            'database': 'databases',
            'crontab': 'crontab_tasks',
            'firewall': 'firewall',
            'panel_config': 'panel_config',
            'terminal_config': 'terminal_config',
            'cluster_nodes': 'cluster_nodes',
        }
        data_key = key_map.get(module_key, module_key)
        items = data_list.get(data_key, [])

        if isinstance(items, dict):
            return items

        if '__all__' in item_ids:
            return items

        return [item for item in items if item.get('id') in item_ids]

    def _collect_data_list(self, data_list_for_restore, module_key, item_ids):
        """收集各模块数据记录，用于还原时传入 items_config"""
        try:
            if module_key == 'site':
                from apps.system.models import Sites, SiteDomains
                for sid in item_ids:
                    site = Sites.objects.filter(id=sid).first()
                    if site:
                        site_data = {
                            'id': site.id, 'name': site.name, 'type': site.type,
                            'path': site.path, 'remark': site.remark, 'status': site.status,
                            'sslcfg': site.sslcfg, 'wafcfg': site.wafcfg,
                            'project_cfg': site.project_cfg, 'domains': [],
                        }
                        for d in SiteDomains.objects.filter(site_id=site.id):
                            site_data['domains'].append({'name': d.name, 'port': d.port})
                        data_list_for_restore['sites'].append(site_data)

            elif module_key == 'database':
                from apps.system.models import Databases
                for did in item_ids:
                    db = Databases.objects.filter(id=did).first()
                    if db:
                        data_list_for_restore['databases'].append({
                            'id': db.id, 'db_name': db.db_name, 'db_type': db.db_type,
                            'db_host': db.db_host or '127.0.0.1', 'db_port': db.db_port or 3306,
                            'db_user': db.db_user or '', 'db_pass': db.db_pass or '',
                            'format': db.format or 'utf8mb4', 'is_remote': db.is_remote,
                        })

            elif module_key == 'crontab':
                from apps.systask.models import CrontabTask
                for cid in item_ids:
                    task = CrontabTask.objects.filter(id=cid).first()
                    if task:
                        data_list_for_restore['crontab_tasks'].append({
                            'id': task.id, 'name': task.name, 'is_sys': task.is_sys,
                            'status': task.status, 'period_type': task.period_type,
                            'year': task.year, 'month': task.month, 'week': task.week,
                            'day': task.day, 'hour': task.hour, 'minute': task.minute,
                            'second': task.second, 'type': task.type,
                            'shell_body': task.shell_body, 'database': task.database,
                            'website': task.website, 'dir': task.dir,
                            'exclude_rules': task.exclude_rules, 'db_type': task.db_type,
                            'backup_to': task.backup_to, 'saveNums': task.saveNums,
                            'url': task.url, 'ai_prompt': task.ai_prompt,
                            'ai_deliver': task.ai_deliver, 'ai_silent': task.ai_silent,
                            'ai_context_from': task.ai_context_from, 'ai_timeout': task.ai_timeout,
                            'run_at': str(task.run_at) if task.run_at else None,
                        })

            elif module_key == 'firewall':
                data_list_for_restore['firewall'].append({'id': 'firewall_rules', 'name': '防火墙规则'})

            elif module_key == 'panel_config':
                for pid in item_ids:
                    data_list_for_restore['panel_config'].append({'id': pid, 'name': str(pid)})

            elif module_key == 'terminal_config':
                from apps.system.models import TerminalServer, CommonCommands
                for tid in item_ids:
                    tid_str = str(tid)
                    if tid_str.startswith('cmd_'):
                        cc = CommonCommands.objects.filter(id=int(tid_str.replace('cmd_', ''))).first()
                        if cc:
                            data_list_for_restore['terminal_config'].append({
                                'id': f'cmd_{cc.id}', 'name': cc.name, 'type': '常用命令',
                                'shell': cc.shell,
                            })
                    else:
                        ts = TerminalServer.objects.filter(id=tid).first()
                        if ts:
                            data_list_for_restore['terminal_config'].append({
                                'id': ts.id, 'name': ts.remark or f"{ts.host}:{ts.port}",
                                'type': ts.get_connect_protocol_display(),
                                'host': ts.host, 'port': ts.port, 'username': ts.username,
                                'connect_protocol': ts.connect_protocol, 'auth_type': ts.type,
                            })

            elif module_key == 'cluster_nodes':
                from apps.sysnode.models import ClusterNode
                for nid in item_ids:
                    node = ClusterNode.objects.filter(id=nid).first()
                    if node:
                        data_list_for_restore['cluster_nodes'].append({
                            'id': node.id, 'name': node.name,
                            'address': node.address, 'server_ip': node.server_ip,
                            'node_type': node.node_type, 'api_key': node.api_key,
                            'ssh_conf': node.ssh_conf, 'remarks': node.remarks,
                            'is_local': node.is_local,
                        })
        except Exception:
            pass

    def _upload_to_cloud(self, cloud_account_id, file_path, file_name):
        """上传到云存储"""
        try:
            from apps.syscloud.models import CloudStorageAccount
            from apps.syscloud.cloud_providers.factory import get_provider
            account = CloudStorageAccount.objects.filter(id=cloud_account_id).first()
            if not account:
                return
            provider = get_provider(account)
            remote_path = os.path.join(account.backup_path, 'panel_backup', file_name).replace('\\', '/')
            provider.upload_file(file_path, remote_path)
        except Exception:
            pass

    # ==================== 数据列表获取 ====================

    @staticmethod
    def get_backup_data_list():
        """获取可备份的数据列表"""
        from apps.system.models import Sites, Databases, TerminalServer, CommonCommands
        from apps.systask.models import CrontabTask
        from apps.sysshop.models import RySoftShop
        from apps.sysnode.models import ClusterNode

        result = {
            'sites': [],
            'databases': [],
            'crontab_tasks': [],
            'env_soft': [],
            'firewall': [],
            'panel_config': [],
            'terminal_config': [],
            'cluster_nodes': [],
        }
        sites = Sites.objects.all().order_by('-id')
        for s in sites:
            size = 0
            if s.path and os.path.exists(s.path):
                try:
                    for dirpath, dirnames, filenames in os.walk(s.path):
                        for f in filenames:
                            try:
                                size += os.path.getsize(os.path.join(dirpath, f))
                            except OSError:
                                pass
                except Exception:
                    pass
            result['sites'].append({
                'id': s.id,
                'name': s.name,
                'type': s.get_type_display(),
                'path': s.path,
                'size': size,
                'size_display': format_size(size),
            })
        databases = Databases.objects.all().order_by('-id')
        db_type_defaults = {
            0: {'host': '127.0.0.1', 'port': 3306, 'user': 'root'},
            1: {'host': '127.0.0.1', 'port': 1433, 'user': 'sa'},
            2: {'host': '127.0.0.1', 'port': 27017, 'user': ''},
            3: {'host': '127.0.0.1', 'port': 5432, 'user': 'postgres'},
            4: {'host': '127.0.0.1', 'port': 6379, 'user': ''},
        }
        for d in databases:
            size = 0
            defaults = db_type_defaults.get(d.db_type, {'host': '127.0.0.1', 'port': 0, 'user': ''})
            db_host = d.db_host or defaults['host']
            db_port = d.db_port or defaults['port']
            db_user = d.db_user or defaults['user']
            try:
                if d.db_type == 0 and not d.is_remote:
                    from utils.ruyiclass.mysqlClass import MysqlClient
                    client = MysqlClient.get_client(
                        db_host=db_host,
                        db_port=db_port,
                        db_user=db_user,
                        db_password=d.db_pass or '',
                    )
                    if client:
                        rows = client.filter(
                            "SELECT COALESCE(SUM(data_length + index_length), 0) "
                            "FROM information_schema.tables WHERE table_schema = %s",
                            sqlstr_args=[d.db_name],
                        )
                        if rows:
                            size = int(rows[0].get('COALESCE(SUM(data_length + index_length), 0)', 0))
                        MysqlClient.close_client(
                            db_host=db_host,
                            db_port=db_port,
                            db_user=db_user,
                            db_name=d.db_name,
                        )
                elif d.db_type == 3 and not d.is_remote:
                    try:
                        from utils.common import pip_install_package
                        pip_install_package('psycopg2-binary')
                        import psycopg2
                        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
                        conn = psycopg2.connect(
                            host=db_host,
                            port=db_port,
                            user=db_user,
                            password=d.db_pass or '',
                            database=d.db_name,
                        )
                        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                        cursor = conn.cursor()
                        cursor.execute("SELECT pg_database_size(%s)", [d.db_name])
                        row = cursor.fetchone()
                        if row:
                            size = int(row[0])
                        cursor.close()
                        conn.close()
                    except Exception:
                        pass
                elif d.db_type == 2 and not d.is_remote:
                    try:
                        from utils.common import pip_install_package
                        pip_install_package('pymongo')
                        from pymongo import MongoClient
                        mongo_url = 'mongodb://'
                        if db_user and d.db_pass:
                            mongo_url += f'{db_user}:{d.db_pass}@'
                        mongo_url += f'{db_host}:{db_port}/'
                        client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
                        db_obj = client[d.db_name]
                        stats = db_obj.command('dbStats')
                        size = int(stats.get('dataSize', 0))
                        client.close()
                    except Exception:
                        pass
                elif d.db_type == 4 and not d.is_remote:
                    try:
                        from utils.ruyiclass.redisClass import RedisClient
                        client = RedisClient.get_client(
                            db_host=db_host,
                            db_port=db_port,
                            db_password=d.db_pass or '',
                        )
                        if client:
                            info = client.info('memory')
                            size = int(info.get('used_memory_dataset', 0)) or int(info.get('used_memory', 0))
                            RedisClient.close_client(
                                db_host=db_host,
                                db_port=db_port,
                                db_password=d.db_pass or '',
                            )
                    except Exception:
                        pass
            except Exception:
                pass
            result['databases'].append({
                'id': d.id,
                'name': d.db_name,
                'type': d.get_db_type_display(),
                'host': db_host,
                'is_remote': d.is_remote,
                'size': size,
                'size_display': format_size(size),
            })
        crontab_tasks = CrontabTask.objects.filter(is_sys=False).order_by('-id')
        for c in crontab_tasks:
            result['crontab_tasks'].append({
                'id': c.id,
                'name': c.name,
                'period_type': c.get_period_type_display(),
                'size': 1024,
                'size_display': format_size(1024),
            })
        soft_list = RySoftShop.objects.filter(type__in=[2, 3, 4, 5]).order_by('id')
        for soft in soft_list:
            result['env_soft'].append({
                'id': soft.id,
                'name': soft.name,
                'title': soft.name,
                'type': soft.type,
            })
        result['firewall'] = [
            {'id': 'firewall_rules', 'name': '防火墙规则', 'size': 30720, 'size_display': '30 KB'},
            {'id': 'ssh_config', 'name': 'SSH配置', 'size': 20480, 'size_display': '20 KB'},
        ]
        result['panel_config'] = [
            {'id': 'panel_settings', 'name': '面板配置', 'size': 51200, 'size_display': '50 KB'},
            {'id': 'security_path', 'name': '安全入口路径', 'size': 1024, 'size_display': '1 KB'},
        ]
        # 终端桌面配置
        terminal_servers = TerminalServer.objects.all().order_by('-id')
        terminal_size = 0
        for ts in terminal_servers:
            result['terminal_config'].append({
                'id': ts.id,
                'name': ts.remark or f"{ts.host}:{ts.port}",
                'type': ts.get_connect_protocol_display(),
                'host': ts.host,
                'port': ts.port,
                'auth_type': ts.get_type_display(),
                'size': 2048,
                'size_display': '2 KB',
            })
            terminal_size += 2048
        common_commands = CommonCommands.objects.all().order_by('-id')
        for cc in common_commands:
            result['terminal_config'].append({
                'id': f'cmd_{cc.id}',
                'name': cc.name or '未命名命令',
                'type': '常用命令',
                'host': '-',
                'port': 0,
                'auth_type': '-',
                'size': 1024,
                'size_display': '1 KB',
            })
            terminal_size += 1024
        # 多机管理节点列表
        cluster_nodes = ClusterNode.objects.all().order_by('-id')
        for cn in cluster_nodes:
            result['cluster_nodes'].append({
                'id': cn.id,
                'name': cn.name,
                'type': cn.get_node_type_display(),
                'host': cn.server_ip or cn.address,
                'status': cn.get_status_display(),
                'is_local': cn.is_local,
                'size': 4096,
                'size_display': '4 KB',
            })
        return result

    @staticmethod
    def calculate_estimated_size(backup_config):
        """计算预计备份大小"""
        from apps.system.models import Sites, Databases

        if isinstance(backup_config, str):
            try:
                backup_config = json.loads(backup_config)
            except Exception:
                backup_config = {}

        total_size = 0
        for sid in backup_config.get('site_ids', []):
            site = Sites.objects.filter(id=sid).first()
            if site and site.path and os.path.exists(site.path):
                for dirpath, dirnames, filenames in os.walk(site.path):
                    for f in filenames:
                        try:
                            total_size += os.path.getsize(os.path.join(dirpath, f))
                        except OSError:
                            pass
        for did in backup_config.get('db_ids', []):
            db = Databases.objects.filter(id=did).first()
            if db and db.db_type == 0 and not db.is_remote:
                try:
                    from utils.ruyiclass.mysqlClass import MysqlClient
                    client = MysqlClient.get_client(
                        db_host=db.db_host or '127.0.0.1',
                        db_port=db.db_port or 3306,
                        db_user=db.db_user or 'root',
                        db_password=db.db_pass or '',
                    )
                    if client:
                        rows = client.filter(
                            "SELECT COALESCE(SUM(data_length + index_length), 0) "
                            "FROM information_schema.tables WHERE table_schema = %s",
                            sqlstr_args=[db.db_name],
                        )
                        if rows:
                            total_size += int(rows[0].get('COALESCE(SUM(data_length + index_length), 0)', 0))
                        MysqlClient.close_client(
                            db_host=db.db_host or '127.0.0.1',
                            db_port=db.db_port or 3306,
                            db_user=db.db_user or 'root',
                            db_name=db.db_name,
                        )
                except Exception:
                    pass

        crontab_ids = backup_config.get('crontab_ids', [])
        total_size += len(crontab_ids) * 1024
        if backup_config.get('firewall_ids'):
            total_size += 50 * 1024
        if backup_config.get('panel_config_ids'):
            total_size += 100 * 1024
        return total_size
