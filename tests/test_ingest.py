import json
from pathlib import Path


def test_ingest(tmpdir, icsd_credentials, icsd_client):
    from icsd_optimade.ingest import ingest_by_year

    # Symlink any cached cifs from main data dir
    data_dir = Path(__file__).parent.parent / "data" / "cifs"
    tmp_data_dir = Path(tmpdir / "data")
    tmp_data_dir.mkdir(parents=True, exist_ok=True)
    (tmp_data_dir / "cifs").symlink_to(data_dir)

    ingest_by_year(
        run_name="test",
        pool_size=1,
        start_year=1987,
        end_year=1987,
        data_dir=Path(tmpdir / "data"),
        log_level="debug",
        skip_download=True,
    )

    assert (Path(tmpdir) / "data" / "cifs").is_dir()
    assert len(list((Path(tmpdir) / "data" / "cifs").iterdir())) > 0
    assert (Path(tmpdir) / "data" / "test-optimade.jsonl").is_file()

    with open(Path(tmpdir) / "data" / "test-optimade.jsonl") as f:
        _header = f.readline()
        _info = f.readline()
        _structure_info = f.readline()
        _reference_info = f.readline()
        other_lines = f.readlines()

    header = json.loads(_header)
    assert header["x-optimade"]
    assert header["x-optimade"]["meta"]["api_version"] == "1.2.0"

    structure_info = json.loads(_structure_info)
    assert structure_info["type"] == "info"
    assert structure_info["id"] == "structures"

    reference_info = json.loads(_reference_info)
    assert reference_info["type"] == "info"
    assert reference_info["id"] == "references"

    entries = [json.loads(_) for _ in other_lines]
    assert all(entry["type"] in ("structures", "references") for entry in entries)
    assert len(entries) == 694
