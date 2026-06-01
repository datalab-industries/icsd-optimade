"""
Convert an OPTIMADE structure, in the format of
[`StructureResource`][optimade.models.structures.StructureResource]
to and from a standard pycifrw CifFile object.
"""

from collections import Counter, defaultdict
import math
import re
from typing import Any, Union
import CifFile
import numpy as np
from optimade.adapters import Reference
from optimade.models import StructureResource
from optimade.models import Species as OptimadeStructureSpecies
from optimade.models import StructureResource as OptimadeStructure
from optimade.models import StructureResourceAttributes, Person
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

def _get_anisotropic_factors(pycifrw_structure: CifFile, atom_site_label: str) -> dict[str, Any]:
    if any(key in pycifrw_structure for key in ["_atom_site_aniso_U_11", "_atom_site_aniso_B_11", "_atom_site_aniso_beta_11"]):
        try:
            i = pycifrw_structure["_atom_site_aniso_label"].index(atom_site_label)
        except ValueError:
            return {}
    else:
        return {}

    if "_atom_site_aniso_U_11" in pycifrw_structure:
        return {
                "_anisotropic_U_factors": {
                                '_atom_site_aniso_U_11': pycifrw_structure["_atom_site_aniso_U_11"][i], 
                                '_atom_site_aniso_U_22': pycifrw_structure["_atom_site_aniso_U_22"][i], 
                                '_atom_site_aniso_U_33': pycifrw_structure["_atom_site_aniso_U_33"][i], 
                                '_atom_site_aniso_U_12': pycifrw_structure["_atom_site_aniso_U_12"][i], 
                                '_atom_site_aniso_U_13': pycifrw_structure["_atom_site_aniso_U_13"][i], 
                                '_atom_site_aniso_U_23': pycifrw_structure["_atom_site_aniso_U_23"][i]
                    }
                }
        # TODO cast from string to float and store the uncertainties as another field
    elif "_atom_site_aniso_B_11" in pycifrw_structure:
        return {
            "_anisotropic_B_factors": {
                        '_atom_site_aniso_B_11': pycifrw_structure["_atom_site_aniso_B_11"][i], 
                        '_atom_site_aniso_B_22': pycifrw_structure["_atom_site_aniso_B_22"][i], 
                        '_atom_site_aniso_B_33': pycifrw_structure["_atom_site_aniso_B_33"][i], 
                        '_atom_site_aniso_B_12': pycifrw_structure["_atom_site_aniso_B_12"][i], 
                        '_atom_site_aniso_B_13': pycifrw_structure["_atom_site_aniso_B_13"][i], 
                        '_atom_site_aniso_B_23': pycifrw_structure["_atom_site_aniso_B_23"][i]
                }
            }
    elif "_atom_site_aniso_beta_11" in pycifrw_structure:
        return {
            "_anisotropic_beta_factors": {
                        '_atom_site_aniso_beta_11': pycifrw_structure["_atom_site_aniso_beta_11"][i], 
                        '_atom_site_aniso_beta_22': pycifrw_structure["_atom_site_aniso_beta_22"][i], 
                        '_atom_site_aniso_beta_33': pycifrw_structure["_atom_site_aniso_beta_33"][i], 
                        '_atom_site_aniso_beta_12': pycifrw_structure["_atom_site_aniso_beta_12"][i], 
                        '_atom_site_aniso_beta_13': pycifrw_structure["_atom_site_aniso_beta_13"][i], 
                        '_atom_site_aniso_beta_23': pycifrw_structure["_atom_site_aniso_beta_23"][i]
                }
            }


