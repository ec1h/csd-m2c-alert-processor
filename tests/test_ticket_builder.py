"""Tests for Halo ticket payload construction."""

from routing import resolve_route, team_id_for
from ticket_builder import build_resolution_note, build_ticket, fmt_ts


class FakeConfig:
    halo_team_ec1 = 12
    halo_team_jw = 13
    halo_team_internal = 14


def _alert(**overrides):
    alert = {
        "fingerprint": "abc123",
        "startsAt": "2026-09-01T10:00:00Z",
        "endsAt": "2026-09-02T10:00:00Z",
        "generatorURL": "https://grafana.example/alert",
        "silenceURL": "https://grafana.example/silence",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1", "MeterSN": "MTR-1"},
        "values": {"B": 3.21},
    }
    alert.update(overrides)
    return alert


def test_build_ticket_includes_team_and_summary():
    alert = _alert()
    route = resolve_route("Low Battery")
    team_id = team_id_for(route, FakeConfig())

    ticket = build_ticket(alert, "Low Battery", route, team_id, ticket_type_id=64)

    assert ticket["team_id"] == 12
    assert ticket["tickettype_id"] == 64
    assert ticket["summary"] == "[M2C] Low Battery - Device SN: DEV-1"
    assert "Battery Voltage:   3.2100 V" in ticket["details"]


def test_build_ticket_omits_voltage_line_when_absent():
    alert = _alert(values={})
    route = resolve_route("Low Battery")
    ticket = build_ticket(alert, "Low Battery", route, 12, 64)
    assert "Battery Voltage" not in ticket["details"]


def test_build_resolution_note_mentions_device():
    alert = _alert()
    note = build_resolution_note(alert, "Low Battery")
    assert "DEV-1" in note
    assert "RESOLVED" in note


def test_fmt_ts_handles_missing_and_zero_dates():
    assert fmt_ts("") == "N/A"
    assert fmt_ts("0001-01-01T00:00:00Z") == "N/A"
    assert fmt_ts("2026-09-01T10:00:00Z") == "2026-09-01 10:00:00 UTC"
