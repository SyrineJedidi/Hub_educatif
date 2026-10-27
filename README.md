# Hub Éducatif Multimodal — Nexora

Deux interfaces séparées : le **site public** (template Eduleb, accueil et espaces étudiant/enseignant) et le **back-office** (template Soft UI Dashboard de Creative Tim, MIT) sous `/administration/*` pour l’administrateur et `/gestion/*` pour la gestion des fiches par l’enseignant. Chaque zone ne charge que les feuilles de style de son template. Les fichiers HTML et `assets/` du template original sont conservés comme référence dans `template/eduleb-original/`. Le README original est conservé dans `docs/EDULEB_ORIGINAL_README.md`.

React 19.2 / TypeScript 5.9 / Vite 7.3.7 ; Python 3.13 / Django 5.2.18 / DRF 3.16.1 / backend officiel MongoDB 5.2.4. Les versions transitives sont verrouillées dans `frontend/package-lock.json` et `backend/requirements.lock`. Aucune base SQL de remplacement.

La présentation générale et les objectifs définis par l’équipe sont conservés dans [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md). Modules disponibles : le socle commun utilisateurs/groupes/assiduité ; Cours et ressources (matières, chapitres, PDF, transcription audio Whisper — voir [docs/COURS.md](docs/COURS.md)) ; Quiz et progression (conception, génération locale de propositions avec Ollama, passage, correction, calendrier, progression, export PDF et retours étudiants — voir [le passage des quiz](docs/QUIZ-PASSAGE.md) et [les compléments du module](docs/QUIZ-PROGRESSION.md)) ; Résumés et illustrations (fiches de révision, résumés Gemini, illustrations Hugging Face — voir [docs/RESUMES-ILLUSTRATIONS.md](docs/RESUMES-ILLUSTRATIONS.md)) ; l’assistant pédagogique (réponses Gemini sourcées, questions vocales Whisper) ; Planification et coaching (objectifs, disponibilités, planning de révision proposé par Gemini, suivi par l’enseignant — voir [docs/PLANNING.md](docs/PLANNING.md)). Données de démonstration complètes : `manage.py seed_complete --password <mot de passe>` (voir ci-dessous) ; parcours de test de toute l’application : [docs/SCENARIO-COMPLET.md](docs/SCENARIO-COMPLET.md).

## Organisation du dépôt

```
backend/            API Django (une application par module : accounts, classrooms, attendance, courses, quizzes, revisions, assistant, planning)
  revisions/        module Résumés et illustrations
    ai/             clients Gemini / Ollama / Hugging Face, tâches de fond, métriques de qualité
    services/       règles métier (périmètres d’accès, contenu des fiches, suivi des étudiants)
    views/          API regroupée par domaine (fiches, illustrations, IA, révision)
    tests/          tests automatisés du module
frontend/           application React (Vite)
  src/layouts/front/        gabarit du site public
  src/layouts/backoffice/   gabarit du back-office
  src/styles/front/ · src/styles/backoffice/
  src/revisions/            pages/ components/ hooks/ styles/ du module
deploy/             Dockerfiles, configuration nginx, modèle de configuration de production
docker-compose.yml  pile complète : nginx + React, Django/gunicorn, worker Celery, MongoDB, Redis
docs/               documentation, scénarios de test, preuves (couverture, accessibilité)
```

## Déploiement

```bash
cp deploy/.env.production.example deploy/.env.production   # puis renseigner les secrets
docker compose up -d --build                                # http://localhost:8080
```

Guide complet (HTTPS, sauvegardes, mises à jour) : [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md).

## Travail en équipe

Chaque membre développe son module de bout en bout :
interface React, API Django, données, validations, tests et documentation.

| Branche prévue | Périmètre |
|---|---|
| `main` | Version commune intégrée et vérifiée. |
| `feature/cours-ressources` | Cours et ressources. |
| `feature/resumes-illustrations` | Résumés et illustrations. |
| `feature/assistant-pedagogique` | Assistant pédagogique. |
| `feature/quiz-progression` | Quiz et progression. |
| `feature/planning-coaching` | Planification et coaching. |

### Règles de contribution

1. Partir d’une version à jour de `main`.
2. Travailler sur une branche dédiée.
3. Réaliser des commits réguliers et explicites.
4. Vérifier son module et exécuter les tests concernés.
5. Ouvrir une Pull Request vers `main`.
6. Faire relire les modifications par un autre membre avant la fusion.
7. Résoudre les conflits avec les personnes concernées.

Chaque membre utilise son propre compte et sa propre identité Git.

### Exemple de création d’une branche

