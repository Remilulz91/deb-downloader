# Third-party packages

Some tools aren't published in the base Debian/Ubuntu archives. **deb-downloader**
knows a small set of official third-party apt repositories and adds the right one
**automatically** when you request one of their packages — you don't configure
anything. Just type the exact package name in the *Package(s)* field.

How it works: when a requested name matches one of the providers below, the engine
adds that provider's signed apt repository inside the disposable container, then
downloads the package and all its dependencies into your `.zip`, exactly like a
normal package.

## Rules that always apply

- **Architecture: `amd64` only.** These repositories are offered for amd64.
- **No EOL releases.** Third-party repos are not offered on end-of-life
  distributions (e.g. Debian 9/10). Use a supported release
  (Debian 11/12/13, Ubuntu 20.04/22.04/24.04/26.04).
- **A few combos are blocked** when they pull in dozens of unrelated packages
  (see notes per provider).
- If a provider doesn't publish for the distro/version you picked, the tool tells
  you clearly instead of producing a broken archive.

## Pinning a specific version

For any package you can request an exact version with the apt syntax
**`name=version`**, e.g.:

```
gitlab-ce=18.10.0-ce.0
docker-ce=5:27.3.1-1~debian.13~trixie
terraform=1.9.8-1
```

Leave the version off (`gitlab-ce`) to get the latest the repository offers. If
the exact version string doesn't exist, the tool reports it (so you can adjust).

---

## Docker

Official Docker CE repository (`download.docker.com`).

| Package | What it is |
| --- | --- |
| `docker-ce` | Docker Engine (daemon) |
| `docker-ce-cli` | The `docker` command-line client |
| `containerd.io` | Container runtime |
| `docker-buildx-plugin` | `docker buildx` plugin |
| `docker-compose-plugin` | `docker compose` plugin |
| `docker-ce-rootless-extras` | Rootless mode helpers |

**Typical request:** `docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`

## GitLab (Community Edition)

Official GitLab packagecloud repository, which keeps the **full version history**.

| Package | What it is |
| --- | --- |
| `gitlab-ce` | GitLab Omnibus (Community Edition) — bundles its own runtime |

**Notes**
- GitLab is large (~1 GB+). Mind the per-job size quota if one is set.
- Upgrades require going through **mandatory stop versions in order**, so this is
  where pinning matters most: `gitlab-ce=18.10.0-ce.0`, then the next step, etc.
- The Omnibus package bundles its runtime, so you don't need to match dependency
  versions separately.

**Typical request:** `gitlab-ce=18.10.0-ce.0`

## Wazuh

Official Wazuh 4.x apt repository (`packages.wazuh.com/4.x`).

| Package | What it is |
| --- | --- |
| `wazuh-agent` | Endpoint agent |
| `wazuh-manager` | Manager / server |
| `wazuh-indexer` | Indexer |
| `wazuh-dashboard` | Web dashboard |

**Typical request:** `wazuh-agent`

## HashiCorp

Official HashiCorp repository (`apt.releases.hashicorp.com`).

| Package | What it is |
| --- | --- |
| `packer` | Image builder |
| `terraform` | Infrastructure as code |
| `vault` | Secrets management |
| `consul` | Service mesh / discovery |
| `nomad` | Workload orchestrator |
| `boundary` | Secure remote access |
| `waypoint` | Application deployment |
| `vagrant` | Dev environments |

**Notes**
- **Blocked on Ubuntu 20.04** (the repo pulls in dozens of unrelated
  dependencies there). Use another supported release.

**Typical request:** `packer` or `terraform=1.9.8-1`

---

## Everything else

Any package **not** listed above is fetched from the standard Debian/Ubuntu
archives — just type its name (e.g. `nginx`, `build-essential`, `gnome-core`).
You can mix base packages and third-party packages in the same request as long as
they come from the same provider context for the chosen distro/version.

> **Updating a whole machine?** Fetching packages is for *installing* software.
> To bring an offline machine fully up to date within its release (kernel and
> security fixes included), use the **System update** tab instead: upload that
> machine's `/var/lib/dpkg/status` and you'll get a `.zip` with exactly the
> updates it needs.
