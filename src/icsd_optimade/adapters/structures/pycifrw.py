"""
Convert an OPTIMADE structure, in the format of
[`StructureResource`][optimade.models.structures.StructureResource]
to and from a standard pycifrw CifFile object.
"""

import math
import re
from collections import defaultdict
from typing import Any, TypedDict, Union

import CifFile
import numpy as np
from ase.cell import Cell
from ase.spacegroup import Spacegroup
from optimade.adapters import Reference
from optimade.adapters.structures.utils import UncertainFloat
from optimade.models import Person, StructureResource, StructureResourceAttributes
from optimade.models import Species as OptimadeStructureSpecies
from optimade.models.utils import _reduce_or_anonymize_formula
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
    """Blindly strip the uncertainty from a cif value, returning only the nominal value as a float."""
    return float(x.split("(")[0])


def _strip_atom_symbol(symbol: str) -> str:
    """Strip the trailing digits from the atom site type symbols to get the atomic symbols"""
    return re.sub(r"\d.*$", "", symbol)


def _get_elements_ratios(
    pycifrw_structure: CifFile,
) -> tuple[list[str], list[float], int, str, str]:
    """
    Get the elements ratios from the cif formula

    Parameters
    -----------
    pycifrw_structure: CifFile - The cif structure to extract the elements ratios from

    Returns
    -----------
    elements: list[str] - The list of elements in the structure
    elements_ratios: list[float] - The list of element ratios in the structure, calculated from the formula
    n_elements: int - The number of elements in the structure
    formula_string: str - The original formula string from the cif file
    chemical_formula_reduced: str - The reduced chemical formula calculated from the original formula string, where the element ratios have been reduced to the smallest integer ratio
    """
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

    chemical_formula_reduced = ""

    # If we have floating proprtions (should be int ideally...) then
    # multiply by the 10** mantissa places and use the nearest integer
    # elements, float_proportions = zip(*[(element, float(x)) for element, x in el_dict.items()])
    mantissas = [str(float(x)).split(".")[1] for x in float_proportions]
    # Remove any which are all zero
    mantissas = [
        mantissa
        for mantissa in mantissas
        if not all(digit == "0" for digit in mantissa)
    ]

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

    return (
        elements,
        elements_ratios,
        n_elements,
        formula_string,
        chemical_formula_reduced,
    )


def _get_anisotropic_factors(
    pycifrw_structure: CifFile, atom_site_label: str
) -> dict[str, Any]:
    """
    Get the anisotropic factors for a given atom site label from the cif structure, if they exist.

    Parameters
    -----------
    pycifrw_structure: CifFile - The cif structure to extract the anisotropic factors from
    atom_site_label: str - The atom site label to extract the anisotropic factors for

    Returns
    -----------
    A dictionary of anisotropic factors for the given atom site label, keyed by the type of anisotropic factor (U, B or beta) and then the specific factor (e.g. _atom_site_aniso_U_11). If the anisotropic factor does not exist, it is omitted from the dictionary.
    """
    if any(
        key in pycifrw_structure
        for key in [
            "_atom_site_aniso_U_11",
            "_atom_site_aniso_B_11",
            "_atom_site_aniso_beta_11",
        ]
    ):
        try:
            i = pycifrw_structure["_atom_site_aniso_label"].index(atom_site_label)
        except ValueError:
            return {}
    else:
        return {}

    if "_atom_site_aniso_U_11" in pycifrw_structure:
        return {
            "_anisotropic_U_factors": {
                "_atom_site_aniso_U_11": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_U_11"][i]
                ),
                "_atom_site_aniso_U_22": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_U_22"][i]
                ),
                "_atom_site_aniso_U_33": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_U_33"][i]
                ),
                "_atom_site_aniso_U_12": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_U_12"][i]
                ),
                "_atom_site_aniso_U_13": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_U_13"][i]
                ),
                "_atom_site_aniso_U_23": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_U_23"][i]
                ),
            }
        }

    elif "_atom_site_aniso_B_11" in pycifrw_structure:
        return {
            "_anisotropic_B_factors": {
                "_atom_site_aniso_B_11": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_B_11"][i]
                ),
                "_atom_site_aniso_B_22": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_B_22"][i]
                ),
                "_atom_site_aniso_B_33": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_B_33"][i]
                ),
                "_atom_site_aniso_B_12": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_B_12"][i]
                ),
                "_atom_site_aniso_B_13": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_B_13"][i]
                ),
                "_atom_site_aniso_B_23": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_B_23"][i]
                ),
            }
        }

    elif "_atom_site_aniso_beta_11" in pycifrw_structure:
        return {
            "_anisotropic_beta_factors": {
                "_atom_site_aniso_beta_11": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_beta_11"][i]
                ),
                "_atom_site_aniso_beta_22": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_beta_22"][i]
                ),
                "_atom_site_aniso_beta_33": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_beta_33"][i]
                ),
                "_atom_site_aniso_beta_12": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_beta_12"][i]
                ),
                "_atom_site_aniso_beta_13": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_beta_13"][i]
                ),
                "_atom_site_aniso_beta_23": UncertainFloat(
                    pycifrw_structure["_atom_site_aniso_beta_23"][i]
                ),
            }
        }

    return {}


