import json

from core.canonical import CANONICAL_EMPTY

PARSER_TIMEOUT = 60  # seconds


def run_parser(parser_script: str, raw_input: str) -> dict:
    """
    Execute a parser script in an isolated namespace.

    The script has two pre-assigned variables:
      result  - str  - the raw output from the collection script
      output  - dict - a copy of CANONICAL_EMPTY to populate

    After the script runs, `output` is returned as the canonical dict.

    Example parser:
        for line in result.splitlines():
            if line.startswith('hostname'):
                output['device']['hostname'] = line.split()[-1]
    """
    namespace = {
        'result': raw_input,
        'output': {k: (v.copy() if isinstance(v, dict) else list(v))
                   for k, v in CANONICAL_EMPTY.items()},
    }

    try:
        exec(parser_script, namespace, namespace)  # noqa: S102
    except Exception as exc:
        raise RuntimeError(f'Parser error: {exc}') from exc

    parsed = namespace['output']
    if not isinstance(parsed, dict):
        raise RuntimeError('Parser must leave `output` as a dict.')
    return parsed
