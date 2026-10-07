---
name: halo-mock-harness
description: 'Use when testing the M2C alert processor without live HaloITSM access (stage 1, while org/API access is pending): mocking HaloITSM auth/ticket/note responses (success and failure, e.g. HTTP 400 "Ticket Type not found"), running the full unit -> integration -> local e2e -> replay test pyramid, or reconstructing regression fixtures from CloudWatch logs like error_dump.json.'
---

# Halo Mock Harness

Simulates HaloITSM locally so the M2C alert processor can be tested end-to-end
without real Halo credentials or network access. This is a **stage 1** stand-in:
once live Halo access is granted, replace the mock base URL with the real one
and re-run the same fixtures as a sanity check.

## When to Use
- No live HaloITSM access yet, but you need confidence beyond unit tests
- Extending Halo failure coverage (auth failure, ticket-type errors, 5xx)
- Reproducing a specific CloudWatch-logged failure (e.g. the `[HALO ERROR]`
  "Ticket Type not found" 400s in [error_dump.json](../../../error_dump.json))
- Deciding which test layer a new case belongs in

## Test Pyramid (bottom to top)

| Layer | What it exercises | How |
|---|---|---|
| Unit | `routing.py`, `ticket_builder.py` — pure functions | Plain pytest, no mocking |
| Integration | `lambda_function.py` orchestration | In-memory `FakeHalo`/`FakeDedup` (see [tests/test_lambda_handler.py](../../../tests/test_lambda_handler.py)) — no network |
| E2E local | Real `HaloClient` urllib request/response/error parsing | [scripts/mock_halo_server.py](./scripts/mock_halo_server.py) on loopback HTTP |
| Replay | Full `lambda_handler` against a real-shaped payload | [scripts/replay_alert.py](./scripts/replay_alert.py) + a fixture from [fixtures/](./fixtures/) |

Add new cases at the lowest layer that can express them. Only reach for the
mock HTTP server when you need to prove `HaloClient`'s own request/error
handling (status codes, error body parsing) — everything about routing,
dedup, and retry semantics is already covered by the in-memory fakes.

## Procedure

### 1. Integration layer — extend the in-memory fakes first
`FakeHalo`/`FakeDedup` in `tests/test_lambda_handler.py` already model success
and a single injectable failure (`raise_on_create`, `raise_on_save`). Prefer
adding scenarios here (e.g. `raise_on_add_note`) over reaching for the HTTP
mock — it's faster and doesn't need a server. Match real exception shapes:
`HaloAuthError(msg)` and `HaloRequestError(status_code, msg)` from
[src/handlers/alert-processor/halo_client.py](../../../src/handlers/alert-processor/halo_client.py).

### 2. E2E layer — run the local mock Halo server
[scripts/mock_halo_server.py](./scripts/mock_halo_server.py) is a stdlib-only
(`http.server`) fake of Halo's `/auth/token`, `/api/tickets`, and
`/api/Actions` endpoints. It runs in-process (a background thread), so tests
control its behavior by mutating `server.scenario` directly — no HTTP control
channel needed.

```python
from mock_halo_server import MockHaloServer

with MockHaloServer() as server:
    server.scenario["create_ticket"] = "ticket_type_not_found"  # or "ok", "auth_failed", "server_error"
    halo = HaloClient(server.base_url, "test-id", "test-secret")
    ...
    assert server.requests[-1].path == "/api/tickets"
```

See [references/scenarios.md](./references/scenarios.md) for the full
scenario catalog and the exact error bodies reproduced from Halo.

### 3. Replay layer — run a full payload through `lambda_handler`
[scripts/replay_alert.py](./scripts/replay_alert.py) wires up real
`lambda_function.lambda_handler`, a real `HaloClient` pointed at the mock
server, and an in-memory dedup store (same shape as `FakeDedup` — DynamoDB is
never touched). Use it to reproduce a specific broken invocation end-to-end:

```bash
python .github/skills/halo-mock-harness/scripts/replay_alert.py \
  .github/skills/halo-mock-harness/fixtures/tamper_firing.json \
  --scenario ticket_type_not_found
```

Run it again with `--scenario ok` to confirm the same payload succeeds once
the ticket type / permissions issue is fixed on the Halo side.

### 4. Reconstructing fixtures from CloudWatch logs
**Important limitation:** `error_dump.json` only has print-statement logs, not
the original Alertmanager JSON bodies. Failed-ticket lines
(`[ERROR] Failed for SN:X: HTTP Error 400`) only give you the device `SN` —
not the `M2C` alert type or `fingerprint`, since those aren't printed on that
code path. Fixtures in [fixtures/](./fixtures/) are therefore **synthetic
reconstructions** built from a known mapped alert type (see
[routing.py](../../../src/handlers/alert-processor/routing.py) for the valid `M2C` label values), not
byte-for-byte replays of the original request. When you get real payload
exports (Halo audit log, Grafana silence history, or raw webhook capture),
drop them into `fixtures/` instead and prefer those.
`fixtures/` currently has one firing fixture per mapped `M2C` alert type
(`low_battery_firing.json`, `tamper_firing.json`, `no_usage_firing.json`,
`excessive_usage_firing.json`, `no_communication_firing.json`,
`reverse_flow_firing.json`, `device_reboot_firing.json`) plus
`low_battery_resolved.json` for the resolved/add-note path. All are covered
by [tests/test_halo_mock_e2e.py](../../../tests/test_halo_mock_e2e.py). The
resolved fixture only produces `ticket_updated` when replayed against a
dedup store that already has the matching fingerprint open — chain a firing
replay first and pass the same `InMemoryDedup` instance to `replay()` (see
`test_resolved_alert_adds_note_to_existing_ticket`).
To add a new fixture: copy an existing one, set `labels.SN` /
`labels.MeterSN` to the real device serial from the log line, set
`labels.M2C` to the actual alert type once known, and give it a unique
`fingerprint`.

## Root Cause Note
The `[HALO ERROR] POST /tickets -> HTTP 400: "Ticket Type not found..."`
pattern in the logs is a Halo-side configuration issue (the `tickettype_id`
sent — driven by `HALO_TICKET_TYPE_ID` — isn't valid/permitted for this
client in the target Halo org), not a payload bug. The mock harness
reproduces this as an environment/config problem
(`server.scenario["create_ticket"] = "ticket_type_not_found"`), so don't
spend time trying to "fix" it via payload changes — confirm the correct
ticket type ID with the Halo owner once access is granted.

## Stage 2 — once Halo access is granted
Swap the mock for the real thing with
[tests/test_halo_live_integration.py](../../../tests/test_halo_live_integration.py)
(opt-in, skipped by default — see [tests/README.md](../../../tests/README.md))
and the gated `live-halo-smoke.yml` workflow. It first checks OAuth token
acquisition only (no side effects), then — opt-in via
`HALO_LIVE_ALLOW_TICKET_CREATION=1` — creates one real ticket to confirm the
actual `tickettype_id`/`team_id` values, which is the only thing this whole
mock harness cannot prove for you.
