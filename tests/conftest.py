import os
from pathlib import Path

import pytest

from icsd_optimade.client import ICSDClient


@pytest.fixture(scope="session")
def icsd_credentials():
    if not (os.getenv("ICSD_LOGIN_ID") and os.getenv("ICSD_LOGIN_PASSWORD")):
        pytest.skip("No ICSD credentials set.")


@pytest.fixture(scope="session")
def icsd_client():
    with ICSDClient() as client:
        yield client


@pytest.fixture(scope="session")
def data_dir():
    return Path(__file__).parent.parent / "data"
