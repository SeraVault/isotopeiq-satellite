"""
Audit logging middleware (SRD §17.3).

Records every mutating API request (POST/PUT/PATCH/DELETE) and any request
to a path under /api/ that modifies state, after the response is returned
(so the status code is available).

Read-only requests (GET/HEAD/OPTIONS) are not logged — they produce no
state change and would flood the audit table.

Login/logout events are captured separately via Django signals in signals.py.
"""
import logging

from .models import AuditLog

logger = logging.getLogger('audit')

_WRITE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def _get_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (
            request.method in _WRITE_METHODS
            and request.path.startswith('/api/')
            and hasattr(request, 'user')
            and request.user.is_authenticated
        ):
            self._record(request, response)

        return response

    @staticmethod
    def _record(request, response):
        method = request.method
        if method == 'DELETE':
            action = 'delete'
        elif method == 'POST':
            action = 'action' if _is_action_url(request.path) else 'create'
        else:
            action = 'update'

        resource_type, resource_id = _parse_path(request.path)

        entry = AuditLog(
            username=request.user.username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=_get_ip(request),
            method=method,
            path=request.path,
            status_code=response.status_code,
        )
        entry.save()

        logger.info(
            'AUDIT %s %s %s %s -> %s',
            request.user.username,
            method,
            request.path,
            resource_type,
            response.status_code,
        )


# ── helpers ────────────────────────────────────────────────────────────────

# DRF action URLs end with a word segment that is not a numeric PK:
# /api/policies/3/run/  /api/jobs/7/cancel/  /api/drift/2/acknowledge/
def _is_action_url(path: str) -> bool:
    parts = [p for p in path.rstrip('/').split('/') if p]
    return len(parts) >= 3 and not parts[-1].isdigit()


def _parse_path(path: str):
    """Return (resource_type, resource_id) from a DRF URL like /api/devices/5/."""
    parts = [p for p in path.strip('/').split('/') if p]
    # parts: ['api', 'devices', '5', ...]
    if len(parts) >= 2:
        resource_type = parts[1]
        resource_id = parts[2] if len(parts) >= 3 and parts[2].isdigit() else ''
        return resource_type, resource_id
    return '', ''
