"""Tests for alert-type routing rules."""

from routing import known_alert_types, resolve_route, team_id_for


class FakeConfig:
    halo_team_ec1 = 12
    halo_team_jw = 13
    halo_team_internal = 14


def test_known_alert_types_resolve_to_a_route():
    for alert_type in known_alert_types():
        route = resolve_route(alert_type)
        assert route is not None
        assert team_id_for(route, FakeConfig()) in (12, 13, 14)


def test_unmapped_alert_type_returns_none():
    assert resolve_route("Boot") is None
    assert resolve_route("") is None
    assert resolve_route("Unknown") is None


def test_case_and_whitespace_are_not_normalized_implicitly():
    assert resolve_route("low battery") is None
    assert resolve_route("Low Battery ") is None
    assert resolve_route("Low Battery") is not None


def test_excessive_usage_routes_to_jw_metering():
    route = resolve_route("Excessive Usage")
    assert route.responsible == "JW Metering"
    assert team_id_for(route, FakeConfig()) == 13
