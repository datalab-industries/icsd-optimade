import os

import pytest

from icsd_optimade.client import ICSDClient


@pytest.fixture()
def icsd_credentials():
    if not (os.getenv("ICSD_LOGIN_ID") and os.getenv("ICSD_LOGIN_PASSWORD")):
        pytest.skip("No ICSD credentials set.")


@pytest.fixture()
def icsd_client():
    return ICSDClient()
