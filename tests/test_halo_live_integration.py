"""Opt-in live-Halo integration smoke tests.

Skipped entirely unless HALO_LIVE_BASE_URL, HALO_LIVE_CLIENT_ID, and
HALO_LIVE_CLIENT_SECRET are all set - never runs in the default `pytest`
invocation or the `tests.yml` CI workflow (see tests/README.md). Intended for
a manual run, or the `live-halo-smoke` workflow_dispatch job, once real Halo
access is granted.

These tests talk to a real HaloITSM instance. Do not point HALO_LIVE_BASE_URL
at a production org.
"""

import os

import pytest

from halo_client import HaloClient

_BASE_URL = os.environ.get("HALO_LIVE_BASE_URL")
_CLIENT_ID = os.environ.get("HALO_LIVE_CLIENT_ID")
_CLIENT_SECRET = os.environ.get("HALO_LIVE_CLIENT_SECRET")

pytestmark = pytest.mark.skipif(
    not (_BASE_URL and _CLIENT_ID and _CLIENT_SECRET),
    reason=(
        "HALO_LIVE_BASE_URL / HALO_LIVE_CLIENT_ID / HALO_LIVE_CLIENT_SECRET not set - "
        "opt-in live Halo test, see tests/README.md"
    ),
)


def test_live_oauth_token_acquired():
    """Read-only: proves the client-credentials grant and base URL are correct."""
    halo = HaloClient(_BASE_URL, _CLIENT_ID, _CLIENT_SECRET)
    token = halo._get_token()
    assert token


def test_live_create_ticket_uses_configured_ticket_type():
    """Creates one real Halo ticket - the actual regression check for the
    'Ticket Type not found' 400s in error_dump.json. Only runs when
    explicitly opted into, since it has a real side effect in Halo."""
    if os.environ.get("HALO_LIVE_ALLOW_TICKET_CREATION") != "1":
        pytest.skip("set HALO_LIVE_ALLOW_TICKET_CREATION=1 to allow this test to create a real Halo ticket")

    ticket_type_id = int(os.environ.get("HALO_LIVE_TICKET_TYPE_ID", "64"))
    team_id = int(os.environ.get("HALO_LIVE_TEAM_ID", "12"))

    halo = HaloClient(_BASE_URL, _CLIENT_ID, _CLIENT_SECRET)
    ticket_id = halo.create_ticket({
        "tickettype_id": ticket_type_id,
        "team_id": team_id,
        "summary": "[M2C][smoke-test] halo-live-integration - safe to close",
        "details": (
            "Created by tests/test_halo_live_integration.py to verify "
            "HALO_TICKET_TYPE_ID/team routing against a live Halo org. "
            "Safe to close once confirmed."
        ),
    })
    print(f"[LIVE SMOKE] created ticket {ticket_id} at {_BASE_URL} - close manually after verifying")
    assert ticket_id
