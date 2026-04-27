"""
Convert an OPTIMADE structure, in the format of
[`StructureResource`][optimade.models.structures.StructureResource]
to and from a standard python dictionary.

This conversion function relies on the [pycifrw](https://github.com/jamesrhester/pycifrw) package.

For more information on the pycifrw code see [their github repository](https://github.com/jamesrhester/pycifrw).
"""

from typing import Union
from warnings import warn

from optimade.adapters.structures.utils import (
    species_from_species_at_sites,
    valid_lattice_vector,
)
from optimade.models import Species as OptimadeStructureSpecies
from optimade.models import StructureResource as OptimadeStructure
from optimade.models import StructureResourceAttributes
from optimade.models.utils import anonymize_formula, reduce_formula

__all__ = (
    "get_dict",
    "from_dict",
)

def get_dict(optimade_structure: OptimadeStructure) -> dict:
    """Get standard python mapped dictionary from OPTIMADE structure.

    This function will return a python dictionary based on the OPTIMADE structure.

    # For structures that are periodic in one or more dimensions, a pymatgen `Structure` is returned when valid lattice_vectors are given.
    # This means, if the any of the values in the [`dimension_types`][optimade.models.structures.StructureResourceAttributes.dimension_types]
    # attribute is `1`s or if [`nperiodic_dimesions`][optimade.models.structures.StructureResourceAttributes.nperiodic_dimensions] > 0.

    # Otherwise, a pymatgen `Molecule` is returned.

    Parameters:
        optimade_structure: OPTIMADE structure.

    Returns:
        A python dictionary.

    """
    # if valid_lattice_vector(optimade_structure.attributes.lattice_vectors) and (  # type: ignore[arg-type]
    #     optimade_structure.attributes.nperiodic_dimensions > 0  # type: ignore[operator]
    #     or any(optimade_structure.attributes.dimension_types)  # type: ignore[arg-type]
    # ):
    #     return _get_structure(optimade_structure)

    return _get_structure(optimade_structure)

def _get_structure(optimade_structure: Union[OptimadeStructure, StructureResourceAttributes]) -> dict:
    """Create a python dictionary from an OPTIMADE structure."""
    if isinstance(optimade_structure, OptimadeStructure):   
        opt_attributes = optimade_structure.attributes
    elif isinstance(optimade_structure, StructureResourceAttributes):
        opt_attributes = optimade_structure

    return opt_attributes.model_dump()

def from_dict(attributes: dict) -> StructureResourceAttributes:
    """Create an OPTIMADE structure from a python dictionary."""

    if not isinstance(attributes, dict):
        raise RuntimeError(
            f"Cannot convert type {type(attributes)} into an OPTIMADE `StructureResourceAttributes` model using this method, please provide a dictionary."
        )

    return StructureResourceAttributes(**attributes)