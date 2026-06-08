from .base import CloudStorageBase


class TencentCOSProvider(CloudStorageBase):
    provider_name = "tencent_cos"
    provider_display = "腾讯云 COS"
    protocol = "native"

    def __init__(self, account):
        super().__init__(account)
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        from qcloud_cos import CosS3Client
        from qcloud_cos import CosConfig

        config = CosConfig(
            Region=self.region,
            SecretId=self.access_key,
            SecretKey=self.secret_key,
        )
        self._client = CosS3Client(config)
        return self._client

    def test_connection(self):
        try:
            client = self._get_client()
            client.head_bucket(Bucket=self.bucket)
            return True, "连接成功，存储桶可访问"
        except Exception as e:
            error_msg = str(e)
            if 'AccessDenied' in error_msg:
                return False, "AccessKey无权限，请检查密钥配置"
            if 'NoSuchBucket' in error_msg:
                return False, "存储桶不存在"
            return False, "连接失败: {}".format(error_msg[:200])

    def list_buckets(self):
        try:
            client = self._get_client()
            resp = client.list_buckets()
            buckets = []
            for b in resp.get('Buckets', {}).get('Bucket', []):
                buckets.append({
                    'name': b.get('Name', ''),
                    'create_time': b.get('CreationDate', ''),
                    'region': b.get('Location', ''),
                })
            return True, buckets
        except Exception as e:
            return False, "获取存储桶列表失败: {}".format(str(e)[:200])

    def list_objects(self, prefix="", delimiter="/", max_keys=200):
        try:
            client = self._get_client()
            resp = client.list_objects(
                Bucket=self.bucket,
                Prefix=prefix,
                Delimiter=delimiter,
                MaxKeys=max_keys,
            )
            result = []
            for p in resp.get('CommonPrefixes', []):
                prefix_key = p.get('Prefix', '')
                display_name = prefix_key.rstrip('/').split('/')[-1]
                result.append({
                    'key': prefix_key,
                    'name': display_name,
                    'size': 0,
                    'is_dir': True,
                    'last_modified': '',
                })
            for obj in resp.get('Contents', []):
                key = obj.get('Key', '')
                if key == prefix:
                    continue
                display_name = key.split('/')[-1] if '/' in key else key
                if not display_name:
                    continue
                result.append({
                    'key': key,
                    'name': display_name,
                    'size': obj.get('Size', 0),
                    'is_dir': False,
                    'last_modified': obj.get('LastModified', ''),
                })
            return True, result
        except Exception as e:
            return False, "获取文件列表失败: {}".format(str(e)[:200])

    def upload_file(self, local_path, remote_path):
        try:
            client = self._get_client()
            client.upload_file(
                Bucket=self.bucket,
                Key=remote_path,
                LocalFilePath=local_path,
            )
            return True, "上传成功"
        except Exception as e:
            return False, "上传失败: {}".format(str(e)[:200])

    def upload_file_with_progress(self, local_path, remote_path, progress_callback=None):
        """上传文件，支持进度回调"""
        try:
            import os
            client = self._get_client()
            total_size = os.path.getsize(local_path)
            
            if progress_callback and total_size > 0:
                # 腾讯云 COS SDK 支持 progress_listener 参数
                def cos_progress_listener(uploaded, total):
                    progress_callback(uploaded, total)
                
                client.upload_file(
                    Bucket=self.bucket,
                    Key=remote_path,
                    LocalFilePath=local_path,
                    progress_listener=cos_progress_listener,
                )
            else:
                client.upload_file(
                    Bucket=self.bucket,
                    Key=remote_path,
                    LocalFilePath=local_path,
                )
            return True, "上传成功"
        except Exception as e:
            return False, "上传失败: {}".format(str(e)[:200])

    def download_file(self, remote_path, local_path):
        try:
            client = self._get_client()
            client.download_file(
                Bucket=self.bucket,
                Key=remote_path,
                DestFilePath=local_path,
            )
            return True, "下载成功"
        except Exception as e:
            return False, "下载失败: {}".format(str(e)[:200])

    def delete_file(self, remote_path):
        try:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket, Key=remote_path)
            return True, "删除成功"
        except Exception as e:
            return False, "删除失败: {}".format(str(e)[:200])

    def create_dir(self, remote_path):
        try:
            client = self._get_client()
            if not remote_path.endswith('/'):
                remote_path += '/'
            client.put_object(Bucket=self.bucket, Key=remote_path, Body=b'')
            return True, "创建目录成功"
        except Exception as e:
            return False, "创建目录失败: {}".format(str(e)[:200])

    def get_file_url(self, remote_path, expires=3600):
        try:
            client = self._get_client()
            url = client.get_presigned_url(
                Method='GET',
                Bucket=self.bucket,
                Key=remote_path,
                Expires=expires,
            )
            return True, url
        except Exception as e:
            return False, "获取URL失败: {}".format(str(e)[:200])

    def get_bucket_usage(self):
        try:
            client = self._get_client()
            used_size = 0
            total_count = 0
            marker = ''
            while True:
                resp = client.list_objects(Bucket=self.bucket, Marker=marker, MaxKeys=1000)
                if 'Contents' in resp:
                    for obj in resp['Contents']:
                        used_size += obj.get('Size', 0)
                        total_count += 1
                if resp.get('IsTruncated') in ('true', True):
                    marker = resp.get('NextMarker', '')
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
            client = self._get_client()
            copy_source = {
                'Bucket': self.bucket,
                'Region': self.region,
                'Key': src_path,
            }
            client.copy_object(
                Bucket=self.bucket,
                Key=dst_path,
                CopySource=copy_source,
            )
            return True, "复制成功"
        except Exception as e:
            return False, "复制失败: {}".format(str(e)[:200])

    def file_exists(self, remote_path):
        try:
            client = self._get_client()
            client.head_object(Bucket=self.bucket, Key=remote_path)
            return True, "文件存在"
        except Exception:
            return False, "文件不存在"

    def get_file_info(self, remote_path):
        try:
            client = self._get_client()
            resp = client.head_object(Bucket=self.bucket, Key=remote_path)
            return True, {
                'key': remote_path,
                'size': resp.get('Content-Length', 0),
                'last_modified': resp.get('Last-Modified', ''),
                'content_type': resp.get('Content-Type', ''),
                'etag': resp.get('ETag', ''),
            }
        except Exception as e:
            return False, "获取文件信息失败: {}".format(str(e)[:200])

    def get_presigned_upload_url(self, remote_path, content_type='application/octet-stream', expires=3600):
        """获取腾讯云 COS 前端直传的预签名URL"""
        try:
            client = self._get_client()
            # 生成 PUT 方式的预签名URL
            url = client.get_presigned_url(
                Method='PUT',
                Bucket=self.bucket,
                Key=remote_path,
                Expires=expires,
            )
            return True, {
                'upload_url': url,
                'method': 'PUT',
                'headers': {
                    'Content-Type': content_type,
                },
            }
        except Exception as e:
            return False, "生成上传URL失败: {}".format(str(e)[:200])

    # ========== 存储桶设置 ==========

    def _resolve_bucket_name(self, bucket_name=None):
        return bucket_name or self.bucket

    def _get_client_for_bucket(self, bucket_name):
        """获取指定桶的client（处理跨区域桶）"""
        if bucket_name == self.bucket:
            return self._get_client()
        # 从桶名解析region（COS桶名格式: bucket-appid, region从list_buckets获取）
        from qcloud_cos import CosConfig
        config = CosConfig(
            Region=self.region,
            SecretId=self.access_key,
            SecretKey=self.secret_key,
        )
        from qcloud_cos import CosS3Client
        return CosS3Client(config)

    def get_bucket_cors(self, bucket_name=None):
        """获取存储桶CORS配置"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket_name(bucket_name)
            resp = client.get_bucket_cors(Bucket=bucket)
            rules = []
            for r in resp.get('CORSRules', []):
                rules.append({
                    'allowed_origins': r.get('AllowedOrigins', []),
                    'allowed_methods': r.get('AllowedMethods', []),
                    'allowed_headers': r.get('AllowedHeaders', []),
                    'expose_headers': r.get('ExposeHeaders', []),
                    'max_age_seconds': r.get('MaxAgeSeconds', 0),
                })
            return True, {'rules': rules}
        except Exception as e:
            err_str = str(e)
            if 'NoSuchCORSConfiguration' in err_str or 'NoSuchCorsConfiguration' in err_str:
                return True, {'rules': []}
            return False, "获取CORS配置失败: {}".format(err_str[:200])

    def put_bucket_cors(self, cors_rules, bucket_name=None):
        """设置存储桶CORS配置"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket_name(bucket_name)
            cos_rules = []
            for r in cors_rules:
                rule = {
                    'AllowedOrigins': r.get('allowed_origins', ['*']),
                    'AllowedMethods': r.get('allowed_methods', ['GET']),
                    'AllowedHeaders': r.get('allowed_headers', ['*']),
                }
                expose = r.get('expose_headers', [])
                if expose:
                    rule['ExposeHeaders'] = expose
                max_age = r.get('max_age_seconds', 0)
                if max_age:
                    rule['MaxAgeSeconds'] = max_age
                cos_rules.append(rule)
            client.put_bucket_cors(
                Bucket=bucket,
                CORSConfiguration={'CORSRules': cos_rules},
            )
            return True, "CORS配置设置成功"
        except Exception as e:
            return False, "设置CORS配置失败: {}".format(str(e)[:200])

    def delete_bucket_cors(self, bucket_name=None):
        """删除存储桶CORS配置"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket_name(bucket_name)
            client.delete_bucket_cors(Bucket=bucket)
            return True, "CORS配置已删除"
        except Exception as e:
            return False, "删除CORS配置失败: {}".format(str(e)[:200])

    def get_bucket_acl(self, bucket_name=None):
        """获取存储桶访问权限"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket_name(bucket_name)
            resp = client.get_bucket_acl(Bucket=bucket)
            acl = 'private'
            grants = resp.get('AccessControlList', {}).get('Grant', [])
            all_users_uri = 'http://cam.qcloud.com/groups/global/AllUsers'
            has_read = False
            has_write = False
            for g in grants:
                grantee = g.get('Grantee', {})
                if grantee.get('URI', '') == all_users_uri:
                    permission = g.get('Permission', '')
                    if permission in ('READ', 'FULL_CONTROL'):
                        has_read = True
                    if permission in ('WRITE', 'FULL_CONTROL'):
                        has_write = True
            if has_read and has_write:
                acl = 'public-read-write'
            elif has_read:
                acl = 'public-read'
            return True, {
                'acl': acl,
                'owner': resp.get('Owner', {}).get('DisplayName', ''),
            }
        except Exception as e:
            error_msg = str(e)
            # 权限不足时返回默认值，不报错
            if 'AccessDenied' in error_msg or 'Access Denied' in error_msg or 'UnauthorizedOperation' in error_msg:
                return True, {
                    'acl': 'private',
                    'owner': '',
                    'no_permission': True,
                    'msg': '当前账号权限不足，无法获取ACL，显示默认值'
                }
            return False, "获取ACL失败: {}".format(error_msg[:200])

    def put_bucket_acl(self, acl_config, bucket_name=None):
        """设置存储桶访问权限"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket_name(bucket_name)
            acl = acl_config.get('acl', 'private')
            # COS ACL值: private | public-read | public-read-write
            client.put_bucket_acl(Bucket=bucket, ACL=acl)
            return True, "ACL设置成功"
        except Exception as e:
            return False, "设置ACL失败: {}".format(str(e)[:200])

    # ========== 分片上传管理 ==========

    def list_multipart_uploads(self, bucket_name=None):
        """列出存储桶中未完成的分片上传"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket_name(bucket_name)
            uploads = []
            marker = ''
            while True:
                resp = client.list_multipart_uploads(Bucket=bucket, Marker=marker)
                for u in resp.get('Upload', []):
                    uploads.append({
                        'key': u.get('Key', ''),
                        'upload_id': u.get('UploadId', ''),
                        'initiated': u.get('Initiated', ''),
                        'storage_class': u.get('StorageClass', 'STANDARD'),
                        'owner': u.get('Owner', {}).get('DisplayName', ''),
                    })
                if resp.get('IsTruncated') in ('true', True):
                    marker = resp.get('NextKeyMarker', '')
                else:
                    break
            return True, {'uploads': uploads}
        except Exception as e:
            return False, "获取分片上传列表失败: {}".format(str(e)[:200])

    def abort_multipart_upload(self, bucket_name, upload_id, key):
        """中止指定的分片上传"""
        try:
            client = self._get_client()
            client.abort_multipart_upload(Bucket=bucket_name, Key=key, UploadId=upload_id)
            return True, "已中止分片上传"
        except Exception as e:
            return False, "中止分片上传失败: {}".format(str(e)[:200])

    def abort_all_multipart_uploads(self, bucket_name=None):
        """中止存储桶中所有未完成的分片上传"""
        try:
            success, result = self.list_multipart_uploads(bucket_name=bucket_name)
            if not success:
                return False, result
            uploads = result.get('uploads', [])
            aborted_count = 0
            bucket = self._resolve_bucket_name(bucket_name)
            for u in uploads:
                try:
                    s, _ = self.abort_multipart_upload(bucket, u['upload_id'], u['key'])
                    if s:
                        aborted_count += 1
                except Exception:
                    pass
            return True, {'aborted_count': aborted_count, 'total_count': len(uploads)}
        except Exception as e:
            return False, "中止所有分片上传失败: {}".format(str(e)[:200])
