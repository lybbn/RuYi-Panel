import threading
from concurrent.futures import ThreadPoolExecutor
from apps.sysbak.backup_engine.manager import BackupOrchestrateManager

# 线程池
_executor = ThreadPoolExecutor(max_workers=2)


def run_backup_async(backup_id):
    """异步执行备份任务"""
    manager = BackupOrchestrateManager()
    _executor.submit(manager.run_backup, backup_id)


def run_restore_async(backup_id, restore_config, conflict_strategy='skip'):
    """异步执行还原任务"""
    manager = BackupOrchestrateManager()
    _executor.submit(manager.run_restore, backup_id, restore_config, conflict_strategy)
