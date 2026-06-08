#!/usr/bin/python
# coding: utf-8

import os
import re
import time
import subprocess
import importlib
from utils.common import ReadFile, is_service_running, GetTmpPath, GetInstallPath, WriteFile, DeleteFile, GetLogsPath, RunCommandReturnCode, GetProcessNameInfo, generate_random_string, ConvertToUnixLineEndings, CreateInstallProcess, CleanupInstallProcess, SafeReadStderr, ReleaseMemory
from utils.security.files import download_url_file, get_file_name_from_url
from pathlib import Path
from utils.server.system import system
from django.conf import settings
from apps.systask.subprocessMg import job_subprocess_add


def get_pgsql_path_info():
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path, 'pgsql')
    install_path = root_path + '/pgsql'
    data_path = os.path.join(install_abspath_path, 'data')
    log_path = install_path + '/logs'
    return {
        'name': 'pgsql',
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path': install_abspath_path,
        'install_path': install_path,
        'data_abspath_path': data_path,
        'data_path': data_path,
        'windows_abspath_bin_path': os.path.join(install_abspath_path, 'bin'),
        'windows_abspath_postgres_path': os.path.join(install_abspath_path, 'bin', 'postgres.exe'),
        'windows_abspath_psql_path': os.path.join(install_abspath_path, 'bin', 'psql.exe'),
        'windows_abspath_pg_ctl_path': os.path.join(install_abspath_path, 'bin', 'pg_ctl.exe'),
        'windows_abspath_initdb_path': os.path.join(install_abspath_path, 'bin', 'initdb.exe'),
        'windows_abspath_conf_path': os.path.join(data_path, 'postgresql.conf'),
        'windows_abspath_hba_conf_path': os.path.join(data_path, 'pg_hba.conf'),
        'linux_psql_path': os.path.join(install_path, 'bin', 'psql'),
        'linux_pg_ctl_path': os.path.join(install_path, 'bin', 'pg_ctl'),
        'linux_initdb_path': os.path.join(install_path, 'bin', 'initdb'),
        'linux_conf_path': os.path.join(data_path, 'postgresql.conf'),
        'linux_hba_conf_path': os.path.join(data_path, 'pg_hba.conf'),
        'log_abspath_path': os.path.join(install_abspath_path, 'logs'),
        'log_path': log_path,
        'log_file_path': log_path + '/postgresql.log',
    }


def pgsql_install_call_back(version={}, call_back=None, ok=True):
    if call_back:
        job_id = version.get('job_id')
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id, version=version, ok=ok)


