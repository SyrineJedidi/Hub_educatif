# Hub Éducatif Multimodal — Nexora

Module commun « Utilisateurs, groupes et assiduité ». L’accueil et toutes les pages étudiant/enseignant partagent le front-office Eduleb : header horizontal, menu mobile, avatar et footer. Le back-office React avec sidebar est exclusivement réservé à l’administrateur sous `/administration/*`. Les fichiers HTML et `assets/` à la racine restent les références originales. Le README original est conservé dans `docs/EDULEB_ORIGINAL_README.md`.

React 19.2 / TypeScript 5.9 / Vite 7.3.7 ; Python 3.13 / Django 5.2.18 / DRF 3.16.1 / backend officiel MongoDB 5.2.4. Les versions transitives sont verrouillées dans `frontend/package-lock.json` et `backend/requirements.lock`. Aucune base SQL de remplacement.

La présentation générale et les objectifs définis par l’équipe sont conservés dans [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md). Le socle commun utilisateurs/groupes/assiduité, le module Cours et ressources et le module Quiz–Question (conception, passage, reprise et correction automatique) sont disponibles. Les autres modules, la génération IA et les statistiques avancées de progression restent à développer. Voir [le passage des quiz](docs/QUIZ-PASSAGE.md).

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
.\backend\.venv\Scripts\python.exe -m coverage run --source=accounts,classrooms,attendance,quizzes,courses,ai backend\manage.py test accounts quizzes courses --noinput
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
- Cours et ressources : matières, chapitres, PDF et enregistrements audio, texte extrait et transcrit, recherche, progression et statistiques. Voir la section dédiée ci-dessous.
- Pages « Fonctionnalité en préparation » pour les modules encore à développer.

Séparation des interfaces et captures : [docs/FRONT_OFFICE.md](docs/FRONT_OFFICE.md).

Documentation : [API et rôles](docs/API.md), [architecture et conventions](docs/ARCHITECTURE.md), [références et licences](docs/THIRD_PARTY.md).

## Cours et ressources

Module disponible pour les enseignants, les étudiants et l’administrateur : matières, cours partagés avec des groupes, chapitres, import de PDF et d’enregistrements audio, extraction du texte des PDF, transcription Whisper, correction des textes générés, recherche, consultation, progression et statistiques exportables en CSV. Règles, limites et contrat pour le futur assistant : [docs/COURS.md](docs/COURS.md). Routes : [docs/API.md](docs/API.md#cours-et-ressources).

Après la mise à jour du dépôt, réinstaller `backend\requirements.lock` (ajout de `pypdf`) puis exécuter `migrate`. Les variables suivantes se placent dans `backend/.env` ; absentes, elles prennent la valeur par défaut, aussi indiquée dans `backend/.env.example`.

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `WHISPER_PROVIDER` | `disabled` | `disabled`, `fake` (tests et démonstrations, n’écoute pas l’audio), `local` (faster-whisper) ou `groq` |
| `WHISPER_MODEL`, `WHISPER_CPU_THREADS` | `small`, `2` | Modèle et threads du fournisseur local |
| `WHISPER_LANGUAGE` | vide | Langue imposée, par exemple `fr` ; vide : détection automatique |
| `GROQ_API_KEY`, `GROQ_WHISPER_MODEL` | vide, `whisper-large-v3-turbo` | Fournisseur Groq ; la clé reste côté serveur |
| `COURSES_PROCESS_INLINE` | `false` | `true` : transcrire pendant la requête d’import, pour des démonstrations sur des fichiers courts |
| `COURSES_MAX_PDF_MB`, `COURSES_MAX_AUDIO_MB` | `20`, `25` | Tailles maximales en Mo |
| `COURSES_MAX_PDF_PAGES`, `COURSES_MAX_AUDIO_SECONDS` | `300`, `7200` | Pages d’un PDF ; durée d’un audio, vérifiée par le fournisseur local |

Les PDF sont traités pendant l’import. Les audios restent « En attente » jusqu’au passage du worker, à lancer dans un terminal supplémentaire, MongoDB démarré :

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py process_course_jobs
```

`--once` traite les tâches disponibles puis s’arrête ; Ctrl+C arrête le worker après la tâche en cours.

Transcription locale, facultative et sans service externe : installer le fichier ci-dessous en plus de `requirements.lock`, puis définir `WHISPER_PROVIDER=local`. Le modèle est téléchargé depuis Hugging Face au premier usage. Avec `groq`, l’enregistrement est envoyé au service Groq.

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-whisper.txt
```

Tests du module, sans réseau ni vrai modèle (fournisseur `fake`) :

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py test courses --noinput
```

## Limites et configuration restante

Le code est intégré au dépôt partagé à partir d’un clone dédié. Le dépôt Git parent du profil Windows n’a pas été modifié. La publication GitHub ne constitue pas un déploiement de l’application. Les protections sont présentes dans l’API ; les modèles importés directement dans un shell sont réservés aux opérations techniques maîtrisées.

Le serveur Django de développement et le replica set mono-nœud lié à localhost servent à l’exécution locale. Une production nécessite une clé secrète propre, HTTPS, `DJANGO_DEBUG=false`, hôtes/origines explicites, MongoDB authentifié avec sauvegardes, SMTP choisi et un serveur adapté. Le routage du frontend doit réécrire ses routes vers `index.html` et relayer `/api/` sans mise en cache des réponses privées.

L’archive mentionne MIT dans son README mais ne contient pas le texte intégral de la licence. Les crédits sont préservés ; l’autorisation d’utilisation des photographies n’est pas déduite de cette seule mention. Les polices Google restent chargées à distance, comme dans le template.

Règles de rôles mises à jour : [docs/ROLES.md](docs/ROLES.md).

Module Quiz–Question : [gestion des quiz](docs/QUIZ.md), [validations](docs/QUIZ-VALIDATION.md), [passage et correction](docs/QUIZ-PASSAGE.md). Branche de livraison : `Syrine`, destinée à une Pull Request vers `main`. Le périmètre actuel et les contrôles de publication sont décrits dans [docs/PUBLICATION-SYRINE.md](docs/PUBLICATION-SYRINE.md).

Consultation des résultats des étudiants, réservée à l’enseignant propriétaire et à l’administrateur : [docs/QUIZ-RESULTATS.md](docs/QUIZ-RESULTATS.md).
