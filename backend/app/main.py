"""RE:ENTRY API entrypoint.

The first milestone intentionally keeps the service small: a health endpoint
proves the deployment shape while the case workflow is added in the next
milestone.
"""

from fastapi import FastAPI

app = FastAPI(title="RE:ENTRY", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Return a dependency-free health response for local and cloud checks."""

    return {"status": "ok", "service": "re-entry"}

