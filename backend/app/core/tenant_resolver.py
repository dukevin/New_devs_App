"""Resolve tenant ownership from verified, server-controlled claims."""
from typing import Optional


class TenantResolver:
    @staticmethod
    def resolve_tenant_from_token(token_payload: dict) -> Optional[str]:
        tenant_id = (token_payload.get("app_metadata") or {}).get("tenant_id") or token_payload.get("tenant_id")
        return tenant_id if isinstance(tenant_id, str) and tenant_id.strip() else None

    @staticmethod
    def resolve_tenant_from_user(user_data: dict) -> Optional[str]:
        return TenantResolver.resolve_tenant_from_token(user_data)
