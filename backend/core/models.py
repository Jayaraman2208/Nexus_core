import uuid

from django.conf import settings
from django.db import models
from django_fsm import FSMField, transition


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class NetworkSlice(TimeStampedModel):
    """A logical 5G network slice carved out of the NIB (e.g. eMBB, URLLC, mMTC)."""

    class SliceType(models.TextChoices):
        EMBB = "eMBB", "Enhanced Mobile Broadband"
        URLLC = "URLLC", "Ultra-Reliable Low-Latency Communication"
        MMTC = "mMTC", "Massive Machine-Type Communication"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slice_type = models.CharField(max_length=10, choices=SliceType.choices)
    nib_slice_ref = models.CharField(max_length=100, blank=True, help_text="Vendor-side slice identifier")
    state = FSMField(default="pending", protected=True)
    max_bandwidth_mbps = models.PositiveIntegerField(default=100)
    max_devices = models.PositiveIntegerField(default=50)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.slice_type})"

    @transition(field=state, source="pending", target="provisioning")
    def start_provisioning(self):
        """Kick off provisioning on the NIB."""

    @transition(field=state, source="provisioning", target="active")
    def activate(self):
        """Mark active once the NIB confirms the slice is live."""

    @transition(field=state, source=["active", "provisioning"], target="suspended")
    def suspend(self):
        """Temporarily suspend the slice (e.g. for maintenance)."""

    @transition(field=state, source="suspended", target="active")
    def resume(self):
        """Resume a suspended slice."""

    @transition(field=state, source=["pending", "provisioning", "active", "suspended"], target="failed")
    def mark_failed(self):
        """Something went wrong on the NIB side."""


class SIM(TimeStampedModel):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        PROVISIONING = "provisioning", "Provisioning"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    iccid = models.CharField(max_length=22, unique=True)
    imsi = models.CharField(max_length=15, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sims"
    )
    network_slice = models.ForeignKey(
        NetworkSlice, on_delete=models.SET_NULL, null=True, blank=True, related_name="sims"
    )
    state = FSMField(default=State.PENDING, protected=True)
    nib_request_id = models.UUIDField(default=uuid.uuid4, unique=True, help_text="Idempotency key for NIB calls")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SIM {self.iccid}"

    @transition(field=state, source=State.PENDING, target=State.PROVISIONING)
    def start_provisioning(self):
        pass

    @transition(field=state, source=State.PROVISIONING, target=State.ACTIVE)
    def activate(self):
        pass

    @transition(field=state, source=State.ACTIVE, target=State.SUSPENDED)
    def suspend(self):
        pass

    @transition(field=state, source=State.SUSPENDED, target=State.ACTIVE)
    def resume(self):
        pass

    @transition(field=state, source=[State.ACTIVE, State.SUSPENDED], target=State.DEACTIVATED)
    def deactivate(self):
        pass

    @transition(
        field=state,
        source=[State.PENDING, State.PROVISIONING, State.ACTIVE, State.SUSPENDED],
        target=State.FAILED,
    )
    def mark_failed(self):
        pass


class Device(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    imei = models.CharField(max_length=17, unique=True)
    sim = models.OneToOneField(SIM, on_delete=models.SET_NULL, null=True, blank=True, related_name="device")
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_signal_strength_dbm = models.IntegerField(null=True, blank=True)
    last_throughput_mbps = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.imei})"


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=100)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"])]

    def __str__(self):
        return f"{self.actor}: {self.method} {self.path} ({self.status_code})"
