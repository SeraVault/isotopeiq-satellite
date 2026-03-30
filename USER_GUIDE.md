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
11. [Volatile Rules](#volatile-rules)
12. [Baselines](#baselines)
13. [Audit Log](#audit-log)
14. [Retention](#retention)
15. [Concepts & Glossary](#concepts--glossary)
16. [WinRM Setup for Windows Devices](#winrm-setup-for-windows-devices)

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
| Operations | Job Monitor, Drift, Volatile Rules, Baselines |
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

Drift events are raised when a job's parsed output differs from the established baseline for that device. The view polls for new events every few seconds — badge counts in the sidebar update in real time via WebSocket.

### Drift Statuses

| Status | Meaning |
|---|---|
| new | Unreviewed drift, requires attention |
| resolved | Acknowledged by a user, or device configuration returned to baseline |

A drift event in **new** status is an open issue. Once you take action — either by acknowledging the change or by letting the device return to its previous configuration — the event moves to **resolved**.

### Filtering

Filter by device or status using the dropdowns at the top of the table. Click **Clear** to reset all filters.

### Reviewing Drift

Click **View Diff** on any event row to open the diff viewer.

#### Diff Viewer

The diff viewer shows a structured, section-by-section comparison of the baseline against the current collection:

- **Stats bar** — counts of added, removed, and changed configuration items across all sections
- **Summary cards** — side-by-side key fields for device metadata, hardware, OS, and security
- **Section panels** — one expandable panel per canonical schema section that contains changes; sections with no differences are collapsed
  - Added items highlighted green, removed items red, changed items orange
  - A **Changed only** toggle hides unchanged rows within a section to reduce visual noise

#### Hide Volatile Fields

The **Hide volatile fields** toggle (enabled by default) strips fields governed by your [Volatile Rules](#volatile-rules) before rendering the diff. This suppresses expected transient changes — uptime counters, DHCP lease counts, process IDs, sysctl runtime values — so only meaningful drift is shown.

Disabling this toggle shows the raw unfiltered diff, which is useful for diagnosing why a rule is or isn't matching.

#### Creating a Volatile Rule from the Diff

If you see a field changing that you want to permanently suppress, click the **eye icon** next to that field in the diff viewer. A prefilled rule creation dialog opens. Confirm the details and save — the rule takes effect within 60 seconds.

### Acknowledging Drift

Click **Acknowledge** on a **new** drift event (or from the diff viewer). You must enter a reason before submitting.

When you acknowledge a drift event:

1. The event is marked **resolved** and your username and reason are recorded.
2. The current collection output (the "after" state) is **promoted as the new baseline** for the device.
3. Future collections compare against this new configuration, not the previous one.

Use acknowledgement when a change was intentional (planned upgrade, authorised configuration change). The reason is stored in the audit trail.

### Resolving Without Acknowledging

If the device configuration corrects itself on a subsequent collection run — e.g., a misconfiguration was fixed — the drift event is automatically marked **resolved** with no user action required.

---

## Volatile Rules

*Operations → Volatile Rules*

Volatile Rules tell the drift detector which configuration fields to ignore during comparison. Without them, fast-changing values like uptime counters, DHCP lease counts, and sysctl entropy pools would generate constant false-positive drift events.

Rules are evaluated server-side on every collection run. Changes take effect within 60 seconds (one cache TTL cycle) without requiring a restart.

> **Who can manage rules:** Only administrators can create, edit, or delete rules. All users can view the rules table.

### Rule Types

| Type | What it does | Example |
|---|---|---|
| `section_field` | Drops a scalar field from the top-level section | Ignore `os.uptime` |
| `item_field` | Drops a field from every item in an array section | Ignore `filesystem[*].free_gb` |
| `nested_field` | Drops a field from items inside a nested array | Ignore `routing_protocols[*].neighbors[*].state` |
| `exclude_key` | Removes entire array items whose key field matches a value | Remove sysctl entry `fs.dentry-state` entirely |
| `exclude_section` | Excludes an entire canonical section from comparison | Ignore everything in `custom` |

### Creating a Rule

Click **Add Rule** and fill in:

| Field | Notes |
|---|---|
| Section | The top-level canonical section (e.g., `os`, `network`, `filesystem`, `sysctl`) |
| Rule Type | See the table above |
| Field Name | For most types: the field to suppress. For `exclude_key`: the value to match |
| Nested Key | (`nested_field` only) The name of the nested array (e.g., `neighbors`, `ports`) |
| Key Field | (`exclude_key` only) The subfield to match on; defaults to `key` |
| Description | Required. Document *why* this field is volatile |
| Active | Uncheck to disable without deleting |

**The fastest way to create a rule** is directly from the diff viewer — click the eye icon next to any changing field and the form is pre-populated for you.

### Examples

**Ignore uptime on all Linux servers:**
- Section: `os`, Type: `section_field`, Field: `uptime`

**Ignore free disk space fluctuations:**
- Section: `filesystem`, Type: `item_field`, Field: `free_gb`

**Suppress a specific noisy sysctl entry:**
- Section: `sysctl`, Type: `exclude_key`, Field: `fs.dentry-state`, Key Field: `key`

**Ignore BGP neighbour session state (expected flap during maintenance):**
- Section: `routing_protocols`, Type: `nested_field`, Field: `state`, Nested Key: `neighbors`

### Enabling and Disabling Rules

Toggle the **Active** switch on any rule row to enable or disable it without deleting. This is useful for temporarily re-enabling a rule to investigate a suspected issue, then suppressing it again.

### Deleting Rules

Click the **bin** icon on a rule row. Deletion is permanent. If a rule was suppressing drift that is now present again, a new drift event will be raised on the next collection run.

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

**Drift Event** — A record created when drift is detected. Has a lifecycle: *new → resolved*. Resolution occurs when a user acknowledges the drift (promoting the current state as the new baseline) or when the device configuration returns to the previous baseline on a subsequent collection.

**Baseline** — The most recent successful canonical configuration snapshot for a device. Updated on each successful job.

**Job** — A single execution of a policy against one device. Captures collection, parsing, baseline comparison, and drift detection as a unit.

**Parser Script** — A server-side script that receives raw collection output via stdin and must write valid canonical JSON to stdout.

**Policy** — The main scheduling unit. Binds one or more devices to a collection profile (or individual scripts) and defines when collection should run.

**Push Token** — A per-device secret used by push-mode devices to authenticate when calling `POST /api/push/`.

**Volatile Fields** — Configuration fields that change frequently and legitimately without indicating a real configuration problem (e.g., uptime counters, DHCP lease counts, sysctl runtime values). Volatile Rules tell the drift engine which fields to strip before comparison.

**Volatile Rule** — A database-managed rule that instructs the drift detector to ignore specific fields, array items, or entire sections during comparison. Rules are cached for 60 seconds and evaluated server-side. See [Volatile Rules](#volatile-rules).

---

## WinRM Setup for Windows Devices

Satellite uses **WinRM (Windows Remote Management)** to connect to Windows hosts. WinRM is disabled or restricted by default on most Windows versions and must be configured before Satellite can collect from the device.

Run all commands below in an **elevated PowerShell prompt** (Run as Administrator) on the target Windows host.

### Quick Setup (Lab / Trusted Network)

For a quick start in a trusted network where HTTP transport is acceptable:

```powershell
# Enable WinRM and set default settings
Enable-PSRemoting -Force

# Allow connections from the Satellite host (replace with actual IP or subnet)
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "10.0.1.50" -Force

# Confirm the service is running and the listener is active
winrm enumerate winrm/config/listener
```

This opens WinRM on **port 5985 (HTTP)**. Credentials are still protected by NTLM/Kerberos, but traffic is not encrypted in transit — acceptable only on isolated management networks.

---

### Production Setup (HTTPS)

For production environments, use WinRM over **HTTPS (port 5986)** so that credentials and data are encrypted in transit.

#### Step 1 — Obtain or create a certificate

**Option A: Use an existing certificate from your PKI**

Export the certificate thumbprint:

```powershell
Get-ChildItem Cert:\LocalMachine\My | Select-Object Subject, Thumbprint
```

**Option B: Create a self-signed certificate (lab/test only)**

```powershell
$cert = New-SelfSignedCertificate `
    -DnsName $env:COMPUTERNAME `
    -CertStoreLocation Cert:\LocalMachine\My `
    -KeyExportPolicy NonExportable `
    -NotAfter (Get-Date).AddYears(3)
$thumbprint = $cert.Thumbprint
```

#### Step 2 — Create the HTTPS listener

```powershell
New-Item -Path WSMan:\LocalHost\Listener `
    -Transport HTTPS `
    -Address * `
    -CertificateThumbprint $thumbprint `
    -Force
```

#### Step 3 — Open the firewall

```powershell
New-NetFirewallRule `
    -DisplayName "WinRM HTTPS" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 5986 `
    -Action Allow
```

#### Step 4 — Verify the listener

```powershell
winrm enumerate winrm/config/listener
```

You should see a listener entry with `Transport = HTTPS` and `Port = 5986`.

---

### Configuring the Device in Satellite

In **Infrastructure → Devices → Add Device**:

| Field | Value |
|---|---|
| Connection Type | WinRM |
| Port | `5986` for HTTPS, `5985` for HTTP |
| Credential | A Windows credential (username + password) |

If using a **self-signed certificate**, you also need to disable certificate verification for that device. Set the **Skip TLS Verify** option on the device form. Do not use this option for certificates issued by a trusted CA.

---

### Authentication Options

Satellite supports two WinRM authentication methods:

| Method | Notes |
|---|---|
| **NTLM** (default) | Works for local accounts and workgroup machines. No domain required. |
| **Kerberos** | Required for domain accounts in a least-privilege setup. Satellite host must be able to resolve the domain and reach a KDC. |

For most environments, a **local administrator account** using NTLM is the simplest and most reliable option.

---

### Creating a Least-Privilege WinRM Account

Avoid using the built-in `Administrator` account. Create a dedicated service account:

```powershell
# Create the local user
$pw = ConvertTo-SecureString "StrongPassword123!" -AsPlainText -Force
New-LocalUser -Name "satellite-svc" -Password $pw -PasswordNeverExpires -Description "IsotopeIQ Satellite collection account"

# Add to Remote Management Users (WinRM access)
Add-LocalGroupMember -Group "Remote Management Users" -Member "satellite-svc"

# Add to Performance Monitor Users (for hardware/process data)
Add-LocalGroupMember -Group "Performance Monitor Users" -Member "satellite-svc"
```

Grant read access to WMI namespaces:

```powershell
# Open WMI namespace security
$computer = "."
$namespace = "root\cimv2"
$account = "satellite-svc"

$wmi = [wmiclass]"Win32_SecurityDescriptorHelper"
# Use wmimgmt.msc (GUI) to grant Remote Enable + Execute Methods on root\cimv2
# for the satellite-svc account if scripted access is insufficient
```

For most collection scripts, membership in **Remote Management Users** and **Performance Monitor Users** is sufficient. If the collection script requires registry or WMI access that fails, add the account to the local **Administrators** group as a fallback.

---

### Troubleshooting WinRM Connections

**Test from the Satellite host** using the **Test Connection** button in the UI. If that fails, diagnose from a Linux host with:

```bash
# Test HTTP
curl -u "Administrator:password" http://<windows-host>:5985/wsman

# Test HTTPS (skip cert check for self-signed)
curl -k -u "Administrator:password" https://<windows-host>:5986/wsman
```

Or from another Windows host:

```powershell
Test-WSMan -ComputerName <windows-host> -UseSSL
```

**Common issues:**

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` on 5985/5986 | WinRM service not running or listener not created | Run `Enable-PSRemoting -Force` |
| `Access denied` | Credentials wrong or account not in Remote Management Users | Verify credential and group membership |
| `The server certificate could not be validated` | Self-signed cert not trusted | Enable **Skip TLS Verify** on the device, or add the cert to Satellite's trust store |
| `WinRM cannot process the request` with HTTP 500 | NTLM blocked by security policy | Check `winrm get winrm/config/service/auth` — ensure NTLM is `true` |
| Timeout | Firewall blocking port | Add firewall rule and verify with `Test-NetConnection -ComputerName <host> -Port 5986` |

**Enable NTLM if disabled:**

```powershell
Set-Item WSMan:\localhost\Service\Auth\NTLM -Value $true
```

**Check current WinRM configuration:**

```powershell
winrm get winrm/config
winrm get winrm/config/service/auth
winrm enumerate winrm/config/listener
```
