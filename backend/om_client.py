"""
om_client.py
OpenMetadata REST API wrapper for dq-pilot.
Handles all communication with the OpenMetadata server.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ColumnProfile:
    name: str
    data_type: str
    description: str = ""
    nullable: bool = True
    null_count: int = 0
    null_proportion: float = 0.0
    unique_count: int = 0
    unique_proportion: float = 0.0
    distinct_count: int = 0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    sample_values: list = field(default_factory=list)


@dataclass
class TableProfile:
    fqn: str
    name: str
    description: str = ""
    row_count: int = 0
    column_count: int = 0
    columns: list[ColumnProfile] = field(default_factory=list)


@dataclass
class TestDefinition:
    id: str
    name: str
    display_name: str
    description: str
    entity_type: str          # "COLUMN" or "TABLE"
    supported_data_types: list[str] = field(default_factory=list)
    parameter_definition: list[dict] = field(default_factory=list)


@dataclass
class ExistingTest:
    name: str
    column_name: Optional[str]
    test_definition_name: str


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class OpenMetadataClient:
    """
    Thin wrapper around the OpenMetadata REST API.

    Usage:
        client = OpenMetadataClient.from_env()
        profile = client.get_table_profile("sample_data.ecommerce_db.customers")
    """

    def __init__(self, base_url: str, jwt_token: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        })

        # Retry on transient errors
        retry = Retry(total=3, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "OpenMetadataClient":
        """Create client from environment variables."""
        base_url = os.environ.get("OM_BASE_URL", "http://localhost:8585")
        jwt_token = os.environ["OM_JWT_TOKEN"]          # required
        timeout = int(os.environ.get("OM_TIMEOUT", "30"))
        return cls(base_url, jwt_token, timeout)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}/api/v1{path}"
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}/api/v1{path}"
        resp = self._session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _paginate(self, path: str, params: dict = None) -> list[dict]:
        """Fetch all pages from a paginated endpoint."""
        params = params or {}
        params.setdefault("limit", 100)
        results = []
        after = None

        while True:
            if after:
                params["after"] = after
            data = self._get(path, params)
            results.extend(data.get("data", []))
            paging = data.get("paging", {})
            after = paging.get("after")
            if not after:
                break

        return results

    # ------------------------------------------------------------------
    # Table metadata
    # ------------------------------------------------------------------

    def get_table(self, fqn: str) -> dict:
        """Fetch raw table JSON including columns."""
        encoded = requests.utils.quote(fqn, safe="")
        return self._get(f"/tables/name/{encoded}",
                         params={"fields": "columns,tableProfile,description,tags"})

    def get_table_profile(self, fqn: str) -> TableProfile:
        """
        Return a fully hydrated TableProfile for the given fully-qualified
        table name, e.g. "sample_data.ecommerce_db.customers".
        """
        raw = self.get_table(fqn)
        columns_raw = raw.get("columns", [])

        # Try to pull the latest column-level profile stats
        try:
            encoded = requests.utils.quote(fqn, safe="")
            profile_data = self._get(f"/tables/{raw['id']}/tableProfile/latest")
            col_profiles = {
                cp["name"]: cp
                for cp in profile_data.get("columnProfile", [])
            }
        except requests.HTTPError:
            logger.warning("No column profile found for %s — proceeding without stats", fqn)
            col_profiles = {}

        columns = []
        for col in columns_raw:
            col_name = col["name"]
            cp = col_profiles.get(col_name, {})

            columns.append(ColumnProfile(
                name=col_name,
                data_type=col.get("dataType", "UNKNOWN"),
                description=col.get("description", ""),
                nullable=col.get("constraint") != "NOT_NULL",
                null_count=int(cp.get("nullCount", 0)),
                null_proportion=float(cp.get("nullProportion", 0.0)),
                unique_count=int(cp.get("uniqueCount", 0)),
                unique_proportion=float(cp.get("uniqueProportion", 0.0)),
                distinct_count=int(cp.get("distinctCount", 0)),
                min_value=cp.get("min"),
                max_value=cp.get("max"),
                mean=cp.get("mean"),
                sample_values=cp.get("valuesCount", []),
            ))

        table_profile_raw = raw.get("tableProfile", {})
        return TableProfile(
            fqn=fqn,
            name=raw.get("name", ""),
            description=raw.get("description", ""),
            row_count=int(table_profile_raw.get("rowCount", 0)),
            column_count=len(columns),
            columns=columns,
        )

    # ------------------------------------------------------------------
    # Test definitions (template library)
    # ------------------------------------------------------------------

    def get_test_definitions(self) -> list[TestDefinition]:
        """Fetch all available test definitions from the template library."""
        raw_list = self._paginate("/dataQuality/testDefinitions",
                                  params={"entityType": "COLUMN"})

        # Also grab table-level definitions
        raw_list += self._paginate("/dataQuality/testDefinitions",
                                   params={"entityType": "TABLE"})

        definitions = []
        for raw in raw_list:
            definitions.append(TestDefinition(
                id=raw["id"],
                name=raw["name"],
                display_name=raw.get("displayName", raw["name"]),
                description=raw.get("description", ""),
                entity_type=raw.get("entityType", "COLUMN"),
                supported_data_types=raw.get("supportedDataTypes", []),
                parameter_definition=raw.get("parameterDefinition", []),
            ))

        logger.info("Loaded %d test definitions", len(definitions))
        return definitions

    # ------------------------------------------------------------------
    # Existing test cases
    # ------------------------------------------------------------------

    def get_existing_tests(self, fqn: str) -> list[ExistingTest]:
        """Return all test cases already defined on this table."""
        entity_link = f"<#E::table::{fqn}>"
        try:
            raw_list = self._paginate("/dataQuality/testCases",
                                      params={"entityLink": entity_link,
                                              "includeAllTests": "true"})
        except requests.HTTPError as e:
            logger.warning("Could not fetch existing tests: %s", e)
            return []

        tests = []
        for raw in raw_list:
            # entity link format: <#E::table::fqn::columns::col_name>
            entity_link_str = raw.get("entityLink", "")
            col_name = None
            if "::columns::" in entity_link_str:
                col_name = entity_link_str.split("::columns::")[-1].rstrip(">")

            tests.append(ExistingTest(
                name=raw["name"],
                column_name=col_name,
                test_definition_name=raw.get("testDefinition", {}).get("name", ""),
            ))

        return tests

    # ------------------------------------------------------------------
    # Create test cases
    # ------------------------------------------------------------------

    def create_test_case(
        self,
        fqn: str,
        test_definition_name: str,
        test_case_name: str,
        column_name: Optional[str] = None,
        parameters: Optional[list[dict]] = None,
        description: str = "",
    ) -> dict:
        """
        Create a draft test case on a table (or column).

        Parameters should be a list of {"name": ..., "value": ...} dicts
        matching the test definition's parameterDefinition.
        """
        if column_name:
            entity_link = f"<#E::table::{fqn}::columns::{column_name}>"
        else:
            entity_link = f"<#E::table::{fqn}>"

        payload = {
            "name": test_case_name,
            "description": description,
            "entityLink": entity_link,
            "testDefinition": {
                "type": "testDefinition",
                "name": test_definition_name,
            },
            "parameterValues": parameters or [],
        }

        result = self._post("/dataQuality/testCases", payload)
        logger.info("Created test case: %s", test_case_name)
        return result

    # ------------------------------------------------------------------
    # Convenience: health check
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Return True if OpenMetadata is reachable."""
        try:
            self._get("/system/status")
            return True
        except Exception as e:
            logger.error("OpenMetadata unreachable: %s", e)
            return False