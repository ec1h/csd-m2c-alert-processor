"""Tests for the read-only DynamoDB scanner (pagination, projection, filter)."""

import dynamodb_scanner


class FakeTable:
    def __init__(self, pages):
        self._pages = pages
        self.scan_calls = []

    def scan(self, **kwargs):
        self.scan_calls.append(kwargs)
        return self._pages.pop(0)


def test_scan_open_records_paginates(monkeypatch):
    pages = [
        {"Items": [{"fingerprint": "fp1"}], "LastEvaluatedKey": {"fingerprint": "fp1"}},
        {"Items": [{"fingerprint": "fp2"}]},
    ]
    fake_table = FakeTable(pages)

    class FakeResource:
        def Table(self, name):
            return fake_table

    monkeypatch.setattr("boto3.resource", lambda *_a, **_k: FakeResource())

    records = list(dynamodb_scanner.scan_open_records("table", "af-south-1"))

    assert [r["fingerprint"] for r in records] == ["fp1", "fp2"]
    assert len(fake_table.scan_calls) == 2
    assert "ExclusiveStartKey" not in fake_table.scan_calls[0]
    assert fake_table.scan_calls[1]["ExclusiveStartKey"] == {"fingerprint": "fp1"}
    assert fake_table.scan_calls[0]["ExpressionAttributeValues"] == {":open": "open"}
    assert fake_table.scan_calls[0]["FilterExpression"] == "#s = :open"
