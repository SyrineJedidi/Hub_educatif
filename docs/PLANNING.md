# Planification des révisions et coaching

Module 5 du hub : « Gérer les objectifs, échéances, disponibilités, plannings et tâches de révision » et « Proposer un programme personnalisé avec Gemini, selon les cours, les résultats et le temps disponible ».

L’étudiant décrit ce qu’il veut réussir et quand il peut réviser ; le serveur en tire un planning de tâches, calculé par règles ou proposé par Gemini, que l’étudiant vérifie, active puis suit au quotidien. L’enseignant et l’administrateur consultent l’avancement en lecture seule.

Code : `backend/planning/` (application Django), `backend/ai/gemini.py` (client Gemini), `frontend/src/planning/` (pages React). Aucune nouvelle dépendance Python ni npm : le client Gemini utilise `urllib` de la bibliothèque standard.

## Installation

Depuis la racine, avec l’environnement et MongoDB déjà configurés :

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
.\backend\.venv\Scripts\python.exe backend\manage.py check
```

La migration `planning/0001_initial.py` crée cinq collections (`StudyGoal`, `Deadline`, `Availability`, `StudyPlan`, `RevisionTask`), leurs index et l’index unique partiel `unique_active_study_plan`. Elle ne modifie aucune donnée des autres modules. Sans configuration supplémentaire, l’IA est désactivée et les plannings sont calculés par règles.

## Fonctionnalités par rôle

**Étudiant** (`/espace/planning`) :
- tableau de bord : planning actif, tâches du jour avec les boutons « Terminée », « Ignorée » et « À faire », tâches des sept prochains jours, taux de réalisation, temps réalisé et prévu, tâches en retard, série de jours, trois prochaines échéances et avancement par objectif ;
- objectifs (titre, description, groupe, date cible, priorité, heures estimées, statut) et échéances (examen, quiz, devoir ou autre, date et heure, objectif lié, notes) ;
- disponibilités : créneaux hebdomadaires par jour, avec le total de la semaine ;
- plannings : génération sur une période, avec l’IA ou par règles, et aperçu de ce qui sera pris en compte (objectifs, échéances, disponibilités, résultats de quiz, groupes à renforcer, cours, quota IA restant) ; historique filtrable par statut ;
- détail d’un planning : conseils, origine et métriques de génération, tâches regroupées par jour, ajout, modification et suppression de tâches, activation, archivage, renommage, suppression et export `.ics`.

**Enseignant** (`/espace/suivi-revisions`) : les élèves inscrits actuellement dans l’un de ses groupes non archivés, avec leur planning actif, leur avancement, leur dernière activité et leur prochaine échéance ; puis le détail d’un élève. Lecture seule.

**Administrateur** (`/administration/suivi-revisions`) : les mêmes pages pour tous les comptes étudiants. Lecture seule également.

Les écrans s’appuient sur les composants partagés (`Modal`, `Form`, `Field`, `Pagination`…) et les styles du module sont limités à `.planning-module` (préfixe `planning-`). Les dates sont affichées en fr-FR, fuseau Africa/Tunis.

## Règles métier

**Propriété.** Un étudiant ne voit et ne modifie que ses propres objectifs, échéances, créneaux, plannings et tâches ; l’objet d’un autre compte renvoie 404. Les enseignants et l’administrateur n’écrivent jamais dans ces données.

**Objectif.** Titre obligatoire (120 caractères), description facultative (1 000), groupe facultatif, choisi parmi les groupes où l’étudiant a une inscription en cours à la création ou au changement de groupe (un groupe déjà enregistré reste valable même après la fin de l’inscription), date cible facultative, priorité Faible, Moyenne ou Haute (Moyenne par défaut), heures estimées de 1 à 200 (5 par défaut), statut En cours, Atteint ou Abandonné. La suppression est refusée quand des tâches utilisent l’objectif : il faut alors le marquer « Abandonné ». Les échéances liées à un objectif supprimé sont conservées, sans lien.

**Échéance.** Titre obligatoire, type obligatoire, date et heure dans le futur à la création et à chaque déplacement, objectif facultatif (de l’étudiant), notes facultatives (500). Une échéance peut être supprimée : les tâches qui la préparaient sont conservées et perdent seulement ce lien.

**Créneau hebdomadaire.** Jour de lundi (0) à dimanche (6), début et fin au quart d’heure, durée de 30 minutes à 6 heures, sans chevauchement avec un autre créneau du même jour (des créneaux qui se touchent sont admis), 21 créneaux au maximum. Supprimer un créneau ne modifie pas les plannings existants.

**Planning.** Titre facultatif à la génération (par défaut « Planning du JJ/MM au JJ/MM »), période de 1 à 28 jours qui commence au plus tôt aujourd’hui (heure de Tunis). Cycle de vie :
- la génération crée un **brouillon** : tout y est modifiable, mais le suivi des tâches n’y est pas possible ;
- l’**activation** archive, dans la même transaction, le planning actif précédent : un étudiant a au plus un planning actif, garanti aussi par un index unique partiel MongoDB ;
- l’**archivage** est possible depuis un brouillon ou un planning actif ; un planning archivé est en lecture seule ;
- la **suppression** est réservée aux brouillons et aux plannings archivés ; un planning actif doit d’abord être archivé.

**Tâche.** Titre obligatoire, description facultative (1 000), objectif et échéance facultatifs, début et fin le même jour local, de 15 minutes à 4 heures, à l’intérieur des dates du planning, sans chevaucher une autre tâche du même planning. Les tâches s’ajoutent, se modifient et se suppriment dans un brouillon ou un planning actif. Le statut (À faire, Terminée, Ignorée) ne change que dans un planning actif ; `completed_at` est renseigné au passage à « Terminée » et effacé sinon.

**Avancement.** Pour le planning actif : tâches terminées, ignorées, à faire et en retard (à faire et déjà finies), minutes prévues et réalisées, taux de réalisation = terminées / (terminées + ignorées + en retard), en pourcentage arrondi, ou « Non calculable » quand ce total est nul. La série compte les jours consécutifs, jusqu’à aujourd’hui ou jusqu’à hier si rien n’est encore terminé aujourd’hui, qui ont au moins une tâche terminée, d’après le jour de début de la tâche (tous plannings confondus). Les minutes par objectif sont comptées dans le planning actif.

**Écritures.** Les écritures de l’étudiant sur ses propres données n’utilisent pas la garde transactionnelle globale ; une transaction MongoDB courte est utilisée seulement quand plusieurs documents changent ensemble (activation, création d’un planning et de ses tâches, suppressions). Un conflit d’écriture renvoie 409.

## Algorithme par règles

`backend/planning/scheduler.py` est déterministe : mêmes données, même planning. Il sert au mode « Par règles » et au repli de l’IA.

1. **Fenêtres.** Chaque créneau hebdomadaire devient une fenêtre concrète pour chaque date de la période, en heure de Tunis. Une fenêtre déjà commencée est raccourcie au quart d’heure suivant l’heure actuelle.
2. **Besoins.** Chaque objectif en cours demande `heures estimées × 60` minutes, moins les minutes des tâches terminées qui lui sont liées dans le planning actif. Une échéance sans objectif demande 120 minutes, sous le titre « Préparer : <titre> ». Une échéance liée à un objectif est préparée par cet objectif.
3. **Date limite.** Pour un objectif, la première de ces deux dates : sa plus proche échéance liée à venir, la fin de sa date cible. Pour une échéance seule, sa date. Aucune séance n’est placée après cette limite.
4. **Poids.** Priorité (Haute 3, Moyenne 2, Faible 1 ; une échéance seule compte comme Moyenne), + 1 si le dernier quiz terminé de l’étudiant dans le groupe de l’objectif est sous 60 %, + 2 si la date limite tombe dans la période, + 3 à la place si elle tombe dans les trois jours qui suivent le début du planning.
5. **Remplissage.** Les fenêtres sont parcourues dans l’ordre chronologique, par blocs de 60 minutes ; le dernier bloc d’une fenêtre peut durer de 30 à 59 minutes et un reste de moins de 30 minutes est laissé libre. Chaque bloc revient au besoin encore ouvert de plus fort poids dont la date limite suit la fin du bloc ; à égalité, la date limite la plus proche, puis le titre. Quand le besoin restant est plus petit que le bloc, le bloc est ramené à ce besoin, arrondi au quart d’heure supérieur et de 30 minutes au moins. Les tâches s’appellent « Réviser : <objectif> » et leur description rappelle l’échéance, la date cible et le quiz faible.
6. **Conseils.** Nombre de séances et durée totale, temps planifié par objectif, priorités renforcées par un quiz faible, et un avertissement « Temps disponible insuffisant pour « X » avant le JJ/MM : il manque N h. » pour chaque besoin non couvert dont la date limite tombe dans la période.

Refus : sans objectif en cours ni échéance à venir, « Ajoutez au moins un objectif en cours ou une échéance avant de générer un planning. » ; sans fenêtre dans la période, « Aucune disponibilité sur cette période : ajoutez des créneaux. ». Si toutes les échéances précèdent les créneaux, le planning est créé sans tâche et ses conseils l’expliquent.

## Génération avec Gemini, repli et quotas

En mode « Avec l’IA (Gemini) », `backend/planning/generation.py` procède ainsi :

1. **Quotas**, vérifiés uniquement en mode IA et hors transaction : `PLANNING_AI_DAILY_LIMIT` demandes par étudiant (10 par défaut), puis `PLANNING_AI_DAILY_BUDGET` demandes pour tout le serveur (400 par défaut), sur une fenêtre de 24 heures alignée sur minuit UTC. Une demande refusée avant ce stade (saisie invalide, aucun objectif ni échéance, aucune disponibilité) ne compte pas ; toute autre génération en mode IA compte, même quand elle se termine par un repli. Au-delà, l’étudiant ne reçoit pas d’erreur 429 : le planning est calculé par règles.
2. **Contexte** envoyé en JSON, sans nom, email ni identifiant de compte : la date du jour, la période, les fenêtres (date, début, fin), les objectifs en cours (identifiant, titre, description tronquée à 300 caractères, priorité, heures estimées, minutes restantes, date cible, nom du groupe), les échéances à venir (identifiant, titre, type, date, objectif lié), les 20 derniers quiz terminés (titre, groupe, pourcentage, date) et, si le module de cours est installé, les cours visibles par l’étudiant avec leurs titres de chapitres. L’absence ou l’échec du module de cours ne bloque jamais la génération.
3. **Consigne système** (en français) : coach de révision bienveillant, uniquement les créneaux fournis, priorité aux échéances proches, aux priorités hautes et aux résultats faibles, tâches de 30 à 120 minutes avec des pauses, réponse JSON conforme au schéma, conseils concrets de 1 200 caractères au maximum.
4. **Schéma de réponse** : `{advice, tasks: [{goal_id?, deadline_id?, title, description, date: "AAAA-MM-JJ", start: "HH:MM", end: "HH:MM"}]}`, 120 tâches au maximum.
5. **Validation** de chaque proposition : elle doit tenir entièrement dans une fenêtre, durer de 15 à 240 minutes et ne chevaucher aucune proposition déjà retenue (la première gagne). Un identifiant d’objectif ou d’échéance qui n’appartient pas à l’étudiant est remplacé par aucun lien ; un titre vide devient « Révision ».
6. **Repli** sur l’algorithme par règles, avec un motif affiché sur la page du planning :

| Situation | Générateur | Motif |
|---|---|---|
| Quota étudiant ou global atteint, ou quota Gemini épuisé sur les deux modèles | Règles | « Quota IA atteint : planning calculé par règles. » |
| `GEMINI_PROVIDER=disabled` ou clé absente | Règles | « L’IA n’est pas configurée sur ce serveur : planning calculé par règles. » |
| Service indisponible, délai dépassé, clé refusée, requête refusée | Règles | « Service IA indisponible : planning calculé par règles. » |
| Contenu bloqué par Gemini | Règles | « Le service IA a bloqué la demande : planning calculé par règles. » |
| Réponse illisible ou hors schéma | Règles | « La réponse de l’IA était inexploitable : planning calculé par règles. » |
| Aucune proposition valide | Règles | « La proposition de l’IA ne respectait pas vos disponibilités : planning calculé par règles. » |
| Certaines propositions écartées | IA | « 1 proposition hors créneaux a été ignorée. » ou « N propositions hors créneaux ont été ignorées. » |

Le planning conserve les métriques : fournisseur, modèle, latence, jetons envoyés et générés. La page du planning affiche par exemple « Généré par gemini-3.5-flash-lite en 2,4 s · 1 840 jetons envoyés · 620 jetons générés ». Quand Gemini échoue, le planning garde le fournisseur configuré et aucun nom de modèle.

Gemini n’est jamais appelé dans une transaction : le calcul se fait d’abord, puis le planning et ses tâches sont enregistrés ensemble dans une transaction courte.

### Client Gemini

`backend/ai/gemini.py` envoie un `POST` à `https://generativelanguage.googleapis.com/v1beta/models/{modèle}:generateContent` avec l’en-tête `x-goog-api-key`, la consigne système, le contexte, `responseMimeType: application/json`, le schéma de réponse et `maxOutputTokens` (8 192). Aucun paramètre d’échantillonnage (`temperature`, `topP`, `topK`) n’est envoyé : ils sont dépréciés sur les modèles récents.

