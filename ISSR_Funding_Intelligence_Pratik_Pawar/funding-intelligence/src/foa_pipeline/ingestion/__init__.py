"""Source connectors: Grants.gov API, NSF RSS/scraping, and PDF retrieval."""

from .grants_gov import GrantsGovClient, poll_grants
from .nsf_awards import NSFAwardsClient, harvest_awards
from .nsf_rss import poll_nsf_rss
from .nsf_scraper import drain_nsf_queue
from .pdf_downloader import run_downloader

__all__ = [
    "GrantsGovClient",
    "poll_grants",
    "NSFAwardsClient",
    "harvest_awards",
    "poll_nsf_rss",
    "drain_nsf_queue",
    "run_downloader",
]
