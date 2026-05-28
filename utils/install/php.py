#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-10-22
# +-------------------------------------------------------------------
# | EditDate: 2025-05-05
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# PHP环境安装/卸载/启停/配置
# ------------------------------

import os,platform,re,json,errno
import time
from contextlib import contextmanager
from utils.common import ReadFile,GetTmpPath,GetInstallPath,WriteFile,DeleteFile,GetLogsPath,RunCommandReturnCode,RunCommand,ConvertToUnixLineEndings,is_service_running,current_os,CreateInstallProcess,CleanupInstallProcess,SafeReadStderr,ReleaseMemory
from utils.security.files import download_url_file,get_file_name_from_url
import subprocess
import importlib
from utils.server.system import system
from django.conf import settings
from apps.systask.subprocessMg import job_subprocess_add

def get_php_path_info(version):
    root_path = GetInstallPath()
    root_abspath_path = os.path.abspath(root_path)
    install_abspath_path = os.path.join(root_abspath_path,'php',version)
    install_path = root_path+'/php/'+version
    service_name = f"php{version.replace('.','')}"
    return {
        'root_abspath_path': root_abspath_path,
        'root_path': root_path,
        'install_abspath_path':install_abspath_path,
        'install_path':install_path,
        'service_name':service_name,
        'windows_abspath_php_path':os.path.join(install_abspath_path,'php.exe'),
        'windows_abspath_phpcgi_path':os.path.join(install_abspath_path,'php-cgi.exe'),
        'windows_abspath_fpm_path':os.path.join(install_abspath_path,'php-cgi.exe'),
        'windows_abspath_conf_path':os.path.join(install_abspath_path,'php.ini'),
        'windows_abspath_fpm_conf_path':os.path.join(install_abspath_path,'php-fpm.conf'),
        'windows_server_exe':os.path.join(install_abspath_path,f'{service_name}_server.exe'),
        'linux_abspath_php_path':os.path.join(install_abspath_path,'bin','php'),
        'linux_abspath_phpcgi_path':os.path.join(install_abspath_path,'bin','php-cgi'),
        'linux_abspath_fpm_path':os.path.join(install_abspath_path,'sbin','php-fpm'),
        'linux_abspath_conf_path':os.path.join(install_abspath_path,'lib','php.ini'),
        'linux_abspath_fpm_conf_path':os.path.join(install_abspath_path,'etc','php-fpm.conf'),
        'linux_abspath_fpm_conf_d_path':os.path.join(install_abspath_path,'etc','php-fpm.d'),
        'log_path':install_path+'/var/log',
        'error_log_path':install_path+'/var/log/php-fpm.log',
        'fpm_port':get_php_fpm_port(version),
    }

def get_php_fpm_port(version):
    parts = version.split('.')
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    return 9000 + major * 10 + minor

def php_install_call_back(version={},call_back=None,ok=True):
    if call_back:
        job_id = version.get('job_id')
        module_path, function_name = call_back.rsplit('.', 1)
        module = importlib.import_module(module_path)
        function = getattr(module, function_name)
        function(job_id=job_id,version=version,ok=ok)

def isSupportSys():
    if platform.architecture()[0] == '64bit':
        arch = platform.machine().lower()
        if arch in ['x86_64','amd64','aarch64']:
            return True
        return False
    return False

