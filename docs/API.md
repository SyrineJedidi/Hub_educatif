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

## Espaces React

- Public : `/`, `/connexion`, `/inscription`, `/mot-de-passe-oublie`, `/reinitialiser-mot-de-passe?token=…`, `/modules/{slug}`, 404.
- Étudiant : `/espace/etudiant`, `/espace/profil`, `/espace/groupes`, `/espace/groupes/{id}`, `/espace/seances`, `/espace/seances/{id}`, `/espace/assiduite`.
- Enseignant : `/espace/enseignant`, mêmes pages de profil/groupes/séances/statistiques, plus `/espace/seances/{id}/appel`.
- Administrateur : `/administration`, `/administration/utilisateurs`, `/administration/groupes`, `/administration/groupes/{id}`, `/administration/seances`, `/administration/seances/{id}`, `/administration/seances/{id}/appel`, `/administration/assiduite`, `/administration/profil`.
- Modules futurs : `{base}/modules/{cours|resumes|assistant|quiz|coaching}`. Ils sont explicitement en préparation.

Le backend contrôle toujours les droits : masquer un bouton dans React n’est jamais la seule protection.

## Cours et ressources

Règles métier, limites et fonctionnement de la transcription : [COURS.md](COURS.md). Routes de gestion réservées à l’enseignant (ses cours) et à l’administrateur (tous) ; routes `student/` réservées aux étudiants, sur les cours publiés de leurs groupes actuels. Un cours, un chapitre, une ressource ou un extrait hors périmètre renvoie 404.

| Route `/api/…` | Méthodes | Accès / fonction |
| --- | --- | --- |
| `subjects/` | GET, POST | Enseignant, ADMIN ; `q`, `archived`, `page` ; création `name`, `code`, `description` |
| `subjects/{id}/` | GET, PATCH, DELETE | Écriture par l’auteur ou ADMIN (403 sinon) ; PATCH accepte aussi `archived` ; suppression si aucun cours ne l’utilise |
| `courses/` | GET, POST | `q`, `status`, `subject`, `group`, `teacher` (ADMIN), `page` ; création `title`, `description`, `subject_id`, `group_ids` (0 à 20), plus `teacher_id` obligatoire pour ADMIN |
| `courses/{id}/` | GET, PATCH, DELETE | Détail avec `chapters` et `publication_blockers` ; PATCH partiel ; suppression d’un brouillon jamais publié |
| `courses/{id}/publish/`, `unpublish/`, `archive/`, `restore/` | POST `{}` | Changement de statut ; refus de publication dans `fields.publication` |
| `courses/{id}/chapters/` | GET, POST | `title`, `description` ; ajout en fin de cours |
| `courses/{id}/chapters/reorder/` | POST | `chapter_ids` : tous les chapitres du cours, sans doublon |
| `courses/{id}/chapters/{chapter_id}/` | PATCH, DELETE | Suppression d’un chapitre vide uniquement |
| `courses/{id}/chapters/{chapter_id}/resources/reorder/` | POST | `resource_ids` : toutes les ressources du chapitre |
| `courses/{id}/resources/` | GET, POST multipart | `chapter` en filtre ; import `chapter_id`, `title`, `description`, `file` |
| `courses/{id}/resources/{resource_id}/` | GET, PATCH, DELETE | PATCH `title`, `description`, `chapter_id` (déplacement en fin de chapitre) |
| `courses/{id}/resources/{resource_id}/reprocess/` | POST `{}` | Relance l’extraction ou la transcription ; 409 si une tâche est active |
| `courses/{id}/resources/{resource_id}/segments/` | GET | Extraits : `count`, `results` (5 000 au plus) |
| `courses/{id}/resources/{resource_id}/segments/{segment_id}/` | PATCH | Correction `text` ; 409 pendant un traitement |
| `courses/{id}/statistics/` | GET | Synthèse, ressources et élèves ; `?format=csv` pour l’export |
| `courses/processing/` | GET | Enseignant, ADMIN : `provider`, `configured`, `model`, `process_inline`, `pending`, `running`, `failed` |
| `courses/search/` | GET | Tous les rôles, cours visibles uniquement ; `q`, `subject`, `course`, `kind` (`PDF`, `AUDIO`), `page` |
| `courses/resources/{resource_id}/file/` | GET | Compte actif qui voit le cours ; `?download=1`, en-tête `Range` |
| `student/courses/` | GET | Étudiant ; `q`, `subject`, `page` ; progression de chaque cours |
| `student/courses/{id}/` | GET | Cours, progression et chapitres avec ressources et indicateur `viewed` |
| `student/courses/{id}/resources/{resource_id}/` | GET | Ressource, chapitre et cours |
| `student/courses/{id}/resources/{resource_id}/segments/` | GET | Extraits, comme pour la gestion |
| `student/courses/{id}/resources/{resource_id}/views/` | POST `{}` | Enregistre une consultation ; renvoie `viewed`, `view_count`, `progress` |

Listes de cours, de matières et résultats de recherche : `count`, `page`, `page_size=20`, `results`. Un résultat de recherche porte `type` (`course`, `chapter`, `resource`, `segment`), `score`, `course`, `chapter`, `resource`, `snippet`, `highlights` (positions `[début, fin]` dans `snippet`), `page`, `start_seconds` et `link`. Une ressource de gestion expose `processing_status`, `processing_error`, `text_version`, `segments_count`, `file_url`, `download_url` et sa dernière tâche (`job`) ; la version étudiante n’expose ni l’erreur ni la tâche. Un extrait porte `order`, `text`, `page`, `start_seconds`, `end_seconds`, `edited` et `edited_at`.

Codes propres au module : 409 `processing_in_progress` (traitement actif), 416 `range_not_satisfiable` (plage hors du fichier), 429 au-delà de 30 imports par heure, 60 recherches par minute ou 600 consultations par heure et par utilisateur. Un corps d’import plus gros que la plus grande limite de taille plus 1 Mo est refusé en 400 avant sa lecture.
