#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-09-07
# +-------------------------------------------------------------------
# | EditDate: 2024-10-07
# +-------------------------------------------------------------------
# | Version: 1.1
# +-------------------------------------------------------------------

# ------------------------------
# nginx 类
# ------------------------------
import os,re,json
from django.conf import settings
from utils.common import ast_convert,current_os,DeleteFile,DeleteDir,GetLogsPath,check_is_domain,check_is_ipv4,check_is_port,ReadFile,WriteFile
from utils.install.nginx import get_nginx_path_info
from apps.system.models import SiteDomains,Sites
from utils.sslPem import getCertInfo
from datetime import datetime

class NginxClient:
    is_windows=True
    siteName = None
    sitePath = None
    logAccessPath = None
    logErrorPath = None
    confBasePath = None
    confPath = None
    softPathInfo = None
    stopPath = None#停止站点根目录
    antichainBasePath = None#防盗链配置目录
    ratelimitBasePath = None#流量限制配置目录
    ratelimitPath = None
    antichainPath = None
    proxyBasePath = None#反向代理配置目录
    proxyPath = None
    redirectBasePath = None#重定向配置目录
    redirectPath = None
    antichainStartKey = "RyAntiChain-Start"
    antichainEndKey = "RyAntiChain-End"
    replaceLine1Key = "#RUYIREPLACELINE1"
    replaceLine2Key = "#RUYIREPLACELINE2"
    
    def __init__(self, *args, **kwargs):
        self.is_windows = True if current_os == 'windows' else False
        self.confBasePath = settings.RUYI_VHOST_PATH.replace("\\", "/")+"/nginx"
        if not os.path.exists(self.confBasePath): os.makedirs(self.confBasePath)
        self.antichainBasePath = settings.RUYI_VHOST_PATH.replace("\\", "/")+"/antichain"
        if not os.path.exists(self.antichainBasePath): os.makedirs(self.antichainBasePath)
        self.siteName = kwargs.get('siteName', '')
        self.sitePath = kwargs.get('sitePath', '')
        log_base_path = GetLogsPath()
        self.logAccessPath = log_base_path + "/" + self.siteName +".log"
        self.logErrorPath = log_base_path + "/" + self.siteName +".error.log"
        self.confPath = self.confBasePath + "/" + self.siteName +".conf"
        self.proxyBasePath = self.confBasePath + "/proxy/" + self.siteName 
        if not os.path.exists(self.proxyBasePath): os.makedirs(self.proxyBasePath)
        self.proxyPath = settings.RUYI_VHOST_PATH.replace("\\", "/")+"/proxy"+ "/" + self.siteName +"_proxy.json"
        self.antichainPath = self.antichainBasePath + "/" + self.siteName +"_antichain.json"
        self.ratelimitBasePath = settings.RUYI_VHOST_PATH.replace("\\", "/") + "/ratelimit"
        if not os.path.exists(self.ratelimitBasePath): os.makedirs(self.ratelimitBasePath)
        self.ratelimitPath = self.ratelimitBasePath + "/" + self.siteName +"_ratelimit.json"
        self.redirectBasePath = self.confBasePath + "/redirect/" + self.siteName
        if not os.path.exists(self.redirectBasePath): os.makedirs(self.redirectBasePath)
        self.redirectPath = settings.RUYI_VHOST_PATH.replace("\\", "/")+"/redirect"+ "/" + self.siteName +"_redirect.json"
        self.sslBasePath = settings.RUYI_VHOST_PATH.replace("\\", "/")+"/ssl/" + self.siteName
        self.stopPath = os.path.join(settings.RUYI_TEMPLATE_BASE_PATH,"www","stop").replace("\\", "/")
        self.softPathInfo = get_nginx_path_info()
        self.check_default_config()
        
    def check_default_config(self):
        """
        @name 检测默认配置，没有的话自动生成
        @author lybbn<2024-09-07>
        """
        install_path = self.softPathInfo['install_path']
        nginx_html_path = install_path + "/html"
        conf_default = f"""server {{
    listen 80;
    server_name _;
    index index.html;
    root {nginx_html_path};
}}"""
        conf_default_path = self.confBasePath + "/ruyidefault.conf"
        if not os.path.exists(conf_default_path):WriteFile(conf_default_path,conf_default)
        return True
    
    def create_site(self,domainList = []):
        """
        创建站点
        """
        # 创建网站根目录
        if not os.path.exists(self.sitePath):
            try:
                os.makedirs(self.sitePath)
            except Exception as e:
                return False,'创建根目录失败：%s'%e
        
        self.create_default_file()
        self.create_conf(domainList=domainList)
        return True,"ok"
    
    def create_default_file(self):
        """
        生成网站默认文件
        """
        file_404_path = self.sitePath + '/404.html'
        file_index_path = self.sitePath + '/index.html'
        source_template_base_path = os.path.join(settings.RUYI_TEMPLATE_BASE_PATH,'html')
        WriteFile(file_404_path, ReadFile(os.path.join(source_template_base_path,'404.html')))
        WriteFile(file_index_path, ReadFile(os.path.join(source_template_base_path,'index.html')))
        return True
    
    def create_conf(self,domainList = []):
        conf_content = self.ry_get_conf(domainList = domainList)
        WriteFile(self.confPath,conf_content)
        return True
    
    def ry_get_conf(self,domainList = []):
        """
        @name 生成nginx server 配置文件
        @author lybbn<2024-09-07>
        @param domainList 域名端口列表[{'domain':xxx,'port':xxx}]
        """
        server_names = " ".join(d['domain'] for d in domainList)
        l_ports = list(set([d['port'] for d in domainList]))#相同端口去重
        listen_ports = "\n".join(f"    listen {d};" for d in l_ports)
        error_log_off = "off" if self.is_windows else "/dev/null"
        conf = f"""server 
{{
{listen_ports}
    server_name {server_names};
    root {self.sitePath};
    index index.html index.htm index.php default.php default.htm default.html; 
    access_log {self.logAccessPath};
    error_log {self.logErrorPath};
    
    {self.replaceLine2Key} 禁止删除本行，自动插入配置使用，否则会导致部分功能失效
    
    {self.replaceLine1Key} 禁止删除本行，自动插入配置使用，否则会导致部分功能失效
    
    #禁止访问 文件或目录
    location ~ ^/(\.htaccess|\.git|\.env|\.svn|\.project|LICENSE|README.md|readme.md) {{
        return 404;
    }}

    #申请SSL证书验证目录
    location ^~ /.well-known {{
        allow all; 
    }}
    
    #图片资源文件 缓存和日志策略 (需要时开启)
    #location ~ .*\\.(gif|jpg|jpeg|png|bmp|swf)$ {{
    #    expires      20d;
    #    error_log {error_log_off};
    #    access_log off;
    #}}
    
    #js css 资源文件 缓存和日志策略 (需要时开启)
    #location ~ .*\\.(js|css)?$ {{
    #    expires      6h;
    #    error_log {error_log_off};
    #    access_log off;
    #}}
    
}}"""
        return conf

    def add_domain_port(self,domain="",port=""):
        """
        @name 配置文件加入域名和端口
        @author lybbn<2024-09-07>
        """
        local_conf = ReadFile(self.confPath)
        if not local_conf: return False,"配置文件不存在"
        if domain:
            rep = r"server_name\s*(.*);"
            tmp = re.search(rep, local_conf).group()
            domains = tmp.replace(';', '').strip().split(' ')
            if domain not in domains:
                servername = tmp.replace(';', ' ' + domain + ';')
                local_conf = local_conf.replace(tmp, servername)
        if port:
            port = str(port)
            rep = r"listen\s+[\[\]\:]*([0-9]+).*;"
            tmp = re.findall(rep, local_conf)
            if port not in tmp:
                listen = re.search(rep, local_conf).group()
                local_conf = local_conf.replace(listen, listen + "\n\tlisten " + port + ';')
        
        WriteFile(self.confPath, local_conf)
        return True,"ok"
    
    def set_site_path(self,path=""):
        """
        @name 设置网站根目录
        @author lybbn<2024-09-07>
        """
        local_conf = ReadFile(self.confPath)
        if not local_conf: return False,"配置文件不存在"
        if path:
            new_config_content = re.sub(
                r'\s*root\s+[^\s;]+;',
                f'    root {path};',
                local_conf,
                count=1,  # 只替换第一个匹配
                flags=re.MULTILINE  # 使 ^ 匹配每一行的开头
            )
            WriteFile(self.confPath, new_config_content)
        return True,"ok"
    
    def get_conf_path(self):
        """
        取站点配置路径
        """
        return {
            "conf_path":self.confPath,
            "access_log_path":self.logAccessPath,
            "error_log_path":self.logErrorPath,
            "antichain_base_path":self.antichainBasePath,
            "antichain_path":self.antichainPath,
            "proxy_base_path":self.proxyBasePath,
            "proxy_path":self.proxyPath,
            "ratelimit_base_path":self.ratelimitBasePath,
            "ratelimit_path":self.ratelimitPath,
            "redirect_base_path":self.redirectBasePath,
            "redirect_path":self.redirectPath,
            "ssl_base_path":self.sslBasePath,
            "indexDocs":self.get_indexdoc()
        }
        
    def site_log_open(self,action="stop",type="access_log"):
        """
        站点日志开关
        """
        local_conf = ReadFile(self.confPath)
        log_off = "off" if self.is_windows else "/dev/null"
        if local_conf:
            if type == "access_log":
                log_path = self.logAccessPath
                type_log = "access_log"
                type_log_re = r'^\s*access_log\s+.*$'
            else:
                log_path = self.logErrorPath
                type_log = "error_log"
                type_log_re = r'^\s*error_log\s+.*$'
            if action == "stop":
                log_path = log_off
            elif action == "start":
                pass
            n_local_conf = re.sub(
                type_log_re,  # 匹配以 access_log\error_log 开头的行
                f'    {type_log} {log_path};',  # 替换成新的路径
                local_conf,
                count=1,  # 只替换第一个匹配
                flags=re.MULTILINE  # 使 ^ 匹配每一行的开头
            )
            WriteFile(self.confPath,n_local_conf)
            
        return True
    
    def delete_domain(self,id=None):
        """
        删除网站域名
        """
        sitedm_ins = SiteDomains.objects.filter(id=id).first()
        if not sitedm_ins:return False,"无此域名"
        port = sitedm_ins.port
        del_domain = sitedm_ins.name
        local_conf = ReadFile(self.confPath)
        if local_conf:
            # 域名删除
            rep = r"server_name\s+(.+);"
            tmp = re.search(rep, local_conf).group()
            nServerName = tmp.replace(' ' + del_domain + ';', ';')
            nServerName = nServerName.replace(' ' + del_domain + ' ', ' ')
            local_conf = local_conf.replace(tmp, nServerName)

            # 端口如果仅有一个，则删除，如果存在多个同端口，则不删除
            port_nums = SiteDomains.objects.filter(site_id = sitedm_ins.site_id,port=port).count()
            if port_nums <2:
                rep = r"listen.*[\s:]+(\d+).*;"
                tmp = re.findall(rep, local_conf)
                port = str(port)
                if port in tmp:
                    rep = r"\n*\s+listen.*[\s:]+" + port + r"\s*;"
                    local_conf = re.sub(rep, '', local_conf)
            # 保存配置
            WriteFile(self.confPath, local_conf)
        
        sitedm_ins.delete()
        return True,"ok"
    
    def delete_site(self,id=None):
        """
        删除网站
        id:站点id
        """
        site_ins = Sites.objects.filter(id=id).first()
        if not site_ins:return False,"未找到站点"
        w_path = site_ins.path
        #删除配置文件
        DeleteFile(self.confPath,empty_tips=False)
        
        # 删除日志
        DeleteFile(self.logAccessPath,empty_tips=False)
        DeleteFile(self.logErrorPath,empty_tips=False)
        
        #删除网站根目录
        DeleteDir(w_path)
        
        #删除防盗链
        DeleteFile(self.antichainPath,empty_tips=False)
        
        #删除流量限制
        DeleteFile(self.ratelimitPath,empty_tips=False)
        
        #删除重定向
        DeleteFile(self.redirectPath,empty_tips=False)
        DeleteDir(self.redirectBasePath)
        
        #删除反向代理
        DeleteFile(self.proxyPath,empty_tips=False)
        DeleteDir(self.proxyBasePath)
        
        #删除站点、域名列表
        SiteDomains.objects.filter(site_id=id).delete()
        site_ins.delete()

        return True,"ok"
    
    def get_indexdoc(self):
        """
        取默认文档
        """
        local_conf = ReadFile(self.confPath)
        if not local_conf:return ""
        rep = r"\s+index\s+(.+);"
        if re.search(rep, local_conf):
            tmp = re.search(rep, local_conf).groups()
            return tmp[0].replace(' ', ',')
        return ""
    
    def set_indexdoc(self,index=""):
        """
        设置默认文档 index = "index.html,index.php"
        """
        if not index:return False,"默认文档不能为空"
        local_conf = ReadFile(self.confPath)
        if not local_conf:return False,"配置文件不存在"
        index_s = index.replace(",", " ")
        rep = r"\s+index\s+.+;"
        local_conf = re.sub(rep, "\n\tindex " + index_s + ";", local_conf)
        WriteFile(self.confPath, local_conf)
        return True,"ok"
    
    def set_site_default(self,id=""):
        """
        @name 设置默认站点
        @author lybbn<2024-09-07>
        @param id 要设置默认站站点的id
        """
        site_ins = Sites.objects.filter(is_default=True).first()
        if not id == '0':# 为0时表示不设置默认站点（去除默认站点）
            site_ins2 = Sites.objects.filter(id=id).first()
            if not site_ins2:return False,"站点不存在"
            conf_path2 = self.confBasePath + "/" + site_ins2.name +".conf"
            local_conf2 = ReadFile(conf_path2)
            if not local_conf2: return False,"配置文件不存在"
        #存在默认站点则先去除默认
        site_name = "去除默认站点"
        if site_ins:
            if not id == '0':# 为0时表示不设置默认站点（去除默认站点）
                if site_ins2.id == site_ins.id:
                    return False,"此站点已是默认站点"
            conf_path = self.confBasePath + "/" + site_ins.name +".conf"
            local_conf = ReadFile(conf_path)
            if local_conf:
                listen_pattern = re.compile(r'(listen\s+\d+\s*)default_server\s*(;)')
                updated_content = listen_pattern.sub(r'\1\2', local_conf)
                WriteFile(conf_path,updated_content)
            site_ins.is_default = False
            site_ins.save()
            site_name = site_name + "=>"+ site_ins.name
        
        if not id == '0':# 为0时表示不设置默认站点（去除默认站点）
            pattern = re.compile(r'(listen\s+\d+\s*)')
            updated_content2 = pattern.sub(r'\1 default_server', local_conf2, 1)
            WriteFile(conf_path2, updated_content2)
            site_ins2.is_default = True
            site_ins2.save()
            site_name = site_ins2.name
        return True,site_name
    
    def get_antichain(self,id=""):
        """
        获取防盗链配置
        param: id 站点id
        """
        data = {}
        local_conf = ReadFile(self.confPath)
        if local_conf:
            data['status'] = False
            if local_conf.find(self.antichainStartKey) != -1:
                data['status'] = True
                rep = re.compile(fr'#{re.escape(self.antichainStartKey)}(.*?)#{re.escape(self.antichainEndKey)}', re.DOTALL)
                tmp = re.search(rep, local_conf).group()
                noReferer = tmp.find('none blocked') != -1
                data['noReferer'] = noReferer
                if noReferer:
                    req = r"valid_referers\s+none\s+blocked\s+(.+);\n"
                else:
                    req = r"valid_referers\s+(.+);\n"
                domian_list = re.search(req, tmp).group(1).strip().split()
                data['domains'] = ",".join(domian_list)
                data['exts'] = re.search(r"\(.+\)\$", tmp).group().replace('(', '').replace(')$', '').replace('|', ',')
                try:
                    data['returnCode'] = re.search(r'(return|rewrite)\s+.*(\d{3}|(/.+)\s+(break|last));',tmp).group(2).replace('break', '').strip()
                except:
                    data['returnCode'] = '404'
            else:#不存在则读取防盗链配置文件或默认配置
                antichain_conf = ReadFile(self.antichainPath)
                try:
                    data = json.loads(antichain_conf)
                except:
                    domain_list = list(set(SiteDomains.objects.filter(site_id = id).order_by("-id").values_list("name",flat=True)))
                    domains = ",".join(domain_list)
                    data = {
                        "exts": "js,css,png,jpg,jpeg,gif,ico,bmp,swf,eot,svg,ttf,woff,woff2",
                        "domains": domains,
                        "status": False,
                        "noReferer": True,
                        "returnCode": '404',
                    }
        return data
    
    def set_antichain(self,cont):
        """
        设置防盗链
        """
        log_off = "off" if self.is_windows else "/dev/null"
        exts = cont.get('exts','')#格式 ".jpg,.png"
        domains = cont.get('domains','')#格式 "ruyi.lybbn.cn,download.lybbn.cn"
        status = cont.get('status',False)
        noReferer = cont.get('noReferer',False)
        returnCode = cont.get('returnCode','404')
        returnRule = ""
        if returnCode in ['404', '403', '401', '301', '302', '201', '200']:
            returnRule = f'return {returnCode}'
        else:
            if not returnCode.startswith('/'):
                return False, "响应资源应为HTTP状态码或URI路径!"
            returnRule = f'rewrite /.* {returnCode} break'
        if len(exts) < 2: return False, 'URL后缀不能为空!'
        if len(domains) < 3: return False, '防盗链允许域名不能为空!'
        data = {
            "name": self.siteName,#标记属于哪个站点
            "exts": exts,
            "domains": domains,
            "status": status,
            "noReferer": noReferer,
            "returnCode": returnCode,
        }
        WriteFile(self.antichainPath,json.dumps(data))
        local_conf = ReadFile(self.confPath)
        if local_conf:
            if local_conf.find(self.antichainStartKey) != -1:
                rep = r"\s+valid_referers.+"
                local_conf = re.sub(rep, '', local_conf)#防止域名过多，先替换
                rep = re.compile(fr'\s+#{re.escape(self.antichainStartKey)}(\n|.){{1,600}}#{re.escape(self.antichainEndKey)}', re.DOTALL)
                local_conf = re.sub(rep, '\n', local_conf)#去除原来的防盗链配置
            if not status:
                WriteFile(self.confPath,local_conf)
            else:#开启防盗链
                referers = ("none blocked " if noReferer else "") + domains.replace(","," ")
                anti_conf = f"""#{self.antichainStartKey} 防盗链配置
    location ~ .*\.({exts.replace(",","|")})$ {{
        expires      30d;
        access_log {log_off};
        valid_referers {referers};
        if ($invalid_referer) {{
            {returnRule};
        }}
    }}
    #{self.antichainEndKey}
    {self.replaceLine1Key}"""
                local_conf = re.sub(fr'{self.replaceLine1Key}', anti_conf, local_conf)
                WriteFile(self.confPath,local_conf)
        return True,"ok"
    
    def set_site_ratelimit(self,cont):
        """
        设置站点流量限制
        """
        perserver = int(cont.get('perserver',0))#并发限制
        perip = int(cont.get('perip',0))#单ip限制
        rate = int(cont.get('rate',0))#流量限制
        status = cont.get('status',False)
        if perserver < 1 or perip < 1 or rate < 1:return False,"并发限制、单ip限制、流量限制 阀值要大于0"
        data = {
            "name": self.siteName,#标记属于哪个站点
            "perserver": perserver,
            "perip": perip,
            "rate": rate,
            "status": status,
            "plan":cont.get('plan',"custom")
        }
        WriteFile(self.ratelimitPath,json.dumps(data))
        perserver_str = f'limit_conn perserver {perserver};'
        perip_str = f'limit_conn perip {perip};'
        rate_str = f'limit_rate {rate}k;'
        nginx_conf_path = self.softPathInfo['abspath_conf_path']
        nginx_conf = ReadFile(nginx_conf_path)
        local_conf = ReadFile(self.confPath)
        if not nginx_conf or not local_conf:return False,"无法获取Nginx配置文件"
        if not status:#如果要关闭
            local_conf = re.sub(r"limit_conn\s+perserver\s+([0-9]+);.*\n", '', local_conf)
            local_conf = re.sub(r"limit_conn\s+perip\s+([0-9]+);.*\n", '', local_conf)
            local_conf = re.sub(r"limit_rate\s+([0-9]+)\w+;.*\n", '', local_conf)
        else:
            #nginx开启流量限制
            nginx_ratelimit_conf = f"""limit_conn_zone $binary_remote_addr zone=perip:10m;
    limit_conn_zone $server_name zone=perserver:10m;"""
            nginx_conf = re.sub(r"#ruyi_limit_conn_zone please do not delete", nginx_ratelimit_conf, nginx_conf)
            WriteFile(nginx_conf_path,nginx_conf)
            #当前站点开启流量限制
            if local_conf.find('limit_conn perserver') != -1 or local_conf.find('limit_conn perip') != -1:#如果之前已开启，则替换
                local_conf = re.sub(r"limit_conn\s+perserver\s+([0-9]+);", perserver_str, local_conf)
                local_conf = re.sub(r"limit_conn\s+perip\s+([0-9]+);", perip_str, local_conf)
                local_conf = re.sub(r"limit_rate\s+([0-9]+)\w+;", rate_str, local_conf)
            else:#如果没有则直接添加
                new_nginx_ratelimit_conf = f"""{perserver_str}
    {perip_str}
    {rate_str}
    {self.replaceLine1Key}"""
                local_conf = re.sub(fr'{self.replaceLine1Key}', new_nginx_ratelimit_conf, local_conf)
        WriteFile(self.confPath,local_conf)
        return True,"ok"
    
    def get_site_ratelimit(self):
        """
        获取站点流量限制
        """
        data = {}
        local_conf = ReadFile(self.confPath)
        if local_conf:
            data['status'] = False
            ratelimit_conf = ReadFile(self.ratelimitPath)
            try:
                data = json.loads(ratelimit_conf)
            except:
                data = {
                    "plan": "bbs",
                    "rate": 512,
                    "status": False,
                    "perserver": 300,
                    "perip": 25,
                }
            if local_conf.find('limit_conn perserver') != -1:
                data['status'] = True
                data['perserver'] = int(re.search(r"limit_conn\s+perserver\s+([0-9]+);", local_conf).group(1))
                data['perip'] = int(re.search(r"limit_conn\s+perip\s+([0-9]+);", local_conf).group(1))
                data['rate'] = int(re.search(r"limit_rate\s+([0-9]+)\w+;", local_conf).group(1))
                
        return data

    def set_site_redirect(self,cont):
        """
        设置站点重定向(新增、编辑、删除)
        """
        sitename = self.siteName
        redirectId = cont.get('redirectId',"")#重定向ID
        type = cont.get('type',"")#重定向类型 404、domain、path
        path = cont.get('path',"")
        domains = ast_convert(cont.get('domains',[]))
        redirectCode = cont.get('redirectCode',"301")
        redirectRoot = cont.get('redirectRoot',True)
        target = cont.get('target',"")
        keepUrlPath = cont.get('keepUrlPath',False)
        status = cont.get('status',False)
        operate = cont.get('operate',"add")#操作动作：add、edit、del
        if not redirectId or len(str(redirectId)) > 20:return False,"重定向ID错误，长度需1-20位"
        if type not in ["404","domain","path"]:return False,"重定向类型错误"
        if operate not in ["add","edit","del"]:return False,"操作动作错误"
        if redirectCode not in ['301','302']:return False,"重定向方式错误，需为：301、302"
        
        is_delete_mode = True if operate == "del" else False
        
        redirect_conf_name = self.redirectBasePath + "/" + redirectId + "_" + self.siteName + ".conf"
        
        redirect_rule = ""
        if type == "domain":
            path = ""
            if not target:return False, "目标URL地址不能为空"
            if not re.match(r"^http(s)?\:\/\/([a-zA-Z0-9][-a-zA-Z0-9]{0,100}\.)+([a-zA-Z0-9][a-zA-Z0-9]{0,100})+.?", target):return False, "目标URL地址格式错误"
            if not domains:return False,"请选择源域名"
            target_domain = re.search(r"https?://([\w\-\.]+)",target).group(1)
            for d in domains:
                if not re.match(r"^([a-zA-Z0-9][-a-zA-Z0-9]{0,100}\.)+([a-zA-Z0-9][a-zA-Z0-9]{0,100})+.?", d):return False, "源域名格式错误"
                if d == target_domain:
                    return False,f'源域名[{d}]与目标URL域名一致,请选择其他域名!!!'
        
            redirect_rule_arr = []
            for ds in domains:
                keepUrlPath_str = ""
                if keepUrlPath:
                    keepUrlPath_str = "$request_uri"
                redirect_rule_str = f"""
    if ($host ~ '^{ds}'){{
        return {redirectCode} {target}{keepUrlPath_str};
    }}
"""
                redirect_rule_arr.append(redirect_rule_str)
                
            redirect_rule = "\n".join(redirect_rule_arr)

        elif type == "path":
            if not path:return False,"重定向路径不能为空"
            if not path.startswith('/'):return False, "路径错误，格式如：/ruyi"
            if not target:return False, "目标URL地址不能为空"
            if not re.match(r"^http(s)?\:\/\/([a-zA-Z0-9][-a-zA-Z0-9]{0,100}\.)+([a-zA-Z0-9][a-zA-Z0-9]{0,100})+.?", target):return False, "目标URL地址格式错误"
            site_domian_list = list(set(SiteDomains.objects.filter(site__name = self.siteName).values_list("name",flat=True)))
            target_domain = re.search(r"https?://(.*)",target).group(1)
            for sl in site_domian_list:
                d_p = f"{sl}{path}"
                if target_domain == d_p:
                    return False,"目标URL地址和重定向路径一致会导致无限重定向,请更换路径！！！"
            redirectCode_str = "redirect"
            keepUrlPath_str = ""
            if redirectCode == "301":
                redirectCode_str = "permanent"
            if keepUrlPath:
                keepUrlPath_str = "$1"
            redirect_rule = f"rewrite ^{path}(.*)  {target}{keepUrlPath_str} {redirectCode_str};"
        else:#404(只有一个404重定向)
            domains = []
            path = ""
            tourlpath = ""
            if redirectRoot:
                path = "/"
                target = ""
                tourlpath = path
            else:
                if not target:return False, "目标URL地址不能为空"
                if not re.match(r"^http(s)?\:\/\/([a-zA-Z0-9][-a-zA-Z0-9]{0,100}\.)+([a-zA-Z0-9][a-zA-Z0-9]{0,100})+.?", target):return False, "目标URL地址格式错误"
                tourlpath = target
            redirect_rule =f"""
    error_page 404 = @pagenotfound;
    location @pagenotfound {{
        return {redirectCode} {tourlpath};
    }}
"""
            
        is_delete_nginx_include = False#是否删除nginx的include 重定向配置
        local_conf = ReadFile(self.confPath)
        if not local_conf:return False,"无法获取站点配置文件"
        redirect_c_file = self.redirectBasePath + "/*.conf"
        redirect_cont = ReadFile(self.redirectPath)
        if not redirect_cont:
            redirect_cont = []
        else:#存在原始配置
            redirect_cont = json.loads(redirect_cont)
            
        redirect_conf_content = f"""#RUYI-REDIRECT-START    
    {redirect_rule}
#RUYI-REDIRECT-END"""
        
        if operate == "del":#删除当前重定向条目
            redirect_cont = [obj for obj in redirect_cont if obj['redirectId'] != redirectId]
            if len(redirect_cont) == 0:
                is_delete_nginx_include = True
            DeleteFile(redirect_conf_name,empty_tips=False)
        
        elif operate == "add":
            if any(obj['redirectId'] == redirectId for obj in redirect_cont):
                return False,"重定向ID重复"
            canadd = True #主要针对404
            if type == "404":
                for rc in redirect_cont:
                    if rc['type'] == "404":
                        canadd = False
                        rc['status'] = status
                        rc['keepUrlPath'] = keepUrlPath
                        rc['path'] = path
                        rc['target'] = target
                        rc['redirectCode'] = redirectCode
                        rc['domains'] = domains
                        redirectId = rc['redirectId']
                        redirect_conf_name = self.redirectBasePath + "/" + redirectId + "_" + self.siteName + ".conf"
                        break
            if canadd:
                redirect_cont.append({
                    "sitename":sitename,
                    "redirectId":redirectId,
                    "type":type,
                    "keepUrlPath":keepUrlPath,
                    "path":path,
                    "target":target,
                    "redirectCode":redirectCode,
                    "domains":domains,
                    "status":status,
                })
                
        elif operate == "edit":
            for rc in redirect_cont:
                if rc['redirectId'] == redirectId:
                    if not type == rc['type']:
                        return False,"不能修改重定向类型"
                    rc['status'] = status
                    # rc['type'] = type
                    rc['keepUrlPath'] = keepUrlPath
                    rc['path'] = path
                    rc['target'] = target
                    rc['redirectCode'] = redirectCode
                    rc['domains'] = domains
                    break
        
        WriteFile(self.redirectPath,json.dumps(redirect_cont))
        
        if status:#开启时（或创建时）
            if not is_delete_nginx_include and not re.search(r"include.*\/nginx.*\/redirect\/.*\*.conf;",local_conf):
                #创建站点配置文件重定向配置引用
                addlinecontent = f"""    include {redirect_c_file};"""
                self.file_add_line(self.confPath,self.replaceLine1Key,addlinecontent)
            if not is_delete_nginx_include or not is_delete_mode:#写重定向规则文件
                WriteFile(redirect_conf_name,redirect_conf_content)
        else:#关闭
            DeleteFile(redirect_conf_name,empty_tips=False)
        
        if is_delete_nginx_include:
            local_conf = ReadFile(self.confPath)
            local_conf = re.sub(r"include.*\/nginx.*\/redirect\/.*\*.conf;\n?",'',local_conf)
            WriteFile(self.confPath, local_conf)
        
        return True,"ok"
    
    def set_site_proxy(self,cont):
        """
        设置站点反向代理(新增、编辑、删除)
        """
        sitename = self.siteName
        name = cont.get('name',"")
        proxyPath = cont.get('proxyPath',"")
        proxyPass = cont.get('proxyPass',"")
        subFilters = ast_convert(cont.get('subFilters',[]))
        proxyHost = cont.get('proxyHost',"")
        sniEnable = cont.get('sniEnable',False)
        cache = cont.get('cache',False)
        cacheTime = int(cont.get('cacheTime',1))
        cacheUnit = cont.get('cacheUnit','m')
        advanced = cont.get('advanced',False)
        status = cont.get('status',False)
        operate = cont.get('operate',"add")#操作动作：add、edit、del
        if len(name)<2 or len(name)>30:return False,"代理名称长度要大于2小于30"
        if not proxyPath:return False,"代理路径不能为空"
        if not proxyPass:return False,"转发到URL不能为空"
        if not proxyHost:return False,"发送域名不能为空"
        if not re.match(r'http(s)?\:\/\/([a-zA-Z0-9][-a-zA-Z0-9]{0,70}\.)+([a-zA-Z0-9][a-zA-Z0-9]{0,70})+.?',proxyPass):
            return False, f'域名格式错误:{proxyPass}'
        if re.search(r'[\=\?\[\]\)\(\&\*\^\$\%\#\@\!\~\`{\}\>\<\,\',\"]+', proxyPass):
            return False, "转发到URL有特殊符号"
        if cache and not cacheTime:
            return False, "缓存时间不能为空"
        
        subfilter_rule = ""
        
        if subFilters:
            for s in subFilters:
                if not s["key"]:
                    return False, '请输入原内容'
                elif s["key"] == s["value"]:
                    return False, '原内容与替换内容不能一致'
                subfilter_rule += f'\n\tsub_filter "{s['key']}" "{s['value']}";'
        else:
            subFilters = []
                
        if subfilter_rule:
            subfilter_rule = f"""
    proxy_set_header Accept-Encoding "";{subfilter_rule}
    sub_filter_once off;"""

        if operate not in ["add","edit","del"]:return False,"操作动作错误"
        
        is_delete_mode = True if operate == "del" else False
        
        proxy_conf_name = self.proxyBasePath + "/" + name + "_" + self.siteName + ".conf"
        
        is_delete_nginx_include = False#是否删除nginx的include 代理配置
        local_conf = ReadFile(self.confPath)
        if not local_conf:return False,"无法获取站点配置文件"
        proxy_c_file = self.proxyBasePath + "/*.conf"
        proxy_cont = ReadFile(self.proxyPath)
        if not proxy_cont:
            proxy_cont = []
        else:#存在原始配置
            proxy_cont = json.loads(proxy_cont)
            
        cache_content = f"""
    if ( $uri ~* "\.(gif|png|jpg|css|js|woff|woff2)$" )
    {{
        expires {cacheTime}{cacheUnit};
    }}
    proxy_ignore_headers Set-Cookie Cache-Control expires;
    proxy_cache cache_one;
    proxy_cache_key $host$uri$is_args$args;
    proxy_cache_valid 200 304 301 302 {cacheTime}{cacheUnit};
"""
        no_cache_content = f"""
    add_header Cache-Control no-cache;"""
            
        proxy_conf_content = f"""#RUYI-PROXY-START    
location ^~ {proxyPath} {{
    proxy_pass {proxyPass};
    proxy_set_header Host {proxyHost};
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    {"proxy_ssl_server_name on;\n" if sniEnable else ""}{subfilter_rule if subfilter_rule else ""}{cache_content if cache else no_cache_content}
}}
#RUYI-PROXY-END"""

        if operate == "del":#删除当前代理条目
            proxy_cont = [obj for obj in proxy_cont if obj['name'] != name]
            if len(proxy_cont) == 0:
                is_delete_nginx_include = True
            DeleteFile(proxy_conf_name,empty_tips=False)
        
        elif operate == "add":
            if any(obj['name'] == name for obj in proxy_cont):
                return False,"代理名称重复"
            proxy_cont.append({
                "sitename":sitename,
                "name":name,
                'proxyPath':proxyPath,
                'proxyPass':proxyPass,
                'cache':cache,
                'cacheTime':cacheTime,
                'cacheUnit':cacheUnit,
                'sniEnable':sniEnable,
                'status':status,
                'advanced':advanced,
                'subFilters':subFilters, 
                'proxyHost':proxyHost,
            })
                
        elif operate == "edit":
            for rc in proxy_cont:
                if rc['name'] == name:
                    rc['status'] = status
                    rc['proxyPath'] = proxyPath
                    rc['proxyPass'] = proxyPass
                    rc['cache'] = cache
                    rc['cacheTime'] = cacheTime
                    rc['cacheUnit'] = cacheUnit
                    rc['sniEnable'] = sniEnable
                    rc['status'] = status
                    rc['advanced'] = advanced
                    rc['subFilters'] = subFilters
                    rc['proxyHost'] = proxyHost
                    break
        
        WriteFile(self.proxyPath,json.dumps(proxy_cont))
        
        if status:#开启时（或创建时）
            if not is_delete_nginx_include and not re.search(r"include.*\/nginx.*\/proxy\/.*\*.conf;",local_conf):
                #创建站点配置文件代理配置引用
                addlinecontent = f"""    include {proxy_c_file};"""
                self.file_add_line(self.confPath,self.replaceLine2Key,addlinecontent)
            if not is_delete_nginx_include or not is_delete_mode:#写重定向规则文件
                WriteFile(proxy_conf_name,proxy_conf_content)
        else:#关闭
            DeleteFile(proxy_conf_name,empty_tips=False)
        
        if is_delete_nginx_include:
            local_conf = ReadFile(self.confPath)
            local_conf = re.sub(r"include.*\/nginx.*\/proxy\/.*\*.conf;\n?",'',local_conf)
            WriteFile(self.confPath, local_conf)
        
        return True,"ok"
    
    def get_site_cert(self,is_simple=False):
        """
        取站点SSL信息
        is_simple:key和cert内容返回为空（减少特殊场景下非必须情况）
        """
        data = {
            "enableHttps":False,
            "forceHttps":False,
            "key":"",
            "cert":"",
            "certinfo":{},
            "expire_days":0,#距离过期剩余天数,0表示过期
        }
        if os.path.exists(self.sslBasePath):
            cert_path = self.sslBasePath+"/certificate.pem"
            key_path = self.sslBasePath+"/privateKey.pem"
            data['key'] = ReadFile(key_path)
            data['cert'] = ReadFile(cert_path)
            if data['cert']:
                info_path = self.sslBasePath+"/info.json"
                if os.path.exists(info_path):
                    data['certinfo'] = json.loads(ReadFile(info_path))
                else:
                    data['certinfo'] = getCertInfo(mode="content",cert_content=ReadFile(cert_path,mode="rb"))
                expiry_date = datetime.strptime(data['certinfo']['not_valid_after'], "%Y-%m-%d %H:%M:%S")
                today_date = datetime.today()
                data['expire_days'] = (expiry_date - today_date).days
                if data['expire_days'] <0:data['expire_days']=0
                if is_simple:
                    data['key'] = "is_simple"
                    data['cert'] = "is_simple"
        
        local_conf = ReadFile(self.confPath)
        if local_conf:
            if local_conf.find('ssl_certificate') >= 0: data['enableHttps'] = True
            if local_conf.find('$server_port !~ 443') != -1: data['forceHttps'] = True
        return data
    
    def set_site_ssl_status(self,cont):
        """
        设置站点SSL状态启用/关闭
        """
        status = cont.get('status',False)
        local_conf = ReadFile(self.confPath)
        if status:
            if local_conf and local_conf.find('ssl_certificate') == -1:
                cert_path = self.sslBasePath+"/certificate.pem"
                key_path = self.sslBasePath+"/privateKey.pem"
                if not os.path.exists(cert_path) or not os.path.exists(key_path):
                    return False,"请先申请证书/或提供证书"
                sslcontent = f"""    #RUYI-SSL-START
    ssl_certificate    {cert_path};
    ssl_certificate_key    {key_path};
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:HIGH:!aNULL:!MD5:!RC4:!DHE;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    error_page 497  https://$host$request_uri; 
    #RUYI-SSL-END"""
                self.file_add_line(self.confPath,self.replaceLine2Key,sslcontent)
                local_conf = ReadFile(self.confPath)
                rep = r"listen\s+([0-9]+)\s*[default_server]*;"
                tmpg = re.findall(rep, local_conf)
                if '443' not in tmpg or local_conf.find('listen 443') < 0:
                    tmpg2 = re.search(rep, local_conf)
                    if tmpg2:
                        listen = tmpg2.group()
                        default_site = ''
                        if local_conf.find('default_server') != -1: default_site = ' default_server'
                        local_conf = local_conf.replace(listen, listen + "\n\t listen 443 ssl;" + default_site)
                WriteFile(self.confPath, local_conf)

        else:
            if local_conf:
                rep = r"#RUYI-SSL-START(.|\n)*?#RUYI-SSL-END"
                local_conf = re.sub(rep, "", local_conf);
                rep = r"\s+listen 443 ssl;"
                local_conf = re.sub(rep, "", local_conf)
                WriteFile(self.confPath, local_conf)
                
        return True,"ok"
        
    def set_site_ssl_forcehttps(self,cont):
        """
        设置站点SSL强制HTTPS跳转 启用/关闭
        """
        status = cont.get('status',False)
        local_conf = ReadFile(self.confPath)
        if status:
            #开启强制HTTPS
            if local_conf:
                cert_path = self.sslBasePath+"/certificate.pem"
                key_path = self.sslBasePath+"/privateKey.pem"
                if not os.path.exists(cert_path) or not os.path.exists(key_path):
                    return False,"请先申请证书/或提供证书"
                forceContent = f'''    #RUYI_FORCE_HTTPS_START
    if ($server_port !~ 443){{
        rewrite ^ https://$host$request_uri permanent;
    }}
    #RUYI_FORCE_HTTPS_END'''
                self.file_add_line(self.confPath,self.replaceLine1Key,forceContent)
        else:
            #关闭强制HTTPS
            if local_conf:
                rep = r"#RUYI_FORCE_HTTPS_START(.|\n)*?#RUYI_FORCE_HTTPS_END"
                new_conf = re.sub(rep,"", local_conf)
                WriteFile(self.confPath, new_conf)
        return True,"ok"
    
    def save_site_ssl_cert(self,cont):
        """
        保存证书
        """
        cert = cont.get('cert',"")
        key = cont.get('key',"")
        if not os.path.exists(self.sslBasePath): os.makedirs(self.sslBasePath)
        if (key.find('KEY') == -1): return False, '私钥格式错误'
        if (cert.find('CERTIFICATE') == -1): return False, '证书格式错误'
        certinfo = getCertInfo(cert_content=cert.encode('utf-8'),mode=None)
        if not certinfo:
            return False,"证书解析错误"
        WriteFile(self.sslBasePath + '/info.json',json.dumps(certinfo))
        cert_path = self.sslBasePath+"/certificate.pem"
        key_path = self.sslBasePath+"/privateKey.pem"
        WriteFile(cert_path,cert)
        WriteFile(key_path,key)
        return True,"ok"
    
    def start_site(self):
        """
        启动站点
        """
        local_conf = ReadFile(self.confPath)
        if local_conf:
            local_conf = local_conf.replace(self.stopPath, self.sitePath)
            local_conf = local_conf.replace("#include", "include")
            WriteFile(self.confPath, local_conf)
        return True
    
    def stop_site(self):
        """
        停止站点
        """
        local_conf = ReadFile(self.confPath)
        if local_conf:
            o_root_cfg = 'root ' + self.sitePath
            n_root_cfg = 'root ' + self.stopPath
            if local_conf.find(o_root_cfg) != -1:
                local_conf = local_conf.replace(o_root_cfg, n_root_cfg)
            else:
                local_conf = local_conf.replace(self.sitePath, self.stopPath)
            local_conf = local_conf.replace("include", "#include")
            WriteFile(self.confPath, local_conf)
        return True
    
    def file_add_line(self,filename, target_line_pattern, addline,mode='r'):
        """
        在指定文件 中 指定行下 添加内容
        """
        lines = []
        try:
            with open(filename, mode, encoding="utf-8", errors='ignore') as file:
                    lines = file.readlines()
            
        except:
            try:
                with open(filename, mode) as file:
                    lines = file.readlines()
            except:
                try:
                    with open(filename, mode, encoding="GBK", errors='ignore') as file:
                        lines = file.readlines()
                except:
                    pass
        
        if not lines:return False
        
        # 找到目标行
        target_index = None
        for i, line in enumerate(lines):
            # if target_line_pattern in line.strip():
            if re.search(target_line_pattern, line):
                target_index = i
                break
            
        if target_index is None:return False
        
        # 在目标行后添加内容
        if not addline.endswith("\n"):
            addline += "\n"
        lines.insert(target_index + 1, addline)
        
        # 写回文件
        with open(filename, 'w',encoding="utf-8") as file:
            file.writelines(lines)
        return True
        