def _get_species_enumerated(
    pycifrw_structure: CifFile,
) -> tuple[
    list[OptimadeStructureSpecies],
    list[str],
    list[tuple[float, float, float]],
    list[list[float]],
    list[float],
    list[str],
    dict[str, dict[str, dict[str, float]]],
    dict[str, Any],
    dict[str, list[dict[str, float]]],
]:
    """
    Generate the cell data, loop through the species from the atom site type symbols, construct
    equivalent sites and store anisotropic factors and uncertainties. Generate unique labels
    for each site and cast to cartesian coordinates, storing as Optimade StructureSpecies objects.

    Parameters
    -----------
    pycifrw_structure: CifFile: The pycifrw structure to extract the species data from


    Returns
    -----------
    species_list: list[OptimadeStructureSpecies] - The list of species in the structure
    species_at_sites: list[str] - The list of unique labels stored in species_list
    fractional_sites: list[Tuple[float, float, float]] - The list of fractional coordinates for each site
    cartesian_sites: list[list[float]] - The list of cartesian coordinates for each site
    cell: List[float] - The 6 cell lattice parameters in the order [a, b, c, alpha, beta, gamma]
    structure_features: list[str] - The list of optimade flags for structure features, currently only 'disorder' is supported
    anisotropic_displacements: dict[str, dict[str, dict[str, float]]] - A dictionary of anisotropic displacement parameters for each site, keyed by the site label, then the atom site label, then each of the 6 displacement vectors
    cell_uncertainties: dict[str, float] - A dictionary of uncertainties for the cell lattice parameters, keyed by the parameter name
    site_uncertainties: dict[str, List[Dict[str, float]]]] - A dictionary of uncertainties for the site labels, where each dictionary in the list is keyed by the original atomic label and its x,y,z fractional and cartesian uncertainties, keyed by the format {atomic_label}_{x/y/z}_{fractional/cartesian}
    """

    cell_vectors = [
        UncertainFloat(pycifrw_structure["_cell_length_a"]),
        UncertainFloat(pycifrw_structure["_cell_length_b"]),
        UncertainFloat(pycifrw_structure["_cell_length_c"]),
        UncertainFloat(pycifrw_structure["_cell_angle_alpha"]),
        UncertainFloat(pycifrw_structure["_cell_angle_beta"]),
        UncertainFloat(pycifrw_structure["_cell_angle_gamma"]),
    ]

    cell = Cell.new([x.value for x in cell_vectors])
    cell_uncertainties = {
        "a": cell_vectors[0].uncertainty,
        "b": cell_vectors[1].uncertainty,
        "c": cell_vectors[2].uncertainty,
        "alpha": cell_vectors[3].uncertainty,
        "beta": cell_vectors[4].uncertainty,
        "gamma": cell_vectors[5].uncertainty,
    }

    class TemporarySpecies(TypedDict):
        symbol: str
        concentration: float
        site: tuple[float, float, float]
        aniso_factors: dict[str, Any]
        atom_site_label: str
        uncertainties: dict[str, float]

    atom_site_species: list[TemporarySpecies] = []

    for i, (atom_site_label, concentration, x, y, z) in enumerate(
        zip(
            pycifrw_structure["_atom_site_label"],
            pycifrw_structure["_atom_site_occupancy"],
            pycifrw_structure["_atom_site_fract_x"],
            pycifrw_structure["_atom_site_fract_y"],
            pycifrw_structure["_atom_site_fract_z"],
        )
    ):
        # Cast any Deuterium or Tritium symbols to Hydrogen
        # Use regex to switch D or T exactly, leaving trailing digits intact and skipping Dy etc.
        symbol = re.sub(r"(D|T)(?![a-z])", "H", atom_site_label)
        concentration = _strip_uncertainty(concentration)
        site = (_strip_uncertainty(x), _strip_uncertainty(y), _strip_uncertainty(z))

        aniso_factors = _get_anisotropic_factors(pycifrw_structure, atom_site_label)

        fractional_uncertainty_tensor = np.array(
            [
                UncertainFloat(x).uncertainty,
                UncertainFloat(y).uncertainty,
                UncertainFloat(z).uncertainty,
            ]
        )

        cartesian_uncertainty_tensor = cell.cartesian_positions(
            fractional_uncertainty_tensor
        )

        if sum(fractional_uncertainty_tensor) > 0:
            atom_site_uncertainties = {
                f"{atom_site_label}_x_fractional": float(
                    fractional_uncertainty_tensor[0]
                ),
                f"{atom_site_label}_y_fractional": float(
                    fractional_uncertainty_tensor[1]
                ),
                f"{atom_site_label}_z_fractional": float(
                    fractional_uncertainty_tensor[2]
                ),
                f"{atom_site_label}_x_cartesian": float(
                    cartesian_uncertainty_tensor[0]
                ),
                f"{atom_site_label}_y_cartesian": float(
                    cartesian_uncertainty_tensor[1]
                ),
                f"{atom_site_label}_z_cartesian": float(
                    cartesian_uncertainty_tensor[2]
                ),
            }
        else:
            atom_site_uncertainties = {}

        species = TemporarySpecies(
            symbol=symbol,
            concentration=concentration,
            site=site,
            aniso_factors=aniso_factors,
            atom_site_label=atom_site_label,
            uncertainties=atom_site_uncertainties,
        )

        atom_site_species.append(species)

    class SiteData(TypedDict):
        symbols: list[Any]
        concentrations: list[Any]
        equivalent_sites: list[Any]
        _anisotropic_factors: list[dict[str, Any]]
        _atom_site_labels: list[Any]
        _uncertainties: list[dict[str, float]]
        label: str

    # For each of the site coordinates, we need to calculate the atomic label
    temp_sites_struct: defaultdict[tuple[float, float, float], SiteData] = defaultdict(
        lambda: {
            "symbols": [],
            "concentrations": [],
            "_anisotropic_factors": [],
            "_atom_site_labels": [],
            "_uncertainties": [],
            "label": "",
            "equivalent_sites": [],
        }
    )

    for x in atom_site_species:
        temp_sites_struct[x["site"]]["symbols"].append(_strip_atom_symbol(x["symbol"]))  # noqa: Q000
        temp_sites_struct[x["site"]]["concentrations"].append(x["concentration"])
        temp_sites_struct[x["site"]]["_anisotropic_factors"].append(x["aniso_factors"])
        temp_sites_struct[x["site"]]["_atom_site_labels"].append(x["atom_site_label"])
        temp_sites_struct[x["site"]]["_uncertainties"].append(x["uncertainties"])

    # Calculate the concentrations of any vacancy symbols
    for site, site_data in temp_sites_struct.items():
        total_ratio = sum(site_data["concentrations"])
        if total_ratio > 1.0:
            raise ValueError(
                f"The concentration at the site {site} is greater than 1.0, please check the CIF file."
            )

        if total_ratio < 1.0:
            vacancy_concentration = 1.0 - total_ratio
            site_data["symbols"].append("vacancy")
            site_data["concentrations"].append(vacancy_concentration)

    sg = Spacegroup(int(pycifrw_structure["_space_group_IT_number"]))

    for site in temp_sites_struct.keys():
        temp_sites_struct[site]["equivalent_sites"] = sg.equivalent_sites(
            np.array(site)
        )[0].tolist()

    # Now that we have all of the equivalent sites, we must work out the labels for these.
    atomic_label_counter: dict[str, int] = defaultdict(lambda: 1)

    for site in temp_sites_struct.keys():
        atom_label = "".join(sorted(list(set(temp_sites_struct[site]["symbols"]))))
        temp_sites_struct[site]["label"] = (
            f"{atom_label}_{atomic_label_counter[atom_label]}"
        )

        atomic_label_counter[atom_label] += 1

    # Now that we have all of the fractional coordinates and labels, we can construct the species list
    species_at_sites: list[str] = []
    species_list: list[OptimadeStructureSpecies] = []
    fractional_sites: list[tuple[float, float, float]] = []
    anisotropic_displacements: dict[str, dict[str, dict[str, float]]] = {}
    site_uncertainties: dict[str, list[dict[str, float]]] = {}

    # Use ase cell to convert the fractional coordinates to cartesian coordinates
    cartesian_sites: list[list[float]] = []

    for site, site_data in temp_sites_struct.items():
        label = site_data["label"] + "_1"
        fractional_sites.append(site)
        cart_coords = cell.cartesian_positions(np.array(site).reshape(-1, 3))
        cartesian_sites.append(cart_coords.reshape(-1).tolist())
        species_at_sites.append(label)
        species_list.append(
            OptimadeStructureSpecies(
                name=label,
                chemical_symbols=site_data["symbols"],
                concentration=site_data["concentrations"],
            )
        )

        if any([len(x) > 0 for x in site_data["_anisotropic_factors"]]):
            anisotropic_displacements[label] = {
                site_data["_atom_site_labels"][i]: site_data["_anisotropic_factors"][i]
                for i in range(len(site_data["_anisotropic_factors"]))
            }

        if any([len(x) > 0 for x in site_data["_uncertainties"]]):
            site_uncertainties[label] = site_data["_uncertainties"]

        for i, equivalent_site in enumerate(site_data["equivalent_sites"]):
            label = site_data["label"] + f"_{i + 2}"
            fractional_sites.append(equivalent_site)
            cart_coords = cell.cartesian_positions(
                np.array(equivalent_site).reshape(-1, 3)
            )
            cartesian_sites.append(cart_coords.reshape(-1).tolist())
            species_at_sites.append(label)
            species_list.append(
                OptimadeStructureSpecies(
                    name=label,
                    chemical_symbols=site_data["symbols"],
                    concentration=site_data["concentrations"],
                )
            )

            if any([len(x) > 0 for x in site_data["_anisotropic_factors"]]):
                anisotropic_displacements[label] = {
                    site_data["_atom_site_labels"][i]: site_data[
                        "_anisotropic_factors"
                    ][i]
                    for i in range(len(site_data["_anisotropic_factors"]))
                }

            if any([len(x) > 0 for x in site_data["_uncertainties"]]):
                site_uncertainties[label] = site_data["_uncertainties"]

    # Check the structure features flag by seeing if any site has disorder
    structure_features = []

    for site in species_list:
        if len(site.chemical_symbols) > 1:
            structure_features.append("disorder")
            break

    return (
        species_list,
        species_at_sites,
        fractional_sites,
        cartesian_sites,
        cell.tolist(),
        structure_features,
        anisotropic_displacements,
        cell_uncertainties,
        site_uncertainties,
    )


