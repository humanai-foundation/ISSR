import dataclasses

from foa_pipeline.ingestion.grants_gov import GrantsGovClient, poll_grants


class DummyClient(GrantsGovClient):
    def __init__(self, config):
        super().__init__(config)
        self.calls = []

    def _post(self, endpoint, payload):
        self.calls.append((endpoint, payload))
        if endpoint == config.grants_gov_search_endpoint:
            start = payload.get("startRecordNum")
            if start == 1:
                return {
                    "oppHits": [
                        {"OpportunityID": "100", "OpportunityTitle": "A"},
                        {"OpportunityID": "200", "OpportunityTitle": "B"},
                    ]
                }
            return {"oppHits": []}
        return {"details": {"ok": True}}


def test_poll_grants_pagination(test_config, monkeypatch):
    monkeypatch.setattr("foa_pipeline.ingestion.grants_gov.GrantsGovClient", DummyClient)

    # Set page size to match the test mock using replace since it's frozen
    test_config = dataclasses.replace(test_config, grants_gov_page_size=2)

    # Store globally for DummyClient to access
    global config
    config = test_config

    stats = poll_grants(test_config, dry_run=True)

    assert stats["pages"] == 2
    assert stats["records_written"] == 0


def test_poll_grants_sends_rows_not_numrecords(test_config, monkeypatch):
    """The live search2 API silently ignores "numRecords" and always caps at
    25 hits/page regardless of the requested size -- "rows" is the parameter
    it actually honours. Asserting on the outgoing payload (not just a mocked
    response) is what would have caught the wrong key before it shipped."""
    monkeypatch.setattr("foa_pipeline.ingestion.grants_gov.GrantsGovClient", DummyClient)

    test_config = dataclasses.replace(test_config, grants_gov_page_size=2)

    global config
    config = test_config

    dummy = DummyClient(test_config)
    monkeypatch.setattr(
        "foa_pipeline.ingestion.grants_gov.GrantsGovClient", lambda cfg: dummy
    )

    poll_grants(test_config, dry_run=True)

    search_calls = [call for call in dummy.calls if call[0] == config.grants_gov_search_endpoint]
    assert search_calls, "expected at least one search2 call"
    for _, payload in search_calls:
        assert "rows" in payload, f"expected 'rows' in payload, got keys: {list(payload)}"
        assert payload["rows"] == 2
        assert "numRecords" not in payload
