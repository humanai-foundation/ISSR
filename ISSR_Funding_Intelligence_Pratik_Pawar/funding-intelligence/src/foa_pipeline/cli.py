import argparse
import json
import logging

from .config import get_config
from .ingestion.grants_gov import poll_grants
from .ingestion.nsf_rss import poll_nsf_rss
from .logging_setup import setup_logging

# Boilerplate PDFs that are generic and don't describe a specific FOA
SKIP_URLS = {
    "https://resources.research.gov/common/attachment/Common/"
    "Grants_govProposal_Processing_in_Research.pdf",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ISSR Funding Intelligence Pipeline CLI"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without writing outputs"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── Ingestion ──
    subparsers.add_parser("grants-poll", help="Poll Grants.gov API")
    subparsers.add_parser("nsf-rss-poll", help="Poll NSF RSS feed")
    subparsers.add_parser(
        "nsf-listing-crawl",
        help="Crawl NSF's full funding-search results (not just the RSS "
        "feed's recent-postings window), dedup against existing FOAs by "
        "fuzzy title match, and queue genuinely new ones for nsf-scrape",
    )
    sub_scrape = subparsers.add_parser("nsf-scrape", help="Scrape pending NSF URLs")
    sub_scrape.add_argument(
        "--max-pages", type=int, default=50, help="Max pages to scrape"
    )
    subparsers.add_parser(
        "harvest-openalex",
        help="Vendor the OpenAlex field taxonomy (CC0) to data/ontology/ "
        "as a staged, inactive CSV",
    )
    sub_awards = subparsers.add_parser(
        "harvest-nsf-awards",
        help="Harvest NSF awards as a directorate-labelled evaluation corpus "
        "(written to the evaluation directory, never to the FOA database)",
    )
    sub_awards.add_argument(
        "--per-directorate",
        type=int,
        default=200,
        help="Max awards to keep per directorate (default: 200)",
    )
    sub_awards.add_argument(
        "--date-start", default="01/01/2023", help="MM/DD/YYYY (default: 01/01/2023)"
    )
    sub_awards.add_argument(
        "--date-end", default="12/31/2025", help="MM/DD/YYYY (default: 12/31/2025)"
    )

    # ── Normalisation ──
    subparsers.add_parser("normalise", help="Normalise raw records to canonical schema")
    subparsers.add_parser("enrich-foas", help="Download and parse FOA PDFs for Grants.gov and NSF")
    subparsers.add_parser(
        "extract-budget", help="Extract complex budget tiers from FOA text using LLM"
    )

    # ── Ontology ──
    subparsers.add_parser(
        "setup-ontology", help="Load ontology CSVs and expand synonyms"
    )
    mine_syn_p = subparsers.add_parser(
        "mine-synonyms", help="Mine high-confidence L2 tags for WordNet synonyms"
    )
    mine_syn_p.add_argument(
        "--threshold",
        type=float,
        default=0.88,
        help="Minimum L2 confidence to consider for mining",
    )

    # ── Tagging ──
    tag_all_p = subparsers.add_parser("tag-all", help="Run tagging pipeline on all FOAs")
    tag_all_p.add_argument("--limit", type=int, default=0, help="Limit number of FOAs to tag")
    tag_all_p.add_argument(
        "--open-only",
        dest="all_statuses",
        action="store_false",
        default=True,
        help="Tag only FOAs still accepting applications. Off by default: "
        "skipping closed FOAs makes gold-set metrics decay as the calendar "
        "advances and gold FOAs expire. Search results are unaffected either "
        "way, since the vector index filters to open FOAs separately.",
    )
    tag_all_p.add_argument(
        "--llm-backstop",
        action="store_true",
        default=False,
        help="Run an LLM classification pass on FOAs that L1+L2+L3+CFDA leave "
        "with zero tags. Off by default: unlike L3's narrow A-or-B calls, "
        "this is an open-ended classification per zero-evidence FOA against "
        "the whole ontology, slow enough that it should not run on every "
        "routine tag-all/evaluate iteration.",
    )

    # ── Embeddings ──
    subparsers.add_parser(
        "precompute-embeddings",
        help="Pre-compute ontology embeddings for Layer 2",
    )

    # ── Export ──
    sub_csv = subparsers.add_parser("export-csv", help="Export FOAs to CSV")
    sub_csv.add_argument("--output", "-o", default=None, help="Output file path")

    sub_json = subparsers.add_parser(
        "export-json",
        help="Export FOAs to JSON (full nested records, unlike the flattened CSV)",
    )
    sub_json.add_argument("--output", "-o", default=None, help="Output file path")
    sub_json.add_argument(
        "--include-raw",
        dest="include_raw",
        action="store_true",
        help="Include the untouched upstream API payload. Off by default: it is "
        "large, source-specific, and already kept in data/raw/*.jsonl",
    )

    # ── Search ──
    sub_search = subparsers.add_parser(
        "search", help="Search FOAs by researcher profile"
    )
    sub_search.add_argument("--profile", required=True, help="Research profile text")
    sub_search.add_argument("--k", type=int, default=10, help="Number of results")

    # ── Server ──
    subparsers.add_parser("serve", help="Start the FastAPI server")

    # ── Evaluation ──
    eval_p = subparsers.add_parser("evaluate", help="Run evaluation on labelled set")
    eval_p.add_argument(
        "--gold",
        action="store_true",
        help="Evaluate DB tags against the hand-labelled gold set "
        "(default: re-tag in-memory against the LLM-generated silver set)",
    )
    sep_p = subparsers.add_parser(
        "diagnose-separation",
        help="Report how well Layer 2 cosine scores separate correct from "
        "incorrect tags (run an evaluation first)",
    )
    sep_p.add_argument(
        "--eval-set",
        choices=["gold", "silver"],
        default="gold",
        help="Which run's error logs to read (default: gold)",
    )
    bench_p = subparsers.add_parser(
        "benchmark-disciplines",
        help="Rank NSF directorates on the agency-labelled award corpus "
        "(run harvest-nsf-awards first)",
    )
    bench_p.add_argument(
        "--limit", type=int, default=None, help="Score only the first N awards"
    )
    bench_p.add_argument(
        "--top-k", type=int, default=3, help="k for top-k accuracy (default: 3)"
    )
    bench_p.add_argument(
        "--split",
        choices=["tune", "eval", "all"],
        default="all",
        help="Corpus half to score. Use 'tune' while editing concept "
        "descriptions and 'eval' when reporting, so results are held out "
        "from the edits that produced them (default: all)",
    )
    annot_p = subparsers.add_parser(
        "annotate-eval-set",
        help="Draft SILVER labels for eval_set_50.json with the local LLM "
        "(never the gold set; requires Ollama)",
    )
    annot_p.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Annotate only this ontology category; repeatable. Omit for all. "
        "Only FOAs missing the category are touched.",
    )
    annot_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-annotate even where labels already exist, discarding them",
    )
    curate_p = subparsers.add_parser(
        "curate-eval-set", help="Generate a stratified sample of FOAs for evaluation"
    )
    curate_p.add_argument("--size", type=int, default=50, help="Number of FOAs to sample")

    # ── PDF Parse ──
    sub_pdf = subparsers.add_parser("pdf-parse", help="Parse a FOA PDF")
    sub_pdf.add_argument("pdf_path", help="Path to the PDF file")

    sub_dl = subparsers.add_parser(
        "download-pdfs", help="Asynchronously download and parse pending PDFs"
    )
    sub_dl.add_argument("--dry-run", action="store_true", help="Do not actually download")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = get_config()
    setup_logging(config.log_level)

    if args.command == "grants-poll":
        stats = poll_grants(config, dry_run=args.dry_run)
        logging.info("Grants.gov poll complete: %s", stats)

    elif args.command == "nsf-rss-poll":
        stats = poll_nsf_rss(config, dry_run=args.dry_run)
        logging.info("NSF RSS poll complete: %s", stats)

    elif args.command == "nsf-listing-crawl":
        from .ingestion.nsf_listing_scraper import discover_nsf_listings

        stats = discover_nsf_listings(config, dry_run=args.dry_run)
        logging.info("NSF listing crawl complete: %s", stats)

    elif args.command == "nsf-scrape":
        from .ingestion.nsf_scraper import drain_nsf_queue

        stats = drain_nsf_queue(
            config, max_pages=args.max_pages, dry_run=args.dry_run
        )
        logging.info("NSF scrape complete: %s", stats)

    elif args.command == "harvest-openalex":
        from .ingestion.openalex import harvest_openalex_fields

        stats = harvest_openalex_fields(config.ontology_dir)
        logging.info("OpenAlex harvest complete: %s", stats)

    elif args.command == "harvest-nsf-awards":
        from .ingestion.nsf_awards import harvest_awards

        stats = harvest_awards(
            config,
            date_start=args.date_start,
            date_end=args.date_end,
            per_directorate=args.per_directorate,
        )
        logging.info("NSF award harvest complete: %s", stats)

    elif args.command == "normalise":
        _run_normalise(config, args)

    elif args.command == "enrich-foas":
        _run_enrich_foas(config)

    elif args.command == "extract-budget":
        _run_extract_budget(config)

    elif args.command == "setup-ontology":
        _run_setup_ontology(config)

    elif args.command == "tag-all":
        _run_tag_all(config, args)

    elif args.command == "mine-synonyms":
        _run_mine_synonyms(config, args)

    elif args.command == "curate-eval-set":
        _run_curate_eval_set(config, args)

    elif args.command == "precompute-embeddings":
        _run_precompute_embeddings(config)

    elif args.command == "export-json":
        _run_export_json(config, args)

    elif args.command == "export-csv":
        _run_export_csv(config, args)

    elif args.command == "search":
        _run_search(config, args)

    elif args.command == "serve":
        _run_server(config)

    elif args.command == "evaluate":
        _run_evaluate(args)

    elif args.command == "diagnose-separation":
        _run_diagnose_separation(config, args)

    elif args.command == "benchmark-disciplines":
        _run_benchmark_disciplines(config, args)

    elif args.command == "annotate-eval-set":
        from .evaluation.synthetic_annotator import annotate_foas

        annotate_foas(categories=args.categories, overwrite=args.overwrite)

    elif args.command == "pdf-parse":
        _run_pdf_parse(args)

    elif args.command == "download-pdfs":
        _run_download_pdfs(config, args)


