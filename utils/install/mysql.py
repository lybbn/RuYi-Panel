#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-04-22
# +-------------------------------------------------------------------
# | EditDate: 2024-04-22
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Mysql安装/卸载
# ------------------------------

import os
import re
import time
import zipfile
import tarfile
import psutil
import configparser
from utils.common import DeleteFile,GetRandomSet,ReadFile,GetBackupPath,is_service_running,GetTmpPath,GetInstallPath,WriteFile,DeleteFile,GetLogsPath,RunCommandReturnCode,GetPidCpuPercent,RunCommand,GetProcessNameInfo,generate_random_string
from utils.security.files import download_url_file,get_file_name_from_url
from pathlib import Path
import subprocess
import importlib
from utils.server.system import system
from apps.sysshop.models import RySoftShop
from utils.ruyiclass.mysqlClass import MysqlClient
from apps.sysbak.models import RuyiBackup
from django.conf import settings

def is_sql_result_error(result):
    result = str(result)
    if "MySQLdb" in result: return True,'MySQLdb组件缺失!'
    if "2002," in result or '2003,' in result: return True, '数据库连接失败!'
    if "using password:" in result: return True, '数据库密码错误!'
    if "Connection refused" in result: return True, '数据库连接失败!'
    if "1133," in result: return True, '数据库用户不存在!'
    if "3679," in result: return True, '从数据库删除失败，数据目录不存在!'
    if "1141," in result: return True, '数据库用户添加失败!'
    if "1142," in result: return True, '数据库用户执行命令被拒绝!'
    return False,"ok"

def get_mysql_path_info():
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,'mysql')
    install_path = root_path+'/mysql'
    log_path = install_path+'/logs'
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'windows_abspath_mysqld_path':os.path.join(install_abspath_path,'bin','mysqld.exe'),
        'windows_abspath_mysql_path':os.path.join(install_abspath_path,'bin','mysql.exe'),
        'windows_abspath_mysqladmin_path':os.path.join(install_abspath_path,'bin','mysqladmin.exe'),
        'windows_abspath_conf_path':os.path.join(install_abspath_path,'conf','my.ini'),
        'windows_abspath_mysqldump_path':os.path.join(install_abspath_path,'bin','mysqldump.exe'),
        'linux_mysql_path':os.path.join(install_path,'bin','mysql'),
        'linux_mysqld_path':os.path.join(install_path,'bin','mysqld'),
        'linux_mysqladmin_path':os.path.join(install_path,'bin','mysqladmin'),
        'linux_conf_path':os.path.join('/etc','my.cnf'),
        'linux_mysqldump_path':os.path.join(install_path,'bin','mysqldump'),
        'data_abspath_path':os.path.join(root_abspath_path,'data'),
        'log_abspath_path':os.path.join(install_abspath_path,'logs'),
        'log_path':log_path,
        'error_log_path':log_path+'/mysql_error.log',
        'slow_log_path':log_path+'/mysql_slow.log',
    }

def mysql_install_call_back(version={},call_back=None,ok=True):
    if call_back:
        job_id = version['job_id']
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id,version=version,ok=ok)
    
