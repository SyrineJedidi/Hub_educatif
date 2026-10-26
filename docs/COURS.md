# Cours et ressources

Le module permet aux enseignants d’organiser leurs cours par matière et par chapitre, d’y importer des documents PDF et des enregistrements audio, puis de les partager avec leurs groupes. Le texte des PDF est extrait et les enregistrements sont transcrits avec Whisper : ce texte sert à la consultation, à la recherche et au futur assistant pédagogique. Le code se trouve dans `backend/courses/`, `backend/ai/transcription.py` et `frontend/src/courses/`.

## Installation et migration

Depuis la racine du projet, avec l’environnement et MongoDB déjà configurés :

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\backend\.venv\Scripts\python.exe backend\manage.py migrate
```

`requirements.lock` ajoute `pypdf==6.21.2`, la seule nouvelle dépendance obligatoire. La migration `courses/0001_initial.py` crée les collections du module et leurs index sans toucher aux données existantes. Les fichiers importés sont écrits sous `backend/media/courses/`, ignoré par Git. La transcription locale demande une installation facultative, décrite plus bas.

## Fonctionnalités par rôle

| Rôle | Fonctionnalités |
| --- | --- |
| Enseignant | Crée des matières et modifie, archive ou supprime celles qu’il a créées. Crée ses cours, les partage avec ses groupes actifs, gère chapitres et ressources, publie, retire de la publication, archive et restaure. Corrige le texte extrait et les transcriptions. Consulte les statistiques de consultation et les exporte en CSV. Recherche dans ses cours, quel que soit leur statut. |
| Administrateur | Mêmes actions sur tous les cours et toutes les matières. À la création d’un cours, il choisit l’enseignant propriétaire (`teacher_id`, obligatoire). Il peut confier un cours à un autre enseignant ; les groupes du cours, envoyés ou déjà liés, doivent alors appartenir au nouvel enseignant. |
| Étudiant | Consulte les cours publiés de ses groupes : PDF affiché dans la page ou téléchargé, audio avec transcription horodatée, texte extrait page par page. Voit sa progression et le badge « Consulté ». Recherche dans ses cours. |

Pages, sous `/espace` pour les enseignants et les étudiants et sous `/administration` pour l’administrateur :

| Page | Chemin | Accès |
| --- | --- | --- |
| Liste des cours | `cours` | Tous (« Mes cours » pour l’étudiant, « Gestion des cours » sinon) |
| Recherche | `cours/recherche` | Tous |
| Cours | `cours/{id}` | Tous (consultation pour l’étudiant, gestion pour les autres) |
| Ressource | `cours/{id}/ressources/{rid}` (`?page=N`, `?t=secondes`) | Tous |
| Création, modification | `cours/nouveau`, `cours/{id}/modifier` | Enseignant, administrateur |
| Statistiques | `cours/{id}/statistiques` | Enseignant, administrateur |
| Matières | `matieres` | Enseignant, administrateur |

L’alias `/modules/cours` dirige vers `/administration/cours`, `/espace/cours` ou la connexion. Un étudiant qui ouvre une page de gestion est renvoyé vers `/espace/cours`. Le backend contrôle toujours les droits, indépendamment de l’interface.

## Règles métier et statuts

**Visibilité.** Un étudiant voit uniquement les cours PUBLISHED partagés avec au moins un groupe non archivé où il a une inscription en cours (`entrée ≤ maintenant < sortie`, ou sortie absente), comme pour les quiz. Une inscription future ou terminée n’ouvre aucun accès. Un enseignant voit tous ses cours, quel que soit leur statut ; l’administrateur voit tout. Un objet hors périmètre renvoie 404 avec un message en français ; un rôle non autorisé renvoie 403.

**Matières.** Nom obligatoire (80 caractères), unique sans tenir compte des accents, de la casse ni des espaces : « Mathématiques » et « mathematiques » sont un doublon. Code unique de 2 à 20 caractères, mis en majuscules : lettres, chiffres et tirets, en commençant par une lettre ou un chiffre. Description facultative (1 000). Seuls l’auteur et l’administrateur modifient, archivent ou suppriment une matière. Une matière archivée ne peut plus être choisie pour un cours, mais les cours qui l’utilisent la gardent. Une matière utilisée par des cours ne peut pas être supprimée.

**Cours.** Titre (120) et description (2 000) obligatoires, une matière non archivée, de 0 à 20 groupes non archivés dont l’enseignant du cours est responsable. Statuts :

| Statut | Libellé | Effet |
| --- | --- | --- |
| `DRAFT` | Brouillon | Modifiable, invisible des étudiants. |
| `PUBLISHED` | Publié | Modifiable : un cours s’enrichit pendant le semestre. Doit rester partagé avec au moins un groupe. |
| `ARCHIVED` | Archivé | Lecture seule, invisible des étudiants. Toute écriture renvoie 400 « Ce cours est archivé. Restaurez-le pour le modifier. » |

Transitions par actions dédiées, corps `{}` : publier (brouillon → publié), retirer de la publication (publié → brouillon), archiver (brouillon ou publié → archivé), restaurer (archivé → brouillon). La publication renvoie toutes les raisons de refus à la fois : titre et description valides, enseignant actif, matière non archivée, au moins un groupe actif de l’enseignant, au moins un chapitre et au moins une ressource. `published_at` garde la date de la première publication. Seul un brouillon jamais publié peut être supprimé ; la suppression efface consultations, extraits, tâches, ressources, fichiers, chapitres et liens de groupes. Sinon : « Ce cours a déjà été publié : archivez-le plutôt que de le supprimer. »

**Chapitres.** Titre obligatoire (120), description facultative (1 000), positions 1 à N. Un nouveau chapitre est ajouté à la fin ; le réordonnancement exige la liste exacte des chapitres du cours. Seul un chapitre vide peut être supprimé, et les positions sont alors resserrées.

**Ressources.** Titre obligatoire (120) et description facultative (1 000). Une ressource déplacée vers un autre chapitre est ajoutée à sa fin ; le réordonnancement se fait à l’intérieur d’un chapitre. Supprimer une ressource efface aussi son fichier, ses extraits, ses tâches et l’historique de consultation de cette ressource.

| Traitement | Libellé |
| --- | --- |
| `PENDING` | En attente |
| `PROCESSING` | En cours de traitement |
| `READY` | Prêt |
| `NO_TEXT` | Sans texte exploitable |
| `FAILED` | Échec du traitement |

**Autres modules.** La suppression d’un groupe partagé avec un cours est refusée : il faut l’archiver. Le rôle d’un enseignant qui possède encore un cours non archivé ne peut pas être changé.

Les écritures de gestion passent par la garde transactionnelle commune ; un conflit persistant renvoie 409. Aucun appel à pypdf ni à Whisper n’a lieu dans une transaction.

## Import : formats et limites

Le type est déterminé par le contenu du fichier, jamais par son nom ni par le Content-Type envoyé :

| Type | Signature reconnue | Stocké en |
| --- | --- | --- |
| PDF | `%PDF-` dans les 1 024 premiers octets | `application/pdf`, `.pdf` |
| MP3 | `ID3` ou synchronisation de trame MPEG | `audio/mpeg`, `.mp3` |
| WAV | `RIFF` … `WAVE` | `audio/wav`, `.wav` |
| OGG / Opus | `OggS` | `audio/ogg`, `.ogg` |
| WEBM | `1A 45 DF A3` | `audio/webm`, `.webm` |
| M4A / MP4 | `ftyp` à l’octet 4 | `audio/mp4`, `.m4a` |
| FLAC | `fLaC` | `audio/flac`, `.flac` |

Tout autre contenu est refusé : « Format non pris en charge : importez un PDF ou un fichier audio (MP3, M4A, WAV, OGG, WEBM, FLAC). »

| Limite | Variable | Défaut |
| --- | --- | --- |
| Taille d’un PDF | `COURSES_MAX_PDF_MB` | 20 Mo |
| Taille d’un audio | `COURSES_MAX_AUDIO_MB` | 25 Mo, la limite par requête de l’offre gratuite Groq |
| Pages d’un PDF | `COURSES_MAX_PDF_PAGES` | 300 |
| Durée d’un audio | `COURSES_MAX_AUDIO_SECONDS` | 7 200 s, vérifiée par le fournisseur local uniquement |
| Imports | — | 30 tentatives par heure et par utilisateur |

Un Mo vaut ici 1 048 576 octets. Une requête plus grosse que la plus grande limite plus 1 Mo est refusée avant la lecture du formulaire. Sont aussi refusés : fichier vide, PDF illisible ou endommagé, PDF protégé par un mot de passe (un PDF chiffré qui s’ouvre sans mot de passe est accepté), PDF au-delà de la limite de pages, et fichier déjà présent dans le même cours, détecté par son SHA-256 (« Ce fichier existe déjà dans ce cours : « titre ». »). Le même fichier reste importable dans un autre cours.

Le serveur choisit le nom stocké, `courses/<32 caractères hexadécimaux>.<extension>`. Le nom d’origine est réduit à un nom de fichier sans chemin ni caractère de contrôle (180 caractères) et ne sert qu’à l’affichage et au téléchargement. Le fichier est écrit avant la transaction et supprimé si l’écriture en base échoue. L’interface vérifie aussi le type et la taille avant l’envoi, mais seul le contrôle serveur fait foi.

## Extraction du texte des PDF

Un PDF est traité dès l’import, dans la même requête, et de nouveau sur « Relancer le traitement ». pypdf extrait le texte page par page : un extrait par page non vide, avec son numéro de page (à partir de 1), les espaces normalisés, les paragraphes conservés et au plus 20 000 caractères par page. Une page illisible est ignorée et journalisée.

Si le document donne moins de 20 caractères par page en moyenne, la ressource passe en « Sans texte exploitable » : « Ce PDF semble numérisé : aucun texte exploitable. Il reste consultable mais n’est pas indexé. » Il n’y a pas de reconnaissance de caractères (OCR). La tâche enregistre le fournisseur `pypdf`, sa version, la durée en millisecondes et le nombre d’extraits.

## Transcription Whisper

Un audio importé reste « En attente » jusqu’à son traitement par le worker :

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py process_course_jobs
```

