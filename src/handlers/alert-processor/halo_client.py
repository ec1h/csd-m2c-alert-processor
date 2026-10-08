"""Halo ITSM OAuth2 client and ticket/action requests."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


class HaloAuthError(Exception):
    """Raised when Halo OAuth2 token acquisition fails."""


class HaloRequestError(Exception):
    """Raised when a Halo API request fails after a token was obtained."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class HaloClient:
    """Thin Halo ITSM client. One instance is reused across warm invocations."""

    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self._base_url = base_url
        self._client_id = client_id
        self._client_secret = client_secret
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
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            # Never read/log the response body here - it can echo request params.
            raise HaloAuthError(f"Halo token request failed: HTTP {exc.code}") from exc

        self._token = result["access_token"]
        self._token_expiry = now + result.get("expires_in", 3600)
        return self._token

    def _request(self, method: str, path: str, body=None):
        token = self._get_token()
        data = json.dumps(body).encode() if body is not None else None

        req = urllib.request.Request(
            f"{self._base_url}/api{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode(errors="replace")
            print(f"[HALO ERROR] {method} {path} -> HTTP {exc.code}: {err_body}")
            raise HaloRequestError(exc.code, f"Halo {method} {path} failed: HTTP {exc.code}") from exc

    def create_ticket(self, ticket_body: dict) -> int:
        result = self._request("POST", "/tickets", [ticket_body])
        tickets = result if isinstance(result, list) else [result]
        return int(tickets[0]["id"])

    def add_note(self, ticket_id: int, note_text: str) -> None:
        self._request("POST", "/Actions", [{
            "ticket_id": ticket_id,
            "note": note_text,
            "actionarrival": datetime.now(timezone.utc).isoformat(),
            "who": "M2C IoT Integration",
            "isoutgoing": False,
            "sendemail": False,
            "outcome": "Alert Resolved",
        }])