- HTTP 429 : erreur `quota`, après un seul nouvel essai avec `GEMINI_FALLBACK_MODEL`, chaque modèle ayant son propre quota gratuit. Si ce second appel échoue autrement, c’est son erreur qui est retenue.
- 401 et 403 : `auth` ; autre 4xx : `refused` ; 5xx, délai dépassé ou réseau : `unavailable` ; `promptFeedback.blockReason` ou fin pour raison de sécurité : `blocked` ; texte absent ou JSON invalide : `invalid_response`.
- Les messages d’erreur sont en français et sans détail du fournisseur. Les journaux ne contiennent que le modèle, le code d’erreur et le statut HTTP, jamais la clé, le contexte ni la réponse.
- Le fournisseur réel est refusé quand le nom de la base commence par `test_` : une exécution de tests n’atteint jamais le réseau et ne consomme pas le quota.
- Le fournisseur `fake` ne fait aucun appel réseau : il renvoie le planning par règles au format de la réponse IA, avec le fournisseur et le modèle « fake ». Il sert aux démonstrations et aux tests.

## Configuration `.env`

Variables lues par `backend/config/settings.py`, documentées avec leurs valeurs par défaut dans `backend/.env.example` :

| Variable | Défaut | Rôle |
|---|---|---|
| `GEMINI_PROVIDER` | `disabled` | `disabled`, `fake` (démonstration sans réseau) ou `gemini` |
| `GEMINI_API_KEY` | vide | Clé de l’API Gemini (Google AI Studio) ; obligatoire avec `gemini` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Modèle principal |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.1-flash-lite` | Modèle essayé une fois après un HTTP 429 |
| `GEMINI_TIMEOUT_SECONDS` | `60` | Délai maximal d’un appel |
| `PLANNING_AI_DAILY_LIMIT` | `10` | Générations IA par étudiant et par jour |
| `PLANNING_AI_DAILY_BUDGET` | `400` | Générations IA pour tout le serveur et par jour |

Pour activer Gemini, ajouter dans `backend/.env` (jamais versionné) :

```dotenv
GEMINI_PROVIDER=gemini
GEMINI_API_KEY=votre-clé
```

puis redémarrer Django. L’aperçu de la page « Mes plannings » indique si l’IA est configurée, le modèle et le nombre de générations restantes aujourd’hui. Sans clé, le mode IA reste proposé mais se replie sur les règles avec un motif explicite.

## Export iCalendar

`GET /api/student/planning/plans/{id}/ics/`, lien « Exporter vers mon agenda (.ics) ↗ » de la page du planning. Fichier `planning-{id}.ics`, type `text/calendar; charset=utf-8`, conforme à la RFC 5545 : `PRODID:-//Nexora//Hub Educatif//FR`, un `VEVENT` par tâche (`UID:{id}@nexora`, `DTSTAMP`, `DTSTART` et `DTEND` en UTC, `SUMMARY`, `DESCRIPTION` avec l’objectif et l’échéance, `STATUS:CANCELLED` pour une tâche ignorée, `CONFIRMED` sinon), échappement des `\`, `;`, `,` et retours à la ligne, lignes repliées à 75 octets sans couper un caractère UTF-8, fins de ligne CRLF. L’export fonctionne aussi pour un client qui n’accepte que `text/calendar`. C’est un téléchargement ponctuel, pas un abonnement synchronisé.

