import os
import time
from abc import ABC, abstractmethod


class BaseBackupModule(ABC):
    """备份模块基类"""

    def __init__(self, backup_record, backup_dir, progress_callback=None):
        self.backup_record = backup_record
        self.backup_dir = backup_dir
        self.progress_callback = progress_callback
        self.log_lines = []

    @abstractmethod
    def get_data_list(self):
        """获取可备份的数据列表（含大小估算）"""
        pass

    @abstractmethod
    def backup(self, item_ids=None):
        """执行备份，返回 {item_id: {status, file_path, size, error_msg}}"""
        pass

    @abstractmethod
    def restore(self, backup_dir, items_config, conflict_strategy='skip'):
        """执行还原"""
        pass

    def report_progress(self, module, item_id, status, msg=''):
        """上报进度（WebSocket + 数据库）"""
        if self.progress_callback:
            self.progress_callback(module, item_id, status, msg)

    def log(self, msg):
        """记录日志"""
        time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{time_str}] {msg}"
        self.log_lines.append(line)

    def get_logs(self):
        """获取所有日志"""
        return '\n'.join(self.log_lines)
