import os

import pytest


def test_login_credentials(icsd_credentials, icsd_client):
    if not icsd_credentials:
        pytest.skip("No ICSD credentials set.")

    assert icsd_client.login()

def test_date_range(icsd_credentials, icsd_client):
    if not icsd_credentials:
        pytest.skip("No ICSD credentials set.")

    assert icsd_client.query_date_range((2020, 2021))
