import datetime
import json
from io import BytesIO
from pathlib import Path

import ase.io
import CifFile
from optimade.adapters import Reference, Structure
from optimade.models import Person

from .client import ICSDClient
from .utils import get_cif, uncertain_float


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
            atoms = ase.io.read(fp, format="cif")
    except Exception as exc:
        return RuntimeError(f"Unable to convert CIF to ASE atoms: {exc}")

    try:
        structure = Structure.ingest_from(atoms)
    except Exception as exc:
        return RuntimeError(f"Unable to convert ASE atoms to OPTIMADE structure: {exc}")

    entry = structure.entry.model_dump()
    entry["attributes"].pop("_ase_spacegroup", None)  # Remove non-serializable data
    entry["attributes"]["_icsd_cif_file_id"] = entry_id

    # Read with PyCIFRW to extract other metdata: IDs, dates, references
    try:
        with BytesIO(cif_bytes) as fp:
            pycifrw_dct = CifFile.ReadCif(fp)

    except Exception as exc:
        return RuntimeError(f"Unable to read CIF with PyCIFRW: {exc}")

    root_block_key = pycifrw_dct.keys()[0]
    cif = pycifrw_dct[root_block_key]
    id = root_block_key.split("-icsd")[0]
    if cif["_database_code_icsd"] != id:
        raise RuntimeError(
            f"ICSD code mismatch in CIF file: {id} vs {cif['_database_code_icsd']}"
        )

    entry["id"] = str(id)
    entry["attributes"]["immutable_id"] = str(id)

    def _isoformat(date_str: str | None) -> str | None:
        if date_str is None:
            return None

        return datetime.datetime.fromisoformat(date_str).isoformat()

    entry["attributes"]["last_modified"] = _isoformat(cif.get("_audit_update_record"))
    entry["attributes"]["_cif_audit_creation_date"] = _isoformat(
        cif.get("_audit_creation_date")
    )
    if (
        entry["attributes"]["last_modified"] is None
        and entry["attributes"]["_cif_audit_creation_date"] is not None
    ):
        entry["attributes"]["last_modified"] = entry["attributes"][
            "_cif_audit_creation_date"
        ]

    entry["attributes"]["space_group_it_number"] = cif["_space_group_it_number"]
    # entry["attributes"]["space_group_symbol_hermann_mauguin_extended"] = cif[
    #    "_space_group_name_H-M_alt"
    # ]

    # TODO: unify this with fields.py module
    cif_namespace = {
        "_cell_formula_units_Z": int,
        "_cell_length_a": uncertain_float,
        "_cell_length_b": uncertain_float,
        "_cell_length_c": uncertain_float,
        "_cell_volume": uncertain_float,
        "_cell_angle_alpha": uncertain_float,
        "_cell_angle_beta": uncertain_float,
        "_cell_angle_gamma": uncertain_float,
        "_chemical_name_common": str,
        "_chemical_formula_structural": str,
        "_chemical_formula_sum": str,
        "_chemical_name_structure_type": str,
        "_exptl_crystal_density_diffrn": float,
        "_diffrn_ambient_temperature": float,
        # "_space_group_name_H-M_alt": str,
    }
    for field in cif_namespace:
        value = cif.get(field)
        if not value:
            continue

        if cif_namespace[field] is uncertain_float:
            entry["attributes"][f"_cif{field}"], u = cif_namespace[field](value)  # type: ignore
            entry["attributes"][f"_cif{field}_uncertainty"] = u
            entry["attributes"][f"_cif{field}_raw"] = value
        else:
            entry["attributes"][f"_cif{field}"] = cif_namespace[field](value)  # type: ignore

    entry["attributes"]["chemical_formula_descriptive"] = cif.get(
        "_chemical_formula_structural"
    )

    # TODO: extract uncertainties for other float fields, and expose them as metadata

    ref_entry = {
        "id": id,
        "type": "references",
        "attributes": {
            "doi": None,
            "last_modified": entry["attributes"]["_cif_audit_creation_date"],
        },
    }
    reference = Reference(ref_entry)
    reference_index = cif["_citation_id"].index("primary")
    reference.entry.attributes.title = cif["_citation_title"].strip()
    reference.entry.attributes.year = str(cif["_citation_year"][reference_index])
    reference.entry.attributes.journal = cif["_citation_journal_full"][reference_index]
    reference.entry.attributes.authors = [
        Person(name=n) for n in cif["_citation_author_name"]
    ]  # TODO: need to check this, CIF may not be parsed correctly here wrt. loop over authors

    entry["relationships"] = {}
    entry["relationships"]["references"] = {}
    entry["relationships"]["references"]["data"] = [{"id": id, "type": "references"}]

    return f"{json.dumps(entry)}\n{reference.entry.model_dump_json()}"
