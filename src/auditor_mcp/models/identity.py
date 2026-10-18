

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class IdentitySettings:
    issuer: str # "https://login.microsoftonline.com/company-a-tenant/v2.0"
    audience: str # "api://moko"
    allowed_organization_ids: tuple[str, ...] # "company-a-tenant"
    jwks_uri: str
    
    
@dataclass(frozen=True)
class VerifiedIdentity:
    provider: str
    issuer: str 
    subject: str
    organization_id: str
    client_id: str
    principal_type: Literal["user", "workload"]
    authorization_mode: Literal["delegated", "app_only"]
    roles: tuple[str, ...]
    scopes: tuple[str, ...]