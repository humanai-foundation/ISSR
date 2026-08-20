#!/bin/bash
# test_phase2.sh
# End-to-end test script for Phase 2: Schema Enforcement, Ontology, and Layer 1 Tagging

set -e  # Exit immediately if any command fails

echo "=========================================================="
echo "ISSR Funding Intelligence - Phase 2 End-to-End Test"
echo "=========================================================="
echo "Phase 2 Scope: Ontology Setup, Synonym Expansion, Tagging"
echo ""

# Activate the virtual environment
echo ">>> Activating virtual environment..."
source .venv/bin/activate
echo "Virtual environment activated."
echo ""

echo "----------------------------------------------------------"
echo "1. Schema Validation (Pre-check)"
echo "----------------------------------------------------------"
echo ">>> Verifying JSON Schema file exists and is valid..."
if [ -f "data/foa_schema.json" ]; then
    echo "data/foa_schema.json exists ($(wc -c < data/foa_schema.json) bytes)"
else
    echo "❌ data/foa_schema.json NOT FOUND"
    exit 1
fi
echo ""

echo "----------------------------------------------------------"
echo "2. Verify Ontology CSV Files"
echo "----------------------------------------------------------"
echo ">>> Checking all 4 ontology CSV files..."
for csv_file in great_act_categories.csv un_sdg_goals.csv research_methods.csv populations.csv; do
    if [ -f "data/ontology/$csv_file" ]; then
        lines=$(wc -l < "data/ontology/$csv_file" | tr -d ' ')
        echo "  $csv_file: $lines lines ($(( lines - 1 )) concepts)"
    else
        echo "  ❌ data/ontology/$csv_file NOT FOUND"
        exit 1
    fi
done
echo ""

echo "----------------------------------------------------------"
echo "3. Load Ontology & Expand Synonyms"
echo "----------------------------------------------------------"
echo ">>> Running: setup-ontology (load CSVs + WordNet synonym expansion)"
PYTHONPATH=src python -m foa_pipeline.cli setup-ontology
echo "Ontology setup complete."
echo ""

echo "----------------------------------------------------------"
echo "4. Verify Ontology in Database"
echo "----------------------------------------------------------"
echo ">>> Querying ontology tables..."
CONCEPT_COUNT=$(sqlite3 data/db/funding_intelligence.db "SELECT COUNT(*) FROM ontology_concepts;")
SYNONYM_COUNT=$(sqlite3 data/db/funding_intelligence.db "SELECT COUNT(*) FROM ontology_synonyms;")
echo "  Concepts loaded: $CONCEPT_COUNT"
echo "  Synonyms generated: $SYNONYM_COUNT"

if [ "$CONCEPT_COUNT" -lt 50 ]; then
    echo "  Warning: Expected 50+ concepts, got $CONCEPT_COUNT"
else
    echo "  Concept count looks good ($CONCEPT_COUNT)"
fi

if [ "$SYNONYM_COUNT" -lt 100 ]; then
    echo "   Warning: Expected 100+ synonyms, got $SYNONYM_COUNT"
else
    echo "  Synonym count looks good ($SYNONYM_COUNT)"
fi

echo ""
echo "  By category:"
sqlite3 data/db/funding_intelligence.db \
    "SELECT category, COUNT(*) as count FROM ontology_concepts GROUP BY category ORDER BY count DESC;"
echo ""

echo "----------------------------------------------------------"
echo "5. Pre-check: FOA Records in Database"
echo "----------------------------------------------------------"
FOA_COUNT=$(sqlite3 data/db/funding_intelligence.db "SELECT COUNT(*) FROM foa_records;")
OPEN_COUNT=$(sqlite3 data/db/funding_intelligence.db "SELECT COUNT(*) FROM foa_records WHERE status='open';")
echo "  Total FOAs: $FOA_COUNT"
echo "  Open FOAs: $OPEN_COUNT"

if [ "$FOA_COUNT" -eq 0 ]; then
    echo "  No FOAs in database! Run Phase 1 first."
    echo "  Run: bash phase-test-scripts/test_phase1.sh"
    exit 1
