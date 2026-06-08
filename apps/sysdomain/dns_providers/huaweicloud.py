import json
import copy
import sys
import hashlib
import hmac
import binascii
from datetime import datetime
import requests
from .base import DnsProviderBase, extract_zone


class HuaweiCloudProvider(DnsProviderBase):
    provider_name = "huaweicloud"
    provider_display = "华为云"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.ak = credentials.get('AccessKey', '')
        self.sk = credentials.get('SecretKey', '')
        self.project_id = credentials.get('project_id', '')
        self.url = "https://dns.cn-north-1.myhuaweicloud.com"
        self.BasicDateFormat = "%Y%m%dT%H%M%SZ"
        self.Algorithm = "SDK-HMAC-SHA256"

    def _sign_request(self, method, path, headers=None, body=""):
        url = self.url + path
        if sys.version_info.major >= 3:
            body = body.encode("utf-8") if isinstance(body, str) else body
            from urllib.parse import quote, unquote

            def hmacsha256(keyByte, message):
                return hmac.new(keyByte.encode('utf-8'), message.encode('utf-8'), digestmod=hashlib.sha256).digest()
        else:
            from urllib import quote, unquote

            def hmacsha256(keyByte, message):
                return hmac.new(keyByte, message, digestmod=hashlib.sha256).digest()

        def HexEncodeSHA256Hash(data):
            sha256 = hashlib.sha256()
            sha256.update(data)
            return sha256.hexdigest()

        def findHeader(hdrs, header):
            for k in hdrs:
                if k.lower() == header.lower():
                    return hdrs[k]
            return None

        def CanonicalQueryString(query):
            keys = sorted(query.keys())
            a = []
            for key in keys:
                k = quote(key, safe='~')
                value = query[key]
                if isinstance(value, list):
                    value.sort()
                    for v in value:
                        a.append(k + "=" + quote(str(v), safe='~'))
                else:
                    a.append(k + "=" + quote(str(value), safe='~'))
            return '&'.join(a)

        def SignStringToSign(stringToSign, signingKey):
            hm = hmacsha256(signingKey, stringToSign)
            return binascii.hexlify(hm).decode()

        def AuthHeaderValue(signature, AppKey, signedHeaders):
            return "%s Access=%s, SignedHeaders=%s, Signature=%s" % (
                self.Algorithm, AppKey, ";".join(signedHeaders), signature)

        spl = url.split("://", 1)
        scheme = 'http'
        if len(spl) > 1:
            scheme = spl[0]
            url = spl[1]
        query = {}
        spl = url.split('?', 1)
        url = spl[0]
        if len(spl) > 1:
            for kv in spl[1].split("&"):
                spl2 = kv.split("=", 1)
                key = spl2[0]
                value = ""
                if len(spl2) > 1:
                    value = spl2[1]
                if key != '':
                    key = unquote(key)
                    value = unquote(value)
                    query[key] = [value]
        spl = url.split('/', 1)
        host = spl[0]
        if len(spl) > 1:
            url = '/' + spl[1]
        else:
            url = '/'
        if headers is None:
            headers = {"content-type": "application/json"}
        else:
            headers = copy.deepcopy(headers)
        headerTime = findHeader(headers, "X-Sdk-Date")
        if headerTime is None:
            t = datetime.utcnow()
            headers["X-Sdk-Date"] = datetime.strftime(t, self.BasicDateFormat)
        else:
            t = datetime.strptime(headerTime, self.BasicDateFormat)
        haveHost = False
        for key in headers:
            if key.lower() == 'host':
                haveHost = True
                break
        if not haveHost:
            headers["host"] = host
        signedHeaders = sorted([key.lower() for key in headers])
        a = []
        __headers = {}
        for key in headers:
            keyEncoded = key.lower()
            value = headers[key]
            valueEncoded = value.strip()
            __headers[keyEncoded] = valueEncoded
        for key in signedHeaders:
            a.append(key + ":" + __headers[key])
        canonicalHeaders = '\n'.join(a) + "\n"
        hexencode = HexEncodeSHA256Hash(body)
        from urllib.parse import quote as up_quote
        pattens = unquote(url).split('/')
        CanonicalURI = [up_quote(v, safe="~") for v in pattens]
        CanonicalURL = "/".join(CanonicalURI)
        if CanonicalURL[-1] != '/':
            CanonicalURL = CanonicalURL + "/"
        canonicalRequest = "%s\n%s\n%s\n%s\n%s\n%s" % (
            method.upper(), CanonicalURL, CanonicalQueryString(query),
            canonicalHeaders, ";".join(signedHeaders), hexencode)
        stringToSign = "%s\n%s\n%s" % (self.Algorithm, datetime.strftime(t, self.BasicDateFormat),
                                        HexEncodeSHA256Hash(canonicalRequest.encode('utf-8')))
        signature = SignStringToSign(stringToSign, self.sk)
        authValue = AuthHeaderValue(signature, self.ak, signedHeaders)
        headers["Authorization"] = authValue
        headers["content-length"] = str(len(body))
        queryString = CanonicalQueryString(query)
        if queryString != "":
            url = url + "?" + queryString
        res = requests.request(method, scheme + "://" + host + url, headers=headers, data=body)
        return res

    def _get_zone_id_dict(self):
        res = self._sign_request("GET", "/v2/zones")
        if res.status_code != 200:
            return {}
        response = res.json()
        return {i["name"][:-1]: i["id"] for i in response.get("zones", [])}

    def get_domain_list(self):
        try:
            res = self._sign_request("GET", "/v2/zones")
            if res.status_code != 200:
                return {"status": False, "msg": res.text, "data": []}
            response = res.json()
            domain_list = [
                {
                    "id": i["id"],
                    "name": i["name"][:-1],
                    "remark": i.get("description") or "",
                    "record_count": i.get("record_num") or 0,
                }
                for i in response.get("zones", [])
            ]
            return {"status": True, "msg": "success", "data": domain_list}
        except Exception as e:
            return {"status": False, "msg": str(e), "data": []}

    def get_dns_record(self, domain_name, **kwargs):
        root_domain, _, sub_domain = extract_zone(domain_name)
        data = {"list": [], "info": {"record_total": 0}}
        try:
            zone_dic = self._get_zone_id_dict()
            zone_id = zone_dic.get(root_domain)
            if not zone_id:
                return data
            limit = int(kwargs.get("limit", 100))
            offset = 0
            if kwargs.get("page"):
                offset = ((int(kwargs["page"]) - 1) * limit)
            url = "/v2.1/zones/{}/recordsets?limit={}&offset={}".format(zone_id, limit, offset)
            if kwargs.get("search"):
                url = url + "&name={}".format(kwargs["search"])
            res = self._sign_request("GET", url)
            if res.status_code != 200:
                return data
            response = res.json()
            line_type_dict = {
                "default_view": "默认", "Dianxin": "电信", "Liantong": "联通",
                "Yidong": "移动", "Jiaoyuwang": "教育网", "Tietong": "铁通",
            }
            data["list"] = [
                {
                    "RecordId": i["id"],
                    "name": i["name"][:-1] if i["name"].endswith(".") else i["name"],
                    "value": i["records"],
                    "line": line_type_dict.get(i.get("line", ""), "其它"),
                    "ttl": i["ttl"],
                    "type": i["type"],
                    "status": "enable" if i["status"] == "ACTIVE" else "disable",
                    "weight": i.get("weight", "-") or "-",
                    "updated_on": i.get("update_at", ""),
                    "remark": i.get("description") or "",
                }
                for i in response.get("recordsets", [])
            ]
            data["info"] = {"record_total": response.get('metadata', {}).get('total_count', 0)}
        except Exception:
            pass
        return data

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            records = json.loads(value) if value.startswith('[') else [value]
        except Exception:
            records = [value]
        remark = kwargs.get("remark", "")
        if record_type == 'MX':
            mx = kwargs.get('mx', 10)
            records = ["{} {}".format(mx, r) if not r.split(' ')[0].isdigit() else r for r in records]
        try:
            zone_dic = self._get_zone_id_dict()
            zone_id = zone_dic.get(root_domain)
            if not zone_id:
                return {"status": False, "msg": "domain zone not found"}
            body = json.dumps({
                "name": domain_name if sub_domain else root_domain,
                "type": record_type,
                "records": records,
                "description": remark,
                "ttl": kwargs.get("ttl", 300),
                "line": kwargs.get("record_line", "default_view"),
            })
            res = self._sign_request("POST", "/v2.1/zones/{}/recordsets".format(zone_id), body=body)
            if res.status_code != 202:
                return {"status": False, "msg": res.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        root_domain, _, _ = extract_zone(domain_name)
        try:
            zone_dic = self._get_zone_id_dict()
            zone_id = zone_dic.get(root_domain)
            if not zone_id:
                return {"status": False, "msg": "domain zone not found"}
            res = self._sign_request("DELETE", "/v2.1/zones/{}/recordsets/{}".format(zone_id, record_id))
            if res.status_code != 202:
                return {"status": False, "msg": res.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            records = json.loads(value) if value.startswith('[') else [value]
        except Exception:
            records = [value]
        remark = kwargs.get("remark", "")
        if record_type == 'MX':
            mx = kwargs.get('mx', 10)
            records = ["{} {}".format(mx, r) if not r.split(' ')[0].isdigit() else r for r in records]
        try:
            zone_dic = self._get_zone_id_dict()
            zone_id = zone_dic.get(root_domain)
            if not zone_id:
                return {"status": False, "msg": "domain zone not found"}
            body = json.dumps({
                "name": domain_name if sub_domain else root_domain,
                "type": record_type,
                "records": records,
                "description": remark,
                "ttl": kwargs.get("ttl", 300),
                "line": kwargs.get("record_line", "default_view"),
            })
            res = self._sign_request("PUT", "/v2.1/zones/{}/recordsets/{}".format(zone_id, record_id), body=body)
            if res.status_code != 202:
                return {"status": False, "msg": res.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        root_domain, _, _ = extract_zone(domain_name)
        status_str = "DISABLE" if int(status) else "ENABLE"
        try:
            zone_dic = self._get_zone_id_dict()
            zone_id = zone_dic.get(root_domain)
            if not zone_id:
                return {"status": False, "msg": "domain zone not found"}
            body = json.dumps({"status": status_str})
            res = self._sign_request("PUT", "/v2.1/zones/{}/recordsets/{}/statuses/set".format(zone_id, record_id), body=body)
            if res.status_code != 202:
                return {"status": False, "msg": res.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}
