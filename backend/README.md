# deb-downloader — backend (moteur de recuperation)

> Copyright (c) 2026 Remilulz91 — Tous droits reserves.
> MVP : Debian 13 et Ubuntu 26.04 (amd64). Voir `../ARCHITECTURE.md`.

Ce dossier contient le **moteur** qui recupere un paquet + toutes ses
dependances et produit une archive `.zip` (depot local hors-ligne). Il est
independant du site vitrine et **doit tourner sur un hote Linux avec Docker**.

## Prerequis (hote / VM Linux)
- Docker installe et fonctionnel (`docker run hello-world`)
- `dpkg-dev` (fournit `dpkg-scanpackages`) : `sudo apt-get install -y dpkg-dev`
- Python >= 3.10 (aucune dependance pip pour le MVP)

## Utilisation (ligne de commande)
```bash
# Voir la commande sans rien executer (utile pour comprendre/auditer)
python3 fetch.py --distro ubuntu --release 26.04 --packages nginx --dry-run

# Recuperer nginx + dependances pour Ubuntu 26.04 -> archive .zip
python3 fetch.py --distro ubuntu --release 26.04 --packages nginx

# Plusieurs paquets, dossier de sortie choisi, sans recommends
python3 fetch.py --distro debian --release 13 --packages nginx curl \
    --out ./out --no-recommends
```
L'archive `<paquets>_<distro>-<release>_<arch>.zip` est creee a cote du dossier
de travail. Son contenu : `debs/*.deb`, `Packages.gz`, `Packages`, `INSTALL.txt`.

## Comment ca marche (resume)
1. `fetch.py` valide les entrees (distrib supportee, noms de paquets surs).
2. Il lance un conteneur Docker **jetable** (`--rm`, non privilegie, ressources
   limitees) de l'image cible, qui fait `apt-get install --download-only`.
3. Les `.deb` (paquet + dependances) sont copies dans `out/debs/`.
4. `build_repo.py` genere l'index APT (`dpkg-scanpackages`), ecrit `INSTALL.txt`
   et compresse le tout en `.zip`.

## Securite
Conteneurs jetables et non privilegies (`--cap-drop ALL`,
`--security-opt no-new-privileges`, `--memory`, `--cpus`, `--pids-limit`),
timeout, et validation stricte des noms de paquets (`^[a-z0-9][a-z0-9+._-]*$`)
pour empecher toute injection.

## Fichiers
- `fetch.py` — orchestration Docker + CLI (point d'entree)
- `build_repo.py` — index APT + INSTALL.txt + zip (host-side)
- `distros.py` — distributions/versions supportees
- `requirements.txt` — vide pour le MVP (etape API plus tard)

## Etape suivante
Envelopper `fetch.py` dans une API FastAPI + file de jobs Redis/RQ
(voir `../ARCHITECTURE.md`, sections 5 et 9).
