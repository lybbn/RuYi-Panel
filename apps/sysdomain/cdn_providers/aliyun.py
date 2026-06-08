import base64
import hashlib
import hmac
import logging
import time
import uuid
import urllib.parse
import requests
from .base import CdnProviderBase

logger = logging.getLogger(__name__)


class AliyunCdnProvider(CdnProviderBase):
    """阿里云CDN缓存管理

    API文档: https://help.aliyun.com/document_detail/91157.html
    认证方式: AccessKey + HMAC-SHA1签名
    """

    provider_name = "aliyun"
    provider_display = "阿里云CDN"

    supports_purge_url = True
    supports_purge_all = True        # 通过目录刷新根路径实现
    supports_purge_tag = False       # 阿里云无Cache-Tag概念
    supports_preload = True
    supports_quota = True

    API_URL = "https://cdn.aliyuncs.com/"
    API_VERSION = "2018-05-10"
    SIGNATURE_METHOD = "HMAC-SHA1"
    SIGNATURE_VERSION = "1.0"
    FORMAT = "JSON"

    def __init__(self, credentials, zone_id=None, domain_name=None):
        super().__init__(credentials)
        self.access_key = credentials.get('AccessKey', '')
        self.secret_key = credentials.get('SecretKey', '')
        self.domain_name = domain_name
        self.timeout = 65

    def _percent_encode(self, s):
        """URL编码（阿里云规范）"""
        if isinstance(s, str):
            s = s.encode('utf-8')
        return urllib.parse.quote(s, safe='').replace('+', '%20').replace('*', '%2A').replace('%7E', '~')

    def _compute_signature(self, method, params):
        """计算HMAC-SHA1签名"""
        sorted_params = sorted(params.items())
        query_string = '&'.join(
            '{}={}'.format(self._percent_encode(k), self._percent_encode(v))
            for k, v in sorted_params
        )
        string_to_sign = '{}&%2F&{}'.format(method, self._percent_encode(query_string))
        key = (self.secret_key + '&').encode('utf-8')
        signature = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()
        return base64.b64encode(signature).decode('utf-8')

    def _request(self, api_action, extra_params=None):
        """发送阿里云API请求"""
        params = {
            'Format': self.FORMAT,
            'Version': self.API_VERSION,
            'AccessKeyId': self.access_key,
            'SignatureMethod': self.SIGNATURE_METHOD,
            'SignatureVersion': self.SIGNATURE_VERSION,
            'SignatureNonce': str(uuid.uuid4()),
            'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'Action': api_action,
        }
        if extra_params:
            params.update(extra_params)

        signature = self._compute_signature('GET', params)
        params['Signature'] = signature

        try:
            resp = requests.get(self.API_URL, params=params, timeout=self.timeout)
            data = resp.json()
            if 'Code' in data:
                return False, data.get('Message', 'Unknown error'), data
            return True, 'success', data
        except requests.RequestException as e:
            return False, str(e), {}
        except Exception as e:
            return False, str(e), {}

    def purge_urls(self, urls):
        """按URL刷新缓存（RefreshObjectCaches）
        urls: URL列表
        """
        if not urls:
            return {"status": False, "msg": "URL列表不能为空"}
        # 阿里云单次最多1000个URL，用换行分隔
        object_path = '\n'.join(urls)
        success, msg, data = self._request('RefreshObjectCaches', {
            'ObjectPath': object_path,
            'ObjectType': 'File',
        })
        if success:
            task_id = data.get('RefreshTaskId', '')
            return {"status": True, "msg": "缓存刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "缓存刷新失败: {}".format(msg)}

    def purge_directory(self, directories):
        """按目录刷新缓存
        directories: 目录路径列表
        """
        if not directories:
            return {"status": False, "msg": "目录列表不能为空"}
        object_path = '\n'.join(directories)
        success, msg, data = self._request('RefreshObjectCaches', {
            'ObjectPath': object_path,
            'ObjectType': 'Directory',
        })
        if success:
            task_id = data.get('RefreshTaskId', '')
            return {"status": True, "msg": "目录刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "目录刷新失败: {}".format(msg)}

    def purge_all(self):
        """全量刷新：通过目录刷新域名根路径，清空该域名下所有缓存"""
        if not self.domain_name:
            return {"status": False, "msg": "需要指定域名才能全量刷新"}
        # 同时刷新https和http的根路径
        directories = ['https://{}/'.format(self.domain_name), 'http://{}/'.format(self.domain_name)]
        object_path = '\n'.join(directories)
        success, msg, data = self._request('RefreshObjectCaches', {
            'ObjectPath': object_path,
            'ObjectType': 'Directory',
        })
        if success:
            task_id = data.get('RefreshTaskId', '')
            return {"status": True, "msg": "全量缓存刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "全量缓存刷新失败: {}".format(msg)}

    def preload_urls(self, urls):
        """预热URL（PushObjectCache）"""
        if not urls:
            return {"status": False, "msg": "预热URL列表不能为空"}
        object_path = '\n'.join(urls)
        success, msg, data = self._request('PushObjectCache', {
            'ObjectPath': object_path,
        })
        if success:
            task_id = data.get('PushTaskId', '')
            return {"status": True, "msg": "缓存预热提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "缓存预热失败: {}".format(msg)}

    def get_purge_quota(self):
        """查询刷新配额（DescribeRefreshQuota）"""
        success, msg, data = self._request('DescribeRefreshQuota')
        if success:
            return {
                "status": True,
                "msg": "success",
                "data": {
                    "url_quota": data.get('UrlQuota', ''),
                    "url_remain": data.get('UrlRemain', ''),
                    "dir_quota": data.get('DirQuota', ''),
                    "dir_remain": data.get('DirRemain', ''),
                    "preload_quota": data.get('PreloadQuota', ''),
                    "preload_remain": data.get('PreloadRemain', ''),
                }
            }
        return {"status": False, "msg": "查询配额失败: {}".format(msg)}

    def get_zone_info(self):
        """阿里云CDN无Zone概念，返回域名配置概要"""
        if not self.domain_name:
            return {"status": False, "msg": "需要指定域名"}
        success, msg, data = self._request('DescribeUserDomains', {
            'DomainName': self.domain_name,
        })
        if success:
            domains = data.get('Domains', {}).get('PageData', [])
            if domains:
                d = domains[0]
                return {
                    "status": True,
                    "msg": "success",
                    "data": {
                        "zone_id": d.get('DomainName', ''),
                        "name": d.get('DomainName', ''),
                        "status": d.get('DomainStatus', ''),
                        "type": d.get('CdnType', ''),
                        "plan": '',
                    }
                }
            return {"status": False, "msg": "域名未在CDN中找到"}
        return {"status": False, "msg": "获取域名信息失败: {}".format(msg)}
