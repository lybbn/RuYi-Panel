#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板 RUYI
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-07-03
# +-------------------------------------------------------------------

# ------------------------------
# IP 归属地
# ------------------------------

import os
import ipaddress
import json
import time
import threading
from qqwry import QQwry
from django.conf import settings
from utils.security.files import download_url_file

class IPCache:
    _instance = None
    _lock = threading.Lock()
    CACHE_DIR = os.path.join(settings.BASE_DIR, 'data', 'cache') if hasattr(settings, 'BASE_DIR') else None
    CACHE_FILE = None
    CACHE_EXPIRE_DAYS = 30
    _cache = {}
    _dirty = False
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._init_cache()
        return cls._instance
    
    @classmethod
    def _init_cache(cls):
        if cls._initialized:
            return
        cls.CACHE_DIR = os.path.join(settings.BASE_DIR, 'data', 'cache')
        cls.CACHE_FILE = os.path.join(cls.CACHE_DIR, 'ip_location.json')
        cls._cache = {}
        cls._dirty = False
        cls._load()
        cls._initialized = True
    
    @classmethod
    def _load(cls):
        try:
            if cls.CACHE_FILE and os.path.exists(cls.CACHE_FILE):
                with open(cls.CACHE_FILE, 'r', encoding='utf-8') as f:
                    cls._cache = json.load(f)
        except:
            cls._cache = {}
    
    @classmethod
    def _save(cls):
        if not cls._dirty:
            return
        try:
            os.makedirs(cls.CACHE_DIR, exist_ok=True)
            with open(cls.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cls._cache, f, ensure_ascii=False, indent=2)
            cls._dirty = False
        except Exception as e:
            print(f"[IPCache] 保存缓存失败: {e}")
    
    @classmethod
    def get(cls, ip):
        data = cls._cache.get(ip)
        if not data:
            return None
        if time.time() - data.get('ts', 0) > cls.CACHE_EXPIRE_DAYS * 86400:
            del cls._cache[ip]
            cls._dirty = True
            return None
        return data
    
    @classmethod
    def set(cls, ip, location, **kwargs):
        cls._cache[ip] = {
            'location': location,
            'ts': time.time(),
            **kwargs
        }
        cls._dirty = True
        if len(cls._cache) % 100 == 0:
            cls._save()
    
    @classmethod
    def flush(cls):
        cls._save()

def is_valid_ipv4(ip):
    '''
    @name 是否有效的ipv4地址
    @author lybbn
    @date 2024-07-18
    @param ip地址
    @return True、False
    '''
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ipaddress.AddressValueError:
        return False

