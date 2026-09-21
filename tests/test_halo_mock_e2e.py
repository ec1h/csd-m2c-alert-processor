"""E2E-local and replay tests using the halo-mock-harness skill.

Unlike test_lambda_handler.py (in-memory FakeHalo), these tests exercise the
real HaloClient urllib request/response/error-handling code paths against a
loopback HTTP server, and the full lambda_handler against Alertmanager
fixtures. See .github/skills/halo-mock-harness/SKILL.md for the full test
pyramid and scenario catalog.
"""

import json
import sys
from pathlib import Path

import pytest

_SKILL_SCRIPTS = Path(__file__).resolve().parents[1] / ".github/skills/halo-mock-harness/scripts"
_FIXTURES = Path(__file__).resolve().parents[1] / ".github/skills/halo-mock-harness/fixtures"
sys.path.insert(0, str(_SKILL_SCRIPTS))

from halo_client import HaloAuthError, HaloRequestError  # noqa: E402
from mock_halo_server import MockHaloServer  # noqa: E402
from replay_alert import InMemoryDedup, replay  # noqa: E402

ALL_MAPPED_FIRING_FIXTURES = [
    "low_battery_firing.json",
    "tamper_firing.json",
    "no_usage_firing.json",
    "excessive_usage_firing.json",
    "no_communication_firing.json",
    "reverse_flow_firing.json",
    "device_reboot_firing.json",
]


@pytest.fixture
def mock_halo():
    with MockHaloServer() as server:
        yield server


def _ticket_body(tickettype_id=64):
    return {"tickettype_id": tickettype_id, "team_id": 12, "summary": "x", "details": "y"}


class TestMockHaloServer:
    """E2E-local layer: real HaloClient against the loopback mock server."""

    def test_create_ticket_success(self, mock_halo):
        from halo_client import HaloClient
        halo = HaloClient(mock_halo.base_url, "id", "secret")
        assert halo.create_ticket(_ticket_body()) == 1001

    def test_create_ticket_type_not_found(self, mock_halo):
        from halo_client import HaloClient
        mock_halo.scenario["create_ticket"] = "ticket_type_not_found"
        halo = HaloClient(mock_halo.base_url, "id", "secret")
        with pytest.raises(HaloRequestError) as exc_info:
            halo.create_ticket(_ticket_body())
        assert exc_info.value.status_code == 400

    def test_create_ticket_unknown_tickettype_id_is_rejected(self, mock_halo):
        from halo_client import HaloClient
        halo = HaloClient(mock_halo.base_url, "id", "secret")
        with pytest.raises(HaloRequestError) as exc_info:
            halo.create_ticket(_ticket_body(tickettype_id=999))
        assert exc_info.value.status_code == 400

    def test_auth_failure_raises_halo_auth_error(self, mock_halo):
        from halo_client import HaloClient
        mock_halo.scenario["auth"] = "failed"
        halo = HaloClient(mock_halo.base_url, "id", "secret")
        with pytest.raises(HaloAuthError):
            halo.create_ticket(_ticket_body())

    def test_add_note_server_error(self, mock_halo):
        from halo_client import HaloClient
        mock_halo.scenario["add_note"] = "server_error"
        halo = HaloClient(mock_halo.base_url, "id", "secret")
        with pytest.raises(HaloRequestError) as exc_info:
            halo.add_note(1001, "note")
        assert exc_info.value.status_code == 500


class TestReplay:
    """Replay layer: full lambda_handler against Alertmanager fixtures."""

    @pytest.mark.parametrize("fixture_name", ALL_MAPPED_FIRING_FIXTURES)
    def test_every_mapped_alert_type_creates_a_ticket(self, fixture_name):
        resp = replay(_FIXTURES / fixture_name, "ok")
        assert resp["statusCode"] == 200

    def test_low_battery_ticket_type_not_found_is_retryable(self):
        # Regression coverage for the [HALO ERROR] "Ticket Type not found"
        # 400s observed in error_dump.json.
        resp = replay(_FIXTURES / "low_battery_firing.json", "ticket_type_not_found")
        assert resp["statusCode"] == 502

    def test_auth_failed_is_retryable(self):
        resp = replay(_FIXTURES / "tamper_firing.json", "auth_failed")
        assert resp["statusCode"] == 502

    def test_resolved_alert_adds_note_to_existing_ticket(self):
        # Chain firing -> resolved through a shared dedup store, since the
        # resolved path only adds a note if an open record already exists.
        dedup = InMemoryDedup()
        firing_resp = replay(_FIXTURES / "low_battery_firing.json", "ok", dedup=dedup)
        assert firing_resp["statusCode"] == 200

        resolved_resp = replay(_FIXTURES / "low_battery_resolved.json", "ok", dedup=dedup)
        assert resolved_resp["statusCode"] == 200
        payload = json.loads(resolved_resp["body"])
        assert payload["results"][0]["action"] == "ticket_updated"
