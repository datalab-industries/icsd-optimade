"""Construct provider-specific fields and info for the ICSD OPTIMADE implementation,
borrows heavily from the csd-optimade implementation.

"""

import datetime

from optimade import __api_version__
from optimade import __version__ as __tools_version__
from optimade.models import StructureResource, StructureResourceAttributes
from optimade.models.baseinfo import BaseInfoAttributes, BaseInfoResource
from optimade.models.utils import OptimadeField
from pydantic import model_validator

from icsd_optimade import __version__
from icsd_optimade.adapters.structures.utils import UncertainFloat


class CifStructureResourceAttributes(StructureResourceAttributes):
    cif_chemical_name_common: str | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_chemical_name_common"
    )
    cif_chemical_formula_structural: str | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_chemical_formula_structural"
    )
    cif_chemical_formula_sum: str | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_chemical_formula_sum"
    )
    cif_chemical_name_structure_type: str | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_chemical_name_structure_type"
    )
    cif_exptl_crystal_density_diffrn: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_exptl_crystal_density_diffrn"
    )
    cif_diffrn_ambient_temperature: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_diffrn_ambient_temperature"
    )
    cif_audit_creation_date: datetime.datetime | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_audit_creation_date"
    )
    cif_cell_formula_units_z: int | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_formula_units_z"
    )
    cif_cell_volume: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_volume"
    )
    cif_cell_length_a: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_length_a"
    )
    cif_cell_length_b: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_length_b"
    )
    cif_cell_length_c: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_length_c"
    )
    cif_cell_length_a_uncertainty: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_length_a_uncertainty"
    )
    cif_cell_length_b_uncertainty: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_length_b_uncertainty"
    )
    cif_cell_length_c_uncertainty: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_length_c_uncertainty"
    )
    cif_cell_angle_alpha: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_angle_alpha"
    )
    cif_cell_angle_beta: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_angle_beta"
    )
    cif_cell_angle_gamma: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_angle_gamma"
    )
    cif_cell_angle_alpha_uncertainty: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_angle_alpha_uncertainty"
    )
    cif_cell_angle_beta_uncertainty: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_angle_beta_uncertainty"
    )
    cif_cell_angle_gamma_uncertainty: float | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_cell_angle_gamma_uncertainty"
    )
    cif_space_group_name_H__M_alt: str | None = OptimadeField(
        None, description="See CIF dict", alias="_cif_space_group_name_H-M_alt"
    )

    @model_validator(mode="before")
    def cast_uncertain_floats(cls, values):
        """Cast uncertain floats to UncertainFloat objects."""

        uncertain_float_fields = [
            "_cif_cell_length_a",
            "_cif_cell_length_b",
            "_cif_cell_length_c",
            "_cif_cell_angle_alpha",
            "_cif_cell_angle_beta",
            "_cif_cell_angle_gamma",
        ]

        for field in uncertain_float_fields:
            if field in values and values[field] is not None:
                unc_float = UncertainFloat(values[field])
                values[field] = unc_float.value
                if unc_float.uncertainty == 0.0:
                    values[f"{field}_uncertainty"] = None
                else:
                    values[f"{field}_uncertainty"] = unc_float.uncertainty

        return values


class CifStructureResource(StructureResource):
    attributes: CifStructureResourceAttributes


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
            {
                "name": "_cif_space_group_name_H-M_alt",
                "type": "string",
                "description": "spg symbol",
            },
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
