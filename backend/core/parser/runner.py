import json
import os
import subprocess
import sys
import tempfile

PARSER_TIMEOUT = 60  # seconds

# Minimal safe environment for parser subprocess execution.
# TODO: For production, run parsers inside a container or with seccomp/cgroups.
_SAFE_ENV = {
    'PATH': '/usr/bin:/bin',
    'PYTHONPATH': '',
}


def run_parser(parser_script: str, raw_input: str) -> dict:
    """
    Execute a parser script in an isolated subprocess.

    The script receives raw_input on stdin and must write a single
    canonical JSON object to stdout.
    """
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, prefix='isotopeiq_parser_'
    ) as tmp:
        tmp.write(parser_script)
        script_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            input=raw_input,
            capture_output=True,
            text=True,
            timeout=PARSER_TIMEOUT,
            env=_SAFE_ENV,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f'Parser exited with code {result.returncode}. stderr: {result.stderr[:500]}'
            )
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'Parser timed out after {PARSER_TIMEOUT} seconds')
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'Parser produced invalid JSON: {exc}')
    finally:
        os.unlink(script_path)
