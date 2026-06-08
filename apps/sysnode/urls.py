from django.urls import path
from apps.sysnode.views.node_views import (
    NodeCategoryViewSet, ClusterNodeViewSet, ClusterNodeManageView
)
from apps.sysnode.views.loadbalance_views import (
    UpstreamResourceViewSet, LoadBalanceSiteViewSet, LoadBalanceManageView
)
from apps.sysnode.views.replication_views import (
    MysqlReplicationViewSet, MysqlReplicationManageView,
    RedisReplicationViewSet, RedisReplicationManageView
)
from apps.sysnode.views.transfer_views import (
    FileTransferTaskViewSet, FileTransferManageView
)

urlpatterns = [
    path('category/', NodeCategoryViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='节点分类'),
    path('category/<int:pk>/', NodeCategoryViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='节点分类详情'),
    path('node/', ClusterNodeViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='集群节点'),
    path('node/<int:pk>/', ClusterNodeViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='集群节点详情'),
    path('node/manage/', ClusterNodeManageView.as_view(), name='节点管理'),
    path('upstream/', UpstreamResourceViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='Upstream资源'),
    path('upstream/<int:pk>/', UpstreamResourceViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='Upstream资源详情'),
    path('upstream/batch_delete/', UpstreamResourceViewSet.as_view({'post': 'batch_delete'}), name='Upstream批量删除'),
    path('lb_site/', LoadBalanceSiteViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='负载均衡站点'),
    path('lb_site/<int:pk>/', LoadBalanceSiteViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='负载均衡站点详情'),
    path('loadbalance/manage/', LoadBalanceManageView.as_view(), name='负载均衡管理'),
    path('mysql_replication/', MysqlReplicationViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='MySQL主从复制'),
    path('mysql_replication/<int:pk>/', MysqlReplicationViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='MySQL主从复制详情'),
    path('mysql_replication/manage/', MysqlReplicationManageView.as_view(), name='MySQL主从复制管理'),
    path('redis_replication/', RedisReplicationViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='Redis主从复制'),
    path('redis_replication/<int:pk>/', RedisReplicationViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='Redis主从复制详情'),
    path('redis_replication/manage/', RedisReplicationManageView.as_view(), name='Redis主从复制管理'),
    path('file_transfer/', FileTransferTaskViewSet.as_view({'get': 'list', 'post': 'create', 'delete': 'destroy'}), name='文件传输'),
    path('file_transfer/<int:pk>/', FileTransferTaskViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='文件传输详情'),
    path('file_transfer/manage/', FileTransferManageView.as_view(), name='文件传输管理'),
]
