from __future__ import annotations

import datetime
import glob
import json
import os
import tempfile
from functools import partial
from pathlib import Path

import tqdm
from optimade_maker.convert import _construct_entry_type_info

from .client import ICSDClient
from .mapper import map_cif_to_optimade
from .utils import get_cif, setup_log


def handle_chunk(
    chunk: tuple[datetime.date, datetime.date],
    run_name: str = "test",
    num_chunks: int | None = None,
    client: ICSDClient | None = None,
    download_only: bool = False,
):
    """Handle a chunk of the ICSD database, queried by date, logging bad entries and showing a progress bar.

    Parameters:
        chunk: A tuple of (start_date, end_date) defining the date range to process.
        run_name: A name for this run, used in output file naming.
        num_chunks: Total number of chunks being processed (for logging purposes).
        client: An optional ICSDClient instance to use for querying and downloading.
        download_only: If True, only download CIFs without mapping to OPTIMADE, caching them to disk.

    """

    log = setup_log("ingest")

    if client is None:
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
                get_cif(int(entry), client)
                total_count += 1

        else:
            with open(f"data/{run_name}-optimade-{chunk[0].year}.jsonl", "w") as f:
                log.info(
                    f"Mapping entries to OPTIMADE format and saving as {run_name}-optimade-{chunk[0].year}.jsonl"
                )
                for entry in entry_ids:
                    optimade = map_cif_to_optimade(int(entry), client)
                    if isinstance(entry, Exception):
                        bad_count += 1
                        continue

                    else:
                        f.write(str(optimade) + "\n")

                    total_count += 1

            if total_count == 0 and bad_count != 0:
                raise RuntimeError(
                    "No good entries found in chunk {chunk}; something went wrong."
                )

    return total_count, bad_count


def cli():
    import argparse
    from multiprocessing import Pool

    parser = argparse.ArgumentParser()
    parser.add_argument("--num-processes", type=int, default=4)
    parser.add_argument("--run-name", type=str, default="icsd")
    parser.add_argument("--combine-only", action="store_true")

    log = setup_log("ingest")

    args = parser.parse_args()

    pool_size = args.num_processes
    run_name = args.run_name

    start_year = 1950
    end_year = datetime.datetime.today().year

    date_ranges = (
        (datetime.date(year=i, month=1, day=1), datetime.date(year=i, month=12, day=31))
        for i in range(start_year, end_year)
    )

    icsd_client = ICSDClient()

    chunk_processor = partial(
        handle_chunk, run_name=run_name, client=icsd_client, download_only=True
    )

    with tqdm.tqdm(
        desc="Downloading ICSD CIFs single-threaded",
    ) as pbar:
        for dates in date_ranges:
            total_count, bad_count = chunk_processor(dates)
            pbar.update(total_count)

    total_bad = 0
    total = 0
    if not args.combine_only:
        with Pool(pool_size) as pool:
            with tqdm.tqdm(
                desc=f"Mapping ICSD to OPTIMADE ({pool_size=}",
            ) as pbar:
                for total_count, bad_count in pool.imap_unordered(
                    partial(
                        handle_chunk,
                        run_name=run_name,
                        client=icsd_client,
                    ),
                    date_ranges,
                    chunksize=1,
                ):
                    total_bad += bad_count
                    total += total_count
                    pbar.update(total)
                    try:
                        pbar.set_postfix({"% bad": 100 * (total_bad / total)})
                    except ZeroDivisionError:
                        pbar.set_postfix({"% bad": "???"})

    # Combine all results into a single JSONL file, first temporary
    output_file = f"{run_name}-optimade.jsonl"
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_jsonl_path = Path(tmp_dir.name) / output_file
    print(f"Collecting results into {output_file}")

    pattern = f"{run_name}-optimade-*.jsonl"
    input_files = sorted(
        glob.glob(os.path.join("data", pattern)),
        key=lambda x: int(x.split("-")[-1].split(".")[0]),
    )

    with open(tmp_jsonl_path, "w") as tmp_jsonl:
        # Write headers
        tmp_jsonl.write(
            json.dumps({"x-optimade": {"meta": {"api_version": "1.1.0"}}}) + "\n"
        )
        tmp_jsonl.write(
            _construct_entry_type_info(
                "structures", properties=[], provider_prefix=""
            ).model_dump_json()
            + "\n"
        )

        for filename in input_files:
            file = Path(filename)
            with open(file) as infile:
                tmp_jsonl.write(infile.read())
            tmp_jsonl.write("\n")
            # file.unlink()

    with open(tmp_jsonl_path) as tmp_jsonl:
        ids_by_type: dict[str, set] = {}
        with open(output_file, "a") as final_jsonl:
            for line_entry in tmp_jsonl:
                if not line_entry.strip():
                    continue
                try:
                    json_entry = json.loads(line_entry)
                except Exception as exc:
                    log.error(f"Bad entry at {line_entry}: {exc}")
                if _type := json_entry.get("type"):
                    if _type not in ids_by_type:
                        ids_by_type[_type] = set()
                    if _id := json_entry.get("id") in ids_by_type[_type]:
                        continue
                    ids_by_type[_type].add(json_entry["id"])
                    final_jsonl.write(line_entry)

    tmp_dir.cleanup()

    # Final scan to remove duplicates an empty lines
    print(
        f"Combined {len(input_files)} files into {output_file} (total size of file: {os.path.getsize(output_file) / 1024**2:.1f} MB)"
    )
