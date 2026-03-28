from deepdiff import DeepDiff
from core.canonical import strip_volatile


def detect_drift(baseline: dict, current: dict) -> dict:
    """
    Return a serialisable diff between baseline and current canonical JSON.
    Volatile fields (timestamps, utilisation, runtime state) are stripped
    before comparison so they do not generate spurious drift events.
    Returns an empty dict if there are no differences.
    """
    diff = DeepDiff(
        strip_volatile(baseline),
        strip_volatile(current),
        ignore_order=True,
        verbose_level=2,
    )
    return diff.to_dict() if diff else {}
