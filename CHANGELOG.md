# Changelog

All notable versions of **deb-downloader** are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

## [v1.7.1] — 2026-06-04
### Fixed
- **Raw "HTTP 413" when uploading a status file through `/app`.** nginx's
  default upload limit (1 MB) rejected dpkg status files (typically 3-5 MB)
  before they reached the API, returning a raw HTML page the UI couldn't
  localize. `deploy/nginx.conf` now allows 25 MB on `/app/`
  (`client_max_body_size`), and the UI shows a clear localized message for
  oversized uploads even when the error doesn't come from the API.
  (Apply with: `git pull` then `sudo docker restart deb-downloader-web`.)
### Changed
- The landing page (FR/EN) now presents the **System update** feature: new
  feature card, updated hero text and meta description. All docs (`README`,
  `ARCHITECTURE`, `THIRD_PARTY_PACKAGES`) mention it too.

## [v1.7.0] — 2026-06-04
### Added
- **System update for offline machines.** New **System update** tab: upload the
  target machine's dpkg status file (`/var/lib/dpkg/status`, copied e.g. on a
  USB stick) and get a `.zip` containing **exactly the updates that machine
  needs** within its release (point release, kernel and security fixes
  included) — the offline equivalent of `apt dist-upgrade`, with no extra tool
  to install on either side. One machine = one file = one job, so a whole fleet
  can be handled machine by machine. The engine mounts the uploaded status into
  the disposable container so apt sees the target's exact installed set; if the
  machine is already current, the UI says so ("already up to date"). The bundle
  ships an update-specific `INSTALL.txt`. Major upgrades (e.g. Debian 12 → 13)
  are intentionally out of scope; EOL releases are brought to their last
  published state. (API: `POST /api/jobs/update`, multipart; new dependency:
  `python-multipart` — re-run `pip install -r requirements.txt`.)

## [v1.6.0] — 2026-06-03
### Added
- **Interactive installer (`deploy/install.sh`).** A single script that
  reproduces the whole `DEPLOY.md` over plain HTTP: Docker, the project, the
  nginx website, and the engine/API as a systemd service. It pauses to ask for
  each required value (user, install directory, web port — Enter accepts the
  default) and asks **y/n** before every optional step (custom jobs directory,
  per-job size limit, localhost-only website, UFW firewall, fail2ban for SSH
  and/or nginx), writing each answer into the right file automatically. It ends
  by printing the URL to open (e.g. `http://<ip>/app`). Re-running it updates an
  existing install rather than duplicating it. Documented at the top of
  `DEPLOY.md`.

## [v1.5.0] — 2026-06-03
### Added
- **Quick-pick package selection.** The app interface now offers a curated list
  of common packages (web servers, databases, languages, build/dev tools, system
  utilities, plus the third-party Docker/HashiCorp/Wazuh/GitLab entries), grouped
  by category as clickable pills — no need to remember exact names.
### Changed
- **Selected packages are shown as readable "chips"** instead of one long text
  field. Each chip has its own optional **version box**, so pinning versions
  (e.g. `gitlab-ce` → `18.10.0-ce.0`) no longer turns the input into an
  unreadable string. Free typing is kept (name or `name=version`, Enter/comma to
  add) for anything not in the list. Fully bilingual (FR/EN).

## [v1.4.1] — 2026-06-02
### Fixed
- **Failures are no longer silent.** When a job fails (including a timeout), the
  container output is now kept as `error.log` in the job folder instead of being
  deleted with the work tree, and the full output is written to the server log
  (`journalctl`). On timeout the engine also returns the **last log lines**, and
  the UI shows them under the error — so a stalled Docker image pull (e.g. frozen
  on "Pulling fs layer" after a network change) is visible directly instead of a
  bare "timed out". Added a localized `timeout` message (EN/FR).

## [v1.4.0] — 2026-06-01
### Removed
- **arm64 support dropped — amd64 only.** Removed the architecture selector from
  the UI, the arm64 platform/arch entries, the arm64 emulation detection and its
  message, and the arm64/qemu note from `DEPLOY.md`. (arm64 only ever worked
  under flaky qemu emulation; amd64 is the supported target.)

## [v1.3.2] — 2026-06-01
### Fixed
- Job archives are now purged by a **background thread every 5 minutes** (not
  only when a new job is submitted), so disk space is reclaimed even when the
  service is idle. The purge also sweeps the filesystem to remove **orphan job
  folders** left by a previous run (e.g. after an API restart). Jobs that are
  still queued/running are never touched.

