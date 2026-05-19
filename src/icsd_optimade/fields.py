"""Construct provider-specific fields and info for the ICSD OPTIMADE implementation,
borrows heavily from the csd-optimade implementation.

"""

from optimade import __api_version__
from optimade import __version__ as __tools_version__
from optimade.models.baseinfo import BaseInfoAttributes, BaseInfoResource

from icsd_optimade import __version__


def generate_provider_fields() -> dict[str, list[dict[str, str]]]:
    # TODO: replace placeholder descriptions with those from CIF
    return {
        "references": [],
        "structures": [
            {
                "name": "_cif_chemical_name_common",
                "type": "string",
                "description": "Chemical name",
            },
            {
                "name": "_chemical_formula_structural",
                "type": "string",
                "description": "See also chemical_formula_descriptive.",
            },
            {
                "name": "_cif_chemical_formula_sum",
                "type": "string",
                "description": "Chemical formula sum",
            },
            {
                "name": "_cif_chemical_name_structure_type",
                "type": "string",
                "description": "Structure type",
            },
            {
                "name": "_cif_exptl_crystal_density_diffrn",
                "type": "float",
                "description": "Density from diffrn",
            },
            {
                "name": "_cif_diffrn_ambient_temperature",
                "type": "float",
                "description": "Temperature during diffrn",
            },
            {
                "name": "_cif_audit_creation_date",
                "type": "string",
                "format": "date-time",
                "description": "Creation date of the CIF file.",
            },
            {
                "name": "_cif_cell_formula_units_z",  # Note lowercase 'Z' vs CIF standard
                "type": "integer",
                "description": "Number of formula units in the unit cell (Z).",
            },
            {
                "name": "_cif_cell_volume",
                "type": "float",
                "description": "Unit cell volume in cubic angstroms.",
            },
            {
                "name": "_cif_cell_length_a",
                "type": "float",
                "description": "Unit cell length a in angstroms.",
            },
            {
                "name": "_cif_cell_length_a_uncertainty",
                "type": "float",
                "description": "Standard uncertainty of unit cell length a.",
            },
            {
                "name": "_cif_cell_length_a_raw",
                "type": "string",
                "description": "Raw string value of unit cell length a from the CIF.",
            },
            {
                "name": "_cif_cell_length_b",
                "type": "float",
                "description": "Unit cell length b in angstroms.",
            },
            {
                "name": "_cif_cell_length_b_uncertainty",
                "type": "float",
                "description": "Standard uncertainty of unit cell length b.",
            },
            {
                "name": "_cif_cell_length_b_raw",
                "type": "string",
                "description": "Raw string value of unit cell length b from the CIF.",
            },
            {
                "name": "_cif_cell_length_c",
                "type": "float",
                "description": "Unit cell length c in angstroms.",
            },
            {
                "name": "_cif_cell_length_c_uncertainty",
                "type": "float",
                "description": "Standard uncertainty of unit cell length c.",
            },
            {
                "name": "_cif_cell_length_c_raw",
                "type": "string",
                "description": "Raw string value of unit cell length c from the CIF.",
            },
            {
                "name": "_cif_cell_angle_alpha",
                "type": "float",
                "description": "Unit cell angle alpha in degrees.",
            },
            {
                "name": "_cif_cell_angle_alpha_uncertainty",
                "type": "float",
                "description": "Standard uncertainty of unit cell angle alpha.",
            },
            {
                "name": "_cif_cell_angle_alpha_raw",
                "type": "string",
                "description": "Raw string value of unit cell angle alpha from the CIF.",
            },
            {
                "name": "_cif_cell_angle_beta",
                "type": "float",
                "description": "Unit cell angle beta in degrees.",
            },
            {
                "name": "_cif_cell_angle_beta_uncertainty",
                "type": "float",
                "description": "Standard uncertainty of unit cell angle beta.",
            },
            {
                "name": "_cif_cell_angle_beta_raw",
                "type": "string",
                "description": "Raw string value of unit cell angle beta from the CIF.",
            },
            {
                "name": "_cif_cell_angle_gamma",
                "type": "float",
                "description": "Unit cell angle gamma in degrees.",
            },
            {
                "name": "_cif_cell_angle_gamma_uncertainty",
                "type": "float",
                "description": "Standard uncertainty of unit cell angle gamma.",
            },
            {
                "name": "_cif_cell_angle_gamma_raw",
                "type": "string",
                "description": "Raw string value of unit cell angle gamma from the CIF.",
            },
            # {
            #    "name": "_cif_space_group_name_H-M_alt",
            #    "type": "string",
            #    "description": "spg symbol",
            # },
        ],
    }


def generate_provider_info():
    return {
        "prefix": "icsd",
        "name": "Inorganic Crystal Structure Database (ICSD)",
        "description": "A database of fully determined inorganic crystal structures.",
        "homepage": "https://icsd.fiz-karlsruhe.de/",
    }


def generate_implementation_info():
    return {
        "name": f"ICSD OPTIMADE (based on optimade-python-tools {__tools_version__})",
        "version": __version__,
        "source_url": "https://github.com/datalab-industries/icsd-optimade",
        "issue_tracker": "https://github.com/datalab-industries/icsd-optimade",
        "homepage": "https://github.com/datalab-industries/icsd-optimade",
    }


def generate_license_link():
    return "https://icsd.products.fiz-karlsruhe.de/en/support/support"


def generate_icsd_info_endpoint() -> dict[str, BaseInfoResource]:
    return {
        "data": BaseInfoResource(
            attributes=BaseInfoAttributes(
                api_version=__api_version__,
                available_api_versions=[],
                formats=["json"],
                available_endpoints=["info", "structures", "references"],
                entry_types_by_format={"json": ["info", "structures", "references"]},
                is_index=False,
                license={"href": generate_license_link()},
                available_licenses=None,
            )
        )
    }
