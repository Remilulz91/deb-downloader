#!/usr/bin/env bash
# deb-downloader — interactive installer (Debian 13 / Ubuntu, plain HTTP).
# Copyright (c) 2026 Remilulz91. All rights reserved.
#
# Reproduces DEPLOY.md from start to finish:
#   - Docker Engine
#   - the project (git clone into your chosen directory)
#   - the website (nginx in Docker)
#   - the engine/API as a systemd service (FastAPI/uvicorn on port 8000)
#   - optional tuning (jobs directory, per-job size limit)
#   - optional hardening (UFW firewall, fail2ban for SSH and/or nginx)
#
# The script PAUSES to ask for each value it needs (press Enter to accept the
# shown default), and asks y/n before every OPTIONAL step. Nothing uses HTTPS.
#
# Usage (run as root):
#   sudo bash deploy/install.sh
#
# Or fetched standalone:
#   curl -fsSL https://raw.githubusercontent.com/Remilulz91/deb-downloader/main/deploy/install.sh -o install.sh
#   sudo bash install.sh
#
set -euo pipefail

# --------------------------------------------------------------------------
# Pretty output
# --------------------------------------------------------------------------
c_blue=$'\033[1;34m'; c_grn=$'\033[1;32m'; c_yel=$'\033[1;33m'
c_red=$'\033[1;31m';  c_dim=$'\033[2m';    c_off=$'\033[0m'
step(){ echo; echo "${c_blue}==> $*${c_off}"; }
ok(){   echo "${c_grn}  OK${c_off} $*"; }
warn(){ echo "${c_yel}  ! ${c_off}$*"; }
die(){  echo "${c_red}  ERROR:${c_off} $*" >&2; exit 1; }
trap 'die "Installation interrupted (around line $LINENO)."' ERR

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
# ask VAR "prompt" "default"  -> reads a value (Enter keeps the default)
ask(){
  local __var="$1" __prompt="$2" __def="${3:-}" __in=""
  if [ -n "$__def" ]; then
    read -r -p "  ${__prompt} [${__def}]: " __in || true
    __in="${__in:-$__def}"
  else
    read -r -p "  ${__prompt}: " __in || true
  fi
  printf -v "$__var" '%s' "$__in"
}

# yesno "question" default(y|n)  -> returns 0 for yes, 1 for no
yesno(){
  local q="$1" def="${2:-n}" ans="" hint="[y/N]"
  [ "$def" = "y" ] && hint="[Y/n]"
  read -r -p "  ${q} ${hint}: " ans || true
  ans="${ans:-$def}"
  case "$ans" in y|Y|yes|YES|o|O|oui|OUI) return 0;; *) return 1;; esac
}

# run a command as the target (non-root) user, with a login shell
as_user(){ sudo -u "$RUN_USER" -H bash -lc "$*"; }

[ "$(id -u)" -eq 0 ] || die "Please run as root:  sudo bash $0"

# --------------------------------------------------------------------------
# 0. Gather settings (interactive)
# --------------------------------------------------------------------------
echo "${c_blue}deb-downloader installer${c_off} ${c_dim}— plain HTTP, local network${c_off}"
echo "This installs Docker, the website (nginx) and the engine/API."
echo "Press Enter to accept each [default]. You'll be asked y/n for optional parts."
echo

# Required values
default_user="${SUDO_USER:-}"
[ -z "$default_user" ] && default_user="$(getent passwd 1000 2>/dev/null | cut -d: -f1)"
[ -z "$default_user" ] && default_user="debdownloader"
ask RUN_USER    "System user that will OWN the project and RUN the API" "$default_user"
id "$RUN_USER" >/dev/null 2>&1 || die "User '$RUN_USER' does not exist. Create it first:  sudo adduser $RUN_USER"

ask PROJECT_DIR "Install directory"        "/var/www/deb-downloader"
ask REPO_URL    "Git repository URL"       "https://github.com/Remilulz91/deb-downloader.git"
ask WEB_PORT    "Website HTTP port"        "80"

# Optional: restrict website to localhost
LOCALHOST_ONLY=0
yesno "Make the website reachable from the LOCAL machine only (not the LAN)?" n && LOCALHOST_ONLY=1

