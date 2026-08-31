"""
Black-box tests for database resilience: retry, lazy re-init, honest health.

The bug these exist for ran in production for weeks. Neon suspends an idle
database on the free tier and Cloud Run scales to zero, so a cold container
regularly starts while the database is waking and the pool creation times out.
That failure was caught as non-fatal and app.state.db_pool was set to None -
PERMANENTLY, because nothing ever retried. Every request that instance served
afterwards silently skipped persistence.

Observed on 12, 19 and 25 Aug 2026 with "DB pool init failed (non-fatal):
Authentication timed out". The consequences were invisible: /health said "ok",
the guardrail suite passed 9/9, and analysis worked. What stopped was quiz
score persistence, which is what makes comprehension_delta computable, and
discharge history, which is what the clinician dashboard reads.

Nothing here touches a real database. Async calls use asyncio.run(),
matching the convention already used elsewhere in this suite rather
than adding a pytest plugin.
"""

import asyncio
from types import SimpleNamespace

import pytest

from dischargeiq.api.dependencies import get_db_pool as pool_dependency
from dischargeiq.db import history


class _FakePool:
    """Stands in for asyncpg.Pool; identity is all these tests need."""


def _request(app_state) -> SimpleNamespace:
    """Minimal stand-in for a FastAPI Request carrying app.state."""
    return SimpleNamespace(app=SimpleNamespace(state=app_state))


class TestPoolCreationRetries:
    """A cold Neon database must be waited for, not given up on."""

    def test_succeeds_on_a_later_attempt(self, monkeypatch):
        """
        The production failure exactly: the first attempt times out while the
        database wakes, a later one succeeds.
        """
        calls = {"n": 0}

        async def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError("Authentication timed out")
            return _FakePool()

        monkeypatch.setattr(history.asyncpg, "create_pool", flaky)
        monkeypatch.setattr(history.asyncio, "sleep", _no_sleep)

        pool = asyncio.run(history.get_db_pool("postgresql://x", attempts=4, base_delay=0))
        assert isinstance(pool, _FakePool)
        assert calls["n"] == 3

    def test_a_timeout_is_retried_at_all(self, monkeypatch):
        """
        The specific defect. asyncpg's connect timeout is a TimeoutError, NOT
        an asyncpg.PostgresError, so the original narrow `except
        asyncpg.PostgresError` never ran for the failure that actually
        happened and the error escaped to a caller that swallowed it.
        """
        calls = {"n": 0}

        async def always_timeout(*args, **kwargs):
            calls["n"] += 1
            raise TimeoutError("Authentication timed out")

        monkeypatch.setattr(history.asyncpg, "create_pool", always_timeout)
        monkeypatch.setattr(history.asyncio, "sleep", _no_sleep)

        with pytest.raises(TimeoutError):
            asyncio.run(history.get_db_pool("postgresql://x", attempts=3, base_delay=0))
        assert calls["n"] == 3, "a timeout must be retried, not raised on sight"

    def test_gives_up_rather_than_hanging_forever(self, monkeypatch):
        """Retrying must be bounded; a patient is waiting on the request."""
        calls = {"n": 0}

        async def always_fail(*args, **kwargs):
            calls["n"] += 1
            raise OSError("connection refused")

        monkeypatch.setattr(history.asyncpg, "create_pool", always_fail)
        monkeypatch.setattr(history.asyncio, "sleep", _no_sleep)

        with pytest.raises(OSError):
            asyncio.run(history.get_db_pool("postgresql://x", attempts=2, base_delay=0))
        assert calls["n"] == 2


