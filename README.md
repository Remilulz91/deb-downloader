# deb-downloader

> Grab a **Debian / Ubuntu** package and **all of its dependencies**, ready for an **offline / air-gapped** install — without touching the command line.

Copyright © 2026 **Remilulz91** — All rights reserved. Proprietary license (see [`LICENSE`](LICENSE)).

---

## This repository

This repository contains the **website** for deb-downloader: a static landing
page that presents the project and **automatically tells visitors whether they
are running the latest version** (no auto-update). The site is bilingual
(English / French).

The site is **100% static** (HTML/CSS/JS, no build step, no dependencies) and
deploys by simply **dropping the files** onto any web host.

```
deb-downloader/
├─ index.html        ← the whole site (CSS + JS inlined), bilingual EN/FR
├─ 404.html          ← error page
├─ LICENSE           ← proprietary license
├─ CHANGELOG.md      ← version history
├─ DEPLOY.md         ← self-hosting tutorial (Debian 13 + nginx + Docker)
├─ ARCHITECTURE.md   ← backend engine design
├─ deploy/           ← ready-made nginx / Docker Compose / fail2ban configs
└─ backend/          ← the package-fetching engine (separate component)
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
- **Self-hosting with nginx + Docker** — see [`DEPLOY.md`](DEPLOY.md) for a full
  step-by-step tutorial (Debian 13, local HTTP, optional UFW + fail2ban).

No Linux server, nginx config or package install is required **for the site**
unless you choose to self-host it.

> ℹ️ The **engine** that actually fetches the `.deb` files (dependency
> resolution via `apt` inside Docker containers) runs server-side and is
> developed separately under `backend/`. That part does require a Linux host
> with Docker.

## Contributing

Community feedback is welcome: open an
[issue](https://github.com/Remilulz91/deb-downloader/issues) to report a bug or
suggest an idea. **Only the author publishes official releases.**

## License

**Proprietary** project. Reuse, redistribution or appropriation prohibited
without written permission. See [`LICENSE`](LICENSE).
