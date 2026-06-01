# deb-downloader

> Récupérez un paquet **Debian / Ubuntu** et **toutes ses dépendances**, prêts pour une installation **hors-ligne / air-gapped**, sans toucher à la ligne de commande.

Copyright © 2026 **Remilulz91** — Tous droits réservés. Projet sous licence propriétaire (voir [`LICENSE`](LICENSE)).

---

## Ce dépôt

Ce dépôt contient le **site web** de deb-downloader : une vitrine statique
qui présente le projet et **indique automatiquement à l'utilisateur s'il
dispose de la dernière version** (sans mise à jour automatique).

Le site est **100 % statique** (HTML/CSS/JS, sans build ni dépendance) et
se déploie par simple **glisser-déposer** sur n'importe quel hébergement.

```
deb-downloader/
├─ index.html      ← le site complet (CSS + JS intégrés)
├─ 404.html        ← page d'erreur
├─ LICENSE         ← licence propriétaire
├─ CHANGELOG.md    ← historique des versions
└─ README.md
```

## L'indicateur de version

À l'ouverture, la page interroge l'API publique GitHub Releases
(`/releases/latest`) et compare la **dernière version publiée** à la
**version embarquée** dans la copie déployée. Elle affiche alors :

- ✅ **À jour** — la copie correspond à la dernière release ;
- ⚠️ **Mise à jour disponible** — une release plus récente existe (lien fourni) ;
- ℹ️ / ❓ — aucune release publiée, ou vérification impossible (hors-ligne, quota API).

> **À chaque nouvelle release :** modifiez `CONFIG.version` en haut du
> bloc `<script>` dans `index.html` avec le tag publié (ex. `v0.2.0`),
> puis publiez. C'est ce numéro qui sert de référence « cette copie ».

## Déploiement (au choix, tous en glisser-déposer)

- **GitHub Pages** — Settings → Pages → branche `main`, dossier `/root`. Gratuit, lié au dépôt.
- **Cloudflare Pages / Netlify** — glissez le dossier, ou connectez le dépôt.
- **Hébergement mutualisé (FTP)** — déposez les fichiers dans le dossier web public.

Aucun serveur Linux, aucun nginx, aucun paquet à installer ne sont
nécessaires **pour le site**.

> ℹ️ Le **moteur** qui récupère réellement les `.deb` (résolution des
> dépendances via `apt` dans des conteneurs Docker) s'exécute côté
> serveur et fait l'objet d'un développement séparé. Cette partie, elle,
> nécessite un hôte Linux + Docker.

## Contribuer

Les retours de la communauté sont les bienvenus : ouvrez une
[issue](https://github.com/Remilulz91/deb-downloader/issues) pour signaler
un bug ou proposer une idée. **Seul l'auteur publie les versions
officielles.**

## Licence

Projet **propriétaire**. Réutilisation, redistribution ou appropriation
interdites sans autorisation écrite. Voir [`LICENSE`](LICENSE).
