# Tests

Unit tests for alert routing, ticket building, and the webhook handler response contract, using in-memory fakes for Halo and DynamoDB (no AWS credentials or network access required). The read-only reconciliation tool has its own test suite. `test_halo_mock_e2e.py` adds an e2e-local/replay layer against a loopback mock Halo server (see `.github/skills/halo-mock-harness/`).

## Live Halo integration (opt-in, stage 2)

`test_halo_live_integration.py` talks to a **real** Halo instance and is skipped
unless `HALO_LIVE_BASE_URL`, `HALO_LIVE_CLIENT_ID`, and `HALO_LIVE_CLIENT_SECRET`
are all set - it never runs as part of a plain `pytest` invocation or the
`tests.yml` CI workflow. Run it manually once real access is granted:

```bash
HALO_LIVE_BASE_URL=https://ec1helpdesk.haloitsm.com \
HALO_LIVE_CLIENT_ID=... \
HALO_LIVE_CLIENT_SECRET=... \
pytest -q tests/test_halo_live_integration.py
```

That only checks OAuth token acquisition (no side effects). To also verify the
configured `tickettype_id`/`team_id` actually work by creating one real Halo
ticket, add `HALO_LIVE_ALLOW_TICKET_CREATION=1` (and optionally
`HALO_LIVE_TICKET_TYPE_ID`/`HALO_LIVE_TEAM_ID` to override the defaults) -
this is the direct regression check for the "Ticket Type not found" 400s in
`error_dump.json`. The same test is wired into the gated
`live-halo-smoke.yml` workflow (`workflow_dispatch` only, `uat` environment).