## Suivi enseignant

- Un enseignant suit les étudiants qui ont une inscription en cours (début passé, fin absente ou future) dans l’un de ses groupes non archivés, la règle déjà appliquée aux quiz. Un ancien élève, l’élève d’un autre enseignant ou un groupe archivé renvoient 404.
- L’administrateur suit tous les comptes étudiants.
- Liste : élève, groupes (ceux de l’enseignant seulement), planning actif et période, taux de réalisation, tâches terminées et en retard, dernière tâche terminée, prochaine échéance. Filtres : groupe (pris dans l’API existante `groups/`, groupes non archivés) et recherche sur le prénom ou le nom.
- Détail : groupes, indicateurs, série de jours, objectifs (titre, priorité, statut, minutes prévues et réalisées, sans description), échéances à venir, planning actif avec ses conseils et ses tâches par jour.
- Aucune adresse email n’est renvoyée, pas même à l’administrateur. Les vues n’acceptent que GET : aucune modification possible.

## API

Toutes les routes sont sous `/api/`, avec la session, le CSRF et le format d’erreur communs (voir [API.md](API.md)). Identifiants MongoDB de 24 caractères hexadécimaux ; un identifiant invalide ou hors périmètre renvoie 404.

Routes étudiant (rôle STUDENT uniquement, sinon 403 « Le planning de révision est réservé aux étudiants. »), préfixe `student/planning/` :

