import requests
from .base import DnsProviderBase, extract_zone


class CloudflareProvider(DnsProviderBase):
    provider_name = "cloudflare"
    provider_display = "CloudFlare"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.api_token = credentials.get('API Token', '')
        self.email = credentials.get('E-Mail', '')
        self.api_key = credentials.get('API Key', '')
        self.base_url = "https://api.cloudflare.com/client/v4"
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

    def _get_zone_id(self, domain_name):
        url = "{}/zones?name={}".format(self.base_url, domain_name)
        res = requests.get(url, headers=self._get_headers(), timeout=self.timeout).json()
        if res.get("success") and res.get("result"):
            return res["result"][0]["id"]
        return None

    def get_domain_list(self):
        url = "{}/zones".format(self.base_url)
        try:
            res = requests.get(url, headers=self._get_headers(), timeout=self.timeout).json()
            if not res.get("success"):
                return {"status": False, "msg": res.get("errors", [{}])[0].get("message", "error"), "data": []}
            domain_list = [
                {
                    "id": i["id"],
                    "name": i["name"],
                    "remark": i.get("description") or "",
                    "record_count": 0,
                }
                for i in res.get("result", [])
            ]
            return {"status": True, "msg": "success", "data": domain_list}
        except Exception as e:
            return {"status": False, "msg": str(e), "data": []}

    def get_dns_record(self, domain_name, **kwargs):
        root_domain, _, sub_domain = extract_zone(domain_name)
        data = {"list": [], "info": {"record_total": 0}}
        try:
            zone_id = self._get_zone_id(root_domain)
            if not zone_id:
                return data
            url = "{}/zones/{}/dns_records?per_page=100".format(self.base_url, zone_id)
            if kwargs.get("search"):
                url += "&name={}".format(kwargs["search"])
            if kwargs.get("record_type"):
                url += "&type={}".format(kwargs["record_type"])
            res = requests.get(url, headers=self._get_headers(), timeout=self.timeout).json()
            if not res.get("success"):
                return data
            data["list"] = [
                {
                    "RecordId": i["id"],
                    "name": i["name"],
                    "value": i["content"],
                    "line": i.get("proxied") and "Proxied" or "DNS only",
                    "ttl": i["ttl"],
                    "type": i["type"],
                    "status": "enable",
                    "mx": i.get("priority") or 0,
                    "updated_on": i.get("modified_on", ""),
                    "remark": i.get("comment") or "",
                }
                for i in res.get("result", [])
            ]
            data["info"] = {"record_total": res.get("result_info", {}).get("total_count", len(data["list"]))}
        except Exception:
            pass
        return data

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            zone_id = self._get_zone_id(root_domain)
            if not zone_id:
                return {"status": False, "msg": "zone not found"}
            url = "{}/zones/{}/dns_records".format(self.base_url, zone_id)
            body = {
                "type": record_type,
                "name": domain_name if sub_domain else root_domain,
                "content": value,
                "ttl": kwargs.get("ttl", 1),
                "proxied": kwargs.get("proxied", False),
                "comment": kwargs.get("remark", ""),
            }
            if record_type == "MX":
                body["priority"] = kwargs.get("mx", 10)
            res = requests.post(url, headers=self._get_headers(), json=body, timeout=self.timeout).json()
            if not res.get("success"):
                return {"status": False, "msg": res.get("errors", [{}])[0].get("message", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        root_domain, _, _ = extract_zone(domain_name)
        try:
            zone_id = self._get_zone_id(root_domain)
            if not zone_id:
                return {"status": False, "msg": "zone not found"}
            url = "{}/zones/{}/dns_records/{}".format(self.base_url, zone_id, record_id)
            res = requests.delete(url, headers=self._get_headers(), timeout=self.timeout).json()
            if not res.get("success"):
                return {"status": False, "msg": res.get("errors", [{}])[0].get("message", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            zone_id = self._get_zone_id(root_domain)
            if not zone_id:
                return {"status": False, "msg": "zone not found"}
            url = "{}/zones/{}/dns_records/{}".format(self.base_url, zone_id, record_id)
            body = {
                "type": record_type,
                "name": domain_name if sub_domain else root_domain,
                "content": value,
                "ttl": kwargs.get("ttl", 1),
                "proxied": kwargs.get("proxied", False),
                "comment": kwargs.get("remark", ""),
            }
            if record_type == "MX":
                body["priority"] = kwargs.get("mx", 10)
            res = requests.put(url, headers=self._get_headers(), json=body, timeout=self.timeout).json()
            if not res.get("success"):
                return {"status": False, "msg": res.get("errors", [{}])[0].get("message", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        return {"status": False, "msg": "Cloudflare does not support pausing individual records"}
