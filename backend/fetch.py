#!/usr/bin/env python3
"""deb-downloader — moteur de recuperation (MVP, autonome).
Copyright (c) 2026 Remilulz91. Tous droits reserves.

Lance un conteneur Docker JETABLE de la distribution cible, y telecharge le(s)
paquet(s) demande(s) + toutes leurs dependances via apt, puis assemble une
archive .zip (depot local hors-ligne) cote hote. Le conteneur est detruit.

Exemple :
    python3 fetch.py --distro ubuntu --release 26.04 --packages nginx
    python3 fetch.py --distro debian --release 13 --packages nginx curl --out ./out
    python3 fetch.py --distro ubuntu --release 26.04 --packages nginx --dry-run

Necessite Docker (hote) + dpkg-dev (dpkg-scanpackages) cote hote.
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

# Validation stricte d'un nom de paquet Debian/Ubuntu.
PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+._-]*$")

# Plafonds par defaut (anti-abus / protection de l'hote)
DEFAULTS = {
    "memory": "1g",
    "cpus": "1.0",
    "pids_limit": "256",
    "timeout": 600,         # secondes
    "max_packages": 20,
}


def validate(distro, release, arch, packages):
    """Valide les entrees. Leve ValueError en cas de probleme."""
    image = distros.image_for(distro, release)  # leve si non supporte
    if arch not in distros.ARCHES:
        raise ValueError(f"Architecture non supportee: {arch} (MVP: {sorted(distros.ARCHES)}).")
    if not packages:
        raise ValueError("Aucun paquet demande.")
    if len(packages) > DEFAULTS["max_packages"]:
        raise ValueError(f"Trop de paquets (max {DEFAULTS['max_packages']}).")
    bad = [p for p in packages if not PKG_RE.match(p)]
    if bad:
        raise ValueError(f"Nom(s) de paquet invalide(s): {bad}")
    return image


def container_script(packages, no_recommends=False):
    """Script execute DANS le conteneur jetable : telecharge les .deb dans /out/debs."""
    rec = "--no-install-recommends " if no_recommends else ""
    # packages deja valides -> sûr a interpoler ; on les quote tout de meme.
    pkgs = " ".join(shlex.quote(p) for p in packages)
    return (
        "set -e; export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -qq; "
        "mkdir -p /out/debs; "
        "rm -f /var/cache/apt/archives/*.deb || true; "
        f"apt-get install -y {rec}--download-only {pkgs}; "
        "cp /var/cache/apt/archives/*.deb /out/debs/ 2>/dev/null || true; "
        # marqueur du nombre de .deb recuperes
        "ls -1 /out/debs/*.deb | wc -l > /out/.count"
    )


def docker_command(image, arch, out_host, script, limits):
    """Construit la commande `docker run` (liste d'arguments)."""
    platform = distros.PLATFORM.get(arch, "linux/amd64")
    return [
        "docker", "run", "--rm",
        "--platform", platform,
        "--memory", limits["memory"],
        "--cpus", limits["cpus"],
        "--pids-limit", limits["pids_limit"],
        # securite : pas de privileges, pas de socket docker monte
        "--cap-drop", "ALL",
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
        print("# [dry-run] commande Docker qui serait executee :\n")
        print(" ".join(shlex.quote(c) for c in cmd))
        print("\n# [dry-run] script dans le conteneur :\n")
        print(script)
        return None

    if shutil.which("docker") is None:
        raise RuntimeError("Docker introuvable sur l'hote.")

    print(f"[*] Recuperation de {packages} pour {distro} {release} ({arch})...")
    subprocess.run(cmd, check=True, timeout=limits["timeout"])

    safe_pkg = "-".join(packages)
    zip_name = f"{safe_pkg}_{distro}-{release}_{arch}.zip"
    zip_path = out_dir.parent / zip_name
    build_repo.build(out_dir, distro, release, packages, zip_path)
    print(f"[OK] Archive prete : {zip_path}")
    return zip_path


def main(argv=None):
    p = argparse.ArgumentParser(description="deb-downloader — recuperation de paquets .deb + dependances")
    p.add_argument("--distro", required=True, help="debian | ubuntu")
    p.add_argument("--release", required=True, help="ex: 13 (debian) ou 26.04 (ubuntu)")
    p.add_argument("--arch", default="amd64", help="amd64 (defaut)")
    p.add_argument("--packages", required=True, nargs="+", help="un ou plusieurs paquets")
    p.add_argument("--out", default=None, help="dossier de travail (defaut: temporaire)")
    p.add_argument("--no-recommends", action="store_true", help="exclure les paquets recommandes")
    p.add_argument("--timeout", type=int, default=DEFAULTS["timeout"])
    p.add_argument("--dry-run", action="store_true", help="affiche la commande sans l'executer")
    a = p.parse_args(argv)
    try:
        run(a.distro, a.release, a.arch, a.packages, out_dir=a.out,
            no_recommends=a.no_recommends, limits={"timeout": a.timeout},
            dry_run=a.dry_run)
    except (ValueError, RuntimeError) as e:
        print(f"[ERREUR] {e}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("[ERREUR] Timeout depasse.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
