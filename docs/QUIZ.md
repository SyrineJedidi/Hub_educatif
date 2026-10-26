# Quiz et progression — première étape

La suite du module (passage, reprise et correction automatique) est documentée dans [QUIZ-PASSAGE.md](QUIZ-PASSAGE.md). Le dépôt de travail actuel est `.local/publication` ; le périmètre et la synchronisation décrits ci-dessous correspondent à la livraison initiale du CRUD.

Les règles de saisie actuelles (titre de 50 caractères maximum, description et explication obligatoires, durée explicitement choisie) sont détaillées dans [QUIZ-VALIDATION.md](QUIZ-VALIDATION.md), avec le rapport des anciennes données non conformes.

Cette livraison implémente la conception et la gestion des Quiz et Question. Elle ne contient ni génération IA, ni passage de quiz, ni tentative, score ou tableau de progression. Les paramètres de durée et de tentatives sont enregistrés pour les étapes suivantes ; aucune action « Commencer » n’est affichée.

## Installation et migration

Depuis la racine du projet, avec l’environnement et MongoDB déjà configurés :

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py migrate
.\backend\.venv\Scripts\python.exe backend\manage.py check
.\backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
```

Puis, dans le terminal frontend existant : `npm.cmd run dev`. Aucune dépendance ni infrastructure supplémentaire. La migration `quizzes/0001_initial.py` crée deux collections, leurs index et la contrainte de position, sans modifier ni effacer les comptes, groupes ou séances existants.

## Modèles et règles

`Quiz` : titre obligatoire (150 caractères), description facultative (2 000), enseignant propriétaire, groupe pédagogique, niveau EASY/MEDIUM/HARD, durée positive ou `null` (illimitée), tentatives 1–10 (défaut 1), statut initial DRAFT, dates de création/modification et `published_at`.

`Question` : QCM à réponse unique, énoncé obligatoire (2 000 caractères), quatre propositions obligatoires (500 chacune), bonne réponse A/B/C/D, explication facultative en brouillon, points 1–10 et position positive unique dans le quiz. Les espaces successifs sont normalisés et la casse ignorée pour refuser des propositions identiques. Les champs requis composés uniquement d’espaces sont refusés.

Le nombre de questions et le total des points sont calculés à partir des questions lors de la lecture ; ils ne sont pas dupliqués en base.

- Création/modification : groupe actif et enseignant actif responsable de ce groupe.
- DRAFT : modification du contenu et des questions, suppression après confirmation.
- Publication dédiée : au moins une question valide, explication non vide pour chacune, groupe actif et affectation cohérente. Les raisons précises d’un refus sont retournées.
- PUBLISHED : verrouillage du quiz et des questions. Seule l’action dédiée d’archivage change le statut.
- ARCHIVED : conservation et verrouillage ; aucune suppression.
- Duplication d’un publié/archivé : nouveau DRAFT, nouvelles questions indépendantes avec positions et points copiés ; `published_at` reste nul. Si le groupe d’origine est archivé, le formulaire permet de choisir un groupe actif compatible.

Les bornes et choix sont vérifiés par DRF et `full_clean()`. La position est en plus protégée par un véritable index unique composé MongoDB `(quiz_id, position)` nommé `unique_question_position_in_quiz`. Aucune contrainte SQL `CHECK` n’est supposée disponible. Référence : [index du backend officiel MongoDB 5.2](https://www.mongodb.com/docs/languages/python/django-mongodb/v5.2/model-data/indexes/).

Les créations, publications, suppressions et déplacements réutilisent la garde transactionnelle commune existante. Une création sans position reçoit `max(position)+1` dans la transaction. Les déplacements renumérotent l’ordre complet de 1 à N ; des positions temporaires positives libres évitent les collisions d’index pendant l’échange. Une suppression peut laisser des positions libres, sans réécrire les autres questions. Un conflit persistant renvoie 409 : relire les données avant de réessayer ; le frontend ne rejoue pas silencieusement l’opération. Replica set MongoDB toujours requis, comme pour les autres modules.

La suppression d’un groupe contenant des quiz est refusée proprement avec une erreur métier ; il doit être archivé.

## Permissions

- **Enseignant** : uniquement ses propres quiz. Le propriétaire provient de la session ; un `teacher_id` envoyé par un enseignant est refusé.
- **Administrateur** : tous les quiz, avec les mêmes verrouillages. À la création/duplication/modification d’un brouillon, il sélectionne un enseignant actif et un groupe dont cet enseignant est responsable.
- **Étudiant** : seulement la présentation des quiz PUBLISHED de ses groupes non archivés, avec une inscription en cours à la date de consultation (`entrée ≤ maintenant < sortie`, ou sortie absente). Une inscription future ou terminée n’ouvre pas l’accès. Une inscription actuelle donne accès aux quiz déjà publiés du groupe.

Les serializers étudiants sont distincts. Aucune question, proposition, bonne réponse, explication, ni identifiant de question n’est renvoyé aux étudiants. Toutes les routes de gestion, de questions et d’actions leur sont interdites, y compris par URL directe. Les listes et détails enseignants sont limités au propriétaire ; les identifiants de questions doivent aussi appartenir au quiz indiqué dans l’URL.

Les sessions et protections CSRF existantes sont conservées. Les écritures exigent `X-CSRFToken`. Aucun sélecteur de rôle ou système de connexion supplémentaire.

## API

Toutes les routes sont sous `/api/` ; pagination des listes de quiz : `count`, `page`, `page_size=20`, `results`.

| Route | Méthodes | Usage |
| --- | --- | --- |
| `quizzes/` | GET, POST | Liste de gestion et création de brouillon |
| `quizzes/{id}/` | GET, PATCH, DELETE | Détail ; modification/suppression DRAFT uniquement |
| `quizzes/{id}/questions/` | GET, POST | Liste ordonnée et ajout |
| `quizzes/{id}/questions/{question_id}/` | GET, PATCH, DELETE | Gestion d’une question du quiz |
| `quizzes/{id}/reorder/` | POST | Ordre complet : `question_ids` sans doublon |
| `quizzes/{id}/preview/` | GET | Quiz, questions, corrections et `publication_blockers` |
| `quizzes/{id}/publish/` | POST | Publication dédiée, corps `{}` |
| `quizzes/{id}/archive/` | POST | Archivage d’un publié, corps `{}` |
| `quizzes/{id}/duplicate/` | POST | Nouveau brouillon ; paramètres éditables facultatifs |
| `student/quizzes/` | GET | Liste des présentations autorisées |
| `student/quizzes/{id}/` | GET | Présentation seule |

Filtres : `q` (titre), `status` (gestion), `level`, `group`, `teacher` (administrateur), `page`. Les filtres ne peuvent élargir le périmètre autorisé.

Création de quiz : `title`, `learning_group_id`, puis `description`, `level` (défaut EASY), `duration_minutes` (défaut null), `max_attempts` (défaut 1). L’administrateur ajoute obligatoirement `teacher_id`. PATCH est partiel. Les champs inconnus, `status`, dates, compteurs et propriétaire client enseignant sont refusés.

Question : `statement`, `choice_a`, `choice_b`, `choice_c`, `choice_d`, `correct_answer`, `points`, `explanation` facultatif et `position` facultative à l’ajout. PATCH est partiel. L’unicité de position est garantie aussi en cas de requêtes concurrentes.

Erreurs structurées conformes au projet : 400 validation/verrouillage, 401 session absente ou inactive, 403 rôle non autorisé/CSRF, 404 objet hors périmètre ou question d’un autre quiz, 409 conflit transactionnel.

## Pages et design

| Page | Front-office | Back-office |
| --- | --- | --- |
| Liste | `/espace/quiz` | `/administration/quiz` |
| Présentation / gestion des questions | `/espace/quiz/{id}` | `/administration/quiz/{id}` |
| Création | `/espace/quiz/nouveau` | `/administration/quiz/nouveau` |
| Modification | `/espace/quiz/{id}/modifier` | `/administration/quiz/{id}/modifier` |
| Ajout de question | `/espace/quiz/{id}/questions/nouvelle` | `/administration/quiz/{id}/questions/nouvelle` |
| Modification de question | `/espace/quiz/{id}/questions/{qid}/modifier` | `/administration/quiz/{id}/questions/{qid}/modifier` |
| Prévisualisation | `/espace/quiz/{id}/previsualisation` | `/administration/quiz/{id}/previsualisation` |
| Duplication | `/espace/quiz/{id}/dupliquer` | `/administration/quiz/{id}/dupliquer` |

Les étudiants accèdent uniquement aux deux premières pages en présentation. L’alias `/modules/quiz` dirige vers le bon espace ou la connexion. Les menus existants intègrent les quiz ; les autres futurs modules restent signalés en préparation. L’accueil public, sa composition et les styles globaux ne sont pas refaits.

Les styles du module sont limités à `.quiz-module` et à ses composants, avec la palette, les polices, cartes et boutons Eduleb. Les champs et dialogues partagés sont réutilisés ; les champs prennent désormais en charge des erreurs associées et un textarea a été ajouté.

Le routeur React conserve toutes les routes dans un RouterProvider pour utiliser le blocage officiel `useBlocker` : avertissement sur les liens internes et le retour navigateur, avertissement natif lors d’une fermeture/actualisation. Les mises à jour du RouterProvider utilisent `useTransitions=false` et le retour au formulaire est synchronisé : une transition concurrente différée ne peut ainsi rétablir une ancienne valeur juste après la fermeture du dialogue. Référence : [useBlocker](https://reactrouter.com/api/hooks/useBlocker). Les saisies sont gardées en cas d’erreur API et aucun brouillon local persistant n’est créé.

## Vérifications

Les contrôles de saisie détaillés de chaque champ et leur dernière vérification figurent dans [QUIZ-VALIDATION.md](QUIZ-VALIDATION.md).

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py check
.\backend\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\backend\.venv\Scripts\python.exe -m coverage run --source=accounts,classrooms,attendance,quizzes backend\manage.py test accounts quizzes --noinput
Set-Location frontend
npm.cmd run build
npx.cmd playwright test
```

