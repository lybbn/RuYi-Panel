#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-08-10
# +-------------------------------------------------------------------
# | EditDate: 2024-08-10
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# web服务器方法
# ------------------------------
from utils.ruyiclass.nginxClass import NginxClient
from utils.ruyiclass.pythonClass import PythonClient
from utils.install.install_soft import Ry_Reload_Soft,Ry_Restart_Soft
from utils.common import current_os

class WebClient:
    is_windows =True if current_os == 'windows' else False
    
    @staticmethod
    def create_site(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            domainList = kwargs.get('domainList', [])
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).create_site(domainList=domainList)
            return isok,msg
        elif webserver == "python":
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont =  kwargs.get('cont', {})
            isok,msg = PythonClient(siteName=siteName,sitePath=sitePath,cont=cont).create_site()
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def autoStart(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'python':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont =  kwargs.get('cont', {})
            isok = PythonClient(siteName=siteName,sitePath=sitePath,cont=cont).autoStart()
            return isok
        return False,"无此类型webserver"
    
    @staticmethod
    def start_site(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            isok = NginxClient(siteName=siteName,sitePath=sitePath).start_site()
            return isok
        elif webserver == 'python':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont =  kwargs.get('cont', {})
            isok = PythonClient(siteName=siteName,sitePath=sitePath,cont=cont).start_site()
            return isok
        return False,"无此类型webserver"
    
    @staticmethod
    def stop_site(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            isok = NginxClient(siteName=siteName,sitePath=sitePath).stop_site()
            return isok,None
        elif webserver == 'python':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont =  kwargs.get('cont', {})
            isok = PythonClient(siteName=siteName,sitePath=sitePath,cont=cont).stop_site()
            return isok,None
        return False,"无此类型webserver"
    
    @staticmethod
    def del_site(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            id = kwargs.get('id', '')
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).delete_site(id=id)
            return isok,msg
        if webserver == 'python':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont =  kwargs.get('cont', {})
            isok,msg = PythonClient(siteName=siteName,sitePath=sitePath,cont=cont).delete_site()
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def del_site_domain(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            id = kwargs.get('id', '')
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).delete_domain(id=id)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def add_site_domain(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            domain = kwargs.get('domain', '')
            port = kwargs.get('port', '')
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).add_domain_port(domain=domain,port=port)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_path(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            path = kwargs.get('path', '')
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).set_site_path(path=path)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_indexdoc(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            index = kwargs.get('index', '')
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).set_indexdoc(index=index)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_default(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            id = kwargs.get('id', '')
            isok,msg = NginxClient().set_site_default(id=id)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def get_site_antichain(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            id = kwargs.get('id', '')
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            data = NginxClient(siteName=siteName,sitePath=sitePath).get_antichain(id=id)
            return True,data
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_antichain(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont = kwargs.get('cont', {})
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).set_antichain(cont=cont)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def get_site_ratelimit(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            data = NginxClient(siteName=siteName,sitePath=sitePath).get_site_ratelimit()
            return True,data
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_ratelimit(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont = kwargs.get('cont', {})
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).set_site_ratelimit(cont=cont)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_redirect(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont = kwargs.get('cont', {})
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).set_site_redirect(cont=cont)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_proxy(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont = kwargs.get('cont', {})
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).set_site_proxy(cont=cont)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def reload_service(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            Ry_Reload_Soft(name=webserver,is_windows=WebClient.is_windows)
            return True,"ok"
        return False,"无此类型webserver"
    
    @staticmethod
    def restart_service(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            Ry_Restart_Soft(name=webserver,is_windows=WebClient.is_windows)
            return True,"ok"
        return False,"无此类型webserver"
    
    @staticmethod
    def get_conf_path(*args, **kwargs):
        """
        取站点配置路径
        """
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            conf_path = NginxClient(siteName=siteName,sitePath=sitePath).get_conf_path()
            return conf_path,None
        return False,"无此类型webserver"
    
    @staticmethod
    def get_site_cert(*args, **kwargs):
        """
        取站点SSL信息
        """
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            is_simple = kwargs.get('is_simple', False)
            data = NginxClient(siteName=siteName,sitePath=sitePath).get_site_cert(is_simple=is_simple)
            return data,None
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_ssl_status(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont = kwargs.get('cont', {})
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).set_site_ssl_status(cont=cont)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def set_site_ssl_forcehttps(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont = kwargs.get('cont', {})
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).set_site_ssl_forcehttps(cont=cont)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def save_site_ssl_cert(*args, **kwargs):
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            cont = kwargs.get('cont', {})
            isok,msg = NginxClient(siteName=siteName,sitePath=sitePath).save_site_ssl_cert(cont=cont)
            return isok,msg
        return False,"无此类型webserver"
    
    @staticmethod
    def site_log_open(*args, **kwargs):
        """
        站点日志开关
        """
        webserver = kwargs.get('webserver', '')
        if webserver == 'nginx':
            siteName = kwargs.get('siteName', '')
            sitePath = kwargs.get('sitePath', '')
            action = kwargs.get('action', '')
            type = kwargs.get('type', '')
            isok = NginxClient(siteName=siteName,sitePath=sitePath).site_log_open(action=action,type=type)
            return isok,None
        return False,"无此类型webserver"