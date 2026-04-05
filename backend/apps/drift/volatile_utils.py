"""
Utilities for building and caching the volatile-field spec from the database.

The spec is rebuilt from `VolatileFieldRule` rows at most once per
CACHE_TTL seconds.  Call `invalidate_spec_cache()` after any write to
force an immediate rebuild on the next drift comparison.
"""
import time

_spec_cache: dict | None = None
_spec_cache_ts: float = 0.0
CACHE_TTL = 60  # seconds


def build_spec_from_rules(rules) -> dict:
    """
    Convert an iterable of VolatileFieldRule instances into the
    VOLATILE_FIELDS-compatible dict consumed by core.canonical.strip_volatile.
    """
    spec: dict = {}
    for rule in rules:
        s = spec.setdefault(rule.section, {})
        if rule.spec_type == 'section_field':
            s.setdefault('fields', set()).add(rule.field_name)
        elif rule.spec_type == 'item_field':
            s.setdefault('items', set()).add(rule.field_name)
        elif rule.spec_type == 'nested_field':
            s.setdefault('nested', {}).setdefault(rule.aux, set()).add(rule.field_name)
        elif rule.spec_type == 'exclude_key':
            key_field = rule.aux or 'key'
            if 'exclude_keys' not in s:
                s['exclude_keys'] = {'key_field': key_field, 'values': set()}
            s['exclude_keys']['values'].add(rule.field_name)
        elif rule.spec_type == 'exclude_section':
            s['exclude_section'] = True
        elif rule.spec_type == 'key_prefix':
            key_field = rule.aux or 'key'
            if 'exclude_key_prefixes' not in s:
                s['exclude_key_prefixes'] = {'key_field': key_field, 'prefixes': set()}
            s['exclude_key_prefixes']['prefixes'].add(rule.field_name)
    return spec


def get_volatile_spec() -> dict:
    """Return the cached volatile spec, refreshing from DB if stale."""
    global _spec_cache, _spec_cache_ts
    now = time.monotonic()
    if _spec_cache is None or (now - _spec_cache_ts) > CACHE_TTL:
        from .models import VolatileFieldRule
        rules = list(VolatileFieldRule.objects.filter(is_active=True))
        _spec_cache = build_spec_from_rules(rules)
        _spec_cache_ts = now
    return _spec_cache


def invalidate_spec_cache() -> None:
    """Force the next call to get_volatile_spec() to re-query the database."""
    global _spec_cache
    _spec_cache = None
