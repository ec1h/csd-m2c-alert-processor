"""Read-only Halo ticket lookup for reconciliation.

Deliberately exposes only `get_ticket` - no create/update/delete method
exists anywhere in this module, so reconciliation cannot mutate Halo.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

# Field names that might indicate a closed/resolved ticket. Not yet confirmed
# against the live Halo schema - validate during Halo Agent-login testing
# (see the incident plan) before trusting `is_closed` for real decisions.
_CLOSED_STATUS_FIELDS = ("closedon", "dateclosed")


@dataclass(frozen=True)
class HaloLookupResult:
    outcome: str  # "found" | "not_found" | "forbidden" | "unavailable"
    ticket: dict | None = None
    is_closed: bool | None = None
    detail: str = ""


def _infer_closed(ticket: dict) -> bool | None:
    for field in _CLOSED_STATUS_FIELDS:
        if ticket.get(field):
            return True
    if any(field in ticket for field in _CLOSED_STATUS_FIELDS):
        return False
    return None


class HaloReadOnlyClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str,
                 max_retries: int = 2, retry_backoff_seconds: float = 1.0):
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._token: str | None = None
        self._token_expiry: float = 0.0

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token

        data = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "all",
        }).encode()
        req = urllib.request.Request(
            f"{self._base_url}/auth/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())

        self._token = result["access_token"]
        self._token_expiry = now + result.get("expires_in", 3600)
        return self._token

    def get_ticket(self, ticket_id: int) -> HaloLookupResult:
        for attempt in range(self._max_retries + 1):
            try:
                token = self._get_token()
                req = urllib.request.Request(
                    f"{self._base_url}/api/tickets/{ticket_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    ticket = json.loads(resp.read())
                return HaloLookupResult(outcome="found", ticket=ticket, is_closed=_infer_closed(ticket))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return HaloLookupResult(outcome="not_found", detail="HTTP 404")
                if exc.code == 403:
                    return HaloLookupResult(outcome="forbidden", detail="HTTP 403")
                if exc.code >= 500 and attempt < self._max_retries:
                    time.sleep(self._retry_backoff_seconds * (attempt + 1))
                    continue
                return HaloLookupResult(outcome="unavailable", detail=f"HTTP {exc.code}")
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < self._max_retries:
                    time.sleep(self._retry_backoff_seconds * (attempt + 1))
                    continue
                return HaloLookupResult(outcome="unavailable", detail=str(exc))

        return HaloLookupResult(outcome="unavailable", detail="max retries exceeded")