# Optional: custom jobs/working directory
JOBS_DIR=""
if yesno "OPTIONAL — set a custom working/jobs directory (recommended if /tmp is small)?" y; then
  ask JOBS_DIR "Jobs directory" "/var/lib/deb-downloader-jobs"
fi

# Optional: per-job size limit
MAX_JOB_MB=""
if yesno "OPTIONAL — set a per-job size limit (reject sets larger than N MB)?" n; then
  ask MAX_JOB_MB "Max MB per job (0 = unlimited)" "2000"
fi

# Optional: UFW firewall
DO_UFW=0
yesno "OPTIONAL — enable the UFW firewall (allow SSH + web, close the rest)?" n && DO_UFW=1

# Optional: fail2ban
DO_F2B=0; DO_F2B_NGINX=0
if yesno "OPTIONAL — install fail2ban to protect SSH?" n; then
  DO_F2B=1
  yesno "  …also enable the fail2ban jail for nginx (advanced)?" n && DO_F2B_NGINX=1
fi

# Confirm
echo
step "Summary"
echo "  user            : $RUN_USER"
echo "  directory       : $PROJECT_DIR"
echo "  repository      : $REPO_URL"
echo "  website port    : $WEB_PORT $( [ "$LOCALHOST_ONLY" -eq 1 ] && echo '(localhost only)')"
echo "  jobs directory  : ${JOBS_DIR:-<system temp (default)>}"
echo "  per-job limit   : ${MAX_JOB_MB:-<unlimited>}"
echo "  UFW firewall    : $( [ "$DO_UFW" -eq 1 ] && echo yes || echo no)"
echo "  fail2ban (SSH)  : $( [ "$DO_F2B" -eq 1 ] && echo yes || echo no)"
echo "  fail2ban (nginx): $( [ "$DO_F2B_NGINX" -eq 1 ] && echo yes || echo no)"
echo
yesno "Proceed with these settings?" y || die "Aborted by user — nothing was changed."

export DEBIAN_FRONTEND=noninteractive

# --------------------------------------------------------------------------
# 1. Base system + tools  (DEPLOY.md §1, §3)
# --------------------------------------------------------------------------
step "Updating package lists and installing base tools"
apt-get update -y
apt-get install -y ca-certificates curl gnupg git lsb-release apt-transport-https
ok "Base tools installed"

# --------------------------------------------------------------------------
# 2. Docker Engine  (DEPLOY.md §2)
# --------------------------------------------------------------------------
if command -v docker >/dev/null 2>&1; then
  ok "Docker already installed ($(docker --version 2>/dev/null || echo present))"
else
  step "Installing Docker Engine"
  . /etc/os-release
  os_id="${ID:-debian}"; [ "$os_id" = "ubuntu" ] || os_id="debian"
  codename="${VERSION_CODENAME:-trixie}"
  install -m 0755 -d /usr/share/keyrings
  curl -fsSL "https://download.docker.com/linux/${os_id}/gpg" \
    | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
  chmod a+r /usr/share/keyrings/docker-archive-keyring.gpg
  echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/${os_id} ${codename} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  ok "Docker installed and started"
fi

# Make sure the Compose plugin is available (older Docker installs may lack it)
if ! docker compose version >/dev/null 2>&1; then
  warn "Docker Compose plugin missing — installing it"
  apt-get install -y docker-compose-plugin
fi

# --------------------------------------------------------------------------
# 3. Engine dependencies  (DEPLOY.md §8)
# --------------------------------------------------------------------------
step "Installing engine dependencies (dpkg-dev, python venv)"
apt-get install -y dpkg-dev python3-venv python3-pip
usermod -aG docker "$RUN_USER"
ok "Engine dependencies installed; '$RUN_USER' added to the docker group"

# --------------------------------------------------------------------------
# 4. Fetch the project  (DEPLOY.md §3)
# --------------------------------------------------------------------------
step "Fetching the project into $PROJECT_DIR"
mkdir -p "$(dirname "$PROJECT_DIR")"
if [ -d "$PROJECT_DIR/.git" ]; then
  warn "Already present — updating with git pull"
  chown -R "$RUN_USER":"$RUN_USER" "$PROJECT_DIR"
  as_user "cd '$PROJECT_DIR' && git pull --ff-only" || warn "git pull skipped (local changes?)"
