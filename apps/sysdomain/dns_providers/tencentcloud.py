import json
import hashlib
import hmac
import time
from datetime import datetime
import requests
from .base import DnsProviderBase, extract_zone


class TencentCloudProvider(DnsProviderBase):
    provider_name = "tencentcloud"
    provider_display = "腾讯云"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.secret_id = credentials.get('secret_id', '')
        self.secret_key = credentials.get('secret_key', '')
        self.endpoint = "dnspod.tencentcloudapi.com"
        self.host = "https://dnspod.tencentcloudapi.com"
        self.version = "2021-03-23"
        self.algorithm = "TC3-HMAC-SHA256"

    def _get_headers(self, action, payload):
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        ct = "application/json; charset=utf-8"
        canonical_headers = "content-type:%s\nhost:%s\nx-tc-action:%s\n" % (ct, self.endpoint, action.lower())
        signed_headers = "content-type;host;x-tc-action"
        hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (http_request_method + "\n" + canonical_uri + "\n" + canonical_querystring + "\n" +
                             canonical_headers + "\n" + signed_headers + "\n" + hashed_request_payload)
        credential_scope = date + "/" + "dnspod" + "/" + "tc3_request"
        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (self.algorithm + "\n" + str(timestamp) + "\n" + credential_scope + "\n" + hashed_canonical_request)

        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = sign(("TC3" + self.secret_key).encode("utf-8"), date)
        secret_service = sign(secret_date, "dnspod")
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (self.algorithm + " " + "Credential=" + self.secret_id + "/" + credential_scope + ", " +
                         "SignedHeaders=" + signed_headers + ", " + "Signature=" + signature)
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.endpoint,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": self.version,
        }
        return headers

    def get_domain_list(self):
        try:
            params = json.dumps({})
            headers = self._get_headers("DescribeDomainList", params)
            res = requests.post(self.host, headers=headers, data=params).json()
            domain_list = [
                {
                    "id": i["DomainId"],
                    "name": i["Name"],
                    "remark": i.get("Remark") or "",
                    "record_count": i.get("RecordCount") or 0,
                }
                for i in res.get("Response", {}).get("DomainList", [])
            ]
            if "Error" in res.get("Response", {}):
                return {"status": False, "msg": res["Response"]["Error"]["Message"], "data": []}
            return {"status": True, "msg": "success", "data": domain_list}
        except Exception as e:
            return {"status": False, "msg": str(e), "data": []}

    def get_dns_record(self, domain_name, **kwargs):
        root_domain, _, sub_domain = extract_zone(domain_name)
        params_data = {"Domain": root_domain}
        if kwargs.get("limit"):
            params_data["Limit"] = int(kwargs["limit"])
        if kwargs.get("page"):
            params_data["Offset"] = ((int(kwargs["page"]) - 1) * int(kwargs.get("limit", 20)))
        if kwargs.get("search"):
            params_data["Keyword"] = kwargs["search"]
        params = json.dumps(params_data)
        data = {"list": [], "info": {"record_total": 0}}
        try:
            headers = self._get_headers("DescribeRecordList", params)
            json_data = requests.post(self.host, headers=headers, data=params).json()
            json_data = json_data.get('Response', {})
            if "Error" in json_data:
                if json_data["Error"]["Code"] == "ResourceNotFound.NoDataOfRecord":
                    return data
                return data
            if 'RecordCountInfo' in json_data:
                data['info'] = {"record_total": json_data['RecordCountInfo'].get('SubdomainCount', 0)}
            data["list"] = [
                {
                    "RecordId": i["RecordId"],
                    "name": i["Name"] + "." + root_domain if i["Name"] != '@' else root_domain,
                    "value": i["Value"],
                    "line": i["Line"],
                    "ttl": i["TTL"],
                    "type": i["Type"],
                    "status": "enable" if i["Status"] == "ENABLE" else "disable",
                    "mx": i.get("MX"),
                    "updated_on": i.get("UpdatedOn", ""),
                    "remark": i.get("Remark") or "",
                }
                for i in json_data.get("RecordList", [])
            ]
        except Exception:
            pass
        return data

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        params = json.dumps({
            "Domain": root_domain,
            "SubDomain": sub_domain or "@",
            "RecordType": record_type,
            "RecordLine": kwargs.get("record_line", "默认"),
            "Value": value,
            "Remark": kwargs.get("remark", ""),
            "MX": kwargs.get("mx", 10),
            "TTL": kwargs.get("ttl", 600),
        })
        try:
            headers = self._get_headers("CreateRecord", params)
            res = requests.post(self.host, headers=headers, data=params).json()
            if "Error" in res.get('Response', {}):
                return {"status": False, "msg": res['Response']["Error"]["Message"]}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        root_domain, _, _ = extract_zone(domain_name)
        params = json.dumps({"Domain": root_domain, "RecordId": int(record_id)})
        try:
            headers = self._get_headers("DeleteRecord", params)
            res = requests.post(self.host, headers=headers, data=params).json()
            if "Error" in res.get('Response', {}):
                return {"status": False, "msg": res['Response']["Error"]["Message"]}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        params = json.dumps({
            "Domain": root_domain,
            "SubDomain": sub_domain or "@",
            "RecordType": record_type,
            "RecordLine": kwargs.get("record_line", "默认"),
            "Remark": kwargs.get("remark", ""),
            "Value": value,
            "RecordId": int(record_id),
            "MX": kwargs.get("mx", 10),
            "TTL": kwargs.get("ttl", 600),
        })
        try:
            headers = self._get_headers("ModifyRecord", params)
            res = requests.post(self.host, headers=headers, data=params).json()
            if "Error" in res.get('Response', {}):
                return {"status": False, "msg": res['Response']["Error"]["Message"]}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        root_domain, _, _ = extract_zone(domain_name)
        status_str = "DISABLE" if int(status) else "ENABLE"
        params = json.dumps({"Domain": root_domain, "RecordId": int(record_id), "Status": status_str})
        try:
            headers = self._get_headers("ModifyRecordStatus", params)
            res = requests.post(self.host, headers=headers, data=params).json()
            if "Error" in res.get('Response', {}):
                return {"status": False, "msg": res['Response']["Error"]["Message"]}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}
