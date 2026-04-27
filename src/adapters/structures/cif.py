"""
Convert an OPTIMADE structure, in the format of
[`StructureResource`][optimade.models.structures.StructureResource]
to and from a standard cif file string.
"""

from io import StringIO
import CifFile
from optimade.models import StructureResource

from adapters.structures.pycifrw import from_pycifrw, get_pycifrw

def get_cif(optimade_structure: StructureResource) -> str:
    """Get cif file string from OPTIMADE structure.

    This function will return a cif file string based on the OPTIMADE structure.
    """
    # TODO
    
    return str(get_pycifrw(optimade_structure))

def _parse_cif(fp: bytes, cast=False) -> CifFile:
    if cast:
        cif_bytes = cif_bytes.decode('utf-8', errors='ignore')
        fp = cif_bytes.encode(cast, errors='ignore')

    if 'Unauthorized' in fp.getvalue():
        return 'Unauthorized', False, None

    try:
        return CifFile.ReadCif(fp), True, None

    except Exception as exc:
        return None, False, exc


def from_cif(cif_string: bytes, fp=False) -> StructureResource:
    """Create an OPTIMADE structure from a cif file string.

    This function will return an OPTIMADE structure based on the cif file string.
    """
    if fp:
        with open(fp, 'rb') as f:
            cif_bytes = f.read()
    else:
        cif_bytes = cif_string

    pycifrw_dct, succ, exc = _parse_cif(cif_string) 

    if not succ:
        pycifrw_dct, succ, exc = _parse_cif(cif_string, 'ascii')

    if not succ:
        raise RuntimeError(f"Unable to read CIF: {exc}")

    return from_pycifrw(pycifrw_dct)
