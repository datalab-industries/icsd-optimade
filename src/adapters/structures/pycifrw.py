"""
Convert an OPTIMADE structure, in the format of
[`StructureResource`][optimade.models.structures.StructureResource]
to and from a standard pycifrw CifFile object.
"""

from collections import Counter, defaultdict
import re
import CifFile
import numpy as np
from optimade.adapters.structures.adapter import from_pymatgen
from optimade.models import StructureResource

from optimade.models import Species as OptimadeStructureSpecies
from optimade.models import StructureResource as OptimadeStructure
from optimade.models import StructureResourceAttributes
from optimade.models.utils import anonymize_formula, reduce_formula, _reduce_or_anonymize_formula

from CifFile.CifFile_module import CifFile
from ase.cell import Cell

def get_pycifrw(optimade_structure: StructureResource) -> CifFile:
    """Get pycifrw StarFile object from OPTIMADE structure.

    This function will return a pycifrw StarFile object based on the OPTIMADE structure.
    """
    # First convert to a pymatgen object to assist in fractional/cartesian mapping

    attributes = optimade_structure.attributes.model_dump()

    cell = Cell(attributes["lattice_vectors"])
    pycifrw_structure = CifFile()

    a, b, c = cell.lengths()
    alpha, beta, gamma = cell.angles()

    pycifrw_structure["_cell_length_a"] = a
    pycifrw_structure["_cell_length_b"] = b
    pycifrw_structure["_cell_length_c"] = c
    pycifrw_structure["_cell_angle_alpha"] = alpha
    pycifrw_structure["_cell_angle_beta"] = beta
    pycifrw_structure["_cell_angle_gamma"] = gamma

    pycifrw_structure["_atom_site_label"] 




    return pycifrw_structure

def _strip_uncertainty(x: str) -> float:
    return float(x.split('(')[0])

def _get_cell_cart_coords(pycifrw_structure: CifFile) -> Cell:
    ''' Construct an ase cell object and use to convert fractional to cartesian coordinates
    '''
    # TODO: Store uncertainty?
    cell = Cell.new([
        _strip_uncertainty(pycifrw_structure["_cell_length_a"]),
        _strip_uncertainty(pycifrw_structure["_cell_length_b"]),
        _strip_uncertainty(pycifrw_structure["_cell_length_c"]),
        _strip_uncertainty(pycifrw_structure["_cell_angle_alpha"]),
        _strip_uncertainty(pycifrw_structure["_cell_angle_beta"]),
        _strip_uncertainty(pycifrw_structure["_cell_angle_gamma"])
    ])

    (fractional_site_positions_x, 
    fractional_site_positions_y, 
    fractional_site_positions_z) = (pycifrw_structure["_atom_site_fract_x"], 
                                    pycifrw_structure["_atom_site_fract_y"], 
                                    pycifrw_structure["_atom_site_fract_z"])

    frac_coords = list(zip(fractional_site_positions_x, fractional_site_positions_y, fractional_site_positions_z))
    frac_coords = [_strip_uncertainty(y) for x in frac_coords for y in x]
    frac_coords = np.array(frac_coords).reshape(-1, 3)
    cart_coords = cell.cartesian_positions(frac_coords)

    return cell, cart_coords

def _strip_atom_symbol(symbol: str) -> str:
    ''' Strip the trailing digits from the atom site type symbols to get the atomic symbols '''
    return re.sub(r"\d.*$", "", symbol)

def _get_atom_symbols(pycifrw_structure: CifFile) -> list[str]:
    ''' Strip the trailing digits from the atom site type symbols to get the atomic symbols '''
    return [symbol for symbol in pycifrw_structure["_atom_site_label"]]

def _get_elements_ratios(species_at_sites: list[str]) -> list[float]:
    ''' Get the elements ratios from the atom site type symbols '''
    elements = set([symbol for symbol in species_at_sites])
    counts = {e: species_at_sites.count(e) for e in elements}
    num_sites = len(species_at_sites)
    return [counts[e] / num_sites for e in sorted(elements)]

def _get_species(pycifrw_structure: CifFile) -> tuple[list[OptimadeStructureSpecies], np.ndarray]:
    ''' Get the species from the atom site type symbols '''

    # First construct the mapping keyed by site position, return the cartesian keys as the site positions
    species_list = []
    
    for symbol, concentration, x, y, z in zip(pycifrw_structure["_atom_site_label"], 
                                                pycifrw_structure["_atom_site_occupancy"],
                                                pycifrw_structure["_atom_site_fract_x"],
                                                pycifrw_structure["_atom_site_fract_y"],
                                                pycifrw_structure["_atom_site_fract_z"]):
        species_list.append([symbol, 
                            _strip_uncertainty(concentration), 
                            (_strip_uncertainty(x), _strip_uncertainty(y), _strip_uncertainty(z))])

    # Now we have all our data, we need to group by xyz site positions, and then create the species list
    sites = defaultdict(lambda: {
        "name": "",
        "symbols": [],
        "concentrations": []
    })

    for symbol, concentration, xyz in species_list:
        sites[xyz]["name"] = symbol
        sites[xyz]["symbols"].append(_strip_atom_symbol(symbol))
        sites[xyz]["concentrations"].append(concentration)

    optimade_sites = []
    fractional_sites = []

    for k, v in sites.items():
        fractional_sites.append(k)
        optimade_sites.append(OptimadeStructureSpecies(name=v["name"], 
                                chemical_symbols=v["symbols"], 
                                concentration=v["concentrations"]))

    fractional_sites = np.array(fractional_sites)

    return optimade_sites, fractional_sites

def _get_chemical_formula_descriptive(pycifrw_structure: CifFile) -> str:
    if "_chemical_formula_structural" in pycifrw_structure:
        return pycifrw_structure["_chemical_formula_structural"]
    else:
        return pycifrw_structure["_chemical_formula_sum"]

def from_pycifrw(pycifrw_structure: CifFile) -> StructureResourceAttributes:
    """Create an OPTIMADE structure from a pycifrw StarFile object.

    This function will return an OPTIMADE structure based on the pycifrw StarFile object.
    """
    attributes = {}

    pycfrw_d = pycifrw_structure[pycifrw_structure.keys()[0]]

    cell, cart_coords = _get_cell_cart_coords(pycfrw_d)
    
    attributes["lattice_vectors"] = cell.tolist()

    attributes['species_at_sites'] = _get_atom_symbols(pycfrw_d)
    attributes['elements_ratios'] = _get_elements_ratios(attributes['species_at_sites'])

    attributes['species'], frac_positions = _get_species(pycfrw_d)
    attributes["cartesian_site_positions"] = cell.cartesian_positions(frac_positions)

    attributes['dimension_types'] = [1, 1, 1]
    attributes['nperiodic_dimensions'] = 3
    attributes['nelements'] = len(attributes['species_at_sites']) # TODO should this be the count of set? 
    attributes["elements"] = sorted([_.name for _ in attributes["species"]])
    attributes["nsites"] = len(attributes["species_at_sites"])

    attributes['chemical_formula_descriptive'] = _get_chemical_formula_descriptive(pycfrw_d)

    attributes['chemical_formula_reduced'] = _reduce_or_anonymize_formula(pycfrw_d['_chemical_formula_sum'], alphabetize=True, anonymize=False)
    attributes['chemical_formula_anonymous'] = _reduce_or_anonymize_formula(pycfrw_d['_chemical_formula_sum'], alphabetize=True, anonymize=True)

    attributes["last_modified"] = None
    attributes["immutable_id"] = None
    attributes["structure_features"] = []

    # TODO add extra fields? 

    return StructureResourceAttributes(**attributes)