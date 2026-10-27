# Résumés et illustrations

Module de gestion des fiches de révision : création, modification, organisation et export ; résumés générés avec **Gemini** (secours local **Ollama**) ; illustrations importées ou générées avec un modèle **Hugging Face**. Les générations IA s’exécutent **en arrière-plan** (Celery + Redis), sont suivies en temps réel dans un **Studio IA** et mesurées dans un tableau de bord **Pilotage IA**. Application Django `revisions`, pages React `frontend/src/revisions/`.

## Correspondance avec la grille d’évaluation

| Critère | Ce que le module apporte | Où le montrer |
|---|---|---|
| CRUD et cohérence | Fiches (CRUD complet, publication, archivage, duplication, export) et illustrations (import, génération, légende, ordre, suppression) ; validations serveur et client | Bibliothèque, fiche, éditeur |
| Tests unitaires et API | 27 tests du module + 2 tests de la commande de données, IA simulée | `manage.py test revisions` |
| Couverture | **94 %** du module | [coverage-revisions.txt](coverage-revisions.txt) |
| Sécurité | CSRF, ORM uniquement, clés IA côté serveur dans `.env`, images privées servies après contrôle d’accès, limites d’usage IA, téléchargement d’images restreint à l’adresse du Space | Code `revisions/`, `.env.example` |
| Permissions | Contrôle par rôle et par propriétaire sur chaque route (404 hors périmètre, y compris les images et les tâches IA), testé explicitement | Tests `test_isolation_*`, `test_rating_metrics_and_job_permissions` |
| Robustesse | Erreurs IA traduites, nouvelles tentatives automatiques, secours Ollama, tâches interrompues expirées, validation des fichiers | Studio IA, tableau de bord |
| Accessibilité | **0 violation axe** (WCAG 2.1 A/AA) sur 15 écrans dont mobile ; navigation clavier, focus visible, textes alternatifs obligatoires | `docs/axe-revisions-*.json` |
| IA : pertinence et intégration | Résumé structuré d’un cours, illustration pédagogique ; vues dédiées, clés en variables d’environnement | Studio IA |
| IA : retour utilisateur | Bouton flottant Studio IA, bandeau de progression avec chronomètre, statuts, messages d’erreur explicites, note de pertinence | Fiche |
| IA : métriques | Couverture des mots-clés, compression, conformité de structure, notes, taux de relecture, latences p50/p95 | [AI-EVALUATION.md](AI-EVALUATION.md), Pilotage IA |
| IA : asynchronisme | Réponse HTTP **202 en ~0,2 s**, génération dans un worker Celery (Redis) | Pilotage IA, journal du worker |
| UX/UI | Interface Eduleb cohérente, responsive (390 px sans débordement), impression A4 | Captures `docs/screenshots/revisions-*` |

## Configuration et démarrage

Dans `backend/.env` (les clés restent côté serveur, jamais dans le frontend) :

```env
GEMINI_API_KEY=...            # https://aistudio.google.com/apikey
REVISIONS_GEMINI_MODEL=gemini-3.5-flash
HF_TOKEN=hf_...               # jeton Hugging Face
HF_IMAGE_SPACE=black-forest-labs/FLUX.1-schnell   # Space public (quota GPU gratuit) ; vide = API payante HF_IMAGE_MODEL
HF_IMAGE_MODEL=stabilityai/stable-diffusion-3-medium-diffusers
AI_TIMEOUT_SECONDS=90
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b         # secours local facultatif (vide = désactivé)
REVISIONS_OLLAMA_TIMEOUT_SECONDS=300
CELERY_BROKER_URL=redis://127.0.0.1:6379/0   # vide = file de tâches intégrée (sans infrastructure)
```

Avec Celery, lancer Redis puis un worker, en plus de Django et Vite :

```powershell
docker run -d --name nexora-redis -p 127.0.0.1:6379:6379 redis:7-alpine
.\backend\.venv\Scripts\celery.exe -A config worker --pool=solo --loglevel=info   # depuis backend\
```

