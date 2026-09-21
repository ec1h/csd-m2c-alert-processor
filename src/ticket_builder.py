"""Builds Halo ticket and resolution-note payloads from Grafana alerts."""

from datetime import datetime

from routing import AlertRoute


def fmt_ts(iso_str: str) -> str:
    try:
        if not iso_str or iso_str.startswith("0001"):
            return "N/A"
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return iso_str or "N/A"


def build_ticket(alert: dict, alert_type: str, route: AlertRoute, team_id: int, ticket_type_id: int) -> dict:
    labels = alert.get("labels", {})
    values = alert.get("values", {})

    sn = labels.get("SN", "N/A")
    meter_sn = labels.get("MeterSN", "N/A")
    folder = labels.get("grafana_folder", "M2C Alerts")
    voltage = values.get("B")
    started_at = fmt_ts(alert.get("startsAt", ""))
    fingerprint = alert.get("fingerprint", "N/A")
    grafana_url = alert.get("generatorURL", "N/A")
    silence_url = alert.get("silenceURL", "N/A")

    voltage_line = f"\n  Battery Voltage:   {voltage:.4f} V" if voltage is not None else ""

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
        + f"  Responsible:       {route.responsible}\n"
        + f"  Action:            {route.action}\n\n"
        + "LINKS\n"
        + f"  Grafana Alert:     {grafana_url}\n"
        + f"  Silence in Grafana:{silence_url}\n\n"
        + "=" * 55 + "\n"
        + "This ticket was created automatically by the M2C IoT Alert Integration.\n"
    )

    return {
        "tickettype_id": ticket_type_id,
        "team_id": team_id,
        "summary": f"[M2C] {alert_type} - Device SN: {sn}",
        "details": details,
    }


def build_resolution_note(alert: dict, alert_type: str) -> str:
    labels = alert.get("labels", {})
    sn = labels.get("SN", "N/A")
    ended_at = fmt_ts(alert.get("endsAt", ""))

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
