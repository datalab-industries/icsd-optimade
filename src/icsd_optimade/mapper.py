from io import BytesIO
from pathlib import Path

import CifFile
from optimade.models import ReferenceResource, StructureResource

from .adapters.structures.pycifrw import from_pycifrw
from .client import ICSDClient
from .utils import get_cif


def map_cif_to_optimade(
    entry_id: int,
    client: ICSDClient,
    data_dir: Path | None = None,
    download: bool = True,
    ignore_errors: bool = False,
) -> str | Exception:
    """For a given ICSD entry ID (CollCode), either look up a cached
    copy of the CIF or download from the ICSD API and map it into an OPTIMADE
    Structure resource via ASE, returning a JSON string of the structure.

    Parameters:
        entry_id: The ICSD CollCode of the desired structure.
        client: An ICSDClient instance to use for downloading CIF files.
        data_dir: Optional directory to look for cache of CIF files.
        download: If False, do not attempt to download the CIF if it is not found in the cache.
        ignore_errors: If True, return a RuntimeError instead of raising an exception if the parsing fails.

    Returns:
        A JSONLines string representing the structure and any references, or a RuntimeError if the parsing failed.

    Raises:
        Forbidden: If the CIF download failed for rate-limit reasons.

    """
    cif_bytes = get_cif(entry_id, client, data_dir, download=download)

    try:
        with BytesIO(cif_bytes) as fp:
            pycifrw_dct = CifFile.ReadCif(fp)
            attributes = from_pycifrw(pycifrw_dct).model_dump()
    except Exception as exc:
        if ignore_errors:
            return exc
        raise exc

    references = attributes.pop("references", [])

    root_block_key = pycifrw_dct.keys()[0]
    cif_id = root_block_key.split("-icsd")[0].split("data_")[0]
    attributes["immutable_id"] = cif_id

    references = [
        ReferenceResource(
            **{
                "attributes": ref["data"].entry.attributes,
                "type": "references",
                "id": f"{cif_id}-{i}",
            }
        )
        for i, ref in enumerate(references)
    ]

    entry = StructureResource(
        **{
            "attributes": attributes,
            "id": str(cif_id),
            "type": "structures",
            "relationships": {
                "references": {
                    "data": [
                        {"id": reference.id, "type": "references"}
                        for reference in references
                    ]
                }
            },
        }
    )

    json_str = entry.model_dump_json()
    if references:
        json_str += "\n" + "\n".join(x.model_dump_json() for x in references)

    return json_str