Options : `--once` traite les tâches disponibles puis s’arrête, `--sleep 5` fixe l’attente en secondes quand la file est vide, `--limit N` arrête après N tâches. À chaque tour, le worker reprend les tâches restées « En cours » plus de 15 minutes, par exemple après l’arrêt brutal d’un worker : elles repassent en attente, ou en échec après trois tentatives. Il prend ensuite la plus ancienne tâche disponible. Deux workers ne traitent jamais la même tâche. Chaque tâche affiche une ligne ; Ctrl+C ou SIGTERM laisse finir la tâche en cours, puis le worker s’arrête proprement. Avec `COURSES_PROCESS_INLINE=true`, l’audio est transcrit pendant la requête d’import ou de relance, qui attend la fin de la transcription : à réserver aux démonstrations sur des fichiers courts.

Le fournisseur est choisi par `WHISPER_PROVIDER` :

| Valeur | Fonctionnement | À utiliser pour |
| --- | --- | --- |
| `disabled` (défaut) | Aucune transcription : « La transcription automatique n’est pas configurée sur ce serveur. » La page du cours le signale quand des audios attendent. | Serveur sans transcription |
| `fake` | Trois extraits de 5 s, déterministes, dérivés de l’empreinte du fichier, langue `fr`. N’écoute pas l’audio. | Tests et démonstrations |
| `local` | faster-whisper sur le processeur, en int8, modèle `WHISPER_MODEL` (défaut `small`), `WHISPER_CPU_THREADS` threads (défaut 2), filtre de silence et faisceau de 5. | Poste ou serveur sans service externe |
| `groq` | API Groq compatible OpenAI, modèle `GROQ_WHISPER_MODEL` (défaut `whisper-large-v3-turbo`), clé `GROQ_API_KEY`. | Application hébergée |

