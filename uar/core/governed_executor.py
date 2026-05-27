"""Governed executor scaffolding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionAuthorization:
    approved: bool
    reason: str


class GovernedExecutor:
    def authorize(self, execution_name: str) -> ExecutionAuthorization:
        if not execution_name:
            return ExecutionAuthorization(
                approved=False,
                reason="execution_name_missing",
            )

        return ExecutionAuthorization(
            approved=True,
            reason="authorized",
        )

    def execute(self, execution_name: str) -> str:
        authorization = self.authorize(execution_name)

        if not authorization.approved:
            raise PermissionError(authorization.reason)

        return f"executed:{execution_name}"
