from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.models import SIM, AuditLog, Device, NetworkSlice

User = get_user_model()


class NetworkSliceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkSlice
        fields = (
            "id",
            "name",
            "slice_type",
            "nib_slice_ref",
            "state",
            "max_bandwidth_mbps",
            "max_devices",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "state", "nib_slice_ref", "created_at", "updated_at")


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = (
            "id",
            "name",
            "imei",
            "sim",
            "last_seen_at",
            "last_signal_strength_dbm",
            "last_throughput_mbps",
        )
        read_only_fields = ("id",)


class SIMSerializer(serializers.ModelSerializer):
    device = DeviceSerializer(read_only=True)

    class Meta:
        model = SIM
        fields = (
            "id",
            "iccid",
            "imsi",
            "owner",
            "network_slice",
            "state",
            "nib_request_id",
            "device",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "state", "nib_request_id", "created_at", "updated_at")


class SIMProvisionRequestSerializer(serializers.Serializer):
    """Input payload for provisioning a new SIM. Idempotent via client_request_id."""

    iccid = serializers.CharField(max_length=22)
    imsi = serializers.CharField(max_length=15)
    network_slice_id = serializers.UUIDField(required=False, allow_null=True)
    client_request_id = serializers.UUIDField(
        help_text="Client-generated UUID; retrying the same value will not create a duplicate SIM."
    )


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ("id", "actor", "actor_username", "action", "path", "method", "status_code", "metadata", "created_at")
        read_only_fields = fields


class NetworkStatusSerializer(serializers.Serializer):
    """Aggregate real-time snapshot of the NIB, used for the dashboard header."""

    connected_devices = serializers.IntegerField()
    active_sims = serializers.IntegerField()
    total_throughput_mbps = serializers.FloatField()
    avg_signal_strength_dbm = serializers.FloatField()
    active_slices = serializers.IntegerField()
    nib_healthy = serializers.BooleanField()
