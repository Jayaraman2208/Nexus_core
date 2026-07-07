"""
Vendor-agnostic integration layer for the 5G Network-in-a-Box (NIB).

All communication with the physical/virtual NIB hardware goes through this module.
If the underlying hardware vendor changes, only this file (and its request/response
mapping) needs to change — nothing else in the codebase should ever call the NIB's
HTTP API directly.

By default NIB_USE_MOCK=True in settings, so the app runs and can be fully exercised
end-to-end (dashboard, provisioning flow, state machine, audit trail) without real
hardware attached. Flip NIB_USE_MOCK=False and fill in NIB_API_BASE_URL / NIB_API_KEY
to point at a real box.
"""
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests
from django.conf import settings

from api.exceptions import NIBIntegrationError

logger = logging.getLogger("nexuscore")


@dataclass
class SliceProvisionResult:
    nib_slice_ref: str
    success: bool


@dataclass
class SimProvisionResult:
    nib_sim_ref: str
    success: bool


class BaseNIBClient(ABC):
    """Common contract every NIB vendor implementation must satisfy."""

    @abstractmethod
    def health_check(self) -> bool:
        ...

    @abstractmethod
    def provision_slice(self, *, name: str, slice_type: str, max_bandwidth_mbps: int, max_devices: int) -> SliceProvisionResult:
        ...

    @abstractmethod
    def provision_sim(self, *, iccid: str, imsi: str, request_id: str, slice_ref: str | None) -> SimProvisionResult:
        ...

    @abstractmethod
    def get_live_metrics(self) -> dict:
        ...


class MockNIBClient(BaseNIBClient):
    """Simulates a healthy NIB so the whole application can be developed and demoed
    without physical hardware. Deterministic enough for tests, jittery enough to feel real.
    """

    def health_check(self) -> bool:
        return True

    def provision_slice(self, *, name, slice_type, max_bandwidth_mbps, max_devices) -> SliceProvisionResult:
        time.sleep(0.2)  # simulate network latency
        return SliceProvisionResult(nib_slice_ref=f"mock-slice-{uuid.uuid4().hex[:10]}", success=True)

    def provision_sim(self, *, iccid, imsi, request_id, slice_ref) -> SimProvisionResult:
        time.sleep(0.2)
        return SimProvisionResult(nib_sim_ref=f"mock-sim-{uuid.uuid4().hex[:10]}", success=True)

    def get_live_metrics(self) -> dict:
        return {
            "connected_devices": random.randint(5, 50),
            "total_throughput_mbps": round(random.uniform(50, 950), 1),
            "avg_signal_strength_dbm": round(random.uniform(-95, -55), 1),
        }


class HTTPNIBClient(BaseNIBClient):
    """Real implementation talking to the NIB's REST API over HTTPS."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error("NIB request failed: %s %s -> %s", method, url, exc)
            raise NIBIntegrationError(
                f"NIB request failed: {method} {path}", code="nib_request_failed", details={"error": str(exc)}
            ) from exc

    def health_check(self) -> bool:
        try:
            data = self._request("GET", "/health")
            return bool(data.get("healthy"))
        except NIBIntegrationError:
            return False

    def provision_slice(self, *, name, slice_type, max_bandwidth_mbps, max_devices) -> SliceProvisionResult:
        data = self._request(
            "POST",
            "/slices",
            json={
                "name": name,
                "type": slice_type,
                "max_bandwidth_mbps": max_bandwidth_mbps,
                "max_devices": max_devices,
            },
        )
        return SliceProvisionResult(nib_slice_ref=data["slice_ref"], success=True)

    def provision_sim(self, *, iccid, imsi, request_id, slice_ref) -> SimProvisionResult:
        data = self._request(
            "POST",
            "/sims",
            json={"iccid": iccid, "imsi": imsi, "request_id": request_id, "slice_ref": slice_ref},
            headers={"Idempotency-Key": request_id},
        )
        return SimProvisionResult(nib_sim_ref=data["sim_ref"], success=True)

    def get_live_metrics(self) -> dict:
        return self._request("GET", "/metrics")


_client_instance = None


def get_nib_client() -> BaseNIBClient:
    """Factory returning a singleton NIB client based on settings.NIB_USE_MOCK."""
    global _client_instance
    if _client_instance is None:
        if settings.NIB_USE_MOCK:
            _client_instance = MockNIBClient()
        else:
            _client_instance = HTTPNIBClient(
                base_url=settings.NIB_API_BASE_URL,
                api_key=settings.NIB_API_KEY,
                timeout=settings.NIB_REQUEST_TIMEOUT,
            )
    return _client_instance
