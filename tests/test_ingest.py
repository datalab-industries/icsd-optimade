def test_cif_mapper(icsd_client):
    from icsd_optimade.ingest import map_cif_to_optimade

    assert map_cif_to_optimade(111000, icsd_client)