else
  git clone "$REPO_URL" "$PROJECT_DIR"
  chown -R "$RUN_USER":"$RUN_USER" "$PROJECT_DIR"
fi
[ -f "$PROJECT_DIR/backend/app.py" ] || die "Project layout unexpected: $PROJECT_DIR/backend/app.py not found."
ok "Project ready"

# --------------------------------------------------------------------------
# 5. Python virtual environment  (DEPLOY.md §9) — as the target user
# --------------------------------------------------------------------------
step "Creating the Python virtual environment (as $RUN_USER)"
as_user "cd '$PROJECT_DIR/backend' && python3 -m venv .venv && . .venv/bin/activate && pip install --upgrade pip -q && pip install -r requirements.txt -q"
ok "Virtual environment ready"

# --------------------------------------------------------------------------
# 6. Optional jobs directory
# --------------------------------------------------------------------------
if [ -n "$JOBS_DIR" ]; then
  step "Creating jobs directory: $JOBS_DIR"
  mkdir -p "$JOBS_DIR"
  chown "$RUN_USER":"$RUN_USER" "$JOBS_DIR"
  ok "Jobs directory ready"
fi

# --------------------------------------------------------------------------
# 7. systemd service  (DEPLOY.md §11)
# --------------------------------------------------------------------------
step "Installing the systemd service (deb-downloader-api)"
svc="/etc/systemd/system/deb-downloader-api.service"
cp "$PROJECT_DIR/deploy/deb-downloader-api.service" "$svc"
sed -i \
  -e "s|^User=.*|User=${RUN_USER}|" \
  -e "s|^Group=.*|Group=${RUN_USER}|" \
  -e "s|^WorkingDirectory=.*|WorkingDirectory=${PROJECT_DIR}/backend|" \
  -e "s|^ExecStart=.*|ExecStart=${PROJECT_DIR}/backend/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000|" \
  "$svc"

# Environment drop-in (jobs dir / quota) if requested
if [ -n "$JOBS_DIR" ] || [ -n "$MAX_JOB_MB" ]; then
  dropd="/etc/systemd/system/deb-downloader-api.service.d"
  mkdir -p "$dropd"
  {
    echo "[Service]"
    [ -n "$JOBS_DIR" ]   && echo "Environment=DDL_JOBS_DIR=${JOBS_DIR}"
    [ -n "$MAX_JOB_MB" ] && echo "Environment=DDL_MAX_JOB_MB=${MAX_JOB_MB}"
  } > "$dropd/override.conf"
  ok "Service environment drop-in written"
fi

systemctl daemon-reload
systemctl enable --now deb-downloader-api
ok "API service enabled and started"

# --------------------------------------------------------------------------
# 8. Website — nginx in Docker  (DEPLOY.md §4, §6 caveat, §12)
# --------------------------------------------------------------------------
step "Starting the website (nginx in Docker)"
compose="$PROJECT_DIR/deploy/docker-compose.yml"

# Point the compose volume host paths at the chosen directory (no-op if default)
sed -i "s|/var/www/deb-downloader|${PROJECT_DIR}|g" "$compose"

# Adjust the published port / localhost binding
if [ "$LOCALHOST_ONLY" -eq 1 ]; then
  sed -i -E "s|^([[:space:]]*-[[:space:]]*\")[0-9.:]*80:80(\".*)|\1127.0.0.1:${WEB_PORT}:80\2|" "$compose"
elif [ "$WEB_PORT" != "80" ]; then
  sed -i -E "s|^([[:space:]]*-[[:space:]]*\")[0-9.:]*80:80(\".*)|\1${WEB_PORT}:80\2|" "$compose"
fi

# Optional nginx fail2ban: expose the container logs to the host
if [ "$DO_F2B_NGINX" -eq 1 ]; then
  sed -i -E "s|^([[:space:]]*)#[[:space:]]*-[[:space:]]*/var/log/deb-downloader-nginx:/var/log/nginx|\1- /var/log/deb-downloader-nginx:/var/log/nginx|" "$compose"
  mkdir -p /var/log/deb-downloader-nginx
