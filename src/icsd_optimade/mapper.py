import datetime
import json
from io import BytesIO

import ase.io
import CifFile
from optimade.adapters import Reference, Structure
from optimade.models import Person

from .client import ICSDClient
from .utils import get_cif


def map_cif_to_optimade(entry_id: int, client: ICSDClient) -> str | RuntimeError:
    """For a given ICSD entry ID (CollCode), either look up a cached
    copy of the CIF or download from the ICSD API and map it into an OPTIMADE
    Structure resource via ASE, returning a JSON string of the structure.

    Returns:
        A JSONLines string representing the structure and any references, or a RuntimeError if the parsing failed.

    Raises:
        Forbidden: If the CIF download failed for rate-limit reasons.

    """

    cif_bytes = get_cif(entry_id, client)

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

    entry["attributes"]["_cif_audit_creation_date"] = datetime.datetime.fromisoformat(
        cif["_audit_creation_date"]
    ).isoformat()
    entry["attributes"]["last_modified"] = datetime.datetime.fromisoformat(
        cif["_audit_update_record"]
    ).isoformat()

    entry["attributes"]["space_group_it_number"] = cif["_space_group_it_number"]
    entry["attributes"]["_cif_cell_formula_units_Z"] = cif["_cell_formula_units_Z"]
    entry["attributes"]["_cif_cell_length_a"] = cif["_cell_length_a"]
    entry["attributes"]["_cif_cell_length_b"] = cif["_cell_length_b"]
    entry["attributes"]["_cif_cell_length_c"] = cif["_cell_length_c"]
    entry["attributes"]["_cif_cell_volume"] = cif["_cell_volume"]
    entry["attributes"]["_cif_cell_angle_alpha"] = cif["_cell_angle_alpha"]
    entry["attributes"]["_cif_cell_angle_beta"] = cif["_cell_angle_beta"]
    entry["attributes"]["_cif_cell_angle_gamma"] = cif["_cell_angle_gamma"]

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
    reference.entry.attributes.title = cif["_citation_title"][reference_index].strip()
    reference.entry.attributes.year = str(cif["_citation_year"][reference_index])
    reference.entry.attributes.journal = cif["_citation_journal_full"][reference_index]
    reference.entry.attributes.authors = [
        Person(name=n) for n in cif["_citation_author_name"]
    ]  # TODO: need to check this, CIF may not be parsed correctly here wrt. loop over authors

    entry["relationships"] = {}
    entry["relationships"]["references"] = {}
    entry["relationships"]["references"]["data"] = [{"id": id, "type": "references"}]

    return f"{json.dumps(entry)}\n{reference.entry.model_dump_json()}"
