"""Tests for distributed executor."""

from uar.core.distributed import (
    DistributedExecutor,
    WorkerPool,
    WorkerResult,
    WorkerTask,
    get_distributed_executor,
)


class TestWorkerPool:
    def test_pool_initialization(self):
        pool = WorkerPool(max_workers=2)
        assert pool.max_workers == 2
        pool.shutdown()

    def test_execute_task_unregistered_skill(self):
        pool = WorkerPool(max_workers=2)
        task = WorkerTask(
            task_id="t1",
            skill_name="nonexistent_skill_12345",
            ctx_data={},
            goal_objective="test",
        )
        result = pool._execute_task(task)
        assert not result.success
        assert "not registered" in result.error
        pool.shutdown()

    def test_map_tasks_empty(self):
        pool = WorkerPool(max_workers=2)
        results = pool.map_tasks([])
        assert results == []
        pool.shutdown()

    def test_health_tracking(self):
        pool = WorkerPool(max_workers=2)
        health = pool.get_health()
        assert isinstance(health, dict)
        pool.shutdown()


class TestDistributedExecutor:
    def test_init(self):
        pool = WorkerPool(max_workers=2)
        dist = DistributedExecutor(pool=pool)
        assert dist.pool is pool
        pool.shutdown()

    def test_get_distributed_executor_singleton(self):
        d1 = get_distributed_executor()
        d2 = get_distributed_executor()
        assert d1 is d2

    def test_execute_skills_parallel_unregistered(self):
        pool = WorkerPool(max_workers=2)
        dist = DistributedExecutor(pool=pool)

        class FakeGoal:
            objective = "test"

        results = dist.execute_skills_parallel(
            ["nonexistent_skill_12345"], FakeGoal()
        )
        assert len(results) == 1
        assert not results[0].success
        pool.shutdown()


class TestDataClasses:
    def test_worker_task_defaults(self):
        t = WorkerTask(
            task_id="t1",
            skill_name="math_compute",
            ctx_data={},
            goal_objective="test",
        )
        assert t.timeout == 5.0

    def test_worker_result_defaults(self):
        r = WorkerResult(
            task_id="t1", skill_name="math_compute", success=True
        )
        assert r.result is None
        assert r.error is None
        assert r.duration_ms == 0.0
