import datetime
import json

from optimade.models import ReferenceResource

from icsd_optimade.fields import CifStructureResource as StructureResource


def test_cif_mapper_111000(icsd_client, data_dir):
    from icsd_optimade.ingest import map_cif_to_optimade

    json_str = map_cif_to_optimade(
        111000, icsd_client, data_dir=data_dir, download=False
    )
    assert isinstance(json_str, str)

    struc_dct = json.loads(json_str.split("\n")[0])
    ref_dct = json.loads(json_str.split("\n")[1])
    assert struc_dct
    assert ref_dct
    structure = StructureResource(**struc_dct)
    assert structure

    reference = ReferenceResource(**ref_dct)
    assert reference

    assert structure.id == "604000"
    assert structure.attributes.immutable_id == "604000"
    assert structure.attributes.elements == ["Ir", "Si", "U"]
    assert structure.attributes.last_modified == datetime.datetime(2019, 8, 1)

    assert structure.relationships.references.data[0].id == "604000-0"


def test_cif_mapper_86_115(icsd_client, data_dir):
    from icsd_optimade.ingest import map_cif_to_optimade

    json_str = map_cif_to_optimade(86, icsd_client, data_dir=data_dir, download=False)
    assert isinstance(json_str, str)

    struc_dct = json.loads(json_str.split("\n")[0])
    ref_dct = json.loads(json_str.split("\n")[1])
    assert struc_dct
    assert ref_dct
    structure = StructureResource(**struc_dct)
    assert structure

    reference = ReferenceResource(**ref_dct)
    assert reference

    assert structure.id == "115"
    assert structure.attributes.immutable_id == "115"
    assert structure.attributes.elements == ["Ba", "Cl", "Cu", "O"]
    assert structure.attributes.last_modified == datetime.datetime(2000, 7, 15, 0, 0)
    assert structure.attributes.cif_audit_creation_date == datetime.datetime(
        1980, 1, 1, 0, 0
    )
    assert structure.attributes.space_group_it_number == 51
    assert structure.attributes.cif_cell_length_a == 6.553
    assert structure.attributes.cif_cell_length_b == 6.0
    assert structure.attributes.cif_cell_length_c == 10.563
    assert structure.attributes.cif_cell_angle_alpha == 90
    assert structure.attributes.cif_cell_angle_beta == 90
    assert structure.attributes.cif_cell_angle_gamma == 90
    assert structure.attributes.cif_cell_length_a_uncertainty is None
    assert structure.attributes.cif_cell_length_b_uncertainty is None
    assert structure.attributes.cif_cell_length_c_uncertainty is None
    assert structure.attributes.cif_cell_angle_alpha == 90
    assert structure.attributes.cif_cell_angle_beta == 90
    assert structure.attributes.cif_cell_angle_gamma == 90
    assert (
        structure.attributes.cif_chemical_name_common
        == "Tribarium dicopper tetraoxide dichloride"
    )

    assert structure.relationships.references.data[0].id == "115-0"
    assert reference.attributes.year == "1976"
    assert reference.attributes.authors[0].name == "Kipka, R."
    assert reference.attributes.authors[1].name == "Müller-Buschbaum, Hk."
    assert reference.attributes.title == "Zur Kenntnis von Ba3 Cu2 O4 Cl2"


def test_cif_mapper_80213_105101(icsd_client, data_dir):
    from icsd_optimade.ingest import map_cif_to_optimade

    json_str = map_cif_to_optimade(
        80213, icsd_client, data_dir=data_dir, download=False
    )
    assert isinstance(json_str, str)

    struc_dct = json.loads(json_str.split("\n")[0])
    ref_dct = json.loads(json_str.split("\n")[1])
    assert struc_dct
    assert ref_dct
    structure = StructureResource(**struc_dct)
    assert structure

    reference = ReferenceResource(**ref_dct)
    assert reference

    assert structure.id == "105101"
    assert structure.attributes.immutable_id == "105101"
    assert structure.attributes.elements == ["Mo", "Tc"]
    assert structure.attributes.last_modified == datetime.datetime(2017, 8, 1)
    assert structure.attributes.chemical_formula_descriptive == "(Mo0.4 Tc0.6)"
    assert structure.attributes.cif_chemical_name_structure_type == "Cr3Si"
    assert structure.attributes.cif_chemical_formula_structural == "(Mo0.4 Tc0.6)"
    assert structure.attributes.cif_chemical_formula_sum == "Mo0.4 Tc0.6"
    assert (
        structure.attributes.cif_chemical_name_common
        == "Molybdenum technetium (0.4/0.6)"
    )

    assert structure.relationships.references.data[0].id == "105101-0"
    assert reference.attributes.journal == "Physics Letters A"
    assert (
        reference.attributes.title
        == "A low temperature X-ray investigation of technetium and the Tc - Mo A-15 compound"
    )