def _get_reference_fields(pycifrw_structure: CifFile) -> list[dict[str, Any]]:
    """Get the reference fields from the cif file, if they exist.

    Parameters:
    -----------
    pycifrw_structure: CifFile: The pycifrw structure to extract the reference fields from

    Returns:
    --------
    List[Dict[str, Any]]
    A list of 'data' keyed Reference fields extracted from the cif file, if they exist.
    If no reference fields exist, an empty list is returned.
    """
    references = []

    if "_citation_id" in pycifrw_structure:
        for i, (_citation_id) in enumerate(pycifrw_structure["_citation_id"]):
            if "_citation_journal_full" in pycifrw_structure:
                journal = pycifrw_structure["_citation_journal_full"][i]
            elif "_citation_journal_abbrev" in pycifrw_structure:
                journal = pycifrw_structure["_citation_journal_abbrev"][i]
            elif "_citation_journal_id_ASTM" in pycifrw_structure:
                journal = pycifrw_structure["_citation_journal_id_ASTM"][i]
            else:
                journal = None

            if "_citation_doi" in pycifrw_structure:
                doi = pycifrw_structure["_citation_doi"][i]
            else:
                doi = None

            if "_citation_year" in pycifrw_structure:
                year = pycifrw_structure["_citation_year"][i]
            else:
                year = None

            if "_citation_title" in pycifrw_structure:
                title = pycifrw_structure["_citation_title"][i]
            else:
                title = None

            if "_audit_creation_date" in pycifrw_structure:
                last_modified = pycifrw_structure["_audit_creation_date"]
            elif "_cif_audit_creation_date" in pycifrw_structure:
                last_modified = pycifrw_structure["_cif_audit_creation_date"]
            else:
                last_modified = None

            ref_entry = {
                "id": _citation_id,
                "type": "references",
                "attributes": {
                    "doi": doi,
                    "last_modified": last_modified,
                    "authors": [],
                    "year": year,
                    "title": title,
                    "journal": journal,
                },
            }

            references.append({"data": Reference(ref_entry)})

    # Add the author data if available
    if len(references) > 0:
        if "_citation_author_citation_id" in pycifrw_structure:
            for citation_id, author_name in zip(
                pycifrw_structure["_citation_author_citation_id"],
                pycifrw_structure["_citation_author_name"],
            ):
                for ref in references:
                    if ref["data"].entry.id == citation_id:
                        ref["data"].entry.attributes.authors.append(
                            Person(name=author_name)
                        )

    return references