| Route | Méthodes | Usage |
|---|---|---|
| `goals/` | GET, POST | GET `?status=` → `{results}` ; POST `title`, `description?`, `learning_group_id?`, `target_date?`, `priority?`, `estimated_hours?` |
| `goals/{id}/` | GET, PATCH, DELETE | PATCH partiel, accepte aussi `status` |
| `deadlines/` | GET, POST | GET `?upcoming=true\|false` → `{results}` par date ; POST `title`, `kind`, `due_at`, `goal_id?`, `notes?` |
| `deadlines/{id}/` | GET, PATCH, DELETE | PATCH partiel |
| `availability/` | GET, POST | GET → `{results, weekly_minutes}` ; POST `weekday`, `start_time`, `end_time` |
| `availability/{id}/` | PATCH, DELETE | PATCH partiel |
| `groups/` | GET | Groupes actuels de l’étudiant `{results: [{id, name, code}]}` |
| `context/` | GET | Ce que la génération prendra en compte, avec l’état de l’IA |
| `dashboard/` | GET | Tableau de bord |
| `plans/` | GET | `?status=&page=`, liste paginée |
| `plans/generate/` | POST | `start_date`, `end_date`, `mode` (`ai` ou `rules`), `title?` → 201, brouillon détaillé |
| `plans/{id}/` | GET, PATCH, DELETE | Détail avec `advice` et `tasks` ; PATCH `title` |
| `plans/{id}/activate/`, `plans/{id}/archive/` | POST | Corps `{}` → détail |
| `plans/{id}/ics/` | GET | Fichier iCalendar |
| `plans/{id}/tasks/` | POST | `title`, `description?`, `goal_id?`, `deadline_id?`, `starts_at`, `ends_at` → 201 |
| `tasks/{id}/` | PATCH, DELETE | PATCH partiel, accepte aussi `status` |

