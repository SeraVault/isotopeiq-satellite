#!/usr/bin/env bash
# build-vm.sh — Boot a Fedora 41 Cloud VM, deploy IsotopeIQ Satellite via SSH.
# Run from the root of the isotopeiq-satellite-2 directory.
set -euo pipefail

# ── Config ─────────────────────────────────────────────────────────────────────
VM_NAME="isotopeiq-satellite"
VM_RAM_MB=4096
VM_VCPUS=4
VM_DISK_GB=30
VM_IMAGE_DIR="${HOME}/kvm-images"
FEDORA_VERSION=41

FEDORA_IMAGE_URL="https://dl.fedoraproject.org/pub/archive/fedora/linux/releases/${FEDORA_VERSION}/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-${FEDORA_VERSION}-1.4.x86_64.qcow2"
FEDORA_IMAGE_NAME="Fedora-Cloud-Base-Generic-${FEDORA_VERSION}-1.4.x86_64.qcow2"

BASE_IMAGE="${VM_IMAGE_DIR}/${FEDORA_IMAGE_NAME}"
VM_DISK="${VM_IMAGE_DIR}/${VM_NAME}.qcow2"
OVA_PATH="${VM_IMAGE_DIR}/${VM_NAME}.ova"

# Temporary root password used only during build — changed to key-only after deploy
BUILD_PASSWORD="IsoTempBuild99!"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o LogLevel=ERROR"

# ── Colours ───────────────────────────────────────────────────────────────────
log()  { echo -e "\033[1;34m[build-vm]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
warn() { echo -e "\033[1;33m[ WARN ]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ ERR  ]\033[0m $*" >&2; exit 1; }

# ── Preflight ─────────────────────────────────────────────────────────────────
log "Checking prerequisites…"
for cmd in virt-install virsh qemu-img curl python3 rsync ssh sshpass; do
  command -v "$cmd" >/dev/null 2>&1 || die "Required tool not found: $cmd  (install with: sudo apt install $cmd)"
done
ok "All tools present."

[[ -f "${PROJECT_DIR}/deploy.sh" ]] || die "Run this script from the isotopeiq-satellite-2 root directory."

AVAIL_MB=$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo)
if (( AVAIL_MB < VM_RAM_MB )); then
  warn "Only ${AVAIL_MB} MB RAM available; VM needs ${VM_RAM_MB} MB."
  warn "Consider suspending a running VM first (e.g. virsh suspend win11)"
  read -r -p "Continue anyway? (y/N) " yn
  [[ "$yn" =~ ^[Yy]$ ]] || { log "Aborted."; exit 0; }
fi

if virsh dominfo "$VM_NAME" &>/dev/null; then
  die "VM '$VM_NAME' already exists. Remove it first:
  virsh destroy ${VM_NAME} 2>/dev/null; virsh undefine --remove-all-storage ${VM_NAME}"
fi

# ── Generate .env ─────────────────────────────────────────────────────────────
log "Generating .env with fresh secrets…"
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
FIELD_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

cat > "${PROJECT_DIR}/.env" <<EOF
SECRET_KEY=${SECRET_KEY}
FIELD_ENCRYPTION_KEY=${FIELD_ENCRYPTION_KEY}

DB_NAME=isotopeiq
DB_USER=isotopeiq
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/0

ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
SATELLITE_URL=http://localhost:8000

SYSLOG_HOST=localhost
SYSLOG_PORT=514
SYSLOG_FACILITY=local0

LDAP_SERVER_URI=ldap://your-ldap-server:389
LDAP_BIND_DN=cn=readonly,dc=example,dc=com
LDAP_BIND_PASSWORD=
LDAP_START_TLS=False
LDAP_USER_SEARCH_BASE=ou=users,dc=example,dc=com
LDAP_USER_SEARCH_FILTER=(uid=%(user)s)
LDAP_GROUP_SEARCH_BASE=ou=groups,dc=example,dc=com
LDAP_ATTR_FIRST_NAME=givenName
LDAP_ATTR_LAST_NAME=sn
LDAP_ATTR_EMAIL=mail
LDAP_SUPERUSER_GROUP=cn=admins,ou=groups,dc=example,dc=com
LDAP_STAFF_GROUP=cn=staff,ou=groups,dc=example,dc=com

