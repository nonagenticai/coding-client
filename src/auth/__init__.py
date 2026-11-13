"""Authentication, authorization, and tenant isolation for coding-client.

Provides:
- User model and auth dependencies for FastAPI routes
- Auth middleware for Istio header-based authentication
- RBAC helpers (require_role, require_access_coding)
- Tenant isolation middleware and dependencies
"""

from ._header_trust import trust_tenant_header
from ._onbehalf import (
    may_vouch,
    onbehalf_subjects,
    tenant_license_verified,
    tenant_was_vouched,
)
from .dependencies import get_current_user
from .middleware import AuthMiddleware
from .models import User
from .outbound import (
    LICENSE_ID_HEADER,
    TENANT_ID_HEADER,
    TenantMissingError,
    optional_tenant_headers,
    tenant_headers,
)
from .rbac import require_access_coding, require_role
from .tenant import (
    TenantMiddleware,
    check_tenant_access,
    create_tenant_context,
    get_current_user_with_tenant,
    get_tenant_id,
    optional_tenant,
    require_same_tenant,
    require_tenant,
    require_tenant_context,
)
from .websocket import Outcome, WebSocketIdentity, resolve_websocket_identity

__all__ = [
    # Models
    "User",
    # Dependencies
    "get_current_user",
    # Middleware
    "AuthMiddleware",
    # Header-trust posture (TRUST_TENANT_HEADER)
    "trust_tenant_header",
    # On-behalf-of vouching (CODING_ONBEHALF_SUBJECTS)
    "may_vouch",
    "onbehalf_subjects",
    "tenant_license_verified",
    "tenant_was_vouched",
    # WebSocket identity (middleware never runs on a websocket scope)
    "Outcome",
    "WebSocketIdentity",
    "resolve_websocket_identity",
    # Outbound identity headers
    "LICENSE_ID_HEADER",
    "TENANT_ID_HEADER",
    "TenantMissingError",
    "optional_tenant_headers",
    "tenant_headers",
    "TenantMiddleware",
    # RBAC
    "require_access_coding",
    "require_role",
    # Tenant
    "check_tenant_access",
    "create_tenant_context",
    "get_current_user_with_tenant",
    "get_tenant_id",
    "optional_tenant",
    "require_same_tenant",
    "require_tenant",
    "require_tenant_context",
]
