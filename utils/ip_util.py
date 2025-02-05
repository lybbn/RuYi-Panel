#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板 RUYI
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-07-03
# +-------------------------------------------------------------------

# ------------------------------
# IP 归属地
# ------------------------------

import os
import ipaddress
from qqwry import QQwry
from django.conf import settings
from utils.security.files import download_url_file

def is_valid_ipv4(ip):
    '''
    @name 是否有效的ipv4地址
    @author lybbn
    @date 2024-07-18
    @param ip地址
    @return True、False
    '''
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ipaddress.AddressValueError:
        return False

class IPQQwry:
    _instance = None
    _qqwry = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._qqwry = QQwry()
            QQWRY_FILE_PATH = os.path.join(settings.BASE_DIR,'qqwry.dat')
            if not os.path.exists(QQWRY_FILE_PATH):
                download_url_file("https://raw.gitmirror.com/adysec/IP_database/main/qqwry/qqwry.dat",save_path=QQWRY_FILE_PATH)
            cls._qqwry.load_file(QQWRY_FILE_PATH)
            cls._instance = super(IPQQwry, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @staticmethod
    def get_local_ips_area(ip_list):
        '''
        @name 本地离线获取ip地址归属地(第一次会触发下载离线库-文件太大20M左右)
        @author lybbn
        @date 2024-07-18
        @param ip_list 类型list ['x.x.x.x']
        @return list ['国家–省份–市')] 处理后 
        '''
        results = []
        try:
            for ip in ip_list:
                if is_valid_ipv4(ip):
                    result = IPQQwry._qqwry.lookup(ip)#('国家–省份–市', '移动')
                    results.append(result[0])
                else:
                    results.append("")
        except Exception as e:
            results = [""] * (len(ip_list) - len(results))
        return results


