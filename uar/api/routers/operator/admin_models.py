"""Pydantic models for operational admin endpoints.

Provides structured request/response validation and OpenAPI documentation
for all Phase A-C admin routers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Maintenance Windows
# ------------------------------------------------------------------

class MaintenanceWindowIn(BaseModel):
    wid: str = Field(
        ..., min_length=1, max_length=128,
        description="Unique window ID",
    )
    start_at: float = Field(..., description="Unix timestamp (seconds)")
    end_at: float = Field(..., description="Unix timestamp (seconds)")
    description: str = Field(default="", max_length=512)


class MaintenanceWindowOut(BaseModel):
    wid: str
    start_at: float
    end_at: float
    description: str
    active: bool


class MaintenanceListOut(BaseModel):
    windows: List[MaintenanceWindowOut]
    active: Optional[MaintenanceWindowOut] = None


# ------------------------------------------------------------------
# Activity Log
# ------------------------------------------------------------------

class ActivityEventOut(BaseModel):
    id: str
    event_type: str
    actor: str
    target: str
    action: str
    details: Dict[str, Any]
    timestamp: float


class ActivityListOut(BaseModel):
    events: List[ActivityEventOut]
    count: int
    hours: int


# ------------------------------------------------------------------
# File Types
# ------------------------------------------------------------------

class FileTypeSettingsOut(BaseModel):
    whitelist: List[str]
    blocklist: List[str]
    allowed_content_types: List[str]
    source: str  # 'env' | 'default'


# ------------------------------------------------------------------
# Data Sources
# ------------------------------------------------------------------

class DataSourceIn(BaseModel):
    dsid: str = Field(..., min_length=1, max_length=128)
    source_type: str = Field(
        ..., pattern=r"^(postgres|sqlite|json|autonomi|api)$",
    )
    location: str = Field(..., min_length=1, max_length=2048)
    description: str = Field(default="", max_length=512)


class DataSourceOut(BaseModel):
    id: str
    source_type: str
    location: str
    description: str
    healthy: bool
    last_check_at: Optional[float] = None
    error: Optional[str] = None


class DataSourceListOut(BaseModel):
    sources: List[DataSourceOut]
    total: int
    healthy: int


# ------------------------------------------------------------------
# Credentials
# ------------------------------------------------------------------

class CredentialIn(BaseModel):
    cred_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    service_type: str = Field(default="generic")
    value: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class CredentialOut(BaseModel):
    id: str
    name: str
    service_type: str
    encrypted_value: str
    created_at: float
    updated_at: float
    last_tested_at: Optional[float] = None
    last_test_status: Optional[str] = None
    metadata: Dict[str, Any]


class CredentialListOut(BaseModel):
    credentials: List[CredentialOut]
    total: int
    encrypted_at_rest: bool


# ------------------------------------------------------------------
# Sync
# ------------------------------------------------------------------

class ResyncIn(BaseModel):
    target: str = Field(..., min_length=1, max_length=128)
    source: Optional[str] = Field(default=None, max_length=128)


class ResyncOut(BaseModel):
    success: bool
    copied: int
    target: str
    source: Optional[str] = None
    error: Optional[str] = None


# ------------------------------------------------------------------
# Self Update
# ------------------------------------------------------------------

class UpdateStatusOut(BaseModel):
    current_version: str
    latest_version: str
    update_available: bool
    source: str
    last_checked_at: float
    error: Optional[str] = None


# ------------------------------------------------------------------
# Admin Audit
# ------------------------------------------------------------------

class AdminActionOut(BaseModel):
    success: bool
    id: Optional[str] = None
    deleted: Optional[bool] = None
    cancelled: Optional[bool] = None
    message: str = ""
