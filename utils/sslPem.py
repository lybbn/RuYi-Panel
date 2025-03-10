#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-09-05
# +-------------------------------------------------------------------
# | EditDate: 2024-09-05
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# SSL证书
# ------------------------------

from ipaddress import IPv4Address
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.x509 import OID_SUBJECT_ALTERNATIVE_NAME,KeyUsage,IPAddress,BasicConstraints,random_serial_number,NameOID, Name,NameAttribute, CertificateSigningRequestBuilder, CertificateBuilder,SubjectAlternativeName,DNSName,load_pem_x509_certificate
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption,pkcs12,Encoding,PrivateFormat,NoEncryption
import ipaddress
from django.conf import settings
from utils.common import WriteFile,ReadFile,get_online_public_ip
import socket
import datetime
from zoneinfo import ZoneInfo
import logging
logger = logging.getLogger()

# 生成私钥
def generatePrivatekey():
    """
    @author lybbn<2024-09-05>
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    return private_key

# 生成证书请求
def generateSubject(organization_name=u"如意面板",common_name=u"ruyi.lybbn.cn"):
    """
    @author lybbn<2024-09-05>
    """
    subject = Name([
        NameAttribute(NameOID.COUNTRY_NAME, u"CN"),
        NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"HENAN"),
        NameAttribute(NameOID.LOCALITY_NAME, u"ruyi"),
        NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
        NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    return subject

def load_pfx_file(pfx_path, password):
    """
    @author lybbn<2024-09-05>
    """
    pfx_data = ReadFile(pfx_path,mode="rb")
    if not pfx_data:return None,None
    private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(pfx_data, password.encode())
    return certificate, private_key

# 生成根证书私钥和证书
def create_root_certificate(password=None,days=365*10):
    """
    @author lybbn<2024-09-05>
    """
    # 生成根证书的私钥
    key = generatePrivatekey()
    # 生成根证书
    subject = issuer = generateSubject()
    cert = CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=days)
    ).add_extension(
        BasicConstraints(ca=True, path_length=None), critical=True,
    ).sign(key, hashes.SHA256())
    
    # cert = cert.public_bytes(
    #     encoding=serialization.Encoding.PEM
    # )
    
    # key = key.private_bytes(
    #     encoding=Encoding.PEM,
    #     format=PrivateFormat.TraditionalOpenSSL,
    #     encryption_algorithm=NoEncryption()
    # )
    
    if password:
        encryption_algorithm = BestAvailableEncryption(password.encode('utf-8'))
    else:
        encryption_algorithm = NoEncryption()

    # 将证书和私钥保存到 pfx 文件
    pfx_data = pkcs12.serialize_key_and_certificates(
        name=b'ruyi_root_cert',
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=encryption_algorithm
    )
    
    return pfx_data,key,cert

# 生成签署证书私钥和证书(pem格式)
def create_signed_certificate(root_cert=None, root_key=None, hosts=[],days=365*10):
    """
    @author lybbn<2024-09-05>
    """
    key = generatePrivatekey()
    common_name = str(hosts[0]) if hosts else "default"
    subject = Name([
        NameAttribute(NameOID.COUNTRY_NAME, u"CN"),
        NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"HENAN"),
        NameAttribute(NameOID.LOCALITY_NAME, u"ruyi"),
        NameAttribute(NameOID.ORGANIZATION_NAME, u"如意面板"),
        NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    san_entries = []
    for host in hosts:
        try:
            # 尝试将 host 解析为 IP 地址
            ip = ipaddress.ip_address(host)
            san_entries.append(IPAddress(ip))
        except:
            # 如果 host 不是有效的 IP 地址，则尝试将其作为 DNS 名称
            if not host.strip():
                continue
            san_entries.append(DNSName(host))
    cert = CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        root_cert.subject
    ).public_key(
        key.public_key()
    ).serial_number(
        random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=days)
    ).add_extension(
        KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=True,
            data_encipherment=False,
            key_agreement=False,
            encipher_only=False,
            decipher_only=False,
            key_cert_sign=True,
            crl_sign=False
        ), critical=True,
    ).add_extension(
        SubjectAlternativeName(san_entries),
        critical=False,
    ).sign(root_key, hashes.SHA256(),backend=default_backend())
    
    cert_pem = cert.public_bytes(Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm = NoEncryption()
    )

    return cert_pem, key_pem

def getDefaultRuyiSSLPem(mode="rb"):
    """
    @author lybbn<2024-09-05>
    """
    ruyi_root_password = ReadFile(settings.RUYI_ROOTPFX_PASSWORD_PATH_FILE)
    ruyi_root = ReadFile(settings.RUYI_ROOTPFX_PATH_FILE,mode=mode)
    private_key = ReadFile(settings.RUYI_PRIVATEKEY_PATH_FILE,mode=mode)
    certificate = ReadFile(settings.RUYI_CERTKEY_PATH_FILE,mode=mode)
    if ruyi_root_password and ruyi_root and private_key and certificate:
        return ruyi_root_password,ruyi_root,private_key,certificate
    return None,None,None,None

def forceCreateRuyiSSLPem():
    """
    强制生成默认如意面板SSL
    @author lybbn<2025-03-01>
    """
    hosts = []
    host = ReadFile(settings.RUYI_PUBLICIP_FILE)
    if not host:
        print("正在获取服务器公网IP地址...")
        logger.info("正在获取服务器公网IP地址...")
        host = get_online_public_ip()
        if host:
            print("获取服务器公网IP地址：%s"%host)
            logger.info("获取服务器公网IP地址：%s"%host)
            WriteFile(settings.RUYI_PUBLICIP_FILE,host)
        else:
            print("获取服务器公网IP失败!!!")
            logger.info("获取服务器公网IP失败!!!")
    hostname = socket.gethostname()
    ip_addresses = socket.gethostbyname_ex(hostname)[2]
    hosts = [ip for ip in ip_addresses if not ip.startswith("127.")]
    hosts.append('127.0.0.1')
    if host:
        hosts.insert(0, host)
    print("正在生成如意面板SSL证书信息...")
    logger.info("正在生成如意面板SSL证书信息...")
    ruyi_root_password,ruyi_root,private_key,certificate = generateRuyiSSLPem(hosts=hosts,force=True)
    if certificate:
        print("SSL证书信息生成成功")
        logger.info("SSL证书信息生成成功")
    else:
        print("SSL证书信息生成失败!!!")
        logger.info("SSL证书信息生成失败!!!")
    return True

def generateRuyiSSLPem(hosts=[],force=False):
    """
    @author lybbn<2024-09-05>
    """
    try:
        if not hosts:
            hostname = socket.gethostname()
            ip_addresses = socket.gethostbyname_ex(hostname)[2]
            hosts = [ip for ip in ip_addresses if not ip.startswith("127.")]
            hosts.append('127.0.0.1')
        if not force:
            ruyi_root_password,ruyi_root,private_key,certificate = getDefaultRuyiSSLPem()
            if ruyi_root_password and ruyi_root and private_key and certificate:
                return ruyi_root_password,ruyi_root,private_key,certificate
        ruyi_root_password = "ruyi.lybbn.cn"
        WriteFile(settings.RUYI_ROOTPFX_PASSWORD_PATH_FILE,ruyi_root_password)
        ruyi_root,root_key,root_cert = create_root_certificate(password=ruyi_root_password)
        WriteFile(settings.RUYI_ROOTPFX_PATH_FILE,ruyi_root,mode='wb')
        
        certificate, private_key = create_signed_certificate(root_cert=root_cert,root_key=root_key,hosts=hosts)
        WriteFile(settings.RUYI_PRIVATEKEY_PATH_FILE,private_key,mode='wb')
        WriteFile(settings.RUYI_CERTKEY_PATH_FILE,certificate,mode='wb')
        return ruyi_root_password,ruyi_root,private_key,certificate
    except Exception as e:
        print(f"生成面板证书SSL错误：{e}")
        return None,None,None,None

def extract_organization_name(subject):
    """
    @author lybbn<2024-09-05>
    """
    organization_name = None
    for attribute in subject:
        if attribute.oid == NameOID.ORGANIZATION_NAME:
            organization_name = attribute.value
            break
    return organization_name

def extract_common_name(subject):
    """
    @author lybbn<2024-09-05>
    """
    common_name = None
    for attribute in subject:
        if attribute.oid == NameOID.COMMON_NAME:
            common_name = attribute.value
            break
    return common_name

def trans_cert_timeout_to_bj(utc_time):
    beijing_time = utc_time.astimezone(ZoneInfo("Asia/Shanghai"))
    return beijing_time.strftime("%Y-%m-%d %H:%M:%S")

def getCertInfo(cert_path=settings.RUYI_CERTKEY_PATH_FILE,cert_content=None,mode="path"):
    """
    cert_content 证书内容字节类型（b）
    @author lybbn<2024-09-05>
    """
    if mode == "path":
        if not cert_path:cert_path = settings.RUYI_CERTKEY_PATH_FILE
        cert = ReadFile(cert_path,mode="rb")
    else:
        cert = cert_content
    if not cert:return None
    try:
        info = load_pem_x509_certificate(cert)
    except:
        return None
    organization_name = extract_organization_name(info.subject)
    if not organization_name:
        issuer = info.issuer
        for attribute in issuer:
            if attribute.oid._name == "organizationName":
                organization_name = attribute.value
                break
    not_valid_after = info.not_valid_after.strftime("%Y-%m-%d %H:%M:%S")
    if not organization_name.find("Let's Encrypt") == -1:#转为北京时间
        not_valid_after = trans_cert_timeout_to_bj(info.not_valid_after_utc)
    # 获取颁发给的域名列表 (Subject Alternative Name)
    san = None
    try:
        san = info.extensions.get_extension_for_oid(OID_SUBJECT_ALTERNATIVE_NAME)
        san_names = []
        for san_value in san.value:
            if isinstance(san_value.value, IPv4Address):
                san_names.append(str(san_value.value))  # 转换为字符串
            else:
                san_names.append(san_value.value)
    except:
        san_names = []
    data = {
        'serial_number':str(info.serial_number),
        'not_valid_after':not_valid_after,
        'organization_name':organization_name,
        'common_name':extract_common_name(info.subject),
        'san_names':san_names,
        'type':"自签证书" if organization_name == "如意面板" else "三方证书"
    }
    return data
    