# IsotopeIQ Windows Baseline Collector
# Compatible with Windows 7 / PowerShell 2.0 and later
# Usage: Substitute {{PLACEHOLDER}} values before deployment

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ELEVATE      = "{{ELEVATE}}"
$ELEVATE_PASS = "{{ELEVATE_PASS}}"
$USERNAME     = "{{USERNAME}}"
$PASSWORD     = "{{PASSWORD}}"
$HOSTNAME     = "{{HOSTNAME}}"

$SEP = "---ISOTOPEIQ---"

function section($name) {
    Write-Output "$SEP[$name]"
}

function priv {
    param([scriptblock]$Block)
    if ($ELEVATE -eq "runas") {
        $pw = ConvertTo-SecureString $ELEVATE_PASS -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential($USERNAME, $pw)
        $result = & $Block
        return $result
    } elseif ($ELEVATE -eq "scheduled_task") {
        $result = & $Block
        return $result
    } else {
        return & $Block
    }
}

# ---------------------------------------------------------------------------
# DEVICE
# ---------------------------------------------------------------------------
section "device"
try {
    $hostname = $env:COMPUTERNAME
    try {
        $fqdn = [System.Net.Dns]::GetHostEntry('').HostName
    } catch {
        if ($env:USERDNSDOMAIN) {
            $fqdn = "$hostname.$env:USERDNSDOMAIN"
        } else {
            $fqdn = $hostname
        }
    }
    $cs = Get-WmiObject -Class Win32_ComputerSystem -ErrorAction SilentlyContinue
    $vendor = ""
    $model  = ""
    if ($cs) {
        $vendor = $cs.Manufacturer
        $model  = $cs.Model
    }
    Write-Output "hostname=$hostname"
    Write-Output "fqdn=$fqdn"
    Write-Output "device_type=server"
    Write-Output "vendor=$vendor"
    Write-Output "model=$model"
} catch {
    Write-Output "hostname=$env:COMPUTERNAME"
    Write-Output "fqdn=$env:COMPUTERNAME"
    Write-Output "device_type=server"
    Write-Output "vendor=unknown"
    Write-Output "model=unknown"
}

# ---------------------------------------------------------------------------
# HARDWARE
# ---------------------------------------------------------------------------
section "hardware"
try {
    $cpu = Get-WmiObject -Class Win32_Processor -ErrorAction SilentlyContinue | Select-Object -First 1
    $cs  = Get-WmiObject -Class Win32_ComputerSystem -ErrorAction SilentlyContinue
    $bios = Get-WmiObject -Class Win32_BIOS -ErrorAction SilentlyContinue

    $cpu_model  = if ($cpu)  { $cpu.Name.Trim() }                             else { "unknown" }
    $cpu_cores  = if ($cs)   { $cs.NumberOfLogicalProcessors }                else { "unknown" }
    $mem_bytes  = if ($cs)   { $cs.TotalPhysicalMemory }                      else { 0 }
    $mem_gb     = if ($mem_bytes) { [math]::Round($mem_bytes / 1GB, 2) }      else { "unknown" }
    $bios_ver   = if ($bios) { $bios.SMBIOSBIOSVersion }                      else { "unknown" }
    $serial     = if ($bios) { $bios.SerialNumber }                           else { "unknown" }
    $arch       = $env:PROCESSOR_ARCHITECTURE

    $virt = "none"
    if ($cs) {
        $m = $cs.Model
        $mfr = $cs.Manufacturer
        if ($m -match "Virtual|VMware|VBOX|VirtualBox") {
            if ($m -match "VMware")     { $virt = "vmware" }
            elseif ($m -match "VBOX|VirtualBox") { $virt = "virtualbox" }
            else { $virt = "virtual" }
        } elseif ($m -match "HyperV|Hyper-V") {
            $virt = "hyperv"
        } elseif ($mfr -match "Microsoft") {
            $virt = "hyperv"
        }
    }

    Write-Output "cpu_model=$cpu_model"
    Write-Output "cpu_cores=$cpu_cores"
    Write-Output "memory_gb=$mem_gb"
    Write-Output "bios_version=$bios_ver"
    Write-Output "serial_number=$serial"
    Write-Output "architecture=$arch"
    Write-Output "virtualization_type=$virt"
} catch {
    Write-Output "cpu_model=unknown"
    Write-Output "cpu_cores=unknown"
    Write-Output "memory_gb=unknown"
    Write-Output "bios_version=unknown"
    Write-Output "serial_number=unknown"
    Write-Output "architecture=$env:PROCESSOR_ARCHITECTURE"
    Write-Output "virtualization=unknown"
}