Routes de suivi (rôles TEACHER et ADMIN, sinon 403 « Le suivi des révisions est réservé aux enseignants et à l’administrateur. ») :

| Route | Méthodes | Usage |
|---|---|---|
| `planning/students/` | GET | `?group=&q=&page=`, liste paginée ; un groupe hors périmètre renvoie 404 |
| `planning/students/{id}/` | GET | Détail d’un élève suivi |

Formats de réponse :
- **objectif** `{id, title, description, learning_group: {id, name, code}|null, target_date, priority, priority_label, estimated_hours, status, status_label, planned_minutes, done_minutes, created_at, updated_at}` ;
- **échéance** `{id, title, kind, kind_label, due_at, goal: {id, title}|null, notes, created_at, updated_at}` ;
- **créneau** `{id, weekday, weekday_label, start_time: "HH:MM", end_time: "HH:MM", minutes}` ;
- **tâche** `{id, plan_id, title, description, goal, deadline, starts_at, ends_at, minutes, status, status_label, source: AI|RULES|MANUAL, completed_at}` ;
- **planning** `{id, title, start_date, end_date, status, status_label, generator, generator_label, fallback_reason, provider, model_name, latency_ms, prompt_tokens, output_tokens, tasks_count, done_count, planned_minutes, activated_at, created_at, updated_at}` ; le détail ajoute `advice` et `tasks`, triées par début ;
- **avancement** `{done, skipped, todo, overdue, planned_minutes, done_minutes, completion_rate}`, taux entier ou `null` ;
- **contexte** `{goals, deadlines, weekly_minutes, quiz_results: [{quiz_title, group_name, percent, submitted_at}], weak_groups, courses_available, courses: [{title, chapters}], ai: {provider, configured, model, remaining_today}}` ;
- **tableau de bord** `{active_plan, today, upcoming, progress, streak_days, next_deadlines (3 au plus), goals: [{id, title, planned_minutes, done_minutes}]}` ;
- **ligne de suivi** `{student: {id, first_name, last_name}, groups: [{id, name}], active_plan: {id, title, start_date, end_date}|null, progress, last_done_at, next_deadline: {title, due_at}|null}` ;
- **détail de suivi** `{student, groups, progress, streak_days, goals: [{id, title, priority, priority_label, status, status_label, planned_minutes, done_minutes}], deadlines: [{id, title, kind_label, due_at}], active_plan: planning détaillé|null}`.

