import types

from foa_pipeline.ingestion.nsf_rss import poll_nsf_rss


def test_nsf_rss_queue(test_config, monkeypatch):

    feed = types.SimpleNamespace(
        bozo=False,
        entries=[{"link": "https://www.nsf.gov/funding/1"}, {"link": "https://www.nsf.gov/funding/2"}],
    )

    monkeypatch.setattr("foa_pipeline.ingestion.nsf_rss.feedparser.parse", lambda _: feed)
    stats = poll_nsf_rss(test_config, dry_run=False)

    assert stats["total"] == 2
    assert stats["inserted"] == 2
