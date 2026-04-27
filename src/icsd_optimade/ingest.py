from __future__ import annotations

import datetime
import glob
import json
import os
import tempfile
from functools import partial
from multiprocessing import Pool
from pathlib import Path

import tqdm
from optimade import __api_version__
from optimade_maker.convert import _construct_entry_type_info

from .client import ICSDClient
from .fields import generate_icsd_info_endpoint, generate_provider_fields
from .mapper import map_cif_to_optimade
from .utils import get_cif, setup_log


def handle_chunk(
    chunk: tuple[datetime.date, datetime.date],
    data_dir: Path,
    run_name: str = "test",
    num_chunks: int | None = None,
    client: ICSDClient | None = None,
    download_only: bool = False,
    skip_download: bool = False,
    log_level: str = "INFO",
):
    """Handle a chunk of the ICSD database, queried by date, logging bad entries and showing a progress bar.

    Parameters:
        chunk: A tuple of (start_date, end_date) defining the date range to process.
        data_dir: Path to the data directory for storing CIFs and outputs.
        run_name: A name for this run, used in output file naming.
        num_chunks: Total number of chunks being processed (for logging purposes).
        client: An optional ICSDClient instance to use for querying and downloading.
        download_only: If True, only download CIFs without mapping to OPTIMADE, caching them to disk.
        log_level: Logging level as a string (e.g., "INFO", "DEBUG").

    """

    log = setup_log(f"ingest-chunk-{os.getpid()}", log_level=log_level)

    if client is None and not skip_download:
        client = ICSDClient()

    bad_count: int = 0
    total_count: int = 0

    entry_ids = client.query_by_date_range(chunk)

    log.info(
        "Queried date range %s, %s returned %s results",
        chunk[0],
        chunk[1],
        len(entry_ids),
    )

    if entry_ids:
        log.info(
            "Checking for missing CIFs in range %s to %s (%s entries)",
            chunk[0],
            chunk[1],
            len(entry_ids),
        )
        if download_only:
            for entry in entry_ids:
                get_cif(int(entry), client, data_dir=data_dir)
                total_count += 1

        else:
            with open(
                data_dir / f"{run_name}-optimade-{chunk[0].year}.jsonl", "w"
            ) as f:
                log.info(
                    f"Mapping entries to OPTIMADE format and saving as {run_name}-optimade-{chunk[0].year}.jsonl"
                )
                for entry in entry_ids:
                    optimade = map_cif_to_optimade(int(entry), client, data_dir)
                    if isinstance(optimade, Exception):
                        bad_count += 1
                        log.warning("Bad entry %s: %s", entry, optimade)
                        continue

                    else:
                        f.write(str(optimade) + "\n")

                    total_count += 1

            if total_count == 0 and bad_count != 0:
                raise RuntimeError(
                    "No good entries found in chunk {chunk}; something went wrong."
                )

    return total_count, bad_count


