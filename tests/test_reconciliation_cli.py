"""End-to-end test for the reconciliation CLI orchestration."""

import json

import cli
from halo_readonly_client import HaloLookupResult


def test_main_writes_json_report(tmp_path, monkeypatch):
    monkeypatch.setenv("HALO_CLIENT_ID", "id")
    monkeypatch.setenv("HALO_CLIENT_SECRET", "secret")

    monkeypatch.setattr(cli, "scan_open_records",
                         lambda table, region: iter([{"fingerprint": "fp1", "ticket_id": "500"}]))

    class FakeHalo:
        def __init__(self, *_a, **_k):
            pass

        def get_ticket(self, ticket_id):
            return HaloLookupResult(outcome="found", ticket={"tickettype_id": 64, "team_id": 12}, is_closed=False)

    monkeypatch.setattr(cli, "HaloReadOnlyClient", FakeHalo)

    output_path = tmp_path / "report.json"
    exit_code = cli.main([
        "--environment", "uat",
        "--region", "af-south-1",
        "--table", "dedup-table",
        "--halo-base-url", "https://halo.example.test",
        "--output", str(output_path),
        "--rate-limit-per-second", "0",
    ])

    assert exit_code == 0
    report = json.loads(output_path.read_text())
    assert report["summary"] == {"healthy": 1}
    assert report["records"][0]["fingerprint"] == "fp1"


def test_main_requires_halo_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("HALO_CLIENT_ID", raising=False)
    monkeypatch.delenv("HALO_CLIENT_SECRET", raising=False)

    exit_code = cli.main([
        "--environment", "uat",
        "--region", "af-south-1",
        "--table", "dedup-table",
        "--halo-base-url", "https://halo.example.test",
        "--output", str(tmp_path / "report.json"),
    ])
    assert exit_code == 2
