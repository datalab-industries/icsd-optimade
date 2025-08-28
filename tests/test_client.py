def test_login_credentials(icsd_credentials, icsd_client):
    assert icsd_client.login()


def test_date_range(icsd_credentials, icsd_client):
    assert icsd_client.query_date_range((2020, 2021))
