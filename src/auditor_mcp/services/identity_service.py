"""Identity and authorization scenarios for the Moko MCP server.

Scenarios:
    1. User-delegated access:
        An AI assistant or agent acts on behalf of a signed-in user.
        Validate the access token intended for Moko and identify both
        the user and calling application. Enforce user permissions,
        delegated scopes, and Moko policies.

    2. Shared application access:
        An AI application uses one app-only service identity for
        requests from multiple users. The token identifies the
        application, not the individual user. Enforce service-level
        permissions; do not trust user identities supplied by the
        model in tool arguments.

    3. Independent agent access:
        An agent operates using a dedicated workload identity, such
        as a service principal or managed identity. Enforce explicitly
        assigned permissions and task restrictions. Record its owner
        and any verified initiator without inheriting their access.

Notes:
    Shared applications and independent agents can both use app-only
    tokens. Distinguish them through trusted registration/configuration,
    not by asking the model or examining token type alone.

    Validate credentials and authorize every tool call. Derive roles
    from trusted claims or server-side mappings. Record the identity,
    action, resource, and policy decision without logging raw tokens.
"""

from urllib.parse import urlparse

import jwt

from auditor_mcp.models import IdentitySettings, VerifiedIdentity


class IdentityService:
    """Validate credentials and return a trusted identity.

    Called by the HTTP authentication layer before tools execute.
    JWT verification is implemented; identity mapping remains a design sketch.
    """

    def __init__(
        self, settings: IdentitySettings, token_verifier: jwt.PyJWKClient | None = None
    ) -> None:
        self._settings = settings
        self._validate_settings()
        self._token_verifier = (
            token_verifier if token_verifier is not None else jwt.PyJWKClient(settings.jwks_uri)
        )

    def validate_token(self, access_token: str) -> VerifiedIdentity:
        """Pseudocode for authenticating one incoming access token."""

        if not jwt.algorithms.has_crypto:
            raise RuntimeError("JWT cryptography support is required.")

        # 1. Reject a missing or empty token with an authentication error.
        #    The HTTP layer translates authentication errors into a 401.

        if not access_token or not access_token.strip():
            raise ValueError("Access token is required.")
        # 2. Check the admin configuration injected into this service.
        #    This initial version supports one trusted issuer and audience.
        #    Never obtain trust settings from the token or tool arguments.
        self._validate_settings()

        # 3. Select a configured provider to verify the token.
        #    This service supports one provider: the injected verifier
        #    associated with the admin-configured issuer. Selection does
        #    not require decoding the token or trusting a caller's URL.
        self._select_provider()

        # 4. Verify the JWT using the configured provider's signing keys.
        #    Steps 5-7 will map the returned claims into VerifiedIdentity.
        self._verify_and_decode_token(access_token)

        # 5. Normalize the verified provider-specific claims:
        #    - subject: the principal's identifier within this issuer
        #    - organization_id: mapped from verified tenant/organization
        #      claims and trusted server configuration
        #    - client_id: the verified calling application's identifier
        #    - principal_type / authorization_mode: derived using the
        #      provider's documented claims and trusted configuration
        #    - roles / scopes: from verified claims or trusted mappings
        #    Reject tokens that cannot establish the required identity.
        #
        # 6. Confirm the organization is allowed by server configuration.
        #    Keep the issuer and subject together when identifying a
        #    principal. Never substitute identity from tool arguments.
        #
        # 7. Return VerifiedIdentity(
        #        provider=configured_provider.name,
        #        issuer=verified_issuer,
        #        subject=verified_subject,
        #        organization_id=verified_organization_id,
        #        client_id=verified_client_id,
        #        principal_type=verified_principal_type,
        #        authorization_mode=verified_authorization_mode,
        #        roles=verified_roles,
        #        scopes=verified_scopes,
        #    )
        #
        # After authentication, authorization checks whether this identity
        # may perform the requested action on the requested resource.
        # Never log the raw access token.
        raise NotImplementedError(
            "Identity mapping and organization authorization are not implemented."
        )

    def _select_provider(self) -> jwt.PyJWKClient:
        """Select the verifier supplied for this service's configured issuer.

        The server must construct this verifier using the same trusted
        settings. Step 4 must still verify the token's issuer and audience;
        selecting a verifier does not authenticate the token.
        """
        if self._token_verifier is None:
            raise ValueError("A token verifier must be configured for the trusted issuer.")
        return self._token_verifier

    def _validate_settings(self) -> None:
        """Require explicit trust settings before attempting verification."""
        if not self._settings.issuer.strip():
            raise ValueError("Identity issuer must be configured.")
        if not self._settings.audience.strip():
            raise ValueError("Identity audience must be configured.")
        jwks_url = urlparse(self._settings.jwks_uri)
        if jwks_url.scheme != "https" or not jwks_url.hostname:
            raise ValueError("JWKS URI must be a configured HTTPS signing-keys URL.")
        if ".well-known/openid-configuration" in jwks_url.path:
            raise ValueError("Use jwks_uri from discovery, not the OpenID configuration URL.")
        if not self._settings.allowed_organization_ids:
            raise ValueError("At least one allowed organization must be configured.")
        if any(not org_id.strip() for org_id in self._settings.allowed_organization_ids):
            raise ValueError("Allowed organization IDs must not be blank.")

    def _verify_and_decode_token(self, access_token: str) -> dict[str, object]:
        """Return verified claims; propagate PyJWT errors on invalid tokens.

        Only RS256 JWTs are supported. Opaque tokens require a separate
        provider integration. The configured JWKS client is reused so its
        key cache can handle subsequent requests and key rotation.
        """
        if not access_token or not access_token.strip():
            raise ValueError("Access token is required.")
        if not jwt.algorithms.has_crypto:
            raise RuntimeError("JWT cryptography support is required.")

        signing_key = self._select_provider().get_signing_key_from_jwt(access_token)
        return jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self._settings.audience,
            issuer=self._settings.issuer,
            options={"require": ["aud", "iss", "exp", "sub"]},
        )
