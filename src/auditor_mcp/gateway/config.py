"""Gateway configuration, read from a TOML file (``gateway.toml`` by default).

Example::

    [gateway]
    state_dir = "state"     # pins.json lives here
    log_dir = "logs"        # gateway.jsonl lives here

    [servers.weather]
    command = "C:\\\\Users\\\\HP\\\\.local\\\\bin\\\\uv.exe"
    args = ["--directory", "C:\\\\pyProjects\\\\mcp-projects\\\\weather", "run", "weather.py"]

Relative paths are resolved against the folder containing the config file.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_ENV_VAR = "AUDITOR_GATEWAY_CONFIG"
DEFAULT_CONFIG_NAME = "gateway.toml"
NAMESPACE_SEPARATOR = "__"
_SERVER_NAME = re.compile(r"^[A-Za-z0-9-]+$")  # no underscores: keeps "__" unambiguous


@dataclass(frozen=True, slots=True)
class DownstreamServer:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    cwd: Path | None = None
    env: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    servers: list[DownstreamServer]
    state_dir: Path
    log_dir: Path
    call_timeout_seconds: float = 60.0

    @property
    def pins_file(self) -> Path:
        return self.state_dir / "pins.json"

    @property
    def events_file(self) -> Path:
        return self.log_dir / "gateway.jsonl"

    @classmethod
    def load(cls, path: Path | None = None) -> GatewayConfig:
        path = (path or default_config_path()).resolve()
        if not path.exists():
            raise FileNotFoundError(
                f"Gateway config not found: {path}. Copy gateway.example.toml to gateway.toml."
            )
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        base = path.parent

        def resolve(value: str | None, default: str) -> Path:
            p = Path(value or default)
            return p if p.is_absolute() else (base / p).resolve()

        gateway = data.get("gateway", {})
        servers = [
            _parse_server(name, spec, base) for name, spec in data.get("servers", {}).items()
        ]
        return cls(
            servers=servers,
            state_dir=resolve(gateway.get("state_dir"), "state"),
            log_dir=resolve(gateway.get("log_dir"), "logs"),
            call_timeout_seconds=float(gateway.get("call_timeout_seconds", 60)),
        )


def default_config_path() -> Path:
    return Path(os.environ.get(CONFIG_ENV_VAR, Path.cwd() / DEFAULT_CONFIG_NAME))


def _parse_server(name: str, spec: dict, base: Path) -> DownstreamServer:
    if not _SERVER_NAME.match(name):
        raise ValueError(f"Invalid server name {name!r}: use letters, digits and hyphens only.")
    if "command" not in spec:
        raise ValueError(f"Server {name!r} needs a 'command'.")
    cwd = Path(spec["cwd"]) if "cwd" in spec else None
    if cwd is not None and not cwd.is_absolute():
        cwd = (base / cwd).resolve()
    return DownstreamServer(
        name=name,
        command=spec["command"],
        args=[str(a) for a in spec.get("args", [])],
        cwd=cwd,
        env={str(k): str(v) for k, v in spec["env"].items()} if "env" in spec else None,
    )
