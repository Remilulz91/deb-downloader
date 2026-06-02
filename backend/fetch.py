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
import time
import uuid
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
    """Script run INSIDE the disposable container.

    Downloads the .deb files straight into the bind-mounted /out/debs so the host
    can watch progress, and writes the total number of packages to /out/.total
    first (computed with --print-uris, which resolves without downloading).
    """
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
        "mkdir -p /out/debs/partial; "
        # total number of .deb to fetch (resolve only, no download)
        f"{apt} install -y {rec}--print-uris {pkgs} 2>/dev/null "
        "| grep -oE \"https?://[^ ']+\\.deb\" | sort -u > /out/.urls || true; "
        "wc -l < /out/.urls > /out/.total; "
        # real download, straight into the mounted dir (observable from the host)
        f"{apt} -o Dir::Cache::archives=/out/debs install -y {rec}--download-only {pkgs}; "
        "rm -rf /out/debs/partial /out/debs/lock 2>/dev/null || true; "
        "ls -1 /out/debs/*.deb 2>/dev/null | wc -l > /out/.count"
    )


def docker_command(image, arch, out_host, script, limits, name=None):
    """Build the `docker run` command (argument list)."""
    platform = distros.PLATFORM.get(arch, "linux/amd64")
    cmd = ["docker", "run", "--rm"]
    if name:
        cmd += ["--name", name]
    cmd += [
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
    return cmd


def run(distro, release, arch, packages, out_dir=None,
        no_recommends=False, limits=None, dry_run=False, progress_cb=None):
    """Fetch packages and build the .zip.

    progress_cb(done, total) is called ~once per second while downloading, where
    `done` is the number of .deb already written and `total` the expected count
    (or None until it is known).
    """
    limits = {**DEFAULTS, **(limits or {})}
    image = validate(distro, release, arch, packages)

    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="ddl_"))
    debs_dir = out_dir / "debs"
    debs_dir.mkdir(parents=True, exist_ok=True)

    container = "ddl_" + uuid.uuid4().hex[:12]
    script = container_script(packages, no_recommends)
    cmd = docker_command(image, arch, str(out_dir.resolve()), script, limits, name=container)

    if dry_run:
        print("# [dry-run] Docker command that would be executed:\n")
        print(" ".join(shlex.quote(c) for c in cmd))
        print("\n# [dry-run] script inside the container:\n")
        print(script)
        return None

    if shutil.which("docker") is None:
        raise FetchError("docker_missing", "Docker not found on the host.")

    print(f"[*] Fetching {packages} for {distro} {release} ({arch})...")
    log_path = out_dir / ".log"
    total_path = out_dir / ".total"
    deadline = time.time() + limits["timeout"]
    timed_out = False

    def count_debs():
        try:
            return len(list(debs_dir.glob("*.deb")))
        except OSError:
            return 0

    with open(log_path, "w") as logf:
        proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True)
        total = None
        while proc.poll() is None:
            if time.time() > deadline:
                timed_out = True
                subprocess.run(["docker", "kill", container], capture_output=True)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
            if total is None and total_path.exists():
                try:
                    total = int(total_path.read_text().strip() or "0") or None
                except ValueError:
                    total = None
            if progress_cb:
                progress_cb(count_debs(), total)
            time.sleep(1)

    try:
        output = log_path.read_text(errors="replace")
    except OSError:
        output = ""

    if timed_out:
        raise FetchError("timeout", "The fetch timed out.")

    if proc.returncode != 0:
        sys.stderr.write(output)
        notfound = sorted(set(
            re.findall(r"Unable to locate package (\S+)", output)
            + re.findall(r"Package '([^']+)' has no installation candidate", output)
            + re.findall(r"Couldn't find any package by regex '([^']+)'", output)
        ))
        if notfound:
            raise FetchError("package_not_found",
                             "Package(s) not found: " + ", ".join(notfound),
                             packages=notfound)
        if "exec format error" in output or "no matching manifest" in output:
            raise FetchError(
                "emulation_missing",
                "Architecture '%s' needs Docker emulation on this host "
                "(install: docker run --privileged --rm tonistiigi/binfmt --install %s)."
                % (arch, arch),
                arch=arch)
        tail = [ln for ln in output.strip().splitlines() if ln.strip()][-4:]
        raise FetchError("fetch_failed", "\n".join(tail) or "The fetch failed.")

    if progress_cb:
        progress_cb(count_debs(), total)

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