Une valeur inconnue équivaut à `disabled`. `WHISPER_LANGUAGE` vide laisse Whisper détecter la langue ; une valeur comme `fr` l’impose. Par sécurité, `local` et `groq` sont refusés lorsque le nom de la base commence par `test_` : les tests n’appellent jamais un vrai modèle ni le réseau. `GET /api/courses/processing/` indique le fournisseur, s’il est utilisable et le nombre de ressources en attente, en cours et en échec dans le périmètre de l’utilisateur.

**Fournisseur local.** Installation facultative, en plus de `requirements.lock` :

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-whisper.txt
```

Ce fichier fixe `faster-whisper==1.2.1` et `av==18.1.0` : faster-whisper 1.2.1 ne lit plus l’audio avec PyAV 19. Au premier chargement, faster-whisper télécharge le modèle depuis Hugging Face puis le garde en cache. Le modèle est chargé une seule fois par processus, pour un modèle et un nombre de threads donnés. Un enregistrement plus long que `COURSES_MAX_AUDIO_SECONDS` est refusé avant le décodage de ses segments : « Cet enregistrement dépasse la durée maximale de 120 minutes. » avec la valeur par défaut. Sans le paquet : « faster-whisper n’est pas installé sur ce serveur : installez backend/requirements-whisper.txt. »

**Fournisseur Groq.** Une requête HTTPS multipart vers `https://api.groq.com/openai/v1/audio/transcriptions`, avec la bibliothèque standard Python, au format `verbose_json` avec horodatage par segment, délai maximal de 300 s. La clé reste côté serveur. L’enregistrement est envoyé à ce service externe. Un fichier de plus de 25 Mo est refusé sans être envoyé, quelle que soit `COURSES_MAX_AUDIO_MB`. Groq renvoie le nom de la langue ; français, anglais, arabe, espagnol, allemand, italien, portugais, néerlandais et turc sont convertis en code ISO (`fr`, `en`, `ar`…).

