#!/usr/bin/python
# coding: utf-8

import os
import re
import time
import subprocess
import importlib
from utils.common import GetInstallPath, is_service_running, ReadFile, WriteFile, GetTmpPath, GetLogsPath, DeleteFile, generate_random_string, ConvertToUnixLineEndings, CreateInstallProcess, CleanupInstallProcess, SafeReadStderr, ReleaseMemory, GetProcessNameInfo
from utils.security.files import download_url_file, get_file_name_from_url
from utils.server.system import system
from django.conf import settings
from apps.systask.subprocessMg import job_subprocess_add


def get_mongodb_path_info():
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path, 'mongodb')
    install_path = root_path + '/mongodb'
    data_path = os.path.join(install_abspath_path, 'data')
    log_path = install_path + '/logs'
    return {
        'name': 'mongodb',
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path': install_abspath_path,
        'install_path': install_path,
        'data_abspath_path': data_path,
        'data_path': data_path,
        'windows_abspath_bin_path': os.path.join(install_abspath_path, 'bin'),
        'windows_abspath_mongod_path': os.path.join(install_abspath_path, 'bin', 'mongod.exe'),
        'windows_abspath_mongo_path': os.path.join(install_abspath_path, 'bin', 'mongosh.exe'),
        'windows_abspath_conf_path': os.path.join(install_abspath_path, 'mongod.conf'),
        'linux_mongod_path': os.path.join(install_path, 'bin', 'mongod'),
        'linux_mongo_path': os.path.join(install_path, 'bin', 'mongosh'),
        'linux_conf_path': os.path.join(install_path, 'mongod.conf'),
        'log_abspath_path': os.path.join(install_abspath_path, 'logs'),
        'log_path': log_path,
        'log_file_path': log_path + '/mongodb.log',
    }


def Mongodb_Connect(db_host='127.0.0.1', db_port=27017, db_user=None, db_password=None, db_name='admin', local=True, auth_source='admin'):
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
        if local:
            conf_info = get_mongodb_local_conf()
            if conf_info:
                db_host = conf_info.get('bindIp', '127.0.0.1')
                db_port = conf_info.get('port', 27017)
                db_user = conf_info.get('user', db_user)
                db_password = conf_info.get('password', db_password)
        if db_user and db_password:
            uri = "mongodb://%s:%s@%s:%s/%s?authSource=%s" % (
                db_user, db_password, db_host, db_port, db_name, auth_source
            )
        else:
            uri = "mongodb://%s:%s/%s" % (db_host, db_port, db_name)
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        return client
    except (ConnectionFailure, ServerSelectionTimeoutError, OperationFailure) as e:
        return None


def get_mongodb_local_conf():
    paths = get_mongodb_path_info()
    conf_path = paths['windows_abspath_conf_path'] if system.is_windows else paths['linux_conf_path']
    if not os.path.exists(conf_path):
        return None
    try:
        content = ReadFile(conf_path)
        if not content:
            return None
        import yaml
        conf = yaml.safe_load(content)
        if not conf:
            return None
        net = conf.get('net', {}) or {}
        security = conf.get('security', {}) or {}
        result = {
            'port': net.get('port', 27017),
            'bindIp': net.get('bindIp', '127.0.0.1'),
        }
        if security.get('authorization') == 'enabled' or security.get('authorization') == True:
            result['auth'] = True
        else:
            result['auth'] = False
        return result
    except Exception:
        return None


def RY_GET_MONGODB_ROOT_PASS():
    from apps.sysshop.models import RySoftShop
    soft = RySoftShop.objects.filter(name='mongodb').first()
    if soft and soft.password:
        return soft.password
    return ''


