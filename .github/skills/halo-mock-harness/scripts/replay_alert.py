"""Replay one Alertmanager webhook payload through the real lambda_handler.

Uses the real `lambda_function`, `HaloClient`, `routing`, and `ticket_builder`
from `src/handlers/alert-processor/`, with Halo swapped for the local mock server and DynamoDB swapped
for an in-memory dict (same shape as tests/test_lambda_handler.py's
FakeDedup) so nothing touches AWS or a real Halo instance.

Usage:
    python replay_alert.py <fixture.json> [--scenario ok|ticket_type_not_found|auth_failed|server_error]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[4] / "src" / "handlers" / "alert-processor"
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lambda_function as lf  # noqa: E402
from lambda_function import Dependencies  # noqa: E402
from mock_halo_server import MockHaloServer  # noqa: E402
from halo_client import HaloClient  # noqa: E402


class ReplayConfig:
    halo_base_url = ""  # set after the mock server starts
    halo_client_id = "replay-client"
    halo_client_secret = "replay-secret"
    halo_ticket_type_id = 64
    halo_team_ec1 = 12
    halo_team_jw = 13
    halo_team_internal = 14
    dynamodb_table = "replay-table"
    webhook_secret = "replay-secret"
    dynamodb_ttl_days = 90


class InMemoryDedup:
    """Same shape as FakeDedup in tests/test_lambda_handler.py."""

    def __init__(self):
        self.items: dict[str, dict] = {}

    def get(self, fingerprint):
        return self.items.get(fingerprint)

    def save_open_ticket(self, fingerprint, ticket_id, alert_type, device_sn):
        self.items[fingerprint] = {
            "fingerprint": fingerprint, "ticket_id": str(ticket_id),
            "alert_type": alert_type, "device_sn": device_sn, "status": "open",
        }

    def mark_resolved(self, fingerprint):
        self.items[fingerprint]["status"] = "resolved"


def _apply_scenario(server: MockHaloServer, name: str) -> None:
    if name == "ok":
        return
    if name == "ticket_type_not_found":
        server.scenario["create_ticket"] = "ticket_type_not_found"
    elif name == "auth_failed":
        server.scenario["auth"] = "failed"
    elif name == "server_error":
        server.scenario["create_ticket"] = "server_error"
    else:
        raise SystemExit(f"unknown scenario: {name}")


def replay(fixture_path: Path, scenario: str, dedup: "InMemoryDedup | None" = None) -> dict:
    """Replay a single fixture. Pass a shared `dedup` to chain a firing fixture
    into a later resolved fixture (the resolved path needs an existing open
    record to add a note to)."""
    payload = json.loads(fixture_path.read_text())

    with MockHaloServer() as server:
        _apply_scenario(server, scenario)

        config = ReplayConfig()
        config.halo_base_url = server.base_url
        deps = Dependencies(
            config=config,
            halo=HaloClient(server.base_url, config.halo_client_id, config.halo_client_secret),
            dedup=dedup if dedup is not None else InMemoryDedup(),
        )
        lf._deps = deps

        event = {
            "headers": {"Authorization": f"Bearer {config.webhook_secret}"},
            "body": json.dumps(payload),
        }
        response = lf.lambda_handler(event, None)
        lf._deps = None
        return response


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="Path to an Alertmanager webhook JSON fixture")
    parser.add_argument(
        "--scenario", default="ok",
        choices=["ok", "ticket_type_not_found", "auth_failed", "server_error"],
        help="Halo mock behavior to reproduce (default: ok)",
    )
    args = parser.parse_args()

    response = replay(args.fixture, args.scenario)
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
