from deepdiff import DeepDiff
from core.canonical import strip_volatile
from .volatile_utils import get_volatile_spec


def detect_drift(baseline: dict, current: dict) -> dict:
    """
    Return a serialisable diff between baseline and current canonical JSON.
    Volatile fields are stripped using the active DB rules before comparison
    so they do not generate spurious drift events.
    Returns an empty dict if there are no differences.
    """
    spec = get_volatile_spec()
    diff = DeepDiff(
        strip_volatile(baseline, spec),
        strip_volatile(current, spec),
        ignore_order=True,
        verbose_level=2,
    )
    return diff.to_dict() if diff else {}
