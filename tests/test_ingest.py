import json
from pathlib import Path


def test_ingest(tmpdir):
    from icsd_optimade.ingest import ingest_by_year

    ingest_by_year(
        pool_size=1, start_year=1987, end_year=1987, data_dir=Path(tmpdir / "data")
    )

    assert (Path(tmpdir) / "data" / "cifs").is_dir()
    assert len(list((Path(tmpdir) / "data" / "cifs").iterdir())) > 0
    assert (Path(tmpdir) / "data" / "icsd-optimade.jsonl").is_file()

    with open(Path(tmpdir) / "data" / "icsd-optimade.jsonl") as f:
        line = f.readline()
    header = json.loads(line)
    assert header["x-optimade"]
    assert header["x-optimade"]["meta"]["api_version"] == "1.1.0"