def _run_download_pdfs(config, args) -> None:
    """Run the async PDF downloader."""
    from .ingestion.pdf_downloader import run_downloader
    stats = run_downloader(config)
    logging.info("PDF Downloader finished. Stats: %s", stats)


def _run_normalise(config, args) -> None:
    """Normalise all raw records from data/raw/ into data/normalised/."""
    from .normalisation.normaliser import normalise_record
    from .normalisation.validator import validate_record
    from .storage.database import Database
    from .storage.jsonl import ensure_dir

    ensure_dir(config.normalised_output_dir)
    db = Database(config.app_db_path)

    raw_dir = config.raw_output_dir
    total = 0
    valid = 0

    for jsonl_file in raw_dir.glob("*.jsonl"):
        source = "grants_gov" if "grants" in jsonl_file.stem else "nsf_scraper"
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue

                total += 1
                try:
                    normalised = normalise_record(raw, source)
                    is_ok, errors = validate_record(normalised)
                    if is_ok:
                        db.upsert_foa(normalised)
                        valid += 1
                    else:
                        logging.warning(
                            "Validation errors for %s: %s",
                            normalised.get("foa_id"),
                            errors[:3],
                        )
                except Exception as exc:
                    logging.warning("Normalisation failed: %s", exc)

    db.close()
    logging.info("Normalised %d/%d records into database", valid, total)


