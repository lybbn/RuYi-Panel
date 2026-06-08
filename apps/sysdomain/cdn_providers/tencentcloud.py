import hashlib
import hmac
import json
import logging
import time
import datetime
import requests
from .base import CdnProviderBase

logger = logging.getLogger(__name__)


class TencentCloudCdnProvider(CdnProviderBase):
    """腾讯云CDN缓存管理

    API文档: https://cloud.tencent.com/document/api/228/30974
    认证方式: TC3-HMAC-SHA256签名
    """

    provider_name = "tencentcloud"
    provider_display = "腾讯云CDN"

    supports_purge_url = True
    supports_purge_all = True        # 通过目录刷新根路径实现
    supports_purge_tag = False       # 腾讯云无Cache-Tag概念
    supports_preload = True
    supports_quota = True

    SERVICE = "cdn"
    HOST = "cdn.tencentcloudapi.com"
    API_VERSION = "2018-06-06"

    def __init__(self, credentials, zone_id=None, domain_name=None):
        super().__init__(credentials)
        self.secret_id = credentials.get('secret_id', '')
        self.secret_key = credentials.get('secret_key', '')
        self.domain_name = domain_name
        self.timeout = 65

    def _sign(self, payload, action):
        """TC3-HMAC-SHA256签名"""
        timestamp = int(time.time())
        date = datetime.datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')

        # 拼接规范请求串
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        content_type = "application/json; charset=utf-8"
        canonical_headers = "content-type:{}\nhost:{}\nx-tc-action:{}\n".format(
            content_type.lower(), self.HOST, action.lower()
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        canonical_request = "{}\n{}\n{}\n{}\n{}\n{}".format(
            http_request_method, canonical_uri, canonical_querystring,
            canonical_headers, signed_headers, hashed_request_payload
        )

        # 拼接待签名字符串
        algorithm = "TC3-HMAC-SHA256"
        credential_scope = "{}/{}/tc3_request".format(date, self.SERVICE)
        hashed_canonical_request = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        string_to_sign = "{}\n{}\n{}\n{}".format(
            algorithm, timestamp, credential_scope, hashed_canonical_request
        )

        # 计算签名
        secret_date = hmac.new(
            ("TC3" + self.secret_key).encode('utf-8'),
            date.encode('utf-8'), hashlib.sha256
        ).digest()
        secret_service = hmac.new(secret_date, self.SERVICE.encode('utf-8'), hashlib.sha256).digest()
        secret_signing = hmac.new(secret_service, "tc3_request".encode('utf-8'), hashlib.sha256).digest()
        signature = hmac.new(secret_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # 拼接Authorization
        authorization = "{} Credential={}/{}, SignedHeaders={}, Signature={}".format(
            algorithm, self.secret_id, credential_scope, signed_headers, signature
        )

        headers = {
            "Authorization": authorization,
            "Content-Type": content_type,
            "Host": self.HOST,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": self.API_VERSION,
            "X-TC-Region": "",
        }
        return headers

    def _request(self, action, params=None):
        """发送腾讯云API请求"""
        if params is None:
            params = {}
        payload = json.dumps(params)
        headers = self._sign(payload, action)

        try:
            resp = requests.post(
                "https://{}".format(self.HOST),
                headers=headers,
                data=payload,
                timeout=self.timeout
            )
            data = resp.json()
            response = data.get('Response', {})
            error = response.get('Error')
            if error:
                return False, error.get('Message', 'Unknown error'), data
            return True, 'success', response
        except requests.RequestException as e:
            return False, str(e), {}
        except Exception as e:
            return False, str(e), {}

    def purge_urls(self, urls):
        """按URL刷新缓存（PurgeUrlsCache）"""
        if not urls:
            return {"status": False, "msg": "URL列表不能为空"}
        success, msg, data = self._request('PurgeUrlsCache', {
            'Urls': urls,
            'FlushType': 'flush',
        })
        if success:
            task_id = data.get('TaskId', '')
            return {"status": True, "msg": "缓存刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "缓存刷新失败: {}".format(msg)}

    def purge_paths_cache(self, paths):
        """按目录刷新缓存（PurgePathsCache）"""
        if not paths:
            return {"status": False, "msg": "目录列表不能为空"}
        success, msg, data = self._request('PurgePathsCache', {
            'Paths': paths,
            'FlushType': 'flush',
        })
        if success:
            task_id = data.get('TaskId', '')
            return {"status": True, "msg": "目录刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "目录刷新失败: {}".format(msg)}

    def purge_all(self):
        """全量刷新：通过目录刷新域名根路径，清空该域名下所有缓存"""
        if not self.domain_name:
            return {"status": False, "msg": "需要指定域名才能全量刷新"}
        success, msg, data = self._request('PurgePathsCache', {
            'Paths': [
                'https://{}/'.format(self.domain_name),
                'http://{}/'.format(self.domain_name),
            ],
            'FlushType': 'flush',
        })
        if success:
            task_id = data.get('TaskId', '')
            return {"status": True, "msg": "全量缓存刷新提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "全量缓存刷新失败: {}".format(msg)}

    def preload_urls(self, urls):
        """预热URL（PushUrlsCache）"""
        if not urls:
            return {"status": False, "msg": "预热URL列表不能为空"}
        success, msg, data = self._request('PushUrlsCache', {
            'Urls': urls,
        })
        if success:
            task_id = data.get('TaskId', '')
            return {"status": True, "msg": "缓存预热提交成功，任务ID: {}".format(task_id)}
        return {"status": False, "msg": "缓存预热失败: {}".format(msg)}

    def get_purge_quota(self):
        """查询刷新配额（DescribePurgeQuota）"""
        success, msg, data = self._request('DescribePurgeQuota')
        if success:
            url_purge = data.get('UrlPurge', {})
            path_purge = data.get('PathPurge', {})
            preload = data.get('Push', {})
            return {
                "status": True,
                "msg": "success",
                "data": {
                    "url_quota": url_purge.get('Total', ''),
                    "url_remain": url_purge.get('Available', ''),
                    "dir_quota": path_purge.get('Total', ''),
                    "dir_remain": path_purge.get('Available', ''),
                    "preload_quota": preload.get('Total', ''),
                    "preload_remain": preload.get('Available', ''),
                }
            }
        return {"status": False, "msg": "查询配额失败: {}".format(msg)}

    def get_zone_info(self):
        """腾讯云CDN无Zone概念，返回域名配置概要"""
        if not self.domain_name:
            return {"status": False, "msg": "需要指定域名"}
        success, msg, data = self._request('DescribeDomains', {
            'Filters': [{'Name': 'domain', 'Value': [self.domain_name]}],
            'Offset': 0,
            'Limit': 1,
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
