"""Paginated, read-only scan of the alert dedup table.

Only ever calls `Table.scan()` - never put_item/update_item/delete_item.
"""

from collections.abc import Iterator

import boto3

_PROJECTION = "fingerprint, ticket_id, alert_type, device_sn, #s, created_at"
_EXPRESSION_NAMES = {"#s": "status"}


def scan_open_records(table_name: str, region: str) -> Iterator[dict]:
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    scan_kwargs = {
        "FilterExpression": "#s = :open",
        "ProjectionExpression": _PROJECTION,
        "ExpressionAttributeNames": _EXPRESSION_NAMES,
        "ExpressionAttributeValues": {":open": "open"},
    }

    while True:
        response = table.scan(**scan_kwargs)
        yield from response.get("Items", [])

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return
        scan_kwargs["ExclusiveStartKey"] = last_key
