"""Guards proving the reconciliation tool cannot mutate DynamoDB or Halo."""

import dynamodb_scanner
import halo_readonly_client


def test_halo_readonly_client_exposes_no_mutating_methods():
    client = halo_readonly_client.HaloReadOnlyClient("https://halo.example.test", "id", "secret")
    mutating_names = {"create_ticket", "add_note", "update_ticket", "delete_ticket",
                       "post", "put", "patch", "delete"}
    exposed = {name for name in dir(client) if not name.startswith("_")}
    assert exposed == {"get_ticket"}
    assert exposed.isdisjoint(mutating_names)


def test_dynamodb_scanner_only_ever_calls_scan(monkeypatch):
    calls = []

    class GuardedTable:
        def scan(self, **kwargs):
            calls.append("scan")
            return {"Items": []}

        def __getattr__(self, name):
            if name in ("put_item", "update_item", "delete_item", "batch_write_item"):
                raise AssertionError(f"reconciliation scanner must never call Table.{name}")
            raise AttributeError(name)

    class FakeResource:
        def Table(self, name):
            return GuardedTable()

    monkeypatch.setattr("boto3.resource", lambda *_a, **_k: FakeResource())

    list(dynamodb_scanner.scan_open_records("table", "af-south-1"))
    assert calls == ["scan"]
