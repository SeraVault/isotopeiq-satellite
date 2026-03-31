"""
Validate the JSON output of an IsotopeIQ collector.

Usage:
    python validate_collector.py <path-to-output.json>

Exits 0 on success, 1 on validation failure.
"""
import json
import sys

if len(sys.argv) < 2:
    print("Usage: validate_collector.py <output.json>")
    sys.exit(1)

with open(sys.argv[1]) as f:
    data = json.load(f)

errors = []

# ── Required top-level keys ──────────────────────────────────────────────────
required_keys = [
    "device", "hardware", "os", "network", "users", "groups",
    "packages", "services", "filesystem", "security",
    "scheduled_tasks", "startup_items", "ssh_keys", "kernel_modules",
    "pci_devices", "storage_devices", "usb_devices",
    "listening_services", "firewall_rules", "sysctl",
    "certificates", "logging_targets",
]
for key in required_keys:
    if key not in data:
        errors.append("MISSING top-level key: {}".format(key))

# ── Fields that must be non-empty ────────────────────────────────────────────
for section, field in [
    ("device",   "hostname"),
    ("os",       "name"),
    ("hardware", "cpu_model"),
]:
    if not data.get(section, {}).get(field):
        errors.append("EMPTY {}.{}".format(section, field))

# ── Arrays that must be populated ────────────────────────────────────────────
# Note: services is intentionally excluded — bare containers have no init system
for key in ["packages", "users"]:
    if not data.get(key):
        errors.append("EMPTY array: {}".format(key))

# ── Package source must be a known value ─────────────────────────────────────
known_sources = {"deb", "rpm", "apk", "pacman", "snap", "flatpak", "brew", "pkgutil", "winget", "msi", "chocolatey"}
for pkg in data.get("packages", []):
    if pkg.get("source") not in known_sources:
        errors.append("Unknown package source: {}".format(pkg.get("source")))
        break

# ── No unexpected _collection_errors ─────────────────────────────────────────
# Sections that may legitimately fail in a minimal container environment:
# - no root → sysctl, firewall, ssh_keys, security fail
# - no init system → services, scheduled_tasks fail
# - no hardware access → pci_devices, storage_devices, usb_devices fail
# - no network tools → listening_services may fail
ignorable = {
    "certificates", "firewall_rules", "sysctl", "ssh_keys",
    "security", "pci_devices", "storage_devices", "usb_devices",
    "kernel_modules", "listening_services", "services", "scheduled_tasks",
    "startup_items", "filesystem",
}
for k, v in data.get("_collection_errors", {}).items():
    if k not in ignorable:
        errors.append("COLLECTION ERROR in {}: {}".format(k, v))

# ── Summary ───────────────────────────────────────────────────────────────────
print("packages={}  services={}  users={}  os={} {}".format(
    len(data.get("packages", [])),
    len(data.get("services", [])),
    len(data.get("users", [])),
    data.get("os", {}).get("name", ""),
    data.get("os", {}).get("version", ""),
))

if errors:
    print("FAILURES:")
    for e in errors:
        print("  x " + e)
    sys.exit(1)

print("All checks passed.")