fi

( cd "$PROJECT_DIR" && docker compose -f deploy/docker-compose.yml up -d --force-recreate )
ok "Website container started"

# --------------------------------------------------------------------------
# 9. Optional — UFW firewall  (DEPLOY.md §6, §12)
# --------------------------------------------------------------------------
if [ "$DO_UFW" -eq 1 ]; then
  step "Configuring the UFW firewall"
  apt-get install -y ufw
  ufw --force default deny incoming
  ufw --force default allow outgoing
  ufw allow 22/tcp                                   # SSH
  ufw allow "${WEB_PORT}/tcp"                        # website
  ufw allow from 172.20.0.0/24 to any port 8000 proto tcp   # API, container only
  ufw --force enable
  ok "UFW enabled (SSH + port ${WEB_PORT}; API reachable only from the web container)"
  warn "Docker can bypass UFW for published ports — fine on a local machine."
fi

# --------------------------------------------------------------------------
# 10. Optional — fail2ban  (DEPLOY.md §7)
# --------------------------------------------------------------------------
if [ "$DO_F2B" -eq 1 ]; then
  step "Installing fail2ban"
  apt-get install -y fail2ban
  cp "$PROJECT_DIR/deploy/fail2ban/jail.local" /etc/fail2ban/jail.local
  if [ "$DO_F2B_NGINX" -eq 1 ]; then
    # enable = true under [nginx-bad-request]
    awk '
      /^\[nginx-bad-request\]/ {inj=1}
      inj && /^enabled[[:space:]]*=/ {sub(/=.*/,"= true"); inj=0}
      {print}
    ' /etc/fail2ban/jail.local > /etc/fail2ban/jail.local.tmp \
      && mv /etc/fail2ban/jail.local.tmp /etc/fail2ban/jail.local
    ok "nginx jail enabled"
  fi
  systemctl enable --now fail2ban
  systemctl restart fail2ban
  ok "fail2ban active"
fi

# --------------------------------------------------------------------------
# 11. Verify + summary
# --------------------------------------------------------------------------
step "Verifying"
sleep 2
if curl -fsS "http://localhost:8000/healthz" >/dev/null 2>&1; then
  ok "API healthy on :8000"
else
  warn "API not responding yet on :8000 — check: journalctl -u deb-downloader-api -e"
fi
if curl -fsS "http://localhost:${WEB_PORT}/" >/dev/null 2>&1; then
  ok "Website responding on :${WEB_PORT}"
else
  warn "Website not responding yet on :${WEB_PORT} — check: docker logs deb-downloader-web"
fi

ip_addr="$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1 || true)"
port_sfx=""; [ "$WEB_PORT" != "80" ] && port_sfx=":${WEB_PORT}"

echo
echo "${c_grn}============================================================${c_off}"
echo "${c_grn} deb-downloader is installed and running.${c_off}"
echo "------------------------------------------------------------"
echo "  ${c_blue}Use the tool:${c_off}     http://localhost${port_sfx}/app"
[ -n "$ip_addr" ] && [ "$LOCALHOST_ONLY" -eq 0 ] && \
echo "  ${c_blue}From the LAN:${c_off}     http://${ip_addr}${port_sfx}/app"
echo "  ${c_blue}Landing page:${c_off}     http://localhost${port_sfx}/"
echo
echo "  ${c_dim}Service status:   sudo systemctl status deb-downloader-api${c_off}"
echo "  ${c_dim}Service logs:     journalctl -u deb-downloader-api -f${c_off}"
echo "  ${c_dim}Update later:     cd ${PROJECT_DIR} && git pull && sudo systemctl restart deb-downloader-api${c_off}"
echo "${c_grn}============================================================${c_off}"

if id -nG "$RUN_USER" | grep -qw docker; then :; fi
warn "If you plan to run 'docker' as ${RUN_USER} in a shell, log out/in once (or run: newgrp docker)."
echo "  The API service already has Docker access — no action needed for the tool itself."
