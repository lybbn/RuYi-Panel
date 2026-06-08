import hashlib
import hmac
import json
import datetime
import requests
from .base import DnsProviderBase, extract_zone


class AwsProvider(DnsProviderBase):
    provider_name = "aws"
    provider_display = "AWS"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.access_key = credentials.get('AccessKey', '')
        self.secret_key = credentials.get('SecretKey', '')
        self.region = credentials.get('region', 'us-east-1')
        self.host = "route53.amazonaws.com"
        self.base_url = "https://route53.amazonaws.com/2013-04-01"

    def _sign_request(self, method, path, body=""):
        amz_date = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        date_stamp = datetime.datetime.utcnow().strftime("%Y%m%d")
        payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        canonical_headers = "host:{}\nx-amz-content-sha256:{}\nx-amz-date:{}\n".format(
            self.host, payload_hash, amz_date)
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "{}\n{}\n\n{}\n{}\n{}".format(
            method, path, canonical_headers, signed_headers, payload_hash)
        credential_scope = "{}/{}/route53/aws4_request".format(date_stamp, self.region)
        string_to_sign = "AWS4-HMAC-SHA256\n{}\n{}\n{}".format(
            amz_date, credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest())

        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = sign(("AWS4" + self.secret_key).encode("utf-8"), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, "route53")
        k_signing = sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization_header = "AWS4-HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}".format(
            self.access_key, credential_scope, signed_headers, signature)
        headers = {
            "X-Amz-Date": amz_date,
            "X-Amz-Content-Sha256": payload_hash,
            "Authorization": authorization_header,
            "Content-Type": "application/xml",
        }
        return headers

    def get_domain_list(self):
        try:
            path = "/2013-04-01/hostedzone"
            headers = self._sign_request("GET", path)
            res = requests.get(self.base_url.replace("/2013-04-01", "") + path, headers=headers, timeout=65)
            if res.status_code != 200:
                return {"status": False, "msg": res.text, "data": []}
            import xml.etree.ElementTree as ET
            root = ET.fromstring(res.text)
            ns = {'aws': 'https://route53.amazonaws.com/doc/2013-04-01/'}
            domain_list = []
            for zone in root.findall('aws:HostedZones/aws:HostedZone', ns):
                name = zone.find('aws:Name', ns).text
                zone_id = zone.find('aws:Id', ns).text.replace('/hostedzone/', '')
                domain_list.append({
                    "id": zone_id,
                    "name": name.rstrip('.'),
                    "remark": "",
                    "record_count": int(zone.find('aws:ResourceRecordSetCount', ns).text or 0),
                })
            return {"status": True, "msg": "success", "data": domain_list}
        except Exception as e:
            return {"status": False, "msg": str(e), "data": []}

    def get_dns_record(self, domain_name, **kwargs):
        root_domain, _, sub_domain = extract_zone(domain_name)
        data = {"list": [], "info": {"record_total": 0}}
        try:
            path = "/2013-04-01/hostedzone"
            headers = self._sign_request("GET", path)
            res = requests.get(self.base_url.replace("/2013-04-01", "") + path, headers=headers, timeout=65)
            if res.status_code != 200:
                return data
            import xml.etree.ElementTree as ET
            root = ET.fromstring(res.text)
            ns = {'aws': 'https://route53.amazonaws.com/doc/2013-04-01/'}
            zone_id = None
            for zone in root.findall('aws:HostedZones/aws:HostedZone', ns):
                name = zone.find('aws:Name', ns).text.rstrip('.')
                if name == root_domain:
                    zone_id = zone.find('aws:Id', ns).text.replace('/hostedzone/', '')
                    break
            if not zone_id:
                return data
            record_path = "/2013-04-01/hostedzone/{}/rrset".format(zone_id)
            headers = self._sign_request("GET", record_path)
            res = requests.get(self.base_url.replace("/2013-04-01", "") + record_path, headers=headers, timeout=65)
            if res.status_code != 200:
                return data
            root = ET.fromstring(res.text)
            records = []
            for rrset in root.findall('aws:ResourceRecordSets/aws:ResourceRecordSet', ns):
                rtype = rrset.find('aws:Type', ns).text
                rname = rrset.find('aws:Name', ns).text.rstrip('.')
                ttl_el = rrset.find('aws:TTL', ns)
                ttl = int(ttl_el.text) if ttl_el is not None else 300
                values = []
                for rr in rrset.findall('aws:ResourceRecords/aws:ResourceRecord', ns):
                    val = rr.find('aws:Value', ns).text
                    values.append(val)
                records.append({
                    "RecordId": "{}_{}".format(rname, rtype),
                    "name": rname,
                    "value": values[0] if len(values) == 1 else values,
                    "line": "默认",
                    "ttl": ttl,
                    "type": rtype,
                    "status": "enable",
                    "mx": 0,
                    "updated_on": "",
                    "remark": "",
                })
            data["list"] = records
            data["info"] = {"record_total": len(records)}
        except Exception:
            pass
        return data

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            path = "/2013-04-01/hostedzone"
            headers = self._sign_request("GET", path)
            res = requests.get(self.base_url.replace("/2013-04-01", "") + path, headers=headers, timeout=65)
            if res.status_code != 200:
                return {"status": False, "msg": res.text}
            import xml.etree.ElementTree as ET
            root = ET.fromstring(res.text)
            ns = {'aws': 'https://route53.amazonaws.com/doc/2013-04-01/'}
            zone_id = None
            for zone in root.findall('aws:HostedZones/aws:HostedZone', ns):
                name = zone.find('aws:Name', ns).text.rstrip('.')
                if name == root_domain:
                    zone_id = zone.find('aws:Id', ns).text.replace('/hostedzone/', '')
                    break
            if not zone_id:
                return {"status": False, "msg": "zone not found"}
            fqdn = domain_name + "." if not domain_name.endswith('.') else domain_name
            xml_body = '<?xml version="1.0" encoding="UTF-8"?>'
            xml_body += '<ChangeResourceRecordSetsRequest xmlns="https://route53.amazonaws.com/doc/2013-04-01/">'
            xml_body += '<ChangeBatch><Changes><Change><Action>CREATE</Action>'
            xml_body += '<ResourceRecordSet><Name>{}</Name><Type>{}</Type><TTL>{}</TTL>'.format(
                fqdn, record_type, kwargs.get("ttl", 300))
            if record_type == "MX":
                xml_body += '<ResourceRecords><ResourceRecord><Value>{} {}</Value></ResourceRecord></ResourceRecords>'.format(
                    kwargs.get("mx", 10), value)
            else:
                xml_body += '<ResourceRecords><ResourceRecord><Value>{}</Value></ResourceRecord></ResourceRecords>'.format(value)
            xml_body += '</ResourceRecordSet></Change></Changes></ChangeBatch></ChangeResourceRecordSetsRequest>'
            change_path = "/2013-04-01/hostedzone/{}/rrset/".format(zone_id)
            headers = self._sign_request("POST", change_path, xml_body)
            res = requests.post(
                self.base_url.replace("/2013-04-01", "") + change_path,
                headers=headers, data=xml_body, timeout=65)
            if res.status_code not in [200, 201]:
                return {"status": False, "msg": res.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        return {"status": False, "msg": "AWS Route53 delete requires full record details, use update instead"}

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        root_domain, sub_domain, _ = extract_zone(domain_name)
        try:
            path = "/2013-04-01/hostedzone"
            headers = self._sign_request("GET", path)
            res = requests.get(self.base_url.replace("/2013-04-01", "") + path, headers=headers, timeout=65)
            if res.status_code != 200:
                return {"status": False, "msg": res.text}
            import xml.etree.ElementTree as ET
            root = ET.fromstring(res.text)
            ns = {'aws': 'https://route53.amazonaws.com/doc/2013-04-01/'}
            zone_id = None
            for zone in root.findall('aws:HostedZones/aws:HostedZone', ns):
                name = zone.find('aws:Name', ns).text.rstrip('.')
                if name == root_domain:
                    zone_id = zone.find('aws:Id', ns).text.replace('/hostedzone/', '')
                    break
            if not zone_id:
                return {"status": False, "msg": "zone not found"}
            fqdn = domain_name + "." if not domain_name.endswith('.') else domain_name
            xml_body = '<?xml version="1.0" encoding="UTF-8"?>'
            xml_body += '<ChangeResourceRecordSetsRequest xmlns="https://route53.amazonaws.com/doc/2013-04-01/">'
            xml_body += '<ChangeBatch><Changes>'
            xml_body += '<Change><Action>DELETE</Action><ResourceRecordSet><Name>{}</Name><Type>{}</Type><TTL>{}</TTL>'.format(
                fqdn, record_type, kwargs.get("ttl", 300))
            xml_body += '<ResourceRecords><ResourceRecord><Value>{}</Value></ResourceRecord></ResourceRecords>'.format(
                kwargs.get("old_value", value))
            xml_body += '</ResourceRecordSet></Change>'
            xml_body += '<Change><Action>CREATE</Action><ResourceRecordSet><Name>{}</Name><Type>{}</Type><TTL>{}</TTL>'.format(
                fqdn, record_type, kwargs.get("ttl", 300))
            if record_type == "MX":
                xml_body += '<ResourceRecords><ResourceRecord><Value>{} {}</Value></ResourceRecord></ResourceRecords>'.format(
                    kwargs.get("mx", 10), value)
            else:
                xml_body += '<ResourceRecords><ResourceRecord><Value>{}</Value></ResourceRecord></ResourceRecords>'.format(value)
            xml_body += '</ResourceRecordSet></Change>'
            xml_body += '</Changes></ChangeBatch></ChangeResourceRecordSetsRequest>'
            change_path = "/2013-04-01/hostedzone/{}/rrset/".format(zone_id)
            headers = self._sign_request("POST", change_path, xml_body)
            res = requests.post(
                self.base_url.replace("/2013-04-01", "") + change_path,
                headers=headers, data=xml_body, timeout=65)
            if res.status_code not in [200, 201]:
                return {"status": False, "msg": res.text}
            return {"status": True, "msg": "success"}
        except Exception as e:
            return {"status": False, "msg": str(e)}

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        return {"status": False, "msg": "AWS Route53 does not support pausing individual records"}
