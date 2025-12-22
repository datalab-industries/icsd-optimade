import datetime


def test_login_credentials(icsd_credentials, icsd_client):
    assert icsd_client.login()


def test_publication_year_date_range(icsd_credentials, icsd_client):
    results = icsd_client.query_by_date_range(
        (2020, 2021), date_field="publicationyear"
    )
    assert results


def test_recording_date_range(icsd_credentials, icsd_client):
    date_1 = datetime.date(year=2022, month=6, day=2)
    date_2 = datetime.date(year=2022, month=9, day=30)
    results = icsd_client.query_by_date_range(
        (date_2, date_1), date_field="recordingdate"
    )
    assert len(results) == 10_030
    results = icsd_client.query_by_date_range(
        (date_1, date_2), date_field="recordingdate"
    )
    assert len(results) == 10_030

    date_1 = datetime.date(year=1900, month=1, day=1)
    date_2 = datetime.date(year=1990, month=1, day=1)
    results = icsd_client.query_by_date_range(
        (date_2, date_1), date_field="recordingdate"
    )
    assert len(results) == 25_495
