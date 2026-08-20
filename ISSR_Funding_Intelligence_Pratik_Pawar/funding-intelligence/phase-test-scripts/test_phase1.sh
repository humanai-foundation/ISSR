#!/bin/bash
# test_phase1.sh
# End-to-end test script for Phase 1: Data Ingestion, Parsing, and Normalisation

set -e # Exit immediately if any command fails

echo "=========================================================="
echo "ISSR Funding Intelligence - Phase 1 End-to-End Test"
echo "=========================================================="

# Activate the virtual environment
echo ">>> Activating virtual environment..."
source .venv/bin/activate
echo "Virtual environment activated."
echo ""

echo "----------------------------------------------------------"
echo "1. Grants.gov REST API Ingestion"
echo "----------------------------------------------------------"
echo ">>> Polling Grants.gov for 'NSF' opportunities and fetching full details..."
make ingest-grants
echo "Grants.gov ingestion complete (Check data/raw/grants_gov.jsonl)."
echo ""

echo "----------------------------------------------------------"
echo "2. NSF RSS Change Detection"
echo "----------------------------------------------------------"
echo ">>> Polling new.nsf.gov RSS feed for new solicitations..."
make ingest-nsf-rss
echo "NSF RSS polling complete. Pending URLs added to data/queues/nsf_queue.db."
echo ""

echo "----------------------------------------------------------"
echo "3. NSF Playwright Web Scraper"
echo "----------------------------------------------------------"
echo ">>> Draining the SQLite queue and scraping NSF pages via headless browser..."
make ingest-nsf-scrape
echo "NSF scraping complete (Check data/raw/nsf_scraped.jsonl)."
echo ""

echo "----------------------------------------------------------"
echo "4. Layout-Aware PDF Parser (pymupdf4llm & pdfplumber)"
echo "----------------------------------------------------------"
echo ">>> Testing PDF parser on the GSoC proposal PDF..."
make parse-pdf pdf_path="Documentation/ISSR_AI_Powered_Funding_Intelligence_GSoC2026_Pratik_Pawar_draft_01.pdf"
echo "PDF parsing complete."
echo ""

echo "----------------------------------------------------------"
echo "5. Schema Validation & DB Normalisation"
echo "----------------------------------------------------------"
echo ">>> Validating all raw JSON records against schema and loading into SQLite..."
make normalise
echo "Normalisation complete! Database updated at data/db/funding_intelligence.db."
echo ""

echo "=========================================================="
echo "Phase 1 Test Complete! All modules are functioning."
echo "=========================================================="
echo "You can inspect the final SQLite database with:"
echo "sqlite3 data/db/funding_intelligence.db 'SELECT source, count(*) FROM foa_records GROUP BY source;'"
