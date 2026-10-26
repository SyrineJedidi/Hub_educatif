# Vérifications avant déploiement — 26/10/2026

| Contrôle | Résultat |
|---|---|
| `python manage.py check --deploy` (DEBUG=false, HTTPS derrière proxy, cookies sécurisés) | Aucun problème |
| `python manage.py test` | 145 tests réussis |
| `npm run build` (TypeScript strict + Vite) | Réussi |
| `docker compose build` puis `up -d` | 5 conteneurs démarrés ; `backend`, `mongo` et `redis` « healthy » |
| `GET /api/health/` à travers nginx | `{"status": "ok", "database": "ok"}` |
| Routes de l’application monopage servies par nginx (`/espace/fiches`) | 200 |
| Parcours navigateur sur la pile Docker : connexion, back-office, fiche illustrée | Aucune erreur JavaScript ni réponse 5xx |
| Audit d’accessibilité axe-core (WCAG 2.1 A/AA), 18 pages, site public et back-office | 0 violation |

## Performances mesurées

| Mesure | Avant | Après |
|---|---|---|
| Liste des fiches (admin) | 38 requêtes MongoDB, 75 ms | 5 requêtes, 17 ms |
| Vue d’ensemble du module | 60 requêtes, 99 ms | 23 requêtes, 58 ms |
| Journal des générations IA | 25 requêtes, 38 ms | 5 requêtes, 14 ms |
| JavaScript initial | 1 fichier de 562 Ko (161 Ko gzip) | 57 Ko d’application + 288 Ko de bibliothèques mises en cache |
| CSS initial | 115 Ko | 40 Ko |
| Images du template | 12,7 Mo (PNG/JPEG) | 1,5 Mo (WebP) |
| Polices | 3 connexions vers Google Fonts (~800 ms) | hébergées localement, préchargées |
| Événement `load` de l’accueil (pile Docker) | 510 à 800 ms | ~70 ms |

En-têtes nginx vérifiés :
- compression gzip ;
- `Cache-Control: public, max-age=31536000, immutable` sur les fichiers versionnés ;
- `no-cache` sur `index.html` ;
- `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` et `Permissions-Policy`.
