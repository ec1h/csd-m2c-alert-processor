"""In-process, stdlib-only mock of the HaloITSM endpoints used by HaloClient.

Runs a real HTTP server on loopback so `src/halo_client.py`'s urllib requests
are exercised unmodified (status codes, error body parsing, auth header).
Scenario behavior is controlled by mutating `server.scenario` directly from
the same process - no HTTP control channel needed.

Usage:
    from mock_halo_server import MockHaloServer

    with MockHaloServer() as server:
        server.scenario["create_ticket"] = "ticket_type_not_found"
        halo = HaloClient(server.base_url, "id", "secret")
        ...
        assert len(server.requests) == 1
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer

# Reproduced verbatim from CloudWatch logs (error_dump.json) so error-body
# parsing in HaloClient._request is exercised against the real text.
TICKET_TYPE_NOT_FOUND_BODY = (
    'Ticket Type not found\\; this could be due to you not having create '
    "permissions for the type or the type not existing"
)


@dataclass
class RecordedRequest:
    method: str
    path: str
    body: object


@dataclass
class _ServerState:
    scenario: dict = field(default_factory=lambda: {
        "auth": "ok",  # ok | failed
        "create_ticket": "ok",  # ok | ticket_type_not_found | server_error
        "add_note": "ok",  # ok | server_error
        "valid_ticket_types": {64},
        "next_ticket_id": 1001,
    })
    requests: list = field(default_factory=list)


def _make_handler(state: _ServerState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silence default stderr access logging

        def _read_raw_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", 0))
            return self.rfile.read(length) if length else b""

        def _reply(self, status: int, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            raw = self._read_raw_body()

            # /auth/token sends application/x-www-form-urlencoded, not JSON.
            if self.path == "/auth/token":
                state.requests.append(RecordedRequest(self.command, self.path, raw.decode()))
                return self._handle_auth()

            body = json.loads(raw) if raw else None
            state.requests.append(RecordedRequest(self.command, self.path, body))
            if self.path == "/api/tickets":
                return self._handle_create_ticket(body)
            if self.path == "/api/Actions":
                return self._handle_add_note(body)
            self._reply(404, {"error": f"no mock route for {self.path}"})

        def _handle_auth(self):
            if state.scenario["auth"] == "failed":
                return self._reply(401, {"error": "invalid_client"})
            self._reply(200, {"access_token": "mock-token", "expires_in": 3600})

        def _handle_create_ticket(self, body):
            mode = state.scenario["create_ticket"]
            if mode == "server_error":
                return self._reply(500, {"error": "internal server error"})

            tickettype_id = (body or [{}])[0].get("tickettype_id")
            valid_types = state.scenario["valid_ticket_types"]
            if mode == "ticket_type_not_found" or tickettype_id not in valid_types:
                return self._reply(400, TICKET_TYPE_NOT_FOUND_BODY)

            ticket_id = state.scenario["next_ticket_id"]
            state.scenario["next_ticket_id"] += 1
            self._reply(200, [{"id": ticket_id}])

        def _handle_add_note(self, body):
            if state.scenario["add_note"] == "server_error":
                return self._reply(500, {"error": "internal server error"})
            self._reply(200, [{"id": 1}])

    return Handler


class MockHaloServer:
    """Background-thread HTTP server backing a fake Halo instance."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self._state = _ServerState()
        self._httpd = HTTPServer((host, port), _make_handler(self._state))
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def scenario(self) -> dict:
        return self._state.scenario

    @property
    def requests(self) -> list:
        return self._state.requests

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "MockHaloServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def __enter__(self) -> "MockHaloServer":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()
