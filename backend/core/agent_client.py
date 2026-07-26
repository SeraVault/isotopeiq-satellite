"""
Shared HTTP client for talking to IsotopeIQ agents (GET /collect, POST /run).

Centralizes what was previously copy-pasted across jobs/tasks.py and
scripts/tasks.py: URL construction, the X-Agent-Secret header, a response
size cap (a misbehaving/malicious agent script can otherwise return an
unbounded amount of output and balloon worker memory), and retry-with-
backoff on transient network errors only — never on a successful HTTP
response, even an error one, since an agent returning 403/500 won't be
fixed by asking again.
"""
import json
import logging
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # seconds per attempt

# Cap how much of an agent's response we'll hold in memory. 16 MiB is
# generously larger than any real canonical-JSON snapshot or script output
# is expected to be; a response that exceeds this is far more likely to be
# a runaway/misbehaving script than legitimate data.
MAX_RESPONSE_BYTES = 16 * 1024 * 1024

# Retry budget for transient errors (connection refused, DNS hiccup, etc).
# Kept small and fast — these calls already run inside a Celery task with
# its own hard time limit, so retries must not eat into that budget by much.
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 2  # seconds: 2, 4 (then give up)


class AgentError(Exception):
    """Raised for any agent communication failure (network or protocol)."""


def _agent_secret() -> str:
    try:
        from apps.notifications.models import SystemSettings
        return SystemSettings.get().agent_secret or ''
    except Exception:
        return ''


def _read_capped(resp) -> bytes:
    """Read up to MAX_RESPONSE_BYTES+1 from resp; raise if the body is larger."""
    data = resp.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise AgentError(
            'Agent response exceeded {0} bytes; aborting read.'.format(MAX_RESPONSE_BYTES)
        )
    return data


def _request(req, timeout: int) -> bytes:
    """
    Perform one HTTP request with retry-with-backoff on transient errors.

    Retries on urllib.error.URLError (covers connection refused, DNS
    failure, timeout) — these are the cases where trying again shortly
    after has a real chance of succeeding. Does NOT retry on HTTPError
    (the agent responded, just with a non-2xx status) since that's a
    protocol-level outcome a retry won't change.
    """
    last_exc = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — internal agent call
                return _read_capped(resp)
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS:
                backoff = RETRY_BACKOFF_BASE * attempt
                logger.warning(
                    'Agent request failed (attempt %d/%d): %s — retrying in %ds.',
                    attempt, RETRY_ATTEMPTS, exc, backoff,
                )
                time.sleep(backoff)
    raise last_exc


def collect(device, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """GET /collect from the agent on `device` and return the parsed canonical JSON."""
    port = device.agent_port or 9322
    url = 'http://{host}:{port}/collect'.format(host=device.hostname, port=port)
    req = urllib.request.Request(url)  # nosec — internal network call to a known agent endpoint
    secret = _agent_secret()
    if secret:
        req.add_header('X-Agent-Secret', secret)

    try:
        raw = _request(req, timeout)
    except urllib.error.URLError as exc:
        raise AgentError('Agent unreachable at {0}: {1}'.format(url, exc)) from exc

    text = raw.decode('utf-8')
    return text, json.loads(text)


def run_script(device, script_content: str, language: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """POST a script to the agent's /run endpoint and return the decoded JSON result."""
    port = device.agent_port or 9322
    url = 'http://{host}:{port}/run'.format(host=device.hostname, port=port)
    payload = json.dumps({'script': script_content, 'language': language}).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    secret = _agent_secret()
    if secret:
        headers['X-Agent-Secret'] = secret
    req = urllib.request.Request(url, data=payload, headers=headers)

    try:
        raw = _request(req, timeout)
    except urllib.error.URLError as exc:
        raise AgentError('Agent unreachable at {0}: {1}'.format(url, exc)) from exc

    return json.loads(raw.decode('utf-8'))
