"""Multi-tenant security hardening for untrusted agent hosting.

Provides sandboxing, resource isolation, and security controls for
dangerous agent code in multi-tenant environments.
"""
from __future__ import annotations

import hashlib
import logging
import resource
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import threading

logger = logging.getLogger(__name__)

# Security constants
MAX_MEMORY_MB = 512  # Per-run memory limit
MAX_CPU_TIME_SECONDS = 60  # Per-run CPU time limit
MAX_FILE_SIZE_MB = 100
MAX_OPEN_FILES = 64
ALLOWED_FILE_EXTENSIONS: Set[str] = {
    ".txt", ".md", ".json", ".csv", ".py", ".js",
    ".html", ".css", ".xml", ".yaml", ".yml",
}
BLOCKED_PATHS: Set[str] = {
    "/etc/passwd", "/etc/shadow", "/etc/hosts",
    "/proc", "/sys", "/dev",
    ".ssh", ".aws", ".kube",
}


class SecuritySandbox:
    """Sandbox for executing untrusted agent code."""

    def __init__(
        self,
        tenant_id: str,
        run_id: str,
        memory_limit_mb: int = MAX_MEMORY_MB,
        cpu_limit_seconds: int = MAX_CPU_TIME_SECONDS,
    ):
        self.tenant_id = tenant_id
        self.run_id = run_id
        self.memory_limit = memory_limit_mb * 1024 * 1024  # bytes
        self.cpu_limit = cpu_limit_seconds
        self.workspace: Optional[Path] = None
        self._original_limits: Optional[tuple] = None

    def _create_workspace(self) -> Path:
        """Create isolated workspace for tenant."""
        workspace_hash = hashlib.sha256(
            f"{self.tenant_id}:{self.run_id}".encode()
        ).hexdigest()[:16]

        workspace = Path(
            tempfile.gettempdir()
        ) / "uar_sandbox" / workspace_hash
        workspace.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (workspace / "input").mkdir(exist_ok=True)
        (workspace / "output").mkdir(exist_ok=True)
        (workspace / "tmp").mkdir(exist_ok=True)

        return workspace

    def _apply_resource_limits(self) -> None:
        """Apply resource limits to current process."""
        try:
            # Memory limit (soft, hard)
            resource.setrlimit(
                resource.RLIMIT_AS,
                (self.memory_limit, self.memory_limit)
            )

            # CPU time limit
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (
                    self.cpu_limit,
                    self.cpu_limit + 5,
                )  # hard limit slightly higher
            )

            # File size limit
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (
                    MAX_FILE_SIZE_MB * 1024 * 1024,
                    MAX_FILE_SIZE_MB * 1024 * 1024,
                )
            )

            # Open files limit
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (MAX_OPEN_FILES, MAX_OPEN_FILES)
            )

            logger.debug(
                "Applied resource limits for %s", self.run_id
            )
        except Exception as e:
            logger.warning(
                "Could not apply resource limits: %s", e
            )

    def _save_original_limits(self) -> None:
        """Save original resource limits."""
        try:
            self._original_limits = (
                resource.getrlimit(resource.RLIMIT_AS),
                resource.getrlimit(resource.RLIMIT_CPU),
                resource.getrlimit(resource.RLIMIT_FSIZE),
                resource.getrlimit(resource.RLIMIT_NOFILE),
            )
        except Exception:
            logger.exception("Resource limit read failed")

    def _restore_limits(self) -> None:
        """Restore original resource limits."""
        if self._original_limits:
            try:
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    self._original_limits[0],
                )
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    self._original_limits[1],
                )
                resource.setrlimit(
                    resource.RLIMIT_FSIZE,
                    self._original_limits[2],
                )
                resource.setrlimit(
                    resource.RLIMIT_NOFILE,
                    self._original_limits[3],
                )
            except Exception:
                logger.exception("Resource limit restore failed")

    def __enter__(self) -> "SecuritySandbox":
        """Enter sandbox context."""
        self.workspace = self._create_workspace()
        self._save_original_limits()
        self._apply_resource_limits()
        logger.info(
            "Sandbox created for tenant %s, run %s",
            self.tenant_id,
            self.run_id,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit sandbox context - cleanup."""
        self._restore_limits()

        # Cleanup workspace
        if self.workspace and self.workspace.exists():
            try:
                import shutil
                shutil.rmtree(self.workspace, ignore_errors=True)
                logger.debug(
                    "Cleaned up workspace %s", self.workspace
                )
            except Exception as e:
                logger.warning(
                    "Failed to cleanup workspace: %s", e
                )

    def get_working_directory(self) -> Path:
        """Get sandbox working directory."""
        if not self.workspace:
            raise RuntimeError("Sandbox not initialized")
        return self.workspace

    def validate_file_access(self, path: Path) -> bool:
        """Validate file access is within sandbox."""
        try:
            resolved = path.resolve()

            # Check blocked paths
            for blocked in BLOCKED_PATHS:
                if blocked in str(resolved):
                    logger.warning(
                        "Blocked access to %s - matches %s",
                        path,
                        blocked,
                    )
                    return False

            # Must be within sandbox or explicitly allowed
            if self.workspace and str(resolved).startswith(
                str(self.workspace)
            ):
                return True

            # Check extension
            if resolved.suffix.lower() not in ALLOWED_FILE_EXTENSIONS:
                logger.warning(
                    "Blocked file with extension %s",
                    resolved.suffix,
                )
                return False

            return True
        except Exception as e:
            logger.warning(
                "File access validation error: %s", e
            )
            return False


class TenantIsolation:
    """Manage isolation between tenants."""

    def __init__(self):
        self._tenant_workspaces: Dict[str, Path] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _get_tenant_lock(self, tenant_id: str) -> threading.Lock:
        """Get or create lock for tenant."""
        with self._global_lock:
            if tenant_id not in self._locks:
                self._locks[tenant_id] = threading.Lock()
            return self._locks[tenant_id]

    def create_isolated_workspace(
        self,
        tenant_id: str,
        run_id: str,
    ) -> Path:
        """Create isolated workspace for tenant run."""
        with self._get_tenant_lock(tenant_id):
            # Use tenant-specific directory
            tenant_hash = hashlib.sha256(tenant_id.encode()).hexdigest()[:16]
            base = Path(tempfile.gettempdir()) / "uar_tenants" / tenant_hash

            # Run-specific subdirectory
            run_hash = hashlib.sha256(run_id.encode()).hexdigest()[:8]
            workspace = base / run_hash
            workspace.mkdir(parents=True, exist_ok=True)

            self._tenant_workspaces[f"{tenant_id}:{run_id}"] = workspace

            return workspace

    def cleanup_tenant(self, tenant_id: str) -> None:
        """Cleanup all workspaces for a tenant."""
        with self._get_tenant_lock(tenant_id):
            tenant_hash = hashlib.sha256(tenant_id.encode()).hexdigest()[:16]
            tenant_dir = Path(
                tempfile.gettempdir()
            ) / "uar_tenants" / tenant_hash

            if tenant_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(tenant_dir)
                    logger.info(
                        "Cleaned up tenant %s", tenant_id
                    )
                except Exception as e:
                    logger.error(
                        "Failed to cleanup tenant %s: %s",
                        tenant_id,
                        e,
                    )

            # Remove from tracking
            keys_to_remove = [
                k for k in self._tenant_workspaces.keys()
                if k.startswith(f"{tenant_id}:")
            ]
            for key in keys_to_remove:
                del self._tenant_workspaces[key]


class SecurityPolicy:
    """Configurable security policy for multi-tenant hosting."""

    def __init__(
        self,
        allow_network: bool = False,
        allow_file_write: bool = True,
        allow_file_delete: bool = False,
        allowed_imports: Optional[List[str]] = None,
        blocked_imports: Optional[List[str]] = None,
    ):
        self.allow_network = allow_network
        self.allow_file_write = allow_file_write
        self.allow_file_delete = allow_file_delete
        self.allowed_imports = set(allowed_imports or [])
        self.blocked_imports = set(blocked_imports or [
            "os.system", "subprocess", "pty", "socket"
        ])

    def validate_import(self, module_name: str) -> bool:
        """Check if module import is allowed."""
        if self.blocked_imports and module_name in self.blocked_imports:
            return False
        if self.allowed_imports and module_name not in self.allowed_imports:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize policy to dict."""
        return {
            "allow_network": self.allow_network,
            "allow_file_write": self.allow_file_write,
            "allow_file_delete": self.allow_file_delete,
            "allowed_imports": list(self.allowed_imports),
            "blocked_imports": list(self.blocked_imports),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityPolicy":
        """Deserialize policy from dict."""
        return cls(
            allow_network=data.get("allow_network", False),
            allow_file_write=data.get("allow_file_write", True),
            allow_file_delete=data.get("allow_file_delete", False),
            allowed_imports=data.get("allowed_imports"),
            blocked_imports=data.get("blocked_imports"),
        )


# Global tenant isolation manager
_tenant_isolation: Optional[TenantIsolation] = None


def get_tenant_isolation() -> TenantIsolation:
    """Get global tenant isolation manager."""
    global _tenant_isolation
    if _tenant_isolation is None:
        _tenant_isolation = TenantIsolation()
    return _tenant_isolation


@contextmanager
def sandboxed_execution(
    tenant_id: str,
    run_id: str,
    memory_limit_mb: int = MAX_MEMORY_MB,
    cpu_limit_seconds: int = MAX_CPU_TIME_SECONDS,
):
    """Context manager for sandboxed execution.

    Usage:
        with sandboxed_execution("tenant_123", "run_456") as sandbox:
            # Execute untrusted code here
            result = run_agent_code(sandbox)
    """
    sandbox = SecuritySandbox(
        tenant_id, run_id, memory_limit_mb, cpu_limit_seconds
    )
    try:
        yield sandbox
    finally:
        sandbox.__exit__(None, None, None)
