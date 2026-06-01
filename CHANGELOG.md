# Changelog

Toutes les versions notables de **deb-downloader** sont documentées ici.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)
et le projet adhère au [versionnage sémantique](https://semver.org/lang/fr/).

## [v0.3.0] — 2026-06-01
### Ajouté
- **Moteur backend — MVP** (`backend/`) : récupération de paquets `.deb` +
  dépendances via un conteneur Docker jetable, et assemblage d'une archive
  `.zip` (dépôt local hors-ligne).
  - `fetch.py` : orchestration Docker (conteneur non privilégié, ressources
    limitées, timeout), validation stricte des entrées, mode `--dry-run`.
  - `build_repo.py` : génération de l'index APT (`Packages.gz` via
    `dpkg-scanpackages`), `INSTALL.txt`, compression `.zip`.
  - `distros.py` : distributions supportées (Debian 13, Ubuntu 26.04, amd64).
  - `README.md` du backend + `requirements.txt`.
- Packaging validé de bout en bout (index + zip) avec paquets de test.

[v0.3.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.3.0

## [v0.2.0] — 2026-06-01
### Ajouté
- Site multilingue **français / anglais** : bouton de bascule FR/EN,
  détection automatique de la langue du navigateur, choix mémorisé, et
  bannière de version traduite.
- Templates `.github/` : modèle de notes de release, configuration des
  notes auto (`release.yml`), templates d'issues (bug / idée) et de PR.
- `ARCHITECTURE.md` : conception du moteur backend (Python/FastAPI,
  orchestration Docker, sortie .zip, file de jobs, sécurité, MVP).

### Modifié
- Formulation de la sortie clarifiée : **archive .zip** téléchargeable en
  un clic (dépôt local prêt à l'emploi à l'intérieur).

## [v0.1.0] — 2026-06-01
### Ajouté
- Site vitrine statique (HTML/CSS/JS, sans dépendance ni build).
- Indicateur de version automatique : la page compare la version
  embarquée à la dernière release publiée sur GitHub et indique à
  l'utilisateur s'il est à jour ou non (pas de mise à jour automatique).
- Sections : présentation, fonctionnalités, « comment ça marche »,
  contribution / signalement de bugs.
- Licence propriétaire (tous droits réservés).

[v0.2.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.2.0
[v0.1.0]: https://github.com/Remilulz91/deb-downloader/releases/tag/v0.1.0
