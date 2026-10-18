"""Exercise JWT verification with real signatures and no network requests."""

from time import time
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from auditor_mcp.models import IdentitySettings
from auditor_mcp.services.identity_service import IdentityService


@pytest.fixture
def verification():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = Mock(spec=jwt.PyJWKClient)
    verifier.get_signing_key_from_jwt.return_value.key = private_key.public_key()
    settings = IdentitySettings(
        issuer="https://issuer.example",
        audience="moko-api",
        allowed_organization_ids=("org-a",),
        jwks_uri="https://issuer.example/keys",
    )
    claims = {
        "iss": settings.issuer,
        "aud": settings.audience,
        "sub": "user-a",
        "exp": int(time()) + 300,
    }
    return IdentityService(settings, verifier), private_key, claims


def test_verified_claims(verification):
    service, key, claims = verification
    token = jwt.encode(claims, key, algorithm="RS256")
    assert service._verify_and_decode_token(token) == claims


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("aud", "other-api", jwt.InvalidAudienceError),
        ("iss", "https://untrusted.example", jwt.InvalidIssuerError),
        ("exp", 1, jwt.ExpiredSignatureError),
        ("nbf", int(time()) + 3600, jwt.ImmatureSignatureError),
    ],
)
def test_invalid_claims(verification, field, value, error):
    service, key, claims = verification
    claims[field] = value
    with pytest.raises(error):
        service._verify_and_decode_token(jwt.encode(claims, key, algorithm="RS256"))


@pytest.mark.parametrize("field", ["aud", "iss", "exp", "sub"])
def test_required_claims(verification, field):
    service, key, claims = verification
    del claims[field]
    with pytest.raises(jwt.MissingRequiredClaimError):
        service._verify_and_decode_token(jwt.encode(claims, key, algorithm="RS256"))


def test_wrong_signature(verification):
    service, _, claims = verification
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(jwt.InvalidSignatureError):
        service._verify_and_decode_token(jwt.encode(claims, other_key, algorithm="RS256"))


def test_wrong_algorithm(verification):
    service, _, claims = verification
    token = jwt.encode(claims, "a" * 32, algorithm="HS256")
    with pytest.raises(jwt.InvalidAlgorithmError):
        service._verify_and_decode_token(token)


def test_public_method_stops_before_identity_mapping(verification):
    service, key, claims = verification
    with pytest.raises(NotImplementedError, match="Identity mapping"):
        service.validate_token(jwt.encode(claims, key, algorithm="RS256"))
