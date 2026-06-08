from .base import CloudStorageBase


class AliyunOSSProvider(CloudStorageBase):
    provider_name = "aliyun_oss"
    provider_display = "阿里云 OSS"
    protocol = "native"

    def __init__(self, account):
        super().__init__(account)
        self._bucket = None

    def _get_bucket(self):
        if self._bucket is not None:
            return self._bucket
        import oss2

        auth = oss2.Auth(self.access_key, self.secret_key)
        self._bucket = oss2.Bucket(auth, self.endpoint, self.bucket)
        return self._bucket

    def test_connection(self):
        try:
            bucket = self._get_bucket()
            bucket.get_bucket_info()
            return True, "连接成功，存储桶可访问"
        except oss2.exceptions.NoSuchBucket:
            return False, "存储桶不存在"
        except oss2.exceptions.AccessDenied:
            return False, "AccessKey无权限，请检查密钥配置"
        except oss2.exceptions.InvalidAccessKeyId:
            return False, "AccessKey ID无效，请检查配置"
        except Exception as e:
            return False, "连接失败: {}".format(str(e)[:200])

    def list_buckets(self):
        try:
            import oss2
            auth = oss2.Auth(self.access_key, self.secret_key)
            service = oss2.Service(auth, self.endpoint)
            buckets = []
            for b in oss2.BucketIterator(service):
                buckets.append({
                    'name': b.name,
                    'create_time': str(b.creation_date) if b.creation_date else '',
                })
            return True, buckets
        except Exception as e:
            return False, "获取存储桶列表失败: {}".format(str(e)[:200])

    def list_objects(self, prefix="", delimiter="/", max_keys=200):
        try:
            bucket = self._get_bucket()
            result = []
            marker = ''
            while True:
                resp = bucket.list_objects(
                    prefix=prefix, delimiter=delimiter,
                    max_keys=max_keys, marker=marker,
                )
                for p in resp.prefix_list:
                    display_name = p.rstrip('/').split('/')[-1]
                    result.append({
                        'key': p,
                        'name': display_name,
                        'size': 0,
                        'is_dir': True,
                        'last_modified': '',
                    })
                for obj in resp.object_list:
                    if obj.key == prefix:
                        continue
                    display_name = obj.key.split('/')[-1] if '/' in obj.key else obj.key
                    if not display_name:
                        continue
                    result.append({
                        'key': obj.key,
                        'name': display_name,
                        'size': obj.size,
                        'is_dir': False,
                        'last_modified': obj.last_modified.strftime('%Y-%m-%d %H:%M:%S') if obj.last_modified else '',
                    })
                if resp.is_truncated:
                    marker = resp.next_marker
                else:
                    break
                if len(result) >= max_keys:
                    break
            return True, result
        except Exception as e:
            return False, "获取文件列表失败: {}".format(str(e)[:200])

    def upload_file(self, local_path, remote_path):
        try:
            bucket = self._get_bucket()
            bucket.put_object_from_file(remote_path, local_path)
            return True, "上传成功"
        except Exception as e:
            return False, "上传失败: {}".format(str(e)[:200])

    def upload_file_with_progress(self, local_path, remote_path, progress_callback=None):
        """上传文件，支持进度回调"""
        try:
            import os
            bucket = self._get_bucket()
            total_size = os.path.getsize(local_path)
            
            if progress_callback and total_size > 0:
                # oss2 支持 progress_callback 参数
                def oss_progress_callback(bytes_consumed, total_bytes):
                    progress_callback(bytes_consumed, total_bytes)
                
                bucket.put_object_from_file(
                    remote_path, local_path,
                    progress_callback=oss_progress_callback
                )
            else:
                bucket.put_object_from_file(remote_path, local_path)
            return True, "上传成功"
        except Exception as e:
            return False, "上传失败: {}".format(str(e)[:200])

    def download_file(self, remote_path, local_path):
        try:
            bucket = self._get_bucket()
            bucket.get_object_to_file(remote_path, local_path)
            return True, "下载成功"
        except Exception as e:
            return False, "下载失败: {}".format(str(e)[:200])

    def delete_file(self, remote_path):
        try:
            bucket = self._get_bucket()
            bucket.delete_object(remote_path)
            return True, "删除成功"
        except Exception as e:
            return False, "删除失败: {}".format(str(e)[:200])

    def create_dir(self, remote_path):
        try:
            bucket = self._get_bucket()
            if not remote_path.endswith('/'):
                remote_path += '/'
            bucket.put_object(remote_path, b'')
            return True, "创建目录成功"
        except Exception as e:
            return False, "创建目录失败: {}".format(str(e)[:200])

    def get_file_url(self, remote_path, expires=3600):
        try:
            bucket = self._get_bucket()
            url = bucket.sign_url('GET', remote_path, expires)
            return True, url
        except Exception as e:
            return False, "获取URL失败: {}".format(str(e)[:200])

    def get_bucket_usage(self):
        try:
            bucket = self._get_bucket()
            # 优先使用 get_bucket_stat，返回实时统计
            try:
                stat = bucket.get_bucket_stat()
                return True, {
                    'used_size': getattr(stat, 'storage_size', 0) or 0,
                    'total_count': getattr(stat, 'object_count', 0) or 0,
                    'total_quota': 0,
                }
            except Exception:
                # 回退到 get_bucket_info
                info = bucket.get_bucket_info()
                return True, {
                    'used_size': getattr(info, 'storage_size', 0) or 0,
                    'total_count': getattr(info, 'object_count', 0) or 0,
                    'total_quota': 0,
                }
        except Exception as e:
            return False, "获取用量失败: {}".format(str(e)[:200])

    def copy_file(self, src_path, dst_path):
        try:
            bucket = self._get_bucket()
            bucket.copy_object(self.bucket, src_path, dst_path)
            return True, "复制成功"
        except Exception as e:
            return False, "复制失败: {}".format(str(e)[:200])

    def file_exists(self, remote_path):
        try:
            bucket = self._get_bucket()
            bucket.head_object(remote_path)
            return True, "文件存在"
        except Exception:
            return False, "文件不存在"

    def get_file_info(self, remote_path):
        try:
            bucket = self._get_bucket()
            info = bucket.head_object(remote_path)
            return True, {
                'key': remote_path,
                'size': info.content_length,
                'last_modified': info.last_modified.strftime('%Y-%m-%d %H:%M:%S') if info.last_modified else '',
                'content_type': info.content_type,
                'etag': info.etag,
            }
        except Exception as e:
            return False, "获取文件信息失败: {}".format(str(e)[:200])

    def get_presigned_upload_url(self, remote_path, content_type='application/octet-stream', expires=3600):
        """获取阿里云 OSS 前端直传的预签名URL"""
        try:
            import oss2
            bucket = self._get_bucket()
            # 生成 PUT 方式的签名URL
            url = bucket.sign_url('PUT', remote_path, expires, headers={
                'Content-Type': content_type,
            })
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

    def _get_bucket_by_name(self, bucket_name):
        """根据桶名获取Bucket对象（用于跨桶操作）"""
        import oss2
        if bucket_name == self.bucket and self._bucket is not None:
            return self._bucket
        auth = oss2.Auth(self.access_key, self.secret_key)
        return oss2.Bucket(auth, self.endpoint, bucket_name)

    def get_bucket_cors(self, bucket_name=None):
        """获取存储桶CORS配置"""
        try:
            bucket = self._get_bucket_by_name(self._resolve_bucket_name(bucket_name))
            result = bucket.get_bucket_cors()
            rules = []
            for r in result.rules:
                rules.append({
                    'allowed_origins': r.allowed_origins,
                    'allowed_methods': r.allowed_methods,
                    'allowed_headers': r.allowed_headers,
                    'expose_headers': r.expose_headers,
                    'max_age_seconds': r.max_age_seconds or 0,
                })
            return True, {'rules': rules}
        except oss2.exceptions.NoSuchCORS:
            return True, {'rules': []}
        except Exception as e:
            return False, "获取CORS配置失败: {}".format(str(e)[:200])

    def put_bucket_cors(self, cors_rules, bucket_name=None):
        """设置存储桶CORS配置"""
        try:
            import oss2
            bucket = self._get_bucket_by_name(self._resolve_bucket_name(bucket_name))
            cors = oss2.models.BucketCors()
            for r in cors_rules:
                rule = oss2.models.CorsRule(
                    allowed_origins=r.get('allowed_origins', ['*']),
                    allowed_methods=r.get('allowed_methods', ['GET']),
                    allowed_headers=r.get('allowed_headers', ['*']),
                    expose_headers=r.get('expose_headers', []),
                    max_age_seconds=r.get('max_age_seconds', 0),
                )
                cors.rules.append(rule)
            bucket.put_bucket_cors(cors)
            return True, "CORS配置设置成功"
        except Exception as e:
            return False, "设置CORS配置失败: {}".format(str(e)[:200])

    def delete_bucket_cors(self, bucket_name=None):
        """删除存储桶CORS配置"""
        try:
            bucket = self._get_bucket_by_name(self._resolve_bucket_name(bucket_name))
            bucket.delete_bucket_cors()
            return True, "CORS配置已删除"
        except Exception as e:
            return False, "删除CORS配置失败: {}".format(str(e)[:200])

    def get_bucket_acl(self, bucket_name=None):
        """获取存储桶访问权限"""
        try:
            bucket = self._get_bucket_by_name(self._resolve_bucket_name(bucket_name))
            result = bucket.get_bucket_acl()
            acl = result.acl
            return True, {
                'acl': acl,
                'owner': result.owner.get('DisplayName', '') if isinstance(result.owner, dict) else '',
            }
        except Exception as e:
            error_msg = str(e)
            # 权限不足时返回默认值，不报错
            if 'AccessDenied' in error_msg or 'InvalidAccessKeyId' in error_msg or 'SecurityToken' in error_msg:
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
            bucket = self._get_bucket_by_name(self._resolve_bucket_name(bucket_name))
            acl = acl_config.get('acl', 'private')
            bucket.put_bucket_acl(acl)
            return True, "ACL设置成功"
        except Exception as e:
            return False, "设置ACL失败: {}".format(str(e)[:200])

    # ========== 分片上传管理 ==========

    def list_multipart_uploads(self, bucket_name=None):
        """列出存储桶中未完成的分片上传"""
        try:
            bucket = self._get_bucket_by_name(self._resolve_bucket_name(bucket_name))
            uploads = []
            for u in oss2.ObjectUploadIterator(bucket):
                uploads.append({
                    'key': u.key,
                    'upload_id': u.upload_id,
                    'initiated': u.initiated.strftime('%Y-%m-%d %H:%M:%S') if u.initiated and hasattr(u.initiated, 'strftime') else (str(u.initiated) if u.initiated else ''),
                    'storage_class': getattr(u, 'storage_class', 'STANDARD'),
                    'owner': '',
                })
            return True, {'uploads': uploads}
        except Exception as e:
            return False, "获取分片上传列表失败: {}".format(str(e)[:200])

    def abort_multipart_upload(self, bucket_name, upload_id, key):
        """中止指定的分片上传"""
        try:
            bucket = self._get_bucket_by_name(bucket_name)
            bucket.abort_multipart_upload(key, upload_id)
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
            bucket = self._get_bucket_by_name(self._resolve_bucket_name(bucket_name))
            for u in uploads:
                try:
                    bucket.abort_multipart_upload(u['key'], u['upload_id'])
                    aborted_count += 1
                except Exception:
                    pass
            return True, {'aborted_count': aborted_count, 'total_count': len(uploads)}
        except Exception as e:
            return False, "中止所有分片上传失败: {}".format(str(e)[:200])
