#!/bin/python
# coding: utf-8
# +-------------------------------------------------------------------
# | 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2024-08-22
# +-------------------------------------------------------------------
# | EditDate: 2024-08-22
# +-------------------------------------------------------------------
# | Version: 1.0
# +-------------------------------------------------------------------

# ------------------------------
# Redis 类
# ------------------------------
import redis
import threading
from concurrent.futures import ThreadPoolExecutor

class RedisClient:
    _pools = {}
    _clients = {}
    _lock = threading.Lock()
    
    @staticmethod
    def _get_kwargs(*args, **kwargs):
        local = kwargs.get('local', True)
        localOptions = kwargs.get('localOptions', {})
        db_port = kwargs.get('db_port', 6379)
        db_password = kwargs.get('db_password', '')
        db_host = str(kwargs.get('db_host', '127.0.0.1'))
        if local:
            if not localOptions:
                return False
            db_port = int(localOptions['port'])
            db_password = localOptions['requirepass']
            db_host = str("127.0.0.1")
        return {
            'local':local,
            'localOptions':localOptions,
            'db_port':db_port,
            'db_host':db_host,
            'db_password':db_password,
            'db':kwargs.get('db', 0),
            'socket_connect_timeout':kwargs.get('socket_connect_timeout', 10),
            'socket_timeout':kwargs.get('socket_timeout', 5),
            'max_connections':kwargs.get('max_connections', 5)
        }

    @staticmethod
    def get_connection_pool(*args, **kwargs):
        kw = RedisClient._get_kwargs(*args, **kwargs)
        host = kw['db_host']
        db = kw['db']
        key = (host, db)
        if key not in RedisClient._pools:
            RedisClient._pools[key] = redis.ConnectionPool(host=host,port=kw['db_port'],password=kw['db_password'],db=db,socket_connect_timeout=kw['socket_connect_timeout'],socket_timeout=kw['socket_timeout'],max_connections=kw['max_connections'],decode_responses=True)
        return RedisClient._pools[key]
    
    @staticmethod
    def get_client(*args, **kwargs):
        kw = RedisClient._get_kwargs(*args, **kwargs)
        host = kw['db_host']
        db = kw['db']
        key = (host, db)
        try:
            if key not in RedisClient._clients:
                pool = RedisClient.get_connection_pool(*args, **kwargs)
                db_conn = redis.Redis(connection_pool=pool)
                db_conn.ping()
                RedisClient._clients[key] = db_conn
                return db_conn
            else:
                db_conn = RedisClient._clients[key]
                db_conn.ping()
                return db_conn
        except redis.ConnectionError:
            if key in RedisClient._pools:
                del RedisClient._pools[key]
            if key in RedisClient._clients:
                del RedisClient._clients[key]
            return False
        except Exception as e:
            print(f"[error][ruyi] Connect Redis Error:{e}")
            if key in RedisClient._pools:
                del RedisClient._pools[key]
            if key in RedisClient._clients:
                del RedisClient._clients[key]
            return False
        return False
    
    @staticmethod
    def close_all_clients():
        for key, client in RedisClient._clients.items():
            try:
                client.connection_pool.disconnect()
            except:
                pass
        RedisClient._clients.clear()
        RedisClient._pools.clear()

    @staticmethod
    def close_client(*args, **kwargs):
        kw = RedisClient._get_kwargs(*args, **kwargs)
        host = kw['db_host']
        db = kw['db']
        key = (host, db)
        
        if key in RedisClient._clients:
            try:
                client = RedisClient._clients[key]
                client.connection_pool.disconnect()
            except:
                pass
        
        if key in RedisClient._pools:
            del RedisClient._pools[key]
        
        if key in RedisClient._clients:
            del RedisClient._clients[key]
    
    @staticmethod
    def preload_redis_connections(*args, **kwargs):
        kw = RedisClient._get_kwargs(*args, **kwargs)
        host = str(kw['db_host'])
        db_nums = int(kwargs.get('db_nums', 0))
        def preload_db(db):
            key = (host, db)
            with RedisClient._lock:
                if key not in RedisClient._clients:
                    RedisClient.get_client(*args, **kwargs)
        with ThreadPoolExecutor(max_workers=db_nums) as executor:
            executor.map(preload_db, range(db_nums))