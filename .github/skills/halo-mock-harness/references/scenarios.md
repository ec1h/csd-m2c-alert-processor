# Mock Halo Scenario Catalog

All scenarios are set by mutating `server.scenario` (see
[../scripts/mock_halo_server.py](../scripts/mock_halo_server.py)) or passed
as `--scenario` to [../scripts/replay_alert.py](../scripts/replay_alert.py).

| `scenario["auth"]` | Effect |
|---|---|
| `"ok"` (default) | `/auth/token` returns 200 with a mock bearer token |
| `"failed"` | `/auth/token` returns 401 -> `HaloAuthError` in `HaloClient._get_token` |

| `scenario["create_ticket"]` | Effect |
|---|---|
| `"ok"` (default) | `/api/tickets` returns 200 with an incrementing ticket id, if `tickettype_id` is in `valid_ticket_types` |
| `"ticket_type_not_found"` | `/api/tickets` returns 400 with the exact body observed in `error_dump.json` (`Ticket Type not found\; this could be due to you not having create permissions for the type or the type not existing`) regardless of `tickettype_id` |
| `"server_error"` | `/api/tickets` returns 500 |

Note: even with `create_ticket="ok"`, a `tickettype_id` outside
`scenario["valid_ticket_types"]` (default `{64}`) also produces the
`ticket_type_not_found` response - this models the real root cause seen in
production logs (a `tickettype_id` not permitted/known for this Halo client),
without needing a separate explicit scenario flag.

| `scenario["add_note"]` | Effect |
|---|---|
| `"ok"` (default) | `/api/Actions` returns 200 |
| `"server_error"` | `/api/Actions` returns 500 -> `HaloRequestError` in `add_note` (resolved-alert path) |

## Exact error bodies to preserve

When adding a new failure scenario reproduced from real logs, copy the error
body text verbatim (including any escaping) - `HaloClient._request` logs and
surfaces it as-is, and tests may assert on it.
