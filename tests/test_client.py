import datetime
import time


def test_login_credentials(icsd_credentials, icsd_client):
    assert icsd_client.login()


def test_publication_year_date_range(icsd_credentials, icsd_client):
    results = icsd_client.query_by_date_range(
        (2020, 2021), date_field="publicationyear"
    )
    assert results


def test_recording_date_range(icsd_credentials, icsd_client):
    day_1 = int(time.mktime(datetime.date(year=1992, month=11, day=2).timetuple()))
    day_2 = int(time.mktime(datetime.date(year=1992, month=11, day=3).timetuple()))

    results = icsd_client.query_by_date_range((day_1, day_2), date_field="recording")
    assert results
