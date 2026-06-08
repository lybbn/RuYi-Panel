import os
import json
from utils.common import ReadFile, WriteFile, current_os, GetSecurityPath, GetDataPath, GetWebRootPath, GetWindowsRealPath, GetRuyiSetupPath
from apps.sysbak.backup_engine.base import BaseBackupModule


class PanelConfigBackupModule(BaseBackupModule):
    """面板配置备份模块 - 使用已有封装"""

    CONFIG_ITEMS = {
        'panel_settings': '面板基本设置',
        'security_path': '安全入口路径',
    }

    def get_data_list(self):
        return [{'id': k, 'name': v} for k, v in self.CONFIG_ITEMS.items()]

    def backup(self, item_ids=None):
        config_dir = os.path.join(self.backup_dir, 'panel_config')
        os.makedirs(config_dir, exist_ok=True)
        results = {}

        for item_id in (item_ids or self.CONFIG_ITEMS.keys()):
            try:
                handler = getattr(self, f'_backup_{item_id}', None)
                if handler:
                    handler(config_dir)
                    results[item_id] = {'status': 2, 'error_msg': ''}
            except Exception as e:
                self.log(f'备份 {item_id} 失败: {str(e)}')
                results[item_id] = {'status': 3, 'error_msg': str(e)}

        return results

    def restore(self, backup_dir, items_config, conflict_strategy='skip'):
        config_dir = os.path.join(backup_dir, 'panel_config')
        if not os.path.exists(config_dir):
            self.log('未找到面板配置备份文件')
            return

        # 还原面板基本设置
        settings_file = os.path.join(config_dir, 'panel_settings.json')
        if os.path.exists(settings_file):
            try:
                from apps.system.models import Config
                config_data = json.loads(ReadFile(settings_file))
                config_ins = Config.objects.first()
                if config_ins:
                    if isinstance(config_data, dict):
                        config_data = json.dumps(config_data)
                    config_ins.config = config_data
                    config_ins.save()
                    self.log('面板基本设置还原完成')
            except Exception as e:
                self.log(f'还原面板设置失败: {str(e)}')

        # 还原安全入口路径
        security_file = os.path.join(config_dir, 'security_path.json')
        if os.path.exists(security_file):
            try:
                security_data = json.loads(ReadFile(security_file))
                security_path = security_data.get('security_path', '')
                if security_path:
                    from utils.common import WriteFile as WriteFileUtil
                    from utils.common import GetSecurityPath as _get_sp
                    import os as _os
                    from django.conf import settings as _settings
                    sp_file = _os.path.join(_settings.BASE_DIR, 'data', 'security_path.ry')
                    WriteFileUtil(sp_file, security_path)
                    self.log('安全入口路径还原完成')
            except Exception as e:
                self.log(f'还原安全入口路径失败: {str(e)}')

        self.report_progress('panel_config', 'all', 2, '面板配置还原完成')

    # ==================== 备份方法 ====================

    def _backup_panel_settings(self, config_dir):
        """备份面板基本设置"""
        from apps.system.models import Config
        config = Config.objects.first()
        if config:
            config_data = config.config if config.config else '{}'
            if isinstance(config_data, str):
                try:
                    config_data = json.loads(config_data)
                except Exception:
                    config_data = {'raw': config_data}
            config_data['_source_os'] = current_os
            config_data['_source_wwwroot'] = GetWebRootPath()
            WriteFile(os.path.join(config_dir, 'panel_settings.json'), json.dumps(config_data, ensure_ascii=False))

    def _backup_security_path(self, config_dir):
        """备份安全入口路径"""
        security_path = GetSecurityPath()
        if security_path:
            WriteFile(os.path.join(config_dir, 'security_path.json'), json.dumps({'security_path': security_path}))
