# deb-downloader

> Grab a **Debian / Ubuntu** package and **all of its dependencies** — or a
> **full system update** for an offline machine — as a ready-to-use `.zip`,
> without touching the command line. Built for **offline / air-gapped** installs.

Copyright © 2026 **Remilulz91** — All rights reserved. Proprietary license (see [`LICENSE`](LICENSE)).

---

## This repository

This repository holds the whole **deb-downloader** project: the static landing
page (with a built-in version indicator, bilingual EN/FR) **and** the engine +
HTTP API that actually fetches the packages.

👉 **To install it on your own machine, follow [`DEPLOY.md`](DEPLOY.md)** — a
single, step-by-step guide (Debian 13) covering both the website and the engine.

The landing page is **100% static** (HTML/CSS/JS, no build step, no
dependencies) and can also be dropped onto any web host as-is.

```
deb-downloader/
├─ index.html        ← the whole site (CSS + JS inlined), bilingual EN/FR
├─ 404.html          ← error page
├─ favicon.svg       ← site icon
├─ LICENSE           ← proprietary license
├─ CHANGELOG.md      ← version history
├─ DEPLOY.md         ← full self-hosting guide (website + engine/API)
├─ ARCHITECTURE.md   ← backend engine design
├─ THIRD_PARTY_PACKAGES.md ← bundled third-party repos (Docker, GitLab, …)
├─ deploy/           ← ready-made nginx / Compose / systemd / fail2ban configs
└─ backend/          ← the package-fetching engine + HTTP API
```

## The version indicator

On load, the page queries the public GitHub Releases API
(`/releases/latest`) and compares the **latest published version** with the
**version embedded** in the deployed copy. It then shows:

- ✅ **Up to date** — the copy matches the latest release;
- ⚠️ **Update available** — a newer release exists (link provided);
- ℹ️ / ❓ — no release published yet, or the check failed (offline, API limit).

> **On every new release:** update `CONFIG.version` near the top of the
> `<script>` block in `index.html` with the published tag (e.g. `v0.2.0`),
> then publish. That number is the "this copy" reference.

## Deployment

The website is static, so you have several easy options:

- **GitHub Pages** — Settings → Pages → branch `main`, folder `/root`. Free, tied to the repo.
- **Cloudflare Pages / Netlify** — drag-and-drop the folder, or connect the repo.
- **Shared hosting (FTP)** — drop the files into the public web folder.
- **Self-hosting (website + engine/API)** — see [`DEPLOY.md`](DEPLOY.md) for the
  full step-by-step guide (Debian 13, local HTTP, optional UFW + fail2ban).

No Linux server, nginx config or package install is required **for the site**
unless you choose to self-host it.

> ℹ️ The **engine** that actually fetches the `.deb` files (dependency
> resolution via `apt` inside Docker containers) runs server-side under
> `backend/` and requires a Linux host with Docker. Beyond fetching packages,
> it can also build a **full offline system update** bundle: upload the target
> machine's `/var/lib/dpkg/status` in the **System update** tab and get a
> `.zip` with exactly the updates that machine needs within its release
> (kernel and security fixes included). Setup is covered in
> [`DEPLOY.md`](DEPLOY.md) (Part 2).

## Contributing

Community feedback is welcome: open an
[issue](https://github.com/Remilulz91/deb-downloader/issues) to report a bug or
suggest an idea. **Only the author publishes official releases.**

## License

**Proprietary** project. Reuse, redistribution or appropriation prohibited
without written permission. See [`LICENSE`](LICENSE).
