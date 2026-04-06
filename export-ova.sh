#!/usr/bin/env bash
# export-ova.sh — Export a running KVM VM to a VMware-compatible OVA file.
#
# Usage:
#   ./export-ova.sh [vm-name] [output-dir]
#
# Defaults:
#   vm-name    isotopeiq-satellite
#   output-dir ~/kvm-images
#
# The VM is shut down cleanly, exported, then restarted.
# The OVF descriptor is populated with the actual vCPU/RAM of the VM.

set -euo pipefail

VM_NAME="${1:-isotopeiq-satellite}"
OUTPUT_DIR="${2:-${HOME}/kvm-images}"

log()  { printf '\033[1;34m[export-ova]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[  OK  ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[ WARN ]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[ ERR  ]\033[0m %s\n' "$*" >&2; exit 1; }

# ── Preflight ─────────────────────────────────────────────────────────────────
for cmd in virsh qemu-img python3 sha256sum tar; do
  command -v "$cmd" >/dev/null 2>&1 || die "Required tool not found: $cmd"
done

virsh dominfo "$VM_NAME" &>/dev/null || die "VM '$VM_NAME' not found in libvirt."

mkdir -p "$OUTPUT_DIR"
OVA_PATH="${OUTPUT_DIR}/${VM_NAME}.ova"

# ── Read VM parameters from libvirt ──────────────────────────────────────────
log "Reading VM configuration for '$VM_NAME'…"

VM_DISK=$(virsh domblklist "$VM_NAME" --details \
  | awk '$2=="disk" && $4!="" {print $4; exit}')
[[ -n "$VM_DISK" ]] || die "Could not determine disk path for '$VM_NAME'."

VM_VCPUS=$(virsh dominfo "$VM_NAME" | awk '/^CPU\(s\):/ {print $2}')
VM_RAM_MB=$(virsh dominfo "$VM_NAME" | awk '/^Max memory:/ {printf "%d", $3/1024}')

log "  Disk  : $VM_DISK"
log "  vCPUs : $VM_VCPUS"
log "  RAM   : ${VM_RAM_MB} MB"

# ── Shut down VM cleanly ──────────────────────────────────────────────────────
INITIAL_STATE=$(virsh domstate "$VM_NAME" | head -1)
STARTED=false

if [[ "$INITIAL_STATE" == "running" ]]; then
  log "Shutting VM down cleanly for export…"
  virsh shutdown "$VM_NAME" --mode acpi
  for i in $(seq 1 40); do
    sleep 3
    [[ "$(virsh domstate "$VM_NAME" | head -1)" == "shut off" ]] && { STARTED=true; break; }
    (( i % 5 == 0 )) && log "  Still waiting… (${i}×3s = $((i*3))s)"
  done
  if [[ "$(virsh domstate "$VM_NAME" | head -1)" != "shut off" ]]; then
    warn "VM didn't shut down cleanly within 120s — forcing."
    virsh destroy "$VM_NAME"
    STARTED=true
  fi
  ok "VM shut down."
else
  log "VM is already stopped (state: $INITIAL_STATE)."
fi

# ── Convert disk to streamOptimized VMDK ──────────────────────────────────────
OVA_WORK=$(mktemp -d /tmp/isotopeiq-ova-XXXXXX)
trap 'rm -rf "$OVA_WORK"' EXIT

VMDK="${OVA_WORK}/${VM_NAME}-disk1.vmdk"
OVF="${OVA_WORK}/${VM_NAME}.ovf"
MF="${OVA_WORK}/${VM_NAME}.mf"

log "Converting disk to streamOptimized VMDK (this may take several minutes)…"
qemu-img convert -f qcow2 -O vmdk \
  -o subformat=streamOptimized,adapter_type=lsilogic \
  "$VM_DISK" "$VMDK"
ok "Disk converted."

