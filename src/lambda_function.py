"""M2C IoT Alert Integration — Grafana Alertmanager -> Halo ITSM.

Orchestrates config, the Halo client, the DynamoDB dedup repository, alert
routing, and ticket building. See README.md for environment variables and
the response-code contract.
"""

import json
from dataclasses import dataclass

from config import Config, load_config
from dedup_repository import DedupRepository
from halo_client import HaloAuthError, HaloClient, HaloRequestError
from metrics import emit_count
from routing import resolve_route, team_id_for
from ticket_builder import build_resolution_note, build_ticket

_METRIC_NAMESPACE = "M2CAlertProcessor"

# A retryable failure returns this status so Alertmanager/API Gateway retries
# the delivery; 200 means every alert either succeeded or was intentionally
# skipped (duplicate, no open ticket, unmapped type, unknown status).
_RETRYABLE_STATUS_CODE = 502


@dataclass
class Dependencies:
    config: Config
    halo: HaloClient
    dedup: DedupRepository


# Constructed once per execution environment and reused across warm
# invocations, matching the original module-level caching behaviour, but
# lazily so importing this module never makes an AWS or network call.
_deps: Dependencies | None = None


def _get_dependencies() -> Dependencies:
    global _deps
    if _deps is None:
        config = load_config()
        _deps = Dependencies(
            config=config,
            halo=HaloClient(config.halo_base_url, config.halo_client_id, config.halo_client_secret),
            dedup=DedupRepository(config.dynamodb_table, config.dynamodb_ttl_days, config.halo_base_url),
        )
    return _deps


def _is_authorized(deps: Dependencies, event: dict) -> bool:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    token = headers.get("authorization", "").replace("Bearer ", "").strip()
    return token == deps.config.webhook_secret


def _process_firing(deps: Dependencies, alert: dict, fingerprint: str, alert_type: str, sn: str) -> dict:
    existing = deps.dedup.get(fingerprint)
    if existing:
        print(f"[SKIP] {alert_type} SN:{sn} - duplicate, ticket {existing['ticket_id']} exists")
        emit_count(_METRIC_NAMESPACE, "DuplicateSkipped", {"AlertType": alert_type})
        return {"fingerprint": fingerprint, "action": "skipped_duplicate",
                "ticket_id": existing["ticket_id"], "retryable": False}

    route = resolve_route(alert_type)
    if route is None:
        print(f"[UNMAPPED] alert_type={alert_type!r} SN:{sn} fingerprint:{fingerprint} - no ticket created")
        emit_count(_METRIC_NAMESPACE, "UnmappedAlertType", {"AlertType": alert_type})
        return {"fingerprint": fingerprint, "action": "unmapped_alert_type",
                "alert_type": alert_type, "retryable": False}

    team_id = team_id_for(route, deps.config)
    ticket_body = build_ticket(alert, alert_type, route, team_id, deps.config.halo_ticket_type_id)

    try:
        ticket_id = deps.halo.create_ticket(ticket_body)
    except (HaloAuthError, HaloRequestError) as exc:
        print(f"[ERROR] Failed to create ticket for SN:{sn}: {exc}")
        emit_count(_METRIC_NAMESPACE, "HaloRequestFailure", {"Operation": "create_ticket"})
        return {"fingerprint": fingerprint, "action": "error", "error": str(exc), "retryable": True}

    try:
        deps.dedup.save_open_ticket(fingerprint, ticket_id, alert_type, sn)
    except Exception as exc:
        # The Halo ticket already exists; retrying would create a duplicate,
        # so this is reported but deliberately not marked retryable.
        print(f"[ERROR] Ticket {ticket_id} created but dedup write failed for SN:{sn}: {exc}")
        emit_count(_METRIC_NAMESPACE, "DedupWriteFailure", {"Operation": "save_open_ticket"})
        return {"fingerprint": fingerprint, "action": "error", "error": str(exc),
                "ticket_id": ticket_id, "retryable": False}

    halo_url = f"{deps.config.halo_base_url}/ticket?id={ticket_id}"
    print(f"[OK] Created ticket {ticket_id} - {halo_url}")
    emit_count(_METRIC_NAMESPACE, "TicketCreated", {"AlertType": alert_type})
    return {"fingerprint": fingerprint, "action": "ticket_created",
            "ticket_id": ticket_id, "halo_url": halo_url, "retryable": False}


