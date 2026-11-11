"""Provider discovery uses trusted startup configuration, without real HTTP."""

import io
import json
from unittest.mock import patch
from urllib.error import URLError

import pytest

from auditor_mcp.models import IdentitySettings
from auditor_mcp.services.identity_service import IdentityService

ISSUER = "https://login.microsoftonline.com/tenant-a/v2.0"
KEYS = "https://login.microsoftonline.com/tenant-a/discovery/v2.0/keys"


def settings():
    return IdentitySettings(ISSUER, "moko", ("tenant-a",))


def response(metadata):
    result = io.BytesIO(json.dumps(metadata).encode())
    result.geturl = lambda: ISSUER + "/.well-known/openid-configuration"
    return result


def test_discovers_keys_at_startup():
    with (
        patch("auditor_mcp.services.identity_service.urlopen") as fetch,
        patch("auditor_mcp.services.identity_service.jwt.PyJWKClient") as client,
    ):
        fetch.return_value = response({"issuer": ISSUER, "jwks_uri": KEYS})
        IdentityService(settings())
        fetch.assert_called_once_with(ISSUER + "/.well-known/openid-configuration", timeout=10)
        client.assert_called_once_with(KEYS)


@pytest.mark.parametrize(
    "metadata",
    [
        {"issuer": "https://other.example", "jwks_uri": KEYS},
        {"issuer": ISSUER},
        {"issuer": ISSUER, "jwks_uri": "http://insecure.example/keys"},
        {"issuer": ISSUER, "jwks_uri": ISSUER + "/.well-known/openid-configuration"},
        [],
    ],
)
def test_rejects_bad_metadata(metadata):
    with (
        patch("auditor_mcp.services.identity_service.urlopen", return_value=response(metadata)),
        pytest.raises(ValueError),
    ):
        IdentityService(settings())


def test_discovery_failure():
    with (
        patch("auditor_mcp.services.identity_service.urlopen", side_effect=URLError("offline")),
        pytest.raises(RuntimeError, match="Unable to load"),
    ):
        IdentityService(settings())


def test_explicit_keys_skip_discovery():
    with patch("auditor_mcp.services.identity_service.urlopen") as fetch:
        IdentityService(IdentitySettings(ISSUER, "moko", ("tenant-a",), KEYS))
        fetch.assert_not_called()