## [v1.3.1] — 2026-06-01
### Fixed
- The `.zip` filename no longer contains `=` (or `:`) coming from version-pinned
  package names — e.g. `gitlab-ce-18.10.0-ce.0_debian-13_amd64.zip`.

## [v1.3.0] — 2026-06-01
### Added
- **Version pinning**: request a specific version with `name=version` (apt
  syntax, e.g. `gitlab-ce=17.5.0-ce.0`) — useful for stepped upgrades.
- **GitLab CE** via the repo registry (packages.gitlab.com, which keeps the
  version history). amd64. Note: upgrading GitLab requires stepping through
  mandatory "stop" versions — use GitLab's Upgrade Path tool and fetch each step.
- Clear, translated message when a pinned version doesn't exist.

## [v1.2.0] — 2026-06-01
### Added
- **Wazuh packages** (`wazuh-agent`, `wazuh-manager`, `wazuh-indexer`,
  `wazuh-dashboard`) via the third-party repo registry
  (`packages.wazuh.com/4.x`, single `stable main` suite). amd64; provides the
  latest 4.x `.deb` — handy for updating an old agent/manager.

## [v1.1.0] — 2026-06-01
### Added
- **Docker packages** (`docker-ce`, `docker-ce-cli`, `containerd.io`,
  `docker-buildx-plugin`, `docker-compose-plugin`): when requested, the engine
  adds Docker's apt repo (key + source for the codename) and fetches them.

### Changed
- Third-party repos are now driven by a small **registry** (HashiCorp + Docker),
  so adding more is a single data entry. Same reliability limits apply (amd64,
  non-EOL). The "not available" message is now generic and names the repo.

## [v1.0.0] — 2026-06-01
First stable release. **deb-downloader** fetches a Debian/Ubuntu package (or
several) plus all their dependencies as a ready-to-use offline `.zip`. Highlights:

- Bilingual (EN/FR) landing page with an automatic version indicator.
- Web UI + HTTP API with **asynchronous jobs** and a **live progress bar**.
- Distributions: Debian 11/12/13 and Ubuntu 20.04/22.04/24.04/26.04, plus **EOL
  Debian 9/10** (archive mirrors); **amd64 and arm64**.
- **HashiCorp** packages (packer, terraform, vault, …) on amd64.
- Per-job **size quota** + server **disk-space** display.
- Clean, **translated** error messages for every failure case.
- One-file **self-hosting guide** (`DEPLOY.md`): nginx + Docker, systemd,
  reverse proxy at `/app`.

## [v0.11.2] — 2026-06-01
### Changed
- HashiCorp packages are now restricted to **reliable combinations only**:
  `amd64`, **non-EOL** releases, and **not Ubuntu 20.04** (where packer pulled
  ~74 unrelated dependencies). `arm64` is excluded because it hangs under qemu
  emulation. Any other combination shows a clear "not available" message
  (now including the architecture).

## [v0.11.1] — 2026-06-01
### Fixed
- HashiCorp packages on **arm64** no longer hang at dependency resolution: the
  repo key is stored as an armored `.asc` in `trusted.gpg.d` instead of running
  `gpg --dearmor`, which could hang under arm64 qemu emulation.
- HashiCorp packages are now refused up front on **EOL** releases (Debian 10/9),
  with the clear "not available" message.

## [v0.11.0] — 2026-06-01
### Added
- **HashiCorp packages** (`packer`, `terraform`, `vault`, `consul`, `nomad`,
  `boundary`, `waypoint`, `vagrant`): when one is requested, the engine
  automatically adds HashiCorp's apt repo (GPG key + source for the right
  codename and architecture) and fetches it with its dependencies — no special
  action needed, just type the name.
- Clear, translated message when a HashiCorp package isn't published for the
  chosen distro/version (HashiCorp only ships certain codenames).

## [v0.10.4] — 2026-06-01
### Removed
- Debian **8 (jessie)** from the EOL set: its old apt (1.0.x) treats the expired
  archive signature as unauthenticated and demands `--force-yes` (i.e. fetching
  unsigned packages), which we don't do. The reliable EOL floor stays at Debian
  **9 (stretch)**; 10 and 9 keep working cleanly. (The broader Debian
  mirror-host rewrite from v0.10.3 is kept.)

## [v0.10.3] — 2026-06-01
### Added
- **Debian 8 (jessie)** added to the EOL set (`archive.debian.org`) — the most
  recent reliably-archivable Debian below 9. The Debian source rewrite now also
  handles older mirror hosts (`httpredir.debian.org`, `http.debian.net`).

