"""
Utilities for building and caching the volatile-field spec from the database.

Global rules (script_job=None) are cached for CACHE_TTL seconds.
Job-scoped rules are fetched fresh each time and merged on top of globals,
so the final spec is: global rules + any rules scoped to the given ScriptJob.

Call invalidate_spec_cache() after any write to force an immediate rebuild.
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
            s.setdefault('nested', {}) \
             .setdefault(rule.aux, set()) \
             .add(rule.field_name)
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
                s['exclude_key_prefixes'] = {
                    'key_field': key_field, 'prefixes': set(),
                }
            s['exclude_key_prefixes']['prefixes'].add(rule.field_name)
    return spec


def _merge_specs(base: dict, overlay: dict) -> dict:
    """Merge overlay spec on top of base, combining sets."""
    merged = {}
    for section in set(base) | set(overlay):
        b = base.get(section, {})
        o = overlay.get(section, {})
        s: dict = {}
        if b.get('exclude_section') or o.get('exclude_section'):
            s['exclude_section'] = True
        for key in ('fields', 'items'):
            combined = b.get(key, set()) | o.get(key, set())
            if combined:
                s[key] = combined
        nested: dict = {}
        for arr, flds in b.get('nested', {}).items():
            nested.setdefault(arr, set()).update(flds)
        for arr, flds in o.get('nested', {}).items():
            nested.setdefault(arr, set()).update(flds)
        if nested:
            s['nested'] = nested
        for attr in ('exclude_keys', 'exclude_key_prefixes'):
            bv = b.get(attr)
            ov = o.get(attr)
            if bv or ov:
                key_field = (bv or ov)['key_field']
                values_key = 'values' if attr == 'exclude_keys' else 'prefixes'
                combined = (
                    (bv or {}).get(values_key, set())
                    | (ov or {}).get(values_key, set())
                )
                s[attr] = {'key_field': key_field, values_key: combined}
        merged[section] = s
    return merged


def _get_global_spec() -> dict:
    """Return cached global spec (script_job=None rules)."""
    global _spec_cache, _spec_cache_ts
    now = time.monotonic()
    if _spec_cache is None or (now - _spec_cache_ts) > CACHE_TTL:
        from .models import VolatileFieldRule
        rules = list(
            VolatileFieldRule.objects.filter(
                is_active=True, script_job__isnull=True,
            )
        )
        _spec_cache = build_spec_from_rules(rules)
        _spec_cache_ts = now
    return _spec_cache


def get_volatile_spec(script_job_id: int | None = None) -> dict:
    """
    Return the effective volatile spec for a drift comparison.

    When script_job_id is given the result is global rules merged with any
    rules scoped to that ScriptJob.  When None only global rules are returned.
    """
    global_spec = _get_global_spec()
    if script_job_id is None:
        return global_spec
    from .models import VolatileFieldRule
    scoped_rules = list(
        VolatileFieldRule.objects.filter(
            is_active=True, script_job_id=script_job_id,
        )
    )
    if not scoped_rules:
        return global_spec
    return _merge_specs(global_spec, build_spec_from_rules(scoped_rules))


def invalidate_spec_cache() -> None:
    """Force the next call to get_volatile_spec() to re-query the database."""
    global _spec_cache
    _spec_cache = None
