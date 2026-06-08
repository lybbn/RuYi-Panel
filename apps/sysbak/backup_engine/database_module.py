import os
import json
import time
import shutil
from utils.common import ReadFile, WriteFile, current_os, GetBackupPath
from apps.sysbak.backup_engine.base import BaseBackupModule


class DatabaseBackupModule(BaseBackupModule):
    """数据库备份模块 - 使用 RY_BACKUP_* / RY_IMPORT_* 封装"""

    # db_type 映射：与 Databases.DB_TYPE_CHOICES 一致
    # 0=MySQL, 1=SqlServer(暂不支持), 2=MongoDB, 3=PgSql, 4=Redis
    DB_BACKUP_HANDLERS = {
        0: '_backup_mysql',
        # 1: SqlServer —— 暂不支持
        2: '_backup_mongodb',
        3: '_backup_postgresql',
        4: '_backup_redis',
    }

    DB_RESTORE_HANDLERS = {
        0: '_restore_mysql',
        # 1: SqlServer —— 暂不支持
        2: '_restore_mongodb',
        3: '_restore_postgresql',
        4: '_restore_redis',
    }

    def get_data_list(self):
        from apps.system.models import Databases
        databases = Databases.objects.all().order_by('-id')
        result = []
        for d in databases:
            result.append({
                'id': d.id,
                'name': d.db_name,
                'type': d.get_db_type_display(),
                'host': d.db_host,
                'is_remote': d.is_remote,
            })
        return result

    def backup(self, item_ids=None):
        from apps.system.models import Databases

        results = {}
        databases = Databases.objects.filter(id__in=item_ids) if item_ids else Databases.objects.all()

        for db in databases:
            handler_name = self.DB_BACKUP_HANDLERS.get(db.db_type)
            if not handler_name:
                results[db.id] = {'status': 3, 'error_msg': f'不支持的数据库类型: {db.db_type}'}
                continue

            if db.is_remote:
                results[db.id] = {'status': 3, 'error_msg': '远程数据库暂不支持备份'}
                continue

            try:
                self.report_progress('database', db.id, 1, f'正在备份数据库: {db.db_name}')
                self.log(f'开始备份数据库: {db.db_name} ({db.get_db_type_display()})')

                handler = getattr(self, handler_name)
                handler(db)

                self.report_progress('database', db.id, 2, f'数据库备份完成: {db.db_name}')
                self.log(f'数据库备份完成: {db.db_name}')
                results[db.id] = {'status': 2, 'error_msg': ''}
            except Exception as e:
                self.report_progress('database', db.id, 3, f'数据库备份失败: {db.db_name} - {str(e)}')
                self.log(f'数据库备份失败: {db.db_name} - {str(e)}')
                results[db.id] = {'status': 3, 'error_msg': str(e)}

        return results

    def restore(self, backup_dir, items_config, conflict_strategy='skip'):
        from apps.system.models import Databases

        for db_data in items_config:
            db_name = db_data.get('db_name', '')
            db_type = db_data.get('db_type', 0)

            handler_name = self.DB_RESTORE_HANDLERS.get(db_type)
            if not handler_name:
                self.log(f'不支持的数据库类型: {db_type}')
                continue

            # 冲突检测
            existing = Databases.objects.filter(db_name=db_name).first()
            if existing:
                if conflict_strategy == 'skip':
                    self.log(f'跳过已存在的数据库: {db_name}')
                    continue
                elif conflict_strategy == 'overwrite':
                    self.log(f'覆盖已存在的数据库: {db_name}')
                elif conflict_strategy == 'rename':
                    db_name = f"{db_name}_restored_{int(time.time())}"
                    db_data['db_name'] = db_name

            self.report_progress('database', db_data.get('id', ''), 1, f'正在还原数据库: {db_name}')
            self.log(f'开始还原数据库: {db_name}')

            try:
                handler = getattr(self, handler_name)
                handler(db_data, backup_dir)

                self.report_progress('database', db_data.get('id', ''), 2, f'数据库还原完成: {db_name}')
                self.log(f'数据库还原完成: {db_name}')
            except Exception as e:
                self.report_progress('database', db_data.get('id', ''), 3, f'数据库还原失败: {db_name} - {str(e)}')
                self.log(f'数据库还原失败: {db_name} - {str(e)}')

    # ==================== MySQL ====================

    def _backup_mysql(self, db):
        """MySQL备份 - 使用 RY_BACKUP_MYSQL_DATABASE"""
        from utils.install.mysql import RY_BACKUP_MYSQL_DATABASE, RY_GET_MYSQL_LOADSTATUS

        is_win = current_os == 'windows'
        load_status = RY_GET_MYSQL_LOADSTATUS(is_windows=is_win)
        if not load_status.get('status'):
            raise Exception('MySQL未启动')

        db_info = self._build_db_info(db)
        success, file_path, file_size = RY_BACKUP_MYSQL_DATABASE(
            db_info=db_info, is_windows=is_win, return_bk_ins=False
        )
        if not success:
            raise Exception('MySQL备份失败')

        # 移动到备份目录（RY_BACKUP_MYSQL_DATABASE返回.zip文件）
        dst_dir = os.path.join(self.backup_dir, 'databases', 'mysql')
        os.makedirs(dst_dir, exist_ok=True)
        # 保持原始后缀（.zip）
        file_ext = os.path.splitext(file_path)[1] if file_path else '.zip'
        dst_path = os.path.join(dst_dir, f'{db.db_name}{file_ext}')
        if os.path.exists(file_path):
            shutil.move(file_path, dst_path)

        # 保存数据库记录信息
        WriteFile(os.path.join(dst_dir, f'{db.db_name}_info.json'), json.dumps(self._build_db_info(db), default=str))

    def _restore_mysql(self, db_data, backup_dir):
        """MySQL还原 - 使用 RY_IMPORT_MYSQL_SQL"""
        from utils.install.mysql import (
            RY_IMPORT_MYSQL_SQL, RY_GET_MYSQL_LOADSTATUS,
            RY_CHECK_MYSQL_DATANAME_EXISTS, RY_CREATE_MYSQL_DATANAME, RY_CREATE_MYSQL_USER,
        )
        from utils.ruyiclass.mysqlClass import MysqlClient

        is_win = current_os == 'windows'
        load_status = RY_GET_MYSQL_LOADSTATUS(is_windows=is_win)
        if not load_status.get('status'):
            raise Exception('MySQL未启动')

        db_info = db_data.copy()
        db_info['db_port'] = db_info.get('db_port', 3306)
        db_info['db_user'] = db_info.get('db_user', 'root')

        # 检查数据库是否存在，不存在则创建
        mysql_conn = MysqlClient.get_client(
            db_host=db_info.get('db_host', '127.0.0.1'),
            db_port=db_info.get('db_port', 3306),
            db_user=db_info.get('db_user', 'root'),
            db_password=db_info.get('db_pass', ''),
        )
        if mysql_conn:
            if not RY_CHECK_MYSQL_DATANAME_EXISTS(mysql_conn, db_info['db_name']):
                RY_CREATE_MYSQL_DATANAME(mysql_conn, db_info)
                if db_info.get('db_user') and db_info.get('db_pass'):
                    RY_CREATE_MYSQL_USER(mysql_conn, db_info)
            MysqlClient.close_client(
                db_host=db_info.get('db_host', '127.0.0.1'),
                db_port=db_info.get('db_port', 3306),
                db_user=db_info.get('db_user', 'root'),
                db_name=db_info['db_name'],
            )

        sql_dir = os.path.join(backup_dir, 'databases', 'mysql')
        # 查找备份文件（可能是.sql或.zip）
        sql_file = None
        for ext in ['.zip', '.sql', '.tar.gz']:
            candidate = os.path.join(sql_dir, f"{db_info['db_name']}{ext}")
            if os.path.exists(candidate):
                sql_file = candidate
                break
        if not sql_file:
            raise Exception(f'MySQL备份文件不存在: {sql_dir}')

        # RY_IMPORT_MYSQL_SQL 从 db_info['file_name'] 获取文件路径
        db_info['file_name'] = sql_file
        RY_IMPORT_MYSQL_SQL(db_info=db_info, is_windows=is_win)

        # 创建数据库记录
        from apps.system.models import Databases
        Databases.objects.get_or_create(
            db_name=db_info['db_name'],
            defaults={
                'db_type': 0,
                'db_host': db_info.get('db_host', '127.0.0.1'),
                'db_port': db_info.get('db_port', 3306),
                'db_user': db_info.get('db_user', ''),
                'db_pass': db_info.get('db_pass', ''),
            }
        )

    # ==================== PostgreSQL ====================

    def _backup_postgresql(self, db):
        """PostgreSQL备份 - 使用 RY_BACKUP_PGSQL_DATABASE"""
        from utils.install.pgsql import RY_BACKUP_PGSQL_DATABASE, RY_GET_PGSQL_LOADSTATUS

        is_win = current_os == 'windows'
        load_status = RY_GET_PGSQL_LOADSTATUS(is_windows=is_win)
        if not load_status.get('status'):
            raise Exception('PostgreSQL未启动')

        db_info = self._build_db_info(db)
        db_info['db_port'] = db.db_port or 5432
        db_info['db_user'] = db.db_user or 'postgres'

        success, file_path, file_size = RY_BACKUP_PGSQL_DATABASE(
            db_info=db_info, is_windows=is_win
        )
        if not success:
            raise Exception('PostgreSQL备份失败')

        dst_dir = os.path.join(self.backup_dir, 'databases', 'postgresql')
        os.makedirs(dst_dir, exist_ok=True)
        dst_path = os.path.join(dst_dir, f'{db.db_name}.sql')
        if os.path.exists(file_path):
            shutil.move(file_path, dst_path)

    def _restore_postgresql(self, db_data, backup_dir):
        """PostgreSQL还原 - 使用 RY_IMPORT_PGSQL_SQL"""
        from utils.install.pgsql import (
            RY_IMPORT_PGSQL_SQL, RY_GET_PGSQL_LOADSTATUS,
            RY_CHECK_PGSQL_DATANAME_EXISTS, RY_CREATE_PGSQL_DATANAME, RY_CREATE_PGSQL_USER,
        )

        is_win = current_os == 'windows'
        load_status = RY_GET_PGSQL_LOADSTATUS(is_windows=is_win)
        if not load_status.get('status'):
            raise Exception('PostgreSQL未启动')

        db_info = db_data.copy()
        db_info['db_port'] = db_info.get('db_port', 5432)
        db_info['db_user'] = db_info.get('db_user', 'postgres')

        sql_dir = os.path.join(backup_dir, 'databases', 'postgresql')
        sql_file = os.path.join(sql_dir, f"{db_info['db_name']}.sql")
        if not os.path.exists(sql_file):
            raise Exception(f'PostgreSQL备份文件不存在: {sql_file}')

        RY_IMPORT_PGSQL_SQL(db_info=db_info, sql_file=sql_file, is_windows=is_win)

        from apps.system.models import Databases
        Databases.objects.get_or_create(
            db_name=db_info['db_name'],
            defaults={
                'db_type': 3,
                'db_host': db_info.get('db_host', '127.0.0.1'),
                'db_port': db_info.get('db_port', 5432),
                'db_user': db_info.get('db_user', 'postgres'),
            }
        )

    # ==================== MongoDB ====================

    def _backup_mongodb(self, db):
        """MongoDB备份 - 使用 RY_BACKUP_MONGODB_DATABASE"""
        from utils.install.mongodb import RY_BACKUP_MONGODB_DATABASE, RY_GET_MONGODB_LOADSTATUS

        is_win = current_os == 'windows'
        load_status = RY_GET_MONGODB_LOADSTATUS(is_windows=is_win)
        if not load_status.get('status'):
            raise Exception('MongoDB未启动')

        db_info = self._build_db_info(db)
        db_info['db_port'] = db.db_port or 27017

        success, file_path, file_size = RY_BACKUP_MONGODB_DATABASE(
            db_info=db_info, is_windows=is_win
        )
        if not success:
            raise Exception('MongoDB备份失败')

        dst_dir = os.path.join(self.backup_dir, 'databases', 'mongodb')
        os.makedirs(dst_dir, exist_ok=True)
        dst_path = os.path.join(dst_dir, f'mongodb_{db.db_name}.archive')
        if os.path.exists(file_path):
            shutil.move(file_path, dst_path)

    def _restore_mongodb(self, db_data, backup_dir):
        """MongoDB还原 - 使用 RY_IMPORT_MONGODB_SQL"""
        from utils.install.mongodb import RY_IMPORT_MONGODB_SQL, RY_GET_MONGODB_LOADSTATUS

        is_win = current_os == 'windows'
        load_status = RY_GET_MONGODB_LOADSTATUS(is_windows=is_win)
        if not load_status.get('status'):
            raise Exception('MongoDB未启动')

        db_info = db_data.copy()
        db_info['db_port'] = db_info.get('db_port', 27017)

        backup_dir_path = os.path.join(backup_dir, 'databases', 'mongodb')
        archive_file = os.path.join(backup_dir_path, f"mongodb_{db_info['db_name']}.archive")
        if not os.path.exists(archive_file):
            raise Exception(f'MongoDB备份文件不存在: {archive_file}')

        RY_IMPORT_MONGODB_SQL(db_info=db_info, backup_file=archive_file, is_windows=is_win)

        from apps.system.models import Databases
        Databases.objects.get_or_create(
            db_name=db_info['db_name'],
            defaults={
                'db_type': 2,
                'db_host': db_info.get('db_host', '127.0.0.1'),
                'db_port': db_info.get('db_port', 27017),
            }
        )

    # ==================== Redis ====================

    def _backup_redis(self, db):
        """Redis备份 - 使用 RedisClient + RY_GET_REDIS_CONF_OPTIONS"""
        from utils.install.redis import RY_GET_REDIS_LOADSTATUS, RY_GET_REDIS_CONF_OPTIONS
        from utils.ruyiclass.redisClass import RedisClient

        is_win = current_os == 'windows'
        load_status = RY_GET_REDIS_LOADSTATUS(is_windows=is_win)
        if not load_status.get('status'):
            raise Exception('Redis未启动')

        local_options = RY_GET_REDIS_CONF_OPTIONS(is_windows=is_win)
        r = RedisClient.get_client(local=True, localOptions=local_options)
        if not r:
            raise Exception('Redis连接失败')

        r.bgsave()
        time.sleep(2)

        redis_conf = r.config_get()
        redis_dir = redis_conf.get('dir', '')
        redis_dbfilename = redis_conf.get('dbfilename', 'dump.rdb')
        src_path = os.path.join(redis_dir, redis_dbfilename)

        dst_dir = os.path.join(self.backup_dir, 'databases', 'redis')
        os.makedirs(dst_dir, exist_ok=True)
        dst_path = os.path.join(dst_dir, f'dump_{int(time.time())}.rdb')
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)

    def _restore_redis(self, db_data, backup_dir):
        """Redis还原 - 停止Redis → 替换RDB → 启动Redis"""
        from utils.install.redis import RY_GET_REDIS_CONF_OPTIONS
        from utils.install.install_soft import Ry_Stop_Soft, Ry_Start_Soft

        is_win = current_os == 'windows'
        local_options = RY_GET_REDIS_CONF_OPTIONS(is_windows=is_win)
        rdb_dir = local_options.get('dir', '')
        rdb_filename = local_options.get('dbfilename', 'dump.rdb')
        dst_rdb = os.path.join(rdb_dir, rdb_filename)

        # 停止Redis
        Ry_Stop_Soft(name='redis', is_windows=is_win)

        try:
            # 查找备份RDB文件
            redis_backup_dir = os.path.join(backup_dir, 'databases', 'redis')
            if os.path.exists(redis_backup_dir):
                rdb_files = [f for f in os.listdir(redis_backup_dir) if f.endswith('.rdb')]
                if rdb_files:
                    src_rdb = os.path.join(redis_backup_dir, rdb_files[0])
                    if os.path.exists(dst_rdb):
                        shutil.copy2(src_rdb, dst_rdb)
                    else:
                        os.makedirs(os.path.dirname(dst_rdb), exist_ok=True)
                        shutil.copy2(src_rdb, dst_rdb)
        finally:
            # 启动Redis
            Ry_Start_Soft(name='redis', is_windows=is_win)

    # ==================== 辅助方法 ====================

    def _build_db_info(self, db):
        """构建数据库信息字典"""
        return {
            'db_host': db.db_host or '127.0.0.1',
            'db_port': db.db_port or 3306,
            'db_user': db.db_user or '',
            'db_pass': db.db_pass or '',
            'db_name': db.db_name,
            'format': db.format or 'utf8mb4',
        }