**Erreurs et nouvelles tentatives.**

| Cas | Message | Suite |
| --- | --- | --- |
| Groq 429 ou 5xx | Le service de transcription est momentanément indisponible. | Nouvelle tentative |
| Délai dépassé, réseau | Le service de transcription ne répond pas. | Nouvelle tentative |
| Réponse illisible | Réponse inattendue du service de transcription. | Nouvelle tentative |
| Erreur imprévue (journalisée) | Le traitement a échoué. Réessayez plus tard. | Nouvelle tentative |
| Groq 401 ou 403 | Clé du service de transcription invalide. | Échec immédiat |
| Autre refus de Groq | Le service de transcription a refusé ce fichier audio. | Échec immédiat |
| Fournisseur absent, fichier trop gros ou trop long | Messages ci-dessus | Échec immédiat |

Une nouvelle tentative remet la tâche en attente 60 s après le premier échec, puis 120 s après le deuxième ; le troisième échec est définitif. La ressource passe alors en « Échec du traitement » avec le message, et l’enseignant peut relancer le traitement. Un résultat écrit les extraits avec leurs temps de début et de fin, la durée et la langue de l’enregistrement, puis les mesures de la tâche : fournisseur, modèle, secondes d’audio, durée du traitement, nombre d’extraits et worker. Une transcription vide donne « Aucune parole détectée dans cet enregistrement. »

## Correction des textes générés

L’enseignant propriétaire et l’administrateur corrigent un extrait dans la page de la ressource : « Corriger », puis « Enregistrer la correction » ou « Annuler ». Le texte (1 à 20 000 caractères) remplace l’extrait, qui est marqué « Corrigé » ; l’auteur et la date de la correction sont enregistrés. Le texte de recherche est recalculé, la version du texte de la ressource et la version de contenu du cours augmentent. Une correction est refusée (409) tant qu’un traitement est actif, car il l’écraserait. « Relancer le traitement » remplace tous les extraits, corrections comprises. Les étudiants ne peuvent rien modifier.

## Recherche

`/espace/cours/recherche`, aussi accessible depuis un cours avec « Rechercher dans ce cours ↗ ». La recherche porte uniquement sur les cours visibles par l’utilisateur.

- Au moins 2 caractères ; seuls les 100 premiers caractères et les 6 premiers mots comptent. Tous les mots doivent être trouvés, sans tenir compte des accents ni de la casse, et un mot peut apparaître dans un mot plus long.
- Sont cherchés : titre, description et matière des cours ; titre et description des chapitres et des ressources ; texte extrait et transcriptions des ressources prêtes.
- Points par mot : 3 dans un titre, 2 dans une description, 1 dans la matière ou un extrait ; pour une recherche de plusieurs mots, 1 point de plus quand ils apparaissent ensemble, dans l’ordre. Tri par score, puis par cours et par position.
- Filtres : matière, cours et type (PDF ou audio, qui ne renvoie alors que des ressources et des extraits). Au plus 500 extraits candidats et 3 extraits par ressource.
- Chaque résultat donne un passage de 220 caractères au plus autour du premier mot trouvé, les mots surlignés et un lien vers le cours, le chapitre ou la ressource ; pour un extrait, le lien ouvre la bonne page ou le bon instant.
- 20 résultats par page, 60 recherches par minute et par utilisateur.

