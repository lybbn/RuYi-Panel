import requests
from urllib.parse import urljoin
from .base import DnsProviderBase, extract_zone


class DnspodProvider(DnsProviderBase):
    provider_name = "dnspod"
    provider_display = "DNSPod"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.dnspod_id = credentials.get('ID', '')
        self.dnspod_key = credentials.get('Token', '')
        self.api_base_url = 'https://dnsapi.cn/'
        self.timeout = 65
        self.login_token = "{0},{1}".format(self.dnspod_id, self.dnspod_key)

    def get_domain_list(self):
        url = urljoin(self.api_base_url, "Domain.List")
        body = {"login_token": self.login_token, "format": "json"}
        try:
            res = requests.post(url, data=body, timeout=self.timeout).json()
            domain_list = [
                {
                    "id": i["id"],
                    "name": i["name"],
                    "remark": i.get("remark") or "",
                    "record_count": i.get("records") or 0,
                }
                for i in res.get("domains", [])
            ]
            return {"status": True, "msg": "success", "data": domain_list}
        except Exception as e:
            return {"status": False, "msg": str(e), "data": []}

    def get_dns_record(self, domain_name, **kwargs):
        root_domain, _, sub_domain = extract_zone(domain_name)
        url = urljoin(self.api_base_url, "Record.List")
        body = {
            "login_token": self.login_token,
            "format": "json",
            "domain": root_domain,
        }
        if kwargs.get("limit"):
            body["length"] = int(kwargs["limit"])
        if kwargs.get("page"):
            body["offset"] = ((int(kwargs["page"]) - 1) * int(kwargs.get("limit", 20)))
        if kwargs.get("search"):
            body["keyword"] = kwargs["search"]
        try:
            res = requests.post(url, data=body, timeout=self.timeout).json()
        except Exception:
            return {"list": [], "info": {"record_total": 0}}
        data = {}
        if res.get("status", {}).get("code") == "10":
            return {"list": [], "info": {"record_total": 0}}
        if "records" in res:
            for i in res["records"]:
                i['name'] = i['name'] + "." + root_domain if i['name'] != '@' else root_domain
                i['RecordId'] = i['id']
                i["status"] = "enable" if i["status"] == "enable" else "disable"
            data['list'] = res["records"]
        if 'info' in res:
            data['info'] = res['info']
        if not data:
            data = {"list": [], "info": {"record_total": 0}}
        return data

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        url = urljoin(self.api_base_url, "Record.Create")
        body = {
            "record_type": record_type,
            "domain": root_domain,
            "sub_domain": sub_domain or "@",
            "value": value,
            "remark": kwargs.get("remark", ""),
            "mx": kwargs.get("mx", 0),
            "record_line": kwargs.get("record_line", "默认"),
            "ttl": kwargs.get("ttl", 600),
            "format": "json",
            "login_token": self.login_token,
        }
        try:
            res = requests.post(url, data=body, timeout=self.timeout).json()
            if res["status"]["code"] != "1":
                return {"status": False, "msg": res["status"]["message"]}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        root_domain, _, _ = extract_zone(domain_name)
        url = urljoin(self.api_base_url, "Record.Remove")
        body = {
            "login_token": self.login_token,
            "format": "json",
            "domain": root_domain,
            "record_id": record_id,
        }
        try:
            res = requests.post(url, data=body, timeout=self.timeout).json()
            if res["status"]["code"] != "1":
                return {"status": False, "msg": res["status"]["message"]}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        url = urljoin(self.api_base_url, "Record.Modify")
        body = {
            "login_token": self.login_token,
            "domain": root_domain,
            "record_id": record_id,
            "sub_domain": sub_domain or "@",
            "record_type": record_type,
            "record_line": kwargs.get("record_line", "默认"),
            "value": value,
            "remark": kwargs.get("remark", ""),
            "mx": kwargs.get("mx", 0),
            "ttl": kwargs.get("ttl", 600),
        }
        try:
            res = requests.post(url, data=body, timeout=self.timeout).json()
            if res["status"]["code"] != "1":
                return {"status": False, "msg": res["status"]["message"]}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        root_domain, _, _ = extract_zone(domain_name)
        status_str = "disable" if int(status) else "enable"
        url = urljoin(self.api_base_url, "Record.Status")
        body = {
            "login_token": self.login_token,
            "domain": root_domain,
            "record_id": record_id,
            "status": status_str,
        }
        try:
            res = requests.post(url, data=body, timeout=self.timeout).json()
            if res["status"]["code"] != "1":
                return {"status": False, "msg": res["status"]["message"]}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}
