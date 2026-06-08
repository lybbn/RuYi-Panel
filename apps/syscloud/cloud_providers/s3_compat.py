from .base import CloudStorageBase


class S3CompatProvider(CloudStorageBase):
    provider_name = "s3_compat"
    provider_display = "S3兼容存储"
    protocol = "s3"

    def __init__(self, account):
        super().__init__(account)
        self._client = None
        self._s3_resource = None
        from .factory import PROVIDER_REGISTRY
        provider_info = PROVIDER_REGISTRY.get(account.provider, {})
        self._path_style = provider_info.get('s3_path_style', False)

    def _get_default_region(self):
        if self.region:
            return self.region
        if self.account.provider == 'cloudflare_r2':
            return 'auto'
        return 'us-east-1'

    def _get_client(self):
        if self._client is not None:
            return self._client
        import boto3
        from botocore.config import Config

        config_kwargs = {}
        if self._path_style:
            config_kwargs['s3'] = {'addressing_style': 'path'}

        self._client = boto3.client(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            endpoint_url=self.endpoint if self.endpoint else None,
            region_name=self._get_default_region(),
            config=Config(**config_kwargs) if config_kwargs else None,
        )
        return self._client

    def _get_resource(self):
        if self._s3_resource is not None:
            return self._s3_resource
        import boto3

        self._s3_resource = boto3.resource(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            endpoint_url=self.endpoint if self.endpoint else None,
            region_name=self._get_default_region(),
        )
        return self._s3_resource

    def test_connection(self):
        try:
            client = self._get_client()
            if self.bucket:
                client.head_bucket(Bucket=self.bucket)
                return True, "连接成功，存储桶可访问"
            else:
                try:
                    client.list_buckets()
                    return True, "连接成功"
                except Exception as lb_err:
                    err_str = str(lb_err)
                    if 'AccessDenied' in err_str or 'Access Denied' in err_str:
                        return False, "AccessKey无ListBuckets权限，请填写具体的存储桶(Bucket)名称后再测试"
                    raise
        except Exception as e:
            error_msg = str(e)
            if 'AccessDenied' in error_msg or 'Access Denied' in error_msg:
                return False, "AccessKey无权限，请检查密钥配置或填写正确的存储桶名称"
            if 'NoSuchBucket' in error_msg:
                return False, "存储桶不存在，请检查Bucket名称"
            if 'InvalidAccessKeyId' in error_msg:
                return False, "AccessKey ID无效，请检查配置"
            if 'SignatureDoesNotMatch' in error_msg:
                return False, "SecretKey错误，请检查密钥配置"
            return False, "连接失败: {}".format(error_msg[:200])

    def list_buckets(self):
        try:
            client = self._get_client()
            resp = client.list_buckets()
            buckets = []
            for b in resp.get('Buckets', []):
                buckets.append({
                    'name': b['Name'],
                    'create_time': b['CreationDate'].strftime('%Y-%m-%d %H:%M:%S') if b.get('CreationDate') else '',
                })
            return True, buckets
        except Exception as e:
            return False, "获取存储桶列表失败: {}".format(str(e)[:200])

    def list_objects(self, prefix="", delimiter="/", max_keys=200):
        try:
            client = self._get_client()
            kwargs = {
                'Bucket': self.bucket,
                'Prefix': prefix,
                'Delimiter': delimiter,
                'MaxKeys': max_keys,
            }
            resp = client.list_objects_v2(**kwargs)

            dirs = []
            for p in resp.get('CommonPrefixes', []):
                dir_name = p.get('Prefix', '')
                if dir_name:
                    display_name = dir_name.rstrip('/').split('/')[-1]
                    dirs.append({
                        'key': dir_name,
                        'name': display_name,
                        'size': 0,
                        'is_dir': True,
                        'last_modified': '',
                    })

            files = []
            for obj in resp.get('Contents', []):
                key = obj.get('Key', '')
                if key == prefix:
                    continue
                display_name = key.split('/')[-1] if '/' in key else key
                if not display_name:
                    continue
                files.append({
                    'key': key,
                    'name': display_name,
                    'size': obj.get('Size', 0),
                    'is_dir': False,
                    'last_modified': obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S') if obj.get('LastModified') else '',
                })

            return True, dirs + files
        except Exception as e:
            return False, "获取文件列表失败: {}".format(str(e)[:200])

    def upload_file(self, local_path, remote_path):
        try:
            client = self._get_client()
            client.upload_file(local_path, self.bucket, remote_path)
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
                # boto3 支持 Callback 参数
                class ProgressCallback:
                    def __init__(self, callback, total):
                        self._callback = callback
                        self._total = total
                        self._uploaded = 0
                    
                    def __call__(self, bytes_amount):
                        self._uploaded += bytes_amount
                        self._callback(self._uploaded, self._total)
                
                callback = ProgressCallback(progress_callback, total_size)
                client.upload_file(local_path, self.bucket, remote_path, Callback=callback)
            else:
                client.upload_file(local_path, self.bucket, remote_path)
            return True, "上传成功"
        except Exception as e:
            return False, "上传失败: {}".format(str(e)[:200])

    def download_file(self, remote_path, local_path):
        try:
            client = self._get_client()
            client.download_file(self.bucket, remote_path, local_path)
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
            url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': remote_path},
                ExpiresIn=expires,
            )
            return True, url
        except Exception as e:
            return False, "获取URL失败: {}".format(str(e)[:200])

    def get_bucket_usage(self):
        try:
            client = self._get_client()
            used_size = 0
            total_count = 0
            paginator = client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket):
                for obj in page.get('Contents', []):
                    used_size += obj.get('Size', 0)
                    total_count += 1
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
            copy_source = {'Bucket': self.bucket, 'Key': src_path}
            client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket,
                Key=dst_path,
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
                'size': resp.get('ContentLength', 0),
                'last_modified': resp['LastModified'].strftime('%Y-%m-%d %H:%M:%S') if resp.get('LastModified') else '',
                'content_type': resp.get('ContentType', ''),
                'etag': resp.get('ETag', ''),
            }
        except Exception as e:
            return False, "获取文件信息失败: {}".format(str(e)[:200])

    def get_presigned_upload_url(self, remote_path, content_type='application/octet-stream', expires=3600):
        """获取 S3 兼容存储前端直传的预签名URL"""
        try:
            client = self._get_client()
            # 生成 PUT 方式的预签名URL
            url = client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': remote_path,
                    'ContentType': content_type,
                },
                ExpiresIn=expires,
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

    def _resolve_bucket(self, bucket_name=None):
        return bucket_name or self.bucket

    def get_bucket_cors(self, bucket_name=None):
        """获取存储桶CORS配置"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket(bucket_name)
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
            # 各种S3兼容存储的"无CORS配置"错误码
            if any(kw in err_str for kw in ('NoSuchCORSConfiguration', 'NoSuchCorsConfiguration', 'CORSConfigurationNotFoundError', 'NoSuchCORSConfiguration')):
                return True, {'rules': []}
            return False, "获取CORS配置失败: {}".format(err_str[:200])

    def put_bucket_cors(self, cors_rules, bucket_name=None):
        """设置存储桶CORS配置"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket(bucket_name)
            s3_rules = []
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
                s3_rules.append(rule)
            client.put_bucket_cors(
                Bucket=bucket,
                CORSConfiguration={'CORSRules': s3_rules},
            )
            return True, "CORS配置设置成功"
        except Exception as e:
            return False, "设置CORS配置失败: {}".format(str(e)[:200])

    def delete_bucket_cors(self, bucket_name=None):
        """删除存储桶CORS配置"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket(bucket_name)
            client.delete_bucket_cors(Bucket=bucket)
            return True, "CORS配置已删除"
        except Exception as e:
            return False, "删除CORS配置失败: {}".format(str(e)[:200])

    def get_bucket_acl(self, bucket_name=None):
        """获取存储桶访问权限"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket(bucket_name)
            resp = client.get_bucket_acl(Bucket=bucket)
            grants = resp.get('Grants', [])
            owner = resp.get('Owner', {})
            # 解析ACL，判断整体权限类型
            acl = 'private'
            all_users_uri = 'http://acs.amazonaws.com/groups/global/AllUsers'
            has_read = False
            has_write = False
            for g in grants:
                grantee = g.get('Grantee', {})
                if grantee.get('URI') == all_users_uri:
                    permission = g.get('Permission', '')
                    if permission == 'READ':
                        has_read = True
                    elif permission == 'WRITE':
                        has_write = True
                    elif permission == 'FULL_CONTROL':
                        has_read = True
                        has_write = True
            if has_read and has_write:
                acl = 'public-read-write'
            elif has_read:
                acl = 'public-read'
            return True, {
                'acl': acl,
                'owner': owner.get('DisplayName', ''),
                'grants': grants,
            }
        except Exception as e:
            error_msg = str(e)
            # 权限不足时返回默认值，不报错
            if 'AccessDenied' in error_msg or 'Access Denied' in error_msg:
                return True, {
                    'acl': 'private',
                    'owner': '',
                    'grants': [],
                    'no_permission': True,
                    'msg': '当前账号权限不足，无法获取ACL，显示默认值'
                }
            return False, "获取ACL失败: {}".format(error_msg[:200])

    def put_bucket_acl(self, acl_config, bucket_name=None):
        """设置存储桶访问权限"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket(bucket_name)
            acl = acl_config.get('acl', 'private')
            # S3标准ACL值: private | public-read | public-read-write | authenticated-read
            client.put_bucket_acl(Bucket=bucket, ACL=acl)
            return True, "ACL设置成功"
        except Exception as e:
            return False, "设置ACL失败: {}".format(str(e)[:200])

    # ========== 分片上传管理 ==========

    def list_multipart_uploads(self, bucket_name=None):
        """列出存储桶中未完成的分片上传"""
        try:
            client = self._get_client()
            bucket = self._resolve_bucket(bucket_name)
            resp = client.list_multipart_uploads(Bucket=bucket)
            uploads = []
            for u in resp.get('Uploads', []):
                uploads.append({
                    'key': u.get('Key', ''),
                    'upload_id': u.get('UploadId', ''),
                    'initiated': u['Initiated'].strftime('%Y-%m-%d %H:%M:%S') if u.get('Initiated') and hasattr(u['Initiated'], 'strftime') else (str(u.get('Initiated', '')) if u.get('Initiated') else ''),
                    'storage_class': u.get('StorageClass', 'STANDARD'),
                    'owner': u.get('Owner', {}).get('DisplayName', ''),
                })
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
            bucket = self._resolve_bucket(bucket_name)
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