def _process_resolved(deps: Dependencies, alert: dict, fingerprint: str, alert_type: str, sn: str) -> dict:
    existing = deps.dedup.get(fingerprint)
    if not existing or existing.get("status") != "open":
        print(f"[SKIP] Resolved alert {fingerprint} - no open ticket")
        return {"fingerprint": fingerprint, "action": "skipped_no_open_ticket", "retryable": False}

    ticket_id = int(existing["ticket_id"])
    try:
        deps.halo.add_note(ticket_id, build_resolution_note(alert, alert_type))
    except (HaloAuthError, HaloRequestError) as exc:
        print(f"[ERROR] Failed to add resolution note for SN:{sn}: {exc}")
        emit_count(_METRIC_NAMESPACE, "HaloRequestFailure", {"Operation": "add_note"})
        return {"fingerprint": fingerprint, "action": "error", "error": str(exc), "retryable": True}

    try:
        deps.dedup.mark_resolved(fingerprint)
    except Exception as exc:
        # The note was already added; retrying would add a duplicate note,
        # so this is reported but deliberately not marked retryable.
        print(f"[ERROR] Note added to ticket {ticket_id} but mark_resolved failed for SN:{sn}: {exc}")
        emit_count(_METRIC_NAMESPACE, "DedupWriteFailure", {"Operation": "mark_resolved"})
        return {"fingerprint": fingerprint, "action": "error", "error": str(exc),
                "ticket_id": ticket_id, "retryable": False}

    print(f"[OK] Resolution note added to ticket {ticket_id} for SN:{sn}")
    emit_count(_METRIC_NAMESPACE, "TicketUpdated", {"AlertType": alert_type})
    return {"fingerprint": fingerprint, "action": "ticket_updated", "ticket_id": ticket_id, "retryable": False}


def lambda_handler(event: dict, context) -> dict:
    deps = _get_dependencies()

    if not _is_authorized(deps, event):
        print("[AUTH] Rejected - invalid or missing Authorization Bearer token")
        return {"statusCode": 401, "body": "Unauthorized"}

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as exc:
        print(f"[PARSE ERROR] {exc}")
        return {"statusCode": 400, "body": "Invalid JSON"}

    alerts = body.get("alerts", [])
    print(f"[INFO] {len(alerts)} alert(s) - group status: {body.get('status')}")

    results = []
    for alert in alerts:
        fingerprint = alert.get("fingerprint")
        status = alert.get("status")
        labels = alert.get("labels", {})
        sn = labels.get("SN", "unknown")
        alert_type = labels.get("M2C", "Unknown")

        if not fingerprint:
            print(f"[SKIP] Alert with no fingerprint - alert_type={alert_type!r} SN:{sn}")
            results.append({"action": "invalid_missing_fingerprint", "alert_type": alert_type, "retryable": False})
            continue

        if status == "firing":
            results.append(_process_firing(deps, alert, fingerprint, alert_type, sn))
        elif status == "resolved":
            results.append(_process_resolved(deps, alert, fingerprint, alert_type, sn))
        else:
            print(f"[SKIP] Unknown status '{status}' for SN:{sn}")
            results.append({"fingerprint": fingerprint, "action": "skipped_unknown_status", "retryable": False})

    retryable_failures = [r for r in results if r.get("retryable")]
    status_code = _RETRYABLE_STATUS_CODE if retryable_failures else 200

    print(f"[INFO] Done - {len(results)} processed, {len(retryable_failures)} retryable failure(s)")
    return {
        "statusCode": status_code,
        "body": json.dumps({"processed": len(results), "results": results}),
    }