def _run_enrich_foas(config) -> None:
    import urllib.request
    from pathlib import Path

    from .ingestion.grants_gov import GrantsGovClient
    from .parsing.pdf_parser import extract_structured_fields, parse_foa_pdf
    from .storage.database import Database

    db = Database(config.app_db_path)
    client = GrantsGovClient(config)
    pdf_dir = Path("data/pdfs")

    records, total = db.list_foas(page=1, size=100000)
    enriched_count = 0
    skipped_count = 0
    error_count = 0

    logging.info("Scanning %d FOA records for PDF enrichment...", total)

    for idx, foa in enumerate(records):
        source = foa.get("source")
        raw_payload = foa.get("raw_payload", {})

        # Handle case where raw_payload was stored as a JSON string
        if isinstance(raw_payload, str):
            try:
                raw_payload = json.loads(raw_payload)
            except (json.JSONDecodeError, TypeError):
                raw_payload = {}

        # Check if already enriched
        if raw_payload.get("pdf_enriched"):
            skipped_count += 1
            continue

        all_pdf_text = []
        structured_fields = {}

        # GRANTS.GOV LOGIC
        if source == "grants_gov":
            extracted_pdf_ids = raw_payload.get("extracted_pdf_ids", [])
            if not extracted_pdf_ids:
                continue
            logging.info(
                "[%d/%d] Enriching Grants.gov FOA %s (%s) with %d attachments",
                idx + 1,
                total,
                foa["foa_id"],
                (foa.get("title") or "")[:50],
                len(extracted_pdf_ids),
            )

            for att_id in extracted_pdf_ids:
                out_path = pdf_dir / "grants_gov" / f"{foa['foa_id']}_{att_id}.pdf"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                if not out_path.exists():
                    success = client.download_attachment(att_id, out_path)
                    if not success:
                        error_count += 1
                        continue

                try:
                    result = parse_foa_pdf(out_path)
                    text_content = "\n".join([sec.content for sec in result.sections])
                    if len(text_content.strip()) > 50:  # Skip trivially small PDFs
                        all_pdf_text.append(text_content)

                    fields = extract_structured_fields(result)
                    structured_fields.update(fields)
                except Exception as exc:
                    logging.warning("Failed to parse PDF %s: %s", out_path, exc)
                    error_count += 1

        # NSF LOGIC
        elif source == "nsf_scraper":
            pdf_links = raw_payload.get("pdf_links", [])
            # Filter out boilerplate PDFs
            pdf_links = [link for link in pdf_links if link not in SKIP_URLS]
            if not pdf_links:
                continue
            logging.info(
                "[%d/%d] Enriching NSF FOA %s (%s) with %d PDF links",
                idx + 1,
                total,
                foa["foa_id"],
                (foa.get("title") or "")[:50],
                len(pdf_links),
            )

            for i, link in enumerate(pdf_links):
                out_path = pdf_dir / "nsf" / f"{foa['foa_id']}_{i}.pdf"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                if not out_path.exists():
                    try:
                        urllib.request.urlretrieve(link, out_path)
                    except Exception as exc:
                        logging.warning("Failed to download NSF PDF %s: %s", link, exc)
                        error_count += 1
                        continue

                try:
                    result = parse_foa_pdf(out_path)
                    text_content = "\n".join([sec.content for sec in result.sections])
                    if len(text_content.strip()) > 50:
                        all_pdf_text.append(text_content)

                    fields = extract_structured_fields(result)
                    structured_fields.update(fields)
                except Exception as exc:
                    logging.warning("Failed to parse PDF %s: %s", out_path, exc)
                    error_count += 1
        else:
            continue

        # Update FOA with text and structured fields
        if all_pdf_text:
            combined_text = "\n\n=== PDF ATTACHMENT ===\n\n".join(all_pdf_text)
            existing_info = foa.get("additional_info") or ""
            foa["additional_info"] = (
                existing_info + "\n\n=== PDF ATTACHMENTS ===\n\n" + combined_text
            )

            # Merge extracted structured fields (don't overwrite if already exists and is non-null)
            if "award_floor" in structured_fields and not foa.get("award_floor"):
                foa["award_floor"] = structured_fields["award_floor"]
            if "award_ceiling" in structured_fields and not foa.get("award_ceiling"):
                foa["award_ceiling"] = structured_fields["award_ceiling"]
            if "close_date_raw" in structured_fields and not foa.get("close_date"):
                foa["close_date"] = structured_fields["close_date_raw"]

        raw_payload["pdf_enriched"] = True
        foa["raw_payload"] = raw_payload
        db.upsert_foa(foa)
        enriched_count += 1

    logging.info(
        "PDF Enrichment complete: %d enriched, %d skipped (already done), %d errors",
        enriched_count,
        skipped_count,
        error_count,
    )



