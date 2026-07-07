import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.db import transaction

from api.exceptions import NIBIntegrationError
from core.models import SIM, NetworkSlice

from .service import get_nib_client

logger = logging.getLogger("nexuscore")


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def provision_sim_task(self, sim_id: str):
    """Provisions a SIM on the NIB and advances its state machine, without blocking the request/response cycle."""
    try:
        sim = SIM.objects.get(id=sim_id)
    except SIM.DoesNotExist:
        logger.warning("provision_sim_task: SIM %s no longer exists", sim_id)
        return

    try:
        with transaction.atomic():
            sim.start_provisioning()
            sim.save(update_fields=["state", "updated_at"])

        client = get_nib_client()
        result = client.provision_sim(
            iccid=sim.iccid,
            imsi=sim.imsi,
            request_id=str(sim.nib_request_id),
            slice_ref=sim.network_slice.nib_slice_ref if sim.network_slice else None,
        )

        with transaction.atomic():
            if result.success:
                sim.activate()
            else:
                sim.mark_failed()
            sim.save(update_fields=["state", "updated_at"])

    except NIBIntegrationError as exc:
        logger.error("Provisioning failed for SIM %s: %s", sim_id, exc.message)
        sim.refresh_from_db()
        sim.mark_failed()
        sim.save(update_fields=["state", "updated_at"])
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def provision_network_slice_task(self, slice_id: str):
    try:
        network_slice = NetworkSlice.objects.get(id=slice_id)
    except NetworkSlice.DoesNotExist:
        logger.warning("provision_network_slice_task: slice %s no longer exists", slice_id)
        return

    try:
        with transaction.atomic():
            network_slice.start_provisioning()
            network_slice.save(update_fields=["state", "updated_at"])

        client = get_nib_client()
        result = client.provision_slice(
            name=network_slice.name,
            slice_type=network_slice.slice_type,
            max_bandwidth_mbps=network_slice.max_bandwidth_mbps,
            max_devices=network_slice.max_devices,
        )

        with transaction.atomic():
            if result.success:
                network_slice.nib_slice_ref = result.nib_slice_ref
                network_slice.activate()
            else:
                network_slice.mark_failed()
            network_slice.save(update_fields=["state", "nib_slice_ref", "updated_at"])

    except NIBIntegrationError as exc:
        logger.error("Provisioning failed for slice %s: %s", slice_id, exc.message)
        network_slice.refresh_from_db()
        network_slice.mark_failed()
        network_slice.save(update_fields=["state", "updated_at"])
        raise self.retry(exc=exc)


@shared_task
def broadcast_live_metrics():
    """Periodic task (wire up via Celery beat) that pulls live metrics from the NIB
    and pushes them to every connected dashboard over the 'network_metrics' WebSocket group.
    """
    client = get_nib_client()
    metrics = client.get_live_metrics()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "network_metrics",
        {"type": "metrics.update", "data": metrics},
    )
    return metrics
