"""
PDF Downloader Module.

Asynchronously downloads PDF files found in FOA records, parses them
using the layout-aware parser, and appends the extracted text to
the program description in the database.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

import aiohttp

from ..config import Config
from ..parsing.pdf_parser import parse_foa_pdf
from ..storage.database import Database
from ..storage.jsonl import ensure_dir

logger = logging.getLogger(__name__)


async def download_pdf(session: aiohttp.ClientSession, url: str, output_path: Path) -> bool:
    """Download a single PDF file asynchronously."""
    try:
        # Some government sites require a User-Agent
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with session.get(url, headers=headers, timeout=30) as response:
            if response.status == 200:
                with open(output_path, "wb") as f:
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                return True
            else:
                logger.warning(f"Failed to download {url}: HTTP {response.status}")
                return False
    except Exception as exc:
        logger.error(f"Error downloading {url}: {exc}")
        return False


async def process_foa_pdfs(
    foa: Dict[str, Any],
    config: Config,
    db: Database,
    session: aiohttp.ClientSession,
) -> bool:
    """Download and parse all PDFs for a single FOA."""
    foa_id = foa["foa_id"]
    pdf_links = foa["pdf_links"]

    if not pdf_links:
        return True

    pdf_dir = Path("data/pdfs")
    ensure_dir(pdf_dir)

    appended_text_blocks = []
    success_count = 0

    for i, url in enumerate(pdf_links):
        if not url.startswith("http"):
            continue

        filename = f"{foa_id}_{i}.pdf"
        output_path = pdf_dir / filename

        # Download
        logger.debug(f"Downloading PDF for {foa_id}: {url}")
        if await download_pdf(session, url, output_path):
            success_count += 1
            # Parse
            try:
                parsed_pdf = parse_foa_pdf(output_path)
                logger.info(f"Successfully parsed {filename} ({parsed_pdf.parse_method})")

                # We append the markdown text
                appended_text_blocks.append(
                    f"## PDF Attachment {i+1}\n\n{parsed_pdf.full_text_markdown}"
                )

            except Exception as exc:
                logger.error(f"Failed to parse PDF {filename}: {exc}")

    # Update database if we extracted any text
    if appended_text_blocks:
        full_appended_text = "\n\n".join(appended_text_blocks)
        db.append_to_program_description(foa_id, full_appended_text, mark_pdf_processed=True)
        logger.info(f"Updated program description for {foa_id} with PDF text")
    else:
        # Still mark as processed so we don't retry forever
        db.append_to_program_description(foa_id, "", mark_pdf_processed=True)

    return success_count > 0


async def run_downloader_async(config: Config) -> Dict[str, int]:
    """Main async entry point to process pending FOA PDFs."""
    db = Database(config.app_db_path)
    pending_foas = db.get_foas_with_unprocessed_pdfs()

    stats = {"total_pending": len(pending_foas), "processed": 0, "failed": 0}

    if not pending_foas:
        logger.info("No pending PDFs to process.")
        db.close()
        return stats

    logger.info(f"Found {len(pending_foas)} FOAs with pending PDFs.")

    async with aiohttp.ClientSession() as session:
        # Process in chunks of 5 to avoid overwhelming the server or memory
        chunk_size = 5
        for i in range(0, len(pending_foas), chunk_size):
            chunk = pending_foas[i:i + chunk_size]
            tasks = [process_foa_pdfs(foa, config, db, session) for foa in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    stats["failed"] += 1
                    logger.error(f"Error in batch: {result}")
                elif result:
                    stats["processed"] += 1
                else:
                    stats["failed"] += 1

    db.close()
    return stats


def run_downloader(config: Config) -> Dict[str, int]:
    """Synchronous wrapper for the downloader."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(run_downloader_async(config))