Les listes `plans/` et `planning/students/` suivent la pagination commune (`count`, `page`, `page_size=20`, `results`) ; les autres listes renvoient `{results}`. Dates `AAAA-MM-JJ`, heures `HH:MM`, dates-heures ISO 8601 avec fuseau.

Les champs inconnus sont refusés (« Ce champ ne peut pas être modifié. »), comme un corps qui n’est pas un objet JSON. Les erreurs métier figurent dans `error.message` (objectif utilisé, aucune disponibilité, planning actif à archiver d’abord, limite de 21 créneaux…) ou dans `error.fields` (`status` pour un planning archivé, déjà actif ou un suivi demandé sur un brouillon ; `start_date`, `due_at`, `starts_at`…). La génération ne renvoie jamais 429.

## Pages React

| Page | Route |
|---|---|
| Tableau de bord étudiant | `/espace/planning` |
| Objectifs et échéances | `/espace/planning/objectifs` |
| Disponibilités | `/espace/planning/disponibilites` |
| Plannings et génération | `/espace/planning/plannings` |
| Détail d’un planning | `/espace/planning/plannings/{id}` |
| Suivi enseignant | `/espace/suivi-revisions`, `/espace/suivi-revisions/{id}` |
| Suivi administrateur | `/administration/suivi-revisions`, `/administration/suivi-revisions/{id}` |

`/modules/coaching`, ainsi que `/espace/modules/coaching` et `/administration/modules/coaching`, redirige vers la page du rôle, ou vers la connexion sans session. Un enseignant qui ouvre une page étudiant est redirigé vers le suivi ; un étudiant qui ouvre le suivi est redirigé vers son planning. Menus : « Mon planning » ou « Suivi des révisions » dans « Mes activités », l’entrée « Planification et coaching » des modules, le lien du pied de page, et « Suivi des révisions » dans la barre latérale de l’administration. L’accueil indique le module comme « Disponible ».

Accessibilité : un titre `h1` visible par page, champs étiquetés, première erreur focalisée, retour du focus à la fermeture des dialogues, annonces polies pendant la génération et après chaque changement de statut, boutons de statut avec `aria-pressed` et le titre de la tâche en texte masqué, mise à jour immédiate puis annulation si le serveur refuse, aucun défilement horizontal à 390 px.

## Limites

