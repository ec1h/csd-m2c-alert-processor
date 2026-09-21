"""Tests for reconciliation classification rules."""

from classifier import RecordStatus, classify_record
from halo_readonly_client import HaloLookupResult


def _lookup(result: HaloLookupResult):
    return lambda ticket_id: result


def test_malformed_when_ticket_id_missing():
    result = classify_record({"fingerprint": "fp1"}, _lookup(None), 64, {12, 13, 14})
    assert result.status == RecordStatus.MALFORMED


def test_malformed_when_ticket_id_not_numeric():
    result = classify_record({"fingerprint": "fp1", "ticket_id": "abc"}, _lookup(None), 64, {12, 13, 14})
    assert result.status == RecordStatus.MALFORMED


def test_missing_when_halo_returns_not_found():
    lookup = _lookup(HaloLookupResult(outcome="not_found"))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.MISSING


def test_forbidden_when_halo_denies_access():
    lookup = _lookup(HaloLookupResult(outcome="forbidden"))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.FORBIDDEN


def test_halo_unavailable_on_transient_failure():
    lookup = _lookup(HaloLookupResult(outcome="unavailable", detail="HTTP 503"))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.HALO_UNAVAILABLE


def test_healthy_when_type_team_match_and_open():
    ticket = {"tickettype_id": 64, "team_id": 12}
    lookup = _lookup(HaloLookupResult(outcome="found", ticket=ticket, is_closed=False))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.HEALTHY


def test_wrong_type_or_team_when_mismatched():
    ticket = {"tickettype_id": 99, "team_id": 12}
    lookup = _lookup(HaloLookupResult(outcome="found", ticket=ticket, is_closed=False))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.WRONG_TYPE_OR_TEAM


def test_closed_or_resolved_when_halo_ticket_is_closed():
    ticket = {"tickettype_id": 64, "team_id": 12}
    lookup = _lookup(HaloLookupResult(outcome="found", ticket=ticket, is_closed=True))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.CLOSED_OR_RESOLVED


def test_ambiguous_when_closed_status_cannot_be_determined():
    ticket = {"tickettype_id": 64, "team_id": 12}
    lookup = _lookup(HaloLookupResult(outcome="found", ticket=ticket, is_closed=None))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.AMBIGUOUS


def test_ambiguous_when_ticket_missing_expected_fields():
    lookup = _lookup(HaloLookupResult(outcome="found", ticket={}, is_closed=None))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.AMBIGUOUS


def test_ambiguous_on_unrecognized_lookup_outcome():
    lookup = _lookup(HaloLookupResult(outcome="something_new"))
    result = classify_record({"fingerprint": "fp1", "ticket_id": "500"}, lookup, 64, {12, 13, 14})
    assert result.status == RecordStatus.AMBIGUOUS
