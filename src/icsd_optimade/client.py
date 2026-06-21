import datetime
import logging
import os
import time
from pathlib import Path
from typing import Literal

import httpx

from icsd_optimade import __version__
from icsd_optimade.utils import setup_log


class Forbidden(RuntimeError): ...


class ICSDClient:
    """A wrapper for the ICSD API."""

    base_url: str = "https://icsd.fiz-karlsruhe.de/api/ws"
    icsd_auth_token: str
    icsd_login_id: str | None
    icsd_login_password: str | None
    _session: httpx.Client | None = None
    _headers: dict[str, str] = {}
    _timeout: httpx.Timeout = httpx.Timeout(10.0, read=60.0)

    exponential_retries: int = 7
    """Whether to retry CIF downloads when rate-limited; each retry
    will add another power of 10 to the back-off time, starting at 60s.
    """

    def __init__(self):
        self._http_client = httpx.Client
        # Check for `ICSD_LOGIN_ID` and `ICSD_LOGIN_PASSWORD` environment variables
        self.icsd_login_id = os.getenv("ICSD_LOGIN_ID")
        self.icsd_login_password = os.getenv("ICSD_LOGIN_PASSWORD")
        self._cached_token_path = Path(".icsd-auth-token")
        self._limit_reached: bool = False
        self._ctime = datetime.datetime.now()
        self._cifs_downloaded: int = 0
        self.log = setup_log("client", logging.ERROR)

        # Clear up stale locks
        lock = Path(".icsd-session.lock")
        if lock.is_file():
            lock.unlink()

        if self.icsd_login_id and self.icsd_login_password:
            self.login()
        else:
            self.log.warning(
                "ICSD login credentials not found in environment variables. "
                "CIF download will not be possible."
            )

        self.headers["User-Agent"] = (
            f"icsd-optimade ingester/{__version__} Contact dev@datalab.industries with issues/problematic usage"
        )

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.logout()

    def logout(self):
        if self._session is None:
            return

        self.headers.pop("Accept", None)
        logout_resp = self.session.get(f"{self.base_url}/auth/logout")
        if logout_resp.status_code != 200:
            raise RuntimeError(
                f"Failed to logout of ICSD session: {logout_resp.content}"
            )
        self.log.info("Logged out of session")

    def rotate_session(self):
        """Attempt to rotate the session key in a parallel-safe way."""
        owns_lock = False
        lock = Path(".icsd-session.lock")
        if not lock.is_file():
            with open(lock, "w") as f:
                f.write(str(os.getpid()))

            owns_lock = True

        if owns_lock:
            self.log.info("Rotating ICSD session key")
            # One PID can now clear the session and create a new one
            try:
                self.logout()
            except RuntimeError:
                pass
            if self._cached_token_path.is_file():
                self._cached_token_path.unlink()

            self.login()
            lock.unlink()

        if not owns_lock:
            self.log.info("Waiting for new session")
            # Wait a bit for another process to finish locking and creating the session
            max_wait_seconds = 120
            wait_seconds = 0
            increment = 1
            while lock.is_file() and wait_seconds < max_wait_seconds:
                time.sleep(increment)
                wait_seconds += increment

    def login(self) -> str:
        """Login with user credentials and return the ICSD auth token."""

        # Check for pre-existing sessions
        self.headers.pop("Accept", None)
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
                self.headers["icsd-auth-token"] = auth_token
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
        token = login_resp.headers["icsd-auth-token"]

        with open(self._cached_token_path, "w") as f:
            f.write(token)

        self.headers["icsd-auth-token"] = token
        self.log.info(f"Logged into session {token}")
        return token

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
        if self._limit_reached:
            raise Forbidden("CIF download limit reached, try again later.")

        self.headers.pop("Accept", None)

        retries = 0
        if self.exponential_retries:
            while retries < self.exponential_retries:
                response = self.session.get(f"{self.base_url}/cif/{identifier}")

                if response.status_code == 403:
                    sleep_time = 60 * 2**retries
                    self.log.warning(
                        f"Hit 403 limit after {datetime.datetime.now() - self._ctime} on process {os.getpid()} -- {self._cifs_downloaded} CIFs downloaded. Process sleeping for %s minutes before retrying",
                        sleep_time / 60,
                    )
                    time.sleep(sleep_time)
                    self.rotate_session()
                    retries += 1
                    continue

                if response.status_code == 200:
                    self._cifs_downloaded += 1

                return response.content

        self._limit_reached = True
        raise Forbidden(
            "CIF download limit ({self._cifs_downloaded}) reached: [{response.status_code}] - {response.content}"
        )

    def get_reference(self, identifier: str) -> str:
        """Download the bibliographic references for the entry given the ICSD identifier."""
        return self.session.get(f"{self.base_url}/reference/{identifier}")

    def query_entries(self, query: str) -> list[str]:
        """Return a list of matching entry IDs."""
        self.headers["Accept"] = "application/json"
        resp = self.session.get(f"{self.base_url}/search/expert?query={query}")
        if resp.status_code != 200:
            raise RuntimeError(f"Search {query} returned an error: {resp.content}")

        return resp.json()["idnums"]

    def query_by_date_range(
        self,
        date_range: tuple[datetime.date, datetime.date] | tuple[int, int],
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

        _date_range = sorted(date_range)  # type: ignore

        if isinstance(_date_range[0], datetime.datetime) and isinstance(
            _date_range[1], datetime.datetime
        ):
            _date_range = (_date_range[0].isoformat(), _date_range[1].isoformat())  # type: ignore

        _date_range = (str(_date_range[0]), str(_date_range[1]))  # type: ignore

        query = f"{date_field}: {_date_range[0]}-{_date_range[1]}"
        results = self.query_entries(query)
        return results
