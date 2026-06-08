import logging
import requests
from .base import CdnProviderBase

logger = logging.getLogger(__name__)


class CloudflareCdnProvider(CdnProviderBase):
    """Cloudflare CDN缓存管理"""

    provider_name = "cloudflare"
    provider_display = "Cloudflare"

    supports_purge_url = True
    supports_purge_all = True
    supports_purge_tag = True
    supports_preload = False    # Cloudflare无预热API，靠缓存规则自动缓存
    supports_quota = False      # Cloudflare无独立配额查询API

    def __init__(self, credentials, zone_id=None, domain_name=None):
        super().__init__(credentials)
        self.api_token = credentials.get('API Token', '')
        self.email = credentials.get('E-Mail', '')
        self.api_key = credentials.get('API Key', '')
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.zone_id = zone_id
        self.domain_name = domain_name
        self.timeout = 65

    def _get_headers(self):
        if self.api_token:
            return {
                "Authorization": "Bearer " + self.api_token,
                "Content-Type": "application/json",
            }
        if self.email:
            return {
                "X-Auth-Email": self.email,
                "X-Auth-Key": self.api_key,
                "Content-Type": "application/json",
            }
        return {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }

    def _request(self, method, path, **kwargs):
        url = "{}{}".format(self.base_url, path)
        try:
            resp = requests.request(
                method, url, headers=self._get_headers(),
                timeout=self.timeout, **kwargs
            )
            data = resp.json()
            if not data.get("success"):
                errors = data.get("errors", [{}])
                msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
                return False, msg, data
            return True, "success", data
        except requests.RequestException as e:
            return False, str(e), {}
        except Exception as e:
            return False, str(e), {}

    def _ensure_zone_id(self):
        """确保zone_id存在，如果没有则通过域名查询"""
        if self.zone_id:
            return self.zone_id
        if not self.domain_name:
            return None
        success, _, data = self._request("GET", "/zones?name={}".format(self.domain_name))
        if success and data.get("result"):
            self.zone_id = data["result"][0]["id"]
            return self.zone_id
        return None

    def purge_urls(self, urls):
        """按URL刷新缓存，urls为URL列表"""
        zone_id = self._ensure_zone_id()
        if not zone_id:
            return {"status": False, "msg": "Zone ID not found, please check domain configuration"}
        if not urls:
            return {"status": False, "msg": "URLs list is empty"}
        success, msg, data = self._request(
            "POST", "/zones/{}/purge_cache".format(zone_id),
            json={"files": urls}
        )
        if success:
            return {"status": True, "msg": "Purge cache submitted successfully"}
        return {"status": False, "msg": "Purge failed: {}".format(msg)}

    def purge_all(self):
        """全量刷新缓存"""
        zone_id = self._ensure_zone_id()
        if not zone_id:
            return {"status": False, "msg": "Zone ID not found, please check domain configuration"}
        success, msg, data = self._request(
            "POST", "/zones/{}/purge_cache".format(zone_id),
            json={"purge_everything": True}
        )
        if success:
            return {"status": True, "msg": "Purge all cache submitted successfully"}
        return {"status": False, "msg": "Purge all failed: {}".format(msg)}

    def purge_tags(self, tags):
        """按Cache-Tag刷新缓存"""
        zone_id = self._ensure_zone_id()
        if not zone_id:
            return {"status": False, "msg": "Zone ID not found, please check domain configuration"}
        if not tags:
            return {"status": False, "msg": "Tags list is empty"}
        success, msg, data = self._request(
            "POST", "/zones/{}/purge_cache".format(zone_id),
            json={"tags": tags}
        )
        if success:
            return {"status": True, "msg": "Purge by tags submitted successfully"}
        return {"status": False, "msg": "Purge by tags failed: {}".format(msg)}

    def get_zone_info(self):
        """获取Zone信息（含缓存设置概览）"""
        zone_id = self._ensure_zone_id()
        if not zone_id:
            return {"status": False, "msg": "Zone ID not found, please check domain configuration"}
        success, msg, data = self._request("GET", "/zones/{}".format(zone_id))
        if success:
            result = data.get("result", {})
            return {
                "status": True,
                "msg": "success",
                "data": {
                    "zone_id": result.get("id"),
                    "name": result.get("name"),
                    "status": result.get("status"),
                    "plan": result.get("plan", {}).get("name", ""),
                    "type": result.get("type"),
                    "name_servers": result.get("name_servers", []),
                    "original_registrar": result.get("original_registrar"),
                }
            }
        return {"status": False, "msg": "Get zone info failed: {}".format(msg)}