def Install_Pgsql(type=2, version={}, is_windows=True, call_back=None):
    try:
        name = version['name']
        log = version.get('log', None)
        is_write_log = False
        log_path = ""
        if log:
            is_write_log = True
            log_path = os.path.join(os.path.abspath(GetLogsPath()), name, log)
        WriteFile(log_path, "-------------------安装任务已开始-------------------\n", mode='a', write=is_write_log)
        if is_service_running(5432):
            error_msg = "[error]检测到本机已安装并开启了PostgreSQL(5432)服务，请关闭后再试!!!"
            WriteFile(log_path, error_msg + '\n', mode='a', write=is_write_log)
            raise ValueError(error_msg)
        download_url = version.get('url', None)
        WriteFile(log_path, "开始下载【%s】安装文件,文件地址：%s\n" % (name, download_url), mode='a', write=is_write_log)
        filename = get_file_name_from_url(download_url)
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_pgsql_path_info()
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
            pgsql_extracted_folder = os.path.join(install_base_directory, 'pgsql')
            src_folder = os.path.join(install_base_directory, Path(filename).stem)
            if os.path.exists(pgsql_extracted_folder) and not os.path.exists(install_directory):
                os.rename(pgsql_extracted_folder, install_directory)
            elif os.path.exists(src_folder) and not os.path.exists(install_directory):
                os.rename(src_folder, install_directory)
            WriteFile(log_path, "解压成功\n", mode='a', write=is_write_log)
            version_file = os.path.join(install_directory, 'version.ry')
            WriteFile(version_file, version['c_version'])
            WriteFile(log_path, "正在初始化PostgreSQL数据库...\n", mode='a', write=is_write_log)
            initdb_path = soft_paths['windows_abspath_initdb_path']
            data_path = soft_paths['data_abspath_path']
            if not os.path.exists(data_path):
                os.makedirs(data_path)
            init_cmd = f'"{initdb_path}" -D "{data_path}" -U postgres -E UTF8 --locale=C'
            result = subprocess.run(init_cmd, cwd=soft_paths['windows_abspath_bin_path'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0:
                raise ValueError(f"初始化PostgreSQL数据库失败: {result.stderr}")
            WriteFile(log_path, "初始化PostgreSQL数据库成功\n", mode='a', write=is_write_log)
            conf_path = soft_paths['windows_abspath_conf_path']
            RY_SET_DEFAULT_PGSQL_CONFIG(conf_path, is_windows=True)
            log_dir = soft_paths['log_abspath_path']
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            WriteFile(soft_paths['log_file_path'], "")
        else:
            script_path = GetInstallPath() + '/ruyi/utils/install/bash/pgsql.sh'
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
                    if not os.path.exists(soft_paths['install_path'] + '/bin/psql'):
                        raise ValueError(r_stderr.strip()[:2000])
            finally:
                CleanupInstallProcess(r_process, version['job_id'])
                r_process = None
            version_file = os.path.join(install_directory, 'version.ry')
            WriteFile(version_file, version['c_version'])
        if is_windows:
            WriteFile(log_path, "正在安装PostgreSQL为系统服务...\n", mode='a', write=is_write_log)
            from utils.server.windows import install_as_service, create_service_account, check_user_exists, delete_user
            sys_username = "pgsql"
            sys_password = generate_random_string(32, special=False)
            if check_user_exists(sys_username):
                delete_user(sys_username)
            isok, msg = create_service_account(username=sys_username, password=sys_password, description="Account for PostgreSQL service", allow_service_logon=True)
            if not isok:
                WriteFile(log_path, f"创建服务账号失败：{msg}，尝试直接安装服务\n", mode='a', write=is_write_log)
            pg_ctl_path = soft_paths['windows_abspath_pg_ctl_path']
            data_path = soft_paths['data_abspath_path']
            service_name = "PostgreSQL"
            reg_cmd = f'"{pg_ctl_path}" register -N {service_name} -D "{data_path}"'
            subprocess.run(reg_cmd, shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        WriteFile(log_path, "正在启动PostgreSQL服务...\n", mode='a', write=is_write_log)
        Start_Pgsql(is_windows=is_windows)
        WriteFile(log_path, "PostgreSQL启动成功\n", mode='a', write=is_write_log)
        time.sleep(1)
        root_pass = generate_random_string(16, special=False)
        WriteFile(log_path, "开始设置PostgreSQL的postgres密码...\n", mode='a', write=is_write_log)
        RY_SET_PGSQL_ROOT_PASS(root_pass, is_windows=is_windows)
        WriteFile(log_path, "设置PostgreSQL的postgres密码成功\n", mode='a', write=is_write_log)
        WriteFile(log_path, "正在安装Python依赖 psycopg2-binary...\n", mode='a', write=is_write_log)
        try:
            from utils.common import pip_install_package
            pip_install_package('psycopg2-binary')
            WriteFile(log_path, "psycopg2-binary安装成功\n", mode='a', write=is_write_log)
        except Exception as pip_err:
            WriteFile(log_path, f"psycopg2-binary安装失败：{pip_err}，扩展管理功能可能不可用\n", mode='a', write=is_write_log)
        version['password'] = root_pass
        DeleteFile(save_path, empty_tips=False)
        WriteFile(log_path, "安装成功，安装目录：%s\n" % install_directory, mode='a', write=is_write_log)
        version['install_path'] = install_directory
        pgsql_install_call_back(version=version, call_back=call_back, ok=True)
        WriteFile(log_path, "-------------------安装任务已结束-------------------\n", mode='a', write=is_write_log)
        version.clear()
        soft_paths.clear()
        ReleaseMemory()
        return True
    except Exception as e:
        WriteFile(log_path, f"【错误】异常信息如下：\n{e}", mode='a', write=is_write_log)
        pgsql_install_call_back(version=version, call_back=call_back, ok=False)
        version.clear()
        ReleaseMemory()
        return False


def Uninstall_Pgsql(is_windows=True):
    soft_paths = get_pgsql_path_info()
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            Stop_Pgsql(is_windows=is_windows)
            time.sleep(0.5)
            pg_ctl_path = soft_paths['windows_abspath_pg_ctl_path']
            subprocess.run(f'"{pg_ctl_path}" unregister -N PostgreSQL', shell=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            from utils.server.windows import uninstall_service, check_user_exists, delete_user
            uninstall_service("PostgreSQL")
            if check_user_exists("pgsql"):
                delete_user("pgsql")
            system.ForceRemoveDir(install_path)
    else:
        try:
            script_path = os.path.join(settings.BASE_DIR, "utils", "install", "bash", "pgsql.sh")
            ConvertToUnixLineEndings(script_path)
            subprocess.run(['bash', script_path, 'uninstall'], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True


def is_pgsql_running(is_windows=True, simple_check=False):
    soft_paths = get_pgsql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    c_content = ReadFile(conf_path)
    if not c_content:
        return False
    port_match = re.search(r"port\s*=\s*(\d+)", c_content)
    if not port_match:
        port = 5432
    else:
        port = int(port_match.group(1))
    if simple_check:
        return is_service_running(port)
    if not is_service_running(port):
        return False
    if is_windows:
        try:
            result = subprocess.run('sc query PostgreSQL | find "STATE"', shell=True, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return "RUNNING" in result.stdout
        except subprocess.CalledProcessError:
            return False
    soft_name = 'postgres'
    info_list = GetProcessNameInfo(soft_name, {}, is_windows=is_windows)
    return len(info_list) > 0


def Start_Pgsql(is_windows=True):
    soft_paths = get_pgsql_path_info()
    if is_windows:
        exe_path = soft_paths['windows_abspath_pg_ctl_path']
        data_path = soft_paths['data_abspath_path']
        if os.path.exists(exe_path):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if not is_pgsql_running(is_windows=True):
                        command = f'"{exe_path}" start -D "{data_path}" -l "{soft_paths["log_file_path"]}"'
                        subprocess.run(command, cwd=soft_paths['windows_abspath_bin_path'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        return True
                    time.sleep(2)
                    if is_pgsql_running(is_windows=True):
                        return True
                except:
                    if attempt == max_retries - 1:
                        raise ValueError("PostgreSQL启动错误")
                    time.sleep(3)
        else:
            raise ValueError("PostgreSQL未安装")
    else:
        exe_path = soft_paths['linux_pg_ctl_path']
        if os.path.exists(exe_path):
            try:
                if not is_pgsql_running(is_windows=False, simple_check=True):
                    subprocess.run(["systemctl", "start", "postgresql"], check=True, timeout=30)
                else:
                    return True
                time.sleep(1)
                if is_pgsql_running(is_windows=False, simple_check=True):
                    return True
            except Exception as e:
                raise ValueError(f"启动PostgreSQL时发生错误: {e}")
            raise ValueError("PostgreSQL启动错误")
        else:
            raise ValueError("PostgreSQL未安装")


def Stop_Pgsql(is_windows=True):
    soft_paths = get_pgsql_path_info()
    if is_windows:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if is_pgsql_running(is_windows=is_windows):
                    exe_path = soft_paths['windows_abspath_pg_ctl_path']
                    data_path = soft_paths['data_abspath_path']
                    command = f'"{exe_path}" stop -D "{data_path}" -m fast'
                    subprocess.run(command, cwd=soft_paths['windows_abspath_bin_path'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    time.sleep(2)
                    if not is_pgsql_running(is_windows=True):
                        return True
            except:
                if attempt == max_retries - 1:
                    raise ValueError("PostgreSQL停止失败")
                time.sleep(2)
        if is_pgsql_running(is_windows=True):
            return False
    else:
        if is_pgsql_running(is_windows=is_windows):
            try:
                subprocess.run(["sudo", "systemctl", "stop", "postgresql"], check=True)
                time.sleep(2)
                return not is_pgsql_running(is_windows=False)
            except Exception as e:
                raise ValueError(f"停止PostgreSQL时发生错误: {e}")
    return True


def Restart_Pgsql(is_windows=True):
    Stop_Pgsql(is_windows=is_windows)
    time.sleep(0.5)
    Start_Pgsql(is_windows=is_windows)


def Reload_Pgsql(is_windows=True):
    soft_paths = get_pgsql_path_info()
    if is_windows:
        exe_path = soft_paths['windows_abspath_pg_ctl_path']
        data_path = soft_paths['data_abspath_path']
        if os.path.exists(exe_path):
            if is_pgsql_running(is_windows=True):
                command = f'"{exe_path}" reload -D "{data_path}"'
                subprocess.run(command, cwd=soft_paths['windows_abspath_bin_path'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                return True
            raise ValueError("PostgreSQL未运行")
        raise ValueError("PostgreSQL未安装")
    else:
        if is_pgsql_running(is_windows=False):
            subprocess.run(["sudo", "systemctl", "reload", "postgresql"], check=True)
            return True
        raise ValueError("PostgreSQL未运行")


def RY_GET_PGSQL_CONF(is_windows=True):
    soft_paths = get_pgsql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    return ReadFile(conf_path)


def RY_SAVE_PGSQL_CONF(conf="", is_windows=True):
    soft_paths = get_pgsql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    WriteFile(conf_path, content=conf)


def RY_GET_PGSQL_PORT(is_windows=True):
    conf = RY_GET_PGSQL_CONF(is_windows=is_windows)
    if not conf:
        return 5432
    port_match = re.search(r"port\s*=\s*(\d+)", conf)
    if port_match:
        return int(port_match.group(1))
    return 5432


def RY_SET_DEFAULT_PGSQL_CONFIG(conf_path, is_windows=True, log_dir=None):
    if log_dir is None:
        soft_paths = get_pgsql_path_info()
        log_dir = soft_paths['log_abspath_path']
    default_conf = """# -----------------------------
# PostgreSQL configuration file
# -----------------------------
listen_addresses = '*'
port = 5432
max_connections = 100
shared_buffers = 128MB
dynamic_shared_memory_type = windows
log_destination = 'stderr'
logging_collector = on
log_directory = '%s'
log_filename = 'postgresql.log'
log_truncate_on_rotation = on
datestyle = 'iso, mdy'
timezone = 'UTC'
lc_messages = 'C'
lc_monetary = 'C'
lc_numeric = 'C'
lc_time = 'C'
default_text_search_config = 'pg_catalog.english'
""" % log_dir.replace('\\', '/')
    if not is_windows:
        default_conf = default_conf.replace("dynamic_shared_memory_type = windows", "dynamic_shared_memory_type = posix")
    WriteFile(conf_path, default_conf)


def RY_GET_PGSQL_ROOT_PASS(is_windows=True):
    from apps.sysshop.models import RySoftShop
    soft_ins = RySoftShop.objects.filter(name='pgsql', installed=True).first()
    if soft_ins and soft_ins.password:
        return soft_ins.password
    return ""


def RY_SET_PGSQL_ROOT_PASS(passwd, is_windows=True):
    soft_paths = get_pgsql_path_info()
    psql_path = soft_paths['windows_abspath_psql_path'] if is_windows else soft_paths['linux_psql_path']
    if not os.path.exists(psql_path):
        raise ValueError("PostgreSQL未安装")
    port = RY_GET_PGSQL_PORT(is_windows=is_windows)
    env = os.environ.copy()
    env['PGPASSWORD'] = RY_GET_PGSQL_ROOT_PASS(is_windows=is_windows) or ''
    alter_cmd = f'"{psql_path}" -U postgres -p {port} -c "ALTER USER postgres WITH PASSWORD \'{passwd}\';"'
    kwargs = dict(shell=True, capture_output=True, text=True, env=env, cwd=soft_paths['windows_abspath_bin_path'] if is_windows else soft_paths['install_path'])
    if is_windows:
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    result = subprocess.run(alter_cmd, **kwargs)
    if result.returncode != 0 and 'does not exist' not in result.stderr:
        env['PGPASSWORD'] = ''
        alter_cmd = f'"{psql_path}" -U postgres -p {port} -c "ALTER USER postgres WITH PASSWORD \'{passwd}\';"'
        kwargs['env'] = env
        result = subprocess.run(alter_cmd, **kwargs)
    from apps.sysshop.models import RySoftShop
    RySoftShop.objects.filter(name='pgsql').update(password=passwd)


def Pgsql_Connect(db_host="127.0.0.1", db_port=5432, db_user="postgres", db_password="", db_name="postgres", local=True, charset="UTF8"):
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        return None
    if local:
        db_host = "127.0.0.1"
        db_user = "postgres"
        db_port = RY_GET_PGSQL_PORT()
        db_password = RY_GET_PGSQL_ROOT_PASS()
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=int(db_port),
            user=db_user,
            password=db_password or "",
            database=db_name,
            connect_timeout=5,
        )
        conn.autocommit = True
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except Exception:
        return None


def RY_CHECK_PGSQL_DATANAME_EXISTS(db_conn, db_name):
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='%s'" % db_name)
        result = cursor.fetchone()
        return result is not None
    except Exception:
        return False


def RY_CREATE_PGSQL_DATANAME(db_conn, db_name):
    try:
        cursor = db_conn.cursor()
        cursor.execute('CREATE DATABASE "%s" ENCODING \'UTF8\'' % db_name)
        return True
    except Exception as e:
        return str(e)


def RY_CREATE_PGSQL_USER(db_conn, db_name, db_user, db_pass):
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='%s'" % db_user)
        user_exists = cursor.fetchone() is not None
        if not user_exists:
            cursor.execute("CREATE USER \"%s\" WITH PASSWORD '%s'" % (db_user, db_pass))
        cursor.execute('GRANT ALL PRIVILEGES ON DATABASE "%s" TO "%s"' % (db_name, db_user))
        return True
    except Exception as e:
        return str(e)


def RY_DELETE_PGSQL_DATABASE(db_conn, db_name, db_user=""):
    try:
        cursor = db_conn.cursor()
        cursor.execute('DROP DATABASE IF EXISTS "%s"' % db_name)
        if db_user and db_user != 'postgres':
            cursor.execute('DROP USER IF EXISTS "%s"' % db_user)
        return True
    except Exception as e:
        return str(e)


def RY_RESET_PGSQL_USER_PASS(db_conn, db_user, db_pass):
    try:
        cursor = db_conn.cursor()
        cursor.execute("ALTER USER \"%s\" WITH PASSWORD '%s'" % (db_user, db_pass))
        return True
    except Exception as e:
        return str(e)


def RY_BACKUP_PGSQL_DATABASE(db_info={}, is_windows=True):
    soft_paths = get_pgsql_path_info()
    dump_path = os.path.join(soft_paths['windows_abspath_bin_path'] if is_windows else soft_paths['install_path'], 'pg_dump')
    if is_windows:
        dump_path = os.path.join(soft_paths['windows_abspath_bin_path'], 'pg_dump.exe')
    if not os.path.exists(dump_path):
        return False, "", 0
    from utils.common import GetBackupPath
    backup_base = os.path.join(GetBackupPath(), "database", "pgsql")
    if not os.path.exists(backup_base):
        os.makedirs(backup_base)
    db_name = db_info.get('db_name', '')
    file_name = "%s_%s.sql" % (time.strftime('%Y%m%d_%H%M%S', time.localtime()), db_name)
    dst_path = os.path.join(backup_base, file_name)
    env = os.environ.copy()
    env['PGPASSWORD'] = db_info.get('db_pass', '')
    cmd = '"%s" -h %s -p %s -U %s -d %s -f "%s"' % (
        dump_path,
        db_info.get('db_host', '127.0.0.1'),
        db_info.get('db_port', 5432),
        db_info.get('db_user', 'postgres'),
        db_name,
        dst_path
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env, cwd=soft_paths['windows_abspath_bin_path'] if is_windows else soft_paths['install_path'], creationflags=subprocess.CREATE_NO_WINDOW if is_windows else 0)
    if os.path.exists(dst_path):
        file_size = os.path.getsize(dst_path)
        return True, dst_path, file_size
    return False, "", 0


def RY_IMPORT_PGSQL_SQL(db_info={}, sql_file="", is_windows=True):
    soft_paths = get_pgsql_path_info()
    psql_path = os.path.join(soft_paths['windows_abspath_bin_path'] if is_windows else soft_paths['install_path'], 'psql')
    if is_windows:
        psql_path = os.path.join(soft_paths['windows_abspath_bin_path'], 'psql.exe')
    if not os.path.exists(psql_path):
        return False, "psql not found"
    env = os.environ.copy()
    env['PGPASSWORD'] = db_info.get('db_pass', '')
    cmd = '"%s" -h %s -p %s -U %s -d %s -f "%s"' % (
        psql_path,
        db_info.get('db_host', '127.0.0.1'),
        db_info.get('db_port', 5432),
        db_info.get('db_user', 'postgres'),
        db_info.get('db_name', ''),
        sql_file
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env, cwd=soft_paths['windows_abspath_bin_path'] if is_windows else soft_paths['install_path'], creationflags=subprocess.CREATE_NO_WINDOW if is_windows else 0)
    if result.returncode == 0:
        return True, ""
    return False, result.stderr[:500]


def RY_GET_PGSQL_INFO(is_windows=True):
    soft_paths = get_pgsql_path_info()
    info = {
        'install_path': soft_paths['install_abspath_path'],
        'data_path': soft_paths['data_abspath_path'],
        'port': RY_GET_PGSQL_PORT(is_windows=is_windows),
        'version': ReadFile(os.path.join(soft_paths['install_abspath_path'], 'version.ry')) or '',
    }
    return info


def RY_SET_PGSQL_PORT(port, is_windows=True):
    conf = RY_GET_PGSQL_CONF(is_windows=is_windows)
    if not conf:
        raise ValueError("配置文件读取失败")
    conf = re.sub(r"port\s*=\s*\d+", "port = %s" % port, conf)
    soft_paths = get_pgsql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    WriteFile(conf_path, conf)


def RY_GET_PGSQL_LOADSTATUS(is_windows=True):
    try:
        db_conn = Pgsql_Connect(local=True)
        if not db_conn:
            return {}
        cursor = db_conn.cursor()
        cursor.execute("SELECT count(*) FROM pg_stat_activity")
        connections = cursor.fetchone()[0]
        cursor.execute("SELECT pg_database_size(datname) FROM pg_database WHERE datistemplate = false")
        total_size = sum([row[0] for row in cursor.fetchall()])
        db_conn.close()
        return {
            'connections': connections,
            'total_size': total_size,
        }
    except:
        return {}


def RY_GET_PGSQL_PERFORMANCE(is_windows=True):
    conf = RY_GET_PGSQL_CONF(is_windows=is_windows)
    if not conf:
        return {}
    result = {}
    perf_keys = {
        'max_connections': r"max_connections\s*=\s*(\d+)",
        'shared_buffers': r"shared_buffers\s*=\s*(\S+)",
        'work_mem': r"work_mem\s*=\s*(\S+)",
        'maintenance_work_mem': r"maintenance_work_mem\s*=\s*(\S+)",
        'effective_cache_size': r"effective_cache_size\s*=\s*(\S+)",
    }
    for key, pattern in perf_keys.items():
        match = re.search(pattern, conf)
        result[key] = match.group(1) if match else ''
    return result


def RY_SET_PGSQL_PERFORMANCE(cont={}, is_windows=True):
    conf = RY_GET_PGSQL_CONF(is_windows=is_windows)
    if not conf:
        return False
    for key, value in cont.items():
        if value:
            pattern = r"(#?\s*%s\s*=\s*)\S+" % key
            conf = re.sub(pattern, "%s = %s" % (key, value), conf)
    soft_paths = get_pgsql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    WriteFile(conf_path, conf)
    return True


def RY_GET_PGSQL_EXTENSIONS(is_windows=True):
    """获取PostgreSQL已安装的扩展列表及pgvector状态"""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        raise ValueError("psycopg2未安装，请先安装 psycopg2-binary")
    db_port = RY_GET_PGSQL_PORT(is_windows=is_windows)
    db_password = RY_GET_PGSQL_ROOT_PASS(is_windows=is_windows)
    try:
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=int(db_port),
            user="postgres",
            password=db_password or "",
            database="postgres",
            connect_timeout=5,
        )
        conn.autocommit = True
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    except Exception as e:
        raise ValueError(f"PostgreSQL连接失败(端口:{db_port})：{e}，请检查密码配置或服务是否运行")
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, default_version, installed_version, comment FROM pg_available_extensions WHERE installed_version IS NOT NULL ORDER BY name")
        extensions = []
        for row in cur.fetchall():
            extensions.append({
                'name': row[0],
                'default_version': row[1] or '',
                'installed_version': row[2] or '',
                'comment': row[3] or '',
            })
        return extensions
    except Exception as e:
        raise ValueError(f"查询扩展列表失败: {e}")
    finally:
        conn.close()


def RY_INSTALL_PGSQL_EXTENSION(ext_name, is_windows=True):
    """安装PostgreSQL扩展"""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        raise ValueError("psycopg2未安装，请先安装 psycopg2-binary")
    db_port = RY_GET_PGSQL_PORT(is_windows=is_windows)
    db_password = RY_GET_PGSQL_ROOT_PASS(is_windows=is_windows)
    try:
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=int(db_port),
            user="postgres",
            password=db_password or "",
            database="postgres",
            connect_timeout=5,
        )
        conn.autocommit = True
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    except Exception as e:
        raise ValueError(f"PostgreSQL连接失败(端口:{db_port})：{e}，请检查密码配置或服务是否运行")
    try:
        cur = conn.cursor()
        cur.execute('CREATE EXTENSION IF NOT EXISTS "%s"' % ext_name)
        return True
    except Exception as e:
        raise ValueError(f"安装扩展 {ext_name} 失败: {e}")
    finally:
        conn.close()


def RY_UNINSTALL_PGSQL_EXTENSION(ext_name, is_windows=True):
    """卸载PostgreSQL扩展"""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        raise ValueError("psycopg2未安装，请先安装 psycopg2-binary")
    db_port = RY_GET_PGSQL_PORT(is_windows=is_windows)
    db_password = RY_GET_PGSQL_ROOT_PASS(is_windows=is_windows)
    try:
        conn = psycopg2.connect(
            host="127.0.0.1",
            port=int(db_port),
            user="postgres",
            password=db_password or "",
            database="postgres",
            connect_timeout=5,
        )
        conn.autocommit = True
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    except Exception as e:
        raise ValueError(f"PostgreSQL连接失败(端口:{db_port})：{e}，请检查密码配置或服务是否运行")
    try:
        cur = conn.cursor()
        cur.execute('DROP EXTENSION IF EXISTS "%s"' % ext_name)
        return True
    except Exception as e:
        raise ValueError(f"卸载扩展 {ext_name} 失败: {e}")
    finally:
        conn.close()
