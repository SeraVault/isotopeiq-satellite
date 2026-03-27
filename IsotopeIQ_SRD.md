# IsotopeIQ Satellite

## Software Requirements Document (SRD)

**Version:** 1.0\
**Date:** March 2026

------------------------------------------------------------------------

# 1. Executive Summary

IsotopeIQ Satellite is a device‑agnostic configuration collection,
analysis, and drift‑detection platform.

The system connects to remote devices, executes collection scripts,
gathers raw data, parses it into a canonical structure, establishes
baselines, detects drift, and notifies users of changes.

The platform supports: - Server‑initiated collection (pull) -
Device‑initiated submission (push)

Conceptually similar to Tripwire, but designed to be: -
Device‑agnostic - Script‑driven - Canonical JSON based - Extensible
across any OS or device type

------------------------------------------------------------------------

# 2. Technology Stack

## Backend

-   Django
-   PostgreSQL
-   Celery
-   Redis or RabbitMQ

## Frontend

-   Vue 3

## Notifications

-   Syslog

------------------------------------------------------------------------

# 3. Core Concepts

  Concept    Description
  ---------- ------------------------------------------
  Device     Any remotely accessible system
  Script     Code that collects or parses data
  Policy     Group of devices + scripts + schedule
  Baseline   Last known good parsed state per device
  Drift      Difference between baseline and new data
  Job        Execution of a policy or script

------------------------------------------------------------------------

# 4. Workflow

1.  Devices grouped into Policies
2.  Policies define scripts + schedules
3.  Celery executes jobs
4.  Raw data stored
5.  Parsed to Canonical JSON
6.  Baseline created per device
7.  Future runs detect drift
8.  UI + Syslog notifications

------------------------------------------------------------------------

# 5. Canonical JSON Requirement (CRITICAL)

All parsed outputs MUST use the same canonical JSON structure across all
device types.

Not all devices must populate all sections, but: - Section names must be
identical - Attribute names must be identical - Parsed output becomes
the device baseline

------------------------------------------------------------------------

# 6. Canonical Top-Level Schema

``` json
{
  "device": {},
  "hardware": {},
  "os": {},
  "network": {},
  "users": [],
  "groups": [],
  "installed_software": [],
  "services": [],
  "packages": [],
  "filesystem": [],
  "security": {},
  "custom": {}
}
```

------------------------------------------------------------------------

# 7. Installed Software Canonical Format

``` json
{
  "name": "",
  "version": "",
  "vendor": "",
  "install_date": "",
  "source": "apt|yum|rpm|msi|brew|manual"
}
```

------------------------------------------------------------------------

# 8. Baselines

Baselines are: - Managed per device - Derived from parsed output - Used
for drift comparison

------------------------------------------------------------------------

# 9. Drift Detection

Drift triggers: - UI alerts - Syslog notifications

------------------------------------------------------------------------

# 10. Job Monitoring

UI must provide: - Real‑time job monitor - Job history - Logs - Raw +
parsed data view

------------------------------------------------------------------------

# END