def from_pycifrw(
    pycifrw_structure: CifFile, id: Union[None, str] = None
) -> StructureResourceAttributes:
    """Create an OPTIMADE structure from a pycifrw StarFile object.

    This function will return an OPTIMADE structure based on the pycifrw StarFile object.

    Parameters:
    -----------
    pycifrw_structure: The pycifrw StarFile object to convert.
    id: The id to use for the structure (default: None).

    Returns:
    --------
    An OPTIMADE structure based on the pycifrw StarFile object.
    """
    attributes: StructureResourceAttributes = {}
    pycfrw_d = pycifrw_structure[pycifrw_structure.keys()[0]]

    (
        attributes["species"],
        attributes["species_at_sites"],
        attributes["fractional_site_positions"],
        attributes["cartesian_site_positions"],
        attributes["lattice_vectors"],
        attributes["structure_features"],
        attributes["anisotropic_displacements"],
        attributes["cell_uncertainties"],
        attributes["site_uncertainties"],
    ) = _get_species_enumerated(pycfrw_d)

    attributes["nsites"] = len(attributes["fractional_site_positions"])

    (
        attributes["elements"],
        attributes["elements_ratios"],
        attributes["nelements"],
        attributes["chemical_formula_descriptive"],
        attributes["chemical_formula_reduced"],
    ) = _get_elements_ratios(pycfrw_d)

    attributes["references"] = _get_reference_fields(pycfrw_d)

    attributes["dimension_types"] = [1, 1, 1]
    attributes["nperiodic_dimensions"] = 3

    attributes["chemical_formula_anonymous"] = _reduce_or_anonymize_formula(
        attributes["chemical_formula_reduced"], alphabetize=True, anonymize=True
    )

    attributes["last_modified"] = None
    attributes["immutable_id"] = id

    return StructureResourceAttributes(**attributes)
