from django.urls import path
from .views import cloud_account_views, cloud_file_views, cloud_mount_views, cloud_sdk_views

urlpatterns = [
    path('providers/', cloud_account_views.CloudProviderListView.as_view(), name='cloud_providers'),

    path('account/', cloud_account_views.CloudAccountListView.as_view(), name='cloud_account_list'),
    path('account/create/', cloud_account_views.CloudAccountCreateView.as_view(), name='cloud_account_create'),
    path('account/<int:pk>/', cloud_account_views.CloudAccountDetailView.as_view(), name='cloud_account_detail'),
    path('account/<int:pk>/test/', cloud_account_views.CloudAccountTestConnectionView.as_view(), name='cloud_account_test'),
    path('account/<int:pk>/set-default/', cloud_account_views.CloudAccountSetDefaultView.as_view(), name='cloud_account_set_default'),
    path('account/check-sdk/', cloud_account_views.CloudAccountCheckSdkView.as_view(), name='cloud_account_check_sdk'),
    path('account/export/', cloud_account_views.CloudAccountExportView.as_view(), name='cloud_account_export'),
    path('account/import/', cloud_account_views.CloudAccountImportView.as_view(), name='cloud_account_import'),

    path('file/list/', cloud_file_views.CloudFileListView.as_view(), name='cloud_file_list'),
    path('file/upload/', cloud_file_views.CloudFileUploadView.as_view(), name='cloud_file_upload'),
    path('file/upload-local/', cloud_file_views.CloudFileUploadLocalView.as_view(), name='cloud_file_upload_local'),
    path('file/upload-cancel/', cloud_file_views.CloudFileUploadCancelView.as_view(), name='cloud_file_upload_cancel'),
    path('file/presigned-upload/', cloud_file_views.CloudFilePresignedUploadView.as_view(), name='cloud_file_presigned_upload'),
    path('file/download/', cloud_file_views.CloudFileDownloadView.as_view(), name='cloud_file_download'),
    path('file/delete/', cloud_file_views.CloudFileDeleteView.as_view(), name='cloud_file_delete'),
    path('file/create-dir/', cloud_file_views.CloudFileCreateDirView.as_view(), name='cloud_file_create_dir'),
    path('file/get-url/', cloud_file_views.CloudFileGetUrlView.as_view(), name='cloud_file_get_url'),
    path('file/bucket-usage/', cloud_file_views.CloudFileBucketUsageView.as_view(), name='cloud_file_bucket_usage'),
    path('file/buckets/', cloud_file_views.CloudFileBucketsView.as_view(), name='cloud_file_buckets'),
    path('file/dir-size/', cloud_file_views.CloudFileDirSizeView.as_view(), name='cloud_file_dir_size'),
    path('file/bucket-cors/', cloud_file_views.CloudBucketCorsGetView.as_view(), name='cloud_bucket_cors_get'),
    path('file/bucket-cors/put/', cloud_file_views.CloudBucketCorsPutView.as_view(), name='cloud_bucket_cors_put'),
    path('file/bucket-cors/delete/', cloud_file_views.CloudBucketCorsDeleteView.as_view(), name='cloud_bucket_cors_delete'),
    path('file/bucket-acl/', cloud_file_views.CloudBucketAclGetView.as_view(), name='cloud_bucket_acl_get'),
    path('file/bucket-acl/put/', cloud_file_views.CloudBucketAclPutView.as_view(), name='cloud_bucket_acl_put'),
    path('file/multipart-uploads/', cloud_file_views.CloudMultipartUploadsListView.as_view(), name='cloud_multipart_uploads_list'),
    path('file/multipart-upload/abort/', cloud_file_views.CloudMultipartUploadAbortView.as_view(), name='cloud_multipart_upload_abort'),
    path('file/multipart-upload/abort-all/', cloud_file_views.CloudMultipartUploadAbortAllView.as_view(), name='cloud_multipart_upload_abort_all'),

    path('mount/', cloud_mount_views.CloudMountListView.as_view(), name='cloud_mount_list'),
    path('mount/create/', cloud_mount_views.CloudMountCreateView.as_view(), name='cloud_mount_create'),
    path('mount/<int:pk>/mount/', cloud_mount_views.CloudMountMountView.as_view(), name='cloud_mount_do_mount'),
    path('mount/<int:pk>/unmount/', cloud_mount_views.CloudMountUnmountView.as_view(), name='cloud_mount_unmount'),
    path('mount/<int:pk>/', cloud_mount_views.CloudMountDeleteView.as_view(), name='cloud_mount_delete'),
    path('mount/check-env/', cloud_mount_views.CloudMountCheckEnvView.as_view(), name='cloud_mount_check_env'),

    path('sdk/', cloud_sdk_views.CloudSdkListView.as_view(), name='cloud_sdk_list'),
    path('sdk/install/', cloud_sdk_views.CloudSdkInstallView.as_view(), name='cloud_sdk_install'),
    path('sdk/uninstall/', cloud_sdk_views.CloudSdkUninstallView.as_view(), name='cloud_sdk_uninstall'),
    path('sdk/check/', cloud_sdk_views.CloudSdkCheckView.as_view(), name='cloud_sdk_check'),
]