def _run_extract_budget(config) -> None:
    from .parsing.budget_extractor import BudgetTierExtractor
    from .storage.database import Database

    db = Database(config.app_db_path)
    extractor = BudgetTierExtractor(base_url=config.ollama_base_url, model=config.ollama_model)

    if not extractor.is_available():
        logging.warning(
            "Ollama is not available. Ensure it is running and model %s is pulled.",
            config.ollama_model,
        )
        logging.warning("Run: ollama serve && ollama pull %s", config.ollama_model)
        return

    records, _ = db.list_foas(page=1, size=100000)
    count = 0
    for record in records:
        if record.get("funding_tiers"):
            continue
        text = record.get("additional_info")
        if not text:
            continue

        logging.info("Extracting budget tiers for FOA %s", record["foa_id"])
        tiers = extractor.extract_tiers(text)
        if tiers:
            record["funding_tiers"] = tiers
            db.upsert_foa(record)
            count += 1
            logging.info("  Found %d tiers", len(tiers))

    logging.info("Extracted budget tiers for %d records", count)


def _run_setup_ontology(config) -> None:
    """Load all ontology CSVs and run synonym expansion."""
    from .ontology.store import OntologyStore
    from .ontology.synonyms import expand_synonyms_for_store

    store = OntologyStore(config.app_db_path)
    stats = store.load_all_ontologies(config.ontology_dir)
    logging.info("Ontology load stats: %s", stats)

    # Clear existing synonyms before regenerating. add_synonyms() uses
    # INSERT OR IGNORE, so without this, any synonym removed from
    # synonym_expander.py (e.g. a governance fix) would persist forever
    # as a stale row instead of actually being removed.
    store.conn.execute("DELETE FROM ontology_synonyms")
    store.conn.commit()

    logging.info("Running synonym expansion...")
    syn_stats = expand_synonyms_for_store(store)
    total_syns = sum(syn_stats.values())
    logging.info(
        "Synonym expansion complete: %d synonyms for %d concepts",
        total_syns,
        len(syn_stats),
    )

    logging.info(
        "Ontology store: %d concepts, %d synonyms",
        store.concept_count(),
        store.synonym_count(),
    )
    store.close()