SAML_SP_ENTITY_ID=https://your-app.example.com/saml2/metadata/
SAML_ACS_URL=https://your-app.example.com/saml2/acs/
SAML_SLS_URL=https://your-app.example.com/saml2/ls/
SAML_IDP_METADATA_URL=https://your-idp.example.com/metadata
SAML_IDP_METADATA_FILE=
SAML_SP_KEY_FILE=
SAML_SP_CERT_FILE=
EOF
ok ".env written (DB_PASSWORD: ${DB_PASSWORD})"

# ── Download base image ────────────────────────────────────────────────────────
mkdir -p "$VM_IMAGE_DIR"
if [[ ! -f "$BASE_IMAGE" ]]; then
  log "Downloading Fedora ${FEDORA_VERSION} Cloud image (~550 MB)…"
  curl -L --progress-bar -o "$BASE_IMAGE" "$FEDORA_IMAGE_URL"
  ok "Download complete."
else
  ok "Base image cached: $BASE_IMAGE"
fi

# ── Create VM disk (flat copy, not overlay) ────────────────────────────────────
log "Creating ${VM_DISK_GB} GB VM disk…"
qemu-img convert -f qcow2 -O qcow2 "$BASE_IMAGE" "$VM_DISK"
qemu-img resize "$VM_DISK" "${VM_DISK_GB}G"
ok "Disk ready: $VM_DISK"

# ── Build cloud-init seed ISO ──────────────────────────────────────────────────
# The Fedora Cloud image requires cloud-init to configure it on first boot.
# We use a NoCloud seed to set the root password and enable SSH password auth.
log "Building cloud-init seed ISO…"
SEED_DIR=$(mktemp -d "${VM_IMAGE_DIR}/isotopeiq-seed-XXXXXX")
chmod 755 "$SEED_DIR"
trap 'rm -rf "$SEED_DIR"' EXIT

# Hash the build password for cloud-init (openssl avoids deprecated Python crypt)
HASHED_PW=$(openssl passwd -6 "${BUILD_PASSWORD}")

cat > "${SEED_DIR}/meta-data" <<EOF
instance-id: ${VM_NAME}
local-hostname: ${VM_NAME}
EOF

cat > "${SEED_DIR}/user-data" <<EOF
#cloud-config
ssh_pwauth: true
disable_root: false
chpasswd:
  list: |
    root:${BUILD_PASSWORD}
    isotopeiq:${BUILD_PASSWORD}
  expire: false
users:
  - name: isotopeiq
    groups: wheel
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
runcmd:
  - sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
  - sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
  - systemctl restart sshd
EOF

cloud-localds "${SEED_DIR}/seed.iso" "${SEED_DIR}/user-data" "${SEED_DIR}/meta-data"
ok "Seed ISO ready."

# ── Start VM ──────────────────────────────────────────────────────────────────
log "Starting VM '${VM_NAME}'…"
virt-install \
  --name "$VM_NAME" \
  --memory "$VM_RAM_MB" \
  --vcpus "$VM_VCPUS" \
  --disk "path=${VM_DISK},format=qcow2,bus=virtio" \
  --disk "path=${SEED_DIR}/seed.iso,device=cdrom,bus=sata" \
  --import \
  --os-variant fedora41 \
  --network network=default,model=virtio \
  --graphics none \
  --noautoconsole \
  --wait 0
ok "VM started."

# ── Wait for SSH ──────────────────────────────────────────────────────────────
log "Waiting for VM to boot and SSH to come up…"
VM_IP=""
for i in $(seq 1 60); do
  VM_IP=$(virsh domifaddr "$VM_NAME" 2>/dev/null | awk '/ipv4/ {print $4}' | cut -d/ -f1 | head -1)
  if [[ -n "$VM_IP" ]]; then
    if sshpass -p "$BUILD_PASSWORD" ssh $SSH_OPTS "isotopeiq@${VM_IP}" true 2>/dev/null; then
      break
    fi
  fi
  printf "."
  sleep 5
done
echo
[[ -n "$VM_IP" ]] || die "VM did not get an IP after 5 minutes."
ok "VM is up at ${VM_IP}"

# ── Deploy ────────────────────────────────────────────────────────────────────
log "Preparing destination directory on VM…"
sshpass -p "$BUILD_PASSWORD" ssh $SSH_OPTS "isotopeiq@${VM_IP}" \
  "sudo mkdir -p /opt/isotopeiq-satellite && sudo chown isotopeiq:isotopeiq /opt/isotopeiq-satellite"