Sans `CELERY_BROKER_URL`, les générations passent par une file de threads intégrée au serveur : le comportement (202 puis suivi) est identique, sans infrastructure supplémentaire. Si Redis devient injoignable, la tâche bascule automatiquement sur cette file. Sans clé IA, le module fonctionne en saisie manuelle ; le Studio IA indique ce qui n’est pas configuré.

Dépendances ajoutées : `pypdf` (texte des PDF), `celery` et `redis` (traitement asynchrone), verrouillées dans `requirements.lock`. Migrations : `revisions/0001_initial.py` (fiches, illustrations) et `0002_aijob.py` (tâches IA).

## Modèles

`RevisionSheet` : titre (120), cours/matière (120), résumé Markdown limité (20 000), points clés (15 × 300), glossaire (20 entrées, termes uniques), étiquettes (8 × 30, normalisées), couleur, épinglage, statut DRAFT/PUBLISHED/ARCHIVED, propriétaire, groupe, traçabilité IA (`ai_generated`, `ai_reviewed`, `ai_model`, `generated_at`, `source_name`, `illustration_prompt`).

`Illustration` : image privée réencodée en WebP (1600 px max), description accessible obligatoire (300), origine UPLOAD/AI, prompt et modèle, dimensions, position. 12 au plus par fiche.

`AIJob` : une génération (résumé ou illustration) avec son statut QUEUED/RUNNING/SUCCEEDED/FAILED, le moteur et le modèle réellement utilisés, le recours au secours, l’erreur, l’attente en file, la durée, les métriques de qualité et la note de pertinence. Le texte du cours n’est conservé que le temps du traitement.

## Règles et permissions

- **Enseignant** : ses propres fiches, destinées à l’un de ses groupes actifs ; publication pour le groupe ; ses propres statistiques IA.
- **Étudiant** : fiches personnelles privées (jamais publiables, IA comprise) et lecture des fiches publiées de ses groupes avec une inscription en cours ; « Ajouter à mes fiches » crée une copie personnelle.
- **Administrateur** : toutes les fiches (création au nom d’un enseignant) et le tableau de bord *Pilotage IA* de toute la plateforme.
- Hors périmètre ⇒ 404, y compris pour les images et les tâches IA. Seul l’auteur d’une génération peut la noter. Toutes les écritures passent par la garde transactionnelle commune et la protection CSRF.

Cycle de vie : DRAFT → PUBLISHED → DRAFT (retrait) ; ARCHIVED en lecture seule, restaurable. Une fiche publiée ne change ni de groupe ni de propriétaire et ne peut pas être supprimée sans retrait préalable.

Conditions de publication : fiche valide, groupe actif, résumé d’au moins 40 caractères, au moins un point clé, **relecture confirmée si le contenu a été généré par l’IA**, descriptions des illustrations renseignées.

## Intelligence artificielle

### Traitement asynchrone

1. `POST sheets/{id}/generate/` (ou `illustrations/generate/`) valide l’entrée, applique les limites d’usage, enregistre une `AIJob` et répond **202 Accepted** avec la tâche, en environ 0,2 s.
2. La tâche est confiée au worker Celery via Redis (ou à la file intégrée). L’appel externe s’exécute hors de toute transaction ; seul le résultat est écrit, de façon atomique, sous la garde commune.
3. L’interface interroge `GET ai/jobs/{id}/` toutes les 1,5 s, affiche un bandeau de progression avec chronomètre et met à jour la fiche à la fin, sans rechargement. L’utilisateur peut continuer à travailler.
4. Si la fiche a été publiée, archivée ou supprimée pendant la génération, le résultat n’est pas appliqué (la tâche échoue avec un message explicite). Une tâche bloquée par un redémarrage est marquée en échec et peut être relancée.

### Moteurs

**Gemini** : texte collé (60 000 caractères) ou PDF/TXT/MD (10 Mo, 80 pages). Réponse JSON contrainte par un schéma puis nettoyée côté serveur. La longueur demandée s’adapte au cours (environ 30 à 60 % d’un extrait court) pour que le résumé condense toujours. Le contenu remplace résumé, points clés et glossaire, fusionne les étiquettes et exige une nouvelle relecture. Génération interdite sur une fiche publiée ou archivée.