def _run_tag_all(config, args) -> None:
    """Run the 3-layer semantic tagging pipeline and build the vector index."""
    from .matching.vector_index import VectorIndex
    from .ontology.store import OntologyStore
    from .storage.database import Database
    from .tagging.pipeline import TaggerPipeline

    db = Database(config.app_db_path)
    store = OntologyStore(config.app_db_path)
    pipeline = TaggerPipeline(config, store, enable_llm_backstop=args.llm_backstop)

    pipeline.initialize()

    # Clear existing tags before re-tagging. Without this, INSERT OR REPLACE
    # (keyed on foa_id+concept_id+source_layer) leaves stale rows behind for
    # any concept that a config/threshold/synonym change causes to no longer
    # be emitted, silently corrupting every subsequent evaluation run.
    db.conn.execute("DELETE FROM foa_tags")
    db.conn.commit()

    # Tag every FOA regardless of status, not just open ones.
    #
    # Restricting to open FOAs made the gold-standard metric decay with the
    # calendar: an FOA closes, tag-all silently skips it, all of its tags become
    # false negatives, and F1 drops with no change to the tagger. This was
    # measured, not theorised — one gold FOA ("Unleashing Tribal Energy
    # Development", closed 2026-07-24) expired and took global gold F1 from
    # 0.517 to 0.500 on its own.
    #
    # Tagging is a property of a document's text, not of whether it is still
    # accepting applications. Availability is a *serving* concern, and the
    # vector index below applies its own open-only filter, so search results
    # are unaffected by this.
    status_filter = None if getattr(args, "all_statuses", True) else "open"
    foas, total = db.list_foas(status=status_filter, page=1, size=100000)

    if args.limit > 0:
        foas = foas[:args.limit]

    logging.info(
        "Tagging %d FOAs (%s)...",
        len(foas),
        "all statuses" if status_filter is None else f"status={status_filter}",
    )

    tagged_count = 0
    total_tags_saved = 0

    for i, foa in enumerate(foas, 1):
        try:
            tags = pipeline.tag_record(foa)
            if tags:
                saved = db.save_tags(foa["foa_id"], tags)
                total_tags_saved += saved
            tagged_count += 1
            if i % 100 == 0:
                logging.info("Tagged %d/%d FOAs...", i, len(foas))
        except Exception as exc:
            logging.error("Failed to tag FOA %s: %s", foa["foa_id"], exc)

    logging.info("Tagging complete. Saved %d tags across %d FOAs.", total_tags_saved, tagged_count)

    # Build vector index
    logging.info("Building vector index...")
    index = VectorIndex(db, config.embedding_model, config.embeddings_cache_dir)
    index.build_index()
    logging.info("Vector index built successfully.")

    store.close()
    db.close()


