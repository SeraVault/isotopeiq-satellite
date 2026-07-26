"""
Validate the JSON output of a baseline exporter (schema 1.2.0, the
ansible-baseline format).

Usage:
    python validate_baseline.py <path-to-output.json>

Exits 0 on success, 1 on validation failure.
"""
import json
import sys

if len(sys.argv) < 2:
    print("Usage: validate_baseline.py <output.json>")
    sys.exit(1)

with open(sys.argv[1]) as f:
    data = json.load(f)

errors = []

# ── Required top-level keys and their types ──────────────────────────────────
expected = {
    "applications": list,
    "collection": dict,
    "firewall_rules": list,
    "groups": list,
    "hardware": dict,
    "host": dict,
    "network": dict,
    "os": dict,
    "patches": list,
    "schema_version": str,
    "security": dict,
    "services": list,
    "startup_items": list,
    "users": list,
}
for key, typ in expected.items():
    if key not in data:
        errors.append("MISSING top-level key: {}".format(key))
    elif not isinstance(data[key], typ):
        errors.append("WRONG TYPE {}: expected {}, got {}".format(
            key, typ.__name__, type(data[key]).__name__))

for key in data:
    if key not in expected:
        errors.append("UNEXPECTED top-level key: {}".format(key))

if data.get("schema_version") != "1.2.0":
    errors.append("schema_version is {!r}, expected '1.2.0'".format(
        data.get("schema_version")))

# ── Fields that must be non-empty ────────────────────────────────────────────
for section, field in [
    ("host", "hostname"),
    ("host", "identifier"),
    ("host", "platform"),
    ("os", "name"),
    ("hardware", "cpu"),
    ("collection", "collected_at"),
    ("collection", "collector"),
]:
    if not data.get(section, {}).get(field):
        errors.append("EMPTY {}.{}".format(section, field))

# ── Arrays that must be populated everywhere (even bare containers) ──────────
for key in ["applications", "users", "groups"]:
    if not data.get(key):
        errors.append("EMPTY array: {}".format(key))

# ── Per-entry shape checks ───────────────────────────────────────────────────
entry_fields = {
    "applications": {"architecture", "name", "source", "vendor", "version"},
    "firewall_rules": {"action", "application", "direction", "enabled", "id",
                       "local_ports", "name", "profiles", "protocol", "raw",
                       "remote_ports", "service", "source"},
    "groups": {"id", "members", "name"},
    "patches": {"description", "id"},
    "services": {"display_name", "name", "path", "run_as", "source",
                 "startup"},
    "startup_items": {"command", "location", "name", "scope"},
    "users": {"admin", "description", "enabled", "home", "id", "name",
              "shell"},
}
for section, fields in entry_fields.items():
    for i, entry in enumerate(data.get(section, [])):
        if not isinstance(entry, dict) or set(entry) != fields:
            errors.append("BAD ENTRY {}[{}]: keys {}".format(
                section, i, sorted(entry) if isinstance(entry, dict)
                else type(entry).__name__))
            break

security = data.get("security", {})
if set(security) != {"file_integrity", "settings"}:
    errors.append("security keys: {}".format(sorted(security)))
for i, s in enumerate(security.get("settings", [])):
    if not isinstance(s, dict) or set(s) != {"key", "value"}:
        errors.append("BAD ENTRY security.settings[{}]".format(i))
        break

network = data.get("network", {})
if set(network) != {"dns_servers", "interfaces"}:
    errors.append("network keys: {}".format(sorted(network)))

# ── Report ───────────────────────────────────────────────────────────────────
if errors:
    print("VALIDATION FAILED:")
    for e in errors:
        print("  - " + e)
    sys.exit(1)

print("Validation passed: {} applications, {} users, {} services, "
      "{} firewall rules, {} security settings".format(
          len(data["applications"]), len(data["users"]),
          len(data["services"]), len(data["firewall_rules"]),
          len(data["security"]["settings"])))