def RY_SET_MONGODB_ROOT_PASS(passwd, is_windows=True):
    from pymongo.errors import OperationFailure
    from apps.sysshop.models import RySoftShop
    RySoftShop.objects.filter(name='mongodb').update(password=passwd)
    db_conn = Mongodb_Connect(local=True)
    if db_conn:
        try:
            db_conn.admin.command('updateUser', 'root', pwd=passwd)
        except OperationFailure:
            try:
                db_conn.admin.command('createUser', 'root', pwd=passwd, roles=[{'role': 'root', 'db': 'admin'}])
            except Exception:
                pass
        finally:
            db_conn.close()


def RY_GET_MONGODB_PORT():
    conf_info = get_mongodb_local_conf()
    if conf_info:
        return conf_info.get('port', 27017)
    return 27017


def RY_SET_MONGODB_PORT(port, is_windows=True):
    soft_paths = get_mongodb_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    if not os.path.exists(conf_path):
        raise ValueError("MongoDB配置文件不存在")
    content = ReadFile(conf_path)
    if not content:
        raise ValueError("MongoDB配置文件读取失败")
    try:
        import yaml
        conf = yaml.safe_load(content)
        if not conf:
            raise ValueError("MongoDB配置文件解析失败")
        if 'net' not in conf:
            conf['net'] = {}
        conf['net']['port'] = int(port)
        new_content = yaml.dump(conf, default_flow_style=False, allow_unicode=True)
        WriteFile(conf_path, new_content)
    except ImportError:
        import re
        new_content = re.sub(r'port:\s*\d+', 'port: %s' % port, content)
        WriteFile(conf_path, new_content)


def RY_CHECK_MONGODB_DATANAME_EXISTS(db_conn, db_name):
    try:
        db_list = db_conn.list_database_names()
        return db_name in db_list
    except Exception:
        return False


def RY_CREATE_MONGODB_DATANAME(db_conn, db_name, db_user, db_pass):
    from pymongo.errors import OperationFailure
    try:
        db = db_conn[db_name]
        db.create_collection('_init_')
        db['_init_'].drop()
        if db_user and db_pass:
            try:
                db_conn[db_name].command('createUser', db_user, pwd=db_pass, roles=[
                    {'role': 'readWrite', 'db': db_name},
                    {'role': 'dbAdmin', 'db': db_name}
                ])
            except OperationFailure:
                try:
                    db_conn[db_name].command('updateUser', db_user, pwd=db_pass, roles=[
                        {'role': 'readWrite', 'db': db_name},
                        {'role': 'dbAdmin', 'db': db_name}
                    ])
                except Exception:
                    pass
        return True
    except Exception as e:
        raise ValueError("创建MongoDB数据库失败：%s" % str(e))


def RY_DELETE_MONGODB_DATABASE(db_conn, db_name, db_user=None):
    try:
        if db_user:
            try:
                db_conn[db_name].command('dropUser', db_user)
            except Exception:
                pass
        db_conn.drop_database(db_name)
        return True
    except Exception as e:
        raise ValueError("删除MongoDB数据库失败：%s" % str(e))


def RY_RESET_MONGODB_USER_PASS(db_conn, db_name, db_user, db_pass):
    from pymongo.errors import OperationFailure
    try:
        db_conn[db_name].command('updateUser', db_user, pwd=db_pass)
        return True
    except OperationFailure:
        try:
            db_conn[db_name].command('createUser', db_user, pwd=db_pass, roles=[
                {'role': 'readWrite', 'db': db_name},
                {'role': 'dbAdmin', 'db': db_name}
            ])
            return True
        except Exception as e:
            raise ValueError("重置MongoDB用户密码失败：%s" % str(e))
    except Exception as e:
        raise ValueError("重置MongoDB用户密码失败：%s" % str(e))