fi
echo ""

echo "----------------------------------------------------------"
echo "6. Run Tagging Pipeline (L1 + L2)"
echo "----------------------------------------------------------"
echo ">>> Running: tag-all (this may take a few minutes on first run)"
echo "    The L2 tagger will download the all-mpnet-base-v2 model (~420MB)"
echo "    on first run. Subsequent runs use the cached model."
PYTHONPATH=src python -m foa_pipeline.cli tag-all
echo "Tagging pipeline complete."
echo ""

echo "----------------------------------------------------------"
echo "7. Verify Tags in Database"
echo "----------------------------------------------------------"
TAG_COUNT=$(sqlite3 data/db/funding_intelligence.db "SELECT COUNT(*) FROM foa_tags;")
TAGGED_FOAS=$(sqlite3 data/db/funding_intelligence.db "SELECT COUNT(DISTINCT foa_id) FROM foa_tags;")
echo "  Total tags saved: $TAG_COUNT"
echo "  FOAs with at least 1 tag: $TAGGED_FOAS"

if [ "$TAG_COUNT" -eq 0 ]; then
    echo "    Warning: No tags were generated! Check pipeline output above."
else
    echo "   Tags generated successfully"
fi

echo ""
echo "  Tags by source layer:"
sqlite3 data/db/funding_intelligence.db \
    "SELECT source_layer, COUNT(*) as count FROM foa_tags GROUP BY source_layer ORDER BY count DESC;"

echo ""
echo "  Tags by category:"
sqlite3 data/db/funding_intelligence.db \
    "SELECT category, COUNT(*) as count FROM foa_tags GROUP BY category ORDER BY count DESC;"

echo ""
echo "  Top 10 most assigned tags:"
sqlite3 data/db/funding_intelligence.db \
    "SELECT label, category, COUNT(*) as count FROM foa_tags GROUP BY concept_id ORDER BY count DESC LIMIT 10;"
echo ""

echo "----------------------------------------------------------"
echo "8. Export Tagged FOAs to CSV"
echo "----------------------------------------------------------"
echo ">>> Running: export-csv"
PYTHONPATH=src python -m foa_pipeline.cli export-csv
echo "CSV export complete."

if [ -f "data/normalised/foa_normalised.csv" ]; then
    CSV_LINES=$(wc -l < data/normalised/foa_normalised.csv | tr -d ' ')
    echo "   data/normalised/foa_normalised.csv: $CSV_LINES lines"
    echo ""
    echo "  CSV header columns:"
    head -1 data/normalised/foa_normalised.csv | tr ',' '\n' | head -20
else
    echo "   CSV file not created"
fi
echo ""

echo "----------------------------------------------------------"
echo "9. Run Unit Tests (Phase 2 specific)"
echo "----------------------------------------------------------"
echo ">>> Running Phase 2 test suite..."
PYTHONPATH=src python -m pytest tests/test_csv_exporter.py tests/test_synonym_expander.py tests/test_validator.py tests/test_ontology_store.py -v --tb=short
echo ""

echo "=========================================================="
echo "Phase 2 Test Complete!"
echo "=========================================================="
echo ""
echo "Summary:"
echo "   Ontology: $CONCEPT_COUNT concepts, $SYNONYM_COUNT synonyms"
echo "   Tags: $TAG_COUNT tags across $TAGGED_FOAS FOAs"
echo "   CSV: data/normalised/foa_normalised.csv"
echo ""
echo "Database inspection commands:"
echo "  sqlite3 data/db/funding_intelligence.db 'SELECT source_layer, COUNT(*) FROM foa_tags GROUP BY source_layer;'"
echo "  sqlite3 data/db/funding_intelligence.db 'SELECT label, COUNT(*) as c FROM foa_tags GROUP BY concept_id ORDER BY c DESC LIMIT 20;'"
echo "  sqlite3 data/db/funding_intelligence.db 'SELECT r.title, GROUP_CONCAT(t.label, \"; \") FROM foa_records r JOIN foa_tags t ON r.foa_id=t.foa_id GROUP BY r.foa_id LIMIT 5;'"
