# Grille de validation — preuves par critère

Hub Éducatif Multimodal, équipe Nexora (5TWIN). Chaque critère de la grille renvoie à une preuve du dépôt et à la commande qui la reproduit. Mesures du 27/10/2026 sur la branche `main`.

## Git, intégration et déploiement

| Exigence | Preuve |
|---|---|
| Git | Chaque membre travaille sur sa branche ; tout est intégré dans `main` par des fusions documentées (`git log --merges`). |
| Intégration continue | [.github/workflows/ci.yml](../.github/workflows/ci.yml) : à chaque push et pull request, tests Django sur un replica set MongoDB avec couverture, build React et audit npm, puis construction et démarrage de la pile Docker complète avec test de fumée à travers nginx. |
| Déploiement | `docker compose up -d --build` : 6 services (nginx + React, Django/gunicorn, worker Celery, worker des cours, MongoDB, Redis). Guide : [DEPLOIEMENT.md](DEPLOIEMENT.md) ; vérifications : [VERIFICATIONS-DEPLOIEMENT.md](VERIFICATIONS-DEPLOIEMENT.md). |

## 1. Fonctionnalités et CRUD

Six modules complets, chacun avec création, lecture, modification et suppression (ou archivage quand l’historique doit être conservé), validations côté serveur et côté client :

| Module | Entités principales |
|---|---|
| Socle commun | utilisateurs, groupes, inscriptions, séances, feuilles d’appel |
| Cours et ressources | matières, cours, chapitres, ressources PDF et audio, extraits |
| Résumés et illustrations | fiches de révision, illustrations, cartes de révision |
| Assistant pédagogique | conversations, messages, notes de cours, avis, signalements |
| Quiz et progression | quiz, questions, tentatives, réponses, retours |
| Planification et coaching | objectifs, échéances, disponibilités, plannings, tâches |

Parcours complet : [SCENARIO-COMPLET.md](SCENARIO-COMPLET.md). Données de démonstration pour tous les comptes et tous les modules, créées à travers l’API : `python manage.py seed_complete --password <mot de passe>` (voir le README).

## 2. Tests et besoins non fonctionnels

| Critère | Preuve |
|---|---|
| Tests unitaires et d’intégration | **618 tests** (modèles, règles métier, API : statuts HTTP et données). `cd backend; python manage.py test` |
| Couverture | **97 %** sur 8 969 instructions ([coverage-summary.txt](coverage-summary.txt)) : assistant, planning et IA 100 %, quiz 98,8 %, cours 96,6 %, assiduité 93,9 %, comptes 93,3 %, résumés 92,8 %, groupes 92,1 %. `python -m coverage run --rcfile=../.coveragerc manage.py test` puis `python -m coverage report --rcfile=../.coveragerc` |
| Sécurité | CSRF actif sur toutes les mutations, ORM uniquement, mots de passe hachés, `DEBUG=False` et cookies sécurisés en production (`python manage.py check --deploy` sans avertissement), secrets dans `backend/.env` ignoré par Git, clés IA uniquement côté serveur. **Comptes** : anti-robot ALTCHA (preuve de travail auto-hébergée, invisible, sans énigme ni service tiers, conforme WCAG 2.2 3.3.8 ; défi signé HMAC, lié au formulaire, expirant et à usage unique) sur l’inscription, la connexion et les demandes d’email, vérifié côté serveur et lié au formulaire ; **confirmation de l’adresse par lien email** (signé, valable trois jours, invalidé si l’adresse change) avant la première connexion ; limitation du nombre d’essais ; réponses identiques que l’adresse existe ou non. |
| Rôles et permissions | Contrôle par le serveur sur chaque vue (étudiant, enseignant, administrateur) ; un accès par URL directe répond 403/404. Tests de permissions dans chaque module ; matrice : [ROLES.md](ROLES.md). |
| Robustesse | Pages 400/404/500 personnalisées (API et site), validation des entrées, erreurs des services IA traduites en messages clairs, quotas et délais. |

## 3. Accessibilité

Audit axe-core (WCAG 2.1 A et AA) de **119 pages** atteintes depuis les menus, pour les quatre profils (visiteur, étudiant, enseignant, administrateur) : **0 violation** ([axe-audit-complet.json](axe-audit-complet.json)). Balises `header`, `nav`, `main`, `footer`, lien d’évitement, hiérarchie des titres, `alt` et `aria-label`, contrastes AA (palette vérifiée), focus visible, navigation au clavier, interface du quiz en arabe (droite à gauche) contrôlée.

## 4. Intelligence artificielle

| Module | Cas d’usage | Intégration | Métriques mesurées | Asynchronisme |
|---|---|---|---|---|
| Cours et ressources | Transcription des enregistrements de cours (Whisper) et extraction des PDF | worker `process_course_jobs` | durée audio, durée de traitement, fournisseur, extraits ([COURS.md](COURS.md)) | file de tâches, 3 tentatives |
| Résumés et illustrations | Fiche de révision depuis un cours (Gemini, secours Ollama) et illustration (Hugging Face) | Celery + Redis, état suivi par la page | couverture des mots-clés, structure, longueur, durée, note de l’enseignant ([AI-EVALUATION.md](AI-EVALUATION.md)) | Celery |
| Assistant pédagogique | Réponses sourcées à partir des cours (Gemini), questions vocales (Whisper) | recherche des extraits, refus hors cours sans appel au modèle | **hit@1 100 %, refus hors cours 100 %, 0 refus à tort, latence médiane 1,1 s** ([ASSISTANT-IA-EVALUATION.md](ASSISTANT-IA-EVALUATION.md)) | réponse en ~1 s |
| Quiz et progression | Propositions de QCM depuis un cours (Ollama, qwen3:8b), relues avant ajout | tâche en arrière-plan, la page interroge la tâche | **9/9 questions valides, ancrage dans le cours 78 %, 100 % d’énoncés distincts, 28 à 51 s** ([QUIZ-IA-EVALUATION.md](QUIZ-IA-EVALUATION.md)) | Celery (202 puis suivi) |
| Résumés — aide à l’étudiant | **Quiz d’entraînement** rédigé à partir d’une fiche ; **plan de révision du jour** sur l’accueil | tâche Celery pour le quiz ; le plan n’ordonne que des éléments repérés par la plateforme (fiches non lues, cartes, quiz échoués, tâches) | quiz : 4/4 questions valides, **ancrage dans la fiche 90 %**, réponses réparties sur A–D ; plan : raisons factuelles, jamais rédigées par le modèle | Celery / cache 3 h |
| Planification | Planning de révision proposé par Gemini, repli sur des règles | quotas par étudiant et global, tâches hors créneaux écartées | durée, jetons, tâches proposées/retenues ([PLANNING.md](PLANNING.md)) | réponse en ~3 s |

Toutes les clés sont dans `backend/.env` ; chaque échec d’un fournisseur (quota, délai, réponse invalide) donne un message explicite à l’utilisateur, sans perdre la saisie. Le contenu produit par l’IA est relu par l’enseignant avant d’être partagé.

## 5. UX / UI

Une seule identité visuelle pour les six modules (site public et back-office Soft UI), responsive (vérifiée à 390 et 1440 px), parcours par rôle, animations désactivées si l’utilisateur demande moins de mouvement.