def _run_precompute_embeddings(config) -> None:
    """Precompute embeddings for all ontology concepts."""
    from .ontology.store import OntologyStore
    from .tagging.layer2_embedding import L2Tagger

    store = OntologyStore(config.app_db_path)
    tagger = L2Tagger(
        model_name=config.embedding_model,
        cache_dir=config.embeddings_cache_dir
    )

    logging.info("Starting embedding precomputation...")
    tagger.build_embeddings(store, force_recompute=True)
    logging.info("Embeddings precomputed and cached.")
    store.close()


def _run_export_csv(config, args) -> None:
    """Export all FOAs from the database to CSV."""
    from .export.csv_exporter import export_foas_to_csv
    from .storage.database import Database

    db = Database(config.app_db_path)
    records, total = db.list_foas(page=1, size=100000)
    db.close()

    output = args.output or str(config.normalised_output_dir / "foa_normalised.csv")
    export_foas_to_csv(records, output)
    logging.info("Exported %d FOAs to %s", len(records), output)


def _run_export_json(config, args) -> None:
    """Export all FOAs from the database to JSON."""
    from .export.json_exporter import export_foas_to_json
    from .storage.database import Database

    db = Database(config.app_db_path)
    records, total = db.list_foas(page=1, size=100000)
    db.close()

    output = args.output or str(config.normalised_output_dir / "foa_normalised.json")
    export_foas_to_json(records, output, include_raw_payload=args.include_raw)
    logging.info("Exported %d FOAs to %s", len(records), output)


def _run_search(config, args) -> None:
    """Match a researcher profile against the indexed FOAs."""
    from .matching.matcher import match_profile_to_foas
    from .matching.vector_index import VectorIndex
    from .ontology.store import OntologyStore
    from .storage.database import Database
    from .tagging.pipeline import TaggerPipeline

    db = Database(config.app_db_path)
    index = VectorIndex(db, config.embedding_model, config.embeddings_cache_dir)

    if not index.load_index():
        logging.error(
            "FAISS index not found at %s. Run `tag-all` first to build it.",
            config.embeddings_cache_dir / "foa_index.faiss",
        )
        db.close()
        return

    store = OntologyStore(config.app_db_path)
    tagger = TaggerPipeline(config, store)
    tagger.initialize()

    results = match_profile_to_foas(args.profile, db, index, tagger=tagger, k=args.k)

    if not results:
        logging.info("No matching FOAs found for this profile.")
    else:
        logging.info("Top %d matches for: %r", len(results), args.profile[:80])
        for rank, foa in enumerate(results, 1):
            logging.info(
                "%2d. [hybrid %.3f] %s (%s)",
                rank,
                foa["hybrid_score"],
                (foa.get("title") or "")[:70],
                foa.get("agency") or "n/a",
            )
            logging.info(
                "      cosine=%.3f  tag_overlap=%.3f  matched: %s",
                foa["cosine_score"],
                foa["tag_overlap_ratio"],
                ", ".join(foa["matched_tags"]) or "none",
            )

    store.close()
    db.close()


def _run_evaluate(args) -> None:
    """Run the tagging evaluation against the gold or silver eval set."""
    from .evaluation.runner import run_evaluation

    run_evaluation(use_gold=args.gold, use_db_tags=args.gold)


def _run_diagnose_separation(config, args) -> None:
    """Report how well Layer 2 scores separate correct from incorrect tags."""
    from .evaluation.diagnostics import cosine_separation, format_separation_report

    try:
        report = cosine_separation(config.evaluation_dir, eval_set=args.eval_set)
    except (FileNotFoundError, ValueError) as exc:
        logging.error("%s", exc)
        return

    print(format_separation_report(report))


