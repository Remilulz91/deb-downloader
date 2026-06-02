"""deb-downloader — supported distributions.
Copyright (c) 2026 Remilulz91. All rights reserved.

Maps (distribution, version) -> official Docker image, plus architectures, and
handles EOL releases (whose apt mirrors moved to archive servers).
"""

# Key: (distro, release) -> base Docker image. Newest first per distro.
SUPPORTED = {
    ("debian", "13"): "debian:13",
    ("debian", "12"): "debian:12",
    ("debian", "11"): "debian:11",
    ("debian", "10"): "debian:10",      # EOL -> archive.debian.org
    ("debian", "9"): "debian:9",        # EOL -> archive.debian.org
    # Debian 8 (jessie) and older: their apt is too old and treats the expired
    # archive signature as unauthenticated (needs --force-yes), so they're not
    # offered (we don't fetch unsigned packages).
    ("ubuntu", "26.04"): "ubuntu:26.04",
    ("ubuntu", "24.04"): "ubuntu:24.04",
    ("ubuntu", "22.04"): "ubuntu:22.04",
    ("ubuntu", "20.04"): "ubuntu:20.04",
    # Ubuntu EOL releases are not offered for now: their packages are not
    # reliably fetchable anonymously (18.04 is still under ESM until 2028; 16.04
    # left ESM in 2026 but isn't cleanly published on old-releases yet). The
    # Ubuntu source-rewrite logic below is kept ready for when that stabilizes.
}

# End-of-life releases: apt sources must be repointed at archive mirrors and
# expired Release files tolerated. Best-effort (archives can be slow/flaky).
_EOL = {
    ("debian", "10"), ("debian", "9"),
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


# --- Third-party apt repos (beyond the base Debian/Ubuntu archives) ----------
# Each entry: the packages it provides; the GPG key URL; the `deb` line template
# ({arch}/{distro} substituted in Python, $CN = codename resolved in the
# container); the supported architectures; and explicitly blocked (distro,
# release) combos. All are amd64-only for now (installing the repo tools hangs
# under arm64 qemu emulation) and never offered on EOL releases.
THIRD_PARTY_REPOS = {
    "hashicorp": {
        "packages": {"packer", "terraform", "vault", "consul", "nomad",
                     "boundary", "waypoint", "vagrant"},
        "key_url": "https://apt.releases.hashicorp.com/gpg",
        "line": "deb [arch={arch}] https://apt.releases.hashicorp.com $CN main",
        "arches": {"amd64"},
        "blocked": {("ubuntu", "20.04")},  # packer pulls dozens of unrelated deps
    },
    "docker": {
        "packages": {"docker-ce", "docker-ce-cli", "containerd.io",
                     "docker-buildx-plugin", "docker-compose-plugin",
                     "docker-ce-rootless-extras"},
        "key_url": "https://download.docker.com/linux/{distro}/gpg",
        "line": "deb [arch={arch}] https://download.docker.com/linux/{distro} $CN stable",
        "arches": {"amd64"},
        "blocked": set(),
    },
}


def repo_for_packages(packages):
    """Return the third-party repo id needed for these packages, or None."""
    for rid, repo in THIRD_PARTY_REPOS.items():
        if any(p in repo["packages"] for p in packages):
            return rid
    return None


def repo_packages_in(repo_id, packages):
    """The requested packages that belong to the given third-party repo."""
    return sorted(set(packages) & THIRD_PARTY_REPOS[repo_id]["packages"])


def repo_supported(repo_id, distro, release, arch) -> bool:
    repo = THIRD_PARTY_REPOS[repo_id]
    if arch not in repo["arches"]:
        return False
    if is_eol(distro, release):
        return False
    if (distro.lower().strip(), release.strip()) in repo["blocked"]:
        return False
    return True


def repo_setup(repo_id, distro, release, arch):
    """Return (key_url, deb_line) for the repo, with {arch}/{distro} filled in."""
    repo = THIRD_PARTY_REPOS[repo_id]
    d = distro.lower().strip()
    return repo["key_url"].format(distro=d), repo["line"].format(arch=arch, distro=d)


def is_eol(distro: str, release: str) -> bool:
    return (distro.lower().strip(), release.strip()) in _EOL


def apt_opts(distro: str, release: str) -> str:
    """Extra apt-get options for the release ('' for live ones)."""
    # EOL archive Release files are expired -> tolerate that.
    return " -o Acquire::Check-Valid-Until=false" if is_eol(distro, release) else ""


def sources_fixup(distro: str, release: str) -> str:
    """Shell snippet (run before `apt-get update`) to repoint apt at archive
    mirrors for EOL releases. Returns '' for live releases."""
    if not is_eol(distro, release):
        return ""
    d = distro.lower().strip()
    if d == "debian":
        # EOL releases moved to archive.debian.org; older images may point at
        # deb.debian.org, httpredir.debian.org or http.debian.net. Drop the
        # -updates pocket (not kept on the archive).
        return (
            "sed -i -E 's|https?://deb\\.debian\\.org|http://archive.debian.org|g; "
            "s|https?://httpredir\\.debian\\.org|http://archive.debian.org|g; "
            "s|https?://http\\.debian\\.net|http://archive.debian.org|g; "
            "s|https?://security\\.debian\\.org|http://archive.debian.org|g' "
            "/etc/apt/sources.list 2>/dev/null || true; "
            "sed -i '/-updates/d' /etc/apt/sources.list 2>/dev/null || true; "
        )
    if d == "ubuntu":
        # xenial moved to old-releases.ubuntu.com; only the base suite remains
        # there (the -updates/-backports/-security pockets are gone -> 404).
        return (
            "sed -i -E 's|https?://[a-z.]*archive\\.ubuntu\\.com|http://old-releases.ubuntu.com|g; "
            "s|https?://security\\.ubuntu\\.com|http://old-releases.ubuntu.com|g' "
            "/etc/apt/sources.list 2>/dev/null || true; "
            "sed -i -E '/-(updates|backports|security)/d' /etc/apt/sources.list 2>/dev/null || true; "
        )
    return ""


def list_supported():
    """Serializable list for the /distributions API."""
    return [{"distro": d, "release": r, "image": img, "eol": (d, r) in _EOL}
            for (d, r), img in SUPPORTED.items()]
