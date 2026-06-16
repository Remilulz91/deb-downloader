# Security policy & model — deb-downloader

This document describes the **threat model**, what is **in scope** and **out of
scope**, the **hardening already in place**, and **how to report** a
vulnerability. The goal is to be honest about what this project is — a
self-hosted tool that fetches public Debian/Ubuntu packages — and to secure it
against the threats that actually apply, rather than ticking boxes that don't.

© 2026 Remilulz91 — All rights reserved.

---

## 1. What the application is (and isn't)

deb-downloader is a **self-hosted web tool**. It takes a distribution + a list of
package names (or an uploaded `dpkg status` file for system updates), resolves
the dependencies by running `apt` inside a **disposable Docker container**, and
returns a `.zip` (a local apt repository). It is meant to run on a **Linux host
on a local network, over plain HTTP** (optionally HTTPS).

Crucially, it has **no user accounts, no authentication, no database, no stored
secrets, no passwords, and no payment or personal data**. It only ever handles
**public** package data. This shapes the entire threat model: the assets worth
protecting are the **host** (don't let a request escape the sandbox or run
arbitrary code) and the **availability** of the service — not confidential data.

---

## 2. Threat model — what we defend against

The primary attack surface is **untrusted input** that reaches the engine, and
the **container** in which `apt` runs. The realistic threats are:

- **Command / code injection** through package names, version pins, or the
  uploaded status file.
- **Cross-site scripting (XSS)** through values reflected back into the UI.
- **Denial of service** (floods, oversized uploads, oversized fetches).
- **Sandbox escape / host compromise** from the fetch container.
- **Supply-chain compromise** (a malicious or vulnerable dependency, a leaked
  secret in the repo, a tampered CI action).

---

## 3. Hardening in place

### Input validation (Zero Trust)
Every value coming from a client is treated as hostile and validated:

- Package tokens must match a **strict allowlist regex**
  (`^[a-z0-9][a-z0-9+._-]*(=version)?$`) **and** be ≤ 200 chars — no shell
  metacharacters can survive. Distro/version are checked against a fixed
  **allowlist**; arch is restricted to `amd64`.
- Hard **length and count bounds** at the API edge (Pydantic / FastAPI `Form`):
  distro ≤ 32, release ≤ 16, ≤ 20 packages.
- The uploaded `dpkg status` file is **size-capped** (20 MB at the API, 25 MB at
  nginx) and **content-checked** (must look like a real status file). It is only
  ever read by `apt` **inside the disposable container** — never executed on the
  host.

### Injection-safe command construction
Package names are validated as above **and** passed through `shlex.quote` before
being interpolated into the container script. Third-party repo lines come from a
**hardcoded registry**, never from user input.

### Container isolation
The fetch runs in a **disposable** container (`--rm`) that is **non-privileged**:
`--cap-drop ALL` (only `DAC_OVERRIDE` added back to write the output),
`--security-opt no-new-privileges`, memory/CPU/PID limits, and **no host mounts
except the job's own output directory**. There is no Docker socket inside it.

### XSS & security headers
All values reflected into the UI are **HTML-escaped**. Both the API and nginx
send a **Content-Security-Policy** (no external scripts, no framing, plugins
blocked, network calls restricted to same origin / the GitHub API for the
version check), plus `X-Content-Type-Options`, `X-Frame-Options: DENY`,
`Referrer-Policy`, and `Permissions-Policy`.

### Denial-of-service mitigations
- **Rate limiting** at nginx (`limit_req` 20 r/s with burst, `limit_conn` per IP).
- **Per-job size quota** (optional `DDL_MAX_JOB_MB`) computed *before* download.
- A bounded **worker pool** (2 concurrent fetches) and per-job timeout.
- Upload size caps (above).

### Transport
Plain HTTP on a LAN by default; the installer offers **optional HTTPS**
(self-signed for a LAN, or your own certificate) with **HSTS** and a
80→443 redirect. SSH hardening on the host is provided via the optional
**fail2ban** jail (per-IP banning).

### Supply-chain & secrets
- Dependencies are pinned with a **secure lower bound** (prevents installing a
  known-vulnerable older version) and an upper major bound; a hashed,
  reproducible install is documented (`pip-compile --generate-hashes` +
  `pip install --require-hashes`).
- **Dependabot** proposes updates (pip, GitHub Actions, Docker).
- A **CI security workflow** runs secret scanning (gitleaks) and a dependency
  vulnerability audit (pip-audit) on every push/PR.
- `.gitignore` blocks committing certificates, keys and `.env` files; repo
  **secret scanning + push protection** are recommended in settings.
- Randomness (job IDs) uses the OS CSPRNG (`uuid4` → `os.urandom`), not a
  predictable PRNG.

---

## 4. Out of scope (and why)

These were considered and deliberately **not** implemented, because they don't
match this application's architecture. Listing them is part of the model.

- **Memory-safety exploits (buffer overflow/underflow):** the code is pure
  Python + browser JavaScript, both memory-managed. There are no manual buffers
  to overflow. (Native-code CVEs in dependencies are handled by the update
  process above.)
- **Authentication primitives (JWT, password hashing such as Argon2id):** there
  is **no login and no password** anywhere in the product. There is nothing to
  authenticate or to hash.
- **File/disk encryption (XChaCha20-Poly1305, LUKS2, Reed-Solomon, plausible
  deniability, post-quantum KEMs):** the tool produces archives of **public**
  packages; there is no secret or sensitive file to encrypt. Disk encryption is
  an OS-install concern, not the app's.
- **Encrypted SQLite / encrypted backups / internal password vaulting:** there
  is no database, no backup of sensitive data, and no internal password.
- **Tor / proxy-chain / reverse-proxy detection and blacklisting:** this is a
  tool you **self-host for yourself or your organisation**. Blocking proxies or
  Tor would only harm legitimate users and add maintenance, with no protective
  value here.

If the project ever grows accounts, stored secrets, or a multi-tenant
deployment, the relevant items above would move back **into** scope.

---

## 5. Reporting a vulnerability

Please report security issues **privately** rather than opening a public issue:
use GitHub's **"Report a vulnerability"** (Security → Advisories) on the
repository, or contact the author directly. Include reproduction steps and the
affected version. You'll get an acknowledgement and a fix timeline.

**Only the author publishes official releases**, which is the single trusted
source for security updates.
