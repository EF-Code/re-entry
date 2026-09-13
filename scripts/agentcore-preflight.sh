#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON_BIN:-"$HOME/.venv/bin/python"}
config_file="$repo_root/agentcore/agentcore.json"
targets_file="$repo_root/agentcore/aws-targets.json"

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

command -v agentcore >/dev/null 2>&1 || fail "agentcore CLI is required"
command -v docker >/dev/null 2>&1 || fail "Docker is required"
command -v aws >/dev/null 2>&1 || fail "AWS CLI v2 is required; install it before deployment"
aws_version=$(aws --version 2>&1 || true)
case "$aws_version" in
  aws-cli/2.*) ;;
  *) fail "AWS CLI v2 is required; found: ${aws_version:-unknown}" ;;
esac
[ -x "$python_bin" ] || fail "Python environment not found at $python_bin"
[ -f "$config_file" ] || fail "missing agentcore/agentcore.json"
[ -f "$targets_file" ] || fail "copy agentcore/aws-targets.example.json to agentcore/aws-targets.json and set your account"

agentcore validate --directory "$repo_root" --json

printf 'AgentCore CLI: '
agentcore --version
printf 'Docker Buildx: '
docker buildx version | head -n 1
printf 'AWS identity:\n'
caller_account=$(aws sts get-caller-identity --query Account --output text)
case "$caller_account" in
  [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;;
  *) fail "AWS caller identity did not return a 12-digit account ID" ;;
esac
aws sts get-caller-identity --output json
printf 'AWS caller account: %s\n' "$caller_account"

"$python_bin" - "$config_file" "$targets_file" "$repo_root" "$caller_account" <<'PY'
import json
import pathlib
import re
import sys

config_file, targets_file, repo_root = map(pathlib.Path, sys.argv[1:4])
caller_account = sys.argv[4]
config = json.loads(config_file.read_text())
targets = json.loads(targets_file.read_text())
runtimes = config.get("runtimes", [])
if len(runtimes) != 1:
    raise SystemExit("ERROR: expected exactly one ReEntry runtime in agentcore.json")
runtime = runtimes[0]
if runtime.get("build") != "Container" or runtime.get("protocol") != "HTTP":
    raise SystemExit("ERROR: ReEntry must deploy as a Container/HTTP runtime")
if runtime.get("authorizerType") not in {"AWS_IAM", "CUSTOM_JWT"}:
    raise SystemExit("ERROR: production runtime requires AWS_IAM or CUSTOM_JWT auth")
if runtime.get("networkMode") == "PUBLIC":
    print("WARNING: runtime network mode is PUBLIC; use VPC when private resources are introduced")
lifecycle = runtime.get("lifecycleConfiguration", {})
idle_timeout = lifecycle.get("idleRuntimeSessionTimeout")
max_lifetime = lifecycle.get("maxLifetime")
if (
    not isinstance(idle_timeout, int)
    or not isinstance(max_lifetime, int)
    or idle_timeout < 60
    or max_lifetime > 28_800
    or idle_timeout > max_lifetime
):
    raise SystemExit("ERROR: idle session timeout must be set and cannot exceed max lifetime")
if not isinstance(targets, list) or not targets:
    raise SystemExit("ERROR: deployment targets must be a non-empty JSON list")
for target in targets:
    if not isinstance(target, dict):
        raise SystemExit("ERROR: each deployment target must be a JSON object")
    if not re.fullmatch(r"\d{12}", str(target.get("account", ""))):
        raise SystemExit("ERROR: deployment targets must contain 12-digit AWS account IDs")
    if not re.fullmatch(r"[a-z0-9-]{1,32}", str(target.get("region", ""))):
        raise SystemExit("ERROR: each deployment target must contain a valid AWS region")
target_accounts = sorted({str(target["account"]) for target in targets})
if any(account != caller_account for account in target_accounts):
    raise SystemExit(
        "ERROR: AWS caller account "
        f"{caller_account} does not match deployment target account(s): {', '.join(target_accounts)}"
    )
env_vars = {
    str(item.get("name", "")): str(item.get("value", ""))
    for item in runtime.get("envVars", [])
    if isinstance(item, dict)
}
runtime_mode = env_vars.get("REENTRY_MODE", "demo").strip().lower() or "demo"
if runtime_mode not in {"demo", "live"}:
    raise SystemExit(f"ERROR: unsupported REENTRY_MODE: {runtime_mode}")
