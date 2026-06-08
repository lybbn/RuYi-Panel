import hashlib
import hmac
import json
import logging
import datetime
import requests
from .base import CdnProviderBase

logger = logging.getLogger(__name__)


class AwsCloudFrontProvider(CdnProviderBase):
    """AWS CloudFront CDN缓存管理

    API文档: https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_CreateInvalidation.html
    认证方式: AWS Signature V4
    CloudFront没有"预热"概念（靠缓存规则自动缓存），也没有配额查询API
    """

    provider_name = "aws"
    provider_display = "AWS CloudFront"

    supports_purge_url = True
    supports_purge_all = True        # 通过Invalidation "/" 实现
    supports_purge_tag = False       # CloudFront无Cache-Tag概念
    supports_preload = False         # CloudFront无预热API
    supports_quota = False           # CloudFront无独立配额查询API

    SERVICE = "cloudfront"
    API_VERSION = "2020-05-31"

    def __init__(self, credentials, zone_id=None, domain_name=None):
        super().__init__(credentials)
        self.access_key = credentials.get('AccessKey', '')
        self.secret_key = credentials.get('SecretKey', '')
        self.region = credentials.get('region', 'us-east-1')
        self.distribution_id = zone_id  # CloudFront使用Distribution ID
        self.domain_name = domain_name
        self.timeout = 65

    def _sign_v4(self, method, uri, query, headers, body=''):
        """AWS Signature V4签名"""
        t = datetime.datetime.utcnow()
        date_stamp = t.strftime('%Y%m%d')
        amz_date = t.strftime('%Y%m%dT%H%M%SZ')

        # 构造小写key的headers映射
        lower_headers = {k.lower(): v for k, v in headers.items()}

        # Step 1: 规范请求
        canonical_uri = uri
        canonical_querystring = query
        # 需要签名的头
        signed_header_keys = sorted(['host', 'x-amz-date'])
        canonical_headers = ''
        for k in signed_header_keys:
            canonical_headers += '{}:{}\n'.format(k, lower_headers.get(k, ''))
        signed_headers = ';'.join(signed_header_keys)
        payload_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
        canonical_request = '{}\n{}\n{}\n{}\n{}\n{}'.format(
            method, canonical_uri, canonical_querystring,
            canonical_headers, signed_headers, payload_hash
        )

        # Step 2: 待签名字符串
        credential_scope = '{}/{}/{}/aws4_request'.format(date_stamp, self.region, self.SERVICE)
        string_to_sign = 'AWS4-HMAC-SHA256\n{}\n{}\n{}'.format(
            amz_date, credential_scope,
            hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        )

        # Step 3: 计算签名
        def hmac_sha256(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

        k_date = hmac_sha256(('AWS4' + self.secret_key).encode('utf-8'), date_stamp)
        k_region = hmac_sha256(k_date, self.region)
        k_service = hmac_sha256(k_region, self.SERVICE)
        k_signing = hmac_sha256(k_service, 'aws4_request')
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        authorization = 'AWS4-HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}'.format(
            self.access_key, credential_scope, signed_headers, signature
        )
        return authorization, amz_date

    def _request(self, method, uri, body=None):
        """发送CloudFront API请求"""
        host = 'cloudfront.amazonaws.com'
        url = 'https://{}{}'.format(host, uri)
        body_str = body or ''
        headers = {
            'host': host,
            'content-type': 'application/xml' if body else 'application/json',
        }
        authorization, amz_date = self._sign_v4(method, uri, '', headers, body_str)
        headers['x-amz-date'] = amz_date
        headers['Authorization'] = authorization

        try:
            resp = requests.request(method, url, headers=headers, data=body_str, timeout=self.timeout)
            if resp.status_code >= 400:
                try:
                    error_data = resp.json()
                    error_msg = error_data.get('Error', {}).get('Message', resp.text)
                except Exception:
                    error_msg = resp.text[:200]
                return False, error_msg, {}
            return True, 'success', resp.text
        except requests.RequestException as e:
            return False, str(e), {}
        except Exception as e:
            return False, str(e), {}

    def _ensure_distribution_id(self):
        """确保有Distribution ID"""
        if self.distribution_id:
            return self.distribution_id
        # CloudFront需要Distribution ID，无法通过域名自动查询（需要ListDistributions遍历）
        return None

    def purge_urls(self, urls):
        """按URL刷新缓存（CreateInvalidation）"""
        dist_id = self._ensure_distribution_id()
        if not dist_id:
            return {"status": False, "msg": "需要指定CloudFront Distribution ID才能刷新缓存"}
        if not urls:
            return {"status": False, "msg": "URL列表不能为空"}
        # 构造Invalidation Batch XML
        caller_ref = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        paths_xml = ''.join('<Path>{}</Path>'.format(u) for u in urls)
        body = (
            '<InvalidationBatch xmlns="http://cloudfront.amazonaws.com/doc/{version}/">'
            '<CallerReference>{ref}</CallerReference>'
            '<Paths><Quantity>{count}</Quantity><Items>{paths}</Items></Paths>'
            '</InvalidationBatch>'
        ).format(version=self.API_VERSION, ref=caller_ref, count=len(urls), paths=paths_xml)

        success, msg, data = self._request(
            'POST',
            '/{version}/distribution/{dist_id}/invalidation'.format(
                version=self.API_VERSION, dist_id=dist_id),
            body=body
        )
        if success:
            return {"status": True, "msg": "缓存刷新提交成功"}
        return {"status": False, "msg": "缓存刷新失败: {}".format(msg)}

    def purge_all(self):
        """全量刷新：Invalidation /* """
        dist_id = self._ensure_distribution_id()
        if not dist_id:
            return {"status": False, "msg": "需要指定CloudFront Distribution ID才能全量刷新"}
        caller_ref = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        body = (
            '<InvalidationBatch xmlns="http://cloudfront.amazonaws.com/doc/{version}/">'
            '<CallerReference>{ref}</CallerReference>'
            '<Paths><Quantity>1</Quantity><Items><Path>/*</Path></Items></Paths>'
            '</InvalidationBatch>'
        ).format(version=self.API_VERSION, ref=caller_ref)

        success, msg, data = self._request(
            'POST',
            '/{version}/distribution/{dist_id}/invalidation'.format(
                version=self.API_VERSION, dist_id=dist_id),
            body=body
        )
        if success:
            return {"status": True, "msg": "全量缓存刷新提交成功"}
        return {"status": False, "msg": "全量缓存刷新失败: {}".format(msg)}

    def get_zone_info(self):
        """获取CloudFront Distribution信息"""
        dist_id = self._ensure_distribution_id()
        if not dist_id:
            return {"status": False, "msg": "需要指定CloudFront Distribution ID"}
        success, msg, data = self._request(
            'GET',
            '/{version}/distribution/{dist_id}'.format(
                version=self.API_VERSION, dist_id=dist_id)
        )
        if success:
            return {
                "status": True,
                "msg": "success",
                "data": {
                    "zone_id": dist_id,
                    "name": self.domain_name or dist_id,
                    "status": '',
                    "type": 'CloudFront',
                    "plan": '',
                }
            }
        return {"status": False, "msg": "获取Distribution信息失败: {}".format(msg)}
