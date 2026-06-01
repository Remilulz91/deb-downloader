# deb-downloader — backend (fetch engine)

> Copyright (c) 2026 Remilulz91 — All rights reserved.
> MVP: Debian 13 and Ubuntu 26.04 (amd64). See `../ARCHITECTURE.md`.

This folder contains the **engine** that fetches a package plus all of its
dependencies and produces a `.zip` archive (offline local repository). It is
independent from the landing site and **must run on a Linux host with Docker**.

## Prerequisites (Linux host / VM)
- Docker installed and working (`docker run hello-world`)
- `dpkg-dev` (provides `dpkg-scanpackages`): `sudo apt-get install -y dpkg-dev`
- Python >= 3.10 (no pip dependencies for the MVP)

## Usage (command line)
```bash
# Show the command without running anything (useful to understand / audit)
python3 fetch.py --distro ubuntu --release 26.04 --packages nginx --dry-run

# Fetch nginx + dependencies for Ubuntu 26.04 -> .zip archive
python3 fetch.py --distro ubuntu --release 26.04 --packages nginx

# Multiple packages, chosen output folder, without recommends
python3 fetch.py --distro debian --release 13 --packages nginx curl \
    --out ./out --no-recommends
```
The archive `<packages>_<distro>-<release>_<arch>.zip` is created next to the
working folder. Contents: `debs/*.deb`, `Packages.gz`, `Packages`, `INSTALL.txt`.

## How it works (summary)
1. `fetch.py` validates the input (supported distro, safe package names).
2. It launches a **disposable** Docker container (`--rm`, unprivileged, capped
   resources) of the target image, which runs `apt-get install --download-only`.
3. The `.deb` files (package + dependencies) are copied into `out/debs/`.
4. `build_repo.py` generates the APT index (`dpkg-scanpackages`), writes
   `INSTALL.txt`, and compresses everything into a `.zip`.

## Security
Disposable, unprivileged containers (`--cap-drop ALL`,
`--security-opt no-new-privileges`, `--memory`, `--cpus`, `--pids-limit`),
a timeout, and strict package-name validation (`^[a-z0-9][a-z0-9+._-]*$`) to
prevent any injection.

## Files
- `fetch.py` — Docker orchestration + CLI (entry point)
- `build_repo.py` — APT index + INSTALL.txt + zip (host-side)
- `distros.py` — supported distributions/versions
- `requirements.txt` — empty for the MVP (API step later)

## Next step
Wrap `fetch.py` in a FastAPI API + Redis/RQ job queue
(see `../ARCHITECTURE.md`, sections 5 and 9).
