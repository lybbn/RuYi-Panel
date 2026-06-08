import hashlib
import hmac
import logging
import time
import datetime
import json
import requests
from .base import CdnProviderBase

logger = logging.getLogger(__name__)


class HuaweiCloudCdnProvider(CdnProviderBase):
    """华为云CDN缓存管理

    API文档: https://support.huaweicloud.com/api-cdn/cdn_02_0001.html
    认证方式: AK/SK HMAC-SHA256签名
    """

    provider_name = "huaweicloud"
    provider_display = "华为云CDN"

    supports_purge_url = True
    supports_purge_all = True        # 通过刷新域名根目录实现
    supports_purge_tag = False
    supports_preload = True
    supports_quota = True

    HOST = "cdn.myhuaweicloud.com"
    REGION = "cn-north-1"
    SERVICE = "cdn"

    def __init__(self, credentials, zone_id=None, domain_name=None):
        super().__init__(credentials)
        self.ak = credentials.get('AccessKey', '')
        self.sk = credentials.get('SecretKey', '')
        self.project_id = credentials.get('project_id', '')
        self.domain_name = domain_name
        self.timeout = 65

    def _sign(self, method, uri, query, headers, body=''):
        """华为云HWS签名"""
        t = datetime.datetime.utcnow()
        date = t.strftime('%Y%m%dT%H%M%SZ')

        # 构造小写key的headers映射，用于签名
        lower_headers = {k.lower(): v for k, v in headers.items()}

        # Step 1: 构造规范请求头
        signed_header_keys = sorted(['host', 'x-sdk-date', 'x-project-id'])
        signed_headers = ';'.join(signed_header_keys)
        canonical_headers = ''
        for k in signed_header_keys:
            canonical_headers += '{}:{}\n'.format(k, lower_headers.get(k, ''))

        # Step 2: 构造规范请求
        hashed_payload = hashlib.sha256(body.encode('utf-8')).hexdigest()
        canonical_request = '{}\n{}\n{}\n{}\n{}\n{}'.format(
            method, uri, query, canonical_headers, signed_headers, hashed_payload
        )

        # Step 3: 构造待签名字符串
        string_to_sign = 'SDK-HMAC-SHA256\n{}\n{}'.format(
            date, hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        )

        # Step 4: 计算签名
        signature = hmac.new(
            self.sk.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        authorization = 'SDK-HMAC-SHA256 Access={},SignedHeaders={},Signature={}'.format(
            self.ak, signed_headers, signature
        )
        return authorization, date

    def _request(self, method, uri, params=None, body=None):
        """发送华为云CDN API请求"""
        url = "https://{}{}".format(self.HOST, uri)
        # 构造查询字符串（签名用）
        query = ''
        if params:
            sorted_params = sorted(params.items())
            query = '&'.join('{}={}'.format(k, v) for k, v in sorted_params)

        body_str = json.dumps(body) if body else ''
        headers = {
            'host': self.HOST,
            'content-type': 'application/json',
            'x-project-id': self.project_id,
        }

        authorization, date = self._sign(method, uri, query, headers, body_str)
        headers['x-sdk-date'] = date
        headers['Authorization'] = authorization

        try:
            if method == 'GET':
                # GET请求：手动拼接URL保证签名与实际请求一致
                if query:
                    full_url = '{}?{}'.format(url, query)
                else:
                    full_url = url
                resp = requests.get(full_url, headers=headers, timeout=self.timeout)
            else:
                resp = requests.request(method, url, data=body_str, headers=headers, timeout=self.timeout)
            data = resp.json()
            # 华为云错误码在 code/message 或 error_code/error_msg
            if 'error_code' in data or ('code' in data and str(data.get('code', '')).startswith('CDN.')):
                error_msg = data.get('error_msg') or data.get('message') or 'Unknown error'
                return False, error_msg, data
            return True, 'success', data
        except requests.RequestException as e:
            return False, str(e), {}
        except Exception as e:
            return False, str(e), {}

    def purge_urls(self, urls):
        """按URL刷新缓存（CreateRefreshTasks - 旧版API）"""
        if not urls:
            return {"status": False, "msg": "URL列表不能为空"}
        success, msg, data = self._request('POST', '/v1.0/cdn/refreshtasks', body={
            'refreshTask': {
                'type': 'file',
                'urls': urls,
            },
        })
        if success:
            return {"status": True, "msg": "缓存刷新提交成功"}
        return {"status": False, "msg": "缓存刷新失败: {}".format(msg)}

    def purge_directory(self, directories):
        """按目录刷新缓存"""
        if not directories:
            return {"status": False, "msg": "目录列表不能为空"}
        success, msg, data = self._request('POST', '/v1.0/cdn/refreshtasks', body={
            'refreshTask': {
                'type': 'directory',
                'urls': directories,
            },
        })
        if success:
            return {"status": True, "msg": "目录刷新提交成功"}
        return {"status": False, "msg": "目录刷新失败: {}".format(msg)}

    def purge_all(self):
        """全量刷新：刷新域名根目录"""
        if not self.domain_name:
            return {"status": False, "msg": "需要指定域名才能全量刷新"}
        success, msg, data = self._request('POST', '/v1.0/cdn/refreshtasks', body={
            'refreshTask': {
                'type': 'directory',
                'urls': [
                    'https://{}/'.format(self.domain_name),
                    'http://{}/'.format(self.domain_name),
                ],
            },
        })
        if success:
            return {"status": True, "msg": "全量缓存刷新提交成功"}
        return {"status": False, "msg": "全量缓存刷新失败: {}".format(msg)}

    def preload_urls(self, urls):
        """预热URL（CreatePreheatingTasks - 旧版API）"""
        if not urls:
            return {"status": False, "msg": "预热URL列表不能为空"}
        success, msg, data = self._request('POST', '/v1.0/cdn/preheatingtasks', body={
            'preheatingTask': {
                'urls': urls,
            },
        })
        if success:
            return {"status": True, "msg": "缓存预热提交成功"}
        return {"status": False, "msg": "缓存预热失败: {}".format(msg)}

    def get_purge_quota(self):
        """查询刷新配额（ShowQuota）"""
        success, msg, data = self._request('GET', '/v1.0/cdn/quota')
        if success:
            quotas = data.get('quotas', {})
            return {
                "status": True,
                "msg": "success",
                "data": {
                    "url_quota": quotas.get('refresh_url_quota', ''),
                    "url_remain": quotas.get('refresh_url_remain', ''),
                    "dir_quota": quotas.get('refresh_dir_quota', ''),
                    "dir_remain": quotas.get('refresh_dir_remain', ''),
                    "preload_quota": quotas.get('preload_quota', ''),
                    "preload_remain": quotas.get('preload_remain', ''),
                }
            }
        return {"status": False, "msg": "查询配额失败: {}".format(msg)}

    def get_zone_info(self):
        """华为云CDN无Zone概念，返回域名配置概要"""
        if not self.domain_name:
            return {"status": False, "msg": "需要指定域名"}
        success, msg, data = self._request('GET', '/v1.0/cdn/domains', params={
            'domain_name': self.domain_name,
            'page_size': 1,
        })
        if success:
            domains = data.get('domains', [])
            if domains:
                d = domains[0]
                return {
                    "status": True,
                    "msg": "success",
                    "data": {
                        "zone_id": d.get('domain_name', ''),
                        "name": d.get('domain_name', ''),
                        "status": d.get('domain_status', ''),
                        "type": d.get('business_type', ''),
                        "plan": '',
                    }
                }
            return {"status": False, "msg": "域名未在CDN中找到"}
        return {"status": False, "msg": "获取域名信息失败: {}".format(msg)}