def check_php_version(phpPath=""):
    try:
        if not phpPath:
            phpPath = "php"
        if current_os == 'windows':
            output = subprocess.check_output([phpPath, "-v"], stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            output = subprocess.check_output([phpPath, "-v"], stderr=subprocess.STDOUT)
        version_line = output.decode('utf-8', errors='replace').strip().split('\n')[0]
        version_match = re.search(r'PHP (\d+\.\d+\.\d+)', version_line)
        if version_match:
            return version_match.group(1)
        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def is_php_running(version,is_windows=True,simple_check=False):
    soft_paths = get_php_path_info(version)
    if is_windows:
        php_cgi_name = 'php-cgi.exe'
        for proc in __import__('psutil').process_iter(['name']):
            if proc.info['name'] == php_cgi_name:
                try:
                    if soft_paths['install_abspath_path'].lower() in proc.exe().lower():
                        return True
                except:
                    pass
        return False
    else:
        service_name = f"php-fpm-{version}"
        try:
            result = subprocess.run(['systemctl','is-active',service_name],capture_output=True,text=True,timeout=5)
            if result.returncode == 0 and 'active' in result.stdout.strip().lower():
                return True
        except Exception:
            pass
        fpm_path = soft_paths['linux_abspath_fpm_path']
        pid_file = os.path.join(soft_paths['install_abspath_path'],'var','run','php-fpm.pid')
        if os.path.isfile(pid_file):
            try:
                with open(pid_file,'r') as f:
                    pid = f.read().strip()
                if pid.isdigit():
                    if os.path.exists(f'/proc/{pid}'):
                        return True
            except:
                pass
        import psutil
        install_path = soft_paths['install_abspath_path']
        for proc in psutil.process_iter(['name','exe','cmdline']):
            try:
                if proc.info['exe'] and proc.info['exe'] == fpm_path:
                    return True
                if proc.info['cmdline']:
                    cmdline_str = ' '.join(proc.info['cmdline'])
                    if fpm_path in cmdline_str:
                        return True
                    if install_path in cmdline_str:
                        return True
            except:
                pass
        return False

def _init_php_fpm_conf_windows(install_path,version):
    soft_paths = get_php_path_info(version)
    php_ini_path = soft_paths['windows_abspath_conf_path']
    php_ini_develop = os.path.join(install_path,'php.ini-development')
    php_ini_production = os.path.join(install_path,'php.ini-production')
    if not os.path.exists(php_ini_path):
        if os.path.exists(php_ini_production):
            import shutil
            shutil.copy2(php_ini_production,php_ini_path)
        elif os.path.exists(php_ini_develop):
            import shutil
            shutil.copy2(php_ini_develop,php_ini_path)
    if not os.path.exists(php_ini_path):
        ext_dir = os.path.join(install_path,'ext')
        default_ini = f"""[PHP]
engine = On
short_open_tag = Off
precision = 14
output_buffering = 4096
zlib.output_compression = Off
implicit_flush = Off
unserialize_callback_func =
serialize_precision = -1
extension_dir = "{ext_dir.replace(os.sep,'/')}"
date.timezone = Asia/Shanghai
disable_functions = {','.join(PHP_DANGEROUS_FUNCTIONS)}
upload_max_filesize = 50M
post_max_size = 50M
max_execution_time = 300
max_input_time = 300
memory_limit = 128M
display_errors = Off
log_errors = On
error_log = {os.path.join(soft_paths["install_abspath_path"],'var','log','php-fpm.log').replace(os.sep,'/')}
"""
        WriteFile(php_ini_path, default_ini)
    if os.path.exists(php_ini_path):
        content = ReadFile(php_ini_path)
        ext_dir = os.path.join(install_path,'ext')
        content = re.sub(r';?\s*extension_dir\s*=.*',f'extension_dir = "{ext_dir.replace(os.sep,"/")}"',content)
        content = re.sub(r';?\s*date\.timezone\s*=.*','date.timezone = Asia/Shanghai',content)
        content = re.sub(r';?\s*disable_functions\s*=.*','disable_functions = '+','.join(PHP_DANGEROUS_FUNCTIONS),content)
        content = re.sub(r';?\s*upload_max_filesize\s*=.*','upload_max_filesize = 50M',content)
        content = re.sub(r';?\s*post_max_size\s*=.*','post_max_size = 50M',content)
        content = re.sub(r';?\s*max_execution_time\s*=.*','max_execution_time = 300',content)
        content = re.sub(r';?\s*max_input_time\s*=.*','max_input_time = 300',content)
        content = re.sub(r';?\s*memory_limit\s*=.*','memory_limit = 128M',content)
        content = re.sub(r';?\s*display_errors\s*=.*','display_errors = Off',content)
        content = re.sub(r';?\s*log_errors\s*=.*','log_errors = On',content)
        content = re.sub(r';?\s*error_log\s*=.*',f'error_log = {os.path.join(soft_paths["install_abspath_path"],"var","log","php-fpm.log").replace(os.sep,"/")}',content)
        content = re.sub(r';?\s*cgi\.fix_pathinfo\s*=.*','cgi.fix_pathinfo = 1',content)
        content = re.sub(r';?\s*expose_php\s*=.*','expose_php = Off',content)
        content = re.sub(r';?\s*short_open_tag\s*=.*','short_open_tag = On',content)
        content = re.sub(r';?\s*error_reporting\s*=.*','error_reporting = E_ALL & ~E_NOTICE',content)
        if 'error_reporting' not in content:
            content += '\nerror_reporting = E_ALL & ~E_NOTICE'
        content = re.sub(r';\s*extension=curl','extension=curl',content)
        content = re.sub(r';\s*extension=gd','extension=gd',content)
        content = re.sub(r';\s*extension=mbstring','extension=mbstring',content)
        content = re.sub(r';\s*extension=mysqli','extension=mysqli',content)
        content = re.sub(r';\s*extension=pdo_mysql','extension=pdo_mysql',content)
        content = re.sub(r';\s*extension=openssl','extension=openssl',content)
        content = re.sub(r';\s*extension=bz2','extension=bz2',content)
        content = re.sub(r';\s*extension=fileinfo','extension=fileinfo',content)
        content = re.sub(r';\s*extension=exif','extension=exif',content)
        content = re.sub(r';\s*extension=zip','extension=zip',content)
        content = re.sub(r';\s*extension=sockets','extension=sockets',content)
        WriteFile(php_ini_path,content)
    var_log_path = os.path.join(install_abspath_path,'var','log')
    if not os.path.exists(var_log_path):
        os.makedirs(var_log_path)

def SET_PHP_WINDOWS_SERVICE(version,log_path=None,is_write_log=True):
    soft_paths = get_php_path_info(version)
    install_path = soft_paths['install_path']
    server_exe = soft_paths['windows_server_exe']
    install_abspath_path = soft_paths['install_abspath_path']
    nginx_server_exe = os.path.join(os.path.abspath(GetInstallPath()),'nginx','nginx_server.exe')
    if os.path.exists(nginx_server_exe):
        import shutil
        shutil.copy2(nginx_server_exe,server_exe)
    else:
        primary_download_url = "https://gitee.com/lybbn/RuYi-Panel/releases/download/v1.0.9/WinSW-x64.exe"
        fallback_download_url = "https://github.com/winsw/winsw/releases/download/v3.0.0-alpha.11/WinSW-x64.exe"
        filename = get_file_name_from_url(primary_download_url)
        save_path = os.path.join(install_abspath_path, filename)
        WriteFile(log_path,"[info]正在下载 WinSW...\n",mode='a',write=is_write_log)
        ok,msg = download_url_file(url=primary_download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
        if not ok:
            WriteFile(log_path,"[warn]下载失败：%s，尝试从GitHub下载...\n"%(msg),mode='a',write=is_write_log)
            filename = get_file_name_from_url(fallback_download_url)
            save_path = os.path.join(install_abspath_path, filename)
            ok,msg = download_url_file(url=fallback_download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
            if not ok:
                WriteFile(log_path,"[warn]GitHub下载失败，尝试加速下载...\n",mode='a',write=is_write_log)
                from utils.security.files import get_github_quick_downloadurl
                new_download_url = get_github_quick_downloadurl(fallback_download_url)
                if not new_download_url:
                    return False,"下载WinSW失败"
                ok,msg = download_url_file(url=new_download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
                if not ok:
                    return False,"下载WinSW失败"
        os.rename(save_path, server_exe)
    SET_PHP_WINDOWS_SERVICE_CONFIG(version)
    from utils.server.windows import install_as_service, get_service_status
    service_name = soft_paths['service_name']
    if get_service_status(service_name) == -1:
        isok, msg = install_as_service(
            name=service_name,
            display_name=f"PHP {version} (Ruyi)",
            path=server_exe,
            description=f"PHP {version} FastCGI Process Manager managed by Ruyi Panel",
            start_type=3
        )
        if not isok:
            return False, msg
    return True, None

def SET_PHP_WINDOWS_SERVICE_CONFIG(version):
    soft_paths = get_php_path_info(version)
    install_path = soft_paths['install_path']
    install_abspath_path = soft_paths['install_abspath_path']
    php_cgi_path = soft_paths['windows_abspath_phpcgi_path']
    php_ini_path = soft_paths['windows_abspath_conf_path']
    fpm_port = soft_paths['fpm_port']
    log_path = os.path.join(install_abspath_path,'var','log')
    service_name = soft_paths['service_name']
    content = f"""
<service>
    <id>{service_name}</id>
    <name>PHP {version} (Ruyi)</name>
    <description>PHP {version} FastCGI Process Manager managed by Ruyi Panel</description>
    <logpath>{log_path}</logpath>
    <logmode>roll</logmode>
    <depend></depend>
    <executable>{php_cgi_path}</executable>
    <arguments>-b 127.0.0.1:{fpm_port} -c "{php_ini_path}"</arguments>
    <stopexecutable>taskkill</stopexecutable>
    <stopargument>/F</stopargument>
    <stopargument>/IM</stopargument>
    <stopargument>php-cgi.exe</stopargument>
    <stopargument>/FI</stopargument>
    <stopargument>"IMAGENAME eq php-cgi.exe and PATH eq {install_abspath_path}"</stopargument>
    <onstart action="restart" delay="10 sec"/>
</service>"""
    WriteFile(install_path+f"/{service_name}_server.xml",content)

def _init_php_fpm_conf_linux(install_path,version):
    soft_paths = get_php_path_info(version)
    php_ini_path = soft_paths['linux_abspath_conf_path']
    if not os.path.exists(php_ini_path):
        php_ini_develop = os.path.join(install_path,'lib','php.ini-development')
        php_ini_production = os.path.join(install_path,'lib','php.ini-production')
        if os.path.exists(php_ini_production):
            import shutil
            shutil.copy2(php_ini_production,php_ini_path)
        elif os.path.exists(php_ini_develop):
            import shutil
            shutil.copy2(php_ini_develop,php_ini_path)
    if not os.path.exists(php_ini_path):
        ext_dir = os.path.join(install_path,'lib','php','extensions','no-debug-non-zts-20220829')
        default_ini = f"""[PHP]
engine = On
short_open_tag = Off
precision = 14
output_buffering = 4096
zlib.output_compression = Off
implicit_flush = Off
unserialize_callback_func =
serialize_precision = -1
date.timezone = Asia/Shanghai
disable_functions = {','.join(PHP_DANGEROUS_FUNCTIONS)}
upload_max_filesize = 50M
post_max_size = 50M
max_execution_time = 300
max_input_time = 300
memory_limit = 128M
display_errors = Off
log_errors = On
error_log = {os.path.join(soft_paths["install_abspath_path"],'var','log','php-fpm.log')}
"""
        WriteFile(php_ini_path, default_ini)
    if os.path.exists(php_ini_path):
        content = ReadFile(php_ini_path)
        content = re.sub(r';?\s*date\.timezone\s*=.*','date.timezone = Asia/Shanghai',content)
        content = re.sub(r';?\s*disable_functions\s*=.*','disable_functions = '+','.join(PHP_DANGEROUS_FUNCTIONS),content)
        content = re.sub(r';?\s*upload_max_filesize\s*=.*','upload_max_filesize = 50M',content)
        content = re.sub(r';?\s*post_max_size\s*=.*','post_max_size = 50M',content)
        content = re.sub(r';?\s*max_execution_time\s*=.*','max_execution_time = 300',content)
        content = re.sub(r';?\s*max_input_time\s*=.*','max_input_time = 300',content)
        content = re.sub(r';?\s*memory_limit\s*=.*','memory_limit = 128M',content)
        content = re.sub(r';?\s*display_errors\s*=.*','display_errors = Off',content)
        content = re.sub(r';?\s*log_errors\s*=.*','log_errors = On',content)
        content = re.sub(r';?\s*error_log\s*=.*',f'error_log = {os.path.join(soft_paths["install_abspath_path"],"var","log","php-fpm.log")}',content)
        content = re.sub(r';?\s*cgi\.fix_pathinfo\s*=.*','cgi.fix_pathinfo = 1',content)
        content = re.sub(r';?\s*expose_php\s*=.*','expose_php = Off',content)
        content = re.sub(r';?\s*short_open_tag\s*=.*','short_open_tag = On',content)
        content = re.sub(r';?\s*error_reporting\s*=.*','error_reporting = E_ALL & ~E_NOTICE',content)
        if 'error_reporting' not in content:
            content += '\nerror_reporting = E_ALL & ~E_NOTICE'
        if os.path.exists('/usr/sbin/sendmail'):
            content = re.sub(r';?\s*sendmail_path\s*=.*','sendmail_path = /usr/sbin/sendmail -t -i',content)
        ca_bundle_paths = ['/etc/pki/tls/certs/ca-bundle.crt','/etc/ssl/certs/ca-certificates.crt']
        ca_path = ''
        for p in ca_bundle_paths:
            if os.path.exists(p):
                ca_path = p
                break
        if ca_path:
            content = re.sub(r';?\s*openssl\.cafile\s*=.*',f'openssl.cafile = {ca_path}',content)
            content = re.sub(r';?\s*curl\.cainfo\s*=.*',f'curl.cainfo = {ca_path}',content)
            if 'openssl.cafile' not in content:
                content += f'\nopenssl.cafile = {ca_path}'
            if 'curl.cainfo' not in content:
                content += f'\ncurl.cainfo = {ca_path}'
        WriteFile(php_ini_path,content)
    fpm_conf_path = soft_paths['linux_abspath_fpm_conf_path']
    fpm_conf_d_path = soft_paths['linux_abspath_fpm_conf_d_path']
    var_run_path = os.path.join(install_abspath_path,'var','run')
    var_log_path = os.path.join(install_abspath_path,'var','log')
    for p in [var_run_path,var_log_path,fpm_conf_d_path]:
        if not os.path.exists(p):
            os.makedirs(p)
    if os.path.exists(fpm_conf_path):
        fpm_content = ReadFile(fpm_conf_path)
        fpm_content = re.sub(r';?\s*pid\s*=.*',f'pid = {var_run_path}/php-fpm.pid',fpm_content)
        fpm_content = re.sub(r';?\s*error_log\s*=.*',f'error_log = {var_log_path}/php-fpm.log',fpm_content)
        fpm_content = re.sub(r';?\s*include\s*=.*',f'include = {fpm_conf_d_path}/*.conf',fpm_content)
        WriteFile(fpm_conf_path,fpm_content)
    default_pool_conf = os.path.join(fpm_conf_d_path,'www.conf')
    if not os.path.exists(default_pool_conf):
        pool_content = RY_GET_PHP_FPM_DEFAULT_POOL(version)
        WriteFile(default_pool_conf,pool_content)

def RY_GET_PHP_FPM_DEFAULT_POOL(version):
    soft_paths = get_php_path_info(version)
    import subprocess
    fpm_user = "www"
    try:
        result = subprocess.run(['id', 'www'], capture_output=True, text=True)
        if result.returncode != 0:
            try:
                subprocess.run(['useradd', '-r', '-s', '/sbin/nologin', 'www'], capture_output=True, text=True)
            except Exception:
                fpm_user = "nobody"
    except Exception:
        fpm_user = "nobody"
    return f"""[www]
user = {fpm_user}
group = {fpm_user}
listen = {soft_paths['install_abspath_path']}/tmp/php-cgi-{version}.sock
listen.backlog = 8192
listen.allowed_clients = 127.0.0.1
listen.owner = {fpm_user}
listen.group = {fpm_user}
listen.mode = 0660
pm = dynamic
pm.max_children = 50
pm.start_servers = 10
pm.min_spare_servers = 5
pm.max_spare_servers = 30
pm.max_requests = 1000
request_terminate_timeout = 100
request_slowlog_timeout = 30
slowlog = {soft_paths['install_abspath_path']}/var/log/php-slow.log
"""

def Install_PHP(type=2,version={},is_windows=True,call_back=None):
    try:
        name = version['name']
        log = version.get('log',None)
        is_write_log = False
        log_path = ""
        if log:
            is_write_log = True
            log_path = os.path.join(os.path.abspath(GetLogsPath()),name,log)
        WriteFile(log_path,"-------------------安装任务已开始-------------------\n",mode='a',write=is_write_log)
        if isSupportSys():
            WriteFile(log_path,"检测系统为64位，环境检测通过 ✔\n",mode='a',write=is_write_log)
        else:
            raise Exception("暂不支持非arm64、amd64和x86_64系统，环境检测不通过 ✖")
        download_url = version.get('url',None)
        WriteFile(log_path,"开始下载【%s】安装文件,文件地址：%s\n"%(name,download_url),mode='a',write=is_write_log)
        filename = get_file_name_from_url(download_url)
        save_directory = os.path.abspath(GetTmpPath())
        soft_paths = get_php_path_info(version['c_version'])
        install_directory = soft_paths['install_abspath_path']
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        save_path = os.path.join(save_directory, filename)
        ok,msg = download_url_file(url=download_url,save_path=save_path,process=True,log_path=log_path,chunk_size=32768)
        if not ok and not is_windows:
            php_version = version.get('c_version','')
            php_filename = filename
            mirror_urls = [
                "https://www.php.net/distributions/" + php_filename,
                "https://github.com/php/php-src/archive/refs/tags/php-" + php_version + ".tar.gz",
            ]
            WriteFile(log_path,"主地址下载失败，尝试回退下载...\n",mode='a',write=is_write_log)
            for mirror_url in mirror_urls:
                WriteFile(log_path,"尝试回退地址：%s\n"%mirror_url,mode='a',write=is_write_log)
                mirror_save_path = save_path
                if "github.com" in mirror_url:
                    mirror_filename = get_file_name_from_url(mirror_url)
                    mirror_save_path = os.path.join(save_directory, mirror_filename)
                ok,msg = download_url_file(url=mirror_url,save_path=mirror_save_path,process=True,log_path=log_path,chunk_size=32768)
                if ok:
                    save_path = mirror_save_path
                    filename = get_file_name_from_url(mirror_url)
                    break
                else:
                    WriteFile(log_path,"回退地址下载失败：%s\n"%msg,mode='a',write=is_write_log)
        if not ok:
            WriteFile(log_path,"[error]【%s】下载失败，原因：%s\n"%(filename,msg),mode='a',write=is_write_log)
            raise ValueError(msg)
        if is_windows:
            WriteFile(log_path,"【%s】下载完成\n"%filename,mode='a',write=is_write_log)
            install_base_directory = soft_paths['root_abspath_path']
            php_base_dir = os.path.join(install_base_directory,'php')
            if not os.path.exists(php_base_dir):
                os.makedirs(php_base_dir)
            system.ForceRemoveDir(install_directory)
            if not os.path.exists(install_directory):
                os.makedirs(install_directory)
            WriteFile(log_path,"正在解压安装文件到%s\n"%install_directory,mode='a',write=is_write_log)
            from apps.systask.tasks import func_unzip
            func_unzip(save_path,install_directory)
            extracted_items = os.listdir(install_directory)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(install_directory,extracted_items[0])):
                src_folder = os.path.join(install_directory,extracted_items[0])
                import shutil
                for item in os.listdir(src_folder):
                    shutil.move(os.path.join(src_folder,item),os.path.join(install_directory,item))
                os.rmdir(src_folder)
            WriteFile(log_path,"解压成功\n",mode='a',write=is_write_log)
            WriteFile(log_path,"正在初始化PHP配置...\n",mode='a',write=is_write_log)
            _init_php_fpm_conf_windows(install_directory,version['c_version'])
            WriteFile(log_path,"正在检测安装结果...\n",mode='a',write=is_write_log)
            time.sleep(0.5)
            install_version = check_php_version(soft_paths['windows_abspath_php_path'])
            if not install_version:
                raise Exception("安装失败，无法执行安装后的php")
            WriteFile(log_path,f"安装成功，检测后安装版本：{install_version}\n",mode='a',write=is_write_log)
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(log_path,"正在注册PHP为Windows系统服务...\n",mode='a',write=is_write_log)
            isok, msg = SET_PHP_WINDOWS_SERVICE(version['c_version'],log_path=log_path,is_write_log=is_write_log)
            if not isok:
                WriteFile(log_path,f"注册PHP系统服务失败：{msg}\n",mode='a',write=is_write_log)
            else:
                WriteFile(log_path,"PHP系统服务注册成功\n",mode='a',write=is_write_log)
        else:
            WriteFile(log_path,"【%s】下载完成，开始编译安装...\n"%filename,mode='a',write=is_write_log)
            script_path = GetInstallPath()+'/ruyi/utils/install/bash/php.sh'
            ConvertToUnixLineEndings(script_path)
            r_process = CreateInstallProcess(['bash', script_path, 'install', version['c_version'], filename])
            job_subprocess_add(version['job_id'],r_process)
            try:
                while True:
                    r_output = r_process.stdout.readline()
                    if r_output == '' and r_process.poll() is not None:
                        break
                    if r_output:
                        WriteFile(log_path,f"{r_output.strip()}\n",mode='a',write=is_write_log)
                    time.sleep(0.1)
                r_stderr = SafeReadStderr(r_process)
                if r_stderr:
                    if not os.path.exists(soft_paths['linux_abspath_php_path']):
                        raise Exception(r_stderr.strip()[:2000])
            finally:
                CleanupInstallProcess(r_process, version['job_id'])
                r_process = None
            WriteFile(log_path,"正在初始化PHP-FPM配置...\n",mode='a',write=is_write_log)
            _init_php_fpm_conf_linux(install_directory,version['c_version'])
            version_file = os.path.join(install_directory,'version.ry')
            WriteFile(version_file,version['c_version'])
            WriteFile(log_path,"正在启动PHP-FPM服务...\n",mode='a',write=is_write_log)
            try:
                Start_PHP(version=version['c_version'],is_windows=False)
                WriteFile(log_path,"PHP-FPM服务启动成功\n",mode='a',write=is_write_log)
            except Exception as start_e:
                WriteFile(log_path,f"PHP-FPM服务启动失败：{start_e}\n",mode='a',write=is_write_log)
        
        DeleteFile(save_path,empty_tips=False)
        WriteFile(log_path,"已删除下载的临时安装文件，并回调\n",mode='a',write=is_write_log)
        WriteFile(log_path,"安装成功，安装目录：%s\n"%install_directory,mode='a',write=is_write_log)
        version['install_path'] = install_directory
        php_install_call_back(version=version,call_back=call_back,ok=True)
        WriteFile(log_path,"-------------------安装任务已结束-------------------\n",mode='a',write=is_write_log)
        version.clear()
        soft_paths.clear()
        ReleaseMemory()
        return True
    except Exception as e:
        WriteFile(log_path,f"【错误】异常信息如下：\n{e}",mode='a',write=is_write_log)
        php_install_call_back(version=version,call_back=call_back,ok=False)
        version.clear()
        ReleaseMemory()
        return False

def Uninstall_PHP(version=None,is_windows=True):
    if not version: raise ValueError("未提供版本号")
    soft_paths = get_php_path_info(version)
    install_path = soft_paths['install_abspath_path']
    if is_windows:
        Stop_PHP(version=version,is_windows=is_windows)
        time.sleep(0.1)
        from utils.server.windows import uninstall_service
        uninstall_service(soft_paths['service_name'])
        if os.path.exists(install_path):
            time.sleep(0.1)
            system.ForceRemoveDir(install_path)
    else:
        try:
            Stop_PHP(version=version,is_windows=is_windows)
            script_path = os.path.join(settings.BASE_DIR,"utils","install","bash","php.sh")
            ConvertToUnixLineEndings(script_path)
            subprocess.run(['bash', script_path,'uninstall',version], capture_output=False, text=True)
        except Exception as e:
            raise ValueError(e)
    return True

def Start_PHP(version=None,is_windows=True,num_workers=None):
    if not version: raise ValueError("未提供版本号")
    soft_paths = get_php_path_info(version)
    if is_windows:
        php_cgi_path = soft_paths['windows_abspath_phpcgi_path']
        if not os.path.exists(php_cgi_path):
            raise FileNotFoundError(f"PHP-CGI可执行文件不存在: {php_cgi_path}")
        if is_php_running(version,is_windows=is_windows):
            return True
        from utils.server.windows import get_service_status
        service_name = soft_paths['service_name']
        service_status = get_service_status(service_name)
        if service_status != -1:
            subprocess.Popen(
                ["net", "start", service_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )
            time.sleep(2)
            return is_php_running(version,is_windows=is_windows)
        var_run_path = os.path.join(soft_paths['install_abspath_path'],'var','run')
        if not os.path.exists(var_run_path):
            os.makedirs(var_run_path)
        php_ini_path = soft_paths['windows_abspath_conf_path']
        if num_workers is None:
            num_workers = 4
        num_workers = int(num_workers)
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        procs = []
        for i in range(num_workers):
            proc = subprocess.Popen(
                [php_cgi_path,'-b',f'127.0.0.1:{soft_paths["fpm_port"]}','-c',php_ini_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )
            procs.append(proc)
        pid_file = os.path.join(var_run_path,'php-cgi.pid')
        pids = ','.join([str(p.pid) for p in procs])
        WriteFile(pid_file,pids)
        return True
    else:
        fpm_path = soft_paths['linux_abspath_fpm_path']
        if not os.path.exists(fpm_path):
            raise FileNotFoundError(f"PHP-FPM可执行文件不存在: {fpm_path}")
        if is_php_running(version,is_windows=is_windows):
            return True
        service_name = f"php-fpm-{version}"
        try:
            result = subprocess.run(['systemctl','start',service_name],capture_output=True,text=True,timeout=30)
            if result.returncode == 0:
                time.sleep(1)
                if is_php_running(version,is_windows=is_windows):
                    return True
        except Exception:
            pass
        subprocess.run([fpm_path,'-y',soft_paths['linux_abspath_fpm_conf_path']],capture_output=True,text=True)
        time.sleep(1)
        return is_php_running(version,is_windows=is_windows)

def Stop_PHP(version=None,is_windows=True):
    if not version: raise ValueError("未提供版本号")
    soft_paths = get_php_path_info(version)
    if is_windows:
        if not is_php_running(version,is_windows=is_windows):
            return True
        from utils.server.windows import get_service_status
        service_name = soft_paths['service_name']
        service_status = get_service_status(service_name)
        if service_status != -1:
            subprocess.Popen(
                ["net", "stop", service_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )
            time.sleep(1)
            if not is_php_running(version,is_windows=is_windows):
                return True
        php_cgi_name = 'php-cgi.exe'
        import psutil
        for proc in psutil.process_iter(['name','exe','pid']):
            try:
                if proc.info['name'] == php_cgi_name:
                    if soft_paths['install_abspath_path'].lower() in (proc.info['exe'] or '').lower():
                        proc.kill()
            except:
                pass
        pid_file = os.path.join(soft_paths['install_abspath_path'],'var','run','php-cgi.pid')
        if os.path.exists(pid_file):
            DeleteFile(pid_file,empty_tips=False)
        return True
    else:
        if not is_php_running(version,is_windows=is_windows):
            return True
        service_name = f"php-fpm-{version}"
        try:
            result = subprocess.run(['systemctl','stop',service_name],capture_output=True,text=True,timeout=30)
            if result.returncode == 0:
                time.sleep(1)
                if not is_php_running(version,is_windows=is_windows):
                    return True
        except Exception:
            pass
        pid_file = os.path.join(soft_paths['install_abspath_path'],'var','run','php-fpm.pid')
        if os.path.isfile(pid_file):
            try:
                with open(pid_file,'r') as f:
                    pid = f.read().strip()
                if pid.isdigit():
                    subprocess.run(['kill','-QUIT',pid],capture_output=True,text=True)
                    time.sleep(1)
                    if not is_php_running(version,is_windows=is_windows):
                        return True
            except:
                pass
        fpm_install_path = soft_paths['install_abspath_path']
        subprocess.run(['pkill','-f',f'php-fpm: master.*{fpm_install_path}'],capture_output=True,text=True)
        return True

def Restart_PHP(version=None,is_windows=True):
    Stop_PHP(version=version,is_windows=is_windows)
    time.sleep(1)
    Start_PHP(version=version,is_windows=is_windows)
    return True

def Reload_PHP(version=None,is_windows=True):
    if not version: raise ValueError("未提供版本号")
    soft_paths = get_php_path_info(version)
    if is_windows:
        Restart_PHP(version=version,is_windows=is_windows)
    else:
        service_name = f"php-fpm-{version}"
        try:
            result = subprocess.run(['systemctl','reload',service_name],capture_output=True,text=True,timeout=30)
            if result.returncode == 0:
                return True
        except Exception:
            pass
        pid_file = os.path.join(soft_paths['install_abspath_path'],'var','run','php-fpm.pid')
        if os.path.isfile(pid_file):
            try:
                with open(pid_file,'r') as f:
                    pid = f.read().strip()
                if pid.isdigit():
                    subprocess.run(['kill','-USR2',pid],capture_output=True,text=True)
                    return True
            except:
                pass
        Restart_PHP(version=version,is_windows=is_windows)
    return True

def RY_GET_PHP_CONF(version=None,is_windows=True):
    if not version: return ""
    soft_paths = get_php_path_info(version)
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if os.path.exists(conf_path):
        return ReadFile(conf_path)
    return ""

def RY_SAVE_PHP_CONF(version=None,conf="",is_windows=True):
    if not version: return False
    soft_paths = get_php_path_info(version)
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    conf = _dedup_extension_lines(conf)
    WriteFile(conf_path,conf)
    return True

def RY_GET_PHP_FPM_CONF(version=None,is_windows=True):
    if not version: return ""
    soft_paths = get_php_path_info(version)
    if is_windows:
        conf_path = soft_paths['windows_abspath_fpm_conf_path']
    else:
        conf_path = soft_paths['linux_abspath_fpm_conf_path']
    if os.path.exists(conf_path):
        return ReadFile(conf_path)
    return ""

def RY_SAVE_PHP_FPM_CONF(version=None,conf="",is_windows=True):
    if not version: return False
    soft_paths = get_php_path_info(version)
    if is_windows:
        conf_path = soft_paths['windows_abspath_fpm_conf_path']
    else:
        conf_path = soft_paths['linux_abspath_fpm_conf_path']
    if not conf_path:
        return False
    WriteFile(conf_path,conf)
    return True

def RY_GET_PHP_EXTENSIONS(version=None,is_windows=True):
    if not version: return []
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    if not os.path.exists(php_path):
        return []
    try:
        if is_windows:
            result = subprocess.run([php_path,'-m'],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            result = subprocess.run([php_path,'-m'],capture_output=True,text=True,encoding='utf-8',errors='replace')
        extensions = [ext.strip() for ext in result.stdout.strip().split('\n') if ext.strip()]
        return extensions
    except:
        return []

def RY_GET_PHP_EXTENSIONS_WITH_VERSION(version=None, is_windows=True):
    if not version: return {}
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    if not os.path.exists(php_path):
        return {}
    try:
        cmd = [php_path, '-r', "foreach(get_loaded_extensions() as $ext) echo $ext.'='.phpversion($ext).PHP_EOL;"]
        if is_windows:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        ext_versions = {}
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if '=' in line:
                name, ver = line.split('=', 1)
                ext_versions[name.strip()] = ver.strip()
        return ext_versions
    except Exception:
        return {}

def RY_GET_PHP_INFO(version=None,is_windows=True):
    if not version: return {}
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    info = {
        'version':version,
        'install_path':soft_paths['install_path'],
        'installed':os.path.exists(php_path),
        'running':is_php_running(version,is_windows=is_windows),
        'conf_path':soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path'],
        'extensions':[],
    }
    if info['installed']:
        info['extensions'] = RY_GET_PHP_EXTENSIONS(version,is_windows)
        v = check_php_version(php_path)
        if v:
            info['version'] = v
    return info

def _get_php_ini_value(content, key, default=""):
    match = re.search(r'^\s*' + re.escape(key) + r'\s*=\s*(.*)', content, re.MULTILINE)
    if match:
        val = match.group(1).strip().strip('"').strip("'")
        if val:
            return val
    return default

def _set_php_ini_value(content, key, value):
    pattern = r'^\s*;?\s*' + re.escape(key) + r'\s*=.*$'
    replacement = f'{key} = {value}'
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return content[:match.start()] + replacement + content[match.end():]
    else:
        return content + f'\n{key} = {value}'

def _dedup_extension_lines(content):
    seen = {}
    lines = content.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        m = re.match(r'^(?:zend_)?extension\s*=\s*(\S+)\s*$', stripped)
        if m:
            ext_name = m.group(1)
            if ext_name in seen:
                result.append(';' + line.lstrip(';'))
                continue
            seen[ext_name] = True
        result.append(line)
    return '\n'.join(result)

def RY_GET_PHP_CONFIG_PARAMS(version=None, is_windows=True):
    if not version: return {}
    soft_paths = get_php_path_info(version)
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if not os.path.exists(conf_path):
        return {}
    content = ReadFile(conf_path)
    params = {
        'memory_limit': _get_php_ini_value(content, 'memory_limit', '128M'),
        'max_execution_time': _get_php_ini_value(content, 'max_execution_time', '30'),
        'max_input_time': _get_php_ini_value(content, 'max_input_time', '60'),
        'upload_max_filesize': _get_php_ini_value(content, 'upload_max_filesize', '2M'),
        'post_max_size': _get_php_ini_value(content, 'post_max_size', '8M'),
        'max_file_uploads': _get_php_ini_value(content, 'max_file_uploads', '20'),
        'max_input_vars': _get_php_ini_value(content, 'max_input_vars', '1000'),
        'output_buffering': _get_php_ini_value(content, 'output_buffering', 'Off'),
        'display_errors': _get_php_ini_value(content, 'display_errors', 'Off'),
        'log_errors': _get_php_ini_value(content, 'log_errors', 'On'),
        'error_reporting': _get_php_ini_value(content, 'error_reporting', 'E_ALL'),
        'date_timezone': _get_php_ini_value(content, 'date.timezone', ''),
        'short_open_tag': _get_php_ini_value(content, 'short_open_tag', 'Off'),
        'open_basedir': _get_php_ini_value(content, 'open_basedir', ''),
        'expose_php': _get_php_ini_value(content, 'expose_php', 'On'),
        'allow_url_fopen': _get_php_ini_value(content, 'allow_url_fopen', 'On'),
        'allow_url_include': _get_php_ini_value(content, 'allow_url_include', 'Off'),
        'default_socket_timeout': _get_php_ini_value(content, 'default_socket_timeout', '60'),
        'disable_functions': _get_php_ini_value(content, 'disable_functions', ''),
        'opcache_enable': _get_php_ini_value(content, 'opcache.enable', '1'),
        'opcache_memory_consumption': _get_php_ini_value(content, 'opcache.memory_consumption', '128'),
        'opcache_interned_strings_buffer': _get_php_ini_value(content, 'opcache.interned_strings_buffer', '8'),
        'opcache_max_accelerated_files': _get_php_ini_value(content, 'opcache.max_accelerated_files', '10000'),
        'session_save_handler': _get_php_ini_value(content, 'session.save_handler', 'files'),
        'session_save_path': _get_php_ini_value(content, 'session.save_path', ''),
        'session_gc_maxlifetime': _get_php_ini_value(content, 'session.gc_maxlifetime', '1440'),
        'session_cookie_lifetime': _get_php_ini_value(content, 'session.cookie_lifetime', '0'),
        'session_cookie_httponly': _get_php_ini_value(content, 'session.cookie_httponly', '0'),
        'session_cookie_secure': _get_php_ini_value(content, 'session.cookie_secure', '0'),
        'session_use_strict_mode': _get_php_ini_value(content, 'session.use_strict_mode', '0'),
    }
    return params

def RY_SAVE_PHP_CONFIG_PARAMS(version=None, params={}, is_windows=True):
    if not version: return False
    soft_paths = get_php_path_info(version)
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if not os.path.exists(conf_path):
        return False
    content = ReadFile(conf_path)
    ini_key_map = {
        'memory_limit': 'memory_limit',
        'max_execution_time': 'max_execution_time',
        'max_input_time': 'max_input_time',
        'upload_max_filesize': 'upload_max_filesize',
        'post_max_size': 'post_max_size',
        'max_file_uploads': 'max_file_uploads',
        'max_input_vars': 'max_input_vars',
        'output_buffering': 'output_buffering',
        'display_errors': 'display_errors',
        'log_errors': 'log_errors',
        'error_reporting': 'error_reporting',
        'date_timezone': 'date.timezone',
        'short_open_tag': 'short_open_tag',
        'open_basedir': 'open_basedir',
        'expose_php': 'expose_php',
        'allow_url_fopen': 'allow_url_fopen',
        'allow_url_include': 'allow_url_include',
        'default_socket_timeout': 'default_socket_timeout',
        'disable_functions': 'disable_functions',
        'opcache_enable': 'opcache.enable',
        'opcache_memory_consumption': 'opcache.memory_consumption',
        'opcache_interned_strings_buffer': 'opcache.interned_strings_buffer',
        'opcache_max_accelerated_files': 'opcache.max_accelerated_files',
        'session_save_handler': 'session.save_handler',
        'session_save_path': 'session.save_path',
        'session_gc_maxlifetime': 'session.gc_maxlifetime',
        'session_cookie_lifetime': 'session.cookie_lifetime',
        'session_cookie_httponly': 'session.cookie_httponly',
        'session_cookie_secure': 'session.cookie_secure',
        'session_use_strict_mode': 'session.use_strict_mode',
    }
    for param_key, ini_key in ini_key_map.items():
        if param_key in params:
            val = params[param_key]
            if val is None:
                continue
            content = _set_php_ini_value(content, ini_key, str(val))
    content = _dedup_extension_lines(content)
    WriteFile(conf_path, content)
    return True

def RY_GET_PHP_DISABLED_FUNCTIONS(version=None, is_windows=True):
    if not version: return []
    soft_paths = get_php_path_info(version)
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if not os.path.exists(conf_path):
        return []
    content = ReadFile(conf_path)
    val = _get_php_ini_value(content, 'disable_functions', '')
    if val:
        return [f.strip() for f in val.split(',') if f.strip()]
    return []

def RY_SAVE_PHP_DISABLED_FUNCTIONS(version=None, functions=[], is_windows=True):
    if not version: return False
    soft_paths = get_php_path_info(version)
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if not os.path.exists(conf_path):
        return False
    content = ReadFile(conf_path)
    val = ','.join(functions)
    content = _set_php_ini_value(content, 'disable_functions', val)
    WriteFile(conf_path, content)
    return True

PHP_DANGEROUS_FUNCTIONS = [
    'exec', 'system', 'passthru', 'shell_exec', 'proc_open', 'popen',
    'pcntl_exec', 'pcntl_fork', 'pcntl_alarm', 'pcntl_signal',
    'pcntl_waitpid', 'pcntl_wexitstatus', 'pcntl_wifexited',
    'pcntl_wifsignaled', 'pcntl_wifstopped', 'pcntl_wstopsig',
    'pcntl_wtermsig', 'pcntl_signal_dispatch', 'pcntl_sigprocmask',
    'pcntl_sigtimedwait', 'pcntl_sigwaitinfo', 'pcntl_getpriority',
    'pcntl_setpriority', 'putenv', 'dl', 'show_source',
    'curl_exec', 'curl_multi_exec', 'parse_ini_file',
]

def RY_GET_PHP_DANGEROUS_FUNCTIONS():
    return PHP_DANGEROUS_FUNCTIONS

def RY_GET_PHP_FPM_POOL_PARAMS(version=None, is_windows=True):
    if not version: return {}
    soft_paths = get_php_path_info(version)
    if is_windows:
        pool_conf_path = soft_paths['windows_abspath_fpm_conf_path']
        if not os.path.exists(pool_conf_path):
            pool_conf_path = soft_paths['windows_abspath_conf_path']
    else:
        pool_conf_path = os.path.join(soft_paths['linux_abspath_fpm_conf_d_path'], 'www.conf')
        if not os.path.exists(pool_conf_path):
            pool_conf_path = soft_paths['linux_abspath_fpm_conf_path']
    if not os.path.exists(pool_conf_path):
        return {}
    content = ReadFile(pool_conf_path)
    params = {
        'pm': _get_php_ini_value(content, 'pm', 'dynamic'),
        'pm_max_children': _get_php_ini_value(content, 'pm.max_children', '50'),
        'pm_start_servers': _get_php_ini_value(content, 'pm.start_servers', '10'),
        'pm_min_spare_servers': _get_php_ini_value(content, 'pm.min_spare_servers', '5'),
        'pm_max_spare_servers': _get_php_ini_value(content, 'pm.max_spare_servers', '30'),
        'pm_max_requests': _get_php_ini_value(content, 'pm.max_requests', '1000'),
        'pm_process_idle_timeout': _get_php_ini_value(content, 'pm.process_idle_timeout', '10s'),
        'request_terminate_timeout': _get_php_ini_value(content, 'request_terminate_timeout', '100'),
        'request_slowlog_timeout': _get_php_ini_value(content, 'request_slowlog_timeout', '30'),
    }
    return params

def RY_SAVE_PHP_FPM_POOL_PARAMS(version=None, params={}, is_windows=True):
    if not version: return False
    soft_paths = get_php_path_info(version)
    if is_windows:
        pool_conf_path = soft_paths['windows_abspath_fpm_conf_path']
        if not os.path.exists(pool_conf_path):
            pool_conf_path = soft_paths['windows_abspath_conf_path']
    else:
        pool_conf_path = os.path.join(soft_paths['linux_abspath_fpm_conf_d_path'], 'www.conf')
        if not os.path.exists(pool_conf_path):
            pool_conf_path = soft_paths['linux_abspath_fpm_conf_path']
    if not os.path.exists(pool_conf_path):
        return False
    content = ReadFile(pool_conf_path)
    fpm_key_map = {
        'pm': 'pm',
        'pm_max_children': 'pm.max_children',
        'pm_start_servers': 'pm.start_servers',
        'pm_min_spare_servers': 'pm.min_spare_servers',
        'pm_max_spare_servers': 'pm.max_spare_servers',
        'pm_max_requests': 'pm.max_requests',
        'pm_process_idle_timeout': 'pm.process_idle_timeout',
        'request_terminate_timeout': 'request_terminate_timeout',
        'request_slowlog_timeout': 'request_slowlog_timeout',
    }
    for param_key, fpm_key in fpm_key_map.items():
        if param_key in params:
            val = params[param_key]
            if val is None:
                continue
            content = _set_php_ini_value(content, fpm_key, str(val))
    WriteFile(pool_conf_path, content)
    return True

PHP_FPM_PRESETS = {
    '1h512m': {'pm': 'dynamic', 'pm_max_children': '20', 'pm_start_servers': '3', 'pm_min_spare_servers': '2', 'pm_max_spare_servers': '5', 'pm_max_requests': '500'},
    '1h1g': {'pm': 'dynamic', 'pm_max_children': '30', 'pm_start_servers': '5', 'pm_min_spare_servers': '3', 'pm_max_spare_servers': '10', 'pm_max_requests': '500'},
    '2h2g': {'pm': 'dynamic', 'pm_max_children': '50', 'pm_start_servers': '10', 'pm_min_spare_servers': '5', 'pm_max_spare_servers': '20', 'pm_max_requests': '1000'},
    '2h4g': {'pm': 'dynamic', 'pm_max_children': '80', 'pm_start_servers': '15', 'pm_min_spare_servers': '8', 'pm_max_spare_servers': '30', 'pm_max_requests': '1000'},
    '4h8g': {'pm': 'dynamic', 'pm_max_children': '150', 'pm_start_servers': '25', 'pm_min_spare_servers': '10', 'pm_max_spare_servers': '50', 'pm_max_requests': '1000'},
}

def RY_GET_PHP_FPM_PRESETS():
    return PHP_FPM_PRESETS

@contextmanager
def _file_lock(lock_file, timeout=10):
    lock_dir = os.path.dirname(lock_file)
    if lock_dir and not os.path.exists(lock_dir):
        os.makedirs(lock_dir, exist_ok=True)
    start_time = time.time()
    while True:
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            if time.time() - start_time > timeout:
                raise TimeoutError(f"无法获取文件锁: {lock_file}")
            time.sleep(0.1)
    try:
        yield
    finally:
        try:
            os.close(fd)
            os.unlink(lock_file)
        except OSError:
            pass

def get_php_pool_port(site_name, php_version):
    pool_port_file = os.path.join(get_php_path_info(php_version)['install_abspath_path'], 'var', 'run', 'pool_ports.json')
    lock_file = pool_port_file + '.lock'
    ports_data = {}
    with _file_lock(lock_file):
        if os.path.exists(pool_port_file):
            try:
                with open(pool_port_file, 'r') as f:
                    ports_data = json.loads(f.read())
            except:
                pass
        if site_name in ports_data:
            return ports_data[site_name]
        base_port = 9100
        used_ports = set(ports_data.values())
        for port in range(base_port, 65535):
            if port not in used_ports:
                if not is_service_running(port=port):
                    ports_data[site_name] = port
                    try:
                        with open(pool_port_file, 'w') as f:
                            f.write(json.dumps(ports_data))
                    except:
                        pass
                    return port
    return None

def release_php_pool_port(site_name, php_version):
    pool_port_file = os.path.join(get_php_path_info(php_version)['install_abspath_path'], 'var', 'run', 'pool_ports.json')
    lock_file = pool_port_file + '.lock'
    if not os.path.exists(pool_port_file):
        return
    with _file_lock(lock_file):
        try:
            with open(pool_port_file, 'r') as f:
                ports_data = json.loads(f.read())
            if site_name in ports_data:
                del ports_data[site_name]
                with open(pool_port_file, 'w') as f:
                    f.write(json.dumps(ports_data))
        except:
            pass

def create_php_fpm_pool_conf(site_name, site_path, php_version, pool_params=None, is_windows=True):
    soft_paths = get_php_path_info(php_version)
    if is_windows:
        pool_port = soft_paths['fpm_port']
    else:
        pool_port = get_php_pool_port(site_name, php_version)
        if not pool_port:
            return False, "无法分配Pool端口"
    if not pool_params:
        pool_params = PHP_FPM_PRESETS.get('2h2g', {})
    pm = pool_params.get('pm', 'dynamic')
    pm_max_children = pool_params.get('pm_max_children', '50')
    pm_start_servers = pool_params.get('pm_start_servers', '10')
    pm_min_spare_servers = pool_params.get('pm_min_spare_servers', '5')
    pm_max_spare_servers = pool_params.get('pm_max_spare_servers', '20')
    pm_max_requests = pool_params.get('pm_max_requests', '1000')
    request_terminate_timeout = pool_params.get('request_terminate_timeout', '100')
    pool_name = site_name.replace('.', '_').replace('-', '_')
    pool_log_dir = os.path.join(site_path, 'logs')
    if not os.path.exists(pool_log_dir):
        os.makedirs(pool_log_dir, exist_ok=True)
    if is_windows:
        listen_addr = f"127.0.0.1:{pool_port}"
    else:
        socket_dir = os.path.join(soft_paths['install_abspath_path'], 'tmp')
        if not os.path.exists(socket_dir):
            os.makedirs(socket_dir, exist_ok=True)
        listen_addr = f"{socket_dir}/php-cgi-{pool_name}.sock"
    if is_windows:
        pool_conf_content = f"""[{pool_name}]
listen = {listen_addr}
pm = {pm}
pm.max_children = {pm_max_children}
pm.start_servers = {pm_start_servers}
pm.min_spare_servers = {pm_min_spare_servers}
pm.max_spare_servers = {pm_max_spare_servers}
pm.max_requests = {pm_max_requests}
request_terminate_timeout = {request_terminate_timeout}
"""
    else:
        slowlog_path = os.path.join(soft_paths['install_abspath_path'], 'var', 'log', f'php-slow-{pool_name}.log')
        pool_conf_content = f"""[{pool_name}]
user = www
group = www
listen = {listen_addr}
listen.backlog = 8192
pm = {pm}
pm.max_children = {pm_max_children}
pm.start_servers = {pm_start_servers}
pm.min_spare_servers = {pm_min_spare_servers}
pm.max_spare_servers = {pm_max_spare_servers}
pm.max_requests = {pm_max_requests}
request_terminate_timeout = {request_terminate_timeout}
request_slowlog_timeout = 30
slowlog = {slowlog_path}
php_admin_value[open_basedir] = {site_path}:/tmp:/proc
php_admin_value[error_log] = {pool_log_dir}/php-error.log
php_admin_flag[log_errors] = on
"""
    if is_windows:
        pool_conf_dir = os.path.join(soft_paths['install_abspath_path'], 'fpm-pool.d')
    else:
        pool_conf_dir = soft_paths['linux_abspath_fpm_conf_d_path']
    if not os.path.exists(pool_conf_dir):
        os.makedirs(pool_conf_dir, exist_ok=True)
    pool_conf_path = os.path.join(pool_conf_dir, f"{pool_name}.conf")
    WriteFile(pool_conf_path, pool_conf_content)
    return True, {"pool_port": pool_port, "pool_name": pool_name, "listen_addr": listen_addr}

def delete_php_fpm_pool_conf(site_name, php_version, is_windows=True):
    pool_name = site_name.replace('.', '_').replace('-', '_')
    soft_paths = get_php_path_info(php_version)
    if is_windows:
        pool_conf_path = os.path.join(soft_paths['install_abspath_path'], 'fpm-pool.d', f"{pool_name}.conf")
    else:
        pool_conf_path = os.path.join(soft_paths['linux_abspath_fpm_conf_d_path'], f"{pool_name}.conf")
    if os.path.exists(pool_conf_path):
        DeleteFile(pool_conf_path, empty_tips=False)
    release_php_pool_port(site_name, php_version)
    return True

def get_php_fpm_pool_conf(site_name, php_version, is_windows=True):
    pool_name = site_name.replace('.', '_').replace('-', '_')
    soft_paths = get_php_path_info(php_version)
    if is_windows:
        pool_conf_path = os.path.join(soft_paths['install_abspath_path'], 'fpm-pool.d', f"{pool_name}.conf")
    else:
        pool_conf_path = os.path.join(soft_paths['linux_abspath_fpm_conf_d_path'], f"{pool_name}.conf")
    if not os.path.exists(pool_conf_path):
        return None
    return ReadFile(pool_conf_path)

def get_php_fpm_pool_port(site_name, php_version):
    pool_port_file = os.path.join(get_php_path_info(php_version)['install_abspath_path'], 'var', 'run', 'pool_ports.json')
    if not os.path.exists(pool_port_file):
        return None
    try:
        with open(pool_port_file, 'r') as f:
            ports_data = json.loads(f.read())
        return ports_data.get(site_name)
    except:
        return None

def RY_VALIDATE_PHP_CONFIG(version=None, is_windows=True):
    if not version: return {'valid': False, 'msg': 'version is required'}
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if not os.path.exists(php_path):
        return {'valid': False, 'msg': 'PHP executable not found'}
    if not os.path.exists(conf_path):
        return {'valid': False, 'msg': 'php.ini not found'}
    try:
        if is_windows:
            result = subprocess.run(
                [php_path, '-c', conf_path, '-m'],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            result = subprocess.run(
                [php_path, '-c', conf_path, '-m'],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
            )
        if result.returncode == 0:
            return {'valid': True, 'msg': 'OK'}
        else:
            err = result.stderr.strip() if result.stderr else result.stdout.strip()
            return {'valid': False, 'msg': err}
    except subprocess.TimeoutExpired:
        return {'valid': False, 'msg': 'Validation timeout'}
    except Exception as e:
        return {'valid': False, 'msg': str(e)}

def RY_CLEAR_PHP_OPCACHE(version=None, is_windows=True):
    if not version: return False
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    if not os.path.exists(php_path):
        return False
    try:
        opcache_script = "<?php if(function_exists('opcache_reset')){opcache_reset();echo 'OK';}else{echo 'NO_OPCACHE';} ?>"
        tmp_script = os.path.join(soft_paths['install_abspath_path'], 'ry_opcache_reset.php')
        WriteFile(tmp_script, opcache_script)
        if is_windows:
            result = subprocess.run(
                [php_path, tmp_script],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            result = subprocess.run(
                [php_path, tmp_script],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
            )
        DeleteFile(tmp_script, empty_tips=False)
        if 'OK' in result.stdout:
            return True
        return False
    except:
        return False

def RY_GET_PHP_SLOWLOG(version=None, is_windows=True):
    if not version: return ""
    soft_paths = get_php_path_info(version)
    slowlog_path = os.path.join(soft_paths['install_abspath_path'], 'var', 'log', 'php-slow.log')
    if not os.path.exists(slowlog_path):
        return ""
    return system.GetFileLastNumsLines(slowlog_path, 2000)

def RY_CLEAR_PHP_ERROR_LOG(version=None, is_windows=True):
    if not version: return False
    soft_paths = get_php_path_info(version)
    log_path = soft_paths['error_log_path']
    abs_log_path = os.path.join(soft_paths['install_abspath_path'], 'var', 'log', 'php-fpm.log')
    for p in [abs_log_path]:
        if os.path.exists(p):
            WriteFile(p, "")
    return True

def RY_CLEAR_PHP_SLOWLOG(version=None, is_windows=True):
    if not version: return False
    soft_paths = get_php_path_info(version)
    slowlog_path = os.path.join(soft_paths['install_abspath_path'], 'var', 'log', 'php-slow.log')
    if os.path.exists(slowlog_path):
        WriteFile(slowlog_path, "")
    return True

def RY_GET_PHP_FPM_STATUS(version=None, is_windows=True):
    if not version: return {'status': {}, 'processes': []}
    soft_paths = get_php_path_info(version)
    if is_windows:
        status_data = {}
        process_list = []
        try:
            import psutil
            install_path = soft_paths['install_abspath_path'].lower()
            total = 0
            idle = 0
            active = 0
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time', 'num_threads', 'cpu_times']):
                if proc.info['name'] and proc.info['name'].lower() == 'php-cgi.exe':
                    try:
                        exe_path = proc.exe().lower()
                        if install_path in exe_path:
                            total += 1
                            pid = proc.pid
                            create_time = proc.info.get('create_time', 0)
                            running_seconds = int(time.time() - create_time) if create_time else 0
                            process_list.append({
                                'pid': pid,
                                'state': 'Running',
                                'start_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(create_time)) if create_time else '',
                                'start_since': running_seconds,
                                'requests': 0,
                                'request_uri': '-',
                                'request_method': '-',
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            active = total
            status_data = {
                'pool': 'www',
                'process_manager': 'dynamic',
                'start_time': '',
                'start_since': 0,
                'accepted_conn': 0,
                'listen_queue': 0,
                'max_listen_queue': 0,
                'listen_queue_len': 0,
                'idle_processes': idle,
                'active_processes': active,
                'total_processes': total,
                'max_active_processes': 0,
                'max_children_reached': 0,
                'slow_requests': 0,
            }
        except Exception:
            pass
        return {'status': status_data, 'processes': process_list}
    fpm_conf_path = soft_paths.get('linux_abspath_fpm_conf_path', '')
    if not fpm_conf_path or not os.path.exists(fpm_conf_path):
        return {'status': {}, 'processes': []}
    content = ReadFile(fpm_conf_path)
    status_path = None
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith(';') or stripped.startswith('#'):
            continue
        m = re.match(r'^pm\.status_path\s*=\s*(.+)$', stripped)
        if m:
            status_path = m.group(1).strip().strip('"').strip("'")
            break
    if not status_path:
        content += '\npm.status_path = /fpm_status\n'
        WriteFile(fpm_conf_path, content)
        status_path = '/fpm_status'
        from utils.install.install_soft import Ry_Reload_Soft
        Ry_Reload_Soft(name='php', is_windows=False, version=version)
    status_data = {}
    process_list = []
    try:
        import urllib.request
        url = f'http://127.0.0.1{status_path}'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode('utf-8', errors='replace')
        for line in text.split('\n'):
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip().replace(' ', '_').lower()
                val = parts[1].strip()
                try:
                    val = int(val)
                except ValueError:
                    pass
                status_data[key] = val
        full_url = f'http://127.0.0.1{status_path}?full'
        req2 = urllib.request.Request(full_url)
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            text2 = resp2.read().decode('utf-8', errors='replace')
        current_proc = {}
        for line in text2.split('\n'):
            stripped = line.strip()
            if stripped.startswith('****'):
                if current_proc.get('pid'):
                    process_list.append(current_proc)
                current_proc = {}
                continue
            if ':' in stripped:
                parts = stripped.split(':', 1)
                key = parts[0].strip().replace(' ', '_').lower()
                val = parts[1].strip()
                try:
                    val = int(val)
                except ValueError:
                    pass
                current_proc[key] = val
        if current_proc.get('pid'):
            process_list.append(current_proc)
    except Exception:
        pass
    return {'status': status_data, 'processes': process_list}

def RY_GET_PHP_EXTENSION_LIST(version=None, is_windows=True):
    if not version: return {'installed': [], 'available': []}
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    if not os.path.exists(php_path):
        return {'installed': [], 'available': []}
    installed = RY_GET_PHP_EXTENSIONS(version, is_windows)
    installed_lower = [ext.lower() for ext in installed]
    ext_versions = RY_GET_PHP_EXTENSIONS_WITH_VERSION(version, is_windows)
    available_names = []
    if is_windows:
        ext_dir = os.path.join(soft_paths['install_abspath_path'], 'ext')
        if os.path.exists(ext_dir):
            for f in os.listdir(ext_dir):
                if f.endswith('.dll'):
                    ext_name = f[4:-4] if f.startswith('php_') else f[:-4]
                    parts = ext_name.split('-')
                    ext_name = parts[0] if parts else ext_name
                    if ext_name and ext_name.lower() not in [a.lower() for a in available_names]:
                        available_names.append(ext_name)
    else:
        ext_dir = os.path.join(soft_paths['install_abspath_path'], 'lib', 'php', 'extensions')
        if os.path.exists(ext_dir):
            for root, dirs, files in os.walk(ext_dir):
                for f in files:
                    if f.endswith('.so'):
                        ext_name = f.replace('.so', '')
                        parts = ext_name.split('-')
                        ext_name = parts[0] if parts else ext_name
                        if ext_name and ext_name.lower() not in [a.lower() for a in available_names]:
                            available_names.append(ext_name)
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if os.path.exists(conf_path):
        content = ReadFile(conf_path)
        commented_exts = re.findall(r'^\s*;\s*extension\s*=\s*(\S+)\s*$', content, re.MULTILINE)
        for ext_line in commented_exts:
            ext_name = ext_line.strip()
            if is_windows:
                if ext_line.lower().endswith('.dll'):
                    ext_name = ext_line[4:-4] if ext_line.startswith('php_') else ext_line[:-4]
                    parts = ext_name.split('-')
                    ext_name = parts[0] if parts else ext_name
            else:
                if ext_line.lower().endswith('.so'):
                    ext_name = ext_line[:-3]
                    parts = ext_name.split('-')
                    ext_name = parts[0] if parts else ext_name
            if ext_name and ext_name.lower() not in [a.lower() for a in available_names] and ext_name.lower() not in installed_lower:
                available_names.append(ext_name)
    pecl_map = {}
    pecl_names_lower = set()
    for pecl_ext in RY_PECL_COMMON_EXTENSIONS:
        pecl_map[pecl_ext['name'].lower()] = pecl_ext
        pecl_names_lower.add(pecl_ext['name'].lower())
    available_info = []
    for ext_name in available_names:
        if ext_name.lower() in installed_lower:
            continue
        if ext_name.lower() in pecl_names_lower:
            continue
        has_dll = False
        if is_windows:
            dll_path = os.path.join(soft_paths['install_abspath_path'], 'ext', f'php_{ext_name}.dll')
            has_dll = os.path.exists(dll_path)
        available_info.append({
            'name': ext_name,
            'desc': '',
            'category': 'builtin',
            'has_file': has_dll if is_windows else True,
        })
    installed_info = []
    for ext_name in installed:
        if ext_name.lower() in pecl_names_lower:
            continue
        installed_info.append({
            'name': ext_name,
            'desc': '',
            'category': 'builtin',
            'version': ext_versions.get(ext_name, ''),
        })
    return {'installed': installed_info, 'available': available_info}

def RY_TOGGLE_PHP_EXTENSION(version=None, ext_name="", enable=True, is_windows=True):
    if not version or not ext_name: return False
    soft_paths = get_php_path_info(version)
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if not os.path.exists(conf_path):
        return False
    content = ReadFile(conf_path)
    if is_windows:
        dll_ext = f'php_{ext_name}.dll'
        ext_patterns = [re.escape(ext_name), re.escape(dll_ext)]
    else:
        so_ext = f'{ext_name}.so'
        ext_patterns = [re.escape(ext_name), re.escape(so_ext)]
    ext_pattern = '(?:' + '|'.join(ext_patterns) + ')'
    if enable:
        active_pattern = r'^\s*extension\s*=\s*' + ext_pattern + r'\s*$'
        if re.search(active_pattern, content, re.MULTILINE):
            return True
        comment_pattern = r'^\s*;\s*extension\s*=\s*' + ext_pattern + r'\s*$'
        match = re.search(comment_pattern, content, re.MULTILINE)
        if match:
            content = content[:match.start()] + f'extension = {ext_name}' + content[match.end():]
        else:
            ext_section = '\n; === RUYI EXT ===\nextension = ' + ext_name + '\n'
            content = content + ext_section
    else:
        active_pattern = r'^\s*extension\s*=\s*' + ext_pattern + r'\s*$'
        matches = list(re.finditer(active_pattern, content, re.MULTILINE))
        for m in reversed(matches):
            content = content[:m.start()] + f';extension = {ext_name}' + content[m.end():]
    WriteFile(conf_path, content)
    return True

def RY_GET_PHPINFO(version=None, is_windows=True):
    if not version: return ""
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    if not os.path.exists(php_path):
        return ""
    try:
        php_code = 'ob_start(); phpinfo(INFO_ALL); $html = ob_get_clean(); echo $html;'
        if is_windows:
            result = subprocess.run(
                [php_path, '-d', 'html_errors=1', '-r', php_code],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            result = subprocess.run(
                [php_path, '-d', 'html_errors=1', '-r', php_code],
                capture_output=True, timeout=10
            )
        output = result.stdout.decode('utf-8', errors='replace')
        if output and '<table' in output.lower():
            return output
    except Exception:
        pass
    try:
        if is_windows:
            result = subprocess.run(
                [php_path, '-r', 'phpinfo();'],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            result = subprocess.run(
                [php_path, '-r', 'phpinfo();'],
                capture_output=True, timeout=10
            )
        text_output = result.stdout.decode('utf-8', errors='replace')
        if not text_output:
            return ""
        return _phpinfo_text_to_html(text_output)
    except Exception:
        return ""

def _phpinfo_text_to_html(text):
    def esc(s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    lines = text.split('\n')
    php_version = ""
    sections = []
    current_section = None
    current_rows = []
    for line in lines:
        line = line.rstrip()
        if not line.strip():
            continue
        if '=>' in line:
            parts = line.split('=>', 1)
            key = parts[0].strip()
            val = parts[1].strip() if len(parts) > 1 else ''
            if not php_version and key == 'PHP Version':
                php_version = val
            if current_section is None:
                current_section = 'General'
            current_rows.append((key, val))
        elif line.strip() and not line.startswith(' ') and not line.startswith("\t"):
            if current_section is not None:
                sections.append((current_section, current_rows))
            current_section = line.strip()
            current_rows = []
    if current_section is not None:
        sections.append((current_section, current_rows))
    css = """
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;font-size:13px;margin:0;padding:16px;background:#fff;color:#333;overflow-x:hidden;}
    .phpinfo-header{background:linear-gradient(135deg,#4F46E5,#7C3AED);color:#fff;padding:20px 24px;border-radius:8px;margin-bottom:20px;}
    .phpinfo-header h1{margin:0 0 4px 0;font-size:22px;font-weight:600;}
    .phpinfo-header .version{font-size:14px;opacity:0.9;}
    .phpinfo-search{margin-bottom:16px;display:flex;gap:10px;align-items:center;}
    .phpinfo-search input{width:300px;padding:6px 12px;border:1px solid #ddd;border-radius:4px;font-size:13px;outline:none;}
    .phpinfo-search input:focus{border-color:#4F46E5;box-shadow:0 0 0 2px rgba(79,70,229,0.15);}
    .phpinfo-search .count{font-size:12px;color:#999;}
    .section{margin-bottom:20px;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;}
    .section-title{background:#f8f9fa;padding:10px 16px;font-weight:600;font-size:14px;color:#1f2937;border-bottom:1px solid #e5e7eb;cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none;}
    .section-title:hover{background:#f0f1f3;}
    .section-title .arrow{transition:transform 0.2s;font-size:12px;color:#9ca3af;}
    .section.collapsed .section-title .arrow{transform:rotate(-90deg);}
    .section.collapsed .section-body{display:none;}
    .section-body{padding:0;}
    .row{display:flex;border-bottom:1px solid #f0f0f0;}
    .row:last-child{border-bottom:none;}
    .row:nth-child(even){background:#fafbfc;}
    .row:hover{background:#f0f4ff;}
    .key{width:35%;min-width:0;padding:7px 16px;font-weight:500;color:#374151;font-size:13px;word-break:break-all;overflow:hidden;text-overflow:ellipsis;}
    .val{width:65%;min-width:0;padding:7px 16px;color:#6b7280;font-size:13px;word-break:break-all;overflow:hidden;}
    .highlight{background:#fef08a !important;}
    .no-result{padding:40px;text-align:center;color:#999;font-size:14px;}
    """
    html_parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8">',
        f'<style>{css}</style>',
        '</head><body>',
        f'<div class="phpinfo-header"><h1>PHP Info</h1>',
        f'<div class="version">PHP {esc(php_version)}</div></div>',
        '<div class="phpinfo-search">',
        '<input type="text" id="searchInput" placeholder="Search..." oninput="filterInfo(this.value)" />',
        '<span class="count" id="resultCount"></span>',
        '</div>',
        '<div id="phpinfoContent">'
    ]
    for sec_name, rows in sections:
        html_parts.append(f'<div class="section">')
        html_parts.append(f'<div class="section-title" onclick="this.parentElement.classList.toggle(\'collapsed\')"><span>{esc(sec_name)}</span><span class="arrow">▼</span></div>')
        html_parts.append('<div class="section-body">')
        for key, val in rows:
            html_parts.append(f'<div class="row"><div class="key">{esc(key)}</div><div class="val">{esc(val)}</div></div>')
        html_parts.append('</div></div>')
    html_parts.append('</div>')
    js = """
    function filterInfo(query){
        var sections=document.querySelectorAll('.section');
        var q=query.toLowerCase().trim();
        var totalVisible=0;
        var totalAll=0;
        sections.forEach(function(sec){
            var rows=sec.querySelectorAll('.row');
            var secVisible=0;
            rows.forEach(function(row){
                totalAll++;
                var text=row.textContent.toLowerCase();
                if(!q||text.indexOf(q)!==-1){
                    row.style.display='';secVisible++;totalVisible++;
                    if(q){row.classList.add('highlight');}else{row.classList.remove('highlight');}
                }else{
                    row.style.display='none';row.classList.remove('highlight');
                }
            });
            if(secVisible>0||!q){
                sec.style.display='';
                if(q&&secVisible===0){sec.classList.add('collapsed');}
                else if(q){sec.classList.remove('collapsed');}
            }else{
                sec.style.display='none';
            }
        });
        var countEl=document.getElementById('resultCount');
        if(q){countEl.textContent=totalVisible+' / '+totalAll;}else{countEl.textContent='';}
    }
    """
    html_parts.append(f'<script>{js}</script>')
    html_parts.append('</body></html>')
    return '\n'.join(html_parts)

RY_PHP_BUILTIN_EXTENSIONS = [
    'bcmath', 'calendar', 'ctype', 'curl', 'date', 'dom', 'exif', 'fileinfo',
    'filter', 'ftp', 'gd', 'gettext', 'hash', 'iconv', 'intl', 'json', 'ldap',
    'libxml', 'mbstring', 'mysqli', 'mysqlnd', 'odbc', 'opcache', 'openssl',
    'pcntl', 'pcre', 'pdo', 'pdo_mysql', 'pdo_pgsql', 'pdo_sqlite', 'pdo_odbc',
    'pgsql', 'phar', 'posix', 'readline', 'reflection', 'session', 'shmop',
    'simplexml', 'soap', 'sockets', 'sodium', 'spl', 'sqlite3', 'standard',
    'sysvmsg', 'sysvsem', 'sysvshm', 'tidy', 'tokenizer', 'xml', 'xmlreader',
    'xmlwriter', 'xsl', 'zip', 'zlib', 'ffi', 'pdo_dblib', 'pdo_sqlsrv',
    'sqlsrv', 'enchant', 'pspell', 'snmp', 'imap', 'xmlrpc',
]

RY_PECL_COMMON_EXTENSIONS = [
    {'name': 'redis', 'desc': 'Redis客户端', 'category': 'cache'},
    {'name': 'memcached', 'desc': 'Memcached客户端', 'category': 'cache'},
    {'name': 'mongodb', 'desc': 'MongoDB客户端', 'category': 'database'},
    {'name': 'swoole', 'desc': '高性能异步网络通信框架', 'category': 'framework'},
    {'name': 'xlswriter', 'desc': 'Excel读写扩展', 'category': 'utility'},
    {'name': 'imagick', 'desc': 'ImageMagick图像处理', 'category': 'image'},
    {'name': 'yaml', 'desc': 'YAML解析器', 'category': 'utility'},
    {'name': 'rdkafka', 'desc': 'Kafka客户端', 'category': 'cache'},
    {'name': 'amqp', 'desc': 'AMQP消息队列协议', 'category': 'cache'},
    {'name': 'event', 'desc': 'Libevent事件驱动', 'category': 'network'},
    {'name': 'grpc', 'desc': 'gRPC框架', 'category': 'framework'},
    {'name': 'protobuf', 'desc': 'Protocol Buffers', 'category': 'utility'},
    {'name': 'ds', 'desc': '数据结构扩展', 'category': 'utility'},
    {'name': 'uv', 'desc': 'Libuv异步IO', 'category': 'network'},
]

def RY_GET_PECL_EXTENSIONS(version=None, is_windows=True):
    if not version: return {'installed': [], 'available': []}
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    if not os.path.exists(php_path):
        return {'installed': [], 'available': []}
    installed_exts = RY_GET_PHP_EXTENSIONS(version, is_windows)
    installed_lower = [e.lower() for e in installed_exts]
    ext_versions = RY_GET_PHP_EXTENSIONS_WITH_VERSION(version, is_windows)
    ext_dir = os.path.join(soft_paths['install_abspath_path'], 'ext') if is_windows else None
    installed = []
    available = []
    for ext in RY_PECL_COMMON_EXTENSIONS:
        has_file = os.path.exists(os.path.join(ext_dir, f'php_{ext["name"]}.dll')) if is_windows else True
        windows_supported = ext['name'] not in RY_PECL_WINDOWS_UNSUPPORTED
        ext_info = {
            'name': ext['name'], 'desc': ext['desc'], 'category': ext['category'],
            'has_file': has_file, 'windows_supported': windows_supported,
            'version': ext_versions.get(ext['name'], ''),
        }
        if ext['name'].lower() in installed_lower:
            installed.append(ext_info)
        else:
            available.append(ext_info)
    return {'installed': installed, 'available': available}

RY_PECL_WINDOWS_DOWNLOAD_MAP = {
    'redis': 'https://windows.php.net/downloads/pecl/releases/redis/',
    'mongodb': 'https://windows.php.net/downloads/pecl/releases/mongodb/',
    'imagick': 'https://windows.php.net/downloads/pecl/releases/imagick/',
    'xlswriter': 'https://windows.php.net/downloads/pecl/releases/xlswriter/',
    'memcached': 'https://windows.php.net/downloads/pecl/releases/memcached/',
    'yaml': 'https://windows.php.net/downloads/pecl/releases/yaml/',
    'protobuf': 'https://windows.php.net/downloads/pecl/releases/protobuf/',
    'grpc': 'https://windows.php.net/downloads/pecl/releases/grpc/',
    'ds': 'https://windows.php.net/downloads/pecl/releases/ds/',
}

RY_PECL_WINDOWS_UNSUPPORTED = ['swoole', 'rdkafka', 'amqp', 'event', 'uv']

def _ry_get_php_thread_safety(php_path):
    try:
        if current_os == 'windows':
            result = subprocess.run(
                [php_path, '-r', 'echo PHP_ZTS ? "ts" : "nts";'],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            result = subprocess.run(
                [php_path, '-r', 'echo PHP_ZTS ? "ts" : "nts";'],
                capture_output=True, timeout=10
            )
        output = result.stdout.decode('utf-8', errors='replace').strip().lower()
        if output in ('ts', 'nts'):
            return output
    except Exception:
        pass
    return 'nts'

def _ry_get_php_arch():
    arch = platform.machine().lower()
    if arch in ('x86_64', 'amd64'):
        return 'x64'
    elif arch in ('aarch64', 'arm64'):
        return 'arm64'
    return 'x86'

def _ry_find_pecl_dll_url(ext_name, php_version, ts_mode, arch):
    base_url = RY_PECL_WINDOWS_DOWNLOAD_MAP.get(ext_name)
    if not base_url:
        return None
    try:
        import requests as req
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        r = req.get(base_url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        import re as _re
        version_dirs = _re.findall(r'href="(\d+\.\d+\.\d+)/"', r.text)
        if not version_dirs:
            version_dirs = _re.findall(r'href="(\d+\.\d+\.\d+\w*)/"', r.text)
        if not version_dirs:
            return None
        from packaging.version import Version
        try:
            version_dirs.sort(key=Version, reverse=True)
        except Exception:
            version_dirs.sort(reverse=True)
        major_minor = '.'.join(php_version.split('.')[:2])
        for ver_dir in version_dirs:
            ver_url = base_url + ver_dir + '/'
            r2 = req.get(ver_url, headers=headers, timeout=15)
            if r2.status_code != 200:
                continue
            dll_pattern = rf'href="(php_{_re.escape(ext_name)}-{_re.escape(ver_dir)}-{_re.escape(major_minor)}-{_re.escape(ts_mode)}-{_re.escape(arch)}\.zip)"'
            dll_matches = _re.findall(dll_pattern, r2.text, _re.IGNORECASE)
            if dll_matches:
                return ver_url + dll_matches[0]
            dll_pattern2 = rf'href="(php_{_re.escape(ext_name)}-\S+?-{_re.escape(major_minor)}-{_re.escape(ts_mode)}-{_re.escape(arch)}\.zip)"'
            dll_matches2 = _re.findall(dll_pattern2, r2.text, _re.IGNORECASE)
            if dll_matches2:
                return ver_url + dll_matches2[0]
        return None
    except Exception:
        return None

def _ry_install_pecl_extension_windows(version, ext_name, soft_paths, php_path, conf_path):
    ext_dir = os.path.join(soft_paths['install_abspath_path'], 'ext')
    dll_path = os.path.join(ext_dir, f'php_{ext_name}.dll')
    if os.path.exists(dll_path):
        result = RY_TOGGLE_PHP_EXTENSION(version, ext_name, enable=True, is_windows=True)
        if result:
            return {'success': True, 'msg': f'{ext_name} 已启用（DLL已存在）'}
        return {'success': False, 'msg': f'{ext_name} 扩展文件已存在且已启用'}
    ts_mode = _ry_get_php_thread_safety(php_path)
    arch = _ry_get_php_arch()
    dll_url = _ry_find_pecl_dll_url(ext_name, version, ts_mode, arch)
    if not dll_url:
        return {'success': False, 'msg': f'未找到 {ext_name} 扩展的Windows DLL下载地址，请手动下载 php_{ext_name}.dll 放入 {ext_dir}'}
    tmp_dir = GetTmpPath()
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    zip_filename = get_file_name_from_url(dll_url)
    zip_path = os.path.join(tmp_dir, zip_filename)
    dl_result = download_url_file(dll_url, save_path=zip_path)
    if not dl_result or not os.path.exists(zip_path):
        return {'success': False, 'msg': f'下载 {ext_name} 扩展失败，请检查网络连接'}
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            dll_found = False
            for member in zf.namelist():
                fname = os.path.basename(member)
                if fname.lower() == f'php_{ext_name.lower()}.dll':
                    with zf.open(member) as src, open(dll_path, 'wb') as dst:
                        dst.write(src.read())
                    dll_found = True
                    break
            if not dll_found:
                for member in zf.namelist():
                    fname = os.path.basename(member)
                    if fname.lower().endswith('.dll') and ext_name.lower() in fname.lower():
                        with zf.open(member) as src, open(dll_path, 'wb') as dst:
                            dst.write(src.read())
                        dll_found = True
                        break
        if os.path.exists(zip_path):
            DeleteFile(zip_path)
        if not dll_found:
            return {'success': False, 'msg': f'下载包中未找到 php_{ext_name}.dll'}
    except Exception as e:
        if os.path.exists(zip_path):
            DeleteFile(zip_path)
        return {'success': False, 'msg': f'解压扩展包失败: {str(e)[:200]}'}
    RY_TOGGLE_PHP_EXTENSION(version, ext_name, enable=True, is_windows=True)
    return {'success': True, 'msg': f'{ext_name} 扩展安装成功'}

def RY_INSTALL_PECL_EXTENSION(version=None, ext_name="", is_windows=True):
    if not version or not ext_name: return {'success': False, 'msg': '参数错误'}
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if not os.path.exists(php_path):
        return {'success': False, 'msg': 'PHP未安装'}
    if ext_name in RY_PHP_BUILTIN_EXTENSIONS:
        result = RY_TOGGLE_PHP_EXTENSION(version, ext_name, enable=True, is_windows=is_windows)
        if result:
            return {'success': True, 'msg': f'{ext_name} 已启用'}
        return {'success': False, 'msg': f'{ext_name} 启用失败'}
    if is_windows:
        if ext_name in RY_PECL_WINDOWS_UNSUPPORTED:
            return {'success': False, 'msg': f'{ext_name} 扩展不支持Windows系统，请在Linux环境下安装'}
        return _ry_install_pecl_extension_windows(version, ext_name, soft_paths, php_path, conf_path)
    pecl_path = os.path.join(soft_paths['install_abspath_path'], 'bin', 'pecl')
    if os.path.exists(pecl_path):
        try:
            result = subprocess.run(
                [pecl_path, 'install', ext_name],
                capture_output=True, text=True, timeout=600,
                env={**os.environ, 'PHP_PEAR_PHP_BIN': php_path}
            )
            if result.returncode == 0:
                so_pattern = re.compile(r'Installing\s+.*?(\S+\.so)', re.IGNORECASE)
                so_match = so_pattern.search(result.stdout)
                if so_match:
                    so_name = so_match.group(1).replace('.so', '')
                    if os.path.exists(conf_path):
                        content = ReadFile(conf_path)
                        active_pattern = r'^\s*extension\s*=\s*' + re.escape(so_name) + r'\s*$'
                        if not re.search(active_pattern, content, re.MULTILINE):
                            content = content + f'\nextension = {so_name}\n'
                            WriteFile(conf_path, content)
                return {'success': True, 'msg': f'{ext_name} 安装成功'}
            else:
                err_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                return {'success': False, 'msg': f'安装失败: {err_msg[:200]}'}
        except subprocess.TimeoutExpired:
            return {'success': False, 'msg': f'{ext_name} 安装超时（超过10分钟），编译安装可能需要较长时间，请稍后查看扩展列表确认是否安装成功'}
        except Exception as e:
            return {'success': False, 'msg': f'安装异常: {str(e)[:200]}'}
    else:
        return {'success': False, 'msg': 'pecl命令不存在，请确认PHP安装是否完整'}

def RY_UNINSTALL_PECL_EXTENSION(version=None, ext_name="", is_windows=True):
    if not version or not ext_name: return {'success': False, 'msg': '参数错误'}
    soft_paths = get_php_path_info(version)
    php_path = soft_paths['windows_abspath_php_path'] if is_windows else soft_paths['linux_abspath_php_path']
    conf_path = soft_paths['windows_abspath_conf_path'] if is_windows else soft_paths['linux_abspath_conf_path']
    if not os.path.exists(php_path):
        return {'success': False, 'msg': 'PHP未安装'}
    if not os.path.exists(conf_path):
        return {'success': False, 'msg': 'php.ini不存在'}
    content = ReadFile(conf_path)
    active_pattern = r'^\s*extension\s*=\s*' + re.escape(ext_name) + r'\s*$'
    matches = list(re.finditer(active_pattern, content, re.MULTILINE))
    for m in reversed(matches):
        content = content[:m.start()] + f';extension = {ext_name}' + content[m.end():]
    if matches:
        WriteFile(conf_path, content)
    if ext_name in RY_PHP_BUILTIN_EXTENSIONS:
        return {'success': True, 'msg': f'{ext_name} 已禁用'}
    if is_windows:
        dll_path = os.path.join(soft_paths['install_abspath_path'], 'ext', f'php_{ext_name}.dll')
        if os.path.exists(dll_path):
            try:
                DeleteFile(dll_path)
            except Exception:
                pass
        return {'success': True, 'msg': f'{ext_name} 已卸载'}
    pecl_path = os.path.join(soft_paths['install_abspath_path'], 'bin', 'pecl')
    if os.path.exists(pecl_path):
        try:
            result = subprocess.run(
                [pecl_path, 'uninstall', ext_name],
                capture_output=True, text=True, timeout=60,
                input='yes\n',
                env={**os.environ, 'PHP_PEAR_PHP_BIN': php_path}
            )
            if result.returncode == 0:
                return {'success': True, 'msg': f'{ext_name} 已卸载'}
            else:
                err_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                return {'success': False, 'msg': f'卸载失败: {err_msg[:200]}'}
        except Exception as e:
            return {'success': False, 'msg': f'卸载异常: {str(e)[:200]}'}
    return {'success': True, 'msg': f'{ext_name} 已禁用'}
