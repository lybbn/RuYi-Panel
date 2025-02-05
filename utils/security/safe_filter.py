#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-02-03  
# +-------------------------------------------------------------------

# ------------------------------
# 字符安全过滤
# ------------------------------

import re
import urllib.parse

def filter_xss1(content):
    """
    @name xss过滤，只替换xss相关关键字符
    @author lybbn<2024-02-08>
    """
    dic_str = {
        '<':'＜',
        '>':'＞',
        '"':'＂',
        "'":'＇'
    }
    for i in dic_str.keys():
        content = content.replace(i,dic_str[i])
    return content

def filter_xss2(content):
    """
    @name xss过滤，替换script中的尖括号为html转义
    @author lybbn<2024-02-08>
    """
    return content.replace('<', '&lt;').replace('>', '&gt;')

def is_validate_db_passwd(passwd):
    """
    @name 是否有效数据库密码
    @author lybbn<2024-08-24>
    """
    if not passwd:
        return False,"密码不能为空"
    pattern = r"[\'\"`]|%27|%22|%60"
    encoded_password = urllib.parse.quote(passwd)
    match = re.search(pattern, encoded_password)
    if match:
        return False,"密码不能包含特殊字符"
    return True,"ok"