# ---------------------------------------------------------------------------
# OS
# ---------------------------------------------------------------------------
section "os"
try {
    $os = Get-WmiObject -Class Win32_OperatingSystem -ErrorAction SilentlyContinue

    $os_name    = if ($os) { $os.Caption }       else { "Windows" }
    $os_version = if ($os) { $os.Version }       else { "unknown" }
    $os_build   = if ($os) { $os.BuildNumber }   else { "unknown" }
    $os_kernel  = $os_version

    # Timezone
    $tz = "unknown"
    try {
        $tz = (Get-TimeZone -ErrorAction SilentlyContinue).Id
    } catch {}
    if ($tz -eq "unknown" -or -not $tz) {
        try {
            $tz = [System.TimeZoneInfo]::Local.Id
        } catch {}
    }
    if ($tz -eq "unknown" -or -not $tz) {
        try {
            $tzutil_out = & tzutil /l 2>$null
            if ($tzutil_out) {
                $tz = ($tzutil_out | Select-String "^\(UTC").Line | Select-Object -First 1
            }
        } catch {}
    }

    # NTP servers
    $ntp_servers = "unknown"
    try {
        $w32peers = & w32tm /query /peers 2>$null
        if ($w32peers) {
            $peer_lines = $w32peers | Where-Object { $_ -match "Peer:" }
            if ($peer_lines) {
                $peers = $peer_lines | ForEach-Object { ($_ -split "Peer:")[1].Trim() }
                $ntp_servers = ($peers -join " ")
            }
        }
    } catch {}
    if ($ntp_servers -eq "unknown") {
        try {
            $reg_ntp = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters" -ErrorAction SilentlyContinue).NtpServer
            if ($reg_ntp) {
                $ntp_servers = ($reg_ntp -replace ",0x\w+","").Trim()
            }
        } catch {}
    }

    # NTP synced
    $ntp_synced = "false"
    try {
        $w32status = & w32tm /query /status 2>$null
        if ($w32status) {
            $source_line = $w32status | Where-Object { $_ -match "^Source:" }
            if ($source_line) {
                $source_val = ($source_line -split "Source:")[1].Trim()
                if ($source_val -notmatch "Local CMOS Clock|Free-running|unspecified") {
                    $ntp_synced = "true"
                }
            }
        }
    } catch {}

    Write-Output "name=$os_name"
    Write-Output "version=$os_version"
    Write-Output "build=$os_build"
    Write-Output "kernel=$os_kernel"
    Write-Output "timezone=$tz"
    Write-Output "ntp_servers=$ntp_servers"
    Write-Output "ntp_synced=$ntp_synced"
} catch {
    Write-Output "os_name=Windows"
    Write-Output "version=unknown"
    Write-Output "build=unknown"
    Write-Output "kernel=unknown"
    Write-Output "timezone=unknown"
    Write-Output "ntp_servers=unknown"
    Write-Output "ntp_synced=false"
}

# ---------------------------------------------------------------------------
# NETWORK
# ---------------------------------------------------------------------------
section "network"
try {
    $use_modern_net = $false
    try {
        $null = Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue
        if (Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue) {
            $use_modern_net = $true
        }
    } catch {}

    if ($use_modern_net) {
        try {
            $addrs = Get-NetIPAddress -ErrorAction SilentlyContinue
            foreach ($a in $addrs) {
                $family = if ($a.AddressFamily -eq "IPv4") { "IPv4" } else { "IPv6" }
                Write-Output "$($a.InterfaceAlias)|$($a.IPAddress)|$($a.PrefixLength)|$family"
            }
        } catch {
            $use_modern_net = $false
        }
    }

    if (-not $use_modern_net) {
        # Fall back to ipconfig /all parsing
        $ipconfig = & ipconfig /all 2>$null
        $current_adapter = ""
        foreach ($line in $ipconfig) {
            if ($line -match "^[A-Za-z]" -and $line -match ":$") {
                $current_adapter = $line.TrimEnd(":").Trim()
            } elseif ($line -match "IPv4 Address.*:\s*(\d+\.\d+\.\d+\.\d+)") {
                $ip = $Matches[1] -replace "\(Preferred\)",""
                $ip = $ip.Trim()
                Write-Output "$current_adapter|$ip|24|IPv4"
            } elseif ($line -match "IPv6 Address.*:\s*([0-9a-fA-F:]+)") {
                $ip = $Matches[1] -replace "\(Preferred\)",""
                $ip = $ip.Trim()
                Write-Output "$current_adapter|$ip|64|IPv6"
            }
        }
    }

    Write-Output "---MAC---"

    if ($use_modern_net) {
        try {
            $adapters = Get-NetAdapter -ErrorAction SilentlyContinue
            foreach ($a in $adapters) {
                Write-Output "$($a.Name)|$($a.MacAddress)"
            }
        } catch {}
    } else {
        $ipconfig = & ipconfig /all 2>$null
        $current_adapter = ""
        foreach ($line in $ipconfig) {
            if ($line -match "^[A-Za-z]" -and $line -match ":$") {
                $current_adapter = $line.TrimEnd(":").Trim()
            } elseif ($line -match "Physical Address.*:\s*([0-9A-Fa-f\-]{17})") {
                $mac = $Matches[1]
                Write-Output "$current_adapter|$mac"
            }
        }
    }
} catch {
    Write-Output "error=failed to collect network"
}

