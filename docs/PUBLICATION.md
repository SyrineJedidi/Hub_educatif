# Vérifications avant publication GitHub

Publication autorisée vers `SyrineJedidi/Hub_educatif`, branche `main`.

- Dépôt distant cloné dans un dossier isolé, sans utiliser ni modifier le dépôt parent du profil Windows.
- Base distante récupérée : `fa33b72` (les commits précédents restent dans l’historique).
- Présentation d’équipe conservée intégralement dans `PROJECT_BRIEF.md` ; règles de contribution également reprises dans le README courant.
- `.gitignore` distant conservé et complété pour Python, React, secrets, médias, données MongoDB, environnements et fichiers temporaires.
- Aucun secret local trouvé dans les fichiers candidats. Seuls les `.env.example` sans secret sont publiés.
- Build React/TypeScript : réussi.
- `manage.py check` : aucun problème.
- `makemigrations --check --dry-run` : aucune migration manquante.
- Tests Django : **39 réussis**, **0 échec**, 23,911 s sur une base MongoDB dédiée.
- Tests Chromium : **4 suites réussies**, **0 échec**, incluant les rôles, le scénario métier, les vues publiques et 54 combinaisons page/écran avec actualisation.

Les versions, commandes de démarrage et limites connues figurent dans le README, `TESTS.md`, `ARCHITECTURE.md`, `ROLES.md` et `FRONT_OFFICE.md`. Les cinq futurs modules restent explicitement en préparation. Cette publication Git ne déploie pas l’application.
