import hashlib
import hmac
import json
import logging
import datetime
import requests
from .base import CdnProviderBase

logger = logging.getLogger(__name__)


class VolcengineCdnProvider(CdnProviderBase):
    """火山引擎CDN缓存管理

    API文档: https://www.volcengine.com/docs/6454/72690
    认证方式: HMAC-SHA256 V4签名
    """

    provider_name = "volcengine"
    provider_display = "火山引擎CDN"

    supports_purge_url = True
    supports_purge_all = True        # 通过刷新域名根目录实现
    supports_purge_tag = False
    supports_preload = True
    supports_quota = True

    HOST = "cdn.volcengineapi.com"
    SERVICE = "CDN"
    VERSION = "2021-03-01"
    REGION = "cn-north-1"

    def __init__(self, credentials, zone_id=None, domain_name=None):
        super().__init__(credentials)
        self.access_key = credentials.get('AccessKey', '')
        self.secret_key = credentials.get('SecretKey', '')
        self.domain_name = domain_name
        self.timeout = 65

    def _sign_request(self, action, body, query=None):
        """HMAC-SHA256 V4签名"""
        method = "POST"
        date = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        short_date = date[:8]
        content_type = "application/json"
        body_str = json.dumps(body) if isinstance(body, dict) else body
        body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()

        # 构造查询字符串
        query_params = {"Action": action, "Version": self.VERSION}
        if query:
            query_params.update(query)
        sorted_query = sorted(query_params.items())
        query_str = "&".join(["{}={}".format(k, v) for k, v in sorted_query])

        canonical_headers = "content-type:{}\nhost:{}\nx-content-sha256:{}\nx-date:{}\n".format(
            content_type, self.HOST, body_hash, date)
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = "{}\n/\n{}\n{}\n{}\n{}".format(
            method, query_str, canonical_headers, signed_headers, body_hash)
        credential_scope = "{}/{}/{}/request".format(short_date, self.REGION, self.SERVICE)
        string_to_sign = "HMAC-SHA256\n{}\n{}\n{}".format(
            date, credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest())

        def hmac_sha256(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = hmac_sha256(self.secret_key.encode("utf-8"), short_date)
        k_region = hmac_sha256(k_date, self.REGION)
        k_service = hmac_sha256(k_region, self.SERVICE)
        k_signing = hmac_sha256(k_service, "request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = "HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}".format(
            self.access_key, credential_scope, signed_headers, signature)
        headers = {
            "Authorization": authorization,
            "Content-Type": content_type,
            "Host": self.HOST,
            "X-Content-Sha256": body_hash,
            "X-Date": date,
        }
        url = "https://{}/?{}".format(self.HOST, query_str)
        return url, headers, body_str

    def _request(self, action, body=None, query=None):
        """发送火山引擎CDN API请求"""
        if body is None:
            body = {}
        url, headers, body_str = self._sign_request(action, body, query)
        try:
            resp = requests.post(url, headers=headers, data=body_str, timeout=self.timeout)
            data = resp.json()
            if 'Error' in data:
                error = data['Error']
                return False, error.get('Message', 'Unknown error'), data
            if 'ResponseMetadata' in data and 'Error' in data.get('ResponseMetadata', {}):
                error = data['ResponseMetadata']['Error']
                return False, error.get('Message', 'Unknown error'), data
            result = data.get('Result', data)
            return True, 'success', result
        except requests.RequestException as e:
            return False, str(e), {}
        except Exception as e:
            return False, str(e), {}

    def purge_urls(self, urls):
        """按URL刷新缓存（SubmitRefreshTask）"""
        if not urls:
            return {"status": False, "msg": "URL列表不能为空"}
        success, msg, data = self._request('SubmitRefreshTask', {
            'Type': 'file',
            'Urls': '\n'.join(urls),
        })
        if success:
            task_id = data.get('TaskId', '')
            return {"status": True, "msg": "缓存刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "缓存刷新失败: {}".format(msg)}

    def purge_directory(self, directories):
        """按目录刷新缓存"""
        if not directories:
            return {"status": False, "msg": "目录列表不能为空"}
        success, msg, data = self._request('SubmitRefreshTask', {
            'Type': 'dir',
            'Urls': '\n'.join(directories),
        })
        if success:
            task_id = data.get('TaskId', '')
            return {"status": True, "msg": "目录刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "目录刷新失败: {}".format(msg)}

    def purge_all(self):
        """全量刷新：刷新域名根目录"""
        if not self.domain_name:
            return {"status": False, "msg": "需要指定域名才能全量刷新"}
        success, msg, data = self._request('SubmitRefreshTask', {
            'Type': 'dir',
            'Urls': 'https://{}/\nhttp://{}/'.format(self.domain_name, self.domain_name),
        })
        if success:
            task_id = data.get('TaskId', '')
            return {"status": True, "msg": "全量缓存刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "全量缓存刷新失败: {}".format(msg)}

    def preload_urls(self, urls):
        """预热URL（SubmitPreloadTask）"""
        if not urls:
            return {"status": False, "msg": "预热URL列表不能为空"}
        success, msg, data = self._request('SubmitPreloadTask', {
            'Urls': '\n'.join(urls),
        })
        if success:
            task_id = data.get('TaskId', '')
            return {"status": True, "msg": "缓存预热提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "缓存预热失败: {}".format(msg)}

    def get_purge_quota(self):
        """查询刷新配额（DescribeContentQuota）"""
        success, msg, data = self._request('DescribeContentQuota')
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
        """火山引擎CDN无Zone概念，返回域名配置概要"""
        if not self.domain_name:
            return {"status": False, "msg": "需要指定域名"}
        success, msg, data = self._request('DescribeDomains', {
            'Domain': self.domain_name,
        })
        if success:
            domains = data.get('Domains', [])
            if domains:
                d = domains[0]
                return {
                    "status": True,
                    "msg": "success",
                    "data": {
                        "zone_id": d.get('Domain', ''),
                        "name": d.get('Domain', ''),
                        "status": d.get('Status', ''),
                        "type": d.get('CdnType', ''),
                        "plan": '',
                    }
                }
            return {"status": False, "msg": "域名未在CDN中找到"}
        return {"status": False, "msg": "获取域名信息失败: {}".format(msg)}
