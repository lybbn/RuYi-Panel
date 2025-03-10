#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-02-22
# +-------------------------------------------------------------------
# | EditDate: 2024-10-18
# +-------------------------------------------------------------------
# | Version: 1.2
# +-------------------------------------------------------------------


# ------------------------------
# acme v2 ssl 证书 客户端 Let’s Encrypt
# 官网：https://letsencrypt.org/
# 流程：注册账号-创建订单-域名验证-请求证书签发-下载证书-处理证书
# 选择ACME服务提供商： 首先需要选择一个支持ACME协议的证书颁发机构或ACME服务器，常见的ACME服务提供商包括Let's Encrypt、ZeroSSL等。
# 生成密钥对： 在使用ACME之前，需要生成公钥和私钥对。私钥用于签署证书签发请求，公钥用于验证证书签发响应。
# 注册账户： 通过与ACME服务器通信注册一个账户，通常需要提供联系信息等必要信息。
# 申请证书： 创建一个证书申请订单，包括要申请证书的域名等信息。
# 验证域名所有权： ACME服务器会要求验证证书申请中指定的域名的所有权。常见的验证方法包括HTTP验证、DNS验证等。
# 签发证书： 完成域名验证后，ACME服务器将签发证书并返回给你。
# 安装证书： 将获得的证书安装到您的服务器上，以确保网站可以使用新的SSL/TLS证书。
# 定期更新证书： 由于Let's Encrypt等证书颁发机构提供的证书有效期较短（通常为90天），因此需要定期更新证书以确保持续有效。
# ------------------------------

import re
import os
import time
import datetime
import json
import base64
import hashlib
import requests
import portalocker
import OpenSSL
import binascii
from utils.common import DeleteDir,GetLetsencryptPath,md5,WriteFile,GetLetsencryptLogPath,GetLetsencryptRootPath,ReadFile
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from utils.ruyiclass.webClass import WebClient
from apps.sysshop.models import RySoftShop
from apps.system.models import Sites