Depuis une copie locale du dépôt, sans modifications en attente :

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/quiz-progression
git push -u origin feature/quiz-progression
```

Si la branche existe déjà, la sélectionner au lieu de la recréer.

## Démarrage local — Windows PowerShell

Pré-requis : Python 3.13, Node.js 22.12 ou ultérieur et MongoDB accessible via `mongod` dans le PATH. Les vérifications de cette livraison ont utilisé Python 3.13.15, Node 22.23.2 et MongoDB 6.0. Docker n’est pas requis.

Depuis la racine de votre clone du dépôt :

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\backend\.venv\Scripts\python.exe scripts\init_env.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Start-Mongo.ps1
.\backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
.\backend\.venv\Scripts\python.exe backend\manage.py create_admin --email admin@votre-domaine.tn --first-name Votre --last-name Nom
.\backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
```

Le mot de passe administrateur est demandé de manière masquée et validé par Django. Aucun mot de passe par défaut. Un `.env` existant n’est jamais écrasé par `init_env.py`. Les environnements locaux et le fichier `.env` ne sont pas versionnés : exécutez ces commandes après clonage, puis créez votre administrateur unique. La commande refuse d’en créer un deuxième.

Dans un second terminal :

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

### Lancement en une commande (après l’installation)

Avec Docker Desktop démarré, `scripts\Start-Hub.ps1` lance MongoDB, Redis et Mailpit en conteneurs (redémarrage automatique), applique les migrations, ouvre Django, Celery, le worker des cours et Vite dans des fenêtres réduites, puis vérifie que l’API répond. Les parties déjà lancées sont conservées. `scripts\Stop-Hub.ps1` arrête les processus de l’application sans toucher aux données.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Start-Hub.ps1
.\backend\.venv\Scripts\python.exe backend\manage.py seed_complete --password "Nexora-Test-2026"   # données de démonstration, une fois
```

Ouvrir **http://127.0.0.1:5173/**. Le proxy Vite relaie `/api/` vers Django ; aucune session dans localStorage. Utiliser le même nom d’hôte pendant un parcours. Les séances sont affichées en **Africa/Tunis**, indépendamment du fuseau de Windows.

## MongoDB et emails

Le script démarre un replica set **nexora**, lié uniquement à `127.0.0.1:27019`, dans `.local/mongo`. Il vérifie l’identité d’une instance déjà présente sur ce port avant toute initialisation. Il ne touche pas aux instances sur 27017/27018. Fermer Django et Vite avec Ctrl+C ; pour arrêter MongoDB proprement, exécuter `scripts/stop_mongo.py` avec le Python du projet. Le script d’arrêt vérifie aussi l’identité du replica set et du dossier de données.

Base de développement : `nexora_hub`. Tests Django : `test_nexora_hub_isolated`. Tests navigateur actuels : `test_nexora_roles_browser_isolated` ; l’ancienne base `test_nexora_browser_isolated` est conservée intacte. Les tests Django recréent uniquement leur base dédiée. Les tests navigateur ajoutent des données identifiées par un suffixe aléatoire ; ils n’effacent aucune donnée existante. Ne configurez jamais les tests pour une base de production.

Le backend email local est **console** : demander un lien sur `/mot-de-passe-oublie`, puis consulter le terminal Django. Le lien n’apparaît jamais dans la réponse API. Il expire après une heure et après son utilisation ; se connecter entre sa génération et son utilisation peut aussi l’invalider (comportement du générateur Django). Les variables SMTP sont décrites dans `backend/.env.example`. Les tests emploient le backend mémoire, sans email réel. L’inscription ne dépend pas d’une vérification d’email ; les adresses restent non vérifiées.

## Vérifications

```powershell
# À la racine ; MongoDB doit être démarré
.\backend\.venv\Scripts\python.exe backend\manage.py check
.\backend\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\backend\.venv\Scripts\python.exe -m coverage run --source=accounts,classrooms,attendance,quizzes backend\manage.py test accounts quizzes --noinput
.\backend\.venv\Scripts\python.exe -m coverage report --omit="*/migrations/*,*/tests/*,*/tests.py,*/management/*"