def Install_Mysql(type=2,version={},is_windows=True,call_back=None):
    """
    @name 安装mysql
    @parma call_back 为执行回调函数的方法路径
    @author lybbn<2024-08-20>
    """
    try:
        name = version['name']
        log = version.get('log',None)#是否开启日志
        is_write_log = False
        log_path = ""
        if log:
            is_write_log = True
            log_path = os.path.join(os.path.abspath(GetLogsPath()),name,log)
        WriteFile(log_path,"-------------------安装任务已开始-------------------\n",mode='a',write=is_write_log)
        #检测系统是否已安装过mysql（主要检测3306端口是否被占用）
        if is_service_running(3306):
            error_msg = "[error]检测到本机已安装并开启了mysql(3306)服务，请关闭后再试!!!"
            WriteFile(log_path,error_msg+'\n',mode='a',write=is_write_log)
            raise ValueError(error_msg)
        download_url = version.get('url',None)
        WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
        filename = get_file_name_from_url(download_url)
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_mysql_path_info()
        install_base_directory = soft_paths['root_abspath_path']
        install_directory = soft_paths['install_abspath_path']
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        save_path = os.path.join(save_directory, filename)
        #开始下载
        ok,msg = download_url_file(url=download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
        if not ok:
            WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
            raise ValueError(msg)
        if is_windows:
            WriteFile(log_path,"【%s】下载完成\n"%filename,mode='a',write=is_write_log)
            src_folder = os.path.join(install_base_directory,Path(filename).stem)
            WriteFile(log_path,"正在解压安装文件到%s\n"%install_directory,mode='a',write=is_write_log)
            from apps.systask.tasks import func_unzip
            func_unzip(save_path,install_base_directory)
            # 如果目标文件夹已经存在，先删除它
            system.ForceRemoveDir(install_directory)
            # 重命名源文件夹为目标文件夹
            os.rename(src_folder, install_directory)
            WriteFile(log_path,"解压成功\n",mode='a',write=is_write_log)
            # 新建版本文件
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(log_path,"正在配置mysql...\n",mode='a',write=is_write_log)
            WriteFile(soft_paths['windows_abspath_conf_path'],RY_GET_MYSQL_CONFIG(version=version['c_version'],is_windows=True))
            mysql_error_log_file_path = soft_paths['error_log_path']
            mysql_slow_file_path = soft_paths['slow_log_path']
            WriteFile(mysql_error_log_file_path,"")
            WriteFile(mysql_slow_file_path,"")
        else:
            r_process = subprocess.Popen(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","mysql.sh"),'install',version['c_version']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # 持续读取输出
            while True:
                r_output = r_process.stdout.readline()
                if r_output == '' and r_process.poll() is not None:
                    break
                if r_output:
                    WriteFile(log_path,f"{r_output.strip()}\n",mode='a',write=is_write_log)

            # 获取标准错误
            r_stderr = r_process.stderr.read()
            if r_stderr:
                if not os.path.exists(soft_paths['linux_mysql_path']):
                    raise ValueError(r_stderr.strip())
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(soft_paths['linux_conf_path'],RY_GET_MYSQL_CONFIG(version=version['c_version'],is_windows=False))
            mysql_error_log_file_path = soft_paths['error_log_path']
            mysql_slow_file_path = soft_paths['slow_log_path']
            WriteFile(mysql_error_log_file_path,"")
            WriteFile(mysql_slow_file_path,"")
            
        init_res = Initialize_Mysql(is_windows=is_windows)
        if not init_res:
            raise ValueError("[error]初始化mysql错误!!!")
        time.sleep(0.1)
        WriteFile(log_path,"正在启动mysql服务...\n",mode='a',write=is_write_log)
        Start_Mysql(is_windows=is_windows)
        WriteFile(log_path,"mysql启动成功\n",mode='a',write=is_write_log)
        time.sleep(0.5)
        root_pass = generate_random_string(16)
        RY_SET_MYSQL_ROOT_PASS(root_pass,is_windows=is_windows)
        WriteFile(log_path,f"设置mysql的root密码成功，root密码：{root_pass}\n",mode='a',write=is_write_log)
        version['password'] = root_pass
        # 删除下载的文件
        DeleteFile(save_path,empty_tips=False)
        WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        version['install_path'] = install_directory
        Drop_Test_Databases(is_windows=is_windows)
        mysql_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        mysql_install_call_back(version=version,call_back=call_back,ok=False)
        return False

def Uninstall_Mysql(is_windows=True):
    """
    @name 卸载mysql
    @author lybbn<2024-08-20>
    """
    soft_paths = get_mysql_path_info()
    install_path = soft_paths['install_abspath_path']
    data_path = soft_paths['data_abspath_path']
    if is_windows:
        if os.path.exists(install_path):
            Stop_Mysql(is_windows=is_windows)
            time.sleep(0.1)
            system.ForceRemoveDir(install_path)
            system.ForceRemoveDir(data_path)
    else:
        try:
            subprocess.run(['bash', os.path.join(settings.BASE_DIR,"utils","install","bash","mysql.sh"),'uninstall'], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True

def is_mysql_running(is_windows=True,simple_check=False):
    soft_paths = get_mysql_path_info()
    conf_path =soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    c_content = ReadFile(conf_path)
    if not c_content:
        return False
    port = int(re.search(r"port\s*=\s*([0-9]+)",c_content).groups()[0])
    if simple_check:
        if is_service_running(port):
            return True
        return False
    if not is_service_running(port):
        return False
    soft_name ='mysqld.exe' if is_windows else "mysqld"
    info_list = GetProcessNameInfo(soft_name,{},is_windows=is_windows)
    if len(info_list)>0:
        return True
    return False

def Start_Mysql(is_windows=True):
    """
    @name 启动mysql
    @author lybbn<2024-08-20>
    """
    soft_paths = get_mysql_path_info()
    if is_windows:
        exe_path = soft_paths['windows_abspath_mysqld_path']
        conf_path = soft_paths['windows_abspath_conf_path']
        r_status = False
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if not is_mysql_running(is_windows=True):
                    command = f'"{exe_path}" --defaults-file="{conf_path}"'
                    subprocess.Popen(command,cwd=soft_paths['install_path'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)#CREATE_NEW_CONSOLE 新窗口 、CREATE_NO_WINDOW 隐藏窗口
                else:
                    r_status = True
                time.sleep(1)
                if not r_status and is_mysql_running(is_windows=True):
                    r_status = True
            except Exception as e:
                raise ValueError(f"启动Mysql时发生错误: {e}")
            if not r_status:
                raise ValueError(f"Mysql启动错误")
        else:
            raise ValueError(f"Mysql未安装")
    else:
        exe_path = soft_paths['linux_mysqld_path']
        r_status = False
        # 确保路径存在
        if os.path.exists(exe_path):
            try:
                if not is_mysql_running(is_windows=False):
                    subprocess.run(["sudo", "systemctl", "start", "mysql"], check=True)
                else:
                    r_status = True
                time.sleep(1)
                if not r_status and is_mysql_running(is_windows=False):
                    r_status = True
            except Exception as e:
                raise ValueError(f"启动Mysql时发生错误: {e}")
            if not r_status:
                raise ValueError(f"Mysql启动错误")
        else:
            raise ValueError(f"Mysql未安装")

def Stop_Mysql(is_windows=True):
    """
    @name 停止mysql
    @author lybbn<2024-08-20>
    """
    soft_name ='mysqld.exe' if is_windows else "mysqld"
    if is_windows:
        if is_mysql_running(is_windows=is_windows):
            import signal
            info_list = GetProcessNameInfo(soft_name,{},is_windows=is_windows)
            for i in info_list:
                os.kill(int(i['ProcessId']), signal.SIGTERM)
            return True
    else:
        if is_mysql_running(is_windows=is_windows):
            try:
                subprocess.run(["sudo", "systemctl", "stop", "mysql"], check=True)
                time.sleep(1)
                if is_mysql_running(is_windows=False):
                    return False
                else:
                    return True
            except Exception as e:
                raise ValueError(f"停止Mysql时发生错误: {e}")
    return True

def Restart_Mysql(is_windows=True):
    """
    @name 重启mysql
    @author lybbn<2024-08-20>
    """
    Stop_Mysql(is_windows=is_windows)
    time.sleep(0.1)
    Start_Mysql(is_windows=is_windows)

def Reload_Mysql(is_windows=True):
    """
    @name 重载mysql
    @author lybbn<2024-08-20>
    """
    soft_paths = get_mysql_path_info()
    mysqladmin =soft_paths['windows_abspath_mysqladmin_path'] if is_windows else soft_paths['linux_mysqladmin_path']
    root_pass = RY_GET_MYSQL_ROOT_PASS()
    # 确保路径存在
    if os.path.exists(mysqladmin):
        if is_mysql_running(is_windows=is_windows):
            try:
                env = os.environ.copy()
                env['MYSQL_PWD'] = root_pass#避免命令行直接使用密码
                result = subprocess.run([mysqladmin, '-u', 'root', 'reload'],cwd=soft_paths['install_path'],check=True, text=True,env=env)
                return True
            except Exception as e:
                raise ValueError(f"重载Mysql时发生错误: {e}")
        else:
            raise ValueError(f"Mysql未运行")
    else:
        raise ValueError(f"Mysql未安装")

def Initialize_Mysql(is_windows=True):
    """
    @name 初始化mysql
    @author lybbn<2024-08-20>
    """
    soft_paths = get_mysql_path_info()
    install_path = soft_paths['install_path']
    data_path = soft_paths['data_abspath_path'].replace("\\","/")
    mysqld =soft_paths['windows_abspath_mysqld_path'] if is_windows else soft_paths['linux_mysqld_path']
    if not os.path.exists(data_path):
        os.makedirs(data_path)
    if not is_windows:
        command_str = f"{mysqld} --initialize-insecure --basedir={install_path} --datadir={data_path} --user=mysql"
        RunCommandReturnCode(f"chown -R mysql:mysql {soft_paths['log_abspath_path']}")
        code = RunCommandReturnCode(command_str,cwd=install_path,timeout=120)
    else:
        command_str = [mysqld,"--initialize-insecure",f"--basedir={install_path}",f"--datadir={data_path}"]
        code = RunCommandReturnCode(command_str,cwd=install_path)
    return True if code == 0 else False

def Drop_Test_Databases(is_windows=True):
    if is_mysql_running(is_windows=is_windows):
        conn = Mysql_Connect()
        if conn:
            conn.execute("DROP DATABASE test;")
            conn.execute("delete from mysql.user where user='';")
            conn.execute("flush privileges;")

def RY_GET_MYSQL_ROOT_PASS(is_windows=True):
    mysql_ins = RySoftShop.objects.filter(name="mysql").first()
    root_pass = mysql_ins.password if mysql_ins else ""
    return root_pass

def RY_SET_MYSQL_ROOT_PASS(password,first = True,is_windows=True):
    soft_paths = get_mysql_path_info()
    old_root_pass ="" if first else RY_GET_MYSQL_ROOT_PASS()
    new_root_pass = password
    mysqladmin =soft_paths['windows_abspath_mysqladmin_path'] if is_windows else soft_paths['linux_mysqladmin_path']
    # 确保路径存在
    if os.path.exists(mysqladmin):
        if is_mysql_running(is_windows=is_windows):
            try:
                p ='' if first else f"-p{old_root_pass}"
                command =  f"{mysqladmin} -u root {p} password {new_root_pass}"
                if not is_windows:
                    import shlex
                    command = shlex.split(command)
                result = subprocess.run(command,cwd=soft_paths['install_path'],check=True, text=True)
                return True
            except Exception as e:
                raise ValueError(f"修改mysql root密码时发生错误: {e}")
        else:
            raise ValueError(f"Mysql未运行")
    else:
        raise ValueError(f"Mysql未安装")

def Mysql_Connect(db_host="127.0.0.1",db_port=3306,db_user="root",db_password="",db_name="",connect_timeout=3,charset="utf8mb4",local=True):
    """
    连接mysql
    return 数据库连接
    """
    port = db_port
    password = db_password
    if local:
        conf = RY_GET_MYSQL_CONF()
        port_rep = r"port\s*=\s*([0-9]+)"
        try:
            port = int(re.search(port_rep,conf).groups()[0])
        except:
            port = db_port
        password = RY_GET_MYSQL_ROOT_PASS()
    db_conn = MysqlClient.get_client(db_host=db_host,db_user=db_user,db_password=password,db_port=port,db_name=db_name,charset=charset,connect_timeout=connect_timeout)
    return db_conn

def RY_GET_MYSQL_CONF(is_windows=True):
    soft_paths = get_mysql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    return ReadFile(conf_path)

def RY_SAVE_MYSQL_CONF(conf="",is_windows=True):
    soft_paths = get_mysql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    WriteFile(conf_path,content=conf)
    return True

def RY_CHECK_MYSQL_DATANAME_EXISTS(mysql_conn, dataName):
    if not mysql_conn:
        raise ValueError("mysql连接失败")
    try:
        data = mysql_conn.filter("show databases")
        if data and data[0] == 1045:
            return ValueError("MySQL密码错误!")
        for i in data:
            if i[0] == dataName:
                return True
        return False
    except Exception as e:
        raise ValueError(e)

def RY_CREATE_MYSQL_DATANAME(mysql_conn, db_info={}):
    if not mysql_conn:
        raise ValueError("mysql连接失败")
    try:
        db_name = db_info['db_name']
        charset = db_info.get('charset','utf8mb4')
        db_collate = db_info.get('db_collate','utf8mb4_unicode_ci')
        result = mysql_conn.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET {charset} COLLATE {db_collate};")
        isErr,msg = is_sql_result_error(result)
        if isErr:
            raise ValueError(msg)
        return True
    except Exception as e:
        raise ValueError(e)

def RY_CREATE_MYSQL_USER(mysql_conn, db_info={}):
    if not mysql_conn:
        raise ValueError("mysql连接失败")
    try:
        db_name = db_info['db_name']
        db_user = db_info.get('db_user','')
        db_pass = db_info.get('db_pass','')
        accept = db_info.get('accept','')
        accept_ips = db_info.get('accept_ips','')
        if accept == 'all':
            accept_ips = ['%']
        elif accept == 'localhost':
            accept_ips = ['localhost']
        elif accept == 'ip':
            accept_ips = accept_ips.split(',')
        else:
            accept_ips = []
        #先删除
        mysql_conn.execute(f"DROP USER IF EXISTS '{db_user}'@'localhost'")
        if accept == "ip":
            for a in accept_ips:
                mysql_conn.execute(f"DROP USER IF EXISTS '{db_user}'@'{a}'")
        else:
            mysql_conn.execute(f"DROP USER IF EXISTS '{db_user}'@'%'")
            mysql_conn.execute(f"DROP USER IF EXISTS '{db_user}'@'localhost'")
        #再创建
        mysql_conn.execute("CREATE USER IF NOT EXISTS `%s`@`localhost` IDENTIFIED BY '%s'" % (db_user, db_pass))
        mysql_conn.execute("grant all privileges on `%s`.* to `%s`@`localhost`" % (db_name, db_user))
        for a in accept_ips:
            if not a: continue
            mysql_conn.execute("CREATE USER IF NOT EXISTS `{}`@`{}` IDENTIFIED BY '{}'".format(db_user, a, db_pass))
            mysql_conn.execute("grant all privileges on `%s`.* to `%s`@`%s`" % (db_name, db_user, a))
        mysql_conn.execute("flush privileges")
        return True
    except Exception as e:
        raise ValueError(e)

def RY_RESET_MYSQL_USER_PASS(mysql_conn, db_info={}):
    if not mysql_conn:
        raise ValueError("mysql连接失败")
    try:
        db_name = db_info['db_name']
        db_user = db_info.get('db_user','')
        db_pass = db_info.get('db_pass','')
        accept_data = mysql_conn.filter(f"select Host from mysql.user where User='{db_user}' AND Host!='localhost'")
        isErr,msg = is_sql_result_error(accept_data)
        if isErr:
            raise ValueError(msg)
        mysql_conn.execute(f"update mysql.user set authentication_string='' where User='{db_user}'")
        result = mysql_conn.execute(f"ALTER USER `{db_user}`@`localhost` IDENTIFIED BY '{db_pass}'")
        isErr,msg = is_sql_result_error(result)
        if isErr:
            raise ValueError(msg)
        for a in accept_data:
            mysql_conn.execute(f"ALTER USER `{db_user}`@`{a[0]}` IDENTIFIED BY '{db_pass}'")
        mysql_conn.execute("flush privileges")
        return True
    except Exception as e:
        raise ValueError(e)

def RY_DELETE_MYSQL_DATABASE(mysql_conn, db_info={}):
    if not mysql_conn:
        raise ValueError("mysql连接失败")
    try:
        db_name = db_info['db_name']
        db_user = db_info.get('db_user','')
        result = mysql_conn.execute(f"DROP database `{db_name}`")
        isErr,msg = is_sql_result_error(result)
        if isErr:
            raise ValueError(msg)
        hosts = mysql_conn.filter(f"select Host from mysql.user where User='{db_user}'")
        if isinstance(hosts, list):
            for h in hosts:
                mysql_conn.execute(f"DROP USER `{db_user}`@`{h[0]}`")
        mysql_conn.execute("flush privileges")
        return True
    except Exception as e:
        raise ValueError(e)

def RY_BACKUP_MYSQL_DATABASE(db_info={},is_windows=True,return_bk_ins = False):
    soft_paths = get_mysql_path_info()
    mysqldump = soft_paths['windows_abspath_mysqldump_path'] if is_windows else soft_paths['linux_mysqldump_path']
    db_name = db_info['db_name']
    id = db_info.get('id','')
    db_host = db_info.get('db_host','')
    db_user = db_info.get('db_user','')
    db_pass = db_info.get('db_pass','')
    db_port = db_info.get('db_port','')
    charset = db_info.get('format','utf8mb4')
    file_sql_name = f"db_{db_name}_{time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())}_mysql_{GetRandomSet(5)}.sql"
    file_name = f"{file_sql_name}.zip"
    tmp_back_path =GetBackupPath().replace("/","\\") if is_windows else GetBackupPath()
    export_dir = os.path.join(tmp_back_path, "database",db_name)
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
    # 确保路径存在
    if os.path.exists(mysqldump):
        if not is_mysql_running(is_windows=is_windows):raise ValueError(f"Mysql未启动")
        command = f"{mysqldump} --opt --skip-lock-tables --single-transaction --routines --events --skip-triggers --default-character-set={charset} --force --add-drop-database -h {db_host} --port={db_port} -u {db_user} {db_name}"
        dst_file_sql_path = os.path.join(export_dir,file_sql_name)
        dst_file_path = os.path.join(export_dir,file_name)
        try:
            with open(dst_file_sql_path, 'w',encoding="utf-8") as file:
                env = os.environ.copy()
                env['MYSQL_PWD'] = db_pass#避免命令行直接使用密码
                if not is_windows:
                    import shlex
                    command = shlex.split(command)
                result = subprocess.run(command,stderr=subprocess.PIPE,stdout=file,text=True,env=env)
            if result.returncode != 0:
                raise ValueError(result.stderr)
            else:
                with zipfile.ZipFile(dst_file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(dst_file_sql_path, os.path.basename(dst_file_sql_path))
                DeleteFile(dst_file_sql_path,empty_tips=False)
            dst_file_size = os.path.getsize(dst_file_path)
            bk_ins = RuyiBackup.objects.create(type=1,name=file_name,filename=dst_file_path,size=dst_file_size,fid=id)
            if return_bk_ins:
                return True,dst_file_path,dst_file_size,bk_ins
            return True,dst_file_path,dst_file_size
        except Exception as e:
            DeleteFile(dst_file_sql_path,empty_tips=False)
            DeleteFile(dst_file_path,empty_tips=False)
            raise ValueError(f"备份失败: {e}")
    else:
        raise ValueError(f"Mysql未安装")

def RY_IMPORT_MYSQL_SQL(db_info={},is_windows=True):
    soft_paths = get_mysql_path_info()
    mysql_exec = soft_paths['windows_abspath_mysql_path'].replace("\\","/") if is_windows else soft_paths['linux_mysql_path']
    db_name = db_info['db_name']
    file_name = db_info.get('file_name','')#绝对路径
    db_host = db_info.get('db_host','')
    db_user = db_info.get('db_user','')
    db_pass = db_info.get('db_pass','')
    db_port = db_info.get('db_port','')
    charset = db_info.get('format','utf8mb4')
    if not os.path.exists(file_name): raise ValueError("导入文件不存在!")
    file_base_name = os.path.basename(file_name)
    _, f_ext = os.path.splitext(file_base_name)
    allow_ext_list = [".sql", ".tar.gz", ".zip"]
    if f_ext not in allow_ext_list:
        raise ValueError("请选择[sql,tar.gz,zip]文件格式!")
    import_path_list = []
    extract_tmp_path = os.path.join(os.path.abspath(GetTmpPath()),"ImportDBSql",db_name,"importsql_tmp_{}".format(int(time.time() * 1000_000)))
    # 确保路径存在
    if os.path.exists(mysql_exec):
        if not is_mysql_running(is_windows=is_windows):raise ValueError(f"Mysql未启动")
        is_zip_file = True
        try:
            if f_ext in ['.sql']:
                import_path_list.append(file_name)
                is_zip_file = False
            else: 
                if not os.path.isdir(extract_tmp_path): os.makedirs(extract_tmp_path)
                # 开始解压
                if f_ext in ['.tar.gz']:
                    with tarfile.open(file_name, 'r') as tar:
                        tar.extractall(extract_tmp_path)
                elif f_ext == '.zip':
                    with zipfile.ZipFile(file_name, 'r') as zipf:
                        zipf.extractall(extract_tmp_path)
                def get_importsql_path(ex_tmp_path: str, im_path_list: list):
                    for fn in os.listdir(ex_tmp_path):
                        path = os.path.join(ex_tmp_path, fn)
                        if os.path.isfile(path) and path.endswith(".sql"):
                            im_path_list.append(path)
                        elif os.path.isdir(path):
                            get_importsql_path(path, im_path_list)

                get_importsql_path(extract_tmp_path, import_path_list)
                is_zip_file = True
            env = os.environ.copy()
            env['MYSQL_PWD'] = db_pass#避免命令行直接使用密码
            command = f"{mysql_exec} --force --default-character-set={charset} --host={db_host} --port={db_port} -u {db_user} {db_name}"
            for i in import_path_list:
                i = i.replace("\\",'/')
                result = subprocess.run(f'{command} < {i}',shell=True, text=True, capture_output=True,env=env)
                if result.returncode != 0:
                    raise ValueError(result.stderr)
            # 清理临时目录
            if is_zip_file:
                system.ForceRemoveDir(extract_tmp_path)
            return True
        except Exception as e:
            if is_zip_file:
                system.ForceRemoveDir(extract_tmp_path)
            raise ValueError(f"导入失败: {e}")
    else:
        raise ValueError(f"Mysql未安装")
    

def RY_GET_MYSQL_LOADSTATUS(is_windows=True):
    if not is_mysql_running(is_windows=is_windows):
        raise ValueError("mysql未运行")
    conn = Mysql_Connect()
    if not conn:
        raise ValueError("获取失败")
    try:
        data = conn.filter("SHOW GLOBAL STATUS")
        want_get_list = ['Max_used_connections', 'Com_commit', 'Com_rollback', 'Questions', 'Innodb_buffer_pool_reads',
                'Innodb_buffer_pool_read_requests', 'Key_reads', 'Key_read_requests', 'Key_writes',
                'Key_write_requests', 'Qcache_hits', 'Qcache_inserts', 'Bytes_received', 'Bytes_sent',
                'Aborted_clients', 'Aborted_connects', 'Created_tmp_disk_tables', 'Created_tmp_tables',
                'Innodb_buffer_pool_pages_dirty', 'Opened_files', 'Open_tables', 'Opened_tables', 'Select_full_join',
                'Select_range_check', 'Sort_merge_passes', 'Table_locks_waited', 'Threads_cached', 'Threads_connected',
                'Threads_created', 'Threads_running', 'Connections', 'Uptime']
        if data and data[0] == 1045:
            return ValueError("MySQL密码错误!")
        status_info = {}
        for d in data:
            for w in want_get_list:
                try:
                    if d[0] == w:
                        status_info[w] = d[1]
                except:
                    pass
        if status_info and not 'RunTime' in status_info :
            status_info['RunTime'] = int(time.time()) - int(status_info['Uptime'])
        
        results_2 = conn.filter("show master status")
        try:
            status_info['File'] = results_2[0][0]
            status_info['Position'] = results_2[0][1]
        except:
            status_info['File'] = 'OFF'
            status_info['Position'] = 'OFF'
        return status_info
    except Exception as e:
        raise ValueError(e)

def RY_GET_MYSQL_PERFORMANCE(is_windows=True):
    current_data = {}
    config = configparser.ConfigParser()
    soft_paths = get_mysql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    if not os.path.exists(conf_path):raise ValueError("mysql未安装")
    for encoding in ['utf-8', 'latin-1', 'windows-1252']:
        try:
            with open(conf_path, encoding=encoding) as config_file:
                config.read_file(config_file)
            break  # 成功读取文件后退出循环
        except:
            break
    
    # 提取 [mysqld] 部分的配置
    try:
        mysqld_config = config['mysqld']
    except:
        raise ValueError("无mysqld配置项")
    
    conn = Mysql_Connect()
    if conn:
        current_data = conn.filter('show variables')

    # 提取特定配置项的值
    config_vars = [
        'key_buffer_size', 'query_cache_size', 'tmp_table_size',
        'innodb_buffer_pool_size', 'innodb_log_buffer_size',
        'sort_buffer_size', 'read_buffer_size', 'read_rnd_buffer_size',
        'join_buffer_size', 'thread_stack', 'binlog_cache_size',
        'thread_cache_size', 'table_open_cache', 'max_connections'
    ]
    # 将配置项和它们的值存储在字典中(配置中不存在的)
    config_dict = {}
    for var in config_vars:
        value = ""
        if var in mysqld_config:
            value = mysqld_config[var]
            if re.search(r"\d+(\.\d+)+", value):
                value = re.search(r"\d+(\.\d+)?", value).group()
                value = value
            elif re.search(r"\d+", value):
                value = re.search(r"\d+", value).group()
                value = int(value)
        elif current_data:
            for d in current_data:
                if d[0] == var:
                    value = d[1]
                    if re.search(r"\d+", value):
                        value = int(value)
                    if var in ["key_buffer_size","tmp_table_size","innodb_buffer_pool_size","innodb_log_buffer_size"]:#字节转MB
                        value = int((value/1024)/1024)
                    elif var in ["sort_buffer_size","join_buffer_size","read_rnd_buffer_size","read_buffer_size","thread_stack","binlog_cache_size"]:#字节转KB
                        value = int((value/1024))
                    
        config_dict[var] = value

    return config_dict

def RY_SET_MYSQL_PERFORMANCE(cont,is_windows=True):
    config = configparser.ConfigParser()
    soft_paths = get_mysql_path_info()
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_conf_path']
    if not os.path.exists(conf_path):raise ValueError("mysql未安装")
    for encoding in ['utf-8', 'latin-1', 'windows-1252']:
        try:
            with open(conf_path, encoding=encoding) as config_file:
                config.read_file(config_file)
            break  # 成功读取文件后退出循环
        except:
            break
    
    # 提取 [mysqld] 部分的配置
    try:
        mysqld_config = config['mysqld']
    except:
        raise ValueError("无mysqld配置项")
    
    version_path = soft_paths['install_path'] + "/version.ry"
    version = ReadFile(version_path)
    if not version:raise ValueError("mysql未安装")
    
    is_version_8_or_higher = version and int(version.split('.')[0]) >= 8
    
    config_vars = [
        'key_buffer_size', 'query_cache_size', 'tmp_table_size',
        'innodb_buffer_pool_size', 'innodb_log_buffer_size',
        'sort_buffer_size', 'read_buffer_size', 'read_rnd_buffer_size',
        'join_buffer_size', 'thread_stack', 'binlog_cache_size',
        'thread_cache_size', 'table_open_cache', 'max_connections'
    ]
    
    for var in config_vars:
        value = str(cont[var])
        if is_version_8_or_higher and var in ["query_cache_size"]:
            continue
        if var in ["key_buffer_size","tmp_table_size","innodb_buffer_pool_size","innodb_log_buffer_size"]:#MB
            mysqld_config[var] = value+"M"
        elif var in ["sort_buffer_size","join_buffer_size","read_rnd_buffer_size","read_buffer_size","thread_stack","binlog_cache_size"]:#KB
            mysqld_config[var] = value+"K"
        elif var in ["query_cache_size"]:
            if value == '0' or value == "":
                mysqld_config[var] = "0M"
                mysqld_config['query_cache_type'] = 'OFF'
            else:
                mysqld_config[var] = value + "M"
                mysqld_config['query_cache_type'] = 'ON'
        else:
             mysqld_config[var] = value
    
    config['mysqld'] = mysqld_config
    with open(conf_path, "w",encoding="utf-8") as f:
        config.write(f)
    return True

def RY_GET_MYSQL_CONFIG(version="",is_windows=True):
    cpu_count = psutil.cpu_count()
    total_memory_bytes = psutil.virtual_memory().total
    soft_paths = get_mysql_path_info()
    install_path = soft_paths['install_path']
    error_log_path = soft_paths['error_log_path']
    slow_log_path = soft_paths['slow_log_path']
    data_path = soft_paths['data_abspath_path'].replace("\\","/")
    defaultEngine="InnoDB"
    max_connections = cpu_count*50 if cpu_count*50 > 200 else 200
    table_open_cache = 32
    sort_buffer_size = 256
    # sort_buffer_size = int((total_memory_bytes * 0.01 / 100) / 1024)
    # sort_buffer_size =1 if sort_buffer_size < 1 else int(sort_buffer_size)
    innodb_buffer_pool_size = 128
    # innodb_buffer_pool_size = (total_memory_bytes / (1024 * 1024)) * 0.06
    # innodb_buffer_pool_size =1 if innodb_buffer_pool_size < 1 else int(innodb_buffer_pool_size)
    # query_cache_size = (total_memory_bytes / (1024 * 1024)) * 0.02
    # query_cache_size =1 if query_cache_size < 1 else int(query_cache_size)
    query_cache_size = 0
    # tmp_table_size = (total_memory_bytes / (1024 * 1024)) * 0.03
    # tmp_table_size =1 if tmp_table_size < 1 else int(tmp_table_size)
    tmp_table_size = 32
    key_buffer_size = 8
    read_buffer_size = 128
    thread_cache_size = 8
    innodb_log_file_size = 12
    innodb_log_buffer_size = 8
    
    # if version.find('8.') == 0 and g in ['query_cache_type', 'query_cache_size']:#mysql8.x及以上版本无此配置项
    #     query_cache_size_str = f'query_cache_size = {query_cache_size}M'
    #     query_cache_type_str = f'query_cache_type = OFF' #查询缓存开关 ON、OFF、DEMAND
    is_version_8_or_higher = version and int(version.split('.')[0]) >= 8
    explicit_defaults_for_timestamp=""
    sqlmode = "NO_ENGINE_SUBSTITUTION,STRICT_TRANS_TABLES"
    if version.find('8.') == 0 or version.find('5.7') == 0:
        if not is_windows:
            explicit_defaults_for_timestamp="explicit_defaults_for_timestamp=true"
    if version.find('5.7') == 0:
        sqlmode = "NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,STRICT_TRANS_TABLES,NO_AUTO_CREATE_USER"
        
    total_mem_m = int(total_memory_bytes/1024/1024)
    if total_mem_m >1024 and total_mem_m <2048:
        key_buffer_size=32
        table_open_cache=128
        sort_buffer_size=768
        read_buffer_size=768
        thread_cache_size=16
        tmp_table_size=32
        innodb_buffer_pool_size=128
        innodb_log_file_size=64
        innodb_log_buffer_size=16
    elif total_mem_m >=2048 and total_mem_m <4096:
        key_buffer_size=64
        table_open_cache=256
        sort_buffer_size=1024
        read_buffer_size=1024
        thread_cache_size=32
        tmp_table_size=64
        innodb_buffer_pool_size=256
        innodb_log_file_size=128
        innodb_log_buffer_size=32
    elif total_mem_m >=4096 and total_mem_m <8192:
        key_buffer_size=128
        table_open_cache=512
        sort_buffer_size=2048
        read_buffer_size=2048
        thread_cache_size=64
        tmp_table_size=64
        innodb_buffer_pool_size=512
        innodb_log_file_size=256
        innodb_log_buffer_size=64
    elif total_mem_m >=8192 and total_mem_m <16384:
        key_buffer_size=256
        table_open_cache=1024
        sort_buffer_size=1024*4
        read_buffer_size=1024*4
        thread_cache_size=128
        tmp_table_size=128
        innodb_buffer_pool_size=1024
        innodb_log_file_size=512
        innodb_log_buffer_size=128
    elif total_mem_m >=16384 and total_mem_m <32768:
        key_buffer_size=512
        table_open_cache=1024*2
        sort_buffer_size=1024*8
        read_buffer_size=1024*8
        thread_cache_size=256
        tmp_table_size=256
        innodb_buffer_pool_size=1024*2
        innodb_log_file_size=512*2
        innodb_log_buffer_size=128*2
    else:
        key_buffer_size=512*2
        table_open_cache=1024*4
        sort_buffer_size=1024*16
        read_buffer_size=1024*16
        thread_cache_size=256*2
        tmp_table_size=256*2
        innodb_buffer_pool_size=1024*4
        innodb_log_file_size=512*4
        innodb_log_buffer_size=128*4
        
    
    windows_conf = f"""
[mysql]
default-character-set = utf8mb4

[mysqld]
port = 3306
basedir = {install_path}
datadir = {data_path}
log_error = {error_log_path}

slow_query_log = 1
slow_query_log_file = {slow_log_path}
long_query_time = 3
#log_queries_not_using_indexes = 1 # 记录没有使用索引的查询

thread_stack = 256K
innodb_buffer_pool_size = {innodb_buffer_pool_size}M
innodb_log_file_size = {innodb_log_file_size}M
innodb_log_buffer_size = {innodb_log_buffer_size}M
max_connections = {max_connections}
max_connect_errors = 100
table_open_cache = {table_open_cache}
sort_buffer_size = {sort_buffer_size}K
binlog_cache_size = 32K
key_buffer_size = {key_buffer_size}M
join_buffer_size = 256K
max_allowed_packet = 256M
thread_cache_size = {thread_cache_size}

wait_timeout = 28800
interactive_timeout = 28800

default-storage-engine = {defaultEngine}

sql_mode = STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION

autocommit = 1
read_buffer_size = {read_buffer_size}K
read_rnd_buffer_size = 256K
innodb_flush_log_at_trx_commit = 1
innodb_io_capacity = 200
{"query_cache_size = " + str(query_cache_size) + "M\n" if not is_version_8_or_higher else ""}
{"query_cache_type = OFF\n" if not is_version_8_or_higher else ""}
tmp_table_size = {tmp_table_size}M
max_heap_table_size = 64M

[mysqldump]
quick
max_allowed_packet = 500M
"""
    
    linux_conf = f"""
[client]
#password	= your_password
port		= 3306
socket		= /tmp/mysql.sock

[mysqld]
port		= 3306
socket		= /tmp/mysql.sock
user        = mysql
basedir = {install_path}
datadir = {data_path}
default-storage-engine = {defaultEngine}
skip-external-locking
binlog_cache_size = 32K
key_buffer_size = {key_buffer_size}M
join_buffer_size = 512K
max_allowed_packet = 256M
table_open_cache = {table_open_cache}
sort_buffer_size = {sort_buffer_size}K
net_buffer_length = 4K
read_buffer_size = {read_buffer_size}K
read_rnd_buffer_size = 256K
myisam_sort_buffer_size = 4M
thread_cache_size = {thread_cache_size}
{"query_cache_size = " + str(query_cache_size) + "M\n" if not is_version_8_or_higher else ""}
{"query_cache_type = OFF\n" if not is_version_8_or_higher else ""}
tmp_table_size = {tmp_table_size}M
sql-mode = {sqlmode}

thread_stack = 256K
#skip-name-resolve
max_connections = {max_connections}
max_connect_errors = 100
open_files_limit = 65535

log-bin=mysql-bin
binlog_format=mixed
server-id = 1
slow_query_log=1
slow-query-log-file={slow_log_path}
long_query_time=3

innodb_data_home_dir = {data_path}
innodb_data_file_path = ibdata1:10M:autoextend
innodb_log_group_home_dir = {data_path}
innodb_buffer_pool_size = {innodb_buffer_pool_size}M
innodb_log_file_size = {innodb_log_file_size}M
innodb_log_buffer_size = {innodb_log_buffer_size}M
innodb_flush_log_at_trx_commit = 1
innodb_lock_wait_timeout = 50
{explicit_defaults_for_timestamp}

[mysqldump]
quick
max_allowed_packet = 500M
"""
    
    return windows_conf if is_windows else linux_conf