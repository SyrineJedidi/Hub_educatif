# Déploiement en production

L’application se déploie avec Docker Compose : cinq conteneurs, une seule commande.

| Service | Image | Rôle |
|---|---|---|
| `frontend` | nginx 1.27 + build Vite | Sert l’application React, relaie `/api/` vers Django, compresse (gzip) et met en cache les fichiers versionnés pendant un an. Seul port exposé : **8080**. |
| `backend` | Python 3.12 + gunicorn | API Django. Au démarrage : migrations puis `collectstatic`. Vérification de santé sur `/api/health/` (ping MongoDB). |
| `worker` | même image que `backend` | Worker Celery qui traite les générations IA en arrière-plan. |
| `mongo` | MongoDB 7 | Replica set mono-nœud initialisé automatiquement (requis pour les transactions). Données dans le volume `mongo-data`. |
| `redis` | Redis 7 | File de tâches Celery. |

Les illustrations téléversées sont stockées dans le volume `media`, partagé par l’API et le worker.

## 1. Préparer la configuration

```bash
cp deploy/.env.production.example deploy/.env.production
```

Renseigner au minimum :

- `DJANGO_SECRET_KEY` : `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL` : le domaine public
- le serveur SMTP (réinitialisation de mot de passe)
- `GEMINI_API_KEY` et `HF_TOKEN` pour activer l’IA (vides : la saisie manuelle reste disponible)

`deploy/.env.production` est ignoré par Git : les secrets ne quittent jamais le serveur.

## 2. Lancer

```bash
docker compose up -d --build
docker compose ps          # tous les services « healthy »
```

Créer le premier administrateur :

```bash
docker compose exec backend python manage.py createsuperuser
```

Données de démonstration (facultatif, base de recette uniquement) :

```bash
docker compose exec backend python manage.py seed_demo --password "<mot de passe>"
```

## 3. HTTPS

Le conteneur `frontend` écoute en HTTP. En production, placer devant lui la terminaison TLS de l’hébergeur (ou Caddy / Traefik) qui transmet l’en-tête `X-Forwarded-Proto`. Avec `DJANGO_BEHIND_PROXY=true`, Django l’utilise pour :

- rediriger HTTP vers HTTPS (`DJANGO_SECURE_SSL_REDIRECT=true`) ;
- n’émettre que des cookies `Secure` ;
- envoyer HSTS (un an).

Essai local sans TLS : `DJANGO_SECURE_SSL_REDIRECT=false`, `DJANGO_SECURE_COOKIES=false` et `CSRF_TRUSTED_ORIGINS=http://localhost:8080`, puis ouvrir http://localhost:8080.

## 4. Exploitation

| Besoin | Commande |
|---|---|
| Journaux | `docker compose logs -f backend worker` |
| Mise à jour | `git pull && docker compose up -d --build` (migrations appliquées au démarrage) |
| Sauvegarde MongoDB | `docker compose exec mongo mongodump --archive > sauvegarde-$(date +%F).archive` |
| Restauration | `docker compose exec -T mongo mongorestore --archive < sauvegarde.archive` |
| Sauvegarde des images | volume Docker `nexora-hub_media` |
| Santé | `curl http://localhost:8080/api/health/` → `{"status": "ok", "database": "ok"}` |

## 5. Contrôles effectués avant livraison

- `python manage.py check --deploy` avec la configuration de production : voir le résultat dans `docs/VERIFICATIONS-DEPLOIEMENT.md`.
- Images construites et pile complète démarrée localement avec `docker compose up` ; parcours de connexion vérifié à travers nginx.
- Tests backend (`python manage.py test`) et build frontend (`npm run build`) réussis.

## Performances

- **Frontend** : chaque page est un fichier JavaScript chargé à la première visite. React et le routeur sont isolés dans des fichiers mis en cache entre deux versions. Les images du template sont converties en WebP (12,7 Mo → 1,5 Mo).
- **API** : les listes chargent auteurs, groupes et illustrations en une seule requête groupée. Par exemple, la liste des fiches passe de 38 à 5 requêtes MongoDB et de 75 à 17 ms.
- **nginx** : compression gzip ; fichiers versionnés en cache un an (`immutable`) ; `index.html` jamais mis en cache, pour publier une nouvelle version sans délai.
