import json
from io import BytesIO
from pathlib import Path

import CifFile

from .adapters.structures.pycifrw import from_pycifrw
from .client import ICSDClient
from .utils import get_cif


def map_cif_to_optimade(
    entry_id: int, client: ICSDClient, data_dir: Path | None = None
) -> str | RuntimeError:
    """For a given ICSD entry ID (CollCode), either look up a cached
    copy of the CIF or download from the ICSD API and map it into an OPTIMADE
    Structure resource via ASE, returning a JSON string of the structure.

    Parameters:
        entry_id: The ICSD CollCode of the desired structure.
        client: An ICSDClient instance to use for downloading CIF files.
        data_dir: Optional directory to look for cache of CIF files.

    Returns:
        A JSONLines string representing the structure and any references, or a RuntimeError if the parsing failed.

    Raises:
        Forbidden: If the CIF download failed for rate-limit reasons.

    """
    cif_bytes = get_cif(entry_id, client, data_dir)

    try:
        with BytesIO(cif_bytes) as fp:
            pycifrw_dct = CifFile.ReadCif(fp)
            structure = from_pycifrw(pycifrw_dct)
            entry = structure.entry.model_dump()
    except Exception as exc:
        return RuntimeError(f"Unable to convert CIF to ASE atoms: {exc}")

    references = structure.attributes.pop("references")

    root_block_key = pycifrw_dct.keys()[0]
    cif_id = root_block_key.split("-icsd")[0].split('data_')[1]

    entry["relationships"] = {
        'references': {
            'data': [{
                'id': f"{cif_id}-{i}",
                'type': 'references'
            }]
        } for i in range(len(references))
    }

    for i,reference in enumerate(references):
        reference["id"] = f"{cif_id}-{i}"

    return f"{json.dumps(entry)}\n{[x.entry.model_dump_json() for x in references]}"
