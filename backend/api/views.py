from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import SIM, AuditLog, Device, NetworkSlice
from nib_integration.service import get_nib_client
from nib_integration.tasks import provision_sim_task

from .permissions import IsStaffOrReadOnly
from .serializers import (
    AuditLogSerializer,
    DeviceSerializer,
    NetworkSliceSerializer,
    NetworkStatusSerializer,
    SIMProvisionRequestSerializer,
    SIMSerializer,
)


class NetworkSliceViewSet(viewsets.ModelViewSet):
    queryset = NetworkSlice.objects.all()
    serializer_class = NetworkSliceSerializer
    permission_classes = [IsStaffOrReadOnly]
    filterset_fields = ["slice_type", "state"]

    def perform_create(self, serializer):
        network_slice = serializer.save()
        # Kick off provisioning asynchronously; state transitions happen in the Celery task
        # once the (mock or real) NIB confirms the slice is live.
        from nib_integration.tasks import provision_network_slice_task

        provision_network_slice_task.delay(str(network_slice.id))


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.select_related("sim").all()
    serializer_class = DeviceSerializer
    permission_classes = [IsStaffOrReadOnly]
    filterset_fields = ["sim"]


class SIMViewSet(viewsets.ModelViewSet):
    queryset = SIM.objects.select_related("device", "network_slice", "owner").all()
    serializer_class = SIMSerializer
    permission_classes = [IsStaffOrReadOnly]
    filterset_fields = ["state", "network_slice"]
    http_method_names = ["get", "post", "delete", "head", "options"]  # mutation happens via explicit actions

    @action(detail=False, methods=["post"], url_path="provision")
    def provision(self, request):
        """
        Idempotently provision a new SIM. Retrying with the same client_request_id
        returns the original SIM instead of creating a duplicate — this guards against
        network hiccups causing double-provisioning on the NIB.
        """
        serializer = SIMProvisionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            existing = SIM.objects.filter(nib_request_id=data["client_request_id"]).first()
            if existing:
                return Response(SIMSerializer(existing).data, status=status.HTTP_200_OK)

            sim = SIM.objects.create(
                iccid=data["iccid"],
                imsi=data["imsi"],
                owner=request.user,
                network_slice_id=data.get("network_slice_id"),
                nib_request_id=data["client_request_id"],
            )

        # Async: talk to the NIB and move the state machine forward without blocking the UI.
        provision_sim_task.delay(str(sim.id))

        return Response(SIMSerializer(sim).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        sim = self.get_object()
        sim.suspend()
        sim.save(update_fields=["state", "updated_at"])
        return Response(SIMSerializer(sim).data)

    @action(detail=True, methods=["post"], url_path="resume")
    def resume(self, request, pk=None):
        sim = self.get_object()
        sim.resume()
        sim.save(update_fields=["state", "updated_at"])
        return Response(SIMSerializer(sim).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        sim = self.get_object()
        sim.deactivate()
        sim.save(update_fields=["state", "updated_at"])
        return Response(SIMSerializer(sim).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    filterset_fields = ["method", "status_code", "actor"]


class NetworkStatusView(APIView):
    """Aggregate real-time snapshot used to populate the dashboard header + charts on load.
    Live updates after the initial load stream in over the WebSocket channel instead of polling.
    """

    def get(self, request):
        devices = Device.objects.all()
        aggregates = devices.aggregate(
            total_throughput=Sum("last_throughput_mbps"),
            avg_signal=Avg("last_signal_strength_dbm"),
        )
        connected_cutoff = timezone.now() - timezone.timedelta(minutes=5)

        payload = {
            "connected_devices": devices.filter(last_seen_at__gte=connected_cutoff).count(),
            "active_sims": SIM.objects.filter(state=SIM.State.ACTIVE).count(),
            "total_throughput_mbps": aggregates["total_throughput"] or 0.0,
            "avg_signal_strength_dbm": aggregates["avg_signal"] or 0.0,
            "active_slices": NetworkSlice.objects.filter(state="active").count(),
            "nib_healthy": get_nib_client().health_check(),
        }
        return Response(NetworkStatusSerializer(payload).data)
