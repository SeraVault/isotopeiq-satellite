from deepdiff import DeepDiff


def detect_drift(baseline: dict, current: dict) -> dict:
    """
    Return a serialisable diff between baseline and current canonical JSON.
    Returns an empty dict if there are no differences.
    """
    diff = DeepDiff(baseline, current, ignore_order=True, verbose_level=2)
    return diff.to_dict() if diff else {}