**Secours Ollama** : si Gemini échoue (surcharge, quota, modèle retiré, refus), le même schéma est demandé au modèle local `qwen3:8b` (réflexion désactivée, texte limité à 30 000 caractères). Le moteur réellement utilisé est enregistré et affiché.

**Hugging Face** : FLUX.1-schnell sur son Space public (API Gradio, quota GPU gratuit rattaché au jeton), ou API Inference Providers si `HF_IMAGE_SPACE` est vide. Gemini propose une description d’illustration préremplie. L’image n’est téléchargée que depuis l’adresse du Space, puis validée et réencodée.

Limites : 20 résumés et 12 illustrations par utilisateur et par heure ; une seule génération de résumé à la fois par fiche. Les réponses 429/503 sont relancées deux fois (2 s puis 5 s).

### Interface

- **Bouton flottant « Studio IA »** sur la fiche (avec le nombre de générations en cours) et **« Créer avec l’IA »** sur la bibliothèque.
- **Panneau Studio IA** : moteurs actifs, deux actions claires (*Résumer un cours*, *Créer une illustration*) avec la raison si elles sont indisponibles, et l’activité de la fiche (statut, durée, couverture des mots-clés, structure, note).
- **Note de pertinence** de 1 à 5 étoiles après chaque résumé, aussi proposée dans le bandeau de relecture.
- **Pilotage IA** (`/administration/pilotage-ia` ; `/espace/fiches/pilotage-ia` pour un enseignant, limité à ses générations) : indicateurs clés, générations par jour, latences p50/p95 par moteur, distribution des notes, qualité mesurée, erreurs principales, journal des dernières générations.

### Métriques et évaluation

Chaque résumé est mesuré automatiquement (`revisions/metrics.py`) :

- **Couverture des mots-clés** : part des 15 termes les plus fréquents du cours retrouvés dans le résumé, les points clés ou le glossaire (rappel des notions essentielles).
- **Compression** : mots du résumé ÷ mots du cours (doit rester sous 100 %).
- **Conformité de structure** : sections titrées, nombre de points clés, glossaire, longueur dans la cible, idée d’illustration.
- Signaux humains : note de pertinence et taux de contenus relus avant publication.

La commande `manage.py evaluate_ai` passe un corpus fixe de 6 cours (biologie, informatique, histoire, physique, économie, chimie) et 3 illustrations dans le vrai pipeline, puis écrit [AI-EVALUATION.md](AI-EVALUATION.md). Deux campagnes réelles ont été menées le 26/10/2026 :

| Indicateur | v1 (longueur fixe) | v2 (longueur adaptée) |
|---|---|---|
| Résumés réussis | 6 / 6 | 6 / 6 (dont 2 via le secours Ollama, Gemini étant surchargé) |
| Compression moyenne | 90 % (2 résumés plus longs que le cours) | **49 %** |
| Conformité de structure | 80 % | **100 %** |
| Couverture des mots-clés | 97 % | 91 % (93 à 100 % avec Gemini, 73 % sur un résumé Ollama) |
| Durée médiane / p95 | 19,2 s / 34,0 s | 42,1 s / 127,7 s (surcharge de Gemini et recours au modèle local) |
| Illustrations | 3 / 3, médiane 14,4 s | 3 / 3, médiane 11,6 s |

Lecture : la v1 révélait que, sur des extraits courts, le modèle respectait la longueur demandée au lieu de condenser. L’adaptation de la cible au cours a corrigé la compression et la structure. Les durées de la v2 reflètent une surcharge réelle du service de Google ; le secours local a évité tout échec, au prix d’une génération plus lente, ce qui justifie le traitement asynchrone. Rapport initial conservé : [AI-EVALUATION-v1.md](AI-EVALUATION-v1.md).

## API

Toutes les routes sont sous `/api/`. Pagination standard (`count`, `page`, `page_size=20`, `results`).

