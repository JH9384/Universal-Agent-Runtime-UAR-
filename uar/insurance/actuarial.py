"""Agent Insurance MVP - Actuarial data collection from provenance logs.

Collects run metrics for actuarial analysis, risk scoring,
and insurance pricing.
Generates datasets suitable for underwriting AI agent performance.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import statistics

logger = logging.getLogger(__name__)


@dataclass
class RunMetrics:
    """Metrics for a single run - actuarial data point."""
    run_id: str
    timestamp: float
    duration_seconds: float
    success: bool
    skill_count: int
    error_count: int
    user_id: str
    uor_address: Optional[str] = None
    goal_category: Optional[str] = None  # derived from goal text


@dataclass
class RiskProfile:
    """Risk profile for insurance pricing."""
    user_id: str
    total_runs: int
    success_rate: float
    avg_duration: float
    volatility_score: float  # std dev of durations
    error_frequency: float
    risk_tier: str  # "low", "medium", "high"
    estimated_premium_multiplier: float


class ActuarialCollector:
    """Collect actuarial data from UAR run logs."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path("data/actuarial.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize actuarial database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_metrics (
                    run_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    duration_seconds REAL,
                    success INTEGER,
                    skill_count INTEGER,
                    error_count INTEGER,
                    user_id TEXT,
                    uor_address TEXT,
                    goal_category TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_user_metrics
                ON run_metrics(user_id, timestamp)
                """
            )
            conn.commit()
        finally:
            conn.close()

    def ingest_run(self, run_record: Dict[str, Any]) -> None:
        """Ingest a run record for actuarial analysis."""
        # Derive goal category from goal text
        goal = run_record.get("goal", "")
        goal_category = self._categorize_goal(goal)

        # Count skills
        skills = run_record.get("skills", [])
        skill_count = len(skills) if isinstance(skills, list) else 0

        # Count errors from events
        events = run_record.get("events", [])
        error_count = sum(
            1 for e in events
            if isinstance(e, dict) and e.get("type") == "error"
        )

        # Calculate duration from events
        duration = self._calculate_duration(events)

        metrics = RunMetrics(
            run_id=run_record.get("run_id", ""),
            timestamp=run_record.get("timestamp", 0.0),
            duration_seconds=duration,
            success=run_record.get("status") == "completed",
            skill_count=skill_count,
            error_count=error_count,
            user_id=run_record.get("user_id", "anonymous"),
            uor_address=run_record.get("uor_address"),
            goal_category=goal_category,
        )

        self._store_metrics(metrics)
        logger.debug(
            "Ingested actuarial metrics for run %s", metrics.run_id
        )

    def _categorize_goal(self, goal: str) -> str:
        """Categorize goal text for risk analysis."""
        goal_lower = goal.lower()
        categories = {
            "file": ["file", "document", "pdf", "csv", "read", "write"],
            "web": ["web", "url", "http", "api", "fetch", "download"],
            "data": ["data", "analysis", "calculate", "compute", "math"],
            "code": ["code", "program", "script", "function", "class"],
            "communication": ["email", "message", "send", "notify", "alert"],
        }

        for category, keywords in categories.items():
            if any(kw in goal_lower for kw in keywords):
                return category
        return "general"

    def _calculate_duration(self, events: List[Dict]) -> float:
        """Calculate run duration from events."""
        if not events:
            return 0.0

        timestamps = [
            e.get("timestamp", 0) for e in events
            if isinstance(e, dict) and "timestamp" in e
        ]

        if len(timestamps) < 2:
            return 0.0

        return max(timestamps) - min(timestamps)

    def _store_metrics(self, metrics: RunMetrics) -> None:
        """Store metrics in database."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO run_metrics
                (run_id, timestamp, duration_seconds, success, skill_count,
                 error_count, user_id, uor_address, goal_category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metrics.run_id,
                    metrics.timestamp,
                    metrics.duration_seconds,
                    1 if metrics.success else 0,
                    metrics.skill_count,
                    metrics.error_count,
                    metrics.user_id,
                    metrics.uor_address,
                    metrics.goal_category,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def calculate_risk_profile(self, user_id: str) -> Optional[RiskProfile]:
        """Calculate risk profile for insurance pricing."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                """
                SELECT duration_seconds, success, error_count
                FROM run_metrics
                WHERE user_id = ?
                AND timestamp > ?
                """,
                (user_id, (datetime.now() - timedelta(days=90)).timestamp()),
            )
            rows = cursor.fetchall()

            if not rows:
                return None

            durations = [r[0] for r in rows]
            successes = [r[1] for r in rows]
            error_counts = [r[2] for r in rows]

            total_runs = len(rows)
            success_rate = sum(successes) / total_runs
            avg_duration = statistics.mean(durations)
            volatility = (
                statistics.stdev(durations) if len(durations) > 1 else 0
            )
            error_freq = sum(error_counts) / total_runs

            # Calculate risk tier
            risk_score = (
                (1 - success_rate) * 0.5 +
                (error_freq / max(error_counts + [1])) * 0.3 +
                (volatility / max(avg_duration, 1)) * 0.2
            )

            if risk_score < 0.1:
                tier = "low"
                multiplier = 1.0
            elif risk_score < 0.3:
                tier = "medium"
                multiplier = 1.5
            else:
                tier = "high"
                multiplier = 2.5

            return RiskProfile(
                user_id=user_id,
                total_runs=total_runs,
                success_rate=success_rate,
                avg_duration=avg_duration,
                volatility_score=volatility,
                error_frequency=error_freq,
                risk_tier=tier,
                estimated_premium_multiplier=multiplier,
            )
        finally:
            conn.close()

    def export_dataset(
        self,
        output_path: Path,
        days: int = 90,
    ) -> None:
        """Export actuarial dataset for insurance partners."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                """
                SELECT * FROM run_metrics
                WHERE timestamp > ?
                """,
                ((datetime.now() - timedelta(days=days)).timestamp(),),
            )

            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()

            dataset = {
                "exported_at": datetime.now().isoformat(),
                "period_days": days,
                "total_records": len(rows),
                "records": [
                    dict(zip(columns, row)) for row in rows
                ],
            }

            output_path.write_text(json.dumps(dataset, indent=2))
            logger.info(
                "Exported %s records to %s", len(rows), output_path
            )
        finally:
            conn.close()

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for dashboard."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*),
                    AVG(success),
                    AVG(duration_seconds),
                    AVG(error_count),
                    COUNT(DISTINCT user_id)
                FROM run_metrics
                """
            )
            row = cursor.fetchone()

            return {
                "total_runs": row[0] or 0,
                "overall_success_rate": row[1] or 0,
                "avg_duration": row[2] or 0,
                "avg_errors": row[3] or 0,
                "unique_users": row[4] or 0,
            }
        finally:
            conn.close()


# Global instance
_collector: Optional[ActuarialCollector] = None


def get_actuarial_collector() -> ActuarialCollector:
    """Get global actuarial collector instance."""
    global _collector
    if _collector is None:
        _collector = ActuarialCollector()
    return _collector
