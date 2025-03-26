#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-02-26
# +-------------------------------------------------------------------
# | EditDate: 2025-02-26
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Docker 应用广场类
# ------------------------------
import os,re
import json
import math
import shutil
import docker
import subprocess
import asyncio
from django.conf import settings
from utils.common import ReadFile,WriteFile,DeleteFile,GetTmpPath,RunCommand,GetDataPath,GetInstallPath,DeleteDir,current_os,ast_convert,is_service_running,check_is_port,GetBackupPath,GetRandomSet
import requests
import zipfile
import tarfile
from utils.server.system import system
from apps.sysbak.models import RuyiBackup
from utils.ruyiclass.dockerInclude.ry_dk_gpu import GPUMain
import logging
logger = logging.getLogger()

def calculate_total_pages(total_nums, limit):
    return math.ceil(int(total_nums) / int(limit))

class main:
    docker_url="unix:///var/run/docker.sock"
    tmppath = GetTmpPath()
    download_base_url = "http://download.lybbn.cn/ruyi" 
    apps_file = os.path.join(settings.BASE_DIR,"config", "dkapps.json")
    app_tags_file = os.path.join(settings.BASE_DIR,"config", "dkapptags.json")
    dk_app_base_path = GetDataPath().replace("\\", "/")+"/dkapps"
    templates_path = os.path.join(settings.BASE_DIR,"template","dkapps").replace("\\", "/")
    is_windows = True if current_os == "windows" else False
    compose_bin = "/usr/local/bin/docker-compose"
    
    def __init__(self):
        if not os.path.exists(self.dk_app_base_path): os.makedirs(self.dk_app_base_path)
        if self.is_windows:
            self.docker_url="npipe:////./pipe/dockerDesktopLinuxEngine"
            self.initEnv()
            self.compose_bin = "docker-compose"
        else:
            if not os.path.exists(self.compose_bin):self.compose_bin="/usr/bin/docker-compose"
        try:
            if not os.path.exists(self.apps_file) or not os.path.exists(self.app_tags_file):
                self.update_dk_apps_and_tags()
        except:
            pass
    
    def initEnv(self):
        """
        windows 端初始化环境变量
        """
        root_path = GetInstallPath()
        root_abspath_path = os.path.abspath(root_path)
        install_abspath_path = os.path.join(root_abspath_path,'docker')
        windows_docker_bin_path = os.path.join(install_abspath_path,'docker','resources','bin')
        if os.path.exists(windows_docker_bin_path):
            system.AddBinToPath(windows_docker_bin_path)
        
    def connect(self):
        try:
            # 尝试连接到 Docker 服务
            # if self.is_windows:
            #     return docker.from_env()
            # else:
            return docker.DockerClient(base_url=self.docker_url)
        except:
            return None
            
    def is_docker_running(self):
        if not self.is_windows:
            pid = '/var/run/docker.pid'
            if os.path.exists(pid):
                client = self.connect()
                if client:return True
                return False
            else:
                return False
        else:
            client = self.connect()
            if client:return True
            return False
        
    def check_docker_network_exists(self,network_name):
        """
        使用 docker network inspect 检查 Docker 网络中是否存在指定的网络名称。
        :param network_name: 要检查的网络名称（例如 "ruyi-network"）
        :return: 如果存在返回 True，否则返回 False
        """
        try:
            # 运行 docker network inspect 命令
            subprocess.run(
                ["docker", "network", "inspect", network_name],
                capture_output=True,
                text=True,
                check=True
            )
            # 如果命令成功，说明网络存在
            return True
        except subprocess.CalledProcessError:
            # 如果命令失败，说明网络不存在
            return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False
            
    def check_ruyi_network(self):
        """检查ruyi-network网络是否存在"""
        if not self.is_windows:
            stdout, stderr = RunCommand("docker network ls | grep ruyi-network")
            if stderr:
                if "Cannot connect to the Docker daemon" in stderr:
                    return False,"docker服务未运行，请先安装或启动"
            if not stdout:
                stdout, stderr = RunCommand("docker network create ruyi-network")
                if stderr and "setlocale: LC_ALL: cannot change locale (en_US.UTF-8)" not in stderr:
                    return False, f"创建ruyi-network网络失败： {stderr}"
        else:
            if not self.check_docker_network_exists("ruyi-network"):
                stdout, stderr = RunCommand("docker network create ruyi-network")
                if stderr and "setlocale: LC_ALL: cannot change locale (en_US.UTF-8)" not in stderr:
                    return False, f"创建ruyi-network网络失败： {stderr}"
        return True,"ok"

    def paginated_data(self,data=[],page=1,limit=10):
        total_nums = len(data)
        total_pages = calculate_total_pages(total_nums,limit)
        if page<1:page=1
        if page>total_pages:page=total_pages
        # 根据分页参数对结果进行切片
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        p_data = data[start_idx:end_idx]
        return p_data
        
    def get_apps_list(self):
        if not os.path.exists(self.apps_file):
            return []
        content = ReadFile(self.apps_file)
        if not content: 
            return []
        try:
            config_json = json.loads(content)
            return config_json
        except:
            return []
    
    def get_apptags_list(self):
        if not os.path.exists(self.app_tags_file):
            return []
        content = ReadFile(self.app_tags_file)
        if not content: 
            return []
        try:
            config_json = json.loads(content)
            return config_json
        except:
            return []
    
    def download_url_file(self,url,save_path,chunk_size=8192):
        """
        从指定的 URL 下载文件并保存到本地。

        :param url: 文件的下载链接
        :param save_path: 文件保存的本地路径
        :param chunk_size: 每次下载的数据块大小（默认 8KB）
        :return: 下载成功返回 True 和保存路径，失败返回 False 和错误信息
        """
        try:
            # 发起 HTTP GET 请求
            response = requests.get(url, stream=True)
            response.raise_for_status()  # 检查请求是否成功

            # 确保保存路径的目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 分块下载文件并写入本地
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    file.write(chunk)  # 写入文件

            return True, save_path

        except requests.exceptions.RequestException as e:
            # 捕获请求相关的异常
            return False, f"下载失败: {str(e)}"
        except Exception as e:
            # 捕获其他异常
            return False, f"发生错误: {str(e)}"

    def update_dk_apps_and_tags(self):
        """
        拉取最新广场应用和标签列表
        """
        base_url = f"{self.download_base_url}/install/common/updatejson"
        apps_url = f"{base_url}/dkapps.json"
        app_tags_url = f"{base_url}/dkapptags.json"
        
        bk_apps_file = self.tmppath+"/dkapps.json"
        bk_app_tags_file = self.tmppath+"/dkapptags.json"
        try:
            if os.path.exists(self.apps_file):shutil.copy(self.apps_file, bk_apps_file)
            if os.path.exists(self.app_tags_file):shutil.copy(self.app_tags_file, bk_app_tags_file)
            
            DeleteFile(self.apps_file,empty_tips=False)
            DeleteFile(self.app_tags_file,empty_tips=False)
            
            isok,msg = self.download_url_file(apps_url,self.apps_file)
            if not isok:
                return False,msg
            isok,msg = self.download_url_file(app_tags_url,self.app_tags_file)
            if not isok:
                return False,msg
            return True,"更新成功"
        except Exception as e:
            if os.path.exists(bk_apps_file):
                shutil.copy(bk_apps_file,self.apps_file)
            if os.path.exists(bk_app_tags_file):
                shutil.copy(bk_app_tags_file,self.app_tags_file)
            logger.error(f"更新容器广场列表错误：{e}")
            return False,e
        finally:
            DeleteFile(bk_apps_file,empty_tips=False)
            DeleteFile(bk_apps_file,empty_tips=False)
            
    def get_dkapp_path(self,cont={}):
        """
        获取app根目录
        @param cont appname: app所属名称 、name: app名称
        """
        appname = cont.get("appname","")
        name = cont.get("name","")
        return self.dk_app_base_path+"/"+appname+"/"+name

    def get_dkapp_install_logpath(self,cont={}):
        """
        获取app安装日志目录
        """
        app_path = self.get_dkapp_path(cont=cont)
        return app_path+"/dkapp_install.log"
    
    def __check_compose_config(self, filename):
        """验证配置文件"""
        o,e= RunCommand(f"{self.compose_bin} -f {filename} config")
        if e and "setlocale: LC_ALL: cannot change locale" not in e:
            return False, f"配置文件检测失败: {e}"
        return True,"ok"
    
    def __func_unzip(self,zip_filename,extract_path):
        """
        @name 解压
        @author lybbn<2024-03-07>
        @param zip_filename 压缩文件名（含路径）
        @param extract_path 需要解压的目标目录
        """
        try:
            if current_os == "windows":
                #解除占用
                from utils.server.windows import kill_cmd_if_working_dir
                kill_cmd_if_working_dir(extract_path)
            _, ext = os.path.splitext(zip_filename)
            if ext in ['.tar.gz','.tgz','.tar.bz2','.tbz']:
                with tarfile.open(zip_filename, 'r') as tar:
                    tar.extractall(extract_path)
            elif ext == '.zip':
                with zipfile.ZipFile(zip_filename, 'r') as zipf:
                    zipf.extractall(extract_path)
            else:
                return False,f"不支持的文件格式"
            return True,"ok"
        except Exception as e:
            return False,f"解压失败：{e}"
    
    def __download_compose(self,appname,dlfilename):
        """
        检查本地服务器同步compose
        @param cont appname: app所属名称 dlfilename: 下载路径及名称
        """
        all_apps = self.get_apps_list()
        if all_apps:
            compose_url = ""
            for a in all_apps:
                if appname == a["appname"]:
                    compose_url = a["downloadUrl"]
                    break
            if not compose_url:
                return False,f"无{appname}的配置信息"
            isok,msg = self.download_url_file(compose_url,dlfilename)
            if not isok:return False,f"无{appname}的配置信息下载失败"
            save_directory = os.path.dirname(dlfilename)
            isok2,msg2 = self.__func_unzip(dlfilename,save_directory)
            if not isok2:return False,msg2
            DeleteFile(dlfilename,empty_tips=False)
            return True,"ok"
        else:
            return False,"无apps配置文件"
    
    def set_dkapp_conf(self,cont={}):
        appname = cont.get("appname","")
        if appname in ["frpc","frps"]:
            return self.set_frp_conf(cont=cont)
        elif appname == "discuz":
            return self.set_discuz_conf(cont=cont)
        return True,"ok"

    def chmod_recursive(self,path, mode):
        """
        递归修改目录及其子目录和文件的权限
        :param path: 目标路径
        :param mode: 权限模式（如 0o766）
        """
        if not os.path.exists(path):
            return
        os.chmod(path, mode)
        for root, dirs, files in os.walk(path):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                os.chmod(dir_path, mode)
            for file_name in files:
                file_path = os.path.join(root, file_name)
                os.chmod(file_path, mode)

    def set_discuz_conf(self,cont={}):
        #官网Discuz! 最新下载地址 https://www.discuz.vip/download
        app_path = self.get_dkapp_path(cont=cont)
        app_data_path = f"{app_path}/data"
        app_data_temp_path = f"{app_path}/tmp"
        app_data_upload_path = f"{app_path}/tmp/upload"
        version = cont.get("version","")
        dlfilename = app_path+"discuz.zip"
        dl_url = "https://gitee.com/Discuz/DiscuzX/attach_files/2044572/download"
        if version in ["v3.5","latest"]:
            dl_url = "https://gitee.com/Discuz/DiscuzX/attach_files/2044572/download"
        isok,msg = self.download_url_file(dl_url,dlfilename)
        if not isok:return False,msg
        isok,msg = self.__func_unzip(dlfilename,app_data_temp_path)
        if not isok:return False,msg
        DeleteDir(app_data_path)
        shutil.copytree(app_data_upload_path, app_data_path)
        DeleteDir(app_data_temp_path)
        DeleteFile(dlfilename,empty_tips=False)
        self.chmod_recursive(app_data_path+'/install', 0o777)
        self.chmod_recursive(app_data_path+'/uc_server/install', 0o777)
        self.chmod_recursive(app_data_path+'/data', 0o777)
        self.chmod_recursive(app_data_path+'/config', 0o777)
        self.chmod_recursive(app_data_path+'/uc_client/data', 0o777)
        self.chmod_recursive(app_data_path+'/uc_server/data', 0o777)
        return True,"ok"

    def set_frp_conf(self,cont={}):
        appname = cont.get("appname","")
        app_path = self.get_dkapp_path(cont=cont)
        params = ast_convert(cont.get("params",{}))
        if appname == "frpc":
            frpc_conf_path = f"{app_path}/frpc.toml"
            frpc_conf_content = ReadFile(frpc_conf_path)
            if not frpc_conf_content:return False,"frpc配置文件不存在"
            frps_server_ip = params.get('frps_server_ip')
            frps_server_port = params.get('frps_server_port')
            frpc_web_port = params.get('frpc_web_port')
            frpc_username = params.get('frpc_username')
            frpc_password = params.get('frpc_password')
            frpc_auto_token = params.get('frpc_auto_token')
            if not all([frps_server_ip, frps_server_port, frpc_web_port, frpc_username, frpc_password, frpc_auto_token]):
                return False,"frpc配置参数不全"
            env_content = ReadFile(frpc_conf_path)
            frpc_conf_content = frpc_conf_content.replace("serverAddr = \"127.0.0.1\"", f'serverAddr = "{frps_server_ip}"')
            frpc_conf_content = frpc_conf_content.replace("serverPort = 7000", f"serverPort = {frps_server_port}")
            frpc_conf_content = frpc_conf_content.replace("webServer.port = 7500", f"webServer.port = {frpc_web_port}")
            frpc_conf_content = re.sub(r'webServer.user = "[^"]*"', f'webServer.user = "{frpc_username}"', frpc_conf_content)
            frpc_conf_content = re.sub(r'webServer.password = "[^"]*"', f'webServer.password = "{frpc_password}"', frpc_conf_content)
            frpc_conf_content = re.sub(r'auth.token = "[^"]*"', f'auth.token = "{frpc_auto_token}"', frpc_conf_content)
            WriteFile(frpc_conf_path, frpc_conf_content)
        else:
            frps_conf_path = f"{app_path}/frps.toml"
            frps_conf_content = ReadFile(frpc_conf_path)
            if not frps_conf_content:return False,"frps配置文件不存在"
            frps_server_port = params.get('frps_server_port')
            frps_web_port = params.get('frps_web_port')
            frps_http_port = params.get('frps_http_port')
            frps_https_port = params.get('frps_https_port')
            frps_username = params.get('frps_username')
            frps_password = params.get('frps_password')
            frps_auto_token = params.get('frps_auto_token')
            if not all([frps_server_port, frps_web_port, frps_http_port, frps_https_port, frps_username, frps_password, frps_auto_token]):
                return False,"frps配置参数不全"
            frps_conf_content = frps_conf_content.replace("bindPort = 7000", f"bindPort = {frps_server_port}")
            frps_conf_content = frps_conf_content.replace("webServer.port = 7500", f"webServer.port = {frps_web_port}")
            frps_conf_content = frps_conf_content.replace("vhostHTTPPort = 30800", f"vhostHTTPPort = {frps_http_port}")
            frps_conf_content = frps_conf_content.replace("vhostHTTPSPort = 30443", f"vhostHTTPSPort = {frps_https_port}")
            frps_conf_content = re.sub(r'webServer.user = "[^"]*"', f'webServer.user = "{frps_username}"', frps_conf_content)
            frps_conf_content = re.sub(r'webServer.password = "[^"]*"', f'webServer.password = "{frps_password}"', frps_conf_content)
            frps_conf_content = re.sub(r'auth.token = "[^"]*"', f'auth.token = "{frps_auto_token}"', frps_conf_content)
            WriteFile(frps_conf_path, frpc_conf_content)
        return True,"ok"

    def replace_in_file(self,file_path, old_str, new_str):
        """
        替换文件中的字符串
        :param file_path: 文件路径
        :param old_str: 需要替换的字符串
        :param new_str: 替换后的字符串
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # 替换字符串
            content = content.replace(old_str, new_str)
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
        except Exception as e:
            print(f"Error: {e}")

    def generate_compose_config(self,cont={}):
        """
        写项目compose配置
        """
        appname = cont.get("appname","")
        name = cont.get("name","")
        version = cont.get("version","")
        cpu = cont.get("cpu",0)
        mem = cont.get("mem",0)
        params = ast_convert(cont.get("params",{}))
        if not appname or not name or not params or not version:return False,"参数错误"
        app_path = self.get_dkapp_path(cont=cont)
        app_env_path = f"{app_path}/.env"
        app_compose_path = f"{app_path}/docker-compose.yml"
        
        #设置应用通用配置
        tp_compose_base_path = f"{self.templates_path}/{appname}"
        tp_env_path = f"{self.templates_path}/{appname}/.env"
        tp_compose_path = f"{self.templates_path}/{appname}/docker-compose.yml"
        if not os.path.exists(tp_compose_path):
            DeleteDir(tp_compose_base_path)
            isok,msg = self.__download_compose(appname,tp_compose_base_path+f".zip")
            if not isok:return False,msg
        
        if not os.path.exists(app_env_path):
            shutil.copytree(tp_compose_base_path, app_path, dirs_exist_ok=True)
        
        if not self.is_windows:
            RunCommand(f"sed -i 's/RUYI_DKAPP/{name}/g' {app_compose_path}")
        else:
            self.replace_in_file(app_compose_path, "RUYI_DKAPP", name)

        with open(app_env_path) as f:
            lines = f.readlines()
        
        s_dict = {}
        for line in lines:
            if "=" in line:
                tmp = line.split("=")
                s_dict[tmp[0]] = tmp[1]
        
        env_conf_dict= {}
        env_conf_content=""
        for pkey, pvalue in params.items():
            env_conf_dict[pkey.upper()] = pvalue
        
        env_conf_dict["VERSION"] = version
        env_conf_dict["APP_PATH"] = app_path
        env_conf_dict["CPU"] = cpu
        env_conf_dict["MEM"] = mem
        
        s_dict.update(env_conf_dict)
        
        for key, value in s_dict.items():
            env_conf_content += f"{key}={str(value).strip()}\n"
        
        WriteFile(app_env_path,env_conf_content)

        # 设置应用专属配置
        isok,msg = self.set_dkapp_conf(cont=cont)
        if not isok: return False,msg

        return True,"ok"
    
    def set_status(self,compose_conf_path,status):
        isok=False
        msg="类型错误"
        if status == "start":
            isok,msg = self.start_app(compose_conf_path)
        elif status == "remove":
            isok,msg = self.remove_app(compose_conf_path)
        elif status == "stop":
            isok,msg = self.stop_app(compose_conf_path)
        elif status == "restart":
            isok,msg = self.restart_app(compose_conf_path)
        elif status == "pause":
            isok,msg = self.pause_app(compose_conf_path)
        elif status == "unpause":
            isok,msg = self.unpause_app(compose_conf_path)
        elif status == "rebuild":
            isok,msg = self.rebuild_app(compose_conf_path)
        return isok,msg
    
    def up_app_remove_orphans(self,compose_conf_path):
        if not compose_conf_path:return False,"无配置文件"
        if not os.path.exists(compose_conf_path): return False,"应用配置文件不存在"
        isok2,msg2 = self.__check_compose_config(compose_conf_path)
        if not isok2:return False,msg2
        RunCommand(f"nohup {self.compose_bin} -f {compose_conf_path} up -d --remove-orphans")
        return True, "启动成功"
    
    def rebuild_app(self,compose_conf_path):
        self.stop_app(compose_conf_path)
        self.up_app_remove_orphans(compose_conf_path)
        return True, "重建成功"
    
    def start_app(self,compose_conf_path):
        if not compose_conf_path:return False,"无配置文件"
        if not os.path.exists(compose_conf_path): return False,"应用配置文件不存在"
        isok2,msg2 = self.__check_compose_config(compose_conf_path)
        if not isok2:return False,msg2
        stdout, stderr = RunCommand(f"nohup {self.compose_bin} -f {compose_conf_path} start")
        if stderr:
            if "create failed" in stderr:
                return False, f"启动失败: {stderr}"
            if "Started" in stderr:
                return True, "启动成功"
            if not "Running" in stderr:
                return False, f"启动失败: {stderr}"
        return True, "启动成功"
    
    def remove_app(self,compose_conf_path,force=True):
        self.stop_app(compose_conf_path)
        if not compose_conf_path:False,"无配置文件"
        if not os.path.exists(compose_conf_path):
            servername = os.path.basename(os.path.dirname(compose_conf_path))
            stdout, stderr = RunCommand("docker-compose ls --format json")
            compose_info = []
            try:
                compose_info = json.loads(stdout)
            except:
                pass
            is_has_app = False
            for i in compose_info:
                if i['Name'] == servername.lower():
                    is_has_app = True
                    sot,serr = RunCommand(f"docker-compose -p {servername} down --volumes --remove-orphans")
                    if serr:
                        return False,f"删除错误：{serr}"
                    return True,"删除成功"
            if not is_has_app:return True,"删除成功"
        isok2,msg2 = self.__check_compose_config(compose_conf_path)
        if not isok2:return False,msg2
        del_str = "down"
        if force:del_str="rm -f"
        o,e = RunCommand(f"{self.compose_bin} -f {compose_conf_path} {del_str}")
        if e:
            if "No stopped containers" in e:
                return True, "删除成功"
            elif "Removed" in e:return True,"删除成功"
            return False,f"删除失败:{e}"
        return True, "删除成功"
    
    def stop_app(self,compose_conf_path):
        if not compose_conf_path:return False,"无配置文件"
        if not os.path.exists(compose_conf_path): return False,"应用配置文件不存在"
        isok2,msg2 = self.__check_compose_config(compose_conf_path)
        if not isok2:return False,msg2
        o,e = RunCommand(f"{self.compose_bin} -f {compose_conf_path} stop")
        if e:
            if "Stopped" in e:return True,"停止成功"
            return False,f"停止失败:{e}"
        return True, "停止成功"
    
    def restart_app(self,compose_conf_path):
        if not compose_conf_path:return False,"无配置文件"
        if not os.path.exists(compose_conf_path): return False,"应用配置文件不存在"
        isok2,msg2 = self.__check_compose_config(compose_conf_path)
        if not isok2:return False,msg2
        o,e = RunCommand(f"{self.compose_bin} -f {compose_conf_path} restart")
        return True, "重启成功"
    
    def pause_app(self,compose_conf_path):
        if not compose_conf_path:return False,"无配置文件"
        if not os.path.exists(compose_conf_path): return False,"应用配置文件不存在"
        isok2,msg2 = self.__check_compose_config(compose_conf_path)
        if not isok2:return False,msg2
        o,e = RunCommand(f"{self.compose_bin} -f {compose_conf_path} pause")
        return True, "暂停成功"
    
    def unpause_app(self,compose_conf_path):
        if not compose_conf_path:return False,"无配置文件"
        if not os.path.exists(compose_conf_path): return False,"应用配置文件不存在"
        isok2,msg2 = self.__check_compose_config(compose_conf_path)
        if not isok2:return False,msg2
        o,e = RunCommand(f"{self.compose_bin} -f {compose_conf_path} unpause")
        return True, "恢复成功"
    
    def check_port(self,port):
        """
        检查port是否正确，以及是否有正在运行的被占用
        """
        port=int(port)
        if not check_is_port(port=port):return False,f"端口{port}需在1-65535"
        if is_service_running(port=port):return False,f"端口{port}被占用，请更换"
        return True,"ok"
    
    def get_app_json_detail(self,appid):
        apps_json = self.get_apps_list()
        detail = {}
        for a in apps_json:
            if appid == a["appid"]:
                detail = a
                break
        return detail

    def generate_app(self,cont={}):
        """
        开始生成app
        """
        isok,msg = self.check_ruyi_network()
        if not isok:return False,msg
        
        if not self.is_docker_running():return False,"docker服务未运行，请先安装或启动"
        
        install_log_file = self.get_dkapp_install_logpath(cont=cont)
        
        runcommand_str = "nohup"
        if self.is_windows:
            runcommand_str = "start /B cmd /c"
        
        #依赖服务和端口检查
        appid = cont.get("appid","")
        app_json_detail = self.get_app_json_detail(appid)
        formFields = app_json_detail.get('formFields',[])
        if not app_json_detail:return False,"应用广场无此应用"
        params = ast_convert(cont.get("params",{}))
        ports = []#对外放通的端口
        gpu = False
        for key, value in params.items():
            for a in formFields:
                if a["envkey"] == "gpu":
                    gpu = value
                if a["envkey"] == key and a["type"] == "selectapps" and a["required"]: #检查如果是依赖服务则检查是否选择
                    if not params[a["child"]['envkey']]:
                        return False,a['tips']
                if a["envkey"] == key and "outport" in a and a['outport']:#检查如果是对外端口则检查端口
                    isport,pmsg = self.check_port(value)
                    if not isport:return False,pmsg
                    ports.append(value)
        
        #GPU检查
        if not self.is_windows:
            if gpu and not GPUMain.is_installed_ctk():
                gpu_instance = GPUMain()
                issupport,gpu_env_install_cmd = gpu_instance.get_install_gpu_command(install_log_file)
                if not issupport:return False,"您开启了GPU选项，但系统不支持！！！"
                runcommand_str = f"{runcommand_str} {gpu_env_install_cmd};"
        
        #放通防火墙
        allowport = cont.get("allowport",False)
        if allowport:
            for p in ports:
                system.AddFirewallRule(param={'address':'all','protocol':'tcp','localport':p,'handle':'accept'})
        
        isok,msg = self.generate_compose_config(cont=cont)
        if not isok:return False,msg
        app_path = self.get_dkapp_path(cont=cont)
        compose_conf_path = f"{app_path}/docker-compose.yml"
        if not os.path.exists(compose_conf_path): return False,"应用配置文件不存在"
        isok2,msg2 = self.__check_compose_config(compose_conf_path)
        if not isok2:return False,msg2

        if not self.is_windows:
            runcommand_str = f"{runcommand_str} {self.compose_bin} -f {compose_conf_path} up -d >> {install_log_file} 2>&1 && echo 'ruyi_successful_flag' >> {install_log_file} || echo 'ruyi_failed_flag' >> {install_log_file}"
            runcommand_str = f"{runcommand_str} &"
        else:
            runcommand_str = f"{runcommand_str} {self.compose_bin} -f {compose_conf_path} up -d --timeout 600 >> {install_log_file} 2>&1 && echo 'ruyi_successful_flag' >> {install_log_file} || echo 'ruyi_failed_flag' >> {install_log_file}"

        subprocess.Popen(runcommand_str, shell=True)
        return True,"创建并启动中，初次使用应用镜像可能需等待几分钟..."

    async def get_ws_logs(self,cont):
        """
        获取项目日志
        """
        wsinstace = cont.get("_ws",None)
        try:
            app_path = cont.get("path",None)
            app_compose_path = f"{app_path}/docker-compose.yml"
            time = cont.get("time","1h")
            lines = cont.get("lines",200)
            follow = cont.get("follow",False)
            
            since = ""
            if not time == "all":
                since = f"--since={time}"
            
            # 构建命令参数
            cmd_params = []
            if time != "all":
                cmd_params.append(f"--since={time}")
            if lines != "all":
                cmd_params.append(f"--tail={lines}")
            if follow:
                cmd_params.append("-f")  
            
            cmd = f"{self.compose_bin} -f {app_compose_path} logs {' '.join(cmd_params)}"

            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,universal_newlines=True)
            
            # 异步读取输出
            async def stream_output():
                try:
                    while True:
                        output = await asyncio.get_event_loop().run_in_executor(
                            None, 
                            process.stdout.readline
                        )
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            await wsinstace.send_message(message=output.strip())
                except Exception as e:
                    await wsinstace.send_message(action='error', message=f"日志读取错误: {str(e)}")
                finally:
                    # 读取剩余错误输出
                    error_output = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        process.stderr.read
                    )
                    if error_output:
                        await wsinstace.send_message(action='error', message=error_output.strip())
                    else:
                        await wsinstace.send_message(action='success', message="日志获取完毕")

            # 启动输出流任务
            await stream_output()
        except Exception as e:
            if wsinstace:
                await wsinstace.send_message(action='error', message=f"日志服务错误: {str(e)}")

    def backup_app(self,cont={}):
        """
        备份应用
        """
        id = cont.get("id","")
        appname = cont.get("appname","")
        name = cont.get("name","")
        app_path = self.get_dkapp_path(cont=cont)
        file_name = f"dkapp_{name}_{GetRandomSet(5)}.zip"
        
        tmp_back_path =GetBackupPath().replace("/","\\") if self.is_windows else GetBackupPath()
        export_dir = os.path.join(tmp_back_path, "dkapps",name)
        dst_file_path = os.path.join(export_dir,file_name)
        
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        # 创建临时目录用于存放备份文件
        temp_dir = os.path.join(export_dir, 'temp_backup_%s'%GetRandomSet(10).lower())
        
        try:
            # 备份目录
            shutil.copytree(app_path, temp_dir)

            with zipfile.ZipFile(dst_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, rel_path)
            dst_file_size = os.path.getsize(dst_file_path)
            bk_ins = RuyiBackup.objects.create(type=4,name=file_name,filename=dst_file_path,size=dst_file_size,fid=id)
            return True,"ok",dst_file_path
        except Exception as e:
            DeleteFile(dst_file_path,empty_tips=False)
            return False,f"备份失败：{e}",dst_file_path
        finally:
            # 删除临时备份文件
            DeleteDir(temp_dir)
    
    def restore_app(self,cont={}):
        """
        从备份恢复应用
        """
        backup_file = cont.get("backup_file","")
        app_path = cont.get("app_path","")
        if not os.path.exists(backup_file):
            return False,"备份文件不存在"
        compose_conf_path = f"{app_path}/docker-compose.yml"
        self.stop_app(compose_conf_path)
        DeleteDir(app_path)
        self.__func_unzip(backup_file,app_path)
        self.start_app(compose_conf_path)
        return True,"恢复成功"
        