def _run_benchmark_disciplines(config, args) -> None:
    """Rank NSF directorates on the agency-labelled award corpus."""
    from .evaluation.discipline_benchmark import (
        format_benchmark_report,
        run_discipline_benchmark,
    )
    from .ontology.store import OntologyStore

    store = OntologyStore(config.app_db_path)
    try:
        report = run_discipline_benchmark(
            config, store, limit=args.limit, top_k=args.top_k, split=args.split
        )
    except (FileNotFoundError, ValueError) as exc:
        logging.error("%s", exc)
        return

    print(format_benchmark_report(report, store))

    suffix = "" if args.split == "all" else f"_{args.split}"
    output_path = config.evaluation_dir / f"discipline_benchmark{suffix}.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    logging.info("Wrote %s", output_path)


def _run_server(config) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run(
        "foa_pipeline.api.app:app",
        host=config.api_host,
        port=config.api_port,
        reload=config.api_reload,
    )


def _run_pdf_parse(args) -> None:
    """Parse a single PDF file and print results."""
    from pathlib import Path

    from .parsing.pdf_parser import extract_structured_fields, parse_foa_pdf

    result = parse_foa_pdf(Path(args.pdf_path))
    logging.info("Parsed %s (%s)", args.pdf_path, result.parse_method)
    logging.info("Pages: %d", result.page_count)
    logging.info("Sections found: %d", len(result.sections))
    for sec in result.sections:
        logging.info(
            "  [%s] %s (%d chars)",
            sec.section_type,
            sec.heading[:60],
            len(sec.content),
        )
    logging.info("Tables found: %d", len(result.tables))

    fields = extract_structured_fields(result)
    if fields:
        logging.info("Extracted fields: %s", json.dumps(fields, indent=2))

def _run_mine_synonyms(config, args) -> None:
    import csv

    from .storage.database import Database

    db = Database(config.app_db_path)

    query = """
    SELECT concept_id, label, category, confidence, context_snippet
    FROM foa_tags
    WHERE source_layer = 'layer_2_embedding'
      AND confidence >= ?
    ORDER BY category, confidence DESC
    """

    results = db.conn.execute(query, (args.threshold,)).fetchall()

    out_path = config.ontology_dir / "suggested_synonyms.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["concept_id", "label", "category", "confidence", "suggested_synonym_source"]
        )
        for row in results:
            writer.writerow([
                row["concept_id"],
                row["label"],
                row["category"],
                round(row["confidence"], 3),
                row["context_snippet"].replace('\n', ' ')
            ])

    logging.info("Mined %d potential synonyms to %s", len(results), out_path)

def _run_curate_eval_set(config, args) -> None:
    import json
    import random

    from .storage.database import Database

    db = Database(config.app_db_path)

    # Simple stratified sampling: get half from grants_gov and half from nsf_scraper
    half_size = args.size // 2

    records = []

    # Sample from Grants.gov
    gg_foas = db.conn.execute(
        "SELECT foa_id, title, program_description, eligibility_description, "
        "additional_info, source FROM foa_records WHERE source = 'grants_gov' "
        "ORDER BY RANDOM() LIMIT ?",
        (half_size,)
    ).fetchall()

    # Sample from NSF
    nsf_foas = db.conn.execute(
        "SELECT foa_id, title, program_description, eligibility_description, "
        "additional_info, source FROM foa_records WHERE source = 'nsf_scraper' "
        "ORDER BY RANDOM() LIMIT ?",
        (args.size - len(gg_foas),)
    ).fetchall()

    for r in gg_foas + nsf_foas:
        records.append({
            "foa_id": r["foa_id"],
            "title": r["title"],
            "source": r["source"],
            "program_description": r["program_description"],
            "eligibility_description": r["eligibility_description"],
            "additional_info": r["additional_info"],
            "human_tags": []  # Placeholder for annotation
        })

    random.shuffle(records)

    config.evaluation_dir.mkdir(parents=True, exist_ok=True)
    out_path = config.evaluation_dir / f"eval_set_{args.size}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    logging.info("Curated stratified eval set of %d FOAs to %s", len(records), out_path)

if __name__ == "__main__":
    main()
