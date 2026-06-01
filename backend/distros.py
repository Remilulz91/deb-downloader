"""deb-downloader — distributions supportees (MVP).
Copyright (c) 2026 Remilulz91. Tous droits reserves.

Mapping (distribution, version) -> image Docker officielle, et architectures.
On etend ce dictionnaire pour ajouter de nouvelles versions plus tard.
"""

# Cle: (distro, release) -> image Docker de base
SUPPORTED = {
    ("debian", "13"): "debian:13",
    ("ubuntu", "26.04"): "ubuntu:26.04",
}

# Architectures autorisees (MVP: amd64 uniquement)
ARCHES = {"amd64"}

# docker --platform correspondant a l'arch demandee
PLATFORM = {
    "amd64": "linux/amd64",
    "arm64": "linux/arm64",
}


def image_for(distro: str, release: str) -> str:
    """Retourne l'image Docker pour (distro, release) ou leve ValueError."""
    key = (distro.lower().strip(), release.strip())
    if key not in SUPPORTED:
        dispo = ", ".join(f"{d} {r}" for (d, r) in SUPPORTED)
        raise ValueError(
            f"Distribution non supportee: {distro} {release}. "
            f"Supportees: {dispo}."
        )
    return SUPPORTED[key]


def list_supported():
    """Liste serialisable pour l'API /distributions."""
    return [{"distro": d, "release": r, "image": img}
            for (d, r), img in SUPPORTED.items()]
