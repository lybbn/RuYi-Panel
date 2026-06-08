import json


class CloudStorageBase:
    provider_name = ""
    provider_display = ""
    protocol = ""

    def __init__(self, account):
        self.account = account
        self.access_key = account.access_key
        self.secret_key = account.secret_key
        self.endpoint = account.endpoint
        self.region = account.region
        self.bucket = account.bucket
        self.backup_path = account.backup_path
        try:
            self.extra_config = json.loads(account.extra_config) if account.extra_config else {}
        except (json.JSONDecodeError, TypeError):
            self.extra_config = {}

    def test_connection(self):
        raise NotImplementedError

    def list_buckets(self):
        raise NotImplementedError

    def list_objects(self, prefix="", delimiter="/", max_keys=200):
        raise NotImplementedError

    def upload_file(self, local_path, remote_path):
        raise NotImplementedError

    def upload_file_with_progress(self, local_path, remote_path, progress_callback=None):
        """上传文件，支持进度回调
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            progress_callback: 进度回调函数，签名为 callback(uploaded_bytes, total_bytes)
        """
        # 默认实现：调用 upload_file，不支持进度回调
        return self.upload_file(local_path, remote_path)

    def download_file(self, remote_path, local_path):
        raise NotImplementedError

    def delete_file(self, remote_path):
        raise NotImplementedError

    def create_dir(self, remote_path):
        raise NotImplementedError

    def get_file_url(self, remote_path, expires=3600):
        raise NotImplementedError

    def get_bucket_usage(self):
        raise NotImplementedError

    def copy_file(self, src_path, dst_path):
        raise NotImplementedError

    def file_exists(self, remote_path):
        raise NotImplementedError

    def get_file_info(self, remote_path):
        raise NotImplementedError

    def get_presigned_upload_url(self, remote_path, content_type='application/octet-stream', expires=3600):
        """获取前端直传的预签名上传URL
        
        Args:
            remote_path: 远程文件路径
            content_type: 文件MIME类型
            expires: URL有效期（秒）
            
        Returns:
            tuple: (success, data)
                成功时 data 为 dict，包含 upload_url 和可选的 headers
                失败时 data 为错误信息字符串
        """
        return False, "该云存储类型不支持前端直传"

    # ========== 存储桶设置 ==========

    def get_bucket_cors(self, bucket_name=None):
        """获取存储桶CORS配置
        
        Args:
            bucket_name: 存储桶名称，为空时使用账号默认桶
            
        Returns:
            tuple: (success, data)
                成功时 data 为 dict，包含 rules 列表
                失败时 data 为错误信息字符串
        """
        return False, "该云存储类型不支持CORS配置"

    def put_bucket_cors(self, cors_rules, bucket_name=None):
        """设置存储桶CORS配置
        
        Args:
            cors_rules: CORS规则列表，格式为:
                [
                    {
                        'allowed_origins': ['*'],
                        'allowed_methods': ['GET', 'PUT'],
                        'allowed_headers': ['*'],
                        'expose_headers': ['ETag'],
                        'max_age_seconds': 3600,
                    }
                ]
            bucket_name: 存储桶名称，为空时使用账号默认桶
            
        Returns:
            tuple: (success, msg)
        """
        return False, "该云存储类型不支持CORS配置"

    def delete_bucket_cors(self, bucket_name=None):
        """删除存储桶CORS配置
        
        Args:
            bucket_name: 存储桶名称，为空时使用账号默认桶
            
        Returns:
            tuple: (success, msg)
        """
        return False, "该云存储类型不支持CORS配置"

    def get_bucket_acl(self, bucket_name=None):
        """获取存储桶访问权限
        
        Args:
            bucket_name: 存储桶名称，为空时使用账号默认桶
            
        Returns:
            tuple: (success, data)
                成功时 data 为 dict，包含 acl 信息
                失败时 data 为错误信息字符串
        """
        return False, "该云存储类型不支持ACL配置"

    def put_bucket_acl(self, acl_config, bucket_name=None):
        """设置存储桶访问权限
        
        Args:
            acl_config: ACL配置，格式为:
                {'acl': 'private'|'public-read'|'public-read-write'}
            bucket_name: 存储桶名称，为空时使用账号默认桶
            
        Returns:
            tuple: (success, msg)
        """
        return False, "该云存储类型不支持ACL配置"

    # ========== 分片上传管理 ==========

    def list_multipart_uploads(self, bucket_name=None):
        """列出存储桶中未完成的分片上传

        Args:
            bucket_name: 存储桶名称，为空时使用账号默认桶

        Returns:
            tuple: (success, data)
                成功时 data 为 dict，包含 uploads 列表
                失败时 data 为错误信息字符串
        """
        return False, "该云存储类型不支持分片上传管理"

    def abort_multipart_upload(self, bucket_name, upload_id, key):
        """中止指定的分片上传

        Args:
            bucket_name: 存储桶名称
            upload_id: 分片上传ID
            key: 对象键名

        Returns:
            tuple: (success, msg)
        """
        return False, "该云存储类型不支持分片上传管理"

    def abort_all_multipart_uploads(self, bucket_name=None):
        """中止存储桶中所有未完成的分片上传

        Args:
            bucket_name: 存储桶名称，为空时使用账号默认桶

        Returns:
            tuple: (success, data)
                成功时 data 包含 aborted_count
        """
        return False, "该云存储类型不支持分片上传管理"
