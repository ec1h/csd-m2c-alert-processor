"""Redacted report output for reconciliation results."""

import csv
import json
import sys
from collections import Counter

from classifier import Classification


def write_json(classifications: list[Classification], path: str) -> None:
    payload = {
        "summary": dict(Counter(c.status.value for c in classifications)),
        "records": [
            {"fingerprint": c.fingerprint, "ticket_id": c.ticket_id,
             "status": c.status.value, "detail": c.detail}
            for c in classifications
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def write_csv(classifications: list[Classification], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fingerprint", "ticket_id", "status", "detail"])
        for c in classifications:
            writer.writerow([c.fingerprint, c.ticket_id, c.status.value, c.detail])


def print_summary(classifications: list[Classification]) -> None:
    counts = Counter(c.status.value for c in classifications)
    print(f"[RECONCILE] {len(classifications)} open record(s) checked", file=sys.stderr)
    for status, count in sorted(counts.items()):
        print(f"[RECONCILE]   {status}: {count}", file=sys.stderr)