def RY_BACKUP_MONGODB_DATABASE(db_info={}, is_windows=True):
    import subprocess
    import time
    from utils.common import GetBackupPath
    db_name = db_info.get('db_name', '')
    db_host = db_info.get('db_host', '127.0.0.1')
    db_port = db_info.get('db_port', 27017)
    db_user = db_info.get('db_user', '')
    db_pass = db_info.get('db_pass', '')
    backup_dir = GetBackupPath()
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
    backup_file = os.path.join(backup_dir, "mongodb_%s_%s.archive" % (db_name, timestamp))
    paths = get_mongodb_path_info()
    if is_windows:
        mongodump_path = os.path.join(paths['windows_abspath_bin_path'], 'mongodump.exe')
    else:
        mongodump_path = os.path.join(paths['install_path'], 'bin', 'mongodump')
    if not os.path.exists(mongodump_path):
        try:
            import shutil
            mongodump_path = shutil.which('mongodump') or 'mongodump'
        except Exception:
            mongodump_path = 'mongodump'
    cmd = [mongodump_path, '--host', str(db_host), '--port', str(db_port), '--db', db_name, '--archive=' + backup_file]
    if db_user and db_pass:
        cmd.extend(['--username', db_user, '--password', db_pass, '--authenticationDatabase', 'admin'])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if os.path.exists(backup_file):
            file_size = os.path.getsize(backup_file)
            return True, backup_file, file_size
        return False, '', 0
    except Exception as e:
        return False, '', 0


def RY_IMPORT_MONGODB_SQL(db_info={}, backup_file='', is_windows=True):
    import subprocess
    db_name = db_info.get('db_name', '')
    db_host = db_info.get('db_host', '127.0.0.1')
    db_port = db_info.get('db_port', 27017)
    db_user = db_info.get('db_user', '')
    db_pass = db_info.get('db_pass', '')
    paths = get_mongodb_path_info()
    if is_windows:
        mongorestore_path = os.path.join(paths['windows_abspath_bin_path'], 'mongorestore.exe')
    else:
        mongorestore_path = os.path.join(paths['install_path'], 'bin', 'mongorestore')
    if not os.path.exists(mongorestore_path):
        try:
            import shutil
            mongorestore_path = shutil.which('mongodump') or 'mongorestore'
        except Exception:
            mongorestore_path = 'mongorestore'
    cmd = [mongorestore_path, '--host', str(db_host), '--port', str(db_port), '--db', db_name, '--archive=' + backup_file, '--drop']
    if db_user and db_pass:
        cmd.extend(['--username', db_user, '--password', db_pass, '--authenticationDatabase', 'admin'])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return True
    except Exception as e:
        raise ValueError("导入MongoDB数据库失败：%s" % str(e))


def mongodb_install_call_back(version={}, call_back=None, ok=True):
    if call_back:
        job_id = version.get('job_id')
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id, version=version, ok=ok)


def RY_SET_DEFAULT_MONGODB_CONFIG(conf_path, is_windows=True, log_path='', data_path=''):
    if not log_path:
        soft_paths = get_mongodb_path_info()
        log_path = soft_paths['log_file_path']
    if not data_path:
        soft_paths = get_mongodb_path_info()
        data_path = soft_paths['data_abspath_path']
    log_path = log_path.replace('\\', '/')
    data_path = data_path.replace('\\', '/')
    default_conf = """storage:
  dbPath: %s
systemLog:
  destination: file
  path: %s
  logAppend: true
net:
  port: 27017
  bindIp: 0.0.0.0
security:
  authorization: disabled
""" % (data_path, log_path)
    WriteFile(conf_path, default_conf)