## Consultation, progression et statistiques

Le visualiseur affiche le PDF dans la page, avec « Ouvrir dans un nouvel onglet ↗ », « Télécharger » et le « Texte extrait » page par page. Pour un audio, il affiche le lecteur et la transcription ; chaque extrait a un bouton d’horodatage qui lance la lecture à cet instant, et l’extrait en cours est mis en évidence. `?page=N` ouvre un PDF à la page N et `?t=S` un audio à la seconde S. Les pages se rafraîchissent toutes les 4 s tant qu’une ressource est en traitement.

Quand un étudiant ouvre une ressource, sa consultation est enregistrée une fois par ouverture : nombre de vues et date de dernière consultation (600 par heure et par étudiant au plus). La progression d’un cours est le nombre de ressources consultées sur le nombre de ressources du cours, en pourcentage arrondi.

Les statistiques d’un cours (`cours/{id}/statistiques`) portent sur les étudiants inscrits actuellement dans un groupe non archivé du cours ; seules leurs consultations comptent.

- Synthèse : élèves, ressources, progression moyenne, élèves ayant tout consulté.
- Consultation par ressource : élèves l’ayant ouverte, taux et nombre total de vues.
- Progression des élèves : ressources consultées, total, pourcentage, dernière consultation.

« Exporter en CSV ↗ » télécharge `cours-<id>-progression.csv` : colonnes `Nom;Prénom;Ressources consultées;Total;Progression (%);Dernière consultation`, séparateur `;`, UTF-8 avec BOM pour Excel, dates au format `jj/mm/aaaa hh:mm` en heure de Tunis. Une cellule qui commence par `=`, `+`, `-` ou `@`, même après des espaces, est préfixée d’une apostrophe pour qu’un tableur ne l’exécute pas comme une formule, comme dans l’export de l’assiduité.

## Sécurité des fichiers

- Aucun fichier n’est servi par une URL publique. `GET /api/courses/resources/{id}/file/` exige une session active (sinon 401) et vérifie que l’utilisateur peut voir le cours (sinon 404, sans révéler l’existence de la ressource).
- Le type MIME servi est celui déterminé à l’import et le serveur envoie `X-Content-Type-Options: nosniff`.
- `Content-Disposition` est `inline` par défaut et `attachment` avec `?download=1`. Le nom d’origine est envoyé sous une forme ASCII et en UTF-8 (RFC 5987).
- `X-Frame-Options: SAMEORIGIN` est posé sur cette réponse seulement, pour afficher le PDF dans la page ; la règle globale `DENY` reste en vigueur partout ailleurs. La réponse porte `Cache-Control: private, no-store`.
- Une plage d’octets unique (`Range: bytes=a-b`) est prise en charge pour la lecture audio : 206 avec `Content-Range`, ou 416 si la plage est hors du fichier. Un en-tête mal formé ou à plusieurs plages renvoie le fichier entier.
- Les fichiers d’une ressource ou d’un cours supprimé sont effacés du disque après la validation de la transaction.

## Contrat pour le module Assistant

L’assistant ne lit pas les fichiers : il utilise le texte stocké dans MongoDB, au moyen des fonctions de `courses/services.py`. Les identifiants sont des chaînes.

| Fonction | Résultat |
| --- | --- |
| `visible_courses(user, *, at=None)` | QuerySet des cours lisibles par l’utilisateur ; règle unique de visibilité décrite plus haut. |
| `get_visible_course(user, course_id)` | Le cours, ou `NotFound('Cours introuvable.')`. |
| `course_outline(course_id)` | `[{chapter_id, title, position}]` dans l’ordre des chapitres. |
| `course_segments(course_id)` | Itérateur sur les extraits des ressources prêtes, dans l’ordre chapitre, ressource, extrait : `{resource_id, resource_title, kind, chapter_id, chapter_title, order, text, page, start_seconds, end_seconds}`. |
| `course_content_version(course_id)` | Version de contenu (chaîne), ou `NotFound` pour un cours inconnu. |
| `resource_url(course_id, resource_id, *, page=None, start_seconds=None)` | `/espace/cours/<cours>/ressources/<ressource>`, suivi de `?page=N` ou `?t=<secondes entières>`. |