def ingest_by_year(
    data_dir: Path,
    start_year: int = 1950,
    end_year: int | None = None,
    pool_size: int = 1,
    run_name: str = "icsd",
    log_level: str = "WARNING",
    skip_download: bool = False,
    combine_only: bool = False,
):
    """Ingest ICSD data by year range, downloading CIFs and mapping to OPTIMADE format.

    Parameters:
        start_year: The starting year for ingestion (inclusive).
        end_year: The ending year for ingestion (exclusive). If None, defaults to current year.
        data_dir: Path to the data directory for storing CIFs and outputs.
        pool_size: Number of parallel processes to use for mapping.
        run_name: A name for this run, used in output file naming.
        log_level: Logging level as a string (e.g., "INFO", "DEBUG").
        skip_download: If True, skip the download step and only combine existing files.
        combine_only: If True, only combine existing mapped files without downloading or mapping.

    """

    log = setup_log("ingest", log_level=log_level)

    if not data_dir.is_dir():
        data_dir.mkdir(parents=True, exist_ok=True)

    if end_year is None:
        end_year = datetime.datetime.today().year

    if end_year == start_year:
        end_year += 1

    date_ranges = (
        (
            datetime.date(year=i, month=1, day=1),
            datetime.date(year=i, month=12, day=31),
        )
        for i in range(start_year, end_year)
    )

    if skip_download:
        log.info("Skipping download step as per user request.")
        icsd_client = None
    else:
        icsd_client = ICSDClient()

        chunk_processor = partial(
            handle_chunk,
            run_name=run_name,
            data_dir=data_dir,
            client=icsd_client,
            download_only=True,
            log_level=log_level,
            skip_download=skip_download,
        )

        with tqdm.tqdm(
            desc="Downloading ICSD CIFs single-threaded",
        ) as pbar:
            for dates in date_ranges:
                total_count, bad_count = chunk_processor(dates)
                pbar.update(total_count)

    total_bad = 0
    total = 0
    if not combine_only:
        with tqdm.tqdm(
            desc=f"Mapping ICSD to OPTIMADE ({pool_size=}",
        ) as pbar:
            with Pool(pool_size) as pool:
                for total_count, bad_count in pool.imap_unordered(
                    partial(
                        handle_chunk,
                        data_dir=data_dir,
                        run_name=run_name,
                        client=icsd_client,
                        download_only=False,
                        log_level=log_level,
                        skip_download=skip_download,
                    ),
                    date_ranges,
                    chunksize=1,
                ):
                    total_bad += bad_count
                    total += total_count
                    pbar.update(total_count)
                    try:
                        pbar.set_postfix({"% bad": 100 * (total_bad / total)})
                    except ZeroDivisionError:
                        pbar.set_postfix({"% bad": "???"})

    # Combine all results into a single JSONL file, first temporary
    output_filename = f"{run_name}-optimade.jsonl"
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_jsonl_path = Path(tmp_dir.name) / output_filename
    output_file = data_dir / output_filename
    log.info(f"Collecting results into {output_file}")

    pattern = f"{run_name}-optimade-*.jsonl"
    input_files = sorted(
        glob.glob(os.path.join(str(data_dir), pattern)),
        key=lambda x: int(x.split("-")[-1].split(".")[0]),
    )

    with open(tmp_jsonl_path, "w") as tmp_jsonl:
        # Decompress and combine all files into a single temporary file that needs to be deduplicated
        for filename in input_files:
            file = Path(filename)
            with open(file) as infile:
                tmp_jsonl.write(infile.read())
            tmp_jsonl.write("\n")

    log.info("Filtering duplicates and writing final output")
    with open(tmp_jsonl_path) as tmp_jsonl:
        ids_by_type: dict[str, set] = {}
        with open(output_file, "w") as final_jsonl:
            # Write headers and info endpoints
            final_jsonl.write(
                json.dumps({"x-optimade": {"meta": {"api_version": __api_version__}}})
                + "\n"
            )
            final_jsonl.write(
                json.dumps(
                    {
                        "data": generate_icsd_info_endpoint()["data"].model_dump(
                            exclude_unset=True, exclude_none=False
                        )
                    }
                )
                + "\n"
            )

            final_jsonl.write(
                _construct_entry_type_info(
                    "structures",
                    properties=generate_provider_fields()["structures"],
                    provider_prefix="",
                ).model_dump_json()
                + "\n"
            )
            final_jsonl.write(
                _construct_entry_type_info(
                    "references",
                    properties=generate_provider_fields()["references"],
                    provider_prefix="",
                ).model_dump_json()
                + "\n"
            )

            for line_entry in tmp_jsonl:
                if not line_entry.strip():
                    continue
                json_entry = json.loads(line_entry)
                if _type := json_entry.get("type"):
                    if _type not in ids_by_type:
                        ids_by_type[_type] = set()
                    if _id := json_entry.get("id") in ids_by_type[_type]:
                        continue
                    ids_by_type[_type].add(json_entry["id"])
                    final_jsonl.write(line_entry)

    # Remove the temporary directory
    tmp_jsonl_path.unlink()
    tmp_dir.cleanup()

    # Final scan to remove duplicates an empty lines
    log.info(
        f"Combined {len(input_files)} files into {output_file} (total size of file: {os.path.getsize(output_file) / 1024**2:.1f} MB)"
    )


def cli():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--num-processes", type=int, default=4)
    parser.add_argument("--run-name", type=str, default="icsd")
    parser.add_argument("--combine-only", action="store_true")
    parser.add_argument("--log-level", type=str, default="WARNING")
    parser.add_argument("--skip-download", action="store_true")

    data_dir = Path(__file__).parent.parent.parent / "data"

    args = parser.parse_args()

    pool_size = args.num_processes
    run_name = args.run_name
    log_level = args.log_level
    skip_download = args.skip_download
    combine_only = args.combine_only

    ingest_by_year(
        pool_size=pool_size,
        run_name=run_name,
        log_level=log_level,
        skip_download=skip_download,
        combine_only=combine_only,
        data_dir=data_dir,
    )
