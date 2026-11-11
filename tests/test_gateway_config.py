from pathlib import Path

import pytest

from auditor_mcp.gateway import GatewayConfig
from auditor_mcp.gateway.proxy import namespaced, split_name


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "gateway.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_servers_and_resolves_relative_paths(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
        [gateway]
        state_dir = "state"

        [servers.weather]
        command = "uv"
        args = ["run", "weather.py"]
        cwd = "weather"
        env = { KEY = "value" }
        """,
    )
    config = GatewayConfig.load(path)

    [server] = config.servers
    assert server.name == "weather"
    assert server.args == ["run", "weather.py"]
    assert server.cwd == (tmp_path / "weather").resolve()
    assert server.env == {"KEY": "value"}
    assert config.pins_file == (tmp_path / "state" / "pins.json").resolve()
    assert config.events_file == (tmp_path / "logs" / "gateway.jsonl").resolve()


@pytest.mark.parametrize("name", ["my_server", "bad name", "x.y"])
def test_rejects_ambiguous_server_names(tmp_path: Path, name: str) -> None:
    path = _write(tmp_path, f'[servers."{name}"]\ncommand = "x"\n')
    with pytest.raises(ValueError, match="Invalid server name"):
        GatewayConfig.load(path)


def test_requires_command(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="command"):
        GatewayConfig.load(_write(tmp_path, "[servers.weather]\nargs = []\n"))


def test_missing_config_explains_what_to_do(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"gateway\.example\.toml"):
        GatewayConfig.load(tmp_path / "gateway.toml")


def test_namespacing_round_trips_tool_names_with_underscores() -> None:
    assert split_name(namespaced("weather", "get__forecast")) == ("weather", "get__forecast")
    assert split_name("no_separator") is None
    assert split_name("__tool") is None
