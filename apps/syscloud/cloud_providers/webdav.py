from .base import CloudStorageBase


class WebDAVProvider(CloudStorageBase):
    provider_name = "webdav"
    provider_display = "WebDAV"
    protocol = "webdav"

    def __init__(self, account):
        super().__init__(account)
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        from webdav3.client import Client

        options = {
            'webdav_hostname': self.endpoint,
            'webdav_login': self.access_key,
            'webdav_password': self.secret_key,
        }
        options.update(self.extra_config)
        self._client = Client(options)
        return self._client

    def test_connection(self):
        try:
            client = self._get_client()
            client.list()
            return True, "连接成功"
        except Exception as e:
            return False, "连接失败: {}".format(str(e)[:200])

    def list_buckets(self):
        return True, []

    def list_objects(self, prefix="", delimiter="/", max_keys=200):
        try:
            client = self._get_client()
            path = prefix if prefix else '/'
            items = client.list(path)
            result = []
            for item in items:
                name = item.rstrip('/').split('/')[-1] if '/' in item else item
                if not name:
                    continue
                is_dir = item.endswith('/')
                item_path = item if item.startswith('/') else path.rstrip('/') + '/' + item
                result.append({
                    'key': item_path,
                    'name': name,
                    'size': 0,
                    'is_dir': is_dir,
                    'last_modified': '',
                })
            return True, result
        except Exception as e:
            return False, "获取文件列表失败: {}".format(str(e)[:200])

    def upload_file(self, local_path, remote_path):
        try:
            client = self._get_client()
            client.upload_sync(remote_path=remote_path, local_path=local_path)
            return True, "上传成功"
        except Exception as e:
            return False, "上传失败: {}".format(str(e)[:200])

    def upload_file_with_progress(self, local_path, remote_path, progress_callback=None):
        """上传文件，WebDAV SDK 不支持进度回调，使用默认实现"""
        # WebDAV SDK 不支持进度回调，直接调用 upload_file
        return self.upload_file(local_path, remote_path)

    def download_file(self, remote_path, local_path):
        try:
            client = self._get_client()
            client.download_sync(remote_path=remote_path, local_path=local_path)
            return True, "下载成功"
        except Exception as e:
            return False, "下载失败: {}".format(str(e)[:200])

    def delete_file(self, remote_path):
        try:
            client = self._get_client()
            client.clean(remote_path)
            return True, "删除成功"
        except Exception as e:
            return False, "删除失败: {}".format(str(e)[:200])

    def create_dir(self, remote_path):
        try:
            client = self._get_client()
            client.mkdir(remote_path)
            return True, "创建目录成功"
        except Exception as e:
            return False, "创建目录失败: {}".format(str(e)[:200])

    def get_file_url(self, remote_path, expires=3600):
        return False, "WebDAV不支持生成临时URL"

    def get_bucket_usage(self):
        try:
            import requests
            # WebDAV RFC 4331 支持 quota-available-bytes 和 quota-used-bytes
            url = self.endpoint.rstrip('/') + '/'
            headers = {'Depth': '0'}
            body = '''<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:quota-available-bytes/>
    <d:quota-used-bytes/>
  </d:prop>
</d:propfind>'''
            auth = (self.access_key, self.secret_key) if self.access_key else None
            resp = requests.request('PROPFIND', url, headers=headers, data=body, auth=auth, timeout=10)
            if resp.status_code in (207, 200):
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.content)
                ns = {'d': 'DAV:'}
                used = 0
                available = 0
                for propstat in root.iter('{DAV:}propstat'):
                    prop = propstat.find('{DAV:}prop')
                    if prop is not None:
                        used_el = prop.find('{DAV:}quota-used-bytes')
                        avail_el = prop.find('{DAV:}quota-available-bytes')
                        if used_el is not None and used_el.text:
                            used = int(used_el.text)
                        if avail_el is not None and avail_el.text:
                            available = int(avail_el.text)
                total = used + available if used > 0 and available > 0 else 0
                return True, {
                    'used_size': used,
                    'total_count': 0,
                    'total_quota': total,
                }
            return True, {'used_size': 0, 'total_count': 0, 'total_quota': 0}
        except Exception:
            return True, {'used_size': 0, 'total_count': 0, 'total_quota': 0}

    def copy_file(self, src_path, dst_path):
        try:
            client = self._get_client()
            client.copy(remote_path_from=src_path, remote_path_to=dst_path)
            return True, "复制成功"
        except Exception as e:
            return False, "复制失败: {}".format(str(e)[:200])

    def file_exists(self, remote_path):
        try:
            client = self._get_client()
            exists = client.check(remote_path)
            return bool(exists), "文件存在" if exists else "文件不存在"
        except Exception:
            return False, "文件不存在"

    def get_file_info(self, remote_path):
        try:
            client = self._get_client()
            info = client.info(remote_path)
            return True, {
                'key': remote_path,
                'size': 0,
                'last_modified': info.get('modified', '') if isinstance(info, dict) else '',
                'content_type': '',
                'etag': '',
            }
        except Exception as e:
            return False, "获取文件信息失败: {}".format(str(e)[:200])
