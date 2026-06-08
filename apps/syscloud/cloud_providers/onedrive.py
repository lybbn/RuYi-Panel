from .base import CloudStorageBase


class OneDriveProvider(CloudStorageBase):
    provider_name = "onedrive"
    provider_display = "OneDrive"
    protocol = "onedrive"

    def __init__(self, account):
        super().__init__(account)
        self._client = None
        self._access_token = None

    def _get_access_token(self):
        if self._access_token:
            return self._access_token
        import msal
        import requests

        client_id = self.access_key
        client_secret = self.secret_key
        tenant_id = self.extra_config.get('tenant_id', 'common')
        refresh_token = self.extra_config.get('refresh_token', '')

        if refresh_token:
            authority = "https://login.microsoftonline.com/{}".format(tenant_id)
            app = msal.ConfidentialClientApplication(
                client_id, authority=authority, client_credential=client_secret,
            )
            result = app.acquire_token_by_refresh_token(
                refresh_token,
                scopes=["https://graph.microsoft.com/.default"],
            )
            if 'access_token' in result:
                self._access_token = result['access_token']
                if 'refresh_token' in result:
                    self._update_refresh_token(result['refresh_token'])
                return self._access_token
            error = result.get('error_description', str(result))
            raise Exception("获取access_token失败: {}".format(error[:200]))
        raise Exception("请先完成OneDrive OAuth2授权，获取refresh_token")

    def _update_refresh_token(self, new_refresh_token):
        import json
        self.extra_config['refresh_token'] = new_refresh_token
        self.account.extra_config = json.dumps(self.extra_config)
        self.account.save(update_fields=['extra_config'])

    def _get_headers(self):
        token = self._get_access_token()
        return {
            'Authorization': 'Bearer {}'.format(token),
            'Content-Type': 'application/json',
        }

    def _api_request(self, method, url, **kwargs):
        import requests
        headers = self._get_headers()
        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if resp.status_code == 401:
            self._access_token = None
            headers = self._get_headers()
            resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        return resp

    def test_connection(self):
        try:
            resp = self._api_request('GET', 'https://graph.microsoft.com/v1.0/me/drive')
            if resp.status_code == 200:
                data = resp.json()
                return True, "连接成功，驱动器: {}".format(data.get('name', 'OneDrive'))
            return False, "连接失败: HTTP {}".format(resp.status_code)
        except Exception as e:
            return False, "连接失败: {}".format(str(e)[:200])

    def list_buckets(self):
        return True, []

    def list_objects(self, prefix="", delimiter="/", max_keys=200):
        try:
            if prefix:
                path = '/root:{}'.format(prefix)
            else:
                path = '/root/children'
            url = 'https://graph.microsoft.com/v1.0/me/drive{}'.format(path)
            if not prefix:
                pass
            else:
                url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}:/children'.format(prefix)

            resp = self._api_request('GET', url)
            if resp.status_code != 200:
                return False, "获取文件列表失败: HTTP {}".format(resp.status_code)

            data = resp.json()
            result = []
            for item in data.get('value', []):
                is_dir = 'folder' in item
                name = item.get('name', '')
                result.append({
                    'key': prefix + name + ('/' if is_dir else ''),
                    'name': name,
                    'size': item.get('size', 0),
                    'is_dir': is_dir,
                    'last_modified': item.get('lastModifiedDateTime', ''),
                })
            return True, result
        except Exception as e:
            return False, "获取文件列表失败: {}".format(str(e)[:200])

    def upload_file(self, local_path, remote_path):
        try:
            import os
            file_size = os.path.getsize(local_path)
            file_name = os.path.basename(local_path)
            if file_size <= 4 * 1024 * 1024:
                url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}:/content'.format(remote_path)
                with open(local_path, 'rb') as f:
                    resp = self._api_request('PUT', url, data=f)
            else:
                url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}:/createUploadSession'.format(remote_path)
                resp = self._api_request('POST', url)
                if resp.status_code not in (200, 201):
                    return False, "创建上传会话失败"
                upload_url = resp.json().get('uploadUrl', '')
                if not upload_url:
                    return False, "获取上传URL失败"
                with open(local_path, 'rb') as f:
                    chunk_size = 4 * 1024 * 1024
                    offset = 0
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        chunk_end = offset + len(chunk) - 1
                        headers = {
                            'Content-Range': 'bytes {}-{}/{}'.format(offset, chunk_end, file_size),
                            'Content-Length': str(len(chunk)),
                        }
                        import requests
                        put_resp = requests.put(upload_url, headers=headers, data=chunk, timeout=300)
                        if put_resp.status_code not in (200, 201, 202):
                            return False, "上传分片失败: HTTP {}".format(put_resp.status_code)
                        offset += len(chunk)

            return True, "上传成功"
        except Exception as e:
            return False, "上传失败: {}".format(str(e)[:200])

    def download_file(self, remote_path, local_path):
        try:
            url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}:/content'.format(remote_path)
            import requests
            headers = self._get_headers()
            resp = requests.get(url, headers=headers, stream=True, timeout=300, allow_redirects=True)
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
            url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}'.format(remote_path)
            resp = self._api_request('DELETE', url)
            if resp.status_code in (204, 200):
                return True, "删除成功"
            return False, "删除失败: HTTP {}".format(resp.status_code)
        except Exception as e:
            return False, "删除失败: {}".format(str(e)[:200])

    def create_dir(self, remote_path):
        try:
            parent_path = '/'.join(remote_path.rstrip('/').split('/')[:-1])
            dir_name = remote_path.rstrip('/').split('/')[-1]
            if parent_path:
                url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}:/children'.format(parent_path)
            else:
                url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'
            body = {
                'name': dir_name,
                'folder': {},
                '@microsoft.graph.conflictBehavior': 'rename',
            }
            resp = self._api_request('POST', url, json=body)
            if resp.status_code in (201, 200):
                return True, "创建目录成功"
            return False, "创建目录失败: HTTP {}".format(resp.status_code)
        except Exception as e:
            return False, "创建目录失败: {}".format(str(e)[:200])

    def get_file_url(self, remote_path, expires=3600):
        try:
            url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}:/createLink'.format(remote_path)
            body = {
                'type': 'view',
                'scope': 'anonymous',
            }
            resp = self._api_request('POST', url, json=body)
            if resp.status_code in (200, 201):
                link = resp.json().get('link', {}).get('webUrl', '')
                return True, link
            return False, "获取URL失败"
        except Exception as e:
            return False, "获取URL失败: {}".format(str(e)[:200])

    def get_bucket_usage(self):
        try:
            url = 'https://graph.microsoft.com/v1.0/me/drive'
            resp = self._api_request('GET', url)
            if resp.status_code == 200:
                data = resp.json()
                quota = data.get('quota', {})
                return True, {
                    'used_size': quota.get('used', 0),
                    'total_count': 0,
                    'total_quota': quota.get('total', 0),
                    'remaining': quota.get('remaining', 0),
                }
            return False, "获取用量失败"
        except Exception as e:
            return False, "获取用量失败: {}".format(str(e)[:200])

    def copy_file(self, src_path, dst_path):
        try:
            url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}:/copy'.format(src_path)
            parent_path = '/'.join(dst_path.rstrip('/').split('/')[:-1])
            file_name = dst_path.rstrip('/').split('/')[-1]
            body = {
                'parentReference': {'path': '/drive/root:{}'.format(parent_path)},
                'name': file_name,
            }
            resp = self._api_request('POST', url, json=body)
            if resp.status_code in (200, 201, 202):
                return True, "复制成功"
            return False, "复制失败: HTTP {}".format(resp.status_code)
        except Exception as e:
            return False, "复制失败: {}".format(str(e)[:200])

    def file_exists(self, remote_path):
        try:
            url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}'.format(remote_path)
            resp = self._api_request('GET', url)
            return resp.status_code == 200, "文件存在" if resp.status_code == 200 else "文件不存在"
        except Exception:
            return False, "文件不存在"

    def get_file_info(self, remote_path):
        try:
            url = 'https://graph.microsoft.com/v1.0/me/drive/root:{}'.format(remote_path)
            resp = self._api_request('GET', url)
            if resp.status_code == 200:
                data = resp.json()
                return True, {
                    'key': remote_path,
                    'size': data.get('size', 0),
                    'last_modified': data.get('lastModifiedDateTime', ''),
                    'content_type': '',
                    'etag': data.get('eTag', ''),
                }
            return False, "获取文件信息失败"
        except Exception as e:
            return False, "获取文件信息失败: {}".format(str(e)[:200])