def Install_Mongodb(type=2, version={}, is_windows=True, call_back=None):
    try:
        name = version['name']
        log = version.get('log', None)
        is_write_log = False
        log_path = ""
        if log:
            is_write_log = True
            log_path = os.path.join(os.path.abspath(GetLogsPath()), name, log)
        WriteFile(log_path, "-------------------安装任务已开始-------------------\n", mode='a', write=is_write_log)
        if is_service_running(27017):
            error_msg = "[error]检测到本机已安装并开启了MongoDB(27017)服务，请关闭后再试!!!"
            WriteFile(log_path, error_msg + '\n', mode='a', write=is_write_log)
            raise ValueError(error_msg)
        download_url = version.get('url', None)
        WriteFile(log_path, "开始下载【%s】安装文件,文件地址：%s\n" % (name, download_url), mode='a', write=is_write_log)
        filename = get_file_name_from_url(download_url)
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_mongodb_path_info()
        install_base_directory = soft_paths['root_abspath_path']
        install_directory = soft_paths['install_abspath_path']
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        save_path = os.path.join(save_directory, filename)
        ok, msg = download_url_file(url=download_url, save_path=save_path, process=True, log_path=log_path, chunk_size=32768)
        if not ok:
            msg = "[error]【%s】下载失败，原因：%s" % (filename, msg)
            raise ValueError(msg)
        if is_windows:
            WriteFile(log_path, "【%s】下载完成\n" % filename, mode='a', write=is_write_log)
            WriteFile(log_path, "正在解压安装文件到%s\n" % install_directory, mode='a', write=is_write_log)
            system.ForceRemoveDir(install_directory)
            from apps.systask.tasks import func_unzip
            func_unzip(save_path, install_base_directory)
            extracted_folder = os.path.join(install_base_directory, 'mongodb')
            src_folder = os.path.join(install_base_directory, filename.replace('.zip', ''))
            if os.path.exists(src_folder) and not os.path.exists(extracted_folder):
                os.rename(src_folder, extracted_folder)
            elif not os.path.exists(extracted_folder):
                for item in os.listdir(install_base_directory):
                    if item.startswith('mongodb') and os.path.isdir(os.path.join(install_base_directory, item)):
                        os.rename(os.path.join(install_base_directory, item), extracted_folder)
                        break
            WriteFile(log_path, "解压成功\n", mode='a', write=is_write_log)
            version_file = os.path.join(install_directory, 'version.ry')
            WriteFile(version_file, version['c_version'])
            WriteFile(log_path, "正在初始化MongoDB配置...\n", mode='a', write=is_write_log)
            data_path = soft_paths['data_abspath_path']
            log_dir = soft_paths['log_abspath_path']
            if not os.path.exists(data_path):
                os.makedirs(data_path)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            WriteFile(soft_paths['log_file_path'], "")
            conf_path = soft_paths['windows_abspath_conf_path']
            RY_SET_DEFAULT_MONGODB_CONFIG(conf_path, is_windows=True, log_path=soft_paths['log_file_path'], data_path=data_path)
            WriteFile(log_path, "初始化MongoDB配置成功\n", mode='a', write=is_write_log)
        else:
            script_path = os.path.join(settings.BASE_DIR, "utils", "install", "bash", "mongodb.sh")
            ConvertToUnixLineEndings(script_path)
            r_process = CreateInstallProcess(['bash', script_path, 'install', version['c_version']])
            job_subprocess_add(version['job_id'], r_process)
            try:
                while True:
                    r_output = r_process.stdout.readline()
                    if r_output == '' and r_process.poll() is not None:
                        break
                    if r_output:
                        WriteFile(log_path, f"{r_output.strip()}\n", mode='a', write=is_write_log)
                    time.sleep(0.1)
                r_stderr = SafeReadStderr(r_process)
                if r_stderr:
                    if not os.path.exists(soft_paths['install_path'] + '/bin/mongod'):
                        raise ValueError(r_stderr.strip()[:2000])
            finally:
                CleanupInstallProcess(r_process, version['job_id'])
                r_process = None
            version_file = os.path.join(install_directory, 'version.ry')
            WriteFile(version_file, version['c_version'])
        if is_windows:
            WriteFile(log_path, "正在安装MongoDB为系统服务...\n", mode='a', write=is_write_log)
            mongod_path = soft_paths['windows_abspath_mongod_path']
            conf_path = soft_paths['windows_abspath_conf_path']
            service_name = "MongoDB"
            install_service_cmd = f'"{mongod_path}" --config "{conf_path}" --install --serviceName "{service_name}" --serviceDisplayName "MongoDB"'
            result = subprocess.run(install_service_cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0:
                WriteFile(log_path, f"安装MongoDB服务失败：{result.stderr}\n", mode='a', write=is_write_log)
            else:
                WriteFile(log_path, "安装MongoDB服务成功\n", mode='a', write=is_write_log)
        WriteFile(log_path, "正在启动MongoDB服务...\n", mode='a', write=is_write_log)
        Start_Mongodb(is_windows=is_windows)
        WriteFile(log_path, "MongoDB启动成功\n", mode='a', write=is_write_log)
        time.sleep(2)
        root_pass = generate_random_string(16, special=False)
        WriteFile(log_path, "开始设置MongoDB的root密码...\n", mode='a', write=is_write_log)
        try:
            conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
            conf_content = ReadFile(conf_path)
            if conf_content:
                conf_content = conf_content.replace('authorization: disabled', 'authorization: enabled')
                WriteFile(conf_path, conf_content)
            Restart_Mongodb(is_windows=is_windows)
            time.sleep(2)
            from pymongo import MongoClient
            client = MongoClient("mongodb://127.0.0.1:27017/admin", serverSelectionTimeoutMS=5000)
            client.admin.command('createUser', 'root', pwd=root_pass, roles=[{'role': 'root', 'db': 'admin'}])
            client.close()
        except Exception as e:
            WriteFile(log_path, f"设置root密码时出现警告：{e}，可稍后手动设置\n", mode='a', write=is_write_log)
        version['password'] = root_pass
        DeleteFile(save_path, empty_tips=False)
        WriteFile(log_path, "安装成功，安装目录：%s\n" % install_directory, mode='a', write=is_write_log)
        version['install_path'] = install_directory
        mongodb_install_call_back(version=version, call_back=call_back, ok=True)
        WriteFile(log_path, "-------------------安装任务已结束-------------------\n", mode='a', write=is_write_log)
        version.clear()
        soft_paths.clear()
        ReleaseMemory()
        return True
    except Exception as e:
        WriteFile(log_path, f"【错误】异常信息如下：\n{e}", mode='a', write=is_write_log)
        mongodb_install_call_back(version=version, call_back=call_back, ok=False)
        version.clear()
        ReleaseMemory()
        return False


def Uninstall_Mongodb(is_windows=True):
    soft_paths = get_mongodb_path_info()
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            Stop_Mongodb(is_windows=is_windows)
            time.sleep(0.5)
            mongod_path = soft_paths['windows_abspath_mongod_path']
            conf_path = soft_paths['windows_abspath_conf_path']
            service_name = "MongoDB"
            if os.path.exists(mongod_path):
                remove_cmd = f'"{mongod_path}" --config "{conf_path}" --remove --serviceName "{service_name}"'
                subprocess.run(remove_cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            from utils.server.windows import uninstall_service
            uninstall_service(service_name)
            system.ForceRemoveDir(install_path)
    else:
        try:
            script_path = os.path.join(settings.BASE_DIR, "utils", "install", "bash", "mongodb.sh")
            ConvertToUnixLineEndings(script_path)
            subprocess.run(['bash', script_path, 'uninstall'], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True


def is_mongodb_running(is_windows=True, simple_check=False):
    soft_paths = get_mongodb_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    c_content = ReadFile(conf_path)
    port = 27017
    if c_content:
        try:
            import yaml
            conf = yaml.safe_load(c_content)
            if conf:
                port = conf.get('net', {}).get('port', 27017)
        except Exception:
            port = 27017
    if simple_check:
        return is_service_running(port)
    if not is_service_running(port):
        return False
    if is_windows:
        try:
            result = subprocess.run('sc query MongoDB | find "STATE"', shell=True, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return "RUNNING" in result.stdout
        except subprocess.CalledProcessError:
            return False
    soft_name = 'mongod'
    info_list = GetProcessNameInfo(soft_name, {}, is_windows=is_windows)
    return len(info_list) > 0


def Start_Mongodb(is_windows=True):
    soft_paths = get_mongodb_path_info()
    if is_windows:
        exe_path = soft_paths['windows_abspath_mongod_path']
        conf_path = soft_paths['windows_abspath_conf_path']
        if os.path.exists(exe_path):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if not is_mongodb_running(is_windows=True):
                        command = f'net start MongoDB'
                        subprocess.run(command, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        return True
                    time.sleep(3)
                    if is_mongodb_running(is_windows=True):
                        return True
                except:
                    if attempt == max_retries - 1:
                        raise ValueError("MongoDB启动错误")
                    time.sleep(3)
        else:
            raise ValueError("MongoDB未安装")
    else:
        exe_path = soft_paths['linux_mongod_path']
        if os.path.exists(exe_path):
            try:
                if not is_mongodb_running(is_windows=False, simple_check=True):
                    subprocess.run(["systemctl", "start", "mongod"], check=True, timeout=30)
                else:
                    return True
                time.sleep(2)
                if is_mongodb_running(is_windows=False, simple_check=True):
                    return True
            except Exception as e:
                raise ValueError(f"启动MongoDB时发生错误: {e}")
            raise ValueError("MongoDB启动错误")
        else:
            raise ValueError("MongoDB未安装")


def Stop_Mongodb(is_windows=True):
    soft_paths = get_mongodb_path_info()
    if is_windows:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if is_mongodb_running(is_windows=is_windows):
                    command = 'net stop MongoDB'
                    subprocess.run(command, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    time.sleep(3)
                    if not is_mongodb_running(is_windows=True):
                        return True
            except:
                if attempt == max_retries - 1:
                    raise ValueError("MongoDB停止失败")
                time.sleep(2)
        if is_mongodb_running(is_windows=True):
            return False
    else:
        if is_mongodb_running(is_windows=is_windows):
            try:
                subprocess.run(["sudo", "systemctl", "stop", "mongod"], check=True)
                time.sleep(2)
                return not is_mongodb_running(is_windows=False)
            except Exception as e:
                raise ValueError(f"停止MongoDB时发生错误: {e}")
    return True


def Restart_Mongodb(is_windows=True):
    Stop_Mongodb(is_windows=is_windows)
    time.sleep(1)
    Start_Mongodb(is_windows=is_windows)


def RY_GET_MONGODB_CONF(is_windows=True):
    soft_paths = get_mongodb_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    return ReadFile(conf_path)


def RY_SAVE_MONGODB_CONF(conf="", is_windows=True):
    soft_paths = get_mongodb_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    WriteFile(conf_path, content=conf)


def RY_GET_MONGODB_INFO(is_windows=True):
    soft_paths = get_mongodb_path_info()
    info = {
        'install_path': soft_paths['install_abspath_path'],
        'data_path': soft_paths['data_abspath_path'],
        'port': RY_GET_MONGODB_PORT(),
        'version': ReadFile(os.path.join(soft_paths['install_abspath_path'], 'version.ry')) or '',
    }
    return info


def RY_GET_MONGODB_LOADSTATUS(is_windows=True):
    try:
        db_conn = Mongodb_Connect(local=True)
        if not db_conn:
            return {}
        server_status = db_conn.admin.command('serverStatus')
        connections = server_status.get('connections', {})
        db_stats = {}
        for db_name in db_conn.list_database_names():
            try:
                stats = db_conn[db_name].command('dbStats')
                db_stats[db_name] = stats.get('dataSize', 0)
            except Exception:
                pass
        total_size = sum(db_stats.values())
        db_conn.close()
        return {
            'connections': connections.get('current', 0),
            'available': connections.get('available', 0),
            'total_created': connections.get('totalCreated', 0),
            'total_size': total_size,
        }
    except Exception:
        return {}
