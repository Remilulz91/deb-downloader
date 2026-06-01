"""deb-downloader — assemblage du depot local hors-ligne + archive .zip.
Copyright (c) 2026 Remilulz91. Tous droits reserves.

Une fois les .deb recuperes dans <out>/debs/ (par fetch.py), ce module:
  1. genere l'index APT (Packages.gz) via dpkg-scanpackages,
  2. ecrit un INSTALL.txt expliquant l'usage hors-ligne,
  3. compresse <out>/ en une archive .zip prete a telecharger.

Necessite dpkg-dev (dpkg-scanpackages) sur l'hote backend.
"""
from __future__ import annotations
import os
import gzip
import shutil
import zipfile
import subprocess
from pathlib import Path


def generate_index(out_dir: str | Path) -> Path:
    """Genere <out_dir>/Packages.gz indexant <out_dir>/debs/*.deb.

    Les champs Filename: sont relatifs a out_dir (ex: debs/nginx_....deb),
    ce qui permet un depot 'plat' utilisable via:  deb [trusted=yes] file:<out_dir> ./
    """
    out_dir = Path(out_dir)
    debs = out_dir / "debs"
    if not debs.is_dir():
        raise FileNotFoundError(f"Dossier introuvable: {debs}")
    if not any(debs.glob("*.deb")):
        raise FileNotFoundError(f"Aucun .deb dans {debs}")

    # dpkg-scanpackages debs /dev/null  -> index sur stdout (chemins 'debs/...')
    proc = subprocess.run(
        ["dpkg-scanpackages", "--multiversion", "debs", "/dev/null"],
        cwd=str(out_dir), capture_output=True, check=True,
    )
    packages_gz = out_dir / "Packages.gz"
    with gzip.open(packages_gz, "wb", compresslevel=9) as f:
        f.write(proc.stdout)
    # On garde aussi une version non compressee (pratique pour debug / apt)
    (out_dir / "Packages").write_bytes(proc.stdout)
    return packages_gz


def write_install_txt(out_dir, distro, release, packages):
    out_dir = Path(out_dir)
    pkgs = " ".join(packages)
    txt = f"""deb-downloader — depot local hors-ligne
=========================================
Distribution : {distro} {release}
Paquet(s)    : {pkgs}

Ce dossier contient les .deb demandes + TOUTES leurs dependances, ainsi
qu'un index APT (Packages.gz). Deux facons de l'utiliser sur la machine cible.

--- Methode A : installation directe (rapide) ---
    sudo dpkg -i debs/*.deb
    sudo apt-get install -f      # resout l'ordre si besoin (hors-ligne OK)

--- Methode B : comme depot local APT (recommande) ---
    1) Copiez ce dossier sur la machine, par exemple dans /opt/deb-downloader
    2) Ajoutez la source (depot 'plat', signature non requise) :
         echo 'deb [trusted=yes] file:/opt/deb-downloader ./' \\
           | sudo tee /etc/apt/sources.list.d/deb-downloader.list
    3) Puis :
         sudo apt-get update
         sudo apt-get install {pkgs}

(c) 2026 Remilulz91 - Tous droits reserves.
"""
    (out_dir / "INSTALL.txt").write_text(txt, encoding="utf-8")


def make_zip(out_dir, zip_path) -> Path:
    """Compresse le contenu de out_dir dans zip_path (.zip)."""
    out_dir = Path(out_dir)
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(out_dir):
            for name in files:
                full = Path(root) / name
                # nom dans l'archive relatif a out_dir
                zf.write(full, full.relative_to(out_dir))
    return zip_path


def build(out_dir, distro, release, packages, zip_path) -> Path:
    """Pipeline complet host-side: index + INSTALL.txt + zip."""
    generate_index(out_dir)
    write_install_txt(out_dir, distro, release, packages)
    return make_zip(out_dir, zip_path)
