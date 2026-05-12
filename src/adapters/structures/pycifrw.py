"""
Convert an OPTIMADE structure, in the format of
[`StructureResource`][optimade.models.structures.StructureResource]
to and from a standard pycifrw CifFile object.
"""

from collections import Counter, defaultdict
import math
import re
from typing import Union
import CifFile
import numpy as np
from optimade.models import StructureResource

from optimade.models import Species as OptimadeStructureSpecies
from optimade.models import StructureResource as OptimadeStructure
from optimade.models import StructureResourceAttributes
from optimade.models.utils import anonymize_formula, reduce_formula, _reduce_or_anonymize_formula

from CifFile.CifFile_module import CifFile
from ase.cell import Cell
from ase.spacegroup import Spacegroup
from pymatgen.core import Composition

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

def _strip_atom_symbol(symbol: str) -> str:
    ''' Strip the trailing digits from the atom site type symbols to get the atomic symbols '''
    return re.sub(r"\d.*$", "", symbol)

def _get_elements_ratios(pycifrw_structure: CifFile) -> list[str, int, float]:
    ''' Get the elements ratios from the cif formula '''
    if "_chemical_formula_sum" in pycifrw_structure:
        formula_string = pycifrw_structure["_chemical_formula_sum"]
    else:
        formula_string = pycifrw_structure["_chemical_formula_structural"]
    
    formula = Composition(formula_string)

    el_dict = formula.get_el_amt_dict()

    elements = []
    float_proportions = []
    num_sites = 0

    for element in sorted(el_dict.keys()):
        elements.append(element)
        float_proportions.append(el_dict[element])
        num_sites += el_dict[element]
    
    n_elements = len(elements)
    elements_ratios = [count / num_sites for count in float_proportions] 

    chemical_formula_reduced = ''

    # If we have floating proprtions (should be int ideally...) then
    # multiply by the 10** mantissa places and use the nearest integer 
    # elements, float_proportions = zip(*[(element, float(x)) for element, x in el_dict.items()])
    mantissas = [str(float(x)).split('.')[1] for x in float_proportions]
    # Remove any which are all zero 
    mantissas = [mantissa for mantissa in mantissas if not all(digit == '0' for digit in mantissa)]
    
    order = 0
    if len(mantissas) > 0:
        order = max([len(mantissa) for mantissa in mantissas])
    
    proportions = [int(proportion * 10**order) for proportion in float_proportions]
    
    # Divide by the gcd of the proportions to give reduced integer form 
    gcd = math.gcd(*proportions)
    proportions = [proportion // gcd for proportion in proportions]
    
    for element, proportion in zip(elements, proportions):
        if int(proportion) == 1:
            chemical_formula_reduced += element
        else:
            chemical_formula_reduced += f"{element}{proportion}"

    return elements, elements_ratios, n_elements, formula_string, chemical_formula_reduced


def _get_species_enumerated(pycifrw_structure: CifFile) -> tuple[list[OptimadeStructureSpecies], np.ndarray]:
    ''' Get the species from the atom site type symbols '''

    species_list = []
    
    for symbol, concentration, x, y, z in zip(pycifrw_structure["_atom_site_label"], 
                                                pycifrw_structure["_atom_site_occupancy"],
                                                pycifrw_structure["_atom_site_fract_x"],
                                                pycifrw_structure["_atom_site_fract_y"],
                                                pycifrw_structure["_atom_site_fract_z"]):
        species_list.append([symbol, 
                            _strip_uncertainty(concentration), 
                            (_strip_uncertainty(x), _strip_uncertainty(y), _strip_uncertainty(z))])

    # For each of the site coordinates, we need to calculate the atomic label 
    temp_sites_struct = defaultdict(lambda: {
        "symbols": [],
        "concentrations": []
    })

    for symbol, concentration, xyz in species_list:
        temp_sites_struct[xyz]["symbols"].append(_strip_atom_symbol(symbol))
        temp_sites_struct[xyz]["concentrations"].append(concentration)

    # Calculate the concentrations of any vacancy symbols 
    for site, site_data in temp_sites_struct.items():
        total_ratio = sum(site_data["concentrations"])
        if total_ratio > 1.0:
            raise ValueError(f"The concentration at the site {site} is greater than 1.0, please check the CIF file.")

        if total_ratio < 1.0:
            vacancy_concentration = 1.0 - total_ratio
            site_data["symbols"].append("X")
            site_data["concentrations"].append(vacancy_concentration)

    sg = Spacegroup(int(pycifrw_structure["_space_group_IT_number"]))

    for site in temp_sites_struct.keys():
        temp_sites_struct[site]["equivalent_sites"] = sg.equivalent_sites(np.array(site))[0].tolist()

    # Now that we have all of the equivalent sites, we must work out the labels for these. 
    atomic_label_counter = defaultdict(lambda: 1)

    for site in temp_sites_struct.keys():
        atom_label = ''.join(sorted(list(set(temp_sites_struct[site]["symbols"]))))
        temp_sites_struct[site]["label"] = f"{atom_label}_{atomic_label_counter[atom_label]}"

        atomic_label_counter[atom_label] += 1 

    # Now that we have all of the fractional coordinates and labels, we can construct the species list 
    species_at_sites = []
    species_list = []
    fractional_sites = []

    # Use ase cell to convert the fractional coordinates to cartesian coordinates
    cartesian_sites = []

    cell = Cell.new([
        _strip_uncertainty(pycifrw_structure["_cell_length_a"]),
        _strip_uncertainty(pycifrw_structure["_cell_length_b"]),
        _strip_uncertainty(pycifrw_structure["_cell_length_c"]),
        _strip_uncertainty(pycifrw_structure["_cell_angle_alpha"]),
        _strip_uncertainty(pycifrw_structure["_cell_angle_beta"]),
        _strip_uncertainty(pycifrw_structure["_cell_angle_gamma"])
    ])

    for site in temp_sites_struct.keys():
        fractional_sites.append(site)
        cart_coords = cell.cartesian_positions(np.array(site).reshape(-1, 3))
        cartesian_sites.append(cart_coords.reshape(-1).tolist())
        species_at_sites.append(f"{temp_sites_struct[site]['label']}_1")
        species_list.append(
            OptimadeStructureSpecies(name=f"{temp_sites_struct[site]['label']}_1", 
                                    chemical_symbols=temp_sites_struct[site]['symbols'], 
                                    concentration=temp_sites_struct[site]['concentrations'])
        ) 

        for i, equivalent_site in enumerate(temp_sites_struct[site]["equivalent_sites"]):
            fractional_sites.append(equivalent_site)
            cart_coords = cell.cartesian_positions(np.array(equivalent_site).reshape(-1, 3))
            cartesian_sites.append(cart_coords.reshape(-1).tolist())
            species_at_sites.append(f"{temp_sites_struct[site]['label']}_{i+2}")
            species_list.append(
                OptimadeStructureSpecies(name=f"{temp_sites_struct[site]['label']}_{i+2}", 
                                        chemical_symbols=temp_sites_struct[site]['symbols'], 
                                        concentration=temp_sites_struct[site]['concentrations'])
            )

    # Check the structure features flag by seeing if any site has disorder
    structure_features = []

    for site in species_list:
        if len(site.chemical_symbols) > 1:
            structure_features.append("disorder")
            break

    return species_list, species_at_sites, fractional_sites, cartesian_sites, cell.tolist(), structure_features


def from_pycifrw(pycifrw_structure: CifFile, id: Union[None, str] = None) -> StructureResourceAttributes:
    """Create an OPTIMADE structure from a pycifrw StarFile object.

    This function will return an OPTIMADE structure based on the pycifrw StarFile object.
    """
    attributes = {}
    pycfrw_d = pycifrw_structure[pycifrw_structure.keys()[0]]

    (
        attributes['species'], 
        attributes['species_at_sites'], 
        attributes['fractional_site_positions'], 
        attributes['cartesian_site_positions'], 
        attributes["lattice_vectors"],
        attributes["structure_features"]
    ) = _get_species_enumerated(pycfrw_d)
    
    attributes['nsites'] = len(attributes['fractional_site_positions'])

    (
        attributes['elements'],
        attributes['elements_ratios'],
        attributes['nelements'],
        attributes['chemical_formula_descriptive'],
        attributes['chemical_formula_reduced']
    ) = _get_elements_ratios(pycfrw_d)

    attributes['dimension_types'] = [1, 1, 1]
    attributes['nperiodic_dimensions'] = 3
    
    attributes['chemical_formula_anonymous'] = _reduce_or_anonymize_formula(
                                                attributes['chemical_formula_reduced'], 
                                                alphabetize=True, 
                                                anonymize=True)

    attributes["last_modified"] = None
    attributes["immutable_id"] = id

    return StructureResourceAttributes(**attributes)