# ---------------------------------------------------------------------------
# NETWORK_ROUTES
# ---------------------------------------------------------------------------
section "network_routes"
try {
    $use_modern_route = $false
    try {
        if (Get-Command Get-NetRoute -ErrorAction SilentlyContinue) {
            $use_modern_route = $true
        }
    } catch {}

    if ($use_modern_route) {
        try {
            $routes = Get-NetRoute -ErrorAction SilentlyContinue
            foreach ($r in $routes) {
                Write-Output "$($r.DestinationPrefix)|$($r.NextHop)|$($r.InterfaceAlias)|$($r.RouteMetric)"
            }
        } catch {
            $use_modern_route = $false
        }
    }

    if (-not $use_modern_route) {
        & route print 2>$null
    }
} catch {
    & route print 2>$null
}

# ---------------------------------------------------------------------------
# NETWORK_DNS
# ---------------------------------------------------------------------------
section "network_dns"
try {
    $use_modern_dns = $false
    try {
        if (Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue) {
            $use_modern_dns = $true
        }
    } catch {}

    if ($use_modern_dns) {
        try {
            $dns_addrs = Get-DnsClientServerAddress -ErrorAction SilentlyContinue
            $seen = @{}
            foreach ($d in $dns_addrs) {
                foreach ($ip in $d.ServerAddresses) {
                    if (-not $seen.ContainsKey($ip)) {
                        Write-Output $ip
                        $seen[$ip] = 1
                    }
                }
            }
        } catch {
            $use_modern_dns = $false
        }
    }

    if (-not $use_modern_dns) {
        $ipconfig = & ipconfig /all 2>$null
        $seen = @{}
        foreach ($line in $ipconfig) {
            if ($line -match "DNS Servers.*:\s*(\d+\.\d+\.\d+\.\d+)") {
                $ip = $Matches[1].Trim()
                if (-not $seen.ContainsKey($ip)) {
                    Write-Output $ip
                    $seen[$ip] = 1
                }
            } elseif ($line -match "^\s+(\d+\.\d+\.\d+\.\d+)\s*$") {
                $ip = $Matches[1].Trim()
                if (-not $seen.ContainsKey($ip)) {
                    Write-Output $ip
                    $seen[$ip] = 1
                }
            }
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# NETWORK_HOSTS
# ---------------------------------------------------------------------------
section "network_hosts"
try {
    $hosts_file = "C:\Windows\System32\drivers\etc\hosts"
    if (Test-Path $hosts_file) {
        Get-Content $hosts_file -ErrorAction SilentlyContinue | ForEach-Object {
            $line = $_.Trim()
            if ($line -and $line -notmatch "^#") {
                Write-Output $line
            }
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------
section "users"
try {
    # Build admin group members set
    $admin_members = @{}
    try {
        $admin_group = [ADSI]"WinNT://$env:COMPUTERNAME/Administrators,group"
        $admin_group.Members() | ForEach-Object {
            $member_path = $_.GetType().InvokeMember("AdsPath", "GetProperty", $null, $_, $null)
            $member_name = $_.GetType().InvokeMember("Name", "GetProperty", $null, $_, $null)
            $admin_members[$member_name.ToLower()] = $true
        }
    } catch {}

    $use_modern_users = $false
    try {
        if (Get-Command Get-LocalUser -ErrorAction SilentlyContinue) {
            $use_modern_users = $true
        }
    } catch {}

    if ($use_modern_users) {
        try {
            $local_users = Get-LocalUser -ErrorAction SilentlyContinue
            foreach ($u in $local_users) {
                $sid         = $u.SID.Value
                $homedir     = ""
                $shell       = ""
                $is_admin    = if ($admin_members.ContainsKey($u.Name.ToLower())) { "true" } else { "false" }
                $pw_last_set = if ($u.PasswordLastSet) { $u.PasswordLastSet.ToString("yyyy-MM-dd") } else { "" }
                $last_logon  = if ($u.LastLogon) { $u.LastLogon.ToString("yyyy-MM-dd") } else { "" }

                # Groups for this user
                $user_groups = @()
                try {
                    $all_groups = Get-LocalGroup -ErrorAction SilentlyContinue
                    foreach ($g in $all_groups) {
                        try {
                            $gm = Get-LocalGroupMember -Group $g.Name -ErrorAction SilentlyContinue
                            if ($gm | Where-Object { $_.Name -match "\\$($u.Name)$" }) {
                                $user_groups += $g.Name
                            }
                        } catch {}
                    }
                } catch {}
                $groups_str = $user_groups -join ","

                Write-Output "$($u.Name)|$sid|$homedir|$shell|$groups_str|$pw_last_set|$last_logon|$is_admin"
            }
        } catch {
            $use_modern_users = $false
        }
    }

    if (-not $use_modern_users) {
        # Fall back to ADSI WinNT provider
        try {
            $computer = [ADSI]"WinNT://$env:COMPUTERNAME"
            $computer.Children | Where-Object { $_.SchemaClassName -eq "User" } | ForEach-Object {
                $u = $_
                $uname       = $u.Name[0]
                $sid_bytes   = $u.ObjectSid[0]
                $sid_obj     = New-Object System.Security.Principal.SecurityIdentifier($sid_bytes, 0)
                $sid         = $sid_obj.Value
                $homedir     = try { $u.HomeDirectory[0] } catch { "" }
                $pw_last_set = try { $u.PasswordAge[0] }   catch { "" }
                $last_logon  = try { $u.LastLogin[0] }     catch { "" }
                $is_admin    = if ($admin_members.ContainsKey($uname.ToLower())) { "true" } else { "false" }
                Write-Output "$uname|$sid|$homedir||  |$pw_last_set|$last_logon|$is_admin"
            }
        } catch {
            # Last resort: net user
            $net_users = & net user 2>$null
            if ($net_users) {
                $in_users = $false
                foreach ($line in $net_users) {
                    if ($line -match "^---") { $in_users = $true; continue }
                    if ($in_users -and $line.Trim()) {
                        $line.Trim() -split "\s{2,}" | ForEach-Object {
                            $uname = $_.Trim()
                            if ($uname) {
                                $is_admin = if ($admin_members.ContainsKey($uname.ToLower())) { "true" } else { "false" }
                                Write-Output "$uname|unknown|||  ||  |$is_admin"
                            }
                        }
                    }
                }
            }
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# GROUPS
# ---------------------------------------------------------------------------
section "groups"
try {
    $use_modern_groups = $false
    try {
        if (Get-Command Get-LocalGroup -ErrorAction SilentlyContinue) {
            $use_modern_groups = $true
        }
    } catch {}

    if ($use_modern_groups) {
        try {
            $local_groups = Get-LocalGroup -ErrorAction SilentlyContinue
            foreach ($g in $local_groups) {
                $sid     = $g.SID.Value
                $members_list = @()
                try {
                    $gm = Get-LocalGroupMember -Group $g.Name -ErrorAction SilentlyContinue
                    $members_list = $gm | ForEach-Object {
                        $_.Name -replace "^.*\\",""
                    }
                } catch {}
                $members_str = $members_list -join ","
                Write-Output "$($g.Name)|$sid|$members_str"
            }
        } catch {
            $use_modern_groups = $false
        }
    }

    if (-not $use_modern_groups) {
        try {
            $computer = [ADSI]"WinNT://$env:COMPUTERNAME"
            $computer.Children | Where-Object { $_.SchemaClassName -eq "Group" } | ForEach-Object {
                $g = $_
                $gname    = $g.Name[0]
                $sid_bytes = $g.ObjectSid[0]
                $sid_obj  = New-Object System.Security.Principal.SecurityIdentifier($sid_bytes, 0)
                $sid      = $sid_obj.Value
                $members_list = @()
                try {
                    $g.Members() | ForEach-Object {
                        $mname = $_.GetType().InvokeMember("Name", "GetProperty", $null, $_, $null)
                        $members_list += $mname
                    }
                } catch {}
                $members_str = $members_list -join ","
                Write-Output "$gname|$sid|$members_str"
            }
        } catch {
            # net localgroup fallback
            $net_groups_raw = & net localgroup 2>$null
            if ($net_groups_raw) {
                foreach ($line in $net_groups_raw) {
                    if ($line -match "^\*(.+)") {
                        $gname = $Matches[1].Trim()
                        Write-Output "$gname|unknown|"
                    }
                }
            }
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# PACKAGES
# ---------------------------------------------------------------------------
section "packages"
try {
    $reg_paths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    $seen_pkg = @{}
    foreach ($rp in $reg_paths) {
        try {
            $items = Get-ItemProperty -Path $rp -ErrorAction SilentlyContinue
            foreach ($item in $items) {
                $dname = $item.DisplayName
                if (-not $dname) { continue }
                $key = "$dname|$($item.DisplayVersion)"
                if ($seen_pkg.ContainsKey($key)) { continue }
                $seen_pkg[$key] = 1
                $ver       = if ($item.DisplayVersion) { $item.DisplayVersion } else { "" }
                $publisher = if ($item.Publisher)      { $item.Publisher }      else { "" }
                $idate     = if ($item.InstallDate)    { $item.InstallDate }    else { "" }
                Write-Output "$dname|$ver|$publisher|$idate"
            }
        } catch {}
    }
} catch {}

# ---------------------------------------------------------------------------
# SERVICES
# ---------------------------------------------------------------------------
section "services"
try {
    $services = Get-Service -ErrorAction SilentlyContinue
    # Try to get start mode from WMI (works on PS2+)
    $wmi_services = @{}
    try {
        $wmi_svc_list = Get-WmiObject -Class Win32_Service -ErrorAction SilentlyContinue
        foreach ($ws in $wmi_svc_list) {
            $wmi_services[$ws.Name] = $ws.StartMode
        }
    } catch {}

    foreach ($svc in $services) {
        $name   = $svc.Name
        $status = if ($svc.Status -eq "Running") { "running" } else { "stopped" }
        $start  = "unknown"
        if ($wmi_services.ContainsKey($name)) {
            $sm = $wmi_services[$name]
            if ($sm -match "Auto")     { $start = "automatic" }
            elseif ($sm -match "Manual")   { $start = "manual" }
            elseif ($sm -match "Disabled") { $start = "disabled" }
            else { $start = $sm.ToLower() }
        } else {
            try {
                $st = $svc.StartType
                if ($st -eq "Automatic") { $start = "automatic" }
                elseif ($st -eq "Manual")    { $start = "manual" }
                elseif ($st -eq "Disabled")  { $start = "disabled" }
            } catch {}
        }
        Write-Output "$name|$status|$start"
    }
} catch {}

# ---------------------------------------------------------------------------
# FILESYSTEM
# ---------------------------------------------------------------------------
section "filesystem"
try {
    $use_modern_fs = $false
    try {
        if (Get-Command Get-PSDrive -ErrorAction SilentlyContinue) {
            $use_modern_fs = $true
        }
    } catch {}

    if ($use_modern_fs) {
        try {
            $drives = Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue
            foreach ($d in $drives) {
                $drive   = $d.Name + ":"
                $fstype  = "NTFS"
                $used    = if ($d.Used) { $d.Used } else { 0 }
                $free    = if ($d.Free) { $d.Free } else { 0 }
                $size_gb = [math]::Round(($used + $free) / 1GB, 2)
                $free_gb = [math]::Round($free / 1GB, 2)
                Write-Output "$drive|$fstype|$size_gb|$free_gb"
            }
        } catch {
            $use_modern_fs = $false
        }
    }

    if (-not $use_modern_fs) {
        $disks = Get-WmiObject -Class Win32_LogicalDisk -Filter "DriveType=3" -ErrorAction SilentlyContinue
        foreach ($disk in $disks) {
            $drive   = $disk.DeviceID
            $fstype  = if ($disk.FileSystem) { $disk.FileSystem } else { "unknown" }
            $size_gb = [math]::Round($disk.Size / 1GB, 2)
            $free_gb = [math]::Round($disk.FreeSpace / 1GB, 2)
            Write-Output "$drive|$fstype|$size_gb|$free_gb"
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# FILESYSTEM_SUID (not applicable on Windows)
# ---------------------------------------------------------------------------
section "filesystem_suid"
# Windows does not have SUID bits; section intentionally left empty.

# ---------------------------------------------------------------------------
# SECURITY
# ---------------------------------------------------------------------------
section "security"
try {
    # UAC
    $uac_enabled = "unknown"
    try {
        $uac_val = (Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -ErrorAction SilentlyContinue).EnableLUA
        $uac_enabled = if ($uac_val -eq 1) { "true" } else { "false" }
    } catch {}
    Write-Output "uac_enabled=$uac_enabled"

    # Antivirus / Defender
    $av_name = "unknown"
    try {
        $mp = Get-MpComputerStatus -ErrorAction SilentlyContinue
        if ($mp) {
            $av_name = "Windows Defender"
        }
    } catch {}
    if ($av_name -eq "unknown") {
        try {
            $av_products = Get-WmiObject -Namespace "root\SecurityCenter2" -Class AntiVirusProduct -ErrorAction SilentlyContinue
            if (-not $av_products) {
                $av_products = Get-WmiObject -Namespace "root\SecurityCenter" -Class AntiVirusProduct -ErrorAction SilentlyContinue
            }
            if ($av_products) {
                $av_names_list = $av_products | ForEach-Object { $_.displayName }
                $av_name = $av_names_list -join ","
            }
        } catch {}
    }
    Write-Output "antivirus=$av_name"

    # Firewall
    $fw_state = "unknown"
    try {
        $fw_out = & netsh advfirewall show allprofiles state 2>$null
        if ($fw_out) {
            $on_count  = ($fw_out | Where-Object { $_ -match "State\s+ON" }).Count
            $off_count = ($fw_out | Where-Object { $_ -match "State\s+OFF" }).Count
            if ($on_count -gt 0)     { $fw_state = "enabled" }
            elseif ($off_count -gt 0) { $fw_state = "disabled" }
        }
    } catch {}
    Write-Output "firewall=$fw_state"

    # Secure Boot
    $secure_boot = "unknown"
    try {
        $sb = Confirm-SecureBootUEFI -ErrorAction SilentlyContinue
        $secure_boot = if ($sb) { "true" } else { "false" }
    } catch {
        $secure_boot = "unsupported"
    }
    Write-Output "secure_boot=$secure_boot"

    # Audit policy
    Write-Output "audit_policy_start"
    try {
        & auditpol /get /category:* 2>$null | ForEach-Object { Write-Output $_ }
    } catch {}
    Write-Output "audit_policy_end"

    # Password policy
    Write-Output "password_policy_start"
    try {
        & net accounts 2>$null | ForEach-Object { Write-Output $_ }
    } catch {}
    Write-Output "password_policy_end"
} catch {}

# ---------------------------------------------------------------------------
# SCHEDULED_TASKS
# ---------------------------------------------------------------------------
section "scheduled_tasks"
try {
    $schtasks_out = & schtasks /query /fo CSV /v 2>$null
    if ($schtasks_out) {
        $header_found = $false
        $header_map   = @{}
        foreach ($line in $schtasks_out) {
            $line = $line.Trim()
            if (-not $line) { continue }

            # Parse CSV manually (simple split on comma-between-quotes)
            $fields = @()
            $in_quote = $false
            $current  = ""
            foreach ($char in $line.ToCharArray()) {
                if ($char -eq '"') {
                    $in_quote = -not $in_quote
                } elseif ($char -eq ',' -and -not $in_quote) {
                    $fields += $current
                    $current = ""
                } else {
                    $current += $char
                }
            }
            $fields += $current

            if (-not $header_found) {
                for ($i = 0; $i -lt $fields.Count; $i++) {
                    $header_map[$fields[$i].Trim()] = $i
                }
                $header_found = $true
                continue
            }

            $task_name  = if ($header_map.ContainsKey("TaskName"))      { $fields[$header_map["TaskName"]].Trim() }      else { "" }
            $task_user  = if ($header_map.ContainsKey("Run As User"))   { $fields[$header_map["Run As User"]].Trim() }   else { "" }
            $schedule   = if ($header_map.ContainsKey("Schedule"))      { $fields[$header_map["Schedule"]].Trim() }      else { "" }
            $task_cmd   = if ($header_map.ContainsKey("Task To Run"))   { $fields[$header_map["Task To Run"]].Trim() }   else { "" }
            $status     = if ($header_map.ContainsKey("Status"))        { $fields[$header_map["Status"]].Trim() }        else { "" }
            $enabled    = if ($status -match "Disabled") { "false" } else { "true" }

            if ($task_name -and $task_name -ne "TaskName") {
                Write-Output "windows-task-scheduler|$task_user|$task_name|$schedule|$task_cmd|$enabled"
            }
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# SSH_KEYS
# ---------------------------------------------------------------------------
section "ssh_keys"
try {
    # System-wide administrators authorized keys
    $admin_keys = "C:\ProgramData\ssh\administrators_authorized_keys"
    if (Test-Path $admin_keys) {
        $lines = Get-Content $admin_keys -ErrorAction SilentlyContinue
        foreach ($line in $lines) {
            $line = $line.Trim()
            if ($line -and $line -notmatch "^#") {
                Write-Output "SYSTEM|$line"
            }
        }
    }

    # Per-user authorized_keys
    $users_dir = "C:\Users"
    if (Test-Path $users_dir) {
        $user_dirs = Get-ChildItem -Path $users_dir -Directory -ErrorAction SilentlyContinue
        foreach ($udir in $user_dirs) {
            $uname    = $udir.Name
            $ssh_file = Join-Path $udir.FullName ".ssh\authorized_keys"
            if (Test-Path $ssh_file) {
                $lines = Get-Content $ssh_file -ErrorAction SilentlyContinue
                foreach ($line in $lines) {
                    $line = $line.Trim()
                    if ($line -and $line -notmatch "^#") {
                        Write-Output "$uname|$line"
                    }
                }
            }
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# KERNEL_MODULES (Windows Drivers)
# ---------------------------------------------------------------------------
section "kernel_modules"
try {
    $drivers = Get-WmiObject -Class Win32_SystemDriver -ErrorAction SilentlyContinue
    foreach ($d in $drivers) {
        $name      = if ($d.Name)      { $d.Name }      else { "" }
        $state     = if ($d.State)     { $d.State }     else { "" }
        $startmode = if ($d.StartMode) { $d.StartMode } else { "" }
        $pathname  = if ($d.PathName)  { $d.PathName }  else { "" }
        Write-Output "$name|$state|$startmode|$pathname"
    }
} catch {}

# ---------------------------------------------------------------------------
# LISTENING_SERVICES
# ---------------------------------------------------------------------------
section "listening_services"
try {
    & netstat -ano 2>$null
} catch {}

# ---------------------------------------------------------------------------
# FIREWALL_RULES
# ---------------------------------------------------------------------------
section "firewall_rules"
try {
    $use_modern_fw = $false
    try {
        if (Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue) {
            $use_modern_fw = $true
        }
    } catch {}

    if ($use_modern_fw) {
        try {
            $fw_rules = Get-NetFirewallRule -ErrorAction SilentlyContinue
            foreach ($r in $fw_rules) {
                $addr_filter = $r | Get-NetFirewallAddressFilter  -ErrorAction SilentlyContinue
                $port_filter = $r | Get-NetFirewallPortFilter     -ErrorAction SilentlyContinue
                $rule_name   = $r.DisplayName
                $direction   = $r.Direction.ToString()
                $action      = $r.Action.ToString()
                $enabled     = $r.Enabled.ToString()
                $proto       = if ($port_filter) { $port_filter.Protocol }   else { "Any" }
                $local_port  = if ($port_filter) { $port_filter.LocalPort }  else { "Any" }
                $remote_addr = if ($addr_filter) { $addr_filter.RemoteAddress } else { "Any" }
                Write-Output "RuleName: $rule_name"
                Write-Output "Direction: $direction"
                Write-Output "Action: $action"
                Write-Output "Protocol: $proto"
                Write-Output "LocalPort: $local_port"
                Write-Output "RemoteAddress: $remote_addr"
                Write-Output "Enabled: $enabled"
                Write-Output "----"
            }
        } catch {
            $use_modern_fw = $false
        }
    }

    if (-not $use_modern_fw) {
        & netsh advfirewall firewall show rule name=all verbose 2>$null
    }
} catch {
    & netsh advfirewall firewall show rule name=all verbose 2>$null
}

# ---------------------------------------------------------------------------
# SYSCTL (Windows Registry Security Settings)
# ---------------------------------------------------------------------------
section "sysctl"
try {
    $reg_keys = @{
        "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" = @(
            "LmCompatibilityLevel",
            "NoLMHash",
            "RestrictAnonymous",
            "RestrictAnonymousSAM",
            "EveryoneIncludesAnonymous",
            "DisableDomainCreds",
            "ForceGuest",
            "LimitBlankPasswordUse",
            "AuditBaseObjects",
            "FullPrivilegeAuditing",
            "SCENoApplyLegacyAuditPolicy",
            "CrashOnAuditFail",
            "UseMachineId",
            "MSV1_0 RestrictReceivingNTLMTraffic",
            "MSV1_0 RestrictSendingNTLMTraffic"
        )
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" = @(
            "EnableLUA",
            "ConsentPromptBehaviorAdmin",
            "ConsentPromptBehaviorUser",
            "EnableInstallerDetection",
            "ValidateAdminCodeSignatures",
            "EnableSecureUIAPaths",
            "EnableVirtualization",
            "PromptOnSecureDesktop",
            "FilterAdministratorToken",
            "EnableLUARunVirtualized",
            "DontDisplayLastUserName",
            "NoConnectedUser",
            "EnumerateAdministrators",
            "DisableCAD",
            "BlockDomainPicturePassword"
        )
    }

    foreach ($reg_path in $reg_keys.Keys) {
        $props = Get-ItemProperty -Path $reg_path -ErrorAction SilentlyContinue
        if ($props) {
            foreach ($val_name in $reg_keys[$reg_path]) {
                try {
                    $v = $props.$val_name
                    if ($null -ne $v) {
                        Write-Output "$reg_path\$val_name=$v"
                    }
                } catch {}
            }
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# LOGGING_TARGETS
# ---------------------------------------------------------------------------
section "logging_targets"
try {
    # Windows Event Forwarding subscriptions via wecutil
    try {
        $subs = & wecutil es 2>$null
        foreach ($sub in $subs) {
            $sub = $sub.Trim()
            if (-not $sub) { continue }
            try {
                $sub_config = & wecutil gs $sub 2>$null
                $dest_line = $sub_config | Where-Object { $_ -match "SubscriptionManager|Address" }
                foreach ($dl in $dest_line) {
                    Write-Output $dl.Trim()
                }
            } catch {
                Write-Output "subscription=$sub"
            }
        }
    } catch {}

    # Registry-based subscription manager
    try {
        $sm_path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\EventLog\EventForwarding\SubscriptionManager"
        if (Test-Path $sm_path) {
            $sm_props = Get-ItemProperty -Path $sm_path -ErrorAction SilentlyContinue
            if ($sm_props) {
                $sm_props.PSObject.Properties | Where-Object { $_.Name -notmatch "^PS" } | ForEach-Object {
                    Write-Output $_.Value
                }
            }
        }
    } catch {}
} catch {}

# ---------------------------------------------------------------------------
# STARTUP_ITEMS
# ---------------------------------------------------------------------------
section "startup_items"
try {
    $startup = Get-WmiObject -Class Win32_StartupCommand -ErrorAction SilentlyContinue
    if ($startup) {
        foreach ($item in $startup) {
            $name    = if ($item.Name)     { $item.Name.Trim() }     else { "" }
            $command = if ($item.Command)  { $item.Command.Trim() }  else { "" }
            $loc     = if ($item.Location) { $item.Location.Trim() } else { "" }
            $user    = if ($item.User)     { $item.User.Trim() }     else { "" }
            # Classify type from location
            $type = "other"
            if ($loc -match "RunKey|Run$|RunOnce") { $type = "runkey" }
            elseif ($loc -match "Startup") { $type = "loginitem" }
            Write-Output "$name|$type|$command|$loc|$user"
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# CERTIFICATES
# ---------------------------------------------------------------------------
section "certificates"
try {
    $stores = @("LocalMachine\My", "LocalMachine\Root", "LocalMachine\CA", "LocalMachine\TrustedPublisher")
    foreach ($storePath in $stores) {
        try {
            $certs = Get-ChildItem -Path "Cert:\$storePath" -ErrorAction SilentlyContinue
            foreach ($cert in $certs) {
                try {
                    $subject    = if ($cert.Subject)      { $cert.Subject }               else { "" }
                    $issuer     = if ($cert.Issuer)       { $cert.Issuer }                else { "" }
                    $thumb      = if ($cert.Thumbprint)   { $cert.Thumbprint }            else { "" }
                    $serial     = if ($cert.SerialNumber) { $cert.SerialNumber }          else { "" }
                    $notBefore  = if ($cert.NotBefore)    { $cert.NotBefore.ToString("o") } else { "" }
                    $notAfter   = if ($cert.NotAfter)     { $cert.NotAfter.ToString("o") }  else { "" }
                    $store      = $storePath.Replace("\", "/")
                    Write-Output "$subject|$issuer|$thumb|$serial|$notBefore|$notAfter|$store"
                } catch {}
            }
        } catch {}
    }
} catch {}

# ---------------------------------------------------------------------------
# INSTALLED_SOFTWARE (AppX / Microsoft Store packages)
# ---------------------------------------------------------------------------
section "appx_packages"
try {
    if (Get-Command Get-AppxPackage -ErrorAction SilentlyContinue) {
        Get-AppxPackage -AllUsers -ErrorAction SilentlyContinue | ForEach-Object {
            $name      = if ($_.Name)               { $_.Name }               else { "" }
            $version   = if ($_.Version)            { $_.Version }            else { "" }
            $publisher = if ($_.Publisher)          { $_.Publisher }          else { "" }
            $arch      = if ($_.Architecture)       { $_.Architecture }       else { "" }
            Write-Output "$name|$version|$publisher|$arch"
        }
    }
} catch {}

# ---------------------------------------------------------------------------
# END
# ---------------------------------------------------------------------------
Write-Output "$SEP[END]"
