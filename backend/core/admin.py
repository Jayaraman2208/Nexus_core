from django.contrib import admin

from .models import SIM, AuditLog, Device, NetworkSlice


@admin.register(NetworkSlice)
class NetworkSliceAdmin(admin.ModelAdmin):
    list_display = ("name", "slice_type", "state", "max_bandwidth_mbps", "max_devices", "created_at")
    list_filter = ("slice_type", "state")
    search_fields = ("name", "nib_slice_ref")


@admin.register(SIM)
class SIMAdmin(admin.ModelAdmin):
    list_display = ("iccid", "imsi", "state", "owner", "network_slice", "created_at")
    list_filter = ("state",)
    search_fields = ("iccid", "imsi")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "imei", "sim", "last_seen_at", "last_signal_strength_dbm", "last_throughput_mbps")
    search_fields = ("name", "imei")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "method", "path", "status_code")
    list_filter = ("method", "status_code")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
