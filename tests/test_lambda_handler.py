"""Integration-style tests for the Lambda handler orchestration.

Uses in-memory fakes for Halo and DynamoDB - no AWS credentials, network
access, or real Halo instance is required or contacted.
"""

import json

import pytest

import lambda_function as lf
from halo_client import HaloRequestError
from lambda_function import Dependencies


class FakeConfig:
    halo_base_url = "https://halo.example.test"
    halo_client_id = "id"
    halo_client_secret = "test-only-secret-not-real"
    halo_ticket_type_id = 64
    halo_team_ec1 = 12
    halo_team_jw = 13
    halo_team_internal = 14
    dynamodb_table = "table"
    webhook_secret = "test-webhook-secret"
    dynamodb_ttl_days = 90


class FakeHalo:
    def __init__(self):
        self.created_tickets = []
        self.notes = []
        self._next_ticket_id = 1001
        self.raise_on_create = None
        self.raise_on_add_note = None

    def create_ticket(self, ticket_body):
        if self.raise_on_create:
            raise self.raise_on_create
        self.created_tickets.append(ticket_body)
        ticket_id = self._next_ticket_id
        self._next_ticket_id += 1
        return ticket_id

    def add_note(self, ticket_id, note_text):
        if self.raise_on_add_note:
            raise self.raise_on_add_note
        self.notes.append((ticket_id, note_text))


class FakeDedup:
    def __init__(self):
        self.items = {}
        self.raise_on_save = None

    def get(self, fingerprint):
        return self.items.get(fingerprint)

    def save_open_ticket(self, fingerprint, ticket_id, alert_type, device_sn):
        if self.raise_on_save:
            raise self.raise_on_save
        self.items[fingerprint] = {
            "fingerprint": fingerprint, "ticket_id": str(ticket_id),
            "alert_type": alert_type, "device_sn": device_sn, "status": "open",
        }

    def mark_resolved(self, fingerprint):
        self.items[fingerprint]["status"] = "resolved"


@pytest.fixture
def deps():
    d = Dependencies(config=FakeConfig(), halo=FakeHalo(), dedup=FakeDedup())
    lf._deps = d
    yield d
    lf._deps = None


def _event(body: dict, token: str = "test-webhook-secret") -> dict:
    return {"headers": {"Authorization": f"Bearer {token}"}, "body": json.dumps(body)}


def test_rejects_invalid_webhook_token(deps):
    resp = lf.lambda_handler(_event({"alerts": []}, token="wrong"), None)
    assert resp["statusCode"] == 401


def test_rejects_malformed_json(deps):
    event = {"headers": {"Authorization": "Bearer test-webhook-secret"}, "body": "{not json"}
    resp = lf.lambda_handler(event, None)
    assert resp["statusCode"] == 400


