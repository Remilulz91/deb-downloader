#!/usr/bin/env python3
"""deb-downloader — fetch engine (MVP, standalone).
Copyright (c) 2026 Remilulz91. All rights reserved.

Launches a DISPOSABLE Docker container of the target distribution, downloads the
requested package(s) + all their dependencies via apt, then assembles a .zip
archive (offline local repository) host-side. The container is destroyed.

Examples:
    python3 fetch.py --distro ubuntu --release 26.04 --packages nginx
    python3 fetch.py --distro debian --release 13 --packages nginx curl --out ./out
    python3 fetch.py --distro ubuntu --release 26.04 --packages nginx --dry-run

Requires Docker (host) + dpkg-dev (dpkg-scanpackages) on the host.
"""
from __future__ import annotations
import re
import sys
import shlex
import shutil
import argparse
import subprocess
import tempfile
from pathlib import Path

import distros
import build_repo

# Strict validation of a Debian/Ubuntu package name.
PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+._-]*$")

# Default caps (anti-abuse / host protection)
DEFAULTS = {
    "memory": "1g",
    "cpus": "1.0",
    "pids_limit": "256",
    "timeout": 600,         # seconds
    "max_packages": 20,
}


class FetchError(Exception):
    """A user-facing error with a machine-readable code (for i18n in the UI)."""
    def __init__(self, code, message, **data):
        super().__init__(message)
        self.code = code
        self.data = data


def validate(distro, release, arch, packages):
    """Validate the input. Raises FetchError on any problem."""
    try:
        image = distros.image_for(distro, release)
    except ValueError:
        raise FetchError("unsupported_distro",
                         f"Unsupported distribution: {distro} {release}.",
                         distro=distro, release=release)
    if arch not in distros.ARCHES:
        raise FetchError("bad_arch", f"Unsupported architecture: {arch}.", arch=arch)
    if not packages:
        raise FetchError("no_packages", "No package requested.")
    if len(packages) > DEFAULTS["max_packages"]:
        raise FetchError("too_many", f"Too many packages (max {DEFAULTS['max_packages']}).",
                         max=DEFAULTS["max_packages"])
    bad = [p for p in packages if not PKG_RE.match(p)]
    if bad:
        raise FetchError("invalid_names", f"Invalid package name(s): {bad}", names=bad)
    return image


def container_script(packages, no_recommends=False):
    """Script run INSIDE the disposable container: downloads .deb into /out/debs."""
    rec = "--no-install-recommends " if no_recommends else ""
    # packages are already validated -> safe to interpolate; quote them anyway.
    pkgs = " ".join(shlex.quote(p) for p in packages)
    # APT::Sandbox::User=root keeps apt running as root instead of dropping to
    # the "_apt" user. We harden the container with --cap-drop ALL, which removes
    # the SETUID/SETGID capabilities apt would need to switch users — without
    # this option the download method fails ("setgroups: Operation not permitted").
    apt = "apt-get -o APT::Sandbox::User=root"
    return (
        "set -e; export DEBIAN_FRONTEND=noninteractive; "
        f"{apt} update -qq; "
        "mkdir -p /out/debs; "
        "rm -f /var/cache/apt/archives/*.deb || true; "
        f"{apt} install -y {rec}--download-only {pkgs}; "
        "cp /var/cache/apt/archives/*.deb /out/debs/ 2>/dev/null || true; "
        # marker: number of fetched .deb files
        "ls -1 /out/debs/*.deb | wc -l > /out/.count"
    )


def docker_command(image, arch, out_host, script, limits):
    """Build the `docker run` command (argument list)."""
    platform = distros.PLATFORM.get(arch, "linux/amd64")
    return [
        "docker", "run", "--rm",
        "--platform", platform,
        "--memory", limits["memory"],
        "--cpus", limits["cpus"],
        "--pids-limit", limits["pids_limit"],
        # security: drop all caps, no privilege escalation, no docker socket.
        # DAC_OVERRIDE is added back so the container root can write the .deb
        # files into the bind-mounted /out (owned by the host user).
        "--cap-drop", "ALL",
        "--cap-add", "DAC_OVERRIDE",
        "--security-opt", "no-new-privileges",
        "-v", f"{out_host}:/out",
        image,
        "bash", "-lc", script,
    ]


def run(distro, release, arch, packages, out_dir=None,
        no_recommends=False, limits=None, dry_run=False):
    limits = {**DEFAULTS, **(limits or {})}
    image = validate(distro, release, arch, packages)

    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="ddl_"))
    (out_dir / "debs").mkdir(parents=True, exist_ok=True)

    script = container_script(packages, no_recommends)
    cmd = docker_command(image, arch, str(out_dir.resolve()), script, limits)

    if dry_run:
        print("# [dry-run] Docker command that would be executed:\n")
        print(" ".join(shlex.quote(c) for c in cmd))
        print("\n# [dry-run] script inside the container:\n")
        print(script)
        return None

    if shutil.which("docker") is None:
        raise FetchError("docker_missing", "Docker not found on the host.")

    print(f"[*] Fetching {packages} for {distro} {release} ({arch})...")
    try:
        subprocess.run(cmd, check=True, timeout=limits["timeout"],
                       capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        raise FetchError("timeout", "The fetch timed out.")
    except subprocess.CalledProcessError as e:
        output = (e.stdout or "") + "\n" + (e.stderr or "")
        # Keep the full container output in the journal for debugging.
        sys.stderr.write(output)
        # Detect "package not found" cases from apt's output.
        notfound = sorted(set(
            re.findall(r"Unable to locate package (\S+)", output)
            + re.findall(r"Package '([^']+)' has no installation candidate", output)
            + re.findall(r"Couldn't find any package by regex '([^']+)'", output)
        ))
        if notfound:
            raise FetchError("package_not_found",
                             "Package(s) not found: " + ", ".join(notfound),
                             packages=notfound)
        # Otherwise surface a short, clean tail of the error (no command dump).
        tail = [ln for ln in output.strip().splitlines() if ln.strip()][-4:]
        raise FetchError("fetch_failed", "\n".join(tail) or "The fetch failed.")

    safe_pkg = "-".join(packages)
    zip_name = f"{safe_pkg}_{distro}-{release}_{arch}.zip"
    zip_path = out_dir.parent / zip_name
    build_repo.build(out_dir, distro, release, packages, zip_path)
    print(f"[OK] Archive ready: {zip_path}")
    return zip_path


def main(argv=None):
    p = argparse.ArgumentParser(description="deb-downloader — fetch .deb packages + dependencies")
    p.add_argument("--distro", required=True, help="debian | ubuntu")
    p.add_argument("--release", required=True, help="e.g. 13 (debian) or 26.04 (ubuntu)")
    p.add_argument("--arch", default="amd64", help="amd64 (default)")
    p.add_argument("--packages", required=True, nargs="+", help="one or more packages")
    p.add_argument("--out", default=None, help="working folder (default: temporary)")
    p.add_argument("--no-recommends", action="store_true", help="exclude recommended packages")
    p.add_argument("--timeout", type=int, default=DEFAULTS["timeout"])
    p.add_argument("--dry-run", action="store_true", help="print the command without running it")
    a = p.parse_args(argv)
    try:
        run(a.distro, a.release, a.arch, a.packages, out_dir=a.out,
            no_recommends=a.no_recommends, limits={"timeout": a.timeout},
            dry_run=a.dry_run)
    except FetchError as e:
        print(f"[ERROR] ({e.code}) {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
