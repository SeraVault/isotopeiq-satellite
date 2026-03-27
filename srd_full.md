IsotopeIQ Satellite
Software Requirements Document (SRD)

Version: 1.0
Date: March 2026

1. Executive Summary

IsotopeIQ Satellite is a device-agnostic configuration collection, analysis, and drift-detection platform.

The system connects to remote devices, executes collection scripts, gathers raw data, parses it into a canonical structure, establishes baselines, detects drift, and notifies users of changes.

The platform must support both:

Server-initiated collection (pull)
Device-initiated submission (push)

The system is conceptually similar to Tripwire, but is designed to be:

Device-agnostic
Script-driven
Canonical JSON based
Extensible across any OS or device type
2. Technology Stack
Backend
Django (API + Core platform)
PostgreSQL (primary database)
Celery (job execution)
Redis or RabbitMQ (Celery broker)
Frontend
Vue 3
Notifications
Syslog integration
3. Core Concepts
Concept	Description
Device	Any remotely accessible system
Script	Code that collects or parses data
Policy	Group of devices + scripts + schedule
Baseline	Last known good parsed state per device
Drift	Difference between baseline and new data
Job	Execution of a policy or script
4. High Level Workflow
Devices are defined and grouped into Policies.
Policies define:
Scripts to run
Schedule
Execution order
System runs jobs via Celery.
Raw data is collected and stored.
Parser scripts convert raw data into Canonical JSON.
Parsed output becomes the Device Baseline.
Future runs compare new parsed output vs baseline.
Drift generates UI alerts and Syslog messages.
5. Device Management
5.1 Device Requirements

Devices must support at least one connection method:

SSH
WinRM
HTTPS/API
Custom plugin (future)
5.2 Device Attributes
Name
Hostname / IP
Port
Device Type
OS Type
Tags
Assigned Credentials
6. Credentials Management

Credentials are stored securely and linked per device.

Supported credential types:

SSH username/password
SSH key
Windows credentials
API tokens

Scripts must automatically use device credentials.

7. Script System

Scripts are fully managed via UI.

7.1 Script Types
Collector Scripts (Remote)

Run on target devices to gather raw data.

Parser Scripts (Server)

Transform raw data → Canonical JSON.

Deployment Scripts (Remote)

Deploy collectors and schedule tasks on devices.

8. Policies (Device Groups)

Policies group devices and define automation.

8.1 Policy Includes
Devices
Scripts to run
Schedule configuration
8.2 Scheduling Options
Periodicity (cron-like)
Start time
Delay between devices (seconds)
9. Collection Mechanisms
9.1 Pull Model

Server connects and executes collectors.

9.2 Push Model

Device sends collected data to API endpoint.

10. Data Storage
10.1 Raw Data

Store full unmodified script output.

10.2 Parsed Data

Store canonical JSON output.

11. Baseline & Drift Detection

Baselines are managed per device.

Each device maintains its own baseline snapshot.

Workflow:

First successful run → baseline created
Subsequent runs → compare vs baseline
Differences → drift event generated
12. Canonical JSON Data Model (CRITICAL REQUIREMENT)

This is the most important architectural requirement.

12.1 Purpose

All devices must produce parsed output using the same canonical structure, regardless of OS or vendor.

Device types do NOT need to populate every section, but section names and attribute names must be consistent across all devices.

This guarantees cross-device comparison and reporting.

13. Canonical JSON Schema
13.1 Top Level Structure
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
13.2 Canonical Sections & Attributes
device
{
  "hostname": "",
  "fqdn": "",
  "device_type": "",
  "vendor": "",
  "model": ""
}
hardware
{
  "cpu_model": "",
  "cpu_cores": 0,
  "memory_gb": 0,
  "bios_version": "",
  "serial_number": "",
  "architecture": ""
}
os
{
  "name": "",
  "version": "",
  "build": "",
  "kernel": ""
}
network
{
  "interfaces": [
    {
      "name": "",
      "mac": "",
      "ipv4": [],
      "ipv6": []
    }
  ],
  "open_ports": []
}
users

Canonical user format (all OS must map to this):

{
  "username": "",
  "uid": "",
  "groups": [],
  "home": "",
  "shell": "",
  "disabled": false
}
groups
{
  "group_name": "",
  "gid": "",
  "members": []
}
installed_software (CRITICAL)

All OS/software managers must map to this format.

{
  "name": "",
  "version": "",
  "vendor": "",
  "install_date": "",
  "source": "apt|yum|rpm|msi|brew|manual"
}

Examples:

Windows Programs
Linux Packages
Mac Applications

All normalized into the SAME schema.

services
{
  "name": "",
  "status": "running|stopped",
  "startup": "enabled|disabled"
}
filesystem
{
  "mount": "",
  "type": "",
  "size_gb": 0,
  "free_gb": 0
}
security
{
  "firewall_enabled": true,
  "antivirus": "",
  "secure_boot": false
}
custom

Device-specific data not part of canonical model.

14. Notifications

Drift must trigger:

UI Alerts

Visible in dashboard.

Syslog Messages

External SIEM integration.

15. Job Monitoring & History
15.1 Job Types
Policy runs
Device runs
Parser runs
15.2 Job Status
Pending
Running
Success
Failed
Cancelled
15.3 Job Logs

Store:

stdout/stderr
errors
execution timeline
15.4 Job UI
Real-Time Monitor

Shows running jobs.

Job History

Filter by:

Device
Policy
Script
Status
Date
Job Detail View

Shows:

Raw data
Parsed data
Drift results
Logs
16. Retention Policies

Configurable retention for:

Raw data
Parsed data
Job history
Logs
17. Security Requirements
Role-based access control
Encrypted credentials
Audit logging
TLS for all communications