Le signal `courses.signals.course_content_changed` est envoyé après la validation de la transaction (`django_mongodb_backend.transaction.on_commit`), avec `course_id`, `resource_id` (ou `None`) et `reason`. Il est envoyé en mode robuste : une erreur dans un récepteur est journalisée sans faire échouer la requête. Chaque envoi augmente aussi `content_version`.

| `reason` | Événement |
| --- | --- |
| `resource_processed` | Extraction ou transcription terminée, y compris sans texte |
| `resource_deleted` | Ressource supprimée |
| `resource_updated` | Ressource renommée ou déplacée, ressources réordonnées, nouveau traitement d’une ressource prête |
| `segment_edited` | Extrait corrigé |
| `chapters_changed` | Chapitre renommé, supprimé ou chapitres réordonnés |
| `status_changed` | Publication, retrait, archivage ou restauration |
| `groups_changed` | Groupes du cours modifiés |

La version ne change pas pour le titre ou la description du cours, la description d’un chapitre ou d’une ressource, un import encore en attente ou un traitement en échec. Le panneau de l’assistant n’est pas encore intégré à la page du cours.

## Limites connues

- Pas d’OCR : un PDF numérisé reste consultable mais n’est ni indexé ni utilisable par l’assistant.
- Un audio de plus de 25 Mo est refusé. Il n’est ni découpé ni réencodé.
- La durée maximale n’est vérifiée que par le fournisseur local : Groq transcrit tout fichier de 25 Mo au plus.
- Sans worker démarré, les audios restent « En attente », comme un PDF dont l’extraction a rencontré une erreur temporaire, et « Relancer le traitement » répond 409 tant que la tâche attend. Une tâche interrompue pendant un traitement dans la requête n’est reprise que par le worker, après 15 minutes.
- Les noms de langue renvoyés par Groq en dehors des neuf convertis sont gardés en minuscules et coupés à 8 caractères.
- La recherche compare des sous-chaînes dans MongoDB : pas d’index plein texte, de racinisation ni de tolérance aux fautes.
- Supprimer une ressource efface son historique de consultation, ce qui modifie les statistiques.
- L’interface contrôle les tailles avec les valeurs par défaut (20 et 25 Mo) : si `COURSES_MAX_PDF_MB` ou `COURSES_MAX_AUDIO_MB` change, il faut aussi modifier `frontend/src/courses/validation.ts`.
- Les fichiers sont stockés sur le disque du serveur : en production, `backend/media/` doit être sur un volume persistant et sauvegardé.
- Aucun scénario Playwright ne couvre encore les pages du module.

## Tests

Les tests backend du module sont dans `backend/courses/tests/`, un fichier par sujet : matières, cours, cycle de vie, chapitres, ressources, imports, traitement, fournisseurs de transcription, plus un parcours complet. Ils utilisent `WHISPER_PROVIDER=fake` et un dossier de fichiers temporaire. `test_providers.py` couvre `ai/transcription.py` sans réseau : `urllib.request.urlopen` est remplacé pour simuler les réponses et les erreurs de Groq, et un faux module `faster_whisper` est injecté dans `sys.modules` pour le fournisseur local.

Résultat mesuré sur cette livraison, avec Python 3.13 et MongoDB 7.0 en replica set : 88 tests `courses` réussis, dont 18 dans `test_providers.py` ; 199 tests réussis pour `accounts quizzes courses`. Couverture : 100 % pour `ai/transcription.py`, 97 % pour `courses` et `ai` (hors migrations, tests et commande du worker) et 97 % pour `accounts`, `classrooms`, `attendance`, `quizzes`, `courses` et `ai` réunis.

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py test courses --noinput
.\backend\.venv\Scripts\python.exe -m coverage run --source=accounts,classrooms,attendance,quizzes,courses,ai backend\manage.py test accounts quizzes courses --noinput
.\backend\.venv\Scripts\python.exe -m coverage report --omit="*/migrations/*,*/tests/*,*/tests.py,*/management/*"
Set-Location frontend
npm.cmd run build
```
