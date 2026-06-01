# Self-hosting deb-downloader — Debian 13 + nginx + Docker

This is a step-by-step tutorial to host the **deb-downloader website** on your
own machine. It targets **Debian 13 (Trixie)** — a VirtualBox VM, a spare PC, or
a small server — and serves the site over **plain HTTP on your local network**
(no domain name, no TLS). Think of it as the Linux equivalent of just opening
`index.html` on Windows, but served properly by nginx.

Everything below is copy-paste. Optional hardening with **UFW** and **fail2ban**
is included at the end.

> The site is fully static, so this is lightweight: one small nginx container
> serving a few files. The **backend engine** (which actually fetches `.deb`
> packages) is a separate component — see `backend/README.md`; it is **not**
> required to run the website.

---

## 0. What you will get

A web server reachable at:

- `http://localhost` — from the machine itself, and
- `http://<machine-ip>` — from other devices on the same network.

The page shows the project and tells visitors whether they are on the latest
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
sudo echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable docker
sudo systemctl status docker
```

Check it works:

```bash
sudo docker run --rm hello-world
```

(Optional) Run Docker without `sudo` — log out and back in afterwards:

```bash
sudo usermod -aG docker "$USER"
```

---

## 3. Get the project into /var/www

```bash
sudo apt-get install -y git
sudo mkdir -p /var/www
sudo git clone https://github.com/Remilulz91/deb-downloader.git /var/www/deb-downloader
```

---

## 4. Start the website (nginx in Docker)

The repository already ships a ready-to-use nginx config and a Compose file in
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

## 8. Updating to a new version

The site files are bind-mounted live, so updating is just a `git pull`:

```bash
cd /var/www/deb-downloader
sudo git pull
```

The new files are served immediately — refresh the page and the version banner
should reflect the latest release. Only restart the container if you changed
`deploy/nginx.conf`:

```bash
sudo docker compose -f deploy/docker-compose.yml restart
```

---

## 9. Stopping / removing

```bash
cd /var/www/deb-downloader
sudo docker compose -f deploy/docker-compose.yml down
```

---

## 10. Troubleshooting

**Port 80 already in use** — another web server is running. Stop it
(`sudo systemctl stop apache2` / `nginx`) or change the published port in the
Compose file (e.g. `"8080:80"`).

**`permission denied` talking to Docker** — either use `sudo`, or finish the
`usermod -aG docker` step from section 2 and re-login.

**Can't reach the site from another machine** — check the firewall (section 6)
and, on VirtualBox, the adapter mode (section 5).

**Page shows 403 for a file** — that's intentional: the config blocks source
and project files. Only the site (`index.html`, `404.html`) is served.

---

© 2026 Remilulz91 — All rights reserved. This project is copyrighted; you may
host it for personal use, but you may not claim ownership or republish it as
your own. Only the author publishes official releases.
