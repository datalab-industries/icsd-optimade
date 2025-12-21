import logging
import os
from pathlib import Path
from typing import Literal

import httpx

from icsd_optimade import __version__


class ICSDClient:
    """A wrapper for the ICSD API."""

    base_url: str = "https://icsd.fiz-karlsruhe.de/api/ws"
    icsd_auth_token: str
    icsd_login_id: str | None
    icsd_login_password: str | None
    _session: httpx.Client | None = None
    _headers: dict[str, str] = {}
    _timeout: httpx.Timeout = httpx.Timeout(10.0, read=60.0)

    def __init__(self):
        self._http_client = httpx.Client
        # Check for `ICSD_LOGIN_ID` and `ICSD_LOGIN_PASSWORD` environment variables
        self.icsd_login_id = os.getenv("ICSD_LOGIN_ID")
        self.icsd_login_password = os.getenv("ICSD_LOGIN_PASSWORD")
        self.log = logging.getLogger("icsd_client")
        self._cached_token_path = Path(".icsd-auth-token")

        if not self.icsd_login_id or not self.icsd_login_password:
            raise RuntimeError(
                "No ICSD user credentials found, please set the `ICSD_LOGIN_ID` and `ICSD_LOGIN_PASSWORD` environment variables."
            )

        self.headers["User-Agent"] = f"icsd-optimade ingester/{__version__}"
        auth_token = self.login()
        self.headers["icsd-auth-token"] = auth_token

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.logout()

    def logout(self):
        logout_resp = self.session.get(f"{self.base_url}/auth/logout")
        if logout_resp.status_code != 200:
            raise RuntimeError(
                f"Failed to logout of ICSD session: {logout_resp.content}"
            )
        self.log.info("Logged out of session")

    def login(self) -> str:
        """Login with user credentials and return the ICSD auth token."""

        # Check for pre-existing sessions
        auth_token = os.getenv("ICSD_AUTH_TOKEN")
        if auth_token:
            self.log.debug(f"Trying pre-existing session from env var {auth_token}")

        else:
            if self._cached_token_path.is_file():
                with open(self._cached_token_path) as f:
                    auth_token = f.readlines()[0].strip()
            self.log.debug(
                f"Trying pre-existing session from path {self._cached_token_path}"
            )

        if auth_token:
            # Look for non-existent CIF (to avoid bad statistics) -- should return 404 if logged in
            check_auth = httpx.get(
                f"{self.base_url}/cif/0", headers={"icsd-auth-token": auth_token}
            )
            if check_auth.status_code == 404:
                self.log.info(f"Using pre-existing login session {auth_token}")
                return auth_token

        login_resp = httpx.post(
            f"{self.base_url}/auth/login",
            data={"loginid": self.icsd_login_id, "password": self.icsd_login_password},
            follow_redirects=True,
        )
        if login_resp.status_code != 200:
            raise RuntimeError(
                f"Failed to authenticate to ICSD at {self.base_url!r}: {login_resp.status_code=}. Error returned: {login_resp.content}"
            )
        with open(".icsd-auth-token", "w") as f:
            f.write(login_resp.headers["icsd-auth-token"])
        self.log.info(f"Logged into session {login_resp.headers['icsd-auth-token']}")
        return login_resp.headers["icsd-auth-token"]

    @property
    def session(self) -> httpx.Client:
        if self._session is None:
            return self._http_client(headers=self.headers, timeout=self.timeout)
        return self._session

    @property
    def headers(self) -> dict[str, str]:
        """Any headers to send with each request to the ICSD API."""
        return self._headers

    @property
    def timeout(self) -> httpx.Timeout:
        """A timeout object to use for the ICSD API session."""
        return self._timeout

    def get_cif(self, identifier: str | int) -> bytes:
        """Download a CIF for the entry given the ICSD identifier and return it as bytes."""
        self.headers.pop("Accept")
        response = self.session.get(f"{self.base_url}/cif/{identifier}")
        if response.status_code != 200:
            raise RuntimeError(
                f"CIF {identifier} not found: [{response.status_code}] - {response.content}"
            )

        return response.content

    def get_reference(self, identifier: str) -> str:
        """Download the bibliographic references for the entry given the ICSD identifier."""
        return self.session.get(f"{self.base_url}/reference/{identifier}")

    def query_entries(self, query: str) -> list[str]:
        """Return a list of matching entry IDs."""
        self.headers["Accept"] = "application/json"
        resp = self.session.get(f"{self.base_url}/search/expert?query={query}")
        if resp.status_code != 200:
            raise RuntimeError(f"Search returned an error: {resp.content}")

        return resp.json()["idnums"]

    def query_by_date_range(
        self,
        date_range: tuple[int, int],
        date_field: Literal[
            "recordingdate", "publicationyear", "modificationdate"
        ] = "recordingdate",
    ) -> list[str]:
        """Query the ICSD for the specified date range. The `date_field`
        can be set to one of the supported values in the ICSD:

            - `recordingdate`
            - `publicationyear`
            - `modificationdate`

        Returns a list of matching IDs.
        """
        self.headers["Accept"] = "application/json"
        if date_range[0] == date_range[1]:
            raise RuntimeError("Date range must be a range, not a single date.")

        _date_range = sorted(date_range)

        query = f"{date_field}: {_date_range[0]}-{_date_range[1]}"
        results = self.query_entries(query)
        return results
