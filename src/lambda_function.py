"""
M2C IoT Alert Integration — Grafana Alertmanager → Halo ITSM
=============================================================
Confirmed Halo configuration (ec1helpdesk.haloitsm.com):
  Ticket type 64 : M2C IoT Alert
  Team 12        : M2C — EC1 Installers
  Team 13        : M2C — JW Metering
  Team 14        : M2C — EC1 Internal Support
  No priority_id : SLA applied automatically by Halo per ticket type
  No client_id   : Meter2Cash org is default on the ticket type

Environment variables (set by Terraform):
  HALO_BASE_URL          https://ec1helpdesk.haloitsm.com
  HALO_CLIENT_ID         c0c02fdd-517d-419e-88b2-5e5a79074f76
  HALO_CLIENT_SECRET     your-secret
  HALO_TICKET_TYPE_ID    64
  HALO_TEAM_EC1          12
  HALO_TEAM_JW           13
  HALO_TEAM_INTERNAL     14
  DYNAMODB_TABLE         csd-m2c-{env}-alert-dedup
  WEBHOOK_SECRET         your-webhook-secret
  DYNAMODB_TTL_DAYS      90
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
import boto3
from datetime import datetime, timezone


# ── Config ─────────────────────────────────────────────────────────────────

HALO_BASE_URL       = os.environ["HALO_BASE_URL"].rstrip("/")
HALO_CLIENT_ID      = os.environ["HALO_CLIENT_ID"]
HALO_CLIENT_SECRET  = os.environ["HALO_CLIENT_SECRET"]
HALO_TICKET_TYPE_ID = int(os.environ.get("HALO_TICKET_TYPE_ID", "64"))
HALO_TEAM_EC1       = int(os.environ.get("HALO_TEAM_EC1",       "12"))
HALO_TEAM_JW        = int(os.environ.get("HALO_TEAM_JW",        "13"))
HALO_TEAM_INTERNAL  = int(os.environ.get("HALO_TEAM_INTERNAL",  "14"))
DYNAMODB_TABLE      = os.environ["DYNAMODB_TABLE"]
WEBHOOK_SECRET      = os.environ.get("WEBHOOK_SECRET", "")
DYNAMODB_TTL_DAYS   = int(os.environ.get("DYNAMODB_TTL_DAYS",   "90"))

dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(DYNAMODB_TABLE)


# ── Halo OAuth2 ────────────────────────────────────────────────────────────

_halo_token        = None
_halo_token_expiry = 0.0


def get_halo_token() -> str:
    global _halo_token, _halo_token_expiry
    now = time.time()
    if _halo_token and now < _halo_token_expiry - 60:
        return _halo_token

    data = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     HALO_CLIENT_ID,
        "client_secret": HALO_CLIENT_SECRET,
        "scope":         "all",
    }).encode()

    req = urllib.request.Request(
        f"{HALO_BASE_URL}/auth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())

    _halo_token        = result["access_token"]
    _halo_token_expiry = now + result.get("expires_in", 3600)
    return _halo_token


def halo_request(method: str, path: str, body=None):
    token = get_halo_token()
    data  = json.dumps(body).encode() if body is not None else None

    req = urllib.request.Request(
        f"{HALO_BASE_URL}/api{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[HALO ERROR] {method} {path} -> HTTP {e.code}: {err}")
        raise


# ── Alert business rules ───────────────────────────────────────────────────

def alert_rules(alert_type: str) -> dict:
    rules = {
        "Low Battery": {
            "team_id":     HALO_TEAM_EC1,
            "responsible": "EC1 Installers",
            "action": (
                "Monitor device for 36 hours. If the alarm persists or "
                "communication is lost, schedule a site visit for battery replacement."
            ),
        },
        "Tamper": {
            "team_id":     HALO_TEAM_EC1,
            "responsible": "EC1 Installers",
            "action": (
                "Initiate on-site inspection immediately. Check for physical "
                "tampering, cable cuts between pulse reader and transponder, "
                "or device removal."
            ),
        },
        "No Usage": {
            "team_id":     HALO_TEAM_EC1,
            "responsible": "EC1 Installers",
            "action": (
                "No usage recorded outside normal consumption history. "
                "Schedule on-site inspection to verify meter and pulse reader status."
            ),
        },
        "Excessive Usage": {
            "team_id":     HALO_TEAM_JW,
            "responsible": "JW Metering",
            "action": (
                "Excessive consumption detected outside normal history. "
                "Review IoT and SAP data before dispatching for on-site inspection."
            ),
        },
        "No Communication": {
            "team_id":     HALO_TEAM_EC1,
            "responsible": "EC1 Installers",
            "action": (
                "No communication from pulse reader for 72 hours. Schedule "
                "on-site inspection - possible device failure, theft, or network issue."
            ),
        },
        "Reverse Flow": {
            "team_id":     HALO_TEAM_JW,
            "responsible": "JW Metering",
            "action": (
                "Negative consumption detected. On-site inspection required to "
                "identify meter issue, borehole presence, or illegal connection."
            ),
        },
        "Device Reboot": {
            "team_id":     HALO_TEAM_INTERNAL,
            "responsible": "EC1 Internal Support",
            "action": (
                "Device reboot detected. Internal IoT team to investigate "
                "firmware stability and physical condition of the device."
            ),
        },
    }
    return rules.get(alert_type, {
        "team_id":     HALO_TEAM_INTERNAL,
        "responsible": "EC1 Operations",
        "action":      "Investigate and resolve per standard operating procedure.",
    })


# ── Helpers ────────────────────────────────────────────────────────────────

def fmt_ts(iso_str: str) -> str:
    try:
        if not iso_str or iso_str.startswith("0001"):
            return "N/A"
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return iso_str or "N/A"


# ── Ticket builders ────────────────────────────────────────────────────────

def build_ticket(alert: dict) -> dict:
    labels      = alert.get("labels", {})
    values      = alert.get("values", {})

    alert_type  = labels.get("M2C", "Unknown Alert")
    sn          = labels.get("SN", "N/A")
    meter_sn    = labels.get("MeterSN", "N/A")
    folder      = labels.get("grafana_folder", "M2C Alerts")
    voltage     = values.get("B")
    started_at  = fmt_ts(alert.get("startsAt", ""))
    fingerprint = alert.get("fingerprint", "N/A")
    grafana_url = alert.get("generatorURL", "N/A")
    silence_url = alert.get("silenceURL", "N/A")

    rules        = alert_rules(alert_type)
    voltage_line = f"\n  Battery Voltage:   {voltage:.4f} V" \
                   if voltage is not None else ""

    details = (
        "METER TO CASH - AUTOMATED IoT ALERT\n"
        + "=" * 55 + "\n\n"
        + "ALERT DETAILS\n"
        + f"  Alert Type:        {alert_type}\n"
        + f"  Status:            FIRING\n"
        + f"  Alert Group:       {folder}\n"
        + f"  Alert Started:     {started_at}\n"
        + f"  Fingerprint:       {fingerprint}\n\n"
        + "DEVICE INFORMATION\n"
        + f"  Device SN:         {sn}\n"
        + f"  Meter SN:          {meter_sn}"
        + voltage_line + "\n\n"
        + "ACTION REQUIRED\n"
        + f"  Responsible:       {rules['responsible']}\n"
        + f"  Action:            {rules['action']}\n\n"
        + "LINKS\n"
        + f"  Grafana Alert:     {grafana_url}\n"
        + f"  Silence in Grafana:{silence_url}\n\n"
        + "=" * 55 + "\n"
        + "This ticket was created automatically by the M2C IoT Alert Integration.\n"
    )

    return {
        "tickettype_id": HALO_TICKET_TYPE_ID,
        "team_id":       rules["team_id"],
        "summary":       f"[M2C] {alert_type} - Device SN: {sn}",
        "details":       details,
    }


def build_resolution_note(alert: dict) -> str:
    labels     = alert.get("labels", {})
    alert_type = labels.get("M2C", "Unknown Alert")
    sn         = labels.get("SN", "N/A")
    ended_at   = fmt_ts(alert.get("endsAt", ""))

    return (
        "ALERT RESOLVED - AUTOMATED UPDATE\n"
        + "=" * 55 + "\n\n"
        + "The Grafana alert for this device has cleared.\n\n"
        + f"  Alert Type:   {alert_type}\n"
        + f"  Device SN:    {sn}\n"
        + f"  Resolved At:  {ended_at}\n\n"
        + "NEXT STEPS\n"
        + "  Confirm with the field team that the issue has been physically\n"
        + "  addressed (e.g. battery replaced, tamper investigated) and\n"
        + "  close this ticket manually once confirmed.\n\n"
        + "=" * 55 + "\n"
    )


# ── Halo API ───────────────────────────────────────────────────────────────

def create_halo_ticket(ticket_body: dict) -> int:
    result  = halo_request("POST", "/tickets", [ticket_body])
    tickets = result if isinstance(result, list) else [result]
    return int(tickets[0]["id"])


def add_halo_note(ticket_id: int, note_text: str) -> None:
    halo_request("POST", "/Actions", [{
        "ticket_id":     ticket_id,
        "note":          note_text,
        "actionarrival": datetime.now(timezone.utc).isoformat(),
        "who":           "M2C IoT Integration",
        "isoutgoing":    False,
        "sendemail":     False,
        "outcome":       "Alert Resolved",
    }])


# ── DynamoDB ───────────────────────────────────────────────────────────────

def get_existing(fingerprint: str) -> dict | None:
    resp = table.get_item(Key={"fingerprint": fingerprint})
    return resp.get("Item")


def save_ticket(fingerprint: str, ticket_id: int,
                alert_type: str, sn: str) -> None:
    table.put_item(Item={
        "fingerprint": fingerprint,
        "ticket_id":   str(ticket_id),
        "alert_type":  alert_type,
        "device_sn":   sn,
        "status":      "open",
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "ttl":         int(time.time()) + (DYNAMODB_TTL_DAYS * 24 * 3600),
        "halo_url":    f"{HALO_BASE_URL}/ticket?id={ticket_id}",
    })


def mark_resolved(fingerprint: str) -> None:
    table.update_item(
        Key={"fingerprint": fingerprint},
        UpdateExpression="SET #s = :s, resolved_at = :r",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "resolved",
            ":r": datetime.now(timezone.utc).isoformat(),
        },
    )


# ── Main handler ───────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:

    # Validate webhook secret
    headers     = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    auth_header = headers.get("authorization", "")
    token       = auth_header.replace("Bearer ", "").strip()


    if token != WEBHOOK_SECRET:
        print("[AUTH] Rejected - invalid or missing Authorization Bearer token")
        return {"statusCode": 401, "body": "Unauthorized"}

    # Parse body
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
        status      = alert.get("status")
        labels      = alert.get("labels", {})
        sn          = labels.get("SN", "unknown")
        alert_type  = labels.get("M2C", "Unknown")

        if not fingerprint:
            print(f"[SKIP] Alert with no fingerprint: {alert}")
            continue

        existing = get_existing(fingerprint)

        if status == "firing":
            if existing:
                print(f"[SKIP] {alert_type} SN:{sn} - duplicate, ticket {existing['ticket_id']} exists")
                results.append({"fingerprint": fingerprint, "action": "skipped_duplicate",
                                "ticket_id": existing["ticket_id"]})
            else:
                try:
                    ticket_id = create_halo_ticket(build_ticket(alert))
                    save_ticket(fingerprint, ticket_id, alert_type, sn)
                    halo_url  = f"{HALO_BASE_URL}/ticket?id={ticket_id}"
                    print(f"[OK] Created ticket {ticket_id} - {halo_url}")
                    results.append({"fingerprint": fingerprint, "action": "ticket_created",
                                    "ticket_id": ticket_id, "halo_url": halo_url})
                except Exception as exc:
                    print(f"[ERROR] Failed for SN:{sn}: {exc}")
                    results.append({"fingerprint": fingerprint, "action": "error", "error": str(exc)})

        elif status == "resolved":
            if existing and existing.get("status") == "open":
                try:
                    ticket_id = int(existing["ticket_id"])
                    add_halo_note(ticket_id, build_resolution_note(alert))
                    mark_resolved(fingerprint)
                    print(f"[OK] Resolution note added to ticket {ticket_id} for SN:{sn}")
                    results.append({"fingerprint": fingerprint, "action": "ticket_updated",
                                    "ticket_id": ticket_id})
                except Exception as exc:
                    print(f"[ERROR] Failed to update ticket for SN:{sn}: {exc}")
                    results.append({"fingerprint": fingerprint, "action": "error", "error": str(exc)})
            else:
                print(f"[SKIP] Resolved alert {fingerprint} - no open ticket")
                results.append({"fingerprint": fingerprint, "action": "skipped_no_open_ticket"})
        else:
            print(f"[SKIP] Unknown status '{status}' for SN:{sn}")

    print(f"[INFO] Done - {len(results)} processed")
    return {
        "statusCode": 200,
        "body": json.dumps({"processed": len(results), "results": results}),
    }