"""
Cross-process run locks, backed by the shared Redis cache.

Used to prevent duplicate concurrent triggers of the same Policy/ScriptJob/
device pull — e.g. a double-clicked "Run Now" overlapping a Beat-scheduled
tick. `cache.add()` is atomic at the Redis level (SET ... NX), so this is
safe across multiple Gunicorn/Celery worker processes without any extra
locking primitive.
"""
from contextlib import contextmanager

from django.core.cache import cache


class AlreadyRunning(Exception):
    """Raised when a run is requested while a prior run holding the same key is still in flight."""


def try_acquire_run_lock(key: str, timeout: int) -> bool:
    """
    Attempt to acquire the named run lock.

    Returns True if acquired, False if another run already holds it.
    `timeout` is the lock's max lifetime in seconds — a safety net in case
    the holder dies without releasing it; should comfortably exceed the
    slowest expected run for whatever this key guards.
    """
    return cache.add(f'runlock:{key}', '1', timeout=timeout)


def release_run_lock(key: str) -> None:
    cache.delete(f'runlock:{key}')


@contextmanager
def run_lock(key: str, timeout: int):
    """
    Context manager form. Raises AlreadyRunning if the lock is held.

    Usage:
        with run_lock(f'policy:{policy_id}', timeout=900):
            ...

    Releases the lock on the way out regardless of success/failure, so a
    task that finishes well within `timeout` doesn't block the next run
    until expiry.
    """
    if not try_acquire_run_lock(key, timeout):
        raise AlreadyRunning(f'A run is already in progress for "{key}".')
    try:
        yield
    finally:
        release_run_lock(key)