log "Copying project files to VM…"
rsync -a --progress \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='.DS_Store' \
  --exclude='node_modules' \
  --exclude='*.egg-info' \
  --exclude='.venv' \
  --exclude='venv' \
  -e "sshpass -p '${BUILD_PASSWORD}' ssh ${SSH_OPTS}" \
  "${PROJECT_DIR}/" "isotopeiq@${VM_IP}:/opt/isotopeiq-satellite/"
ok "Files copied."

log "Installing Docker and starting IsotopeIQ…"
sshpass -p "$BUILD_PASSWORD" ssh $SSH_OPTS "fedora@${VM_IP}" bash <<'REMOTE'
set -euo pipefail

# Grow filesystem to use full disk
sudo growpart /dev/vda 3 2>/dev/null || true
sudo btrfs filesystem resize max / 2>/dev/null || sudo xfs_growfs / 2>/dev/null || true

# Install Docker CE
curl -fsSL https://download.docker.com/linux/fedora/docker-ce.repo \
  | sudo tee /etc/yum.repos.d/docker-ce.repo > /dev/null
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker isotopeiq

# Fix agent binary permissions
chmod +x /opt/isotopeiq-satellite/agents/linux_collector_amd64 \
         /opt/isotopeiq-satellite/agents/linux_collector_i686 \
         /opt/isotopeiq-satellite/agents/installers/linux_install.sh \
         2>/dev/null || true

# Start the application (new shell so docker group membership applies)
sudo -u isotopeiq bash -c '
  cd /opt/isotopeiq-satellite
  chmod +x deploy.sh
  newgrp docker <<NEWGRP
    cd /opt/isotopeiq-satellite
    ./deploy.sh up
NEWGRP
'
REMOTE
ok "IsotopeIQ is running."

# ── Export OVA ────────────────────────────────────────────────────────────────
log "Shutting VM down cleanly for OVA export…"
virsh shutdown "$VM_NAME" --mode acpi
for i in $(seq 1 30); do
  [[ "$(virsh domstate "$VM_NAME")" == "shut off" ]] && break
  sleep 3
done
[[ "$(virsh domstate "$VM_NAME")" == "shut off" ]] || { warn "VM didn't shut down cleanly, forcing…"; virsh destroy "$VM_NAME"; }
ok "VM shut down."

log "Exporting OVA for VMware…"
OVA_WORK=$(mktemp -d /tmp/isotopeiq-ova-XXXXXX)
VMDK="${OVA_WORK}/${VM_NAME}-disk1.vmdk"
OVF="${OVA_WORK}/${VM_NAME}.ovf"
MF="${OVA_WORK}/${VM_NAME}.mf"

qemu-img convert -f qcow2 -O vmdk \
  -o subformat=streamOptimized,adapter_type=lsilogic \
  "$VM_DISK" "$VMDK"

DISK_SIZE_GB=$(python3 -c "
import json, subprocess
d = json.loads(subprocess.check_output(['qemu-img','info','--output','json','${VMDK}']))
print((d['virtual-size'] + 2**30 - 1) // 2**30)
")

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
      <Description>Fedora Linux 64-bit</Description>
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

OVF_HASH=$(sha256sum  "$OVF"  | cut -d' ' -f1)
VMDK_HASH=$(sha256sum "$VMDK" | cut -d' ' -f1)
cat > "$MF" <<MFEOF
SHA256(${VM_NAME}.ovf)= ${OVF_HASH}
SHA256(${VM_NAME}-disk1.vmdk)= ${VMDK_HASH}
MFEOF

tar -C "$OVA_WORK" -cf "$OVA_PATH" \
  "${VM_NAME}.ovf" "${VM_NAME}-disk1.vmdk" "${VM_NAME}.mf"
rm -rf "$OVA_WORK"
ok "OVA written: ${OVA_PATH}  ($(du -sh "$OVA_PATH" | cut -f1))"

# Restart the VM now that export is done
virsh start "$VM_NAME"
ok "VM restarted."

echo
echo "============================================================"
echo "  VM IP   : ${VM_IP}"
echo "  SSH     : ssh fedora@${VM_IP}   password: ${BUILD_PASSWORD}"
echo "  Frontend: http://${VM_IP}:5173"
echo "  Backend : http://${VM_IP}:8000/api/v1/"
echo ""
echo "  Create the app admin user:"
echo "    ssh fedora@${VM_IP}"
echo "    cd /opt/isotopeiq-satellite && ./deploy.sh createsuperuser"
echo ""
echo "  VMware OVA: ${OVA_PATH}"
echo "  Secrets   : ${PROJECT_DIR}/.env"
echo "============================================================"
