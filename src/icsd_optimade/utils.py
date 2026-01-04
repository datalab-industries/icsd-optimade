import logging
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "cifs"


def setup_log(
    log_name: str = "ingest", log_level: int = logging.INFO
) -> logging.Logger:
    """Return a named logger with a console handler that records
    timestamps and process IDs.

    Parameters:
        log_name: Name of the logger.
        log_level: Logging level, e.g., logging.INFO, logging.DEBUG.

    """
    log = logging.getLogger(log_name)
    log.handlers = []
    console_handler = logging.StreamHandler()
    log.setLevel(log_level)
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - [PID: %(process)d] - %(levelname)s - %(message)s"
        )
    )
    console_handler.setLevel(log_level)
    log.addHandler(console_handler)
    return log


def _get_cif_cache_path(entry: int) -> Path:
    """Get the path to the cached CIF file for the given CollCode `entry`."""
    entry_str = str(entry)
    # Pad short entry IDs with zeros
    if len(entry_str) < 2:
        entry_str = f"0{entry_str}"

    return DATA_DIR / entry_str[0] / entry_str[1] / f"{entry_str}.cif"


def check_cif_cache(entry: int) -> bytes | None:
    """Check if the CIF with CollCode `entry` is already stored on disk."""

    entry_path = _get_cif_cache_path(entry)

    if entry_path.is_file():
        return entry_path.read_bytes()

    return None


def store_cif(entry_id: int, cif_bytes: bytes) -> None:
    entry_path = _get_cif_cache_path(entry_id)
    entry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(entry_path, "wb") as f:
        f.write(cif_bytes)


def get_cif(entry_id: int, client) -> bytes:
    # First check for cached CIF on disk
    cif_bytes = check_cif_cache(entry_id)

    if not cif_bytes:
        cif_bytes = client.get_cif(entry_id)
        store_cif(entry_id, cif_bytes)

    return cif_bytes
