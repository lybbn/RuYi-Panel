#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-05-06
# +-------------------------------------------------------------------
# | EditDate: 2025-05-06
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# PHP web 类
# ------------------------------
import psutil,time,datetime
import re,os,subprocess
from utils.common import current_os,ReadFile,RunCommand,GetLogsPath,WriteFile,ast_convert,DeleteFile,GetInstallPath
from django.conf import settings
from apps.system.models import Sites
from utils.server.system import system
from utils.install.php import (
    get_php_path_info, get_php_fpm_port,
    Start_PHP, Stop_PHP, Restart_PHP, Reload_PHP, is_php_running,
    create_php_fpm_pool_conf, delete_php_fpm_pool_conf, get_php_fpm_pool_conf,
    get_php_fpm_pool_port, get_php_pool_port
)

class PhpClient:
    is_windows=True
    siteName = None
    sitePath = None

    confBasePath = None
    scriptsPath=None
    log_base_path = None
    project_config = None

    def __init__(self, *args, **kwargs):
        self.is_windows = True if current_os == 'windows' else False
        self.siteName = kwargs.get('siteName', '')
        self.sitePath = kwargs.get('sitePath', '').replace("\\","/")
        self.project_config = kwargs.get('cont', {})
        self.confBasePath = settings.RUYI_VHOST_PATH.replace("\\","/") +"/php_project/"+self.siteName
        self.scriptsPath = self.confBasePath + "/scripts"
        self.log_base_path = self.sitePath+"/logs"
        if not os.path.exists(self.confBasePath): os.makedirs(self.confBasePath, mode=0o755)
        if not os.path.exists(self.log_base_path): os.makedirs(self.log_base_path, mode=0o755)

    def get_conf_path(self):
        data = {
            "confBasePath":self.confBasePath,
            "scriptsPath":self.scriptsPath,
            'log_base_path':self.log_base_path,
            'log_command':self.log_base_path+'/command.log',
            'command_pid':self.confBasePath+f'/{self.siteName}.pid',
        }
        return data

    def create_site(self):
        try:
            cont = self.project_config
            if not os.path.exists(self.sitePath):
                try:
                    os.makedirs(self.sitePath)
                except Exception as e:
                    raise Exception(f'创建根目录失败：{e}')
            php_version = cont.get("php_version","")
            if not php_version:
                raise Exception("请选择PHP版本")
            port = cont.get("port","")
            if not port:
                raise Exception("请输入项目端口")
            self.create_site_config()
            allowport = cont.get("allowport",False)
            if allowport:
                system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':port,'handle':'accept'})
            isstart = self.start_site()
            if not isstart:
                raise Exception("启动失败")
            return True,"ok"
        except Exception as e:
            return False,e

    def is_project_running(self,is_simple=False):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return False
        try:
            return is_php_running(php_version,is_windows=self.is_windows)
        except:
            return False

    def start_site(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return False
        try:
            if is_php_running(php_version,is_windows=self.is_windows):
                return True
            num_workers = cont.get("num_workers",4)
            Start_PHP(version=php_version,is_windows=self.is_windows,num_workers=num_workers)
            time.sleep(1)
            return is_php_running(php_version,is_windows=self.is_windows)
        except:
            return False

    def stop_site(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return True
        try:
            delete_php_fpm_pool_conf(self.siteName, php_version, is_windows=self.is_windows)
            soft_paths = get_php_path_info(php_version)
            has_other_pool = False
            if self.is_windows:
                pool_conf_dir = os.path.join(soft_paths['install_abspath_path'], 'fpm-pool.d')
            else:
                pool_conf_dir = soft_paths['linux_abspath_fpm_conf_d_path']
            if os.path.exists(pool_conf_dir):
                pool_files = [f for f in os.listdir(pool_conf_dir) if f.endswith('.conf')]
                if pool_files:
                    has_other_pool = True
            if is_php_running(php_version, is_windows=self.is_windows):
                if has_other_pool:
                    Reload_PHP(version=php_version, is_windows=self.is_windows)
                else:
                    Stop_PHP(version=php_version, is_windows=self.is_windows)
            return True
        except:
            return True

    def restart_site(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return False
        try:
            Restart_PHP(version=php_version,is_windows=self.is_windows)
            return True
        except:
            return False

    def reload_site(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return False
        try:
            Reload_PHP(version=php_version,is_windows=self.is_windows)
            return True
        except:
            return False

    def edit_site(self,is_need_time=True):
        self.create_fpm_pool_conf()
        self.create_run_script()
        cont = self.project_config
        port = cont.get("port","")
        allowport = cont.get("allowport",False)
        if allowport:
            system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':port,'handle':'accept'})
        self.restart_site()
        return True

    def delete_site(self):
        site_ins = Sites.objects.filter(name=self.siteName,type=3).first()
        if not site_ins:return False,"未找到站点"
        self.stop_site()
        cont = ast_convert(site_ins.project_cfg)
        php_version = cont.get("php_version","")
        if php_version:
            delete_php_fpm_pool_conf(self.siteName, php_version, is_windows=self.is_windows)
            if not self.is_windows and is_php_running(php_version, is_windows=self.is_windows):
                Reload_PHP(version=php_version, is_windows=self.is_windows)
        system.ForceRemoveDir(self.confBasePath)
        site_ins.delete()
        return True,"ok"

    def get_project_pids(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return []
        soft_paths = get_php_path_info(php_version)
        pids = []
        if self.is_windows:
            php_cgi_name = 'php-cgi.exe'
            for proc in psutil.process_iter(['name','exe','pid']):
                try:
                    if proc.info['name'] == php_cgi_name:
                        if soft_paths['install_abspath_path'].lower() in (proc.info['exe'] or '').lower():
                            pids.append(proc.info['pid'])
                except:
                    pass
        else:
            fpm_path = soft_paths['linux_abspath_fpm_path']
            for proc in psutil.process_iter(['name','exe','pid','cmdline']):
                try:
                    cmdline = " ".join(proc.info.get('cmdline') or [])
                    if 'php-fpm' in (proc.info['name'] or '') and php_version in cmdline:
                        pids.append(proc.info['pid'])
                except:
                    pass
        return pids

    def get_loadstatus(self):
        data = {
            'cpu_p':"",
            'mem_p':"",
            'mem_used':"",
            'create_time':"",
            'cmdline':"",
            'threads':"",
            'pids':[],
            'fpid':"",
            'fpid_name':"",
            'user':""
        }
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return data
        pids = self.get_project_pids()
        if not pids:
            return data
        try:
            total_cpu = 0
            total_memory = 0
            total_system_memory = psutil.virtual_memory().total
            total_threads = 0
            main_pid = min(pids)
            main_process = psutil.Process(main_pid)
            create_time = main_process.create_time()
            cmdline = main_process.cmdline()
            user = main_process.username()
            for pid in pids:
                try:
                    p = psutil.Process(pid)
                    total_cpu += p.cpu_percent(interval=0.1)
                    total_memory += p.memory_info().rss
                    total_threads += p.num_threads()
                except:
                    continue
            memory_usage_percent = (total_memory / total_system_memory) * 100
            data['cpu_p'] = round(total_cpu, 2)
            data['mem_p'] = round(memory_usage_percent, 2)
            data['mem_used'] = f"{total_memory / 1024 / 1024:.2f} MB"
            data['threads'] = total_threads
            data['pids'] = pids
            data['create_time'] = datetime.datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
            data['cmdline'] = " ".join(cmdline)
            data['user'] = user
            parent = main_process.parent()
            data['fpid'] = main_process.ppid()
            data['fpid_name'] = parent.name() if parent else ""
        except:
            pass
        return data

    def create_site_config(self):
        self.create_fpm_pool_conf()
        self.create_run_script()
        self.create_nginx_proxy_conf()

    def create_fpm_pool_conf(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return
        pool_params = cont.get("pool_params",{})
        isok, result = create_php_fpm_pool_conf(
            site_name=self.siteName,
            site_path=self.sitePath,
            php_version=php_version,
            pool_params=pool_params if pool_params else None,
            is_windows=self.is_windows
        )
        if isok and isinstance(result, dict):
            cont['pool_port'] = result.get('pool_port','')
            cont['pool_name'] = result.get('pool_name','')
            cont['listen_addr'] = result.get('listen_addr','')

    def create_run_script(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return
        soft_paths = get_php_path_info(php_version)
        conf = self.get_conf_path()
        pool_port = cont.get("pool_port","") or get_php_pool_port(self.siteName, php_version) or soft_paths['fpm_port']
        if self.is_windows:
            php_cgi_path = soft_paths['windows_abspath_phpcgi_path']
            php_ini_path = soft_paths['windows_abspath_conf_path']
            num_workers = int(cont.get("num_workers",4))
            log_path = conf['log_command']
            pid_file = conf['command_pid']
            lines = ["@echo off","chcp 65001 > nul"]
            for i in range(num_workers):
                lines.append(f'start "" /b "{php_cgi_path}" -b 127.0.0.1:{pool_port} -c "{php_ini_path}" >> "{log_path}" 2>&1')
            lines.append(f'echo done >> "{log_path}"')
            content = "\n".join(lines)
        else:
            fpm_path = soft_paths['linux_abspath_fpm_path']
            fpm_conf = soft_paths['linux_abspath_fpm_conf_path']
            fpm_pid_file = os.path.join(soft_paths['install_abspath_path'], 'var', 'run', 'php-fpm.pid')
            log_path = conf['log_command']
            content = f"""#!/bin/bash
LANG=en_US.UTF-8
if ! pgrep -F "{fpm_pid_file}" > /dev/null 2>&1; then
    "{fpm_path}" --fpm-config "{fpm_conf}" --pid "{fpm_pid_file}"
    sleep 1
    if pgrep -F "{fpm_pid_file}" > /dev/null 2>&1; then
        echo "PHP-FPM started successfully" >> "{log_path}"
    else
        echo "ERROR: PHP-FPM failed to start" >> "{log_path}"
        exit 1
    fi
else
    echo "PHP-FPM is already running" >> "{log_path}"
fi
"""
        script_path = self.get_run_script_path()
        WriteFile(script_path,content)

    def create_nginx_proxy_conf(self):
        cont = self.project_config
        php_version = cont.get("php_version","")
        if not php_version:
            return
        soft_paths = get_php_path_info(php_version)
        pool_port = cont.get("pool_port","") or get_php_pool_port(self.siteName, php_version)
        if not pool_port:
            pool_port = soft_paths['fpm_port']
        listen_addr = cont.get("listen_addr","")
        if not listen_addr:
            if self.is_windows:
                listen_addr = f"127.0.0.1:{pool_port}"
            else:
                pool_name = cont.get("pool_name","") or self.siteName.replace('.', '_').replace('-', '_')
                socket_dir = os.path.join(soft_paths['install_abspath_path'], 'tmp')
                listen_addr = f"{socket_dir}/php-cgi-{pool_name}.sock"
        domains = cont.get("domains",[])
        if not domains:
            return
        from utils.ruyiclass.nginxClass import NginxClient
        domain_list = []
        for d in domains:
            if isinstance(d,str):
                domain_list.append({'domain':d,'port':80})
            elif isinstance(d,dict):
                domain_list.append(d)
        nginx_vhost_dir = os.path.join(settings.RUYI_VHOST_PATH.replace("\\","/"), 'nginx')
        if not os.path.exists(nginx_vhost_dir):
            os.makedirs(nginx_vhost_dir, mode=0o755)
        nginx_conf_path = os.path.join(nginx_vhost_dir, f"{self.siteName}.conf")
        nginx_client = NginxClient(siteName=self.siteName,sitePath=self.sitePath)
        nginx_client.create_php_proxy_conf(
            domains=domain_list,
            fpm_listen=listen_addr,
            conf_path=nginx_conf_path,
            is_windows=self.is_windows
        )

    def get_run_script_name(self):
        if self.is_windows:
            return f"{self.siteName}_cmd.bat"
        else:
            return f"{self.siteName}_cmd.sh"

    def get_run_script_path(self):
        return self.scriptsPath+"/"+self.get_run_script_name()

    def autoStart(self):
        cont = self.project_config
        autostart = cont.get("autostart",False)
        if autostart:
            return self.start_site()
        return True

    def get_composer_path(self):
        if self.is_windows:
            composer_path = os.path.join(GetInstallPath(), 'php', 'composer', 'composer.phar')
        else:
            composer_path = '/usr/local/bin/composer'
            if not os.path.exists(composer_path):
                composer_path = os.path.join(GetInstallPath(), 'php', 'composer', 'composer.phar')
        return composer_path

    def is_composer_installed(self):
        composer_path = self.get_composer_path()
        if os.path.exists(composer_path):
            return True
        try:
            result = subprocess.run(['composer', '--version'], capture_output=True, timeout=10)
            return result.returncode == 0
        except:
            return False

    def get_php_bin_path(self):
        cont = self.project_config
        php_version = cont.get("php_version", "")
        if not php_version:
            return ""
        soft_paths = get_php_path_info(php_version)
        if self.is_windows:
            return soft_paths['windows_abspath_php_path']
        else:
            return soft_paths['linux_abspath_php_path']

    def run_composer(self, command, packages=""):
        if not self.is_composer_installed():
            return False, "Composer 未安装"
        php_bin = self.get_php_bin_path()
        if not php_bin:
            return False, "未找到PHP可执行文件"
        composer_path = self.get_composer_path()
        if os.path.exists(composer_path) and composer_path.endswith('.phar'):
            cmd = f'"{php_bin}" "{composer_path}" {command}'
        else:
            cmd = f'composer {command}'
        if packages:
            cmd += f' {packages}'
        if not self.is_windows:
            cmd = f'export COMPOSER_HOME=/tmp/composer && cd "{self.sitePath}" && {cmd} --no-interaction 2>&1'
        else:
            cmd = f'cd /d "{self.sitePath}" && {cmd} --no-interaction 2>&1'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300, cwd=self.sitePath)
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return True, output
            else:
                return False, output
        except subprocess.TimeoutExpired:
            return False, "Composer 命令执行超时（超过300秒）"
        except Exception as e:
            return False, str(e)

    def install_composer(self):
        install_dir = os.path.join(GetInstallPath(), 'php', 'composer')
        if not os.path.exists(install_dir):
            os.makedirs(install_dir, mode=0o755)
        composer_phar = os.path.join(install_dir, 'composer.phar')
        if os.path.exists(composer_phar):
            return True, "Composer 已安装"
        try:
            from utils.security.files import download_url_file
            installer_url = "https://getcomposer.org/installer"
            installer_path = os.path.join(install_dir, "composer-setup.php")
            download_url_file(installer_url, installer_path)
            php_bin = self.get_php_bin_path()
            if not php_bin or not os.path.exists(php_bin):
                if os.path.exists(installer_path):
                    DeleteFile(installer_path)
                return False, "未找到PHP可执行文件，无法安装Composer"
            cmd = f'"{php_bin}" "{installer_path}" --install-dir="{install_dir}" --filename=composer.phar'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
            if os.path.exists(installer_path):
                DeleteFile(installer_path)
            if result.returncode == 0 and os.path.exists(composer_phar):
                return True, "Composer 安装成功"
            else:
                return False, f"Composer 安装失败：{result.stderr}"
        except Exception as e:
            return False, f"Composer 安装异常：{e}"