## [v0.10.2] — 2026-06-01
### Removed
- Ubuntu **16.04** from the list: it just left ESM (2026) and is not yet cleanly
  published on `old-releases.ubuntu.com` (even the base suite 404s), so it can't
  be fetched anonymously right now. With 18.04 still under ESM, no Ubuntu EOL
  version is offered for the moment. **Debian EOL (10, 9) is unaffected and works
  fine.** The Ubuntu source-rewrite logic is kept, ready for when these mirrors
  stabilize.

## [v0.10.1] — 2026-06-01
### Fixed
- Ubuntu **16.04 (EOL)**: the `-updates`/`-backports`/`-security` pockets are now
  dropped (they 404 on `old-releases.ubuntu.com`); only the base suite is kept,
  so fetches work again.

### Removed
- Ubuntu **18.04** from the list: it is still under ESM (until 2028), so its
  packages are not on public mirrors (they require an Ubuntu Pro token). It will
  be re-added once it fully reaches end-of-life and moves to old-releases.

## [v0.10.0] — 2026-06-01
### Added
- **EOL distributions via archive mirrors** (best-effort): **Debian 10 / 9** and
  **Ubuntu 18.04 / 16.04**. The engine repoints apt at `archive.debian.org` /
  `old-releases.ubuntu.com` and tolerates expired Release files
  (`Acquire::Check-Valid-Until=false`). These versions are flagged **"(EOL)"** in
  the version selector. Archive mirrors can be slower or occasionally flaky.

## [v0.9.0] — 2026-06-01
### Added
- **Server disk info** in the tool: free space, plus the per-job limit when set.
- **Per-job size quota**: set `DDL_MAX_JOB_MB` to reject package sets larger than
  that **before** downloading, with a clear, translated message. Disabled (`0`)
  by default. The total size is computed from `apt --print-uris`.
- New `GET /api/status` endpoint (free/total disk space, quota).

