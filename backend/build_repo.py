"""deb-downloader — offline local repository assembly + .zip archive.
Copyright (c) 2026 Remilulz91. All rights reserved.

Once the .deb files have been fetched into <out>/debs/ (by fetch.py), this
module:
  1. generates the APT index (Packages.gz) via dpkg-scanpackages,
  2. writes an INSTALL.txt explaining offline usage,
  3. compresses <out>/ into a ready-to-download .zip archive.

Requires dpkg-dev (dpkg-scanpackages) on the backend host.
"""
from __future__ import annotations
import os
import gzip
import shutil
import zipfile
import subprocess
from pathlib import Path


def generate_index(out_dir: str | Path) -> Path:
    """Generate <out_dir>/Packages.gz indexing <out_dir>/debs/*.deb.

    The Filename: fields are relative to out_dir (e.g. debs/nginx_....deb),
    which allows a 'flat' repository usable via:  deb [trusted=yes] file:<out_dir> ./
    """
    out_dir = Path(out_dir)
    debs = out_dir / "debs"
    if not debs.is_dir():
        raise FileNotFoundError(f"Folder not found: {debs}")
    if not any(debs.glob("*.deb")):
        raise FileNotFoundError(f"No .deb in {debs}")

    # dpkg-scanpackages debs /dev/null  -> index on stdout (paths 'debs/...')
    proc = subprocess.run(
        ["dpkg-scanpackages", "--multiversion", "debs", "/dev/null"],
        cwd=str(out_dir), capture_output=True, check=True,
    )
    packages_gz = out_dir / "Packages.gz"
    with gzip.open(packages_gz, "wb", compresslevel=9) as f:
        f.write(proc.stdout)
    # Also keep an uncompressed copy (handy for debugging / apt)
    (out_dir / "Packages").write_bytes(proc.stdout)
    return packages_gz


def write_install_txt(out_dir, distro, release, packages):
    out_dir = Path(out_dir)
    pkgs = " ".join(packages)
    txt = f"""deb-downloader — offline local repository
=========================================
Distribution : {distro} {release}
Package(s)   : {pkgs}

This folder contains the requested .deb files + ALL their dependencies, plus
an APT index (Packages.gz). There are two ways to use it on the target machine.

--- Method A: direct install (quick) ---
    sudo dpkg -i debs/*.deb
    sudo apt-get install -f      # fixes ordering if needed (works offline)

--- Method B: as a local APT repository (recommended) ---
    1) Copy this folder onto the machine, e.g. into /opt/deb-downloader
    2) Add the source (flat repo, no signature required):
         echo 'deb [trusted=yes] file:/opt/deb-downloader ./' \\
           | sudo tee /etc/apt/sources.list.d/deb-downloader.list
    3) Then:
         sudo apt-get update
         sudo apt-get install {pkgs}

(c) 2026 Remilulz91 - All rights reserved.
"""
    (out_dir / "INSTALL.txt").write_text(txt, encoding="utf-8")


def make_zip(out_dir, zip_path) -> Path:
    """Compress the contents of out_dir into zip_path (.zip).

    Internal working files (dotfiles such as .log, .total, .urls, .count) are
    excluded so the archive only contains debs/, Packages(.gz) and INSTALL.txt.
    """
    out_dir = Path(out_dir)
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(out_dir):
            for name in files:
                if name.startswith("."):
                    continue
                full = Path(root) / name
                # archive name relative to out_dir
                zf.write(full, full.relative_to(out_dir))
    return zip_path


def build(out_dir, distro, release, packages, zip_path) -> Path:
    """Full host-side pipeline: index + INSTALL.txt + zip."""
    generate_index(out_dir)
    write_install_txt(out_dir, distro, release, packages)
    return make_zip(out_dir, zip_path)