| Route | Méthodes | Usage |
| --- | --- | --- |
| `sheets/` | GET, POST | Liste filtrée et création |
| `sheets/facets/` | GET | Cours, étiquettes et compteurs du périmètre |
| `sheets/{id}/` | GET, PATCH, DELETE | Détail, modification partielle, suppression |
| `sheets/{id}/publish/` · `unpublish/` · `archive/` | POST `{}` | Changements de statut |
| `sheets/{id}/duplicate/` | POST `{}` | Copie (personnelle pour un étudiant) |
| `sheets/{id}/export/` | GET | Export Markdown |
| `sheets/{id}/generate/` | POST JSON ou multipart | Lance un résumé IA → **202** + tâche |
| `sheets/{id}/jobs/` | GET | Générations de la fiche (auteur, administrateur) |
| `sheets/{id}/illustrations/` | GET, POST multipart | Liste et import |
| `sheets/{id}/illustrations/generate/` | POST | Lance une illustration IA → **202** + tâche |
| `sheets/{id}/illustrations/reorder/` | POST | Ordre complet des illustrations |
| `sheets/{id}/illustrations/{iid}/` | PATCH, DELETE | Légende, suppression |
| `sheets/{id}/illustrations/{iid}/image/` | GET | Image WebP privée |
| `ai/status/` | GET | Moteurs disponibles (sans aucune clé) |
| `ai/jobs/{id}/` | GET | Suivi d’une génération |
| `ai/jobs/{id}/rating/` | POST `{rating: 1-5}` | Note de pertinence (auteur) |
| `ai/metrics/?days=30` | GET | Indicateurs (administrateur : plateforme ; enseignant : les siens) |

Filtres des fiches : `q`, `scope` (`mine`, `groups`, `pinned`), `status`, `course`, `tag`, `group`, `teacher` (admin), `sort` (`title`, `created`).

## Pages

| Page | Espace | Administration |
| --- | --- | --- |
| Bibliothèque | `/espace/fiches` | `/administration/fiches` |
| Création (`?ia=1` : parcours guidé IA) | `/espace/fiches/nouvelle` | `/administration/fiches/nouvelle` |
| Lecture + Studio IA | `/espace/fiches/{id}` | `/administration/fiches/{id}` |
| Modification | `/espace/fiches/{id}/modifier` | `/administration/fiches/{id}/modifier` |
| Pilotage IA | `/espace/fiches/pilotage-ia` (enseignant) | `/administration/pilotage-ia` |

Le résumé est rendu par un mini-moteur Markdown produisant des éléments React (aucun HTML injecté). Styles limités au module, palette Eduleb, responsive jusqu’à 390 px, impression A4.

## Accessibilité

Audit **axe-core** (règles WCAG 2.1 A et AA) sur 15 écrans : bibliothèque, fiche, fiche IA à relire, panneau Studio IA, dialogue de résumé, édition, création guidée, statistiques (enseignant, étudiant, administrateur), et vues mobiles 390 px. Résultat : **0 violation** ; aucun débordement horizontal en mobile. Rapports : `docs/axe-revisions-*.json`. L’audit a permis de corriger une structure de liste de définitions invalide et un tableau trop large en mobile. Mesures appliquées : boutons-icônes étiquetés, groupes de boutons `aria-pressed`, étoiles de notation en boutons radio, régions de progression `role="status"`, graphique doublé d’un tableau de données et accessible au clavier, `prefers-reduced-motion` respecté.

## Comptes et données de test

`manage.py seed_demo --password "<mot de passe>"` remplit toute l’application (8 comptes, 3 groupes, 9 séances, 4 quiz, 4 tentatives, 8 fiches). Scénarios : [SCENARIO-COMPLET.md](SCENARIO-COMPLET.md) (toute l’application) et [SCENARIO-RESUMES-ILLUSTRATIONS.md](SCENARIO-RESUMES-ILLUSTRATIONS.md) (ce module).

## Vérifications

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py test revisions accounts.tests.test_seed_demo --noinput
.\backend\.venv\Scripts\python.exe -m coverage run --source=backend/revisions backend\manage.py test revisions --noinput
.\backend\.venv\Scripts\python.exe -m coverage report
.\backend\.venv\Scripts\python.exe backend\manage.py evaluate_ai   # appels IA réels, quelques minutes
Set-Location frontend; npm.cmd run build
```
