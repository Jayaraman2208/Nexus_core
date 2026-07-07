from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, DeviceViewSet, NetworkSliceViewSet, NetworkStatusView, SIMViewSet

router = DefaultRouter()
router.register(r"network-slices", NetworkSliceViewSet, basename="network-slice")
router.register(r"sims", SIMViewSet, basename="sim")
router.register(r"devices", DeviceViewSet, basename="device")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("status/", NetworkStatusView.as_view(), name="network-status"),
    path("", include(router.urls)),
]
