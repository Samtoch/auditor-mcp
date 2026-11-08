# auditor-mcp

An MCP server that keeps an audit log of conversation turns. Each turn records
the user's query and the model's response. Text longer than the word limit
(100 by default) is stored as a summary written by the model, and the server
enforces the limit either way.

Entries are appended to `logs/audit.jsonl`, one JSON object per line.

## Project layout

```
auditor-mcp/
├── pyproject.toml           project metadata, dependencies, tool config
├── dev.py                   entry file for the MCP Inspector (mcp dev)
├── src/auditor_mcp/
│   ├── __main__.py          entry point: `uv run auditor-mcp`
│   ├── api/                 reserved for website-facing API routes and app setup
│   ├── mcp/
│   │   ├── server.py        create_server(): wires the MCP interface together
│   │   └── tools/           MCP tool definitions (thin layer over services)
│   ├── config.py            Settings, read from AUDITOR_* env vars
│   ├── logging_setup.py     diagnostic logging to stderr
│   ├── models/              shared audit and identity data models
│   ├── storage/             shared JSONL and PostgreSQL persistence
│   └── services/            shared business rules and identity verification
└── tests/                   unit tests
```

The interfaces are separate: `api/` is reserved for the website, and `mcp/`
contains the AI-facing server and tools. There is no web API implementation yet.
Both interfaces should call shared `services/`, which use `storage/` and
`models/`. Services, storage, and models must not depend on either interface.
Policy enforcement belongs in shared services so both interfaces apply the same rules.
Only `mcp/` imports the MCP SDK. The existing `auditor-mcp` command and
`dev.py` Inspector entry point continue to launch the MCP server.

## Setup

```powershell
uv sync
```

## Run the tests

```powershell
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Try it in the MCP Inspector

```powershell
uv run mcp dev dev.py
```

## Claude Desktop config (this is the window equivalent)

```json
"auditor": {
  "command": "C:\\Users\\HP\\.local\\bin\\uv.exe",
  "args": ["--directory", "C:\\pyProjects\\mcp-projects\\auditor-mcp", "run", "auditor-mcp"]
}
```

## Configuration

| Variable              | Default         | Meaning                                    |
| --------------------- | --------------- | ------------------------------------------ |
| `AUDITOR_LOG_DIR`     | `./logs`        | Folder for `audit.jsonl`                   |
| `AUDITOR_WORD_LIMIT`  | `100`           | Maximum words stored per query or response |
| `AUDITOR_LOG_LEVEL`   | `INFO`          | Diagnostic log level (stderr)              |

## Adding a feature

1. Put the rules in a service under `services/`, with unit tests.
2. If it needs new storage, extend `AuditRepository` and the JSONL implementation.
3. Expose it as tools in a new `mcp/tools/<feature>_tools.py` with a `register_*` function.
4. Call that function from `create_server()` in `mcp/server.py`.

Website endpoints belong in `api/` and should call the same shared services.