class letsencryptTool:
    _letsencrypt_directory = "https://acme-v02.api.letsencrypt.org/directory"
    _apis = {}
    _config = {}
    _config_file_path =  GetLetsencryptPath()
    _log_path = GetLetsencryptLogPath()
    _cert_save_path = GetLetsencryptRootPath()
    _user_agent = "ruyi"
    _ssl_verify = False
    _digest = "sha256"
    _alg = "RS256"
    _bits = 2048
    _kid = None
    _is_log = True #是否需要记录日志

    def __init__(self,is_log=True):
        self._is_log = is_log
        self._config = self.read_config_from_file()
        
    def utc_to_time(self,utcstr):
        utcstr = utcstr.split('.')[0]
        utc_date = datetime.datetime.strptime(utcstr, "%Y-%m-%dT%H:%M:%SZ")
        return int(time.mktime(utc_date.timetuple())) + (3600 * 8)# 北京时间
    
    def trans_cert_timeout_to_bj(self,utc_time):
        from zoneinfo import ZoneInfo
        utc_time = datetime.datetime.strptime(utc_time, '%Y%m%d%H%M%SZ')
        utc_dt = utc_time.replace(tzinfo=ZoneInfo("UTC"))
        beijing_dt = utc_dt.astimezone(ZoneInfo("Asia/Shanghai"))
        return beijing_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    def write_log(self,logstr,mode="ab+",is_error=False):
        """
        写日志
        """
        if not self._is_log:
            return
        with open(self._log_path, mode) as f:
            if isinstance(logstr, int):
                logstr = str(logstr)
            if is_error:
                logstr = "x" * 70 + "\n" + "错误：{}".format(logstr) + "\n"
                logstr += "x" * 70 + "\n"
            else:
                if logstr == "":
                    logstr +=""
                else:
                    logstr += "\n"
            f.write(logstr.encode('utf-8'))

    def get_apis(self):
        """
        取接口目录信息，并设置过期时间
        """
        if not self._apis:
            # 先从配置文件中获取
            if not 'apis' in self._config:
                self._config['apis'] = {}
            if 'expires' in self._config['apis'] and 'directory' in self._config['apis']:#过期则重新获取apis
                if time.time() < self._config['apis']['expires']:
                    self._apis = self._config['apis']['directory']
                    return self._apis
            # 通过网络获取
            res = requests.get(self._letsencrypt_directory)
            if not res.status_code in [200, 201]:
                result = res.json()
                if "type" in result:
                    if result['type'] == 'urn:acme:error:serverInternal':
                        raise Exception('目标证书服务器在维护或内部错误，具体可查看：https://letsencrypt.status.io')
                raise Exception(res.content)
            
            content = res.json()
            self._apis = {}
            self._apis['newAccount'] = content['newAccount']
            self._apis['newNonce'] = content['newNonce']
            self._apis['newOrder'] = content['newOrder']
            self._apis['revokeCert'] = content['revokeCert']
            self._apis['keyChange'] = content['keyChange']

            # 保存到配置文件
            self._config['apis'] = {}
            self._config['apis']['directory'] = self._apis
            self._config['apis']['expires'] = time.time() + (86400*2)  # 48小时后过期
            self.save_to_config_file()
        return self._apis
    
    def read_config_from_file(self):
        """
        读取配置文件
        """
        file_content = ReadFile(self._config_file_path)
        # with open(self._config_file_path, "r") as file:
        #     file_content = file.read()
        if not os.path.exists(self._config_file_path) or not file_content:
            self._config['account'] = {}
            self._config['apis'] = {}
            self._config['email'] = None
            self.save_to_config_file()
            self._apis = self.get_apis()
            return self._config
        self._config = json.loads(file_content)
        self._apis = self._config["apis"]['directory']
        self.save_to_config_file()
        return self._config
        
    def save_to_config_file(self):
        """
        保存到配置文件
        """
        if not os.path.exists(self._config_file_path):
            WriteFile(self._config_file_path,"")
        #WriteFile(self._config_file_path,json.dumps(self._config))
        with open(self._config_file_path, "w") as file:
            portalocker.lock(file, portalocker.LOCK_EX)
            file.write(json.dumps(self._config))
            portalocker.unlock(file)

    def _safe_base64(self,b):
        return base64.urlsafe_b64encode(b).decode('utf8').replace("=", "")
    
    def sign_data(self, data):
        """
        计算signature
        """
        da = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, self.get_account_key().encode())
        return OpenSSL.crypto.sign(da, data.encode("utf8"), self._digest)

    def get_newNonce(self,timeout = 40):
        """
        每次请求获取最新的Nonce值
        """
        try:
            headers = {"User-Agent": self._user_agent}
            response = requests.get(self._apis['newNonce'],timeout=timeout,headers=headers,verify=self._ssl_verify)
            return response.headers.get("Replay-Nonce",None)
        except:
            return None
    
    def create_account_key(self, key_type=OpenSSL.crypto.TYPE_RSA):
        key = OpenSSL.crypto.PKey()
        key.generate_key(key_type, self._bits)
        private_key = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
        return private_key
    
    def get_account_key(self):
        if not 'account' in self._config:
            self._config['account'] = {}
        if not 'key' in self._config['account']:
            self._config['account']['key'] = self.create_account_key()
            if type(self._config['account']['key']) == bytes:
                self._config['account']['key'] = self._config['account']['key'].decode()
            self.save_to_config_file()
        return self._config['account']['key']

    def get_jwk(self):
        private_key = serialization.load_pem_private_key(self.get_account_key().encode(),password=None,backend=default_backend())
        exponent = "{0:x}".format(private_key.public_key().public_numbers().e)
        exponent = "0{0}".format(exponent) if len(exponent) % 2 else exponent
        modulus = "{0:x}".format(private_key.public_key().public_numbers().n)
        jwk = {
            "kty": "RSA",
            "e": self._safe_base64(binascii.unhexlify(exponent)),
            "n": self._safe_base64(binascii.unhexlify(modulus)),
        }
        return jwk

    def do_requests(self,url,payload,timeout=40,contentType=""):
        """
        acme请求交互
        """
        if not contentType:
            contentType = "application/jose+json"
        headers =  {"User-Agent": self._user_agent,"Content-Type": contentType}
        payload64 = "" if not payload else self._safe_base64(json.dumps(payload).encode('utf8'))
        new_nonce = self.get_newNonce()
        if not new_nonce:
            new_nonce = self.get_newNonce()
            if not new_nonce:
                raise ValueError("获取nonce错误，请稍后再试")
        protected = {"url": url, "alg": self._alg, "nonce": new_nonce}
        protected.update({"jwk": self.get_jwk()} if self._config['account'].get('kid',None) is None else {"kid": self._config['account'].get('kid',None)})
        protected64 = self._safe_base64(json.dumps(protected).encode('utf8'))
        signature = self.sign_data(data="{0}.{1}".format(protected64, payload64))
        data = json.dumps({"protected": protected64, "payload": payload64, "signature": self._safe_base64(signature)})
        response = requests.post(url, data=data.encode("utf8"), timeout=timeout, headers=headers, verify=self._ssl_verify)
        return response
    
    def get_kid(self):
        """
        取ACME账号KID
        """
        if not 'account' in self._config:
            self._config['account'] = {}
        if not 'kid' in self._config['account']:
            self._config['account']['kid'] = self.register_account()
            self.save_to_config_file()
            time.sleep(1)
            self._config = self.read_config_from_file()
        return self._config['account']['kid']

    def register_account(self,param={}):
        """
        注册ACME账号
        """
        email = param.get("email","")
        if email:
            self._config['email'] = email
        if not 'email' in self._config or not self._config['email']:
            raise ValueError("没有可用ACME账号")
        payload = {
            "termsOfServiceAgreed": True,
            "contact": ["mailto:{0}".format(self._config['email'])],
        }
        res = self.do_requests(url=self._apis['newAccount'], payload=payload)
        if res.status_code not in [201, 200, 409]:
            raise Exception("注册ACME账号失败: {}".format(res.json()))
        kid = res.headers["Location"]#标识账户密钥（key）的唯一标识符，可以用来在后续的证书申请和管理过程中对账户进行身份验证和操作
        if not 'kid' in self._config['account'] or not self._config['account']['kid'] == kid:
            self._config['account']['kid'] = kid
        self.save_to_config_file()
        return kid
    
    def get_verifyType_name(self,strn):
        if strn == "file":
            return "http-01"
        elif strn == "dns":
            return "dns-01"
        elif strn == "tls":
            return "tls-alpn-01"
        return "http-01"
    
    def create_order(self,domain_list,verifyType="file",order_no=None,site_info={},is_renew=False):
        """
        创建订单
        verifyType:证书申请校验类型file、dns、tls
        domain_list:域名列表 ["xxx.xxx.com"]
        site_info:申请的站点信息
        is_renew:是否是续签
        """
        if not domain_list:
            raise Exception("请提供至少一个域名")
        payload = {"identifiers": [{"type": "dns", "value": domain} for domain in domain_list]}
        self.write_log("----- 正在请求证书服务商创建订单...")
        res = self.do_requests(self._apis['newOrder'], payload)
        if not res.status_code in [201,200]:
            if res.status_code == 429:
                raise Exception("创建订单错误：该域名请求次数过多，请更换域名或稍后再试")
            raise Exception('创建订单错误：%s' % res.reason)
        self.write_log("----- 订单创建成功！")
        resjson = res.json()
        # self.write_log("---订单返回内容：%s"%resjson)
        resjson['verifyType'] = verifyType
        resjson['domain_list'] = domain_list
        resjson['site_name'] = site_info['name']
        resjson['site_id'] = site_info['id']
        resjson['site_path'] = site_info['path']
        if not is_renew:
            resjson['deploy'] = False #是否已部署
            resjson['over'] = False #申请进度是否完成
        else:
            resjson['deploy'] = True
            resjson['over'] = True
        order_no = self.save_order(resjson,order_no,is_renew=is_renew)
        return order_no

    def save_order(self,orderinfo,order_no,is_renew=False):
        """
        保存订单
        """
        self.write_log("----- 正在保存订单...")
        if 'orders' not in self._config:
            self._config['orders'] = {}
        if not order_no:
            order_no = md5(json.dumps(orderinfo['identifiers']))
        if not is_renew:
            self._config['orders'].setdefault(order_no, {})
            self._config['orders'][order_no]['create_time'] = int(time.time())
            self._config['orders'][order_no]['renew_time'] = ""
            orderinfo['save_path'] = os.path.join(self._cert_save_path,orderinfo['site_name'],order_no)
            orderinfo['renew_status'] = ""
        else:
            orderinfo['renew_status'] = "pending"
            orderinfo['save_path'] = self._config['orders'][order_no]['save_path']
            orderinfo['certificate_url'] = self._config['orders'][order_no]['certificate_url']
        orderinfo['expires'] = self.utc_to_time(orderinfo['expires'])
        self._config['orders'][order_no] = orderinfo
        self.save_to_config_file()
        self.write_log("----- 订单已保存！")
        return order_no

    def get_authorization_info(self,order_no):
        """
        获取域名验证信息
        """
        if not order_no in self._config['orders']:
            raise Exception('该订单不存在')
        if 'auth_info_list' in self._config['orders'][order_no]:
            if time.time() < self._config['orders'][order_no]['auth_info_list'][0]['expires']:
                self.write_log("----- 检测验证文件未过期，使用已存在的验证文件！")
                return self._config['orders'][order_no]['auth_info_list']
        self.clear_verify_file(order_no=order_no)
        auth_info_list = []
        self.write_log("----- 正在设置验证文件...")
        for auth_url in self._config['orders'][order_no]['authorizations']:
            res = self.do_requests(auth_url, "")
            if res.status_code not in [200, 201]:
                raise Exception("获取授权失败: %s"%res.text())
            resjson = res.json()
            domain = resjson['identifier']['value']
            if 'status' in resjson:
                if resjson['status'] in ['invalid']:
                    raise Exception("该订单当前验证失败状态,请重新申请")
                if resjson['status'] == "valid":#跳过还在有效的域名
                    continue
            resjson['expires'] = self.utc_to_time(resjson['expires'])
            c_type = self.get_verifyType_name(self._config['orders'][order_no]['verifyType'])
            self.write_log(f"----- 验证类型：{c_type}")
            #challenge = [c for c in resjson['challenges'] if c['type'] == "http-01"][0] # dns-01、tls-alpn-01、http-01
            challenge = [c for c in resjson['challenges'] if c['type'] == c_type][0]
            token = challenge['token']
            challenge_url = challenge["url"]
            accountkey_json = json.dumps(self.get_jwk(), sort_keys=True, separators=(',', ':'))
            thumbprint = self._safe_base64(hashlib.sha256(accountkey_json.encode('utf8')).digest())
            keyauthorization = "{0}.{1}".format(token, thumbprint)
            #将校验文件放置在网站根目录下
            acme_dir = f'{self._config['orders'][order_no]['site_path']}/.well-known/acme-challenge'
            wellknown_path = os.path.join(acme_dir, token)
            WriteFile(wellknown_path,keyauthorization)
            self.write_log("----- 已设置验证文件！")
            auth_info_list.append({
                "keyauthorization":keyauthorization,
                "token":token,
                "challenge_url":challenge_url,
                "auth_url":auth_url,
                "domain":domain,
                "expires":resjson['expires'],
                "site_path":self._config['orders'][order_no]['site_path']
            })
        self._config['orders'][order_no]['auth_info_list'] = auth_info_list
        self.save_to_config_file()
        return auth_info_list
    
    def domain_validation(self,order_no):
        """
        域名验证
        """
        if not order_no in self._config['orders']:
            raise Exception('该订单不存在')
        for auth in self._config['orders'][order_no]['auth_info_list']:
            # 告知 ACME 服务器已准备好文件
            payload = {"keyAuthorization": "{0}".format(auth['keyauthorization'])}
            authorization_res = self.do_requests(auth['challenge_url'], payload)
            authorization_resjson = authorization_res.json()
            if authorization_resjson['status'] != "valid":
                is_retry_ok = False
                for i in range(5):
                    self.write_log(f"----- 第{i+1}次尝试查询验证结果...")
                    time.sleep(3)
                    authorization_res = self.do_requests(auth['challenge_url'], payload)
                    authorization_resjson = authorization_res.json()
                    if authorization_resjson['status'] != "valid":
                        self.write_log(f"----- 第{i+1}次查询验证失败 x")
                        continue
                    else:
                        self.write_log(f"----- 第{i+1}次查询验证成功！")
                        is_retry_ok = True
                        break
                if not is_retry_ok:
                    raise ValueError("验证【%s】失败，当前验证返回：%s"%(auth['challenge_url'],authorization_resjson))
            self.write_log(f"----- 验证【{auth['challenge_url']}】已通过")
        self.write_log("----- 验证域名成功！")
    
    def create_certificate_key(self,order_no):
        if 'private_key' in self._config['orders'][order_no]:
            return self._config['orders'][order_no]['private_key']
        key = OpenSSL.crypto.PKey()
        key.generate_key(OpenSSL.crypto.TYPE_RSA, self._bits)
        private_key = OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)
        if type(private_key) == bytes:
            private_key = private_key.decode()
        self._config['orders'][order_no]['private_key'] = private_key
        self.save_to_config_file()
        return private_key

    def get_certificate(self,order_no):
        """
        获取证书
        """
        if 'csr_pem' in self._config['orders'][order_no]:
            csr_pem  = self._config['orders']['csr_pem']
        else:
            domain_list = self._config['orders'][order_no]["domain_list"]
            domain_str = ",".join([f"DNS:{d}" for d in domain_list]).encode("utf8")
            csr = OpenSSL.crypto.X509Req()
            # 设置证书主题信息
            subject = csr.get_subject()
            subject.CN = domain_list[0]
            # 添加其他证书扩展（可选）
            csr_extensions = [
                OpenSSL.crypto.X509Extension(b"subjectAltName", False, domain_str)
            ]
            csr.add_extensions(csr_extensions)
            # 使用私钥签名证书
            private_key = OpenSSL.crypto.load_privatekey(
                OpenSSL.crypto.FILETYPE_PEM, self.create_certificate_key(order_no).encode()
            )
            csr.set_pubkey(private_key)
            csr.sign(private_key, self._digest)
            csr_pem = OpenSSL.crypto.dump_certificate_request(OpenSSL.crypto.FILETYPE_ASN1, csr)
        payload = {
            "csr": self._safe_base64(csr_pem)
        }
        order_url = self._config['orders'][order_no]["finalize"]
        response = self.do_requests(order_url, payload)
        if response.status_code not in [200, 201]:
            raise Exception("获取证书错误：%s"%response.json())
        response_json = response.json()
        self.write_log(f"----- 获取证书信息：{response_json}")
        certificate_url = response_json["certificate"]
        self._config['orders'][order_no]['certificate_url'] = certificate_url
        self.save_to_config_file()
        self.write_log("----- 获取证书成功！")
        return certificate_url
    
    def download_certificate(self,order_no):
        """
        下载证书
        """
        certificate_url = self._config['orders'][order_no].get('certificate_url',"")
        res = requests.get(certificate_url)
        if res.status_code not in [200, 201]:
            raise Exception("下载证书失败: {}".format(res.json()))
        certificate_content = res.content
        if type(certificate_content) == bytes:
            certificate_content = certificate_content.decode('utf-8')
        split_str = '-----END CERTIFICATE-----\n'
        data_list = certificate_content.split(split_str)
        cret_data = {"cert": data_list[0] + split_str, "root": split_str.join(data_list[1:])}
        try:
            x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cret_data["cert"])
            cert_timeout = x509.get_notAfter().decode('utf-8')
            cert_timeout = self.trans_cert_timeout_to_bj(cert_timeout)
            self.write_log(f"----- 获取证书过期时间：{cert_timeout}")
        except Exception as e:
            self.write_log(f"获取证书时间报错信息：{e}")
            cert_timeout = (datetime.datetime.today()+datetime.timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
            self.write_log(f"----- 证书过期时间：{cert_timeout}")
        if 'cert' in self._config['orders'][order_no]:
            del(self._config['orders'][order_no]['cert'])
        cret_data['cert_timeout'] = cert_timeout
        cret_data['private_key'] = self._config['orders'][order_no]['private_key']
        cret_data['domain_list'] = self._config['orders'][order_no]['domain_list']
        self._config['orders'][order_no]['cert_timeout'] = cert_timeout
        self.save_to_config_file()
        #保存证书
        path = self._config['orders'][order_no]['save_path']
        if not os.path.exists(path):
            os.makedirs(path)

        key_file = os.path.join(path,"private_key.pem") #证书私钥
        pem_file = os.path.join(path,"fullchain.pem")#包含证书链的PEM格式证书(nginx/apache)
        cert_file = os.path.join(path,"cert.csr")#域名证书
        root_cert_file = os.path.join(path,"root_cert.csr")#根证书
            
        WriteFile(key_file, cret_data['private_key'])
        WriteFile(pem_file, cret_data['cert'] + cret_data['root'])
        WriteFile(cert_file, cret_data['cert'])
        WriteFile(root_cert_file, cret_data['root'])
        self.write_log("----- 下载证书完成！")
        return cret_data
        
    def apply_certificate(self,domain_list=[],site_info={},verifyType="file",order_no=""):
        """
        证书申请
        domain_list:要申请的域名列表 ["xxx.xxx.com"]
        site_info:申请的站点信息
        order_no:指定订单号
        """
        try:
            self.write_log("", mode="wb+")
            self.write_log(f"开始申请域名证书：{domain_list}")
            # 步骤1: 创建订单
            self.write_log("【*】正在创建订单...")
            time.sleep(5)
            order_no = self.create_order(domain_list=domain_list,site_info=site_info,verifyType=verifyType,order_no=order_no)
            # 步骤2: 获取域名验证信息
            self.write_log("【*】正在验证域名...")
            time.sleep(5)
            self.get_authorization_info(order_no)
            # 步骤3: 完成域名验证
            self.domain_validation(order_no)
            # 步骤4: 获取证书
            self.write_log("【*】正在获取证书...")
            time.sleep(5)
            self.get_certificate(order_no)
            # 步骤5: 下载证书
            self.write_log("【*】正在下载证书...")
            time.sleep(5)
            self.download_certificate(order_no)
            self.write_log("【*】正在部署证书...")
            time.sleep(2)
            self.applied_callback(order_no=order_no,ok=True)
        except Exception as e:
            self.write_log(str(e),is_error=True)
            self.applied_callback(order_no=order_no,ok=False)
            
    def applied_callback(self,order_no="",ok=True):
        ssl_config = self.read_config_from_file()
        if ok:
            #保存证书到web
            save_path = ssl_config['orders'][order_no]['save_path']
            src_pem_file = os.path.join(save_path,"fullchain.pem")
            src_key_file = os.path.join(save_path,"private_key.pem")
            src_pem_content = ReadFile(src_pem_file)
            src_key_content = ReadFile(src_key_file)
            webServerIns = RySoftShop.objects.filter(type=3).first()
            webServer = ""
            if webServerIns is not None:
                webServer = webServerIns.name
            if not webServer:raise ValueError("无Web环境，请先安装")
            site_name = ssl_config['orders'][order_no]['site_name']
            site_path = ssl_config['orders'][order_no]['site_path']
            cont = {
                'cert':src_pem_content,
                'key':src_key_content
            }
            self.write_log("----- 开始部署...")
            isok,msg = WebClient.save_site_ssl_cert(webserver=webServer,siteName=site_name,sitePath=site_path,cont=cont)
            if not isok:
                self.write_log(f"----- 部署失败：{msg}")
                raise ValueError(msg)
            #仅保留一张站点证书
            ssl_config['orders'][order_no]['deploy'] = True
            ssl_config['orders'][order_no]['over'] = True
            site_id = ssl_config['orders'][order_no]['site_id']
            orders = ssl_config['orders']
            keys_to_delete = []
            for key,value in orders.items():
                if value['site_id'] == site_id and not order_no == key:
                    keys_to_delete.append(key)
            for key in keys_to_delete:
                del ssl_config['orders'][key]
            self._config = ssl_config
            self.save_to_config_file()
            WebClient.reload_service(webserver=webServer)
            self.write_log(f"----- 部署成功！")
        else:
            #失败删除订单
            if order_no:
                ssl_config['orders'][order_no]['deploy'] = False
                ssl_config['orders'][order_no]['over'] = False
                orders = ssl_config['orders']
                keys_to_delete = []
                for key,value in orders.items():
                    if order_no == key:
                        keys_to_delete.append(key)
                for key in keys_to_delete:
                    del ssl_config['orders'][key]
                self._config = ssl_config
                self.save_to_config_file()
            
    def renew_certificate(self,order_no=""):
        """
        续签申请
        order_no:指定订单号
        """
        is_force_https = False
        is_enable_https = True
        expire_days = 0
        webServer = "nginx"
        site_path = ""
        site_id = ""
        site_name = ""
        self.write_log("", mode="wb+")
        try:
            if not order_no:
                raise Exception("没有提供续签订单号，无法续签 x")
            if order_no not in self._config['orders']:
                raise Exception("指定订单号不存在，无法续签 x")
            order = self._config['orders'][order_no]
            site_path = order['site_path']
            site_id = order['site_id']
            site_name = order['site_name']
            self.write_log(f"检测【{site_name}】续签证书是否符合条件...")
            save_path = order['save_path']
            if not os.path.exists(site_path):
                sites_ins = Sites.objects.filter(id=site_id).first()
                if sites_ins and not sites_ins.path == site_path:
                    site_path = sites_ins.path
                    self._config['orders'][order_no]['site_path'] = site_path
                else:
                    raise Exception("续签订单中的网站不存在，无法续签 x")
            webServerIns = RySoftShop.objects.filter(type=3).first()
            if webServerIns is not None:
                webServer = webServerIns.name
            if not webServer:raise Exception("无Web环境，请先安装")
            ssl_info,null = WebClient.get_site_cert(webserver=webServer,siteName=site_name,sitePath=site_path,is_simple=True)
            is_force_https = ssl_info['forceHttps']
            is_enable_https = ssl_info['enableHttps']
            expire_days = ssl_info['expire_days']
            organization_name = ssl_info['certinfo'].get("organization_name","")
            if not is_enable_https:raise Exception(f"检测到【{site_name}】站点未开启HTTPS，跳过续签")
            if not organization_name == "Let's Encrypt":raise Exception(f"当前【{site_name}】站点证书类型为：{organization_name}，非Let's Encrypt，跳过续签")
            if is_force_https:
                self.write_log(f"检测到【{site_name}】站点开启了强制HTTPS，暂时关闭该功能")
                WebClient.set_site_ssl_forcehttps(webserver=webServer,siteName=site_name,sitePath=site_path,cont={'status':False})
                WebClient.reload_service(webserver=webServer)
            self.write_log(f"站点【{site_name}】开始续签证书")
            # 步骤1: 创建订单
            self.write_log("【*】正在创建订单...")
            time.sleep(5)
            site_info = {"id":site_id,"name":site_name,"path":site_path}
            self.create_order(domain_list=self._config['orders'][order_no]['domain_list'],site_info=site_info,verifyType=self._config['orders'][order_no]['verifyType'],order_no=order_no,is_renew=True)
            # 步骤1: 获取域名验证信息
            self.write_log("【*】正在验证域名...")
            time.sleep(5)
            self.get_authorization_info(order_no)
            # 步骤2: 完成域名验证
            self.domain_validation(order_no)
            # 步骤3: 获取证书
            self.write_log("【*】正在获取证书...")
            time.sleep(5)
            self.get_certificate(order_no)
            # 步骤4: 下载证书
            self.write_log("【*】正在下载证书...")
            time.sleep(5)
            self.download_certificate(order_no)
            self.save_to_config_file()
            self.write_log("【*】正在部署证书...")
            time.sleep(2)
            self.applied_callback(order_no=order_no,ok=True)
            self._config['orders'][order_no]['renew_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._config['orders'][order_no]['renew_status'] = "success"
            self.save_to_config_file()
        except Exception as e:
            self.write_log(str(e),is_error=True)
            #恢复
            if is_force_https:
                WebClient.set_site_ssl_forcehttps(webserver=webServer,siteName=site_name,sitePath=site_path,cont={'status':True})
                WebClient.reload_service(webserver=webServer)     
            
    def clear_verify_file(self,order_no=""):
        """
        清理验证文件
        order_no 清理的订单
        """
        if not order_no:
            return False
        if self._config['orders'][order_no]['verifyType'] not in ['file']:
            return False
        acme_path = f'{self._config['orders'][order_no]['site_path']}/.well-known/acme-challenge'
        acme_path = acme_path.replace("//",'/').replace("\\","/")
        if os.path.exists(acme_path):
            DeleteDir(acme_path)
            return True
        return False