if runtime_mode == "live":
    ephemeral_store = env_vars.get("REENTRY_ALLOW_EPHEMERAL_STORE", "false").strip().lower()
    if ephemeral_store in {"1", "true", "yes"}:
        raise SystemExit("ERROR: live deployment cannot allow the process-local ephemeral store")
    try:
        live_budget = int(env_vars.get("REENTRY_MAX_LIVE_PLAN_RUNS", "10"))
    except ValueError as exc:
        raise SystemExit("ERROR: REENTRY_MAX_LIVE_PLAN_RUNS must be an integer") from exc
    if not 1 <= live_budget <= 100:
        raise SystemExit("ERROR: REENTRY_MAX_LIVE_PLAN_RUNS must be between 1 and 100")
    allowed_regions = {
        value.strip()
        for value in env_vars.get("REENTRY_ALLOWED_AWS_REGIONS", "").split(",")
        if value.strip()
    }
    allowed_models = {
        value.strip()
        for value in env_vars.get("REENTRY_ALLOWED_MODEL_IDS", "").split(",")
        if value.strip()
    }
    if not allowed_regions or not allowed_models:
        raise SystemExit("ERROR: live deployment requires non-empty region/model allowlists")
    target_regions = {str(target["region"]) for target in targets}
    if not target_regions.issubset(allowed_regions):
        raise SystemExit("ERROR: every deployment region must be in REENTRY_ALLOWED_AWS_REGIONS")
    configured_model = env_vars.get("REENTRY_MODEL_ID", "").strip()
    if not configured_model or configured_model not in allowed_models:
        raise SystemExit("ERROR: REENTRY_MODEL_ID must be present in REENTRY_ALLOWED_MODEL_IDS")
entrypoint = repo_root / runtime["entrypoint"]
dockerfile = repo_root / runtime.get("dockerfile", "Dockerfile")
if not entrypoint.is_file():
    raise SystemExit(f"ERROR: runtime entrypoint does not exist: {entrypoint}")
if not dockerfile.is_file():
    raise SystemExit(f"ERROR: runtime Dockerfile does not exist: {dockerfile}")
secret_name = re.compile(r"(?:TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)
for env_var in runtime.get("envVars", []):
    if secret_name.search(env_var["name"]):
        raise SystemExit(f"ERROR: secret-like runtime env var is forbidden: {env_var['name']}")
print(f"Config OK: {runtime['name']} ({runtime['authorizerType']}, {runtime['protocol']})")
print(f"Target region(s): {', '.join(item['region'] for item in targets)}")
PY

read -r target_region runtime_mode model_id < <(
  "$python_bin" - "$config_file" "$targets_file" <<'PY'
import json
import pathlib
import sys

config = json.loads(pathlib.Path(sys.argv[1]).read_text())
targets = json.loads(pathlib.Path(sys.argv[2]).read_text())
runtime = config["runtimes"][0]
env_vars = {item["name"]: item["value"] for item in runtime.get("envVars", [])}
mode = str(env_vars.get("REENTRY_MODE", "demo")).strip().lower() or "demo"
if mode not in {"demo", "live"}:
    raise SystemExit(f"ERROR: unsupported REENTRY_MODE: {mode}")
print(targets[0]["region"], mode, str(env_vars.get("REENTRY_MODEL_ID", "")).strip())
PY
)
if [ "$runtime_mode" = "live" ]; then
  [ -n "$model_id" ] || fail "live mode requires REENTRY_MODEL_ID in agentcore.json"
  case "$model_id" in
    global.*|us.*|eu.*|apac.*|au.*|jp.*)
      aws bedrock get-inference-profile \
        --region "$target_region" \
        --inference-profile-identifier "$model_id" \
        --output json >/dev/null \
        || fail "Bedrock inference profile is not accessible: $model_id"
      ;;
    *)
      aws bedrock get-foundation-model \
        --region "$target_region" \
        --model-identifier "$model_id" \
        --output json >/dev/null \
        || fail "Bedrock foundation model is not accessible: $model_id"
      ;;
  esac
  printf 'Bedrock model access verified: %s (%s)\n' "$model_id" "$target_region"
fi

docker buildx build --platform linux/arm64 --check "$repo_root"
printf 'Preflight passed. No AWS resources were created.\n'