def test_firing_known_alert_creates_ticket(deps):
    body = {"status": "firing", "alerts": [{
        "fingerprint": "fp-1", "status": "firing",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert payload["results"][0]["action"] == "ticket_created"
    assert deps.halo.created_tickets[0]["team_id"] == 12
    assert deps.dedup.items["fp-1"]["status"] == "open"


def test_firing_duplicate_is_skipped(deps):
    deps.dedup.items["fp-1"] = {"fingerprint": "fp-1", "ticket_id": "999", "status": "open"}
    body = {"status": "firing", "alerts": [{
        "fingerprint": "fp-1", "status": "firing",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert payload["results"][0]["action"] == "skipped_duplicate"
    assert len(deps.halo.created_tickets) == 0


def test_firing_unmapped_alert_type_does_not_create_ticket(deps):
    body = {"status": "firing", "alerts": [{
        "fingerprint": "fp-1", "status": "firing",
        "labels": {"M2C": "Boot", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert payload["results"][0]["action"] == "unmapped_alert_type"
    assert len(deps.halo.created_tickets) == 0
    assert "fp-1" not in deps.dedup.items


def test_firing_missing_fingerprint_is_not_retryable(deps):
    body = {"status": "firing", "alerts": [{
        "status": "firing", "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert payload["results"][0]["action"] == "invalid_missing_fingerprint"


def test_halo_failure_on_create_triggers_retryable_response(deps):
    deps.halo.raise_on_create = HaloRequestError(400, "Ticket Type not found")
    body = {"status": "firing", "alerts": [{
        "fingerprint": "fp-1", "status": "firing",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 502
    assert payload["results"][0]["action"] == "error"
    assert "fp-1" not in deps.dedup.items


def test_dedup_write_failure_after_ticket_created_is_not_retried(deps):
    # A retry here would create a second Halo ticket for the same fingerprint
    # (the ticket already exists), so this must not trigger a 502.
    deps.dedup.raise_on_save = RuntimeError("DynamoDB throttled")
    body = {"status": "firing", "alerts": [{
        "fingerprint": "fp-1", "status": "firing",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert payload["results"][0]["action"] == "error"
    assert len(deps.halo.created_tickets) == 1


def test_resolved_with_open_ticket_adds_note(deps):
    deps.dedup.items["fp-1"] = {"fingerprint": "fp-1", "ticket_id": "500", "status": "open"}
    body = {"status": "resolved", "alerts": [{
        "fingerprint": "fp-1", "status": "resolved",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert payload["results"][0]["action"] == "ticket_updated"
    assert deps.dedup.items["fp-1"]["status"] == "resolved"
    assert deps.halo.notes[0][0] == 500


def test_halo_failure_on_add_note_triggers_retryable_response(deps):
    deps.dedup.items["fp-1"] = {"fingerprint": "fp-1", "ticket_id": "500", "status": "open"}
    deps.halo.raise_on_add_note = HaloRequestError(500, "Halo unavailable")
    body = {"status": "resolved", "alerts": [{
        "fingerprint": "fp-1", "status": "resolved",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 502
    assert payload["results"][0]["action"] == "error"
    assert deps.dedup.items["fp-1"]["status"] == "open"


def test_resolved_without_open_ticket_is_skipped(deps):
    body = {"status": "resolved", "alerts": [{
        "fingerprint": "fp-1", "status": "resolved",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert payload["results"][0]["action"] == "skipped_no_open_ticket"


def test_unknown_status_is_skipped_but_visible(deps):
    body = {"status": "silenced", "alerts": [{
        "fingerprint": "fp-1", "status": "silenced",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert payload["results"][0]["action"] == "skipped_unknown_status"


def test_mixed_batch_any_retryable_failure_yields_502(deps):
    original_create = deps.halo.create_ticket

    def create_unless_dev3(ticket_body):
        if "DEV-3" in ticket_body["summary"]:
            raise HaloRequestError(500, "Halo unavailable")
        return original_create(ticket_body)

    deps.halo.create_ticket = create_unless_dev3

    body = {"status": "firing", "alerts": [
        {"fingerprint": "fp-ok", "status": "firing", "labels": {"M2C": "Tamper", "SN": "DEV-2"}},
        {"fingerprint": "fp-fail", "status": "firing", "labels": {"M2C": "Tamper", "SN": "DEV-3"}},
    ]}
    resp = lf.lambda_handler(_event(body), None)
    payload = json.loads(resp["body"])

    assert resp["statusCode"] == 502
    assert [r["action"] for r in payload["results"]] == ["ticket_created", "error"]


def test_response_never_contains_client_secret(deps):
    deps.halo.raise_on_create = HaloRequestError(400, "Ticket Type not found")
    body = {"status": "firing", "alerts": [{
        "fingerprint": "fp-1", "status": "firing",
        "labels": {"M2C": "Low Battery", "SN": "DEV-1"},
    }]}
    resp = lf.lambda_handler(_event(body), None)
    assert deps.config.halo_client_secret not in resp["body"]
