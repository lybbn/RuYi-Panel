# -*- coding: utf-8 -*-

"""
@Remark: 系统路由
"""
from django.urls import path, re_path
from rest_framework import routers

from apps.system.views.terminal import TerminalServerViewSet
from apps.system.views.common_commands import CommonCommandsViewSet
from apps.system.views.monitor import *
from apps.system.views.file_manage import RYFileManageView,RYFileDownloadView,RYFileTokenView,RYFileUploadView
from apps.system.views.SiteGroupViews import SiteGroupViewSet
from apps.system.views.sysconfigViews import RYSysconfigManageView,RYGetInterfacesView,RYSysLicenseView,RYUpdateSysManageView
from apps.system.views.soft_shop import RYSoftShopListView,RYSoftShopManageView,RYSoftInstallLogsView,RYSoftInfoManageView
from apps.system.views.serv_manage import RYServManageView
from apps.system.views.databases_manage import DatabasesViewSet
from apps.system.views.site_manage import RYSiteManageView,RYSiteDomainManageView,RYSSLManageView,RYSiteBackupManageView
from apps.system.views.sys_firewall import RYSysFirewallView
from apps.system.views.python_manage import RYPythonManageView,RYPythonSiteManageView
from apps.system.views.go_manage import RYGoManageView
from apps.system.views.supervisor_manage import RYSupervisorManageView
from apps.system.views.sysLicenseView import RYSysImportLicenseView,RYSysUnBindLicenseView

system_url = routers.SimpleRouter()
system_url.register(r'terminal', TerminalServerViewSet)
system_url.register(r'common_command', CommonCommandsViewSet)
system_url.register(r'sitegroup', SiteGroupViewSet)
system_url.register(r'databases', DatabasesViewSet)

urlpatterns = [
    path('getSysMonitor/', GetSystemMonitorAllView.as_view(), name='首页系统监控'),
    path('sitesManage/', RYSiteManageView.as_view(), name='网站管理'),
    path('sitesDomainMg/', RYSiteDomainManageView.as_view(), name='网站域名管理'),
    path('sslMg/', RYSSLManageView.as_view(), name='SSL管理'),
    path('sitesBakMg/', RYSiteBackupManageView.as_view(), name='网站备份管理'),
    path('fileManage/', RYFileManageView.as_view(), name='文件操作'),
    path('fileManage/download/', RYFileDownloadView.as_view(), name='文件下载'),
    path('fileManage/getToken/', RYFileTokenView.as_view(), name='文件token'),
    path('fileManage/upload/', RYFileUploadView.as_view(), name='文件上传'),
    path('settings/', RYSysconfigManageView.as_view(), name='面板设置'),
    path('licenses/', RYSysLicenseView.as_view(), name='license'),
    path('licensesImport/', RYSysImportLicenseView.as_view(), name='license导入'),
    path('unbindLicenses/', RYSysUnBindLicenseView.as_view(), name='解除license绑定'),
    path('sysupdate/', RYUpdateSysManageView.as_view(), name='系统更新'),
    path('interfaces/', RYGetInterfacesView.as_view(), name='获取本机ipv4地址列表'),
    path('softlist/', RYSoftShopListView.as_view(), name='应用列表'),
    path('softmanage/', RYSoftShopManageView.as_view(), name='应用管理'),
    path('softInstallLogs/', RYSoftInstallLogsView.as_view(), name='应用安装日志文件'),
    path('softinfoMg/', RYSoftInfoManageView.as_view(), name='应用信息管理'),
    path('servmanage/', RYServManageView.as_view(), name='服务器/面板管理'),
    path('databases/dbpass/', DatabasesViewSet.as_view({'post':'databasePass'}), name='数据库密码管理'),
    path('databases/dbtools/', DatabasesViewSet.as_view({'post':'dbTools'}), name='数据库管理工具'),
    path('sysFirewall/', RYSysFirewallView.as_view(), name='系统防火墙管理'),
    path('pythonmg/', RYPythonManageView.as_view(), name='python项目管理'),
    path('pythonSiteMg/', RYPythonSiteManageView.as_view(), name='python项目站点管理'),
    path('golangmg/', RYGoManageView.as_view(), name='go项目管理'),
    path('supervisormg/', RYSupervisorManageView.as_view(), name='supervisor管理'),
]
urlpatterns += system_url.urls
