from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.sysdomain.views.domain_views import (
    DnsAccountViewSet, DomainHostingViewSet, DnsProviderInfoView, CdnProviderListView,
    DnsAccountExportView, DnsAccountImportView,
)

router = DefaultRouter()
router.register(r'dns-account', DnsAccountViewSet, basename='dns-account')
router.register(r'domain-hosting', DomainHostingViewSet, basename='domain-hosting')

urlpatterns = [
    path('', include(router.urls)),
    path('provider-info/', DnsProviderInfoView.as_view(), name='dns-provider-info'),
    path('cdn-providers/', CdnProviderListView.as_view(), name='cdn-provider-list'),
    path('dns-account/export/', DnsAccountExportView.as_view(), name='dns-account-export'),
    path('dns-account/import/', DnsAccountImportView.as_view(), name='dns-account-import'),
]
