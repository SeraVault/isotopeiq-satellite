import json

from deepdiff import DeepDiff
from core.canonical import strip_volatile
from .volatile_utils import get_volatile_spec


def detect_drift(
    baseline: dict,
    current: dict,
    script_job_id: int | None = None,
) -> dict:
    """
    Return a serialisable diff between baseline and current canonical JSON.
    Volatile fields are stripped before comparison to suppress spurious drift.
    Pass script_job_id to apply job-scoped exclusion rules on top of globals.
    Returns an empty dict if there are no differences.
    """
    spec = get_volatile_spec(script_job_id)
    diff = DeepDiff(
        strip_volatile(baseline, spec),
        strip_volatile(current, spec),
        ignore_order=True,
        verbose_level=2,
    )
    return json.loads(diff.to_json()) if diff else {}
