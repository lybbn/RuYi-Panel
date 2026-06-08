import json
import hashlib
import hmac
import datetime
import requests
from .base import DnsProviderBase, extract_zone


class VolcengineProvider(DnsProviderBase):
    provider_name = "volcengine"
    provider_display = "火山引擎"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.access_key = credentials.get('AccessKey', '')
        self.secret_key = credentials.get('SecretKey', '')
        self.host = "open.volcengineapi.com"
        self.service = "DNS"
        self.version = "2022-06-01"
        self.region = "cn-north-1"

    def _sign_request(self, action, body, query=None):
        method = "POST"
        date = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        short_date = date[:8]
        content_type = "application/json"
        body_str = json.dumps(body) if isinstance(body, dict) else body
        body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
        query_str = ""
        if query:
            sorted_query = sorted(query.items())
            query_str = "&".join(["{}={}".format(k, v) for k, v in sorted_query])
        canonical_headers = "content-type:{}\nhost:{}\nx-content-sha256:{}\nx-date:{}\n".format(
            content_type, self.host, body_hash, date)
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = "{}\n/\n{}\n{}\n{}\n{}".format(
            method, query_str, canonical_headers, signed_headers, body_hash)
        credential_scope = "{}/{}/{}/request".format(short_date, self.region, self.service)
        string_to_sign = "HMAC-SHA256\n{}\n{}\n{}".format(
            date, credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest())

        def hmac_sha256(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = hmac_sha256(self.secret_key.encode("utf-8"), short_date)
        k_region = hmac_sha256(k_date, self.region)
        k_service = hmac_sha256(k_region, self.service)
        k_signing = hmac_sha256(k_service, "request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = "HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}".format(
            self.access_key, credential_scope, signed_headers, signature)
        headers = {
            "Authorization": authorization,
            "Content-Type": content_type,
            "Host": self.host,
            "X-Content-Sha256": body_hash,
            "X-Date": date,
        }
        url = "https://{}/?{}".format(self.host, query_str) if query_str else "https://{}/".format(self.host)
        res = requests.post(url, headers=headers, data=body_str, timeout=65)
        return res

    def get_domain_list(self):
        try:
            body = {"PageSize": 100, "PageNumber": 1}
            query = {"Action": "ListZones", "Version": self.version}
            res = self._sign_request("ListZones", body, query)
            if res.status_code != 200:
                return {"status": False, "msg": res.text, "data": []}
            response = res.json()
            if "Error" in response:
                return {"status": False, "msg": response["Error"].get("Message", "error"), "data": []}
            domain_list = [
                {
                    "id": i["ZoneID"],
                    "name": i["ZoneName"],
                    "remark": i.get("Remark") or "",
                    "record_count": i.get("RecordCount") or 0,
                }
                for i in response.get("Zones", [])
            ]
            return {"status": True, "msg": "success", "data": domain_list}
        except Exception as e:
            return {"status": False, "msg": str(e), "data": []}

    def get_dns_record(self, domain_name, **kwargs):
        root_domain, _, sub_domain = extract_zone(domain_name)
        data = {"list": [], "info": {"record_total": 0}}
        try:
            body = {"ZoneName": root_domain, "PageSize": 100, "PageNumber": 1}
            if kwargs.get("search"):
                body["Search"] = kwargs["search"]
            query = {"Action": "ListRecords", "Version": self.version}
            res = self._sign_request("ListRecords", body, query)
            if res.status_code != 200:
                return data
            response = res.json()
            if "Error" in response:
                return data
            records = response.get("Records", [])
            data["list"] = [
                {
                    "RecordId": i["RecordID"],
                    "name": i["Host"] + "." + root_domain if i["Host"] != '@' else root_domain,
                    "value": i["Value"],
                    "line": i.get("Line") or "默认",
                    "ttl": i.get("TTL", 600),
                    "type": i["Type"],
                    "status": "enable" if i.get("Enable", True) else "disable",
                    "mx": i.get("Weight", 0),
                    "updated_on": i.get("UpdatedAt", ""),
                    "remark": i.get("Remark") or "",
                }
                for i in records
            ]
            data["info"] = {"record_total": response.get("Total", len(records))}
        except Exception:
            pass
        return data

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            body = {
                "ZoneName": root_domain,
                "Host": sub_domain or "@",
                "Type": record_type,
                "Value": value,
                "TTL": kwargs.get("ttl", 600),
            }
            if record_type == "MX":
                body["Weight"] = kwargs.get("mx", 10)
            query = {"Action": "CreateRecord", "Version": self.version}
            res = self._sign_request("CreateRecord", body, query)
            if res.status_code != 200:
                return {"status": False, "msg": res.text}
            response = res.json()
            if "Error" in response:
                return {"status": False, "msg": response["Error"].get("Message", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        try:
            body = {"RecordID": record_id}
            query = {"Action": "DeleteRecord", "Version": self.version}
            res = self._sign_request("DeleteRecord", body, query)
            if res.status_code != 200:
                return {"status": False, "msg": res.text}
            response = res.json()
            if "Error" in response:
                return {"status": False, "msg": response["Error"].get("Message", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            body = {
                "RecordID": record_id,
                "Host": sub_domain or "@",
                "Type": record_type,
                "Value": value,
                "TTL": kwargs.get("ttl", 600),
            }
            if record_type == "MX":
                body["Weight"] = kwargs.get("mx", 10)
            query = {"Action": "UpdateRecord", "Version": self.version}
            res = self._sign_request("UpdateRecord", body, query)
            if res.status_code != 200:
                return {"status": False, "msg": res.text}
            response = res.json()
            if "Error" in response:
                return {"status": False, "msg": response["Error"].get("Message", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        try:
            body = {"RecordID": record_id, "Enable": not bool(int(status))}
            query = {"Action": "UpdateRecordStatus", "Version": self.version}
            res = self._sign_request("UpdateRecordStatus", body, query)
            if res.status_code != 200:
                return {"status": False, "msg": res.text}
            response = res.json()
            if "Error" in response:
                return {"status": False, "msg": response["Error"].get("Message", "error")}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}
