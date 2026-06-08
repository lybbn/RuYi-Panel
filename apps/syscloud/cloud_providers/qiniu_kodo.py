from .base import CloudStorageBase


class QiniuKodoProvider(CloudStorageBase):
    provider_name = "qiniu_kodo"
    provider_display = "七牛云 Kodo"
    protocol = "native"

    def __init__(self, account):
        super().__init__(account)
        self._auth = None
        self._bucket_manager = None

    def _get_auth(self):
        if self._auth is not None:
            return self._auth
        import qiniu
        self._auth = qiniu.Auth(self.access_key, self.secret_key)
        return self._auth

    def _get_bucket_manager(self):
        if self._bucket_manager is not None:
            return self._bucket_manager
        import qiniu
        auth = self._get_auth()
        self._bucket_manager = qiniu.BucketManager(auth)
        return self._bucket_manager

    def test_connection(self):
        try:
            bm = self._get_bucket_manager()
            ret, info = bm.bucket(self.bucket)
            if info.status_code == 200:
                return True, "连接成功，存储桶可访问"
            elif info.status_code == 401:
                return False, "AccessKey无权限，请检查密钥配置"
            elif info.status_code == 612:
                return False, "存储桶不存在"
            return False, "连接失败: {}".format(str(info)[:200])
        except Exception as e:
            return False, "连接失败: {}".format(str(e)[:200])

    def list_buckets(self):
        try:
            import qiniu
            auth = self._get_auth()
            buckets = qiniu.list_bucket(auth)
            result = []
            for b in buckets:
                result.append({'name': b, 'create_time': ''})
            return True, result
        except Exception as e:
            return False, "获取存储桶列表失败: {}".format(str(e)[:200])

    def list_objects(self, prefix="", delimiter="/", max_keys=200):
        try:
            bm = self._get_bucket_manager()
            delimiter_char = delimiter if delimiter else '/'
            ret, eof, info = bm.list(
                self.bucket, prefix=prefix,
                limit=max_keys, delimiter=delimiter_char,
            )
            result = []
            for p in ret.get('commonPrefixes', []):
                display_name = p.rstrip('/').split('/')[-1]
                result.append({
                    'key': p,
                    'name': display_name,
                    'size': 0,
                    'is_dir': True,
                    'last_modified': '',
                })
            for obj in ret.get('items', []):
                key = obj.get('key', '')
                if key == prefix:
                    continue
                display_name = key.split('/')[-1] if '/' in key else key
                if not display_name:
                    continue
                result.append({
                    'key': key,
                    'name': display_name,
                    'size': obj.get('fsize', 0),
                    'is_dir': False,
                    'last_modified': self._format_time(obj.get('putTime', 0)),
                })
            return True, result
        except Exception as e:
            return False, "获取文件列表失败: {}".format(str(e)[:200])

    def _format_time(self, put_time):
        try:
            if not put_time:
                return ''
            import time
            ts = put_time / 10000000
            return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
        except Exception:
            return ''

    def upload_file(self, local_path, remote_path):
        try:
            import qiniu
            auth = self._get_auth()
            token = auth.upload_token(self.bucket, remote_path)
            ret, info = qiniu.put_file(token, remote_path, local_path)
            if info.status_code == 200:
                return True, "上传成功"
            return False, "上传失败: {}".format(str(info)[:200])
        except Exception as e:
            return False, "上传失败: {}".format(str(e)[:200])

    def download_file(self, remote_path, local_path):
        try:
            import qiniu
            auth = self._get_auth()
            domain = self.extra_config.get('domain', '')
            if not domain:
                return False, "请先在扩展配置中设置域名(domain)"
            if not domain.startswith('http'):
                domain = 'http://' + domain
            base_url = '{}/{}'.format(domain.rstrip('/'), remote_path)
            private_url = auth.private_download_url(base_url, expires=3600)
            import requests
            resp = requests.get(private_url, stream=True, timeout=300)
            if resp.status_code == 200:
                with open(local_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True, "下载成功"
            return False, "下载失败: HTTP {}".format(resp.status_code)
        except Exception as e:
            return False, "下载失败: {}".format(str(e)[:200])

    def delete_file(self, remote_path):
        try:
            bm = self._get_bucket_manager()
            ret, info = bm.delete(self.bucket, remote_path)
            if info.status_code in (200, 612):
                return True, "删除成功"
            return False, "删除失败: {}".format(str(info)[:200])
        except Exception as e:
            return False, "删除失败: {}".format(str(e)[:200])

    def create_dir(self, remote_path):
        try:
            if not remote_path.endswith('/'):
                remote_path += '/'
            import qiniu
            auth = self._get_auth()
            token = auth.upload_token(self.bucket, remote_path)
            ret, info = qiniu.put(token, remote_path, b'')
            if info.status_code == 200:
                return True, "创建目录成功"
            return False, "创建目录失败: {}".format(str(info)[:200])
        except Exception as e:
            return False, "创建目录失败: {}".format(str(e)[:200])

    def get_file_url(self, remote_path, expires=3600):
        try:
            import qiniu
            auth = self._get_auth()
            domain = self.extra_config.get('domain', '')
            if not domain:
                return False, "请先在扩展配置中设置域名(domain)"
            if not domain.startswith('http'):
                domain = 'http://' + domain
            base_url = '{}/{}'.format(domain.rstrip('/'), remote_path)
            private_url = auth.private_download_url(base_url, expires=expires)
            return True, private_url
        except Exception as e:
            return False, "获取URL失败: {}".format(str(e)[:200])

    def get_bucket_usage(self):
        try:
            bm = self._get_bucket_manager()
            used_size = 0
            total_count = 0
            marker = None
            while True:
                ret, info = bm.list(self.bucket, None, marker, 1000, None)
                if info.status_code == 200 and 'items' in ret:
                    for item in ret['items']:
                        used_size += item.get('fsize', 0)
                        total_count += 1
                if ret.get('marker'):
                    marker = ret['marker']
                else:
                    break
            return True, {
                'used_size': used_size,
                'total_count': total_count,
                'total_quota': 0,
            }
        except Exception as e:
            return False, "获取用量失败: {}".format(str(e)[:200])

    def copy_file(self, src_path, dst_path):
        try:
            bm = self._get_bucket_manager()
            ret, info = bm.copy(self.bucket, src_path, self.bucket, dst_path)
            if info.status_code == 200:
                return True, "复制成功"
            return False, "复制失败: {}".format(str(info)[:200])
        except Exception as e:
            return False, "复制失败: {}".format(str(e)[:200])

    def file_exists(self, remote_path):
        try:
            bm = self._get_bucket_manager()
            ret, info = bm.stat(self.bucket, remote_path)
            if info.status_code == 200:
                return True, "文件存在"
            return False, "文件不存在"
        except Exception:
            return False, "文件不存在"

    def get_file_info(self, remote_path):
        try:
            bm = self._get_bucket_manager()
            ret, info = bm.stat(self.bucket, remote_path)
            if info.status_code == 200:
                return True, {
                    'key': remote_path,
                    'size': ret.get('fsize', 0),
                    'last_modified': self._format_time(ret.get('putTime', 0)),
                    'content_type': ret.get('mimeType', ''),
                    'etag': ret.get('hash', ''),
                }
            return False, "获取文件信息失败"
        except Exception as e:
            return False, "获取文件信息失败: {}".format(str(e)[:200])
