import os

import pytest

from icsd_optimade.client import ICSDClient


@pytest.fixture()
def icsd_credentials():
    return os.getenv("ICSD_LOGIN_ID") and os.getenv("ICSD_LOGIN_PASSWORD")


@pytest.fixture()
def icsd_client():
    return ICSDClient()
