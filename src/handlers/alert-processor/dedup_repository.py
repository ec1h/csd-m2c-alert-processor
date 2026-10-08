"""DynamoDB-backed alert deduplication repository."""

import time
from datetime import datetime, timezone

import boto3


class DedupRepository:
    """One instance is reused across warm invocations, matching prior behaviour."""

    def __init__(self, table_name: str, ttl_days: int, halo_base_url: str):
        self._table = boto3.resource("dynamodb").Table(table_name)
        self._ttl_days = ttl_days
        self._halo_base_url = halo_base_url

    def get(self, fingerprint: str) -> dict | None:
        resp = self._table.get_item(Key={"fingerprint": fingerprint})
        return resp.get("Item")

    def save_open_ticket(self, fingerprint: str, ticket_id: int, alert_type: str, device_sn: str) -> None:
        self._table.put_item(Item={
            "fingerprint": fingerprint,
            "ticket_id": str(ticket_id),
            "alert_type": alert_type,
            "device_sn": device_sn,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ttl": int(time.time()) + (self._ttl_days * 24 * 3600),
            "halo_url": f"{self._halo_base_url}/ticket?id={ticket_id}",
        })

    def mark_resolved(self, fingerprint: str) -> None:
        self._table.update_item(
            Key={"fingerprint": fingerprint},
            UpdateExpression="SET #s = :s, resolved_at = :r",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "resolved",
                ":r": datetime.now(timezone.utc).isoformat(),
            },
        )
