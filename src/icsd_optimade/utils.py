import logging
import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    from icsd_optimade.client import ICSDClient


def setup_log(
    log_name: str = "ingest", log_level: int | str = logging.INFO
) -> logging.Logger:
    """Return a named logger with a console handler that records
    timestamps and process IDs.

    Parameters:
        log_name: Name of the logger.
        log_level: Logging level, e.g., logging.INFO, logging.DEBUG.

    """
    log = logging.getLogger(log_name)
    if not log.handlers:
        log.handlers = []
        console_handler = logging.StreamHandler()
        if isinstance(log_level, str):
            log_level = log_level.upper()
        log.setLevel(log_level)
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - [PID: %(process)d] - %(levelname)s - %(message)s"
            )
        )
        console_handler.setLevel(log_level)
        log.addHandler(console_handler)
    return log


def _get_cif_cache_path(entry: int, data_dir: Path) -> Path:
    """Get the path to the cached CIF file for the given CollCode `entry`."""
    entry_str = str(entry)
    # Pad short entry IDs with zeros
    if len(entry_str) < 2:
        entry_str = f"0{entry_str}"

    return data_dir / "cifs" / entry_str[0] / entry_str[1] / f"{entry_str}.cif"


def check_cif_cache(entry: int, data_dir: Path | None = None) -> bytes | None:
    """Check if the CIF with CollCode `entry` is already stored on disk."""

    if data_dir is None:
        return None

    entry_path = _get_cif_cache_path(entry, data_dir)

    if entry_path.is_file():
        return entry_path.read_bytes()

    return None


def store_cif(entry_id: int, cif_bytes: bytes, data_dir: Path | None = None) -> None:
    """Store the CIF bytes for the given CollCode `entry_id` on disk.

    Parameters:
        entry_id: The ICSD CollCode of the CIF.
        cif_bytes: The CIF data as bytes.
        data_dir: Path to the data directory for storing CIFs.

    """

    if data_dir:
        entry_path = _get_cif_cache_path(entry_id, data_dir)
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(entry_path, "wb") as f:
            f.write(cif_bytes)


def get_cif(entry_id: int, client: "ICSDClient", data_dir: Path | None = None) -> bytes:
    """Get the CIF bytes for the given CollCode `entry_id`, either from cache
    or by downloading from the ICSD API.

    Parameters:
        entry_id: The ICSD CollCode of the desired CIF.
        client: An instance of ICSDClient to use for downloading.
        data_dir: Path to the data directory for storing CIFs.

    """
    cif_bytes = check_cif_cache(entry_id, data_dir)

    if not cif_bytes:
        cif_bytes = client.get_cif(entry_id)
        store_cif(entry_id, cif_bytes, data_dir)

    return cif_bytes


def uncertain_float(value: str) -> tuple[float, float | None]:
    """Take a string representing a float optionally with uncertainty in parentheses,
    and return the float value and its uncertainty as a tuple, with scaled uncertainty
    set to None if not present.

    Parameters:
        value: A string representing a float, e.g., "1.234(5)" or "2.0".

    """
    if "(" in value:
        base, uncertainty = value.split("(")
        uncertainty = uncertainty.rstrip(")")
        scale = 10 ** (-len(uncertainty))
        return float(base), float(uncertainty) * scale

    return float(value), None

def strip_copyright(cif_path):
    cif_content = cif_path.read_text()
    lines = cif_content.split('\n')

    # Find the first data_ or global_ line
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('data_') or stripped.startswith('global_'):
            start_idx = i
            break
        # Also accept lines starting with # (comments are OK)
        if stripped.startswith('#'):
            continue
        # If we see anything else before data_, it's likely a header to skip
        if '(C)' in stripped or 'copyright' in stripped.lower() or 'rights reserved' in stripped.lower():
            continue

    # Reconstruct clean CIF
    clean_cif = '\n'.join(lines[start_idx:])

    return clean_cif.encode()