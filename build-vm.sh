#!/usr/bin/env bash
# build-vm.sh — Build a Fedora 41 KVM VM with IsotopeIQ Satellite pre-installed.
# Run from the root of the isotopeiq-satellite-2 directory.
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
VM_NAME="isotopeiq-satellite"
VM_RAM_MB=4096
VM_VCPUS=4
VM_DISK_GB=30
VM_IMAGE_DIR="${HOME}/kvm-images"
FEDORA_VERSION=41

FEDORA_IMAGE_URL="https://download.fedoraproject.org/pub/fedora/linux/releases/${FEDORA_VERSION}/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-${FEDORA_VERSION}-1.4.x86_64.qcow2"
FEDORA_IMAGE_NAME="Fedora-Cloud-Base-Generic-${FEDORA_VERSION}-1.4.x86_64.qcow2"

BASE_IMAGE="${VM_IMAGE_DIR}/${FEDORA_IMAGE_NAME}"
VM_DISK="${VM_IMAGE_DIR}/${VM_NAME}.qcow2"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Colours ───────────────────────────────────────────────────────────────────
log()  { echo -e "\033[1;34m[build-vm]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
warn() { echo -e "\033[1;33m[ WARN ]\033[0m $*"; }
err()  { echo -e "\033[1;31m[ ERR  ]\033[0m $*" >&2; }
die()  { err "$*"; exit 1; }

# ── Preflight ─────────────────────────────────────────────────────────────────
log "Checking prerequisites…"
for cmd in virt-install virsh qemu-img virt-customize curl python3; do
  command -v "$cmd" >/dev/null 2>&1 || die "Required tool not found: $cmd"
done
ok "All tools present."

# Check we're in the right directory
[[ -f "${PROJECT_DIR}/deploy.sh" ]] || die "Run this script from the isotopeiq-satellite-2 root directory."

# Warn about memory
AVAIL_MB=$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo)
if (( AVAIL_MB < VM_RAM_MB )); then
  warn "Only ${AVAIL_MB} MB RAM available; VM needs ${VM_RAM_MB} MB."
  warn "Consider suspending some of these running VMs first:"
  virsh list | grep running || true
  echo
  read -r -p "Continue anyway? (y/N) " yn
  [[ "$yn" =~ ^[Yy]$ ]] || { log "Aborted."; exit 0; }
fi

# Check VM name not already taken
if virsh dominfo "$VM_NAME" &>/dev/null; then
  die "A VM named '$VM_NAME' already exists. Remove it first:
  virsh destroy ${VM_NAME}
  virsh undefine --remove-all-storage ${VM_NAME}"
fi

# ── Generate .env with real secrets ──────────────────────────────────────────
log "Generating .env with fresh secrets…"

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
# Try to generate Fernet key; install cryptography if needed
FIELD_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null) || {
  pip3 install --quiet cryptography
  FIELD_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
}
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

# Accepts connections from anywhere on the VM's NAT network.
# Tighten this to the VM's actual IP once known.
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
SATELLITE_URL=http://localhost:8000

SYSLOG_HOST=localhost
SYSLOG_PORT=514
SYSLOG_FACILITY=local0

# ── LDAP (optional) ───────────────────────────────────────────────────────────
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

# ── SAML 2.0 (optional) ───────────────────────────────────────────────────────
SAML_SP_ENTITY_ID=https://your-app.example.com/saml2/metadata/
SAML_ACS_URL=https://your-app.example.com/saml2/acs/
SAML_SLS_URL=https://your-app.example.com/saml2/ls/
SAML_IDP_METADATA_URL=https://your-idp.example.com/metadata
SAML_IDP_METADATA_FILE=
SAML_SP_KEY_FILE=
SAML_SP_CERT_FILE=
EOF

ok ".env written."
log "  DB_PASSWORD: ${DB_PASSWORD}"
log "  (back up .env — it contains the encryption key for stored credentials)"

# ── Stage a clean copy of the project for injection ──────────────────────────
# virt-customize --copy-in copies a directory *into* a destination directory,
# so we stage everything under a single parent so the path inside the VM is
# exactly /opt/isotopeiq-satellite with no extra nesting.
STAGE_DIR=$(mktemp -d /tmp/isotopeiq-stage-XXXXXX)
trap 'rm -rf "$STAGE_DIR"' EXIT

log "Staging project files…"
rsync -a \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='.DS_Store' \
  --exclude='node_modules' \
  --exclude='*.egg-info' \
  --exclude='.venv' \
  --exclude='venv' \
  "${PROJECT_DIR}/" "${STAGE_DIR}/isotopeiq-satellite/"

# Confirm .env and agents are present in the stage
[[ -f "${STAGE_DIR}/isotopeiq-satellite/.env" ]]     || die "Staged .env missing"
[[ -d "${STAGE_DIR}/isotopeiq-satellite/agents" ]]   || die "Staged agents/ missing"
[[ -d "${STAGE_DIR}/isotopeiq-satellite/examples" ]] || die "Staged examples/ missing"
[[ -d "${STAGE_DIR}/isotopeiq-satellite/backend" ]]  || die "Staged backend/ missing"
[[ -d "${STAGE_DIR}/isotopeiq-satellite/frontend" ]] || die "Staged frontend/ missing"
ok "Project staged at ${STAGE_DIR}/isotopeiq-satellite"

