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
