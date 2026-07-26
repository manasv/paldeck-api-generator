import argparse
import logging
from pathlib import Path
from typing import Optional, Sequence

import requests

from scraper import (
    ScraperError,
    create_session,
    download_pal_image,
    fetch_pal_image_urls,
    scrape_records,
)
from storage import save_individual_pal, save_to_json


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the Paldeck JSON dataset from the Palworld wiki.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated JSON and images (default: output).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only process the first N Pals (useful for smoke tests).",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Generate JSON without downloading Pal images.",
    )
    return parser


def generate(
    output_dir: Path,
    limit: Optional[int] = None,
    skip_images: bool = False,
) -> int:
    if limit is not None and limit < 1:
        raise ValueError("--limit must be greater than zero")

    session = create_session()
    records = scrape_records(session=session, limit=limit)
    LOGGER.info("Found %d Pal records", len(records))
    image_urls = (
        {}
        if skip_images
        else fetch_pal_image_urls(
            [record["name"] for record in records],
            session=session,
        )
    )

    complete_records = []
    failed_pals = []
    for index, record in enumerate(records, start=1):
        pal_name = record["name"]
        pal_id = record["id"]
        LOGGER.info(
            "Processing %s (%d/%d)",
            pal_name,
            index,
            len(records),
        )
        try:
            if not skip_images:
                download_pal_image(
                    pal_name,
                    pal_id,
                    image_urls[pal_name],
                    output_dir=output_dir / "images" / "pals",
                    session=session,
                )
            save_individual_pal(
                record,
                output_dir=output_dir / "pals",
            )
            complete_records.append(record)
        except (requests.RequestException, ScraperError, OSError, KeyError):
            failed_pals.append(pal_name)
            LOGGER.exception("Failed to process %s", pal_name)

    if failed_pals:
        raise ScraperError(
            f"Failed to process {len(failed_pals)} Pals: "
            + ", ".join(failed_pals)
        )

    combined_path = save_to_json(
        complete_records,
        output_dir=output_dir,
    )
    LOGGER.info(
        "Saved %d complete records to %s",
        len(complete_records),
        combined_path,
    )
    return len(complete_records)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        generate(
            output_dir=args.output_dir,
            limit=args.limit,
            skip_images=args.skip_images,
        )
    except (ScraperError, ValueError) as error:
        LOGGER.error("%s", error)
        return 1
    except Exception:
        LOGGER.exception("Generation failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
