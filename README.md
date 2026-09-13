# RE:ENTRY

RE:ENTRY is a human-governed AI recovery agent for the worst paperwork days
of your life. When a flood, eviction, or other crisis scatters documents and
deadlines, it turns evidence into a verified recovery plan and asks for human
approval at the moments that can materially affect a person.

This repository is being built for the Agents for Humans Hackathon. It is a
new project under active development; the demo currently starts with a seeded,
fully synthetic flood-recovery case and deterministic mock connectors so the
workflow can be evaluated without external accounts or real personal data.

## Status

The initial service scaffold is in place. The next milestone adds the case
graph, evidence extraction, action queue, approval gate, and Strands live-mode
adapter.

## Local setup

Use the project Python environment at `~/.venv/` as the default:

```bash
~/.venv/bin/pip install -e ".[dev]"
~/.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

Then open <http://127.0.0.1:8000/api/health>.

Live Bedrock/Strands dependencies are optional while the deterministic demo is
being built:

```bash
~/.venv/bin/pip install -e ".[live]"
```

Never commit credentials. Copy `.env.example` to a local `.env` only after
configuring an AWS identity with the least permissions needed for the chosen
Bedrock model.

## License

MIT. See [LICENSE](LICENSE).

