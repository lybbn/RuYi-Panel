import re

TOP_DOMAIN_LIST = [
    '.com.cn', '.net.cn', '.org.cn', '.gov.cn', '.edu.cn',
    '.ac.cn', '.ah.cn', '.bj.cn', '.cq.cn', '.fj.cn', '.gd.cn',
    '.gs.cn', '.gx.cn', '.gz.cn', '.ha.cn', '.hb.cn', '.he.cn',
    '.hi.cn', '.hk.cn', '.hl.cn', '.hn.cn', '.jl.cn', '.js.cn',
    '.jx.cn', '.ln.cn', '.mo.cn', '.nm.cn', '.nx.cn', '.qhl.cn',
    '.sc.cn', '.sd.cn', '.sh.cn', '.sn.cn', '.sx.cn', '.tj.cn',
    '.tw.cn', '.xj.cn', '.xz.cn', '.yn.cn', '.zj.cn',
    '.co.uk', '.co.jp', '.co.kr', '.co.in', '.com.au', '.com.br',
    '.com.hk', '.com.tw', '.com.sg', '.com.my', '.co.nz',
]


def extract_zone(domain_name):
    domain_name = domain_name.lstrip("*.")
    domain_split = domain_name.split('.')
    if len(domain_split) <= 2:
        root, sub = domain_name, ""
    else:
        root, sub = ".".join(domain_split[-2:]), ".".join(domain_split[:-2])
        for i in range(len(domain_split)):
            suffix = "." + ".".join(domain_split[i:])
            if suffix in TOP_DOMAIN_LIST:
                root = ".".join(domain_split[i - 1:])
                sub = ".".join(domain_split[:i - 1])
                break
    acme_txt = "_acme-challenge.%s" % sub if sub else "_acme-challenge"
    return root, sub, acme_txt


class DnsProviderBase:
    provider_name = ""
    provider_display = ""

    def __init__(self, credentials):
        self.credentials = credentials

    def get_domain_list(self):
        raise NotImplementedError

    def get_dns_record(self, domain_name, **kwargs):
        raise NotImplementedError

    def create_dns_record(self, domain_name, record_type, value, **kwargs):
        raise NotImplementedError

    def delete_dns_record(self, domain_name, record_id, **kwargs):
        raise NotImplementedError

    def update_dns_record(self, domain_name, record_id, record_type, value, **kwargs):
        raise NotImplementedError

    def set_dns_record_status(self, domain_name, record_id, status, **kwargs):
        raise NotImplementedError
