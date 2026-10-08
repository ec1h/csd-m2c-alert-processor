"""Read-only reconciliation of the alert dedup table against Halo.

Never deletes, updates, or replays anything. Review the report and take any
corrective action through separate, explicitly approved tooling.

Halo credentials are read from HALO_CLIENT_ID / HALO_CLIENT_SECRET
environment variables only - never pass them as CLI arguments.
"""

import argparse
import os
import sys
import time

from classifier import classify_record
from dynamodb_scanner import scan_open_records
from halo_readonly_client import HaloReadOnlyClient
from report import print_summary, write_csv, write_json


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True, help="Label only, e.g. uat (for the report header)")
    parser.add_argument("--region", required=True)
    parser.add_argument("--table", required=True, help="DynamoDB dedup table name")
    parser.add_argument("--halo-base-url", required=True)
    parser.add_argument("--expected-ticket-type-id", type=int, default=64)
    parser.add_argument("--expected-team-ids", default="12,13,14",
                         help="Comma-separated Halo team ids considered valid")
    parser.add_argument("--output", required=True, help="Report file path (.json or .csv)")
    parser.add_argument("--rate-limit-per-second", type=float, default=5.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    client_id = os.environ.get("HALO_CLIENT_ID")
    client_secret = os.environ.get("HALO_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("[ERROR] HALO_CLIENT_ID and HALO_CLIENT_SECRET must be set in the environment", file=sys.stderr)
        return 2

    expected_team_ids = {int(t) for t in args.expected_team_ids.split(",") if t.strip()}
    halo = HaloReadOnlyClient(args.halo_base_url, client_id, client_secret)
    delay = 1.0 / args.rate_limit_per_second if args.rate_limit_per_second > 0 else 0.0

    classifications = []
    for record in scan_open_records(args.table, args.region):
        classifications.append(
            classify_record(record, halo.get_ticket, args.expected_ticket_type_id, expected_team_ids)
        )
        if delay:
            time.sleep(delay)

    if args.output.endswith(".csv"):
        write_csv(classifications, args.output)
    else:
        write_json(classifications, args.output)

    print_summary(classifications)
    print(f"[RECONCILE] Report written to {args.output} (environment={args.environment})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
