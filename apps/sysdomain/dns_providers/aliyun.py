import time
import hashlib
import hmac
import uuid
import pytz
import requests
from urllib.parse import urlencode, quote_plus
from datetime import datetime
from .base import DnsProviderBase, extract_zone


class AliyunProvider(DnsProviderBase):
    provider_name = "aliyun"
    provider_display = "阿里云"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.access_key_id = credentials.get('AccessKey', '')
        self.access_key_secret = credentials.get('SecretKey', '')
        self.endpoint = "alidns.cn-hangzhou.aliyuncs.com"
        self.algorithm = "ACS3-HMAC-SHA256"
        self.x_acs_version = "2015-01-09"

    def _sign_request(self, action, query_param):
        def hmac256(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

        def sha256_hex(s):
            return hashlib.sha256(s.encode('utf-8')).hexdigest()

        def percent_code(encoded_str):
            return encoded_str.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')

        headers = {
            "host": self.endpoint,
            "x-acs-action": action,
            "x-acs-version": self.x_acs_version,
            "x-acs-date": datetime.now(pytz.timezone('Etc/GMT')).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "x-acs-signature-nonce": str(uuid.uuid4()),
        }
        sorted_query_params = sorted(query_param.items(), key=lambda item: item[0])
        query_param = {k: v for k, v in sorted_query_params}
        canonical_query_string = '&'.join(
            f'{percent_code(quote_plus(k))}={percent_code(quote_plus(str(v)))}' for k, v in query_param.items())
        hashed_request_payload = sha256_hex('')
        headers['x-acs-content-sha256'] = hashed_request_payload
        sorted_headers = sorted(headers.items(), key=lambda item: item[0])
        headers = {k: v for k, v in sorted_headers}
        canonical_headers = '\n'.join(
            f'{k.lower()}:{v}' for k, v in headers.items() if
            k.lower().startswith('x-acs-') or k.lower() in ['host', 'content-type'])
        signed_headers = ';'.join(sorted(headers.keys(), key=lambda x: x.lower()))
        canonical_request = f'GET\n/\n{canonical_query_string}\n{canonical_headers}\n\n{signed_headers}\n{hashed_request_payload}'
        hashed_canonical_request = sha256_hex(canonical_request)
        string_to_sign = f'{self.algorithm}\n{hashed_canonical_request}'
        signature = hmac256(self.access_key_secret.encode('utf-8'), string_to_sign).hex().lower()
        authorization = f'{self.algorithm} Credential={self.access_key_id},SignedHeaders={signed_headers},Signature={signature}'
        headers['Authorization'] = authorization
        url = f'https://{self.endpoint}/'
        if query_param:
            url += '?' + urlencode(query_param, doseq=True, safe='*')
        response = requests.request(method="GET", url=url, headers=headers)
        return response

    def get_domain_list(self):
        try:
            response = self._sign_request("DescribeDomains", {"PageNumber": 1, "PageSize": 100})
            if response.status_code != 200:
                return {"status": False, "msg": response.text, "data": []}
            data = response.json()
            domain_list = [
                {
                    "id": i["DomainId"],
                    "name": i["DomainName"],
                    "remark": i.get("Remark") or "",
                    "record_count": i.get("RecordCount") or 0,
                }
                for i in data["Domains"]["Domain"]
            ]
            return {"status": True, "msg": "success", "data": domain_list}
        except Exception as e:
            return {"status": False, "msg": str(e), "data": []}

    def get_dns_record(self, domain_name, **kwargs):
        root_domain, _, sub_domain = extract_zone(domain_name)
        query_param = {"DomainName": root_domain}
        if kwargs.get("limit"):
            query_param["PageSize"] = int(kwargs["limit"])
        if kwargs.get("page"):
            query_param["PageNumber"] = kwargs["page"]
        if kwargs.get("search"):
            query_param["KeyWord"] = kwargs["search"]
        data = {"list": [], "info": {"record_total": 0}}
        try:
            response = self._sign_request("DescribeDomainRecords", query_param)
            res = response.json()
            if response.status_code != 200:
                return data
            data["list"] = [
                {
                    "RecordId": i["RecordId"],
                    "name": i["RR"] + "." + root_domain if i["RR"] != '@' else root_domain,
                    "value": i["Value"],
                    "line": i["Line"],
                    "ttl": i["TTL"],
                    "type": i["Type"],
                    "status": "enable" if i["Status"] == "ENABLE" else "disable",
                    "mx": i.get("Priority") or 0,
                    "updated_on": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(i["UpdateTimestamp"] / 1000)) if i.get("UpdateTimestamp") else "",
                    "remark": i.get("Remark") or "",
                }
                for i in res["DomainRecords"]["Record"]
            ]
            data["info"] = {"record_total": res["TotalCount"]}
        except Exception:
            pass
        return data

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        query_param = {
            "DomainName": root_domain,
            "RR": sub_domain or "@",
            "Type": record_type,
            "Value": value,
            "Priority": kwargs.get("mx", 0),
            "Line": kwargs.get("record_line", "default"),
            "TTL": kwargs.get("ttl", 600),
        }
        try:
            response = self._sign_request("AddDomainRecord", query_param)
            if response.status_code != 200:
                return {"status": False, "msg": response.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        try:
            response = self._sign_request("DeleteDomainRecord", {"RecordId": record_id})
            if response.status_code != 200:
                return {"status": False, "msg": response.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        params = {
            "RecordId": record_id,
            "Type": record_type,
            "Value": value,
            "RR": sub_domain or "@",
            "Priority": kwargs.get("mx", 0),
            "Line": kwargs.get("record_line", "default"),
            "TTL": kwargs.get("ttl", 600),
        }
        try:
            response = self._sign_request("UpdateDomainRecord", params)
            if response.status_code != 200:
                return {"status": False, "msg": response.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        status_str = "Disable" if int(status) else "Enable"
        try:
            params = {"RecordId": record_id, "Status": status_str}
            response = self._sign_request("SetDomainRecordStatus", params)
            if response.status_code != 200:
                return {"status": False, "msg": response.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}