class TestLazyReinit:
    """A container that lost the startup race must recover."""

    def test_existing_pool_is_returned_untouched(self, monkeypatch):
        existing = _FakePool()

        async def must_not_run(*args, **kwargs):
            raise AssertionError("should not rebuild an existing pool")

        monkeypatch.setattr(history.asyncpg, "create_pool", must_not_run)
        got = asyncio.run(pool_dependency(_request(SimpleNamespace(db_pool=existing))))
        assert got is existing

    def test_none_after_failed_startup_is_rebuilt(self, monkeypatch):
        """db_pool present and None means the lifespan ran and failed."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://x")
        monkeypatch.setattr(history.asyncpg, "create_pool",
                            lambda *a, **k: _async_return(_FakePool()))

        state = SimpleNamespace(db_pool=None)
        got = asyncio.run(pool_dependency(_request(state)))
        assert isinstance(got, _FakePool)
        # Cached on state, so the next request does not rebuild it.
        assert state.db_pool is got

    def test_missing_attribute_never_builds_a_pool(self, monkeypatch):
        """
        The bug this fix introduced, caught before it shipped.

        A bare TestClient(app) never runs the lifespan, so app.state has no
        db_pool attribute at all. The first version treated that the same as a
        failed startup and happily connected - which pointed the entire test
        suite at the production database. A missing attribute is not a failure
        to recover from.
        """
        monkeypatch.setenv("DATABASE_URL", "postgresql://x")

        async def must_not_run(*args, **kwargs):
            raise AssertionError("must not connect when the lifespan never ran")

        monkeypatch.setattr(history.asyncpg, "create_pool", must_not_run)
        assert asyncio.run(pool_dependency(_request(SimpleNamespace()))) is None

    def test_no_database_url_is_not_an_error(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert asyncio.run(pool_dependency(_request(SimpleNamespace(db_pool=None)))) is None

    def test_a_failed_rebuild_returns_none_rather_than_raising(self, monkeypatch):
        """
        Persistence is never worth failing an analysis for.

        A patient waiting on their discharge summary must not get an error
        because the history table was unreachable.
        """
        monkeypatch.setenv("DATABASE_URL", "postgresql://x")

        async def always_fail(*args, **kwargs):
            raise TimeoutError("still asleep")

        monkeypatch.setattr(history.asyncpg, "create_pool", always_fail)
        monkeypatch.setattr(history.asyncio, "sleep", _no_sleep)
        assert asyncio.run(pool_dependency(_request(SimpleNamespace(db_pool=None)))) is None


async def _no_sleep(_seconds):
    """Skip real backoff delays so the suite stays fast."""
    return None


def _async_return(value):
    """Wrap a value in an awaitable, for monkeypatching async factories."""
    async def _inner():
        return value
    return _inner()


class TestHealthTellsTheTruth:
    """
    /health must not say "ok" while persistence is dead.

    This is the part that let the outage run for weeks. The fault WAS visible,
    buried in database.detail as "pool not initialised" - but monitoring reads
    `status`, humans read `status`, and status said ok.
    """

    @staticmethod
    def _health(app_state, database_url="postgresql://x"):
        """Call the health handler directly with a controlled app.state."""
        import os
        from unittest.mock import patch
        from dischargeiq.api.routes.health import health as health_check

        env = {"DATABASE_URL": database_url} if database_url else {}
        with patch.dict(os.environ, env, clear=False):
            if not database_url:
                os.environ.pop("DATABASE_URL", None)
            return asyncio.run(health_check(_request(app_state)))

    def test_degraded_when_the_pool_failed_at_startup(self):
        """db_pool present and None: the lifespan ran and lost the race."""
        body = self._health(SimpleNamespace(db_pool=None))
        assert body["status"] == "degraded"
        assert body["database"]["configured"] is True
        assert body["database"]["reachable"] is not True

    def test_degraded_reason_names_what_the_patient_loses(self):
        """
        "pool not initialised" tells an operator nothing actionable.

        The reason has to say that quiz scores and comprehension deltas stop
        being saved, because that is the consequence someone has to weigh.
        """
        body = self._health(SimpleNamespace(db_pool=None))
        reason = body.get("degraded_reason", "").lower()
        assert "comprehension" in reason
        assert "analysis still works" in reason

    def test_ok_when_no_database_is_configured(self):
        """Running without a database on purpose is not degraded."""
        body = self._health(SimpleNamespace(db_pool=None), database_url="")
        assert body["status"] == "ok"
        assert body["database"]["configured"] is False

    def test_ok_when_the_lifespan_never_ran(self):
        """
        A bare TestClient has no db_pool attribute at all.

        Reporting degraded there would fail every API test for a condition
        that exists only in the harness.
        """
        assert self._health(SimpleNamespace())["status"] == "ok"
