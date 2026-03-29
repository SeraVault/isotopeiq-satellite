# IsotopeIQ Satellite — User Guide

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Navigation](#navigation)
4. [Dashboard](#dashboard)
5. [Devices](#devices)
6. [Credentials](#credentials)
7. [Scripts](#scripts)
8. [Policies](#policies)
9. [Job Monitor](#job-monitor)
10. [Drift](#drift)
11. [Baselines](#baselines)
12. [Audit Log](#audit-log)
13. [Retention](#retention)
14. [Concepts & Glossary](#concepts--glossary)

---

## Overview

IsotopeIQ Satellite is a configuration collection and drift detection platform. It connects to managed devices, collects their configuration state, stores it as a structured baseline, then continuously compares live collections against that baseline to surface drift — unexpected configuration changes.

**Core workflow:**

```
Devices → Scripts → Policies → Jobs → Baselines → Drift Detection
```

1. Add your **devices** and **credentials**
2. Write or import **collection and parser scripts**
3. Create a **policy** that ties devices, scripts, and a schedule together
4. Policies run as **jobs** — raw output is collected, parsed, and stored
5. Each successful parse updates the device **baseline**
6. If the new baseline differs from the previous one, a **drift event** is raised

---

## Getting Started

### Logging In

Navigate to the Satellite URL and log in with your username and password. Tokens are stored in your browser session and refreshed automatically.

### Recommended Setup Order

1. **Credentials** — Create SSH keys or passwords before adding devices
2. **Devices** — Register the hosts you want to monitor
3. **Scripts** — Upload or write your collection and parser scripts
4. **Policies** — Create a policy that combines devices + scripts + a schedule
5. **Run** — Trigger a manual run to validate everything, then let the schedule take over

---

## Navigation

The left sidebar organises the application into sections:

| Section | Views |
|---|---|
| Overview | Dashboard |
| Infrastructure | Devices, Policies, Scripts |
| Operations | Job Monitor, Drift, Baselines |
| System | Audit Log, Retention |

**Job Monitor** and **Drift** show live badge counts — the number of running jobs and unresolved drift events respectively.

The sidebar can be collapsed to a narrow icon rail by clicking the toggle at the top.

---

## Dashboard

The Dashboard gives a real-time snapshot of the system.

### Stat Cards

| Card | What it shows |
|---|---|
| Managed Devices | Total registered devices |
| Active Policies | Policies currently enabled |
| Running Jobs | Jobs currently executing |
| Unresolved Drift | Drift events not yet acknowledged |

### Panels

**Drift Alerts** — The 10 most recent unresolved drift events, with device name, status, detection time, and a link to review the diff. Click *View all* to go to the full Drift view.

**Recent Jobs** — The last 20 jobs, paginated 5 at a time. Shows device, policy, status, and start time. Click *View all* to go to the Job Monitor.

**Last Scanned** — The 6 stalest baselines, with a freshness indicator:
- Green — collected today
- Blue — collected within 7 days
- Orange — collected within 30 days
- Red — older than 30 days

**Recent Job Results** — Progress bars breaking down the last batch of jobs by status (success, failed, running, pending, cancelled).

**Quick Actions** — Shortcuts to Add Device, New Policy, Review Drift, View Baselines, and View All Jobs.

---

## Devices

*Infrastructure → Devices*

Devices represent any host, appliance, or network node that Satellite will collect configuration data from.

### Viewing Devices

The devices table shows name, hostname, device type, OS type, connection method, and active status. Use the filter bar to narrow by:
- Free-text search (name, hostname, FQDN)
- OS type (Linux, Windows, macOS, Network)
- Connection type (SSH, WinRM, HTTPS, Push)
- Active status

Click any row to open the **Device Viewer**, which shows device details and its most recent baseline data.

### Adding a Device

Click **Add Device** and fill in:

| Field | Notes |
|---|---|
| Name | Human-readable label |
| Hostname / IP | Used for the connection |
| FQDN | Optional; used if hostname is a short name |
| Port | Defaults based on connection type |
| Device Type | Linux, Windows, macOS, Network Device, Other |
| OS Type | Used to match compatible scripts |
| Connection Type | SSH, WinRM, HTTPS/API, or Push |
| Credential | Select a saved credential (recommended) |
| SSH Host Key | Paste to pin the host key and prevent MITM on first connect |
| Tags | Comma-separated; used for grouping and filtering |
| Notes | Free text for documentation |
| Active | Uncheck to exclude this device from policy runs |

**Inline credentials** — If you haven't created a credential yet, you can enter a username and password directly on the device form as a one-off.

#### Testing the Connection

Before saving, click **Test Connection** to verify Satellite can reach the device. For SSH and WinRM connections this also caches the host key. The test result is shown inline.

### Editing and Deleting Devices

Use the **pencil** icon to edit or the **bin** icon to delete. Deleting a device will remove it from all policies. A confirmation dialog is shown before deletion.

### Collecting From a Device

Click the **Collect** button on a device row to trigger an immediate collection. If multiple policies are assigned to the device, a picker will appear to choose which policy to run.

### Push Devices

Devices configured with the **Push** connection type do not get polled. Instead they call `POST /api/push/` with a push token and pre-collected JSON. The push token is displayed on the device detail.

---

## Credentials

*Infrastructure → Devices → Credentials tab*

Credentials are stored encrypted and reused across multiple devices.

### Credential Types

| Type | Fields |
|---|---|
| SSH Password | Username, Password |
| SSH Key | Username, PEM private key |
| Windows / WinRM | Username, Password |
| API Token | Bearer token (for HTTPS devices) |

### Adding a Credential

Click **Add Credential**, select the type, and fill in the required fields. Passwords and private keys are encrypted at rest and never returned to the UI after saving — leave the field blank when editing to keep the existing value.

---

## Scripts

*Infrastructure → Scripts*

Scripts are the executable units that perform collection and parsing. There are three types:

| Type | Runs on | Purpose |
|---|---|---|
| Collection | Remote device (via SSH/WinRM) | Gather raw configuration data and write it to stdout |
| Parser | Satellite server | Receive raw output via stdin, emit canonical JSON to stdout |
| Deployment | Remote device | Push remediation or hardening changes after collection |

### Collection Profiles

A **Collection Profile** bundles a collection script and a parser script into a versioned, distributable unit. This is the recommended way to manage scripts — one profile per OS family or device type.

Profiles are listed in the **Collection Profiles** tab. Columns: Name, Target OS, Version, scripts assigned, and active status.

#### Creating a Profile

1. Click **New Collection Profile**
2. Fill in the metadata: Name, Target OS, Version, Description
3. Write or paste your **Collection** script in the Collection tab
4. Write or paste your **Parser** script in the Parser tab
5. Optionally add a **Deployment** script
6. Click **Save**

#### Testing a Profile

In the profile editor:

1. Set **Test Device** to a real device in your inventory
2. Click **Run Collector** — Satellite connects to the device and captures raw output
3. Switch to the **Parser** tab
4. Click **Run Parser** — Satellite runs the parser against the captured raw output
5. Inspect the results in the output panels on the right

The parsed output must be valid canonical JSON. Errors are shown inline.

### Script Editor

The editor includes:
- Syntax highlighting (Python, Shell, PowerShell, VBScript, SQL)
- Line numbers and code folding
- Bracket matching and auto-indent
- Undo history

#### Substitution Placeholders

Scripts can reference `{{SATELLITE_URL}}` to receive the Satellite server address at runtime.

### Individual Scripts

The **Scripts** tab lists scripts outside of profiles. You can create standalone scripts and assign them to policies independently. Useful for deployment scripts that are shared across multiple profiles.

---

## Policies

*Infrastructure → Policies*

A Policy ties together devices, scripts, and a schedule to create an automated collection workflow.

### Policy Components

| Component | Required | Description |
|---|---|---|
| Name | Yes | Shown in job monitor and notifications |
| Collection Script | Yes | What to run on the device |
| Parser Script | Yes | How to turn raw output into canonical JSON |
| Deployment Script | No | Optional remediation/hardening script |
| Devices | Yes | One or more devices to target |
| Schedule | Yes | When to run |
| Active | — | Uncheck to pause without deleting |

### Schedule Options

| Frequency | Options |
|---|---|
| Hourly | Minute (0–59) |
| Daily | Hour (0–23) and minute |
| Weekly | Day(s) of week + hour + minute |
| Monthly | Day of month (1–28) + hour + minute |
| Custom | Raw cron expression |

A human-readable summary of the schedule is shown as you build it (e.g., *"Every Monday and Wednesday at 09:30 UTC"*).

### Device Picker

The device picker within the policy form is searchable. Type to filter by name, hostname, or FQDN. Check boxes to select devices. All selected devices are listed below with the option to remove individuals.

### Running a Policy Manually

Click **Run Now** on the policy row to trigger an immediate execution. Each device in the policy will get its own job. Watch progress in the [Job Monitor](#job-monitor).

### Deployment Scripts

Click **Deploy Now** on a policy row to push the policy's deployment script to all assigned devices. A confirmation dialog prevents accidental deployment. The deployment runs as a separate job.

---

## Job Monitor

*Operations → Job Monitor*

The Job Monitor shows all collection job executions — historical and in-flight.

### Filtering

Filter by device, policy, status, and/or date range. Click **Refresh** to reload with the current filters.

| Status | Meaning |
|---|---|
| pending | Queued, not yet started |
| running | Currently executing |
| success | Completed without errors, no drift |
| partial | Some devices succeeded, some failed |
| failed | Execution error or parse failure |
| cancelled | Manually cancelled |

### Job Detail

Click **Details** on any job row to open the full detail view:

- **Status and timestamps** for each device result
- **Error message** if the job failed
- **Raw Output** — the literal stdout from the collection script
- **Parsed Output** — the canonical JSON produced by the parser
- **Drift Detected** — if drift was found, the diff is shown inline

### Cancelling a Job

Running or pending jobs show a **Cancel** button. A confirmation dialog is shown. Cancellation is best-effort — if the job is mid-execution on a remote device, the remote script may have already completed.

---

## Drift

*Operations → Drift*

Drift events are raised when a job's parsed output differs from the established baseline for that device.

### Drift Statuses

| Status | Meaning |
|---|---|
| new | Unreviewed drift, requires attention |
| acknowledged | Reviewed and accepted, pending resolution |
| resolved | Baseline has been updated or drift no longer present |

### Filtering

Filter by device or status. Click **Clear** to reset filters.

### Reviewing Drift

Click **View Diff** to open the diff viewer for a drift event.

#### Diff Viewer

The diff viewer shows:

- **Stats bar** — counts of added, removed, and changed configuration items
- **Summary cards** — side-by-side comparison of key fields for device info, hardware, OS, and security
- **Section panels** — one expandable panel per canonical schema section that has changes; sections without changes are collapsed
  - Each panel shows changed rows as a before/after table
  - Added items are highlighted green, removed items red, changed items orange

#### Hide Volatile Fields

Check **Hide volatile fields** to suppress expected transient fields (timestamps, process IDs, ephemeral data) that would otherwise create noise. This is enabled by default.

### Acknowledging Drift

Click **Acknowledge** on a new drift event (or from within the diff viewer). Enter a reason in the text field and click **Submit**. The event moves to *acknowledged* status and your username is recorded.

Drift is automatically resolved on the next successful collection where no differences are found.

---

## Baselines

*Operations → Baselines*

A Baseline is a point-in-time snapshot of a device's configuration in canonical JSON format. It is updated every time a policy job completes successfully.

### Viewing Baselines

The baselines table shows device name, when the baseline was established, and which user or process established it. Filter by device using the dropdown.

### Baseline Viewer

Click **View Data** to open the full baseline viewer for a device. The viewer is structured as:

- **Summary cards** — Device info, hardware, OS version, and security posture at a glance
- **Expandable sections** — One panel per schema section:

| Section | Contents |
|---|---|
| Network | Interfaces, routes, hosts file |
| Users | Local user accounts (searchable) |
| Groups | Local groups |
| Packages | Installed packages (searchable) |
| Services | System services with status (running/stopped/disabled) |
| Filesystem | Mount points and disk usage |
| Listening Services | Open ports and owning processes |
| Firewall Rules | Chains, protocols, source/destination, actions |
| SSH Authorized Keys | Public keys per user |
| SSH Config | SSH daemon configuration |
| Scheduled Tasks | Cron jobs and scheduled tasks |
| Kernel Modules | Loaded kernel modules |
| System Parameters | sysctl / kernel parameters |
| Certificates | Installed certificates and expiry |

---

## Audit Log

*System → Audit Log*

The Audit Log records every significant action taken through the API.

### Columns

| Column | Notes |
|---|---|
| Timestamp | When the action occurred |
| User | Username who made the request |
| Action | login, logout, create, update, delete, action |
| Resource | Type and ID of the affected object |
| Path | HTTP method and URL path |
| Status Code | HTTP response code (green 2xx, orange 4xx, red 5xx) |
| IP Address | Source IP of the request |

### Filtering

Filter by username, action type, resource type, and/or date range. Click **Search** to apply, **Clear** to reset.

---

## Retention

*System → Retention*

Configure how long different categories of data are kept. Pruning runs automatically at **03:00 UTC daily**.

| Setting | Default | Description |
|---|---|---|
| Raw Data | 90 days | Raw stdout from collection scripts |
| Parsed Data | 365 days | Canonical JSON results from parser runs |
| Job History | 180 days | Job metadata and status records |
| Log / Error Messages | 90 days | Error output and diagnostics |

Set any value to **0** to retain data indefinitely. Click **Save** to apply changes.

---

## Concepts & Glossary

**Canonical JSON** — A normalised, schema-validated JSON document produced by a parser script. All canonical documents share the same top-level sections regardless of device OS, making cross-device and cross-time comparison possible.

**Collection Profile** — A versioned bundle of a collection script and a parser script, targeted at a specific OS family.

**Credential** — Stored authentication material (SSH key, password, API token) used to connect to devices. Encrypted at rest.

**Deployment Script** — An optional script pushed to a device to apply remediation or a golden configuration. Assigned to a policy and triggered explicitly via *Deploy Now* or automatically when auto-remediation is enabled.

**Device** — A managed host, appliance, or network node. Devices are collected from using either a pull model (Satellite connects) or a push model (device calls Satellite).

**Drift** — A detected difference between a device's current configuration and its established baseline.

**Drift Event** — A record created when drift is detected. Has a lifecycle: *new → acknowledged → resolved*.

**Baseline** — The most recent successful canonical configuration snapshot for a device. Updated on each successful job.

**Job** — A single execution of a policy against one device. Captures collection, parsing, baseline comparison, and drift detection as a unit.

**Parser Script** — A server-side script that receives raw collection output via stdin and must write valid canonical JSON to stdout.

**Policy** — The main scheduling unit. Binds one or more devices to a collection profile (or individual scripts) and defines when collection should run.

**Push Token** — A per-device secret used by push-mode devices to authenticate when calling `POST /api/push/`.

**Volatile Fields** — Configuration fields that change frequently and legitimately (e.g., process IDs, last-login timestamps). The drift viewer can suppress these to reduce noise.