Set-Location frontend
npm.cmd run build
npm.cmd audit
```

Pour reproduire les parcours Chromium et les captures comparées, voir [docs/TESTS.md](docs/TESTS.md). Les résultats réellement obtenus sont consignés dans [docs/VERIFICATIONS.md](docs/VERIFICATIONS.md).

## Fonctionnalités

- Sessions Django, CSRF sur toutes les écritures, limitation des tentatives, réinitialisation, profil et avatar validé/réencodé.
- Inscription avec choix Étudiant/Enseignant ; rôle ADMIN interdit en inscription publique. Administrateur unique protégé par un index MongoDB ; gestion globale, désactivation et dépendances de rôles conservées.
- Groupes, affectations, périodes d’inscription successives sans chevauchement, archivage et suppression des groupes sans dépendance.
- Séances, dates et chevauchements, annulation avec conservation de l’historique.
- Appel en brouillon puis validation, copie historique des participants, corrections motivées et refus des versions obsolètes.
- Statistiques autorisées par rôle, filtres et CSV protégé contre les formules.
- Pages « Fonctionnalité en préparation » pour les cinq modules futurs.

Séparation des interfaces et captures : [docs/FRONT_OFFICE.md](docs/FRONT_OFFICE.md).

Documentation : [API et rôles](docs/API.md), [architecture et conventions](docs/ARCHITECTURE.md), [références et licences](docs/THIRD_PARTY.md).

## Limites et configuration restante

Le code est intégré au dépôt partagé à partir d’un clone dédié. Le dépôt Git parent du profil Windows n’a pas été modifié. La publication GitHub ne constitue pas un déploiement de l’application. Les protections sont présentes dans l’API ; les modèles importés directement dans un shell sont réservés aux opérations techniques maîtrisées.

Le serveur Django de développement et le replica set mono-nœud lié à localhost servent à l’exécution locale. La production utilise la pile Docker décrite dans [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md) (gunicorn, nginx, HTTPS par un proxy, `DJANGO_DEBUG=false`). Restent à la charge de l’hébergeur : le nom de domaine et son certificat, l’authentification MongoDB et les sauvegardes planifiées, et le serveur SMTP.

L’archive mentionne MIT dans son README mais ne contient pas le texte intégral de la licence. Les crédits sont préservés ; l’autorisation d’utilisation des photographies n’est pas déduite de cette seule mention. Les polices Inter et Jost (SIL OFL) sont hébergées par l’application elle-même : aucune requête vers un service tiers au chargement.

Règles de rôles mises à jour : [docs/ROLES.md](docs/ROLES.md).

Module Quiz–Question : [gestion des quiz](docs/QUIZ.md), [validations](docs/QUIZ-VALIDATION.md), [passage et correction](docs/QUIZ-PASSAGE.md). Branche de livraison : `Syrine`, destinée à une Pull Request vers `main`. Le périmètre actuel et les contrôles de publication sont décrits dans [docs/PUBLICATION-SYRINE.md](docs/PUBLICATION-SYRINE.md).

Consultation des résultats des étudiants, réservée à l’enseignant propriétaire et à l’administrateur : [docs/QUIZ-RESULTATS.md](docs/QUIZ-RESULTATS.md).

Génération locale de propositions depuis un texte de cours, avec révision et confirmation avant ajout : [IA locale — Qwen3 via Ollama](docs/QUIZ-OLLAMA.md).

Calendrier, priorités, progression, export PDF, retours et interface FR/EN/AR : [compléments du module Quiz](docs/QUIZ-PROGRESSION.md).

## Grille de validation

Preuves par critère (tests, couverture, sécurité, accessibilité, métriques IA, CI et déploiement) : [docs/GRILLE-VALIDATION.md](docs/GRILLE-VALIDATION.md).

## Comptes de démonstration

`python manage.py seed_complete --password "<mot de passe>"` crée ou complète, à travers l’API, des données pour tous les comptes et tous les modules : groupes et séances avec appel, cours publiés avec supports PDF, quiz et tentatives aux scores variés, fiches de révision, notes de cours pour l’assistant, plannings de révision actifs. Les comptes partagent le mot de passe choisi et sont déjà confirmés :

| Compte (`@demo.nexora.test`) | Rôle et contenu |
|---|---|
| `admin` | Administrateur : back-office complet |
| `enseignant` | Biologie L1 (BIO-L1) : cours, fiches, quiz, notes de l’assistant |
| `enseignant2` | Informatique L2 (INFO-L2) : cours d’algorithmique, fiches, quiz |
| `etudiant`, `etudiant4`, `etudiant5`, `etudiant7` | Étudiants de BIO-L1 (plans de révision, tentatives, lectures) |
| `etudiante2`, `etudiant3`, `etudiant6` | Étudiants d’INFO-L2 (`etudiante2` et `etudiant5` suivent les deux groupes) |
| `etudiant.sans.groupe`, `ancien.etudiant` | Cas limites : aucun groupe, inscription terminée |

## Comptes et sécurité

Inscription, connexion et demandes d’email sont protégées par **ALTCHA** (anti-robot invisible et auto-hébergé : le navigateur résout une preuve de travail signée par le serveur, sans énigme ni service tiers — conforme au critère WCAG 2.2 3.3.8). Un nouveau compte s’active par le **lien de confirmation envoyé par email** ; la connexion reste refusée tant que l’adresse n’est pas confirmée, avec la possibilité de renvoyer l’email. Configuration : [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md).

### Emails en développement et en démonstration

Les emails (confirmation d’inscription, mot de passe oublié) sont envoyés en SMTP vers **Mailpit**, une boîte de réception locale :

```bash
docker run -d --name mailpit --restart unless-stopped -p 127.0.0.1:8025:8025 -p 127.0.0.1:1025:1025 axllent/mailpit:v1.20
```

Dans `backend/.env` : `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=127.0.0.1`, `EMAIL_PORT=1025`, `EMAIL_USE_TLS=false`. Les messages se lisent sur http://localhost:8025 (bouton « Confirmer mon adresse » cliquable). Pour de vrais envois vers les boîtes des utilisateurs, configurer Gmail ou un autre SMTP : voir [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md).