def _get_species_enumerated(pycifrw_structure: CifFile) -> tuple[list[OptimadeStructureSpecies], np.ndarray]:
    ''' Get the species from the atom site type symbols '''

    species_list = []
    aniso_displacements_flag = False
    
    for i, (atom_site_label, concentration, x, y, z) in enumerate(zip(
                                                pycifrw_structure["_atom_site_label"], 
                                                pycifrw_structure["_atom_site_occupancy"],
                                                pycifrw_structure["_atom_site_fract_x"],
                                                pycifrw_structure["_atom_site_fract_y"],
                                                pycifrw_structure["_atom_site_fract_z"])):
        
        # Cast any Deuterium or Tritium symbols to Hydrogen
        # Use regex to switch D or T exactly, leaving trailing digits intact and skipping Dy etc. 
        symbol = re.sub(r"(D|T)(?![a-z])", "H", atom_site_label)

        species = [symbol, 
                    _strip_uncertainty(concentration), 
                    (_strip_uncertainty(x), _strip_uncertainty(y), _strip_uncertainty(z))]

        
        aniso_factors = _get_anisotropic_factors(pycifrw_structure, atom_site_label)
        species.append(aniso_factors)
        species.append(atom_site_label)

        if len(aniso_factors) > 0:
            aniso_displacements_flag = True

        species_list.append(species)

    # For each of the site coordinates, we need to calculate the atomic label 
    temp_sites_struct = defaultdict(lambda: {
        "symbols": [],
        "concentrations": [],
        "_anisotropic_factors": [],
        "_atom_site_labels": []
    })

    for symbol, concentration, xyz, aniso_factors, atom_site_label in species_list:
        temp_sites_struct[xyz]["symbols"].append(_strip_atom_symbol(symbol))
        temp_sites_struct[xyz]["concentrations"].append(concentration)
        temp_sites_struct[xyz]["_anisotropic_factors"].append(aniso_factors)
        temp_sites_struct[xyz]["_atom_site_labels"].append(atom_site_label)

    # Calculate the concentrations of any vacancy symbols 
    for site, site_data in temp_sites_struct.items():
        total_ratio = sum(site_data["concentrations"])
        if total_ratio > 1.0:
            raise ValueError(f"The concentration at the site {site} is greater than 1.0, please check the CIF file.")

        if total_ratio < 1.0:
            vacancy_concentration = 1.0 - total_ratio
            site_data["symbols"].append("vacancy")
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
    anisotropic_displacements = {}

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

        if aniso_displacements_flag:
            k = list(temp_sites_struct[site]['_anisotropic_factors'][0].keys())[0]
            anisotropic_displacements[f"{temp_sites_struct[site]['label']}_1"] = {
                temp_sites_struct[site]['_atom_site_labels'][i]: temp_sites_struct[site]['_anisotropic_factors'][i] for i in range(len(temp_sites_struct[site]['_anisotropic_factors']))
            }

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

            if aniso_displacements_flag:
                anisotropic_displacements[f"{temp_sites_struct[site]['label']}_{i+2}"] = {
                    temp_sites_struct[site]['_atom_site_labels'][i]: temp_sites_struct[site]['_anisotropic_factors'][i] for i in range(len(temp_sites_struct[site]['_anisotropic_factors']))
                }

    # Check the structure features flag by seeing if any site has disorder
    structure_features = []

    for site in species_list:
        if len(site.chemical_symbols) > 1:
            structure_features.append("disorder")
            break

    return species_list, species_at_sites, fractional_sites, cartesian_sites, cell.tolist(), structure_features, anisotropic_displacements


def _get_reference_fields(pycifrw_structure: CifFile, id: str) -> {str: Any}:
    references = []
    
    if '_citation_id' in pycifrw_structure:
        for i, (_citation_id) in enumerate(
                    pycifrw_structure['_citation_id']):
            if '_citation_journal_full' in pycifrw_structure:
                journal = pycifrw_structure['_citation_journal_full'][i]
            elif '_citation_journal_abbrev' in pycifrw_structure:
                journal = pycifrw_structure['_citation_journal_abbrev'][i]
            elif '_citation_journal_id_ASTM' in pycifrw_structure:
                journal = pycifrw_structure['_citation_journal_id_ASTM'][i]
            else:
                journal = None

            if '_citation_doi' in pycifrw_structure:
                doi = pycifrw_structure['_citation_doi'][i]
            else:
                doi = None

            if '_citation_year' in pycifrw_structure:
                year = pycifrw_structure['_citation_year'][i]
            else:
                year = None

            if '_citation_title' in pycifrw_structure:
                title = pycifrw_structure['_citation_title'][i]
            else:
                title = None

            if '_audit_creation_date' in pycifrw_structure:
                last_modified = pycifrw_structure["_audit_creation_date"]
            elif '_cif_audit_creation_date' in pycifrw_structure:
                last_modified = pycifrw_structure["_cif_audit_creation_date"]
            else:
                last_modified = None

            ref_entry = {
                "id": _citation_id,
                "type": "references",
                "attributes": {
                    "doi": None,
                    "last_modified": last_modified,
                    "authors": [],
                    "year": year,
                    "title": title,
                    "journal": journal,
                    "doi": doi
                }
            }

            references.append({
                "data": Reference(ref_entry)
            })

    # Add the author data if available
    # TODO Person object 
    if len(references) > 0:
        authors = []
        if '_citation_author_citation_id' in pycifrw_structure:
            for citation_id, author_name in zip(pycifrw_structure['_citation_author_citation_id'], pycifrw_structure['_citation_author_name']):
                for ref in references:
                    if ref['data'].entry.id == citation_id:
                        ref['data'].entry.attributes.authors.append(
                            Person(name=author_name)
                        )

    return references


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
        attributes["structure_features"],
        anisotropic_displacements
    ) = _get_species_enumerated(pycfrw_d)

    if len(anisotropic_displacements) > 0:
        attributes["anisotropic_displacements"] = anisotropic_displacements
    
    attributes['nsites'] = len(attributes['fractional_site_positions'])

    (
        attributes['elements'],
        attributes['elements_ratios'],
        attributes['nelements'],
        attributes['chemical_formula_descriptive'],
        attributes['chemical_formula_reduced']
    ) = _get_elements_ratios(pycfrw_d)

    attributes['references'] = _get_reference_fields(pycfrw_d, id)

    attributes['dimension_types'] = [1, 1, 1]
    attributes['nperiodic_dimensions'] = 3
    
    attributes['chemical_formula_anonymous'] = _reduce_or_anonymize_formula(
                                                attributes['chemical_formula_reduced'], 
                                                alphabetize=True, 
                                                anonymize=True)

    attributes["last_modified"] = None
    attributes["immutable_id"] = id

    return StructureResourceAttributes(**attributes)