# Self-hosting deb-downloader — Debian 13

This is the single, step-by-step guide to install **deb-downloader** on your own
machine. It targets **Debian 13 (Trixie)** — a VirtualBox VM, a spare PC, or a
small server — over **plain HTTP on your local network** (no domain, no TLS).

It has two parts:

- **Part 1 — The website**: the landing page, served by nginx in Docker (port 80).
- **Part 2 — The engine & API**: the actual tool that downloads `.deb` packages,
  with a web page to use it. Once set up, the website proxies it at
  `http://<ip>/app` (no port to type). Optional, but it's the whole point.

Everything below is copy-paste. Optional hardening with **UFW** and **fail2ban**
is included.

---

# Part 1 — The website

## 0. What you will get

A web server reachable at:

- `http://localhost` — from the machine itself, and
- `http://<machine-ip>` — from other devices on the same network.

The page presents the project and tells visitors whether they are on the latest
released version.

---

## 1. Prerequisites

- A **Debian 13** system you can `sudo` on.
- **Internet access** (to install packages and pull the nginx image).

Update the system first:

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

---

## 2. Install Docker

Install Docker Engine from Docker's official repository:

```bash
sudo apt-get install apt-transport-https ca-certificates curl gnupg2 lsb-release
sudo curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
sudo echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian trixie stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl status docker
```

Check it works:

```bash
sudo docker run --rm hello-world
```

---

## 3. Get the project into /var/www

```bash
sudo apt-get install -y git
sudo mkdir -p /var/www
sudo git clone https://github.com/Remilulz91/deb-downloader.git /var/www/deb-downloader

# Make the project yours (needed for updates, and for the engine in Part 2)
sudo chown -R "$USER":"$USER" /var/www/deb-downloader
```

---

## 4. Start the website (nginx in Docker)

The repository ships a ready-to-use nginx config and a Compose file in
`deploy/`. Just start it:

```bash
cd /var/www/deb-downloader
sudo docker compose -f deploy/docker-compose.yml up -d
```

Verify the container is running:

```bash
sudo docker ps
```

You should see `deb-downloader-web` listening on port 80.

> **How it works:** nginx serves the cloned folder read-only as its web root.
> The provided config (`deploy/nginx.conf`) hides everything that is not the
> public site (`.git`, `backend/`, `deploy/`, `*.md`, `*.py`, `*.yml`).

---

## 5. Open the site

- **On the machine itself:** open `http://localhost`
- **From another device on the LAN:** find the IP and use it:

```bash
ip -4 addr show | grep inet
```

Then browse to `http://<that-ip>`.

> **VirtualBox note:** if your VM uses the default **NAT** adapter, the LAN
> can't reach it directly. Either switch the adapter to **Bridged** (VM gets a
> LAN IP), or add a **port forward** (Host `8080` → Guest `80`) and browse to
> `http://localhost:8080` from the host. For testing inside the VM,
> `http://localhost` always works.

---

## 6. (Optional) Firewall with UFW

```bash
sudo apt-get install -y ufw

sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH — keep this if you connect remotely
sudo ufw allow 80/tcp      # HTTP — the website
sudo ufw enable
sudo ufw status verbose
```

> **Important caveat:** Docker publishes container ports by editing `iptables`
> directly, which can **bypass UFW**. On a local/test machine this is usually
> fine. If you want the site reachable **only from the machine itself**, bind
> the port to localhost instead — edit `deploy/docker-compose.yml`:
>
> ```yaml
>     ports:
>       - "127.0.0.1:80:80"
> ```
>
> then `sudo docker compose -f deploy/docker-compose.yml up -d` again.

---

## 7. (Optional) fail2ban

fail2ban bans IPs that repeatedly fail authentication. The ready-made config
protects **SSH** out of the box (most useful as soon as the machine is on a
network).

```bash
sudo apt-get install -y fail2ban
sudo cp /var/www/deb-downloader/deploy/fail2ban/jail.local /etc/fail2ban/jail.local
sudo systemctl enable --now fail2ban
sudo systemctl restart fail2ban

# Check
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

### Optional: also protect nginx (advanced)

Because nginx runs in Docker, its logs stay inside the container by default.
To feed them to fail2ban:

1. In `deploy/docker-compose.yml`, **uncomment** the log volume line:
   ```yaml
       - /var/log/deb-downloader-nginx:/var/log/nginx
   ```
2. Create the folder and recreate the container:
   ```bash
   sudo mkdir -p /var/log/deb-downloader-nginx
   cd /var/www/deb-downloader
   sudo docker compose -f deploy/docker-compose.yml up -d --force-recreate
   ```
3. In `/etc/fail2ban/jail.local`, set `enabled = true` under `[nginx-bad-request]`,
   then `sudo systemctl restart fail2ban`.

---

# Part 2 — The engine & API

The website is just the front page. The **engine** is what actually downloads a
package and all its dependencies. It runs on this same machine (it uses Docker)
and gives you a small web page to pick a distribution + packages and download a
`.zip`. The API listens on **port 8000**.

## 8. Install the engine dependencies

Docker is already installed (Part 1). Add `dpkg-dev` (to build the offline
repository) and the Python venv tooling, and let your user use Docker:

```bash
sudo apt-get install -y dpkg-dev python3-venv
sudo usermod -aG docker "$USER"      # then log out/in (or run: newgrp docker)
```

> The `docker` group membership is required: the API calls Docker on your
> behalf. Without it, fetches fail with a permission error.

> **Optional — fetching `arm64` packages on an amd64 machine.** The tool offers
> an `amd64`/`arm64` selector. To fetch `arm64` from an `amd64` host, install
> Docker's emulation once:
> ```bash
> docker run --privileged --rm tonistiigi/binfmt --install arm64
> ```
> Without it, `arm64` fetches fail. (Native arm64 hosts need nothing extra.)

> **EOL versions (best-effort).** Debian 10/9 are marked "(EOL)" in the
> selector; the engine automatically repoints apt at `archive.debian.org`.
> Nothing to install, but the archive mirror can be slower. (Ubuntu EOL versions
> are not offered for now: 18.04 is still under ESM, and 16.04 isn't cleanly
> available on public mirrors yet.)

---

## 9. Create the Python environment

On Debian, `pip` refuses to install system-wide (PEP 668), so use a virtual
environment. **Do not use `sudo` here** — the project is already yours from
section 3.

```bash
cd /var/www/deb-downloader/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 10. Test it once (manually)

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open `http://<machine-ip>:8000` (or `http://localhost:8000` on the machine):
pick a distribution and version, type a package (e.g. `nginx`), and download the
`.zip`. Interactive API docs are at `/docs`. Press `Ctrl+C` to stop.