# ── Write first-boot script ───────────────────────────────────────────────────
FIRSTBOOT=$(mktemp /tmp/isotopeiq-firstboot-XXXXXX.sh)
cat > "$FIRSTBOOT" <<'FIRSTBOOT_EOF'
#!/usr/bin/env bash
set -euo pipefail
exec > /var/log/isotopeiq-firstboot.log 2>&1
echo "=== IsotopeIQ Satellite first-boot: $(date) ==="

# ── Grow root filesystem to use the full disk ─────────────────────────────
# Fedora Cloud uses btrfs on vda3 with vda4 as a small biosboot partition.
# Try common partition layouts; ignore errors.
growpart /dev/vda 3 2>/dev/null || growpart /dev/vda 5 2>/dev/null || true
btrfs filesystem resize max / 2>/dev/null || xfs_growfs / 2>/dev/null || resize2fs /dev/vda3 2>/dev/null || true

# ── System update ─────────────────────────────────────────────────────────
dnf -y upgrade --refresh
dnf -y install curl git python3 dnf-plugins-core

# ── Docker CE ─────────────────────────────────────────────────────────────
dnf config-manager addrepo --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo
dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
usermod -aG docker satellite

# ── Fix agent binary permissions ──────────────────────────────────────────
chmod +x /opt/isotopeiq-satellite/agents/linux_collector_amd64 \
         /opt/isotopeiq-satellite/agents/linux_collector_i686 \
         /opt/isotopeiq-satellite/agents/macos_collector \
         /opt/isotopeiq-satellite/agents/installers/linux_install.sh \
         /opt/isotopeiq-satellite/agents/installers/macos_install.sh \
         2>/dev/null || true

# ── Start the application ─────────────────────────────────────────────────
# Must run as 'satellite' so the docker group membership takes effect.
sudo -u satellite bash -c '
  set -euo pipefail
  cd /opt/isotopeiq-satellite
  chmod +x deploy.sh
  ./deploy.sh up
'

VM_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "=== First-boot complete: $(date) ==="
echo "    Frontend: http://${VM_IP}:5173"
echo "    Backend:  http://${VM_IP}:8000/api/v1/"
echo ""
echo "    Next step — create the admin user:"
echo "      ssh satellite@${VM_IP}"
echo "      cd /opt/isotopeiq-satellite && ./deploy.sh createsuperuser"
FIRSTBOOT_EOF
chmod +x "$FIRSTBOOT"

# ── Disk image setup ──────────────────────────────────────────────────────────
mkdir -p "$VM_IMAGE_DIR"

if [[ ! -f "$BASE_IMAGE" ]]; then
  log "Downloading Fedora ${FEDORA_VERSION} Cloud image (~550 MB)…"
  curl -L --progress-bar -o "$BASE_IMAGE" "$FEDORA_IMAGE_URL"
  ok "Download complete: $BASE_IMAGE"
else
  ok "Base image already cached: $BASE_IMAGE"
fi

log "Creating ${VM_DISK_GB} GB VM disk from base image…"
qemu-img create -f qcow2 -b "$BASE_IMAGE" -F qcow2 "$VM_DISK" "${VM_DISK_GB}G"
ok "Disk created: $VM_DISK"

# ── Customise the image ───────────────────────────────────────────────────────
log "Customising image — copying all project files into VM disk…"
log "  (examples/, agents/, backend/, frontend/, deploy.sh, .env, docker-compose.yml, etc.)"
log "  This takes a few minutes…"

virt-customize \
  --add "$VM_DISK" \
  --timezone "UTC" \
  --hostname "${VM_NAME}" \
  --root-password "password:IsotopeAdmin1!" \
  --run-command "useradd -m -s /bin/bash -G wheel satellite" \
  --password "satellite:password:IsotopeAdmin1!" \
  --run-command "echo 'satellite ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/satellite && chmod 440 /etc/sudoers.d/satellite" \
  --copy-in "${STAGE_DIR}/isotopeiq-satellite:/opt" \
  --run-command "chown -R satellite:satellite /opt/isotopeiq-satellite" \
  --firstboot "$FIRSTBOOT" \
  --selinux-relabel

rm -f "$FIRSTBOOT"
ok "Image customised."

# ── Define and start the VM ───────────────────────────────────────────────────
log "Registering and starting VM '${VM_NAME}'…"

virt-install \
  --name "$VM_NAME" \
  --memory "$VM_RAM_MB" \
  --vcpus "$VM_VCPUS" \
  --disk "path=${VM_DISK},format=qcow2,bus=virtio" \
  --import \
  --os-variant fedora41 \
  --network network=default,model=virtio \
  --graphics none \
  --console pty,target_type=serial \
  --noautoconsole \
  --wait 0

echo
echo "============================================================"
echo "  VM '${VM_NAME}' is booting."
echo ""
echo "  First-boot installs Docker and starts all services."
echo "  This takes ~5-10 minutes on first run."
echo ""
echo "  Watch progress (Ctrl+] to detach from console):"
echo "    virsh console ${VM_NAME}"
echo ""
echo "  Or SSH once it has an IP:"
echo "    virsh domifaddr ${VM_NAME}   # find the IP"
echo "    ssh satellite@<vm-ip>        # password: IsotopeAdmin1!"
echo "    tail -f /var/log/isotopeiq-firstboot.log"
echo ""
echo "  After first-boot completes, create the app admin user:"
echo "    ssh satellite@<vm-ip>"
echo "    cd /opt/isotopeiq-satellite && ./deploy.sh createsuperuser"
echo ""
echo "  Then open:  http://<vm-ip>:5173"
echo ""
echo "  Credentials saved in: ${PROJECT_DIR}/.env"
echo "============================================================"
