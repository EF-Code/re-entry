# RE:ENTRY

RE:ENTRY is a human-governed AI recovery agent for the worst paperwork days
of your life. When a flood, eviction, or other crisis scatters documents and
deadlines, it turns evidence into a verified recovery plan and asks for human
approval at the moments that can materially affect a person.

This repository is being built for the Agents for Humans Hackathon. It is a
new project under active development; the demo starts with a seeded, fully
synthetic flood-recovery case and deterministic mock connectors so the workflow
can be evaluated without external accounts or real personal data.

## Status

The end-to-end demo slice is in place: case graph, evidence extraction,
action queue, approval gate, connector rejection → replanning, bounded upload
quarantine, and a Strands/Bedrock live-mode adapter. Managed AgentCore Runtime,
Gateway credentials, durable storage, and production auth remain a deliberate
deployment slice; see [the architecture notes](docs/architecture.md).

## Local setup

Use the project Python environment at `~/.venv/` as the default:

```bash
~/.venv/bin/pip install -e ".[dev]"
~/.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

In a second terminal, build or run the React surface:

```bash
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173> for the live UI, or run `npm run build` first and
open <http://127.0.0.1:8000> to serve the compiled UI from FastAPI.

Run the regression suite with:

```bash
~/.venv/bin/ruff check backend tests
~/.venv/bin/pytest -q
```

The single-image path is also available with Docker:

```bash
docker compose up --build
```

Then open <http://127.0.0.1:8000>.

The Dockerfile is multi-platform. AgentCore Runtime requires an ARM64 image;
build that target explicitly with BuildKit and verify the result before
publishing it:

```bash
docker buildx build --platform linux/arm64 --load -t reentry:arm64 .
docker image inspect reentry:arm64 --format '{{.Os}}/{{.Architecture}}'
```

The local Compose command follows the host architecture for fast development;
the ARM64 command is the deployment preflight.

The demo exercises a deterministic offline `strands.Agent` model. To enable the
Bedrock-backed planner instead, configure AWS credentials and install the
live extras:

```bash
~/.venv/bin/pip install -e ".[live]"
```

Never commit credentials. Copy `.env.example` to a local `.env` only after
configuring an AWS identity with the least permissions needed for the chosen
Bedrock model.

## Demo path

Follow [the demo script](docs/demo-script.md) to see the approval checkpoint,
mock receipt, rejection-to-evidence loop, and evidence drawer in under two
minutes. The UI explicitly labels demo mode and does not contact real agencies.

## License

MIT. See [LICENSE](LICENSE).

For the prototype threat model and the remaining AWS launch work, see
[SECURITY.md](SECURITY.md) and the [production checklist](docs/production-checklist.md).
