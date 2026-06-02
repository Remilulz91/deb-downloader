"""deb-downloader — supported distributions (MVP).
Copyright (c) 2026 Remilulz91. All rights reserved.

Maps (distribution, version) -> official Docker image, plus architectures.
Extend this dictionary to add new versions later.
"""

# Key: (distro, release) -> base Docker image. Newest first per distro.
# Only versions whose apt mirrors are still live are listed (EOL / non-LTS
# releases moved to archive mirrors and would fail).
SUPPORTED = {
    ("debian", "13"): "debian:13",
    ("debian", "12"): "debian:12",
    ("debian", "11"): "debian:11",
    ("ubuntu", "26.04"): "ubuntu:26.04",
    ("ubuntu", "24.04"): "ubuntu:24.04",
    ("ubuntu", "22.04"): "ubuntu:22.04",
    ("ubuntu", "20.04"): "ubuntu:20.04",
}

# Allowed architectures. arm64 on an amd64 host needs Docker binfmt/qemu
# emulation installed (see DEPLOY.md).
ARCHES = {"amd64", "arm64"}

# docker --platform matching the requested arch
PLATFORM = {
    "amd64": "linux/amd64",
    "arm64": "linux/arm64",
}


def image_for(distro: str, release: str) -> str:
    """Return the Docker image for (distro, release) or raise ValueError."""
    key = (distro.lower().strip(), release.strip())
    if key not in SUPPORTED:
        available = ", ".join(f"{d} {r}" for (d, r) in SUPPORTED)
        raise ValueError(
            f"Unsupported distribution: {distro} {release}. "
            f"Supported: {available}."
        )
    return SUPPORTED[key]


def list_supported():
    """Serializable list for the /distributions API."""
    return [{"distro": d, "release": r, "image": img}
            for (d, r), img in SUPPORTED.items()]
