# -*- coding: utf-8 -*-

"""
@Remark: 系统路由
"""
from django.urls import path, re_path
from rest_framework import routers

from apps.sysdocker.views.image_view import RYDockerImageManageView
from apps.sysdocker.views.network_view import RYDockerNetworkManageView
from apps.sysdocker.views.repo_viewset import RyDockerRepoViewSet
from apps.sysdocker.views.container_view import RYDockerLimitManageView,RYDockerContainerManageView
from apps.sysdocker.views.volumes_view import RYDockerVolumesManageView
from apps.sysdocker.views.square_view import RYDockerSquareAppTagsListManageView,RYUpdateDockerSquareAppsTagsManageView,RYGetDockerSquareAppsListManageView,RYGetDockerSquareAppsManageView
from apps.sysdocker.views.backupApps_view import RYDockerBackupAppManageView,RYDockerRestoreAppManageView,RYDockerBackupDelManageView,RYDockerBackupDownloadManageView


system_url = routers.SimpleRouter()
system_url.register(r'repos', RyDockerRepoViewSet)

urlpatterns = [
    path('images/', RYDockerImageManageView.as_view(), name='镜像管理'),
    path('networks/', RYDockerNetworkManageView.as_view(), name='网络管理'),
    path('volumes/', RYDockerVolumesManageView.as_view(), name='存储卷管理'),
    path('containers/', RYDockerContainerManageView.as_view(), name='容器管理'),
    path('containers/limit/', RYDockerLimitManageView.as_view(), name='容器限制（cpu、内存）'),
    path('square/apptags/', RYDockerSquareAppTagsListManageView.as_view(), name='应用标签列表'),
    path('square/updateAppsTags/', RYUpdateDockerSquareAppsTagsManageView.as_view(), name='更新应用/标签列表'),
    path('square/appslist/', RYGetDockerSquareAppsListManageView.as_view(), name='获取应用列表'),
    path('square/appsmg/', RYGetDockerSquareAppsManageView.as_view(), name='广场应用操作'),
    path('square/backup/', RYDockerBackupAppManageView.as_view(), name='应用备份'),
    path('square/restore/', RYDockerRestoreAppManageView.as_view(), name='恢复备份'),
    path('square/delbackup/', RYDockerBackupDelManageView.as_view(), name='删除备份'),
    path('square/downloadbak/', RYDockerBackupDownloadManageView.as_view(), name='下载备份'),
]
urlpatterns += system_url.urls