> A fetch downloads packages inside a Docker container, so it can take a while.
> The page shows the progress (queued → fetching) and downloads the `.zip`
> automatically once it is ready — the request no longer blocks, and several
> fetches can run at once.

---

## 11. Run the API automatically with systemd (recommended)

So you don't have to start it by hand every time, install the provided service
(it starts on boot and restarts on failure):

```bash
sudo cp /var/www/deb-downloader/deploy/deb-downloader-api.service /etc/systemd/system/
# edit User=/Group= in that file if your username is not "debdownloader"
sudo systemctl daemon-reload
sudo systemctl enable --now deb-downloader-api
sudo systemctl status deb-downloader-api
```

Useful commands: `sudo systemctl restart deb-downloader-api`,
`sudo systemctl stop deb-downloader-api`, and `journalctl -u deb-downloader-api -f`
to follow the logs. Once enabled, you never start it by hand again.

> **Disk space.** Fetches are built under a working directory (default: the
> system temp dir). Large package sets (e.g. `gnome-core`) need a few GB — and
> on some systems `/tmp` is a small RAM-backed `tmpfs`. If you hit "not enough
> disk space", point the working dir at a roomier partition via the
> `DDL_JOBS_DIR` environment variable. With systemd, add a drop-in (this writes
> the file directly, no interactive editor):
> ```bash
> sudo mkdir -p /etc/systemd/system/deb-downloader-api.service.d
> sudo tee /etc/systemd/system/deb-downloader-api.service.d/override.conf >/dev/null <<'EOF'
> [Service]
> Environment=DDL_JOBS_DIR=/var/lib/deb-downloader-jobs
> EOF
> sudo mkdir -p /var/lib/deb-downloader-jobs
> sudo chown "$USER":"$USER" /var/lib/deb-downloader-jobs
> sudo systemctl daemon-reload
> sudo systemctl restart deb-downloader-api
> ```
> Check it is applied with: `systemctl show deb-downloader-api -p Environment`
>
> **Optional per-job size limit.** Add `Environment=DDL_MAX_JOB_MB=2000` to the
> same drop-in to reject package sets larger than 2000 MB before downloading
> (the tool shows the limit and a clear message). `0` / unset means unlimited.

---

## 12. Access the tool at http://&lt;ip&gt;/app (no port)

Once both the website (Part 1) and the API (section 11) are running, the
website **reverse-proxies** the tool. Open **`http://<machine-ip>/app`** (or
`http://localhost/app`) — no `:8000` to type. The landing page stays at `/`.

This relies on `deploy/nginx.conf` (the `/app` proxy) and the fixed Compose
subnet, so the nginx container can reach the API on the host. If you set up the
website **before this version**, recreate its container once to apply the new
config:

```bash
cd /var/www/deb-downloader
sudo docker compose -f deploy/docker-compose.yml up -d --force-recreate
```

You do **not** need to expose port 8000 to the LAN — keep it closed; visitors
reach the tool through port 80. If UFW is enabled (section 6), allow only the
Docker subnet to reach the API internally:

```bash
sudo ufw allow from 172.20.0.0/24 to any port 8000 proto tcp
sudo ufw status verbose
```

---

# Updating to a new version

The project is bind-mounted, so updating the site is just a pull:

```bash
cd /var/www/deb-downloader
git pull
```

The site files are served immediately (refresh the page; the version banner
should reflect the latest release). After an update that touched the engine,
restart the API; if it touched `deploy/nginx.conf`, restart the web container:

```bash
sudo systemctl restart deb-downloader-api                       # engine/API
sudo docker compose -f deploy/docker-compose.yml up -d          # website (recreates if config changed)
```

---

# Stopping / removing

```bash
# Website
cd /var/www/deb-downloader
sudo docker compose -f deploy/docker-compose.yml down

# Engine/API
sudo systemctl disable --now deb-downloader-api
```

---

# Troubleshooting

**Port 80 already in use** — another web server is running. Stop it
(`sudo systemctl stop apache2` / `nginx`) or change the published port in the
Compose file (e.g. `"8080:80"`).

**`permission denied` talking to Docker** — finish the `usermod -aG docker`
step (section 8) and re-login (or run `newgrp docker`).

**`externally-managed-environment` from pip** — you skipped the virtual
environment; do section 9 (`python3 -m venv .venv` + `source .venv/bin/activate`).
Never create the venv with `sudo`.

**Can't reach the site/API from another machine** — check the firewall
(sections 6 and 12) and, on VirtualBox, the adapter mode (section 5).

**Page shows 403 for a file** — that's intentional: the config blocks source
and project files. Only the site (`index.html`, `404.html`) is served.

---

© 2026 Remilulz91 — All rights reserved. This project is copyrighted; you may
host it for personal use, but you may not claim ownership or republish it as
your own. Only the author publishes official releases.
