"""
Script template rendering.

Placeholders use {{VARIABLE_NAME}} syntax and are substituted at runtime
from the device and its credential record.  The raw script stored in the
database never contains real secrets — they are injected per-run.

Available placeholders
----------------------
Credential / auth
  {{USERNAME}}          Login username (credential or device inline)
  {{PASSWORD}}          Password (credential or device inline)
  {{PRIVATE_KEY}}       PEM private key (credential)
  {{TOKEN}}             API token (credential)

Elevation helpers (convenience wrappers around the credential)
  {{ELEVATE}}           Elevation method derived from credential type:
                          password     → sudo_pass
                          private_key  → sudo  (key-based, no password needed)
                          api_token    → none
                          (no cred)    → none
  {{ELEVATE_PASS}}      Same as {{PASSWORD}} — explicit alias for clarity in
                        scripts that use the priv() pattern

Device identity
  {{HOSTNAME}}          Device hostname field
  {{FQDN}}              Device FQDN field
  {{PORT}}              Device port
  {{DEVICE_TYPE}}       Device type (linux / windows / etc.)
  {{OS_TYPE}}           OS type
  {{CONNECTION_TYPE}}   Connection type (ssh / telnet / winrm / etc.)

Satellite / push
  {{SATELLITE_URL}}     Base URL of this Satellite server (from System Settings in the UI, falling back to SATELLITE_URL env var)
  {{PUSH_TOKEN}}        Device push token (for push-mode agents)
"""

import re

from django.conf import settings


def _get_satellite_url() -> str:
    """Return the satellite URL from the database System Settings, falling back
    to the SATELLITE_URL env var in case the DB is not yet available."""
    try:
        from apps.notifications.models import SystemSettings
        return SystemSettings.get().satellite_url
    except Exception:
        return getattr(settings, 'SATELLITE_URL', '')


def render_script(content: str, device) -> str:
    """Replace {{PLACEHOLDER}} tokens in *content* with values from *device*.

    Unknown placeholders are left as-is so the script author can see what
    was not resolved rather than silently receiving an empty string.
    """
    cred = getattr(device, 'credential', None)

    # Resolve username / password from credential FK, falling back to inline fields.
    username = (cred.username if cred else None) or getattr(device, 'username', '') or ''
    password = (cred.password if cred else None) or getattr(device, 'password', '') or ''
    private_key = (cred.private_key if cred else None) or getattr(device, 'ssh_private_key', '') or ''
    token = (cred.token if cred else None) or ''

    cred_type = cred.credential_type if cred else ''
    if cred_type == 'password':
        elevate = 'sudo_pass'
    elif cred_type == 'private_key':
        elevate = 'sudo'
    else:
        elevate = 'none'

    replacements = {
        'USERNAME':        username,
        'PASSWORD':        password,
        'PRIVATE_KEY':     private_key,
        'TOKEN':           token,
        'ELEVATE':         elevate,
        'ELEVATE_PASS':    password,
        'ENABLE_PASS':     password,
        'HOSTNAME':        getattr(device, 'hostname', ''),
        'FQDN':            getattr(device, 'fqdn', ''),
        'PORT':            str(getattr(device, 'port', '')),
        'DEVICE_TYPE':     getattr(device, 'device_type', ''),
        'OS_TYPE':         getattr(device, 'os_type', ''),
        'CONNECTION_TYPE': getattr(device, 'connection_type', ''),
        'SATELLITE_URL':   _get_satellite_url(),
        'PUSH_TOKEN':      str(getattr(device, 'push_token', '') or ''),
    }

    def _replace(match):
        key = match.group(1)
        return replacements.get(key, match.group(0))   # leave unknown as-is

    return re.sub(r'\{\{([A-Z0-9_]+)\}\}', _replace, content)
