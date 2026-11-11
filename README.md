# auditor-mcp

Two MCP components for auditing and securing AI tool use:

- **auditor-gateway**: a security proxy that sits between Claude and your other
  MCP servers to defend against **tool poisoning**. It pins every tool definition,
  quarantines tools that are new or have changed since approval, re-checks each
  tool immediately before forwarding a call, and writes every decision to an
  audit log from code.
- **auditor-mcp**: a conversation log. The model reports each query and response
  (summarised above 100 words) through tools. This is self-reported, so treat it
  as context rather than evidence; the gateway log is the trustworthy record.

## How the gateway protects you

```
Claude Desktop ──► auditor-gateway ──► weather, filesystem, ... (downstream servers)
                     │ 1. pin and check every tool definition
                     │ 2. hide anything not approved
                     │ 3. re-check the definition before each call
                     └─► logs/gateway.jsonl
```

| Attack | What the gateway does |
| --- | --- |
| Poisoned tool added to a server | New tools are quarantined until you review and approve them |
| **Rug pull** (definition changed after approval) | The tool disappears from Claude's list and calls are blocked, even mid-session |
| Poison hidden in parameters | Fingerprints cover the full schema, not just the description |
| Shadowing via tool names | Tools are namespaced as `<server>__<tool>`, so names can't collide |
| Secrets leaking to third-party servers | Downstream servers get a minimal environment; pass variables explicitly |

What phase 1 does **not** do yet: inspect arguments, scan descriptions or
results for injected instructions, or track data flow. Approval is only as good
as your review, so read the definition before approving it.

## Setup

```powershell
uv sync
Copy-Item gateway.example.toml gateway.toml   # then edit the server entries
```

## Reviewing and approving tools

```powershell
uv run auditor-gateway refresh                       # connect and record current tools
uv run auditor-gateway pins                          # list tools and their status
uv run auditor-gateway show weather get_forecast     # full definition, or a diff if changed
uv run auditor-gateway approve weather get_forecast  # approve this exact definition
uv run auditor-gateway approve weather --all         # approve all of a server's tools
uv run auditor-gateway revoke weather get_forecast   # withdraw approval
```

Statuses: `approved`, `new` (never approved), `changed` (differs from the
approved version), `revoked`. Only `approved` tools are visible to Claude.

To make sure you approve exactly what you reviewed, pass the fingerprint prefix
that `show` printed: `approve weather get_forecast --fingerprint 53c110841be4`.
The approval is refused if the definition changed in between.

## Claude Desktop config

Route servers through the gateway instead of configuring them directly:

```json
"mcpServers": {
  "auditor-gateway": {
    "command": "C:\\Users\\HP\\.local\\bin\\uv.exe",
    "args": ["--directory", "C:\\pyProjects\\mcp-projects\\auditor-mcp", "run", "auditor-gateway"]
  },
  "auditor": {
    "command": "C:\\Users\\HP\\.local\\bin\\uv.exe",
    "args": ["--directory", "C:\\pyProjects\\mcp-projects\\auditor-mcp", "run", "auditor-mcp"]
  }
}
```

Any server still listed directly in Claude Desktop bypasses the gateway.

## Files

| File | Contents | In git? |
| --- | --- | --- |
| `gateway.toml` | Downstream servers (machine paths, maybe secrets) | No; commit `gateway.example.toml` |
| `state/pins.json` | Your approvals and change history | Optional; committing it makes approvals reviewable |
| `logs/gateway.jsonl` | Security events: connections, quarantines, allowed and blocked calls | No |
| `logs/audit.jsonl` | Conversation log from `auditor-mcp` | No |

## Project layout

```
auditor-mcp/
├── gateway.example.toml     template gateway config
├── dev.py                   entry file for the MCP Inspector (mcp dev)
├── src/auditor_mcp/
│   ├── gateway/             the security proxy
│   │   ├── config.py          GatewayConfig, read from gateway.toml
│   │   ├── downstream.py      DownstreamPool: MCP clients to the real servers
│   │   ├── proxy.py           Gateway: list/call handlers and enforcement
│   │   └── cli.py             auditor-gateway command
│   ├── security/            fingerprints and the PinStore
│   ├── storage/             audit log, security event log
│   ├── services/            conversation-log rules
│   ├── tools/               conversation-log MCP tools
│   ├── server.py            create_server() for auditor-mcp
│   └── __main__.py          auditor-mcp entry point
└── tests/                   unit tests and end-to-end tests with a fake downstream server
```

## Development

```powershell
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mcp dev dev.py      # Inspector for the auditor-mcp server
```

## Configuration (auditor-mcp)

| Variable | Default | Meaning |
| --- | --- | --- |
| `AUDITOR_LOG_DIR` | `./logs` | Folder for `audit.jsonl` |
| `AUDITOR_WORD_LIMIT` | `100` | Maximum words stored per query or response |
| `AUDITOR_LOG_LEVEL` | `INFO` | Diagnostic log level (stderr) |
| `AUDITOR_GATEWAY_CONFIG` | `./gateway.toml` | Gateway config path |

## Roadmap

1. ✅ Gateway, pinning, quarantine, audit trail
2. Description scanner and argument policy, with allow / confirm / block verdicts
3. Output scanning and data-flow tracking
4. Optional independent-model judge, and a corpus of poisoned tools for measuring detection