class IPQQwry:
    _instance = None
    _qqwry = None
    _loaded = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(IPQQwry, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    @classmethod
    def _load_qqwry(cls):
        if cls._loaded:
            return cls._qqwry is not None
        try:
            cls._qqwry = QQwry()
            QQWRY_FILE_PATH = os.path.join(settings.BASE_DIR,'qqwry.dat')
            if not os.path.exists(QQWRY_FILE_PATH):
                isok, msg = download_url_file("https://gitee.com/lybbn/RuYi-Panel/releases/download/v1.0.5/qqwry.dat", save_path=QQWRY_FILE_PATH)
                if not isok:
                    print(f"[IPQQwry] 下载qqwry.dat失败: {msg}")
                    cls._loaded = True
                    return False
            result = cls._qqwry.load_file(QQWRY_FILE_PATH)
            if result:
                cls._loaded = True
                return True
            else:
                print(f"[IPQQwry] 加载qqwry.dat失败")
                cls._loaded = True
                return False
        except Exception as e:
            print(f"[IPQQwry] 初始化失败: {e}")
            cls._loaded = True
            return False

    @staticmethod
    def get_local_ips_area(ip_list):
        '''
        @name 本地离线获取ip地址归属地(第一次会触发下载离线库-文件太大20M左右)
        @author lybbn
        @date 2024-07-18
        @param ip_list 类型list ['x.x.x.x']
        @return list ['国家–省份–市')] 处理后 
        '''
        results = []
        cache = IPCache()
        need_query = []
        query_indices = []
        
        for i, ip in enumerate(ip_list):
            cached = cache.get(ip)
            if cached and cached.get('location'):
                results.append(cached['location'])
            else:
                results.append(None)
                need_query.append(ip)
                query_indices.append(i)
        
        if need_query and IPQQwry._load_qqwry():
            try:
                for idx, ip in zip(query_indices, need_query):
                    if is_valid_ipv4(ip):
                        result = IPQQwry._qqwry.lookup(ip)
                        location = result[0] if result else ""
                        results[idx] = location
                        if location:
                            cache.set(ip, location)
                    else:
                        results[idx] = ""
            except Exception as e:
                print(f"[IPQQwry] 查询IP归属地失败: {e}")
                for idx in query_indices:
                    if results[idx] is None:
                        results[idx] = ""
        else:
            for i in range(len(results)):
                if results[i] is None:
                    results[i] = ""
        
        return results

    def lookup(self, ip):
        '''
        @name 查询单个IP的归属地
        @author lybbn
        @param ip IP地址
        @return str 归属地字符串
        '''
        cache = IPCache()
        cached = cache.get(ip)
        if cached and cached.get('location'):
            return cached['location']
        if not IPQQwry._load_qqwry():
            return ""
        try:
            if is_valid_ipv4(ip):
                result = IPQQwry._qqwry.lookup(ip)
                location = result[0] if result else ""
                if location:
                    cache.set(ip, location)
                return location
            return ""
        except Exception as e:
            print(f"[IPQQwry] 查询IP归属地失败: {e}")
            return ""


class GeoIP2Lookup:
    '''
    @name GeoIP2 IP地理位置查询（支持经纬度）
    @author lybbn
    '''
    _instance = None
    _reader = None
    _loaded = False
    
    GEOLITE2_DOWNLOAD_URL = "https://git.io/GeoLite2-City.mmdb"
    GEOLITE2_MIRROR_URL = "https://gitee.com/lybbn/RuYi-Panel/releases/download/v1.0.9/GeoLite2-City.mmdb"
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GeoIP2Lookup, cls).__new__(cls, *args, **kwargs)
        return cls._instance
    
    @classmethod
    def _load_database(cls):
        if cls._loaded:
            return cls._reader is not None
        try:
            import geoip2.database
            GEOLITE2_PATH = os.path.join(settings.BASE_DIR, 'GeoLite2-City.mmdb')
            if not os.path.exists(GEOLITE2_PATH):
                isok, msg = download_url_file(cls.GEOLITE2_MIRROR_URL, save_path=GEOLITE2_PATH)
                if not isok:
                    print(f"[GeoIP2] 下载GeoLite2-City.mmdb失败: {msg}")
                    cls._loaded = True
                    return False
            cls._reader = geoip2.database.Reader(GEOLITE2_PATH)
            cls._loaded = True
            return True
        except ImportError:
            print("[GeoIP2] geoip2库未安装，请运行: pip install geoip2")
            cls._loaded = True
            return False
        except Exception as e:
            print(f"[GeoIP2] 初始化失败: {e}")
            cls._loaded = True
            return False
    
    @classmethod
    def lookup(cls, ip):
        '''
        @name 查询IP地理位置信息（包含经纬度）
        @param ip IP地址
        @return dict {country, province, city, latitude, longitude, location}
        '''
        result = {
            'country': '',
            'province': '',
            'city': '',
            'latitude': None,
            'longitude': None,
            'location': ''
        }
        cache = IPCache()
        cached = cache.get(ip)
        if cached and cached.get('location') and 'latitude' in cached:
            return {
                'country': cached.get('country', ''),
                'province': cached.get('province', ''),
                'city': cached.get('city', ''),
                'latitude': cached.get('latitude'),
                'longitude': cached.get('longitude'),
                'location': cached.get('location', '')
            }
        if not cls._load_database():
            return result
        try:
            response = cls._reader.city(ip)
            result['country'] = response.country.names.get('zh-CN', response.country.names.get('en', ''))
            province = response.subdivisions.most_specific if response.subdivisions else None
            result['province'] = province.names.get('zh-CN', province.names.get('en', '')) if province else ''
            result['city'] = response.city.names.get('zh-CN', response.city.names.get('en', ''))
            result['latitude'] = response.location.latitude
            result['longitude'] = response.location.longitude
            location_parts = [result['country'], result['province'], result['city']]
            result['location'] = ' '.join(filter(None, location_parts))
            if result['location']:
                cache.set(ip, result['location'], 
                         country=result['country'],
                         province=result['province'],
                         city=result['city'],
                         latitude=result['latitude'],
                         longitude=result['longitude'])
            return result
        except Exception as e:
            return result
    
    @classmethod
    def get_coordinates(cls, ip):
        '''
        @name 获取IP的经纬度坐标
        @param ip IP地址
        @return tuple (longitude, latitude) 或 None
        '''
        data = cls.lookup(ip)
        if data['latitude'] is not None and data['longitude'] is not None:
            return (data['longitude'], data['latitude'])
        return None
    
    @classmethod
    def close(cls):
        if cls._reader:
            cls._reader.close()
            cls._reader = None


def get_ip_location_with_coords(ip):
    '''
    @name 获取IP归属地和经纬度（优先使用GeoIP2，降级使用qqwry）
    @param ip IP地址
    @return dict {location, latitude, longitude}
    '''
    result = {
        'location': '',
        'latitude': None,
        'longitude': None
    }
    try:
        geoip_result = GeoIP2Lookup.lookup(ip)
        if geoip_result['location']:
            result['location'] = geoip_result['location']
            result['latitude'] = geoip_result['latitude']
            result['longitude'] = geoip_result['longitude']
            return result
    except:
        pass
    try:
        result['location'] = IPQQwry().lookup(ip)
    except:
        pass
    return result


def get_server_location():
    '''
    @name 获取服务器所在位置（从public_ip.ry文件读取外网IP）
    @return dict {ip, location, latitude, longitude}
    '''
    result = {
        'ip': '',
        'location': '',
        'latitude': None,
        'longitude': None
    }
    try:
        public_ip_file = os.path.join(settings.BASE_DIR, 'data', 'public_ip.ry')
        if os.path.exists(public_ip_file):
            with open(public_ip_file, 'r') as f:
                result['ip'] = f.read().strip()
        if result['ip']:
            location_data = get_ip_location_with_coords(result['ip'])
            result['location'] = location_data['location']
            result['latitude'] = location_data['latitude']
            result['longitude'] = location_data['longitude']
    except Exception as e:
        print(f"[get_server_location] 获取服务器位置失败: {e}")
    return result

import atexit
atexit.register(lambda: IPCache.flush())