## [v0.8.2] — 2026-06-01
### Fixed
- `DEPLOY.md`: the `DDL_JOBS_DIR` systemd drop-in now uses a direct,
  non-interactive write (`tee`) instead of `systemctl edit` with commented
  lines, which left an empty override ("new contents are empty, not writing
  file").

## [v0.8.1] — 2026-06-01
### Added
- The working/results directory is now configurable via the **`DDL_JOBS_DIR`**
  environment variable, so it can point at a partition with enough space (large
  package sets like `gnome-core` need a few GB, and `/tmp` may be a small tmpfs).

### Fixed
- Running out of disk now shows a clear, translated **"not enough disk space"**
  message instead of the raw `[Errno 28]`.

## [v0.8.0] — 2026-06-01
### Added
- **Real progress bar.** The engine downloads the `.deb` straight into the
  output folder and learns the total upfront (`apt --print-uris`), so the tool
  shows "Downloading… X/Y packages" with a filling bar (and an indeterminate bar
  while dependencies are being resolved).

### Changed
- Per-job timeout now reliably stops the container (`docker kill`).
- Internal working files (`.log`, `.total`, `.urls`, `.count`) are excluded from
  the `.zip` (it contains only `debs/`, `Packages(.gz)` and `INSTALL.txt`).

## [v0.7.1] — 2026-06-01
### Fixed
- Selecting `arm64` on an amd64 host without emulation now shows a clear,
  translated message explaining how to enable it
  (`docker run --privileged --rm tonistiigi/binfmt --install arm64`), instead of
  the raw "exec format error" Docker output.

## [v0.7.0] — 2026-06-01
### Added
- **More distributions**: Debian 11 / 12 / 13 and Ubuntu 20.04 / 22.04 / 24.04 /
  26.04 (the versions whose apt mirrors are still live).
- **Architecture selector** (`amd64` / `arm64`) in the tool. Fetching `arm64`
  from an `amd64` host requires Docker binfmt emulation (see `DEPLOY.md`).
- **UX**: once a fetch finishes, the page shows the package count and archive
  size and offers a "Download again" link.

## [v0.6.1] — 2026-06-01
### Fixed
- The tool page (`/app`) is now served with **no-cache** headers, so a new
  version is picked up immediately after an update. Previously the browser could
  keep a cached old page that called the removed `/api/fetch` endpoint, making
  the interface appear broken until a manual hard refresh.

## [v0.6.0] — 2026-06-01
### Changed
- **Fetches are now asynchronous.** Submitting a fetch no longer blocks the HTTP
  request: `POST /api/jobs` returns a job id immediately, the page polls the
  progress (queued → fetching) and downloads the `.zip` automatically when it is
  ready. Several fetches can run at once (small in-process worker pool, max 2).
  No extra service to install.

### Added
- New endpoints: `POST /api/jobs`, `GET /api/jobs/{id}`,
  `GET /api/jobs/{id}/download`. Finished jobs (and their archives) are kept for
  one hour, then purged automatically.
- A "queued" status message in the UI (EN/FR).

### Removed
- The synchronous `POST /api/fetch` endpoint (replaced by the job endpoints).

## [v0.5.8] — 2026-06-01
### Fixed
- The "package not found" message no longer hard-codes the apache/apache2
  example (confusing for other packages such as `packer`); it is now generic.
- Status and error messages now **re-translate live** when the language is
  switched (FR/EN). Previously a message stayed in the language it was first
  shown in.

## [v0.5.7] — 2026-06-01
### Changed
- **Clean, localized error messages.** When a fetch fails — e.g. an unknown
  package such as `apache` (the Debian package is `apache2`) — the tool now
  shows a friendly bilingual message ("Package(s) not found: apache…") instead
  of the raw Docker command dump. The API returns structured error codes and
  the UI translates them (FR/EN), with a graceful fallback for unexpected
  errors. The full container output is still written to the journal for
  debugging.

## [v0.5.6] — 2026-06-01
### Fixed
- Fetch failed with exit status 1: `--cap-drop ALL` also removed
  `CAP_DAC_OVERRIDE`, so the container root could not write the `.deb` files
  into the bind-mounted output (owned by the host user). Added
  `--cap-add DAC_OVERRIDE` (the rest of the hardening is unchanged).

### Added
- The tool page now has a bilingual **"← Home"** link back to the landing site.

## [v0.5.5] — 2026-06-01
### Fixed
- **Fetch now works with the hardened container**: apt runs with
  `APT::Sandbox::User=root`, so package downloads no longer fail with
  "setgroups: Operation not permitted" under `--cap-drop ALL`.

### Added
- The **tool UI is now bilingual** (EN / FR) with a language toggle, like the
  landing page.
- The landing page shows an **"Open the tool"** button linking to `/app`
  (shown only when a backend exists; hidden on GitHub Pages).

## [v0.5.4] — 2026-06-01
### Added
- **Reverse proxy**: the website now serves the tool at `http://<ip>/app`
  (no port to type). nginx (`deploy/nginx.conf`) proxies `/app` to the
  engine/API on the host, and `deploy/docker-compose.yml` pins a fixed subnet
  (172.20.0.0/24) so the container can reach it.
- The API now serves its own `/favicon.svg`, so the icon shows on the tool page.

### Changed
- `backend/ui.html` now uses relative paths, so it works both standalone
  (`:8000`) and behind the `/app` proxy.
- `DEPLOY.md`: documented `/app` access, the one-time container recreation, and
  the UFW rule for the Docker subnet (port 8000 stays closed to the LAN).

## [v0.5.3] — 2026-06-01
### Changed
- **All deployment docs consolidated into a single `DEPLOY.md`**: now organized
  in two parts — the website (Part 1) and the engine/API + systemd (Part 2) — so
  anyone can follow one file to install the whole project.
- Root `README.md` trimmed to a project overview that points to `DEPLOY.md`.

### Removed
- `backend/README.md` (its content moved into `DEPLOY.md`).
- Command-line (CLI) usage documentation, now that the web UI is the intended
  way to use the engine (`fetch.py` still works as a script).

## [v0.5.2] — 2026-06-01
### Added
- **systemd service** (`deploy/deb-downloader-api.service`): run the API
  automatically on boot, with restart-on-failure. Documented in
  `backend/README.md`.

### Fixed
- Backend docs: documented the ownership step (`chown` the project so the venv
  can be created without `sudo`), the `docker` group membership and `dpkg-dev`,
  to avoid the `Permission denied` errors when setting up the API.

## [v0.5.1] — 2026-06-01
### Fixed
- Backend docs: install the API in a **Python virtual environment** instead of a
  global `pip install`, which fails on Debian 13 / recent distros with
  `externally-managed-environment` (PEP 668). Updated `backend/README.md` and
  the `app.py` header.

## [v0.5.0] — 2026-06-01
### Added
- **HTTP API** (`backend/app.py`, FastAPI): drive the fetch engine over HTTP.
  - `GET /api/distributions` — supported distro/version pairs + architectures.
  - `POST /api/fetch` — synchronous fetch, returns the `.zip` archive.
  - `GET /healthz`, interactive docs at `/docs`.
- **Web UI** (`backend/ui.html`, served at `/`): pick distribution, version and
  packages, then download the `.zip` from the browser, with a loading state.
- **Favicon** (`favicon.svg`): brand-colored SVG icon, linked from `index.html`
  and `404.html`.
- `requirements.txt`: FastAPI + uvicorn.

### Notes
- The API runs the fetch **synchronously** for now; the async Redis/RQ job
  queue is the next step. Run the API directly on the Docker host.
- Endpoints tested via FastAPI TestClient (validation, injection blocked,
  clean 503 when Docker is absent).

## [v0.4.2] — 2026-06-01
### Fixed
- `DEPLOY.md`: pinned the Docker apt repository to the `trixie` codename (instead
  of `$(lsb_release -cs)`) so a future Debian release can't silently switch it
  after `apt update`/`upgrade`.

## [v0.4.1] — 2026-06-01
### Changed
- `DEPLOY.md`: reworked the Docker install steps (keyring under
  `/usr/share/keyrings`, `systemctl enable/status`).
### Fixed
- `DEPLOY.md`: added `docker-compose-plugin` to the Docker install (so the
  `docker compose` commands used later in the guide work) and `lsb-release` to
  the dependencies.

## [v0.4.0] — 2026-06-01
### Added
- **Self-hosting tutorial** (`DEPLOY.md`): step-by-step guide to host the site
  on Debian 13 with nginx in Docker, over local HTTP, with optional UFW and
  fail2ban hardening.
- **Deployment assets** (`deploy/`): ready-to-use `nginx.conf`,
  `docker-compose.yml`, and `fail2ban/jail.local`.

### Changed
- All documentation translated to **English** (README, CHANGELOG, ARCHITECTURE,
  backend README, `.github` templates, and source-code comments).

## [v0.3.0] — 2026-06-01
### Added
- **Backend engine — MVP** (`backend/`): fetches `.deb` packages and their
  dependencies via a disposable Docker container, then builds a `.zip` archive
  (offline local repository).
  - `fetch.py`: Docker orchestration (unprivileged container, capped resources,
    timeout), strict input validation, `--dry-run` mode.
  - `build_repo.py`: APT index generation (`Packages.gz` via
    `dpkg-scanpackages`), `INSTALL.txt`, `.zip` compression.
  - `distros.py`: supported distributions (Debian 13, Ubuntu 26.04, amd64).
  - Backend `README.md` and `requirements.txt`.
- End-to-end packaging validated (index + zip) with test packages.

## [v0.2.0] — 2026-06-01
### Added
- **Bilingual website** (English / French): FR/EN toggle, automatic browser
  language detection, remembered choice, and a translated version banner.
- `.github/` templates: release notes template, auto-notes config
  (`release.yml`), issue templates (bug / idea) and a PR template.
- `ARCHITECTURE.md`: backend engine design (Python/FastAPI, Docker
  orchestration, `.zip` output, job queue, security, MVP).

### Changed
- Output wording clarified: a downloadable **.zip archive** (one click), with a
  ready-to-use local repository inside.

## [v0.1.0] — 2026-06-01
### Added
- Static landing site (HTML/CSS/JS, no dependency or build step).
- Automatic version indicator: the page compares the embedded version with the
  latest GitHub release and tells the user whether they are up to date (no
  auto-update).
- Sections: overview, features, "how it works", contributing / bug reporting.
- Proprietary license (all rights reserved).

[v1.7.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.7.1
[v1.7.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.7.0
[v1.6.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.6.0
[v1.5.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.5.0
[v1.4.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.4.1
[v1.4.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.4.0
[v1.3.2]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.3.2
[v1.3.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.3.1
[v1.3.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.3.0
[v1.2.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.2.0
[v1.1.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.1.0
[v1.0.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v1.0.0
[v0.11.2]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.11.2
[v0.11.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.11.1
[v0.11.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.11.0
[v0.10.4]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.10.4
[v0.10.3]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.10.3
[v0.10.2]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.10.2
[v0.10.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.10.1
[v0.10.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.10.0
[v0.9.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.9.0
[v0.8.2]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.8.2
[v0.8.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.8.1
[v0.8.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.8.0
[v0.7.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.7.1
[v0.7.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.7.0
[v0.6.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.6.1
[v0.6.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.6.0
[v0.5.8]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.8
[v0.5.7]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.7
[v0.5.6]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.6
[v0.5.5]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.5
[v0.5.4]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.4
[v0.5.3]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.3
[v0.5.2]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.2
[v0.5.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.1
[v0.5.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.5.0
[v0.4.2]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.4.2
[v0.4.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.4.1
[v0.4.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.4.0
[v0.3.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.3.0
[v0.2.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.2.0
[v0.1.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.1.0
