import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_agentcore_runtime_spec_is_authenticated_and_bounded() -> None:
    config = json.loads((ROOT / "agentcore/agentcore.json").read_text())
    runtimes = config["runtimes"]
    assert len(runtimes) == 1
    runtime = runtimes[0]
    assert runtime["build"] == "Container"
    assert runtime["protocol"] == "HTTP"
    assert runtime["authorizerType"] in {"AWS_IAM", "CUSTOM_JWT"}
    lifecycle = runtime["lifecycleConfiguration"]
    assert 60 <= lifecycle["idleRuntimeSessionTimeout"] <= lifecycle["maxLifetime"] <= 28_800
    assert runtime["instrumentation"]["enableOtel"] is True
    assert (ROOT / runtime["entrypoint"]).is_file()
    assert (ROOT / runtime["dockerfile"]).is_file()
    env_vars = {item["name"]: item["value"] for item in runtime.get("envVars", [])}
    assert env_vars["REENTRY_MAX_LIVE_PLAN_RUNS"] == "10"
    assert env_vars["REENTRY_REQUEST_MAX_DURATION_SECONDS"] == "300"
    assert env_vars["REENTRY_MAX_IN_FLIGHT_REQUESTS"] == "32"
    assert env_vars["REENTRY_MAX_IN_FLIGHT_BODY_BYTES"] == "268435456"
    assert env_vars["REENTRY_MAX_IN_FLIGHT_PLANS"] == "8"
    assert env_vars["REENTRY_LIVE_ALLOW_UNREVIEWED_DATA"] == "false"
    assert env_vars["REENTRY_ALLOWED_AWS_REGIONS"] == "us-east-1"
    assert env_vars["REENTRY_ALLOW_EPHEMERAL_STORE"] == "false"
    assert int(env_vars["REENTRY_MAX_LIVE_PLAN_RUNS"]) in range(1, 101)
    assert all(
        not any(secret_word in env["name"].upper() for secret_word in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"))
        for env in runtime.get("envVars", [])
    )


def test_agentcore_target_example_is_safe_placeholder() -> None:
    targets = json.loads((ROOT / "agentcore/aws-targets.example.json").read_text())
    assert len(targets) == 1
    assert targets[0]["account"] == "123456789012"
    assert targets[0]["region"] == "us-east-1"
    assert json.loads((ROOT / "agentcore/aws-targets.json").read_text()) == []


def test_dockerignore_excludes_local_runtime_and_deployment_state() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text()
    for required in (
        "data/",
        "uploads/",
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        ".venv/",
        "frontend/.vite/",
        "agentcore/aws-targets.json",
        "agentcore/.cli/",
    ):
        assert required in dockerignore
