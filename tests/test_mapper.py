import datetime
import json

from optimade.models import ReferenceResource, StructureResource


def test_cif_mapper_111000(icsd_client):
    from icsd_optimade.ingest import map_cif_to_optimade

    json_str = map_cif_to_optimade(111000, icsd_client)

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

    assert structure.relationships.references.data[0].id == "604000"


def test_cif_mapper_86(icsd_client):
    from icsd_optimade.ingest import map_cif_to_optimade

    json_str = map_cif_to_optimade(86, icsd_client)

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
    assert structure.attributes.last_modified == datetime.datetime(2000, 7, 15)
    assert structure.attributes.space_group_it_number == 51
    assert structure.attributes._cif_cell_length_a == 6.553
    assert structure.attributes._cif_cell_length_b == 6.0
    assert structure.attributes._cif_cell_length_c == 10.563
    assert structure.attributes._cif_cell_angle_alpha == 90
    assert structure.attributes._cif_cell_angle_beta == 90
    assert structure.attributes._cif_cell_angle_gamma == 90

    assert structure.relationships.references.data[0].id == "115"
    assert reference.attributes.year == "1976"
    assert reference.attributes.authors[0].name == "Kipka, R."
    assert reference.attributes.authors[1].name == "Müller-Buschbaum, Hk."
