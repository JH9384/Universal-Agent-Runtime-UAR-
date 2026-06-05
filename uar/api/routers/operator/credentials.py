"""Credential vault router for operator dashboard."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from uar.api.routers.operator.admin_models import (
    AdminActionOut,
    CredentialIn,
)
from uar.api.routers.operator.common import (
    audit_admin_action,
    require_operator,
)
from uar.core.credential_vault import get_credential_vault

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/credentials")
async def get_credentials(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return all stored credentials (values masked)."""
    require_operator(credentials)
    vault = get_credential_vault()
    creds = await run_in_threadpool(vault.list_credentials)
    return {
        "credentials": [c.to_dict(mask=True) for c in creds],
        "total": len(creds),
        "encrypted_at_rest": vault._fernet is not None,
    }


@router.post("/api/uar/credentials")
async def post_credential(
    body: CredentialIn,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Store or update a credential."""
    user_info = require_operator(credentials)
    vault = get_credential_vault()
    entry = await run_in_threadpool(
        vault.set_credential,
        body.cred_id,
        body.name,
        body.service_type,
        body.value,
        body.metadata or {},
    )
    audit_admin_action(
        user_info=user_info,
        action="POST /api/uar/credentials",
        resource=f"credential:{body.cred_id}",
        outcome="success",
        details={"service_type": body.service_type},
    )
    return entry.to_dict(mask=True)


@router.delete("/api/uar/credentials/{cred_id}")
async def delete_credential(
    cred_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Remove a credential."""
    user_info = require_operator(credentials)
    vault = get_credential_vault()
    existed = await run_in_threadpool(vault.delete_credential, cred_id)
    audit_admin_action(
        user_info=user_info,
        action="DELETE /api/uar/credentials",
        resource=f"credential:{cred_id}",
        outcome="success" if existed else "not_found",
    )
    return AdminActionOut(
        success=True, id=cred_id, deleted=existed,
        message=(
            f"Credential '{cred_id}' deleted."
            if existed else f"Credential '{cred_id}' not found."
        ),
    ).model_dump()


@router.post("/api/uar/credentials/{cred_id}/test")
async def test_credential(
    cred_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Test connectivity for a credential."""
    require_operator(credentials)
    vault = get_credential_vault()
    result = await run_in_threadpool(vault.test_credential, cred_id)
    return result
