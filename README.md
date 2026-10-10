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
│   ├── server.py            create_server(): wires everything together
│   ├── config.py            Settings, read from AUDITOR_* env vars
│   ├── logging_setup.py     diagnostic logging to stderr
│   ├── models.py            AuditEntry, Turn, EntryType
│   ├── storage/             persistence (AuditRepository + JSONL implementation)
│   ├── services/            business rules (AuditService, word limit)
│   └── tools/               MCP tool definitions (thin layer over services)
└── tests/                   unit tests and in-process MCP client tests
```

Dependencies point one way: `tools → services → storage → models`. Only
`tools/` and `server.py` import the MCP SDK.

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
3. Expose it as tools in a new `tools/<feature>_tools.py` with a `register_*` function.
4. Call that function from `create_server()` in `server.py`.