- Le fuseau est fixé à Africa/Tunis (UTC+1, sans heure d’été) pour les créneaux, les tâches et l’affichage.
- Les créneaux sont hebdomadaires : pas d’exception pour un jour férié ou une semaine particulière ; il faut modifier les créneaux ou les tâches du brouillon.
- Une proposition de Gemini est enregistrée telle qu’elle a été validée ; l’étudiant l’ajuste ensuite dans le brouillon.
- Les quotas IA sont des compteurs journaux en base, sans facturation ni suivi de consommation chez Google.
- Le module de cours n’est pas installé dans ce dépôt : `courses_available` vaut `false` et le contexte IA ne contient pas de cours. L’intégration s’active d’elle-même quand l’application `courses` fournit `visible_courses` et `course_outline`.
- L’export iCalendar est un fichier à importer, pas un flux synchronisé.
- Pas de rappel ni de notification.
- La liste de suivi de l’administrateur inclut les comptes étudiants désactivés.
- Un compte dont le rôle passe d’étudiant à enseignant conserve ses données de planification, mais n’y a plus accès.

## Tests

`backend/planning/tests/`, 66 tests (`TransactionTestCase`, hachage MD5, `override_settings(GEMINI_PROVIDER='fake')`, appels HTTP simulés, aucun accès réseau) :

| Fichier | Tests | Contenu |
|---|---|---|
| `test_objectives.py` | 12 | Objectifs, échéances et créneaux : validations, groupe actuel, limite de 21 créneaux, propriété (404), rôles, compte anonyme ou désactivé, CSRF |
| `test_scheduler.py` | 13 | Fenêtres locales et coupées, priorités et déterminisme, blocs, minutes déjà réalisées, quiz faible, dates limites et temps manquant, échéances seules, égalités, refus, création du brouillon |
| `test_generation.py` | 8 | Mode IA avec le fournisseur simulé, métriques, propositions écartées, repli sur erreur et sur quota, appel hors transaction et sans donnée personnelle, contexte, module de cours facultatif |
| `test_gemini.py` | 9 | Client Gemini : requête envoyée, réponse et jetons, 429 puis modèle de repli, erreurs HTTP et réseau, blocage, JSON invalide, journaux sans clé, garde de la base de test, fournisseur simulé |
| `test_plans.py` | 15 | Listes et filtres, cycle de vie, planning actif unique (index et activations concurrentes), conflits, lecture seule, suppressions, tâches et statuts, CSRF, export iCalendar avec échappement et repli des lignes |
| `test_dashboard.py` | 3 | Indicateurs du tableau de bord, série de jours, tableau vide et rôles |
| `test_coach.py` | 6 | Périmètre enseignant, filtres et pagination, administrateur, détail, 404 hors périmètre, rôles et lecture seule |

```powershell
# À la racine ; MongoDB doit être démarré
.\backend\.venv\Scripts\python.exe backend\manage.py test accounts quizzes planning --noinput
.\backend\.venv\Scripts\python.exe -m coverage run --source=planning,ai backend\manage.py test planning --noinput
.\backend\.venv\Scripts\python.exe -m coverage report --omit="*/migrations/*,*/tests/*,*/management/*"
```

### Vérifications de cette livraison (26/10/2026)

Python 3.13, MongoDB 7.0 en replica set mono-nœud, Node 22.

| Contrôle | Résultat |
|---|---|
| `manage.py check` | Aucun problème |
| `manage.py makemigrations --check --dry-run` | Aucun changement |
| `manage.py test accounts quizzes planning --noinput` | 177 tests OK (111 existants, 66 du module) |
| Couverture `planning` et `ai` | 100 % (1 074 instructions). La ligne qui transforme un conflit d’écriture en 409 n’est atteinte que si les deux requêtes du test de concurrence se croisent : la couverture peut descendre à 99 % sur une autre exécution |
| `npm run build` | OK, aucune erreur TypeScript |
| Parcours API réel (serveur Django, fournisseur `fake`) | 154 contrôles sans écart : chaque réponse JSON comparée champ par champ aux types de `frontend/src/planning/types.ts`, en étudiant, enseignant, autre enseignant et administrateur, y compris les deux modes de génération, le quota IA, l’activation, les statuts, l’export iCalendar et les erreurs |
| Serveur Vite et proxy `/api` | 21 contrôles sans écart : routes React du module, `/api/csrf/`, connexion, changement de statut avec CSRF et export à travers le proxy |
