from __future__ import annotations

import datetime
import glob
import json
import logging
import os
import tempfile
from functools import partial
from io import BytesIO
from pathlib import Path

import ase.io
import tqdm
from optimade.adapters import Structure
from optimade_maker.convert import _construct_entry_type_info

from .client import ICSDClient

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "cifs"

log = logging.getLogger("ingest")
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - [PID: %(process)d] - %(levelname)s - %(message)s")
)
log.addHandler(console_handler)


def _check_cif_cache(entry: int) -> bytes | None:
    """Check if the CIF with CollCode `entry` is already stored on disk."""

    entry_str = str(entry)
    # Pad short entry IDs with zeros
    if len(entry_str) < 2:
        entry_str = f"0{entry_str}"

    entry_path = DATA_DIR / entry_str[0] / entry_str[1] / f"{entry_str}.cif"
    entry_path.parent.mkdir(parents=True, exist_ok=True)

    if entry_path.is_file():
        return entry_path.read_bytes()

    return None


def map_cif_to_optimade(entry: int, client: ICSDClient) -> str | RuntimeError:
    """For a given ICSD entry ID (CollCode), either look up a cached
    copy of the CIF or download from the ICSD API and map it into an OPTIMADE
    Structure resource via ASE, returning a JSON string of the structure.

    Returns:
        A JSON string representing the structure, or a RuntimeError if the parsing failed.

    Raises:
        Forbidden: If the CIF download failed for rate-limit reasons.

    """

    # First check for cached CIF on disk
    cif_bytes = _check_cif_cache(entry)

    if not cif_bytes:
        cif_bytes = client.get_cif(entry)

    try:
        with BytesIO(cif_bytes) as fp:
            atoms = ase.io.read(fp, format="cif")
    except Exception as exc:
        return RuntimeError(f"Unable to convert CIF to ASE atoms: {exc}")

    try:
        structure = Structure.ingest_from(atoms)
    except Exception as exc:
        return RuntimeError(f"Unable to convert ASE atoms to OPTIMADE structure: {exc}")

    entry = structure.entry.model_dump()
    # ASE spg cannot be serialized as JSON, first just take the number
    entry["attributes"]["_ase_spacegroup"] = entry["attributes"]["_ase_spacegroup"].no  # type: ignore
    return json.dumps(entry)


def handle_chunk(
    chunk: tuple[datetime.date, datetime.date],
    run_name: str = "test",
    num_chunks: int | None = None,
    client: ICSDClient | None = None,
):
    """Handle a chunk of the ICSD database, logging bad entries and showing a progress bar."""
    if client is None:
        client = ICSDClient()

    bad_count: int = 0
    total_count: int = 0

    entry_ids = client.query_by_date_range(chunk)

    log.error(
        "Queried date range %s, %s returned %s results",
        chunk[0],
        chunk[1],
        len(entry_ids),
    )

    if entry_ids:
        with open(f"data/{run_name}-optimade-{chunk[0].year}.jsonl", "w") as f:
            for entry in entry_ids:
                optimade = map_cif_to_optimade(entry, client)
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

    total_bad = 0
    total = 0
    if not args.combine_only:
        with Pool(pool_size) as pool:
            with tqdm.tqdm(
                desc=f"Processing ICSD ({pool_size=}",
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
            file.unlink()

    with open(tmp_jsonl_path) as tmp_jsonl:
        ids_by_type: dict[str, set] = {}
        with open(output_file, "a") as final_jsonl:
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

    tmp_dir.cleanup()

    # Final scan to remove duplicates an empty lines
    print(
        f"Combined {len(input_files)} files into {output_file} (total size of file: {os.path.getsize(output_file) / 1024**2:.1f} MB)"
    )
