#!/usr/bin/env python3
"""
从APNIC官方数据生成中国大陆IP段列表
数据源: https://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-extended-latest
"""
import urllib.request
import os

APNIC_URL = "https://ftp.apnic.net/apnic/stats/apnic/delegated-apnic-extended-latest"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "china_ip_ranges.txt")


def cidr_to_range(ip, prefix):
    """将IP和前缀转换为CIDR表示"""
    return f"{ip}/{prefix}"


def int_to_ip(num):
    """整数转IP地址"""
    return ".".join([str((num >> (8 * i)) & 0xFF) for i in range(3, -1, -1)])


def ip_to_int(ip):
    """IP地址转整数"""
    parts = ip.split(".")
    return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])


def num_to_prefix(num):
    """根据IP数量计算CIDR前缀"""
    if num == 0:
        return 0
    prefix = 32
    while num > 1:
        num //= 2
        prefix -= 1
    return prefix


def download_apnic_data():
    """下载APNIC数据"""
    print(f"正在下载APNIC数据: {APNIC_URL}")
    with urllib.request.urlopen(APNIC_URL, timeout=30) as response:
        return response.read().decode('utf-8')


def parse_apnic_data(data):
    """解析APNIC数据，提取中国大陆IP段"""
    china_ranges = []
    
    for line in data.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split('|')
        if len(parts) < 7:
            continue
        
        registry, cc, type_, start, value, date, status = parts[:7]
        
        if cc != 'CN' or type_ != 'ipv4':
            continue
        
        if status != 'allocated' and status != 'assigned':
            continue
        
        try:
            start_ip = start
            num_ips = int(value)
            
            if num_ips == 0:
                continue
            
            start_int = ip_to_int(start_ip)
            
            while num_ips > 0:
                prefix = num_to_prefix(num_ips)
                block_size = 1 << (32 - prefix)
                
                if block_size > num_ips:
                    prefix += 1
                    block_size = 1 << (32 - prefix)
                    while block_size > num_ips:
                        prefix += 1
                        block_size = 1 << (32 - prefix)
                
                if block_size <= num_ips:
                    ip_str = int_to_ip(start_int)
                    china_ranges.append(f"{ip_str}/{prefix}")
                    start_int += block_size
                    num_ips -= block_size
        except Exception as e:
            print(f"解析错误: {line}, {e}")
            continue
    
    return china_ranges


def merge_ranges(ranges):
    """合并相邻的IP段"""
    def ip_sort_key(cidr):
        ip = cidr.split('/')[0]
        return ip_to_int(ip)
    
    ranges.sort(key=ip_sort_key)
    return ranges


def main():
    print("=" * 50)
    print("从APNIC官方数据生成中国大陆IP段列表")
    print("=" * 50)
    
    data = download_apnic_data()
    print(f"下载完成，数据大小: {len(data)} 字节")
    
    china_ranges = parse_apnic_data(data)
    print(f"解析完成，共 {len(china_ranges)} 个IP段")
    
    china_ranges = merge_ranges(china_ranges)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(china_ranges))
    
    print(f"已保存到: {OUTPUT_FILE}")
    print(f"共 {len(china_ranges)} 条记录")

if __name__ == "__main__":
    main()
