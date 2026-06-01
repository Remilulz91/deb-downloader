# Changelog

All notable versions of **deb-downloader** are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/).

## [v0.4.1] — 2026-06-01
### Changed
- `DEPLOY.md`: reworked the Docker install steps (keyring under
  `/usr/share/keyrings`, repo via `lsb_release -cs`, `systemctl enable/status`).
### Fixed
- `DEPLOY.md`: added `lsb-release` to the dependencies (so `$(lsb_release -cs)`
  resolves) and `docker-compose-plugin` to the Docker install (so the
  `docker compose` commands used later in the guide work).

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

[v0.4.1]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.4.1
[v0.4.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.4.0
[v0.3.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.3.0
[v0.2.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.2.0
[v0.1.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.1.0
