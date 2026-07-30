import os

import httpx
import pytest

# Points at the dev server you already run locally (uvicorn app.main:app),
# not a server this suite manages itself -- managing a subprocess server's
# lifecycle reliably turned out to be its own source of flakiness in this
# environment during earlier work this session, and the goal here is a
# real browser exercising real behavior, not a self-contained CI harness.
# Override with E2E_BASE_URL if the dev server runs somewhere else.
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8010")


@pytest.fixture(scope="session")
def base_url() -> str:
    try:
        response = httpx.get(f"{BASE_URL}/docs", timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError:
        pytest.skip(
            f"No dev server reachable at {BASE_URL} -- start it first "
            "(uvicorn app.main:app --port 8010 from apps/api/) to run "
            "these E2E tests. They're not part of the default test run."
        )

    return BASE_URL
