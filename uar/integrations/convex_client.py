"""Convex backend-as-a-service integration for UAR.

Provides real-time database, reactive queries, and serverless functions
as an alternative to the local JsonRunStore.

Install: pip install convex
"""

import os
from typing import Any, AsyncIterator, Optional

from .base import BaseIntegration
from uar.core.circuit_breaker_decorator import with_circuit_breaker

logger = __import__("logging").getLogger(__name__)


class ConvexClient(BaseIntegration):
    """Client for Convex backend.

    Usage:
        client = ConvexClient()
        await client.insert_run(record)
        async for event in client.subscribe_events(run_id):
            ...
    """

    def __init__(self) -> None:
        self.url = os.getenv("CONVEX_URL", "")
        self.deployment = os.getenv("CONVEX_DEPLOYMENT", "")
        self._client: Optional[Any] = None

    def _lazy_client(self) -> Any:
        if self._client is None:
            try:
                from convex import ConvexClient as _ConvexClient

                self._client = _ConvexClient(self.url)
            except ImportError as exc:
                raise ImportError(
                    "convex package not installed. "
                    "Run: pip install convex"
                ) from exc
        return self._client

    @with_circuit_breaker(
        "convex", failure_threshold=5, recovery_timeout=30.0
    )
    async def insert_run(self, record: dict[str, Any]) -> str:
        """Insert a run record into Convex."""
        if not self.url:
            logger.warning("CONVEX_URL not set; skipping insert")
            return ""
        client = self._lazy_client()
        result = await client.mutation("runs:insert", record)
        return str(result.get("_id", ""))

    @with_circuit_breaker(
        "convex", failure_threshold=5, recovery_timeout=30.0
    )
    async def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        """Fetch a single run by ID."""
        if not self.url:
            return None
        client = self._lazy_client()
        return await client.query("runs:get", {"runId": run_id})

    async def list_runs(
        self, user_id: Optional[str] = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List runs, optionally filtered by user."""
        if not self.url:
            return []
        client = self._lazy_client()
        return await client.query(
            "runs:list",
            {"userId": user_id, "limit": limit},
        )

    async def subscribe_events(
        self, run_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to real-time events for a run."""
        if not self.url:
            return
        client = self._lazy_client()
        subscription = await client.subscribe(
            "events:forRun", {"runId": run_id}
        )
        async for update in subscription:
            yield update

    # ------------------------------------------------------------------
    # Schema helpers (Convex mutation definitions — run once at deploy)
    # ------------------------------------------------------------------
    @staticmethod
    def schema_definitions() -> dict[str, str]:
        """Return Convex schema and function definitions as strings.

        Save these into your Convex project's ``schema.ts`` and
        ``convex/`` directory.
        """
        return {
            "schema.ts": '''
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  runs: defineTable({
    runId: v.string(),
    goalId: v.string(),
    userId: v.optional(v.string()),
    skills: v.array(v.string()),
    status: v.string(),
    errors: v.array(v.string()),
    events: v.array(v.any()),
    finalContext: v.optional(v.any()),
    createdAt: v.number(),
  })
    .index("by_run_id", ["runId"])
    .index("by_user", ["userId"]),

  events: defineTable({
    runId: v.string(),
    type: v.string(),
    skill: v.optional(v.string()),
    payload: v.optional(v.any()),
    timestamp: v.number(),
  })
    .index("by_run", ["runId"])
    .index("by_type", ["type"]),
});
''',
            "runs.ts": '''
import { v } from "convex/values";
import { query, mutation } from "./_generated/server";

export const insert = mutation({
  args: {
    runId: v.string(),
    goalId: v.string(),
    userId: v.optional(v.string()),
    skills: v.array(v.string()),
    status: v.string(),
    errors: v.array(v.string()),
    events: v.array(v.any()),
    finalContext: v.optional(v.any()),
    createdAt: v.number(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("runs", args);
  },
});

export const get = query({
  args: { runId: v.string() },
  handler: async (ctx, { runId }) => {
    return await ctx.db
      .query("runs")
      .withIndex("by_run_id", (q) => q.eq("runId", runId))
      .first();
  },
});

export const list = query({
  args: {
    userId: v.optional(v.string()),
    limit: v.number(),
  },
  handler: async (ctx, { userId, limit }) => {
    let q = ctx.db.query("runs");
    if (userId) {
      q = q.withIndex("by_user", (iq) => iq.eq("userId", userId));
    }
    return await q.take(limit);
  },
});
''',
        }
