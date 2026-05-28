"""Locust load tests for UAR API.

Run: locust -f tests/performance/locustfile.py --host http://localhost:8000

Requires: pip install locust
"""

import random

from locust import (  # type: ignore[import-untyped]
    HttpUser, TaskSet, between, task,
)


class StreamingTasks(TaskSet):
    """Load test streaming endpoints."""

    @task(3)
    def test_sse_stream(self):
        """POST to /api/uar/stream and consume SSE events."""
        payload = {
            "goal": f"load test {random.randint(1, 1000000)}",
            "skills": ["section_sum"],
        }
        with self.client.post(
            "/api/uar/stream",
            json=payload,
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                # Consume a few chunks to verify streaming works under load
                chunk_count = 0
                for _ in response.iter_lines():
                    chunk_count += 1
                    if chunk_count >= 3:
                        break
                response.success()
            else:
                response.failure(
                    f"Stream returned {response.status_code}"
                )

    @task(1)
    def test_run_endpoint(self):
        """POST to /api/uar/run (synchronous execution)."""
        payload = {
            "goal": f"run test {random.randint(1, 1000000)}",
            "skills": ["section_sum"],
        }
        self.client.post("/api/uar/run", json=payload)

    @task(2)
    def test_list_runs(self):
        """GET /api/uar/runs (read-heavy endpoint)."""
        self.client.get("/api/uar/runs")

    @task(1)
    def test_get_skills(self):
        """GET /api/uar/skills."""
        self.client.get("/api/uar/skills")

    @task(1)
    def test_health(self):
        """GET /health (used by load balancers)."""
        self.client.get("/health")


class WebSocketTasks(TaskSet):
    """Load test WebSocket endpoints (requires locust-plugins)."""

    @task(1)
    def test_websocket_run(self):
        """Connect to /ws/run and send a goal.

        Note: Locust's built-in HTTP client does not support WebSockets.
        For true WebSocket load testing, use a separate tool like
        `websocat` or a custom asyncio script.
        """
        # Placeholder: In production, use a WebSocket-specific load tester
        pass


class UARUser(HttpUser):
    """Simulated UAR API user."""

    tasks = [StreamingTasks]
    wait_time = between(0.5, 2.0)
    # Default weight for all tasks


class HeavyUser(HttpUser):
    """Simulated heavy UAR API user (more frequent requests)."""

    tasks = [StreamingTasks]
    wait_time = between(0.1, 0.5)
    weight = 3
