import hashlib
import requests
from .base import DnsProviderBase, extract_zone


class WestProvider(DnsProviderBase):
    provider_name = "west"
    provider_display = "西部数码"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.user_name = credentials.get('user_name', '')
        self.api_password = credentials.get('api_password', '')
        self.api_url = "https://api.west.cn/API/v2/domain/"
        self.timeout = 65

    def _get_sign(self):
        return hashlib.md5((self.user_name + self.api_password).encode('utf-8')).hexdigest()

    def _post(self, action, data):
        data['username'] = self.user_name
        data['sign'] = self._get_sign()
        data['act'] = action
        try:
            res = requests.post(self.api_url, data=data, timeout=self.timeout).json()
            return res
        except Exception as e:
            return {"result": 500, "msg": str(e)}

    def get_domain_list(self):
        try:
            res = self._post("getlist", {"page": 1, "limit": 100})
            if res.get("result") != 200:
                return {"status": False, "msg": res.get("msg", "error"), "data": []}
            domain_list = [
                {
                    "id": i.get("domainid", ""),
                    "name": i.get("domain", ""),
                    "remark": "",
                    "record_count": 0,
                }
                for i in res.get("data", [])
            ]
            return {"status": True, "msg": "success", "data": domain_list}
        except Exception as e:
            return {"status": False, "msg": str(e), "data": []}

    def get_dns_record(self, domain_name, **kwargs):
        root_domain, _, sub_domain = extract_zone(domain_name)
        data = {"list": [], "info": {"record_total": 0}}
        try:
            res = self._post("dnslist", {"domain": root_domain})
            if res.get("result") != 200:
                return data
            records = res.get("data", [])
            data["list"] = [
                {
                    "RecordId": i.get("id", ""),
                    "name": i.get("item") + "." + root_domain if i.get("item") != '@' else root_domain,
                    "value": i.get("value", ""),
                    "line": i.get("line", "默认"),
                    "ttl": i.get("ttl", 600),
                    "type": i.get("type", ""),
                    "status": "enable",
                    "mx": i.get("mx", 0),
                    "updated_on": "",
                    "remark": "",
                }
                for i in records
            ]
            data["info"] = {"record_total": len(records)}
        except Exception:
            pass
        return data

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            data = {
                "domain": root_domain,
                "type": record_type,
                "item": sub_domain or "@",
                "value": value,
                "ttl": kwargs.get("ttl", 600),
            }
            if record_type == "MX":
                data["mx"] = kwargs.get("mx", 10)
            res = self._post("dnsadd", data)
            if res.get("result") != 200:
                return {"status": False, "msg": res.get("msg", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        root_domain, _, _ = extract_zone(domain_name)
        try:
            res = self._post("dnsdel", {"domain": root_domain, "id": record_id})
            if res.get("result") != 200:
                return {"status": False, "msg": res.get("msg", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            data = {
                "domain": root_domain,
                "id": record_id,
                "type": record_type,
                "item": sub_domain or "@",
                "value": value,
                "ttl": kwargs.get("ttl", 600),
            }
            if record_type == "MX":
                data["mx"] = kwargs.get("mx", 10)
            res = self._post("dnsmod", data)
            if res.get("result") != 200:
                return {"status": False, "msg": res.get("msg", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        return {"status": False, "msg": "West.cn does not support pausing individual records"}