Pour les serveurs de test, les ports existants restent 8002 et 5174. Le module fournit une configuration de base de test par exécution, pour que des relances rapprochées ne réutilisent pas les quotas d’inscription/connexion d’une exécution précédente. Les limites de sécurité restent actives, aucune ancienne base n’est supprimée.

Terminal backend, depuis la racine :

```powershell
$env:QUIZ_TEST_RUN = 'run' + (Get-Date -Format 'yyyyMMddHHmmss')
.\backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput --settings=config.quiz_e2e_settings
.\backend\.venv\Scripts\python.exe backend\manage.py prepare_browser --settings=config.quiz_e2e_settings
.\backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8002 --noreload --settings=config.quiz_e2e_settings
```

Terminal frontend : `$env:VITE_API_TARGET='http://127.0.0.1:8002'` puis `npm.cmd run dev -- --port 5174 --strictPort`. Le test de référence visuelle existant nécessite aussi `python -m http.server 8001 --bind 127.0.0.1` à la racine. Les identifiants aléatoires restent uniquement dans `.local`, hors Git. Voir également `TESTS.md`. `quizzes.spec.ts` couvre le scénario de démonstration complet, les rôles, les formulaires et erreurs réseau, la confidentialité, les dialogues/clavier, les contrôles axe et les captures.

Les résultats effectivement obtenus sont enregistrés dans `quiz-verification.json` et `QUIZ-VERIFICATIONS.md`. Les captures `screenshots/quiz-*` montrent la prévisualisation enseignant, la présentation étudiante et le back-office. Les contrôles axe et l’inspection visuelle par l’agent ne constituent pas un audit humain complet d’accessibilité.

## Git

Le clone du dépôt est `C:\Users\USER\Downloads\edu\.local\publication`, sur la branche locale `feature/quiz-progression`. Les fichiers de développement et l’aperçu local restent sous `C:\Users\USER\Downloads\edu`. Les changements du module sont synchronisés dans le clone pour être revus avec `git diff`. Aucun push ni fusion n’est effectué à cette étape.
