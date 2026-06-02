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
    # HashiCorp doesn't publish for EOL codenames -> reject early, cleanly.
    hashi = sorted(set(packages) & distros.HASHICORP_PACKAGES)
    if hashi and distros.is_eol(distro, release):
        raise FetchError("hashicorp_unavailable",
                         "HashiCorp packages are not available on EOL releases.",
                         packages=hashi, distro=distro, release=release)
    return image


def container_script(packages, no_recommends=False, fixup="", apt_extra="",
                     hashicorp=False, arch="amd64"):
    """Script run INSIDE the disposable container.

    `fixup` is an optional shell snippet run before `apt-get update` (used to
    repoint apt at archive mirrors for EOL releases); `apt_extra` adds apt
    options (e.g. tolerating expired Release files); `hashicorp` adds HashiCorp's
    apt repo (for packer/terraform/...).

    Resolves the package set with --print-uris (no download) to compute the
    total count (/out/.total) and total size (/out/.size); enforces the optional
    per-job size quota (DDL_MAX_BYTES) before downloading; then downloads the
    .deb straight into the bind-mounted /out/debs so the host can watch progress.
    """
    rec = "--no-install-recommends " if no_recommends else ""
    # packages are already validated -> safe to interpolate; quote them anyway.
    pkgs = " ".join(shlex.quote(p) for p in packages)
    # APT::Sandbox::User=root keeps apt running as root instead of dropping to
    # the "_apt" user. We harden the container with --cap-drop ALL, which removes
    # the SETUID/SETGID capabilities apt would need to switch users — without
    # this option the download method fails ("setgroups: Operation not permitted").
    apt = "apt-get -o APT::Sandbox::User=root" + apt_extra

    hashi = ""
    if hashicorp:
        # Add HashiCorp's apt repo (key + source) for the right codename/arch.
        hashi = (
            f"{apt} install -y ca-certificates curl >/dev/null 2>&1; "
            # Store the armored key directly in trusted.gpg.d (.asc). This avoids
            # running gpg --dearmor, which can hang under arm64 qemu emulation.
            "curl -fsSL https://apt.releases.hashicorp.com/gpg "
            "-o /etc/apt/trusted.gpg.d/hashicorp.asc; "
            ". /etc/os-release; CN=\"${UBUNTU_CODENAME:-$VERSION_CODENAME}\"; "
            "echo \"deb [arch=" + arch + "] https://apt.releases.hashicorp.com "
            "$CN main\" > /etc/apt/sources.list.d/hashicorp.list; "
            f"{apt} update -qq || true; "
        )

    return (
        "set -e; export DEBIAN_FRONTEND=noninteractive; "
        + fixup
        + f"{apt} update -qq; mkdir -p /out/debs/partial; "
        + hashi
        + f"{apt} install -y {rec}--print-uris {pkgs} 2>/dev/null > /out/.uris_raw || true; "
        + "grep -oE \"https?://[^ ']+\\.deb\" /out/.uris_raw | sort -u > /out/.urls; "
        + "wc -l < /out/.urls > /out/.total; "
        + "awk '$2 ~ /\\.deb$/ {s+=$3} END{print s+0}' /out/.uris_raw > /out/.size; "
        + "MAX=\"${DDL_MAX_BYTES:-0}\"; SIZE=\"$(cat /out/.size)\"; "
        + "if [ \"$MAX\" -gt 0 ] && [ \"$SIZE\" -gt \"$MAX\" ]; then "
        + "echo \"DDL_TOO_LARGE size=$SIZE max=$MAX\"; exit 7; fi; "
        + f"{apt} -o Dir::Cache::archives=/out/debs install -y {rec}--download-only {pkgs}; "
        + "rm -rf /out/debs/partial /out/debs/lock 2>/dev/null || true; "
        + "ls -1 /out/debs/*.deb 2>/dev/null | wc -l > /out/.count"
    )


def docker_command(image, arch, out_host, script, limits, name=None, max_bytes=0):
    """Build the `docker run` command (argument list)."""
    platform = distros.PLATFORM.get(arch, "linux/amd64")
    cmd = ["docker", "run", "--rm"]
    if name:
        cmd += ["--name", name]
    cmd += ["-e", "DDL_MAX_BYTES=%d" % int(max_bytes)]
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
        no_recommends=False, limits=None, dry_run=False, progress_cb=None, max_bytes=0):
    """Fetch packages and build the .zip.

    progress_cb(done, total) is called ~once per second while downloading, where
    `done` is the number of .deb already written and `total` the expected count
    (or None until it is known). max_bytes>0 rejects sets larger than that
    (computed before downloading).
    """
    limits = {**DEFAULTS, **(limits or {})}
    image = validate(distro, release, arch, packages)

    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="ddl_"))
    debs_dir = out_dir / "debs"
    debs_dir.mkdir(parents=True, exist_ok=True)

    container = "ddl_" + uuid.uuid4().hex[:12]
    script = container_script(packages, no_recommends,
                             fixup=distros.sources_fixup(distro, release),
                             apt_extra=distros.apt_opts(distro, release),
                             hashicorp=distros.needs_hashicorp(packages), arch=arch)
    cmd = docker_command(image, arch, str(out_dir.resolve()), script, limits,
                         name=container, max_bytes=max_bytes)

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
        # Per-job size quota exceeded (computed before any download).
        if "DDL_TOO_LARGE" in output:
            m = re.search(r"DDL_TOO_LARGE size=(\d+) max=(\d+)", output)
            size = int(m.group(1)) if m else None
            mx = int(m.group(2)) if m else int(max_bytes)
            raise FetchError("too_large",
                             "Requested set is too large: %s > %s bytes." % (size, mx),
                             size=size, max=mx)
        notfound = sorted(set(
            re.findall(r"Unable to locate package (\S+)", output)
            + re.findall(r"Package '([^']+)' has no installation candidate", output)
            + re.findall(r"Couldn't find any package by regex '([^']+)'", output)
        ))
        if notfound:
            # If a HashiCorp package is the one missing, it almost certainly means
            # HashiCorp doesn't publish for this codename -> clearer message.
            hashi_missing = sorted(set(notfound) & distros.HASHICORP_PACKAGES)
            if hashi_missing:
                raise FetchError("hashicorp_unavailable",
                                 "Not published by HashiCorp for %s %s: %s"
                                 % (distro, release, ", ".join(hashi_missing)),
                                 packages=hashi_missing, distro=distro, release=release)
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
