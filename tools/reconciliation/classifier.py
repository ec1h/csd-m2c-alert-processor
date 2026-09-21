"""Classifies DynamoDB dedup records against Halo, without mutating either."""

from dataclasses import dataclass
from enum import Enum


class RecordStatus(str, Enum):
    HEALTHY = "healthy"
    MISSING = "missing"
    FORBIDDEN = "forbidden"
    WRONG_TYPE_OR_TEAM = "wrong_type_or_team"
    CLOSED_OR_RESOLVED = "closed_or_resolved"
    MALFORMED = "malformed"
    HALO_UNAVAILABLE = "halo_unavailable"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Classification:
    fingerprint: str
    ticket_id: str | None
    status: RecordStatus
    detail: str


def classify_record(record: dict, halo_lookup, expected_ticket_type_id: int, expected_team_ids: set[int]) -> Classification:
    """`halo_lookup` is a callable(ticket_id: int) -> HaloLookupResult; never a mutating client."""
    fingerprint = record.get("fingerprint", "N/A")
    raw_ticket_id = record.get("ticket_id")

    if not raw_ticket_id or not str(raw_ticket_id).isdigit():
        return Classification(fingerprint, raw_ticket_id, RecordStatus.MALFORMED,
                               "ticket_id is missing or not numeric")

    result = halo_lookup(int(raw_ticket_id))

    if result.outcome == "not_found":
        return Classification(fingerprint, raw_ticket_id, RecordStatus.MISSING,
                               "Halo returned 404 for this ticket id")
    if result.outcome == "forbidden":
        return Classification(fingerprint, raw_ticket_id, RecordStatus.FORBIDDEN,
                               "Halo returned 403 - diagnostic agent lacks visibility")
    if result.outcome == "unavailable":
        return Classification(fingerprint, raw_ticket_id, RecordStatus.HALO_UNAVAILABLE,
                               f"Halo lookup failed: {result.detail}")
    if result.outcome != "found":
        return Classification(fingerprint, raw_ticket_id, RecordStatus.AMBIGUOUS,
                               f"Unrecognized Halo lookup outcome: {result.outcome}")

    ticket = result.ticket or {}
    ticket_type_id = ticket.get("tickettype_id")
    team_id = ticket.get("team_id")

    if ticket_type_id is None or team_id is None:
        return Classification(fingerprint, raw_ticket_id, RecordStatus.AMBIGUOUS,
                               "Halo response is missing tickettype_id/team_id")

    if ticket_type_id != expected_ticket_type_id or team_id not in expected_team_ids:
        return Classification(fingerprint, raw_ticket_id, RecordStatus.WRONG_TYPE_OR_TEAM,
                               f"tickettype_id={ticket_type_id} team_id={team_id}")

    if result.is_closed is None:
        # Halo's closed/resolved field was not confirmed at write time -
        # treat as unverifiable rather than silently assuming it's open.
        return Classification(fingerprint, raw_ticket_id, RecordStatus.AMBIGUOUS,
                               "Could not determine open/closed status from Halo response")

    if result.is_closed:
        return Classification(fingerprint, raw_ticket_id, RecordStatus.CLOSED_OR_RESOLVED,
                               "Halo ticket is closed/resolved but dedup record is still open")

    return Classification(fingerprint, raw_ticket_id, RecordStatus.HEALTHY,
                           "matches expected type/team and is open")
