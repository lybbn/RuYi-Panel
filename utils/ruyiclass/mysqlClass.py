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
# Mysql 类
# ------------------------------
import MySQLdb

class MysqlClient:
    _clients = {}
    
    @staticmethod
    def _get_kwargs(*args, **kwargs):
        local = kwargs.get('local', True)
        db_port = kwargs.get('db_port', 3306)
        db_password = kwargs.get('db_password', '')
        db_host = str(kwargs.get('db_host', '127.0.0.1'))
        db_user = str(kwargs.get('db_user', ''))
        db_name = str(kwargs.get('db_name', ''))
        charset = kwargs.get('charset', 'utf8mb4')
        connect_timeout = int(kwargs.get('connect_timeout', 3))
        return {
            'local':local,
            'db_port':db_port,
            'db_host':db_host,
            'db_password':db_password,
            'db_name':db_name,
            'db_user':db_user,
            'charset':charset,
            'connect_timeout':connect_timeout
        }
    
    @staticmethod
    def get_client(*args, **kwargs):
        kw = MysqlClient._get_kwargs(*args, **kwargs)
        host = kw['db_host']
        port = kw['db_port']
        user = kw['db_user']
        db = kw['db_name']
        key = (host,port,user,db)
        try:
            if key not in MysqlClient._clients:
                db_conn = MySQLdb.connect(host=host,user=user,passwd=kw['db_password'],port=port,db=db,charset=kw['charset'],connect_timeout=kw['connect_timeout'])
                # MysqlClient._clients[key] = db_conn
                MysqlClient._clients[key] = MySQLClientOperate(db_conn,key)
                return MysqlClient._clients[key]
            else:
                db_conn = MysqlClient._clients[key]
                return db_conn
        except Exception as e:
            print(f"[error][ruyi] Connect Mysql Error:{e}")
            if key in MysqlClient._clients:
                del MysqlClient._clients[key]
            return False

    @staticmethod
    def close_all_clients():
        for key, client in MysqlClient._clients.items():
            try:
                client.close()
            except:
                pass
        MysqlClient._clients.clear()

    @staticmethod
    def close_client(*args, **kwargs):
        kw = MysqlClient._get_kwargs(*args, **kwargs)
        host = kw['db_host']
        port = kw['db_port']
        user = kw['db_user']
        db = kw['db_name']
        key = (host,port,user,db)
        
        if key in MysqlClient._clients:
            try:
                client = MysqlClient._clients[key]
                client.close()
            except:
                pass
        if key in MysqlClient._clients:
            del MysqlClient._clients[key]

class MySQLClientOperate:
    def __init__(self,connection,key):
        self.connection = connection
        self.key = key
        
    def filter(self,sqlstr,is_map_list=True,close_cursor=True,close_conn = False):
        """
        执行SQL语句返回数据集
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(sqlstr)
            results = cursor.fetchall()
            if is_map_list:
                data = list(map(list,results))
                return data
            return results
        except Exception as e:
            return e
        finally:
            self.close(cursor=cursor,close_cursor=close_cursor,close_conn=close_conn)
                
    def execute(self,sqlstr,close_cursor=True,close_conn = False):
        """
        执行SQL语句返回受影响行
        """
        cursor = self.connection.cursor()
        try:
            result = cursor.execute(sqlstr)
            self.connection.commit()
            return result
        except Exception as e:
            return e
        finally:
            self.close(cursor=cursor,close_cursor=close_cursor,close_conn=close_conn)
        
    def close(self,cursor=None,close_cursor=True,close_conn=True):
        """
        资源释放
        """
        try:
            if close_cursor and cursor:
                cursor.close()
            if close_conn:
                self.connection.close()
                del MysqlClient._clients[self.key]
        except:
            pass
        