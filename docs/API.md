# API, routes et droits

Toutes les écritures exigent le cookie de session lorsqu’elles sont privées et un jeton CSRF, y compris les écritures publiques. Obtenir `csrfToken` via `GET /api/csrf/`, puis envoyer `X-CSRFToken`. La connexion renouvelle le jeton ; utiliser celui retourné par le serveur. Les réponses privées portent `Cache-Control: private, no-store`.

| Route `/api/…` | Méthodes | Accès / fonction |
| --- | --- | --- |
| `csrf/` | GET | Public, pose le cookie CSRF |
| `auth/register/` | POST | Public, prénom/nom/email/password/confirmation/role ; role obligatoire : STUDENT ou TEACHER, ADMIN refusé |
| `auth/login/` | POST | Public, email/password, retourne user et csrfToken |
| `auth/logout/` | POST | Compte actif, invalide la session |
| `auth/me/` | GET | Compte actif, utilisateur courant |
| `auth/password/reset/` | POST | Public, email, réponse neutre |
| `auth/password/confirm/` | POST | Public, token/password/confirmation |
| `auth/password/change/` | POST | Compte actif, old_password/password/confirmation, déconnecte toutes les sessions |
| `profile/` | GET, PATCH | Soi-même, seuls first_name/last_name modifiables |
| `profile/avatar/` | GET, POST multipart, DELETE | Soi-même, champ avatar |
| `admin/users/` | GET | ADMIN, `q`, `role`, `active`, `page` |
| `admin/users/{id}/` | GET, PATCH | ADMIN, role/is_active uniquement ; pas de suppression |
| `groups/` | GET, POST | Lecture limitée au rôle ; création ADMIN |
| `groups/{id}/` | GET, PATCH, DELETE | Lecture autorisée ; modification/suppression ADMIN |
| `enrollments/` | GET, POST | Lecture autorisée, étudiant = soi uniquement ; création ADMIN |
| `enrollments/{id}/` | PATCH | ADMIN, renseigne ends_at sans effacer l’inscription |
| `sessions/` | GET, POST | Lecture autorisée, création ADMIN ou enseignant du groupe |
| `sessions/{id}/` | GET, PATCH | Même périmètre ; étudiant lecture seule |
| `sessions/{id}/sheet/` | GET, POST, PUT | ADMIN ou enseignant responsable ; GET consulte, POST ouvre, PUT sauvegarde |
| `statistics/` | GET | Périmètre du rôle ; étudiant = ses propres lignes |
| `statistics/export/` | GET | ADMIN ou enseignant des groupes concernés |

Pagination : `count`, `page`, `page_size=20`, `results`. Groupes : filtres `q`, `archived`. Inscriptions : `group`. Séances/statistiques/CSV : `group`, `from`, `to` (dates ISO 8601 avec offset), séances également `status`. La borne `from` est inclusive, `to` exclusive sur le début de la séance. Utilisateurs : `q` nom/email, `role` en majuscules, `active=true|false`. Les sélections de groupes non autorisés retournent 403, sans données.

Les créations de groupes attendent `name`, `code`, `level`, `academic_year`, `teacher_id`, et facultativement `description`, `archived`. Les PATCH de groupe attendent ces mêmes champs nécessaires (le formulaire renvoie l’état complet). Code ASCII alphanumérique, tiret et souligné, normalisé en majuscules.

Inscription : `group_id`, `student_id`, `starts_at`, `ends_at` facultatif. Fin d’inscription : `ends_at` uniquement. Une période close reste immuable ; une réinscription crée une autre ligne.

Séance : `group_id`, `title`, `starts_at`, `ends_at`, et facultativement `description`, `location`, `status` (`PLANNED`, `COMPLETED`, `CANCELLED`). PATCH attend les champs nécessaires, comme la création. Pas de suppression des séances. Si une feuille existe, groupe et horaires restent figés. Une séance annulée conserve sa feuille consultable et n’accepte plus de saisie.

Sauvegarde d’appel :

```json
{
  "version": 0,
  "entries": [{"student_id": "ObjectId MongoDB", "status": "PRESENT", "comment": ""}],
  "validate_sheet": false,
  "reason": ""
}
```

La liste doit correspondre exactement aux participants historiques, sans doublon. Statuts : `UNSET`, `PRESENT`, `ABSENT`, `LATE`, `EXCUSED`. La validation interdit `UNSET` et les feuilles vides. Après validation, chaque sauvegarde exige un motif non vide et la feuille reste validée. Un conflit de version retourne 409 : relire la feuille et réconcilier les changements. Le frontend ne rejoue pas automatiquement une saisie obsolète.

Erreurs : `{"error":{"code":"…","message":"…","fields":{…}}}`. Codes HTTP : 400 validation, 401 session absente/expirée, 403 permissions ou CSRF, 404 identifiant absent/invalide, 409 concurrence, 429 limitation. Les serializers rejettent les champs inconnus ; aucune attribution ADMIN depuis une inscription publique. Le rôle enseignant est maintenant accessible au choix à l’inscription. L’API d’administration refuse d’attribuer ADMIN à un autre compte.

## Planification des révisions et coaching

Règles, formats de réponse et génération Gemini : [PLANNING.md](PLANNING.md). Les routes `student/planning/…` sont réservées au rôle STUDENT, qui ne voit que ses propres données (404 sinon). Les routes `planning/students/…` sont réservées aux rôles TEACHER et ADMIN et n’acceptent que GET.

| Route `/api/…` | Méthodes | Accès / fonction |
| --- | --- | --- |
| `student/planning/goals/` | GET, POST | Objectifs, filtre `status` ; title, description, learning_group_id (groupe actuel), target_date, priority, estimated_hours |
| `student/planning/goals/{id}/` | GET, PATCH, DELETE | PATCH partiel, avec status ; suppression refusée si des tâches utilisent l’objectif |
| `student/planning/deadlines/` | GET, POST | Échéances triées par date, filtre `upcoming=true\|false` ; title, kind, due_at (futur), goal_id, notes |
| `student/planning/deadlines/{id}/` | GET, PATCH, DELETE | PATCH partiel ; la suppression détache les tâches liées |
| `student/planning/availability/` | GET, POST | Créneaux hebdomadaires et `weekly_minutes` ; weekday 0–6, start_time, end_time au quart d’heure |
| `student/planning/availability/{id}/` | PATCH, DELETE | PATCH partiel |
| `student/planning/groups/` | GET | Groupes de l’inscription en cours, pour le formulaire d’objectif |
| `student/planning/context/` | GET | Données prises en compte par la génération et état de l’IA (quota restant) |
| `student/planning/dashboard/` | GET | Planning actif, tâches du jour et des 7 jours suivants, avancement, série, échéances |
| `student/planning/plans/` | GET | Plannings paginés, filtres `status`, `page` |
| `student/planning/plans/generate/` | POST | start_date, end_date (1 à 28 jours, à partir d’aujourd’hui), mode `ai` ou `rules`, title facultatif ; 201 brouillon |
| `student/planning/plans/{id}/` | GET, PATCH, DELETE | Détail avec conseils et tâches ; PATCH title ; suppression d’un brouillon ou d’un planning archivé |
| `student/planning/plans/{id}/activate/` | POST | Corps `{}` ; archive le planning actif précédent |
| `student/planning/plans/{id}/archive/` | POST | Corps `{}` ; planning en lecture seule |
| `student/planning/plans/{id}/ics/` | GET | Fichier iCalendar `planning-{id}.ics` |
| `student/planning/plans/{id}/tasks/` | POST | Tâche manuelle : title, description, goal_id, deadline_id, starts_at, ends_at |
| `student/planning/tasks/{id}/` | PATCH, DELETE | PATCH partiel ; status TODO, DONE ou SKIPPED dans un planning actif uniquement |
| `planning/students/` | GET | Élèves suivis, filtres `group`, `q`, `page` ; enseignant : inscriptions en cours dans ses groupes non archivés ; administrateur : tous les étudiants |
| `planning/students/{id}/` | GET | Avancement, objectifs, échéances à venir et planning actif d’un élève suivi, sans email |

La génération ne renvoie jamais 429 : quota IA atteint ou service indisponible, le planning est calculé par règles et `fallback_reason` explique pourquoi. Un planning archivé est en lecture seule (`fields.status`).

## Espaces React

- Public : `/`, `/connexion`, `/inscription`, `/mot-de-passe-oublie`, `/reinitialiser-mot-de-passe?token=…`, `/modules/{slug}`, 404.
- Étudiant : `/espace/etudiant`, `/espace/profil`, `/espace/groupes`, `/espace/groupes/{id}`, `/espace/seances`, `/espace/seances/{id}`, `/espace/assiduite`, `/espace/planning`, `/espace/planning/objectifs`, `/espace/planning/disponibilites`, `/espace/planning/plannings`, `/espace/planning/plannings/{id}`.
- Enseignant : `/espace/enseignant`, mêmes pages de profil/groupes/séances/statistiques, plus `/espace/seances/{id}/appel`, `/espace/suivi-revisions` et `/espace/suivi-revisions/{id}`.
- Administrateur : `/administration`, `/administration/utilisateurs`, `/administration/groupes`, `/administration/groupes/{id}`, `/administration/seances`, `/administration/seances/{id}`, `/administration/seances/{id}/appel`, `/administration/assiduite`, `/administration/profil`, `/administration/suivi-revisions`, `/administration/suivi-revisions/{id}`.
- Modules en préparation : `{base}/modules/{cours|resumes|assistant}`. `{base}/modules/quiz` et `{base}/modules/coaching` dirigent vers l’espace du rôle, ou vers la connexion sans session.

Le backend contrôle toujours les droits : masquer un bouton dans React n’est jamais la seule protection.
