"""Shared test fixtures for the ISSR Funding Intelligence pipeline."""

import sqlite3
from pathlib import Path

import pytest

from foa_pipeline.config import Config


@pytest.fixture
def test_config(tmp_path):
    """Test configuration using temporary directories."""
    return Config(
        grants_gov_base_url="https://api.grants.gov/v1/api",
        grants_gov_search_endpoint="search2",
        grants_gov_fetch_endpoint="fetchOpportunity",
        grants_gov_page_size=25,
        grants_gov_max_pages=1,
        grants_gov_query="{}",
        nsf_rss_url="https://example.com/rss",
        nsf_scraper_rate_limit=10.0,
        nsf_scraper_max_concurrent=1,
        sqlite_db_path=tmp_path / "queue.db",
        app_db_path=tmp_path / "app.db",
        raw_output_dir=tmp_path / "raw",
        normalised_output_dir=tmp_path / "normalised",
        embeddings_cache_dir=tmp_path / "embeddings",
        ontology_dir=Path(__file__).parent.parent / "data" / "ontology",
        evaluation_dir=tmp_path / "evaluation",
        spacy_model="en_core_web_lg",
        embedding_model="sentence-transformers/all-mpnet-base-v2",
        cosine_thresholds={"default": 0.75},
        enable_layer3_llm=False,
        ollama_base_url="http://localhost:11434",
        ollama_model="mistral:7b-instruct",
        api_host="127.0.0.1",
        api_port=8000,
        api_reload=False,
        api_cors_origins=["http://localhost:8000"],
        api_rate_limit_per_minute=120,
        api_export_max_rows=10000,
        log_level="DEBUG",
        user_agent="test-agent",
        schema_version="1.0",
    )


@pytest.fixture
def sample_foa():
    """A complete sample normalised FOA record for testing."""
    return {
        "schema_version": "1.0",
        "foa_id": "test-uuid-001",
        "source": "grants_gov",
        "source_id": "123456",
        "source_url": "https://www.grants.gov/view-opportunity.html?oppId=123456",
        "title": "Climate Change Impact on Rural Communities",
        "agency": "National Science Foundation",
        "agency_code": "NSF",
        "opportunity_number": "NSF-25-001",
        "cfda_numbers": ["47.075"],
        "posted_date": "2025-06-01",
        "close_date": "2025-09-15",
        "archive_date": None,
        "status": "open",
        "funding_instrument": "grant",
        "award_floor": 50000.0,
        "award_ceiling": 500000.0,
        "expected_awards": 10,
        "estimated_funding": 5000000.0,
        "eligibility": ["Universities", "Non-profits"],
        "program_description": (
            "This program supports research on climate change impacts on rural "
            "communities, including agricultural systems, water resources, and "
            "community resilience. The program encourages machine learning and "
            "geospatial analysis approaches to study environmental change in "
            "vulnerable populations including indigenous peoples and low-income "
            "rural communities."
        ),
        "eligibility_description": (
            "Eligible applicants include institutions of higher education, "
            "non-profit organizations, and state and local governments."
        ),
        "additional_info": None,
        "tags": [],
        "ingestion_date": "2025-06-01T00:00:00Z",
        "last_updated": "2025-06-01T00:00:00Z",
        "raw_payload": {},
    }


@pytest.fixture
def sample_raw_grants_gov():
    """A sample raw Grants.gov record (pre-normalisation).

    Uses the real API response structure: details.data.synopsis
    """
    return {
        "schema_version": "1.0",
        "source": "grants_gov",
        "source_id": "789012",
        "title": "Health Disparities in Urban Communities",
        "posted_date": "06/15/2025",
        "close_date": "09/30/2025",
        "raw_url": "https://www.grants.gov/view-opportunity.html?oppId=789012",
        "fetched_at": "2025-06-01T00:00:00Z",
        "raw_payload": {
            "search_hit": {
                "OpportunityID": "789012",
                "OpportunityTitle": "Health Disparities in Urban Communities",
                "AgencyName": "Department of Health and Human Services",
                "AgencyCode": "HHS",
                "OpenDate": "06/15/2025",
                "CloseDate": "09/30/2025",
                "OpportunityNumber": "HHS-2025-ACF-002",
            },
            "details": {
                "data": {
                    "opportunityNumber": "HHS-2025-ACF-002",
                    "cfdas": [
                        {"cfdaNumber": "93.103", "programTitle": "Health Disparities"}
                    ],
                    "synopsisAttachmentFolders": [],
                    "synopsis": {
                        "agencyName": "Department of Health and Human Services",
                        "agencyCode": "HHS",
                        "synopsisDesc": (
                            "This program supports research on health disparities "
                            "in urban communities."
                        ),
                        "applicantEligibilityDesc": "Universities, Non-profits, State governments",
                        "applicantTypes": [
                            {
                                "id": "25",
                                "description": (
                                    "Others (see text field entitled \"Additional "
                                    "Information on Eligibility\" for clarification)"
                                ),
                            }
                        ],
                        "awardFloor": "50000",
                        "awardCeiling": "500000",
                        "estimatedFunding": "5000000",
                        "numberOfAwards": "10",
                        "fundingInstruments": [
                            {"id": "G", "description": "Grant"}
                        ],
                        "postingDateStr": "06/15/2025",
                        "responseDateStr": "09/30/2025",
                    },
                },
            },
        },
    }


@pytest.fixture
def in_memory_db():
    """In-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()