# ── Generate OVF descriptor ───────────────────────────────────────────────────
log "Generating OVF descriptor…"
DISK_SIZE_GB=$(python3 - "$VMDK" <<'PYEOF'
import json, subprocess, sys
d = json.loads(subprocess.check_output(['qemu-img', 'info', '--output', 'json', sys.argv[1]]))
print((d['virtual-size'] + 2**30 - 1) // 2**30)
PYEOF
)

cat > "$OVF" <<OVFEOF
<?xml version="1.0" encoding="UTF-8"?>
<Envelope xmlns="http://schemas.dmtf.org/ovf/envelope/1"
          xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1"
          xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData"
          xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData">
  <References>
    <File ovf:id="file1" ovf:href="${VM_NAME}-disk1.vmdk"/>
  </References>
  <DiskSection>
    <Info>Virtual disk</Info>
    <Disk ovf:capacity="${DISK_SIZE_GB}" ovf:capacityAllocationUnits="byte * 2^30"
          ovf:diskId="vmdisk1" ovf:fileRef="file1"
          ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
  </DiskSection>
  <NetworkSection>
    <Info>Networks</Info>
    <Network ovf:name="VM Network"><Description>VM Network</Description></Network>
  </NetworkSection>
  <VirtualSystem ovf:id="${VM_NAME}">
    <Info>IsotopeIQ Satellite</Info>
    <OperatingSystemSection ovf:id="101">
      <Info>Guest OS</Info>
      <Description>Ubuntu Linux 64-bit</Description>
    </OperatingSystemSection>
    <VirtualHardwareSection>
      <Info>Hardware</Info>
      <System>
        <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
        <vssd:InstanceID>0</vssd:InstanceID>
        <vssd:VirtualSystemType>vmx-19</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:InstanceID>1</rasd:InstanceID>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>${VM_VCPUS}</rasd:VirtualQuantity>
        <rasd:ElementName>${VM_VCPUS} vCPU</rasd:ElementName>
      </Item>
      <Item>
        <rasd:InstanceID>2</rasd:InstanceID>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:AllocationUnits>byte * 2^20</rasd:AllocationUnits>
        <rasd:VirtualQuantity>${VM_RAM_MB}</rasd:VirtualQuantity>
        <rasd:ElementName>${VM_RAM_MB} MB RAM</rasd:ElementName>
      </Item>
      <Item>
        <rasd:InstanceID>3</rasd:InstanceID>
        <rasd:ResourceType>6</rasd:ResourceType>
        <rasd:ResourceSubType>lsilogic</rasd:ResourceSubType>
        <rasd:Address>0</rasd:Address>
        <rasd:ElementName>SCSI Controller</rasd:ElementName>
      </Item>
      <Item>
        <rasd:InstanceID>4</rasd:InstanceID>
        <rasd:ResourceType>17</rasd:ResourceType>
        <rasd:Parent>3</rasd:Parent>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
        <rasd:HostResource>ovf:/disk/vmdisk1</rasd:HostResource>
        <rasd:ElementName>Disk</rasd:ElementName>
      </Item>
      <Item>
        <rasd:InstanceID>5</rasd:InstanceID>
        <rasd:ResourceType>10</rasd:ResourceType>
        <rasd:ResourceSubType>VmxNet3</rasd:ResourceSubType>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>VM Network</rasd:Connection>
        <rasd:ElementName>Network Adapter</rasd:ElementName>
      </Item>
    </VirtualHardwareSection>
  </VirtualSystem>
</Envelope>
OVFEOF

# ── SHA-256 manifest ──────────────────────────────────────────────────────────
log "Computing checksums…"
OVF_HASH=$(sha256sum  "$OVF"  | cut -d' ' -f1)
VMDK_HASH=$(sha256sum "$VMDK" | cut -d' ' -f1)
cat > "$MF" <<MFEOF
SHA256(${VM_NAME}.ovf)= ${OVF_HASH}
SHA256(${VM_NAME}-disk1.vmdk)= ${VMDK_HASH}
MFEOF

# ── Package OVA ───────────────────────────────────────────────────────────────
log "Packaging OVA…"
tar -C "$OVA_WORK" -cf "$OVA_PATH" \
  "${VM_NAME}.ovf" "${VM_NAME}-disk1.vmdk" "${VM_NAME}.mf"

ok "OVA written: ${OVA_PATH}  ($(du -sh "$OVA_PATH" | cut -f1))"

# ── Restart VM if it was running ──────────────────────────────────────────────
if [[ "$STARTED" == "true" ]]; then
  log "Restarting VM…"
  virsh start "$VM_NAME"
  ok "VM restarted."
fi

echo
echo "============================================================"
echo "  OVA : ${OVA_PATH}"
echo ""
echo "  Import into VMware vSphere / Workstation / ESXi"
echo "  with 'File → Deploy OVF Template' (or 'Open VM')"
echo "============================================================"
