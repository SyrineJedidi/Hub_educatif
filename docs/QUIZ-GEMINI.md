# Propositions de questions avec Gemini

> Document historique. Le fournisseur actif est désormais **IA locale — Qwen3 via Ollama**. Consulter [la configuration actuelle](QUIZ-OLLAMA.md). Les anciens tests et services Gemini ont été sauvegardés localement avant remplacement.

Depuis un quiz en brouillon, l’enseignant propriétaire ou l’administrateur ouvre **Générer des questions avec l’IA**. Le formulaire accepte du texte collé (obligatoire, 30 000 caractères maximum), entre 1 et 10 questions et un niveau. Le cours est envoyé comme donnée à analyser, séparé des instructions système ; aucun outil, compte ou secret de l’application n’est transmis.

Les propositions ne sont pas enregistrées. L’utilisateur vérifie et modifie l’énoncé, les quatre choix, la bonne réponse, l’explication, la notion et les points, puis sélectionne ou retire les propositions. **Ajouter les questions sélectionnées** enregistre uniquement la sélection, en une transaction et à la suite des questions existantes. Le quiz reste en brouillon.

## Configuration serveur

Dans l’environnement Django ou son `backend/.env` ignoré par Git :

```dotenv
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_TIMEOUT_SECONDS=30
```

Renseigner la clé localement sans la copier dans le frontend, les journaux ou la documentation. `GOOGLE_API_KEY` est accepté en repli uniquement lorsque `GEMINI_API_KEY` n’est pas défini. Le modèle doit accepter `generateContent` avec sortie JSON structurée. Gemini 3 utilise un niveau de réflexion faible pour ces QCM courts afin de limiter l’attente ; les modèles 2.x personnalisés ne reçoivent pas ce paramètre incompatible. Le délai est configurable de 1 à 60 secondes. Redémarrer Django après modification de configuration. Aucune nouvelle dépendance Python ou npm.

Appliquer `python backend/manage.py migrate`. La migration additive `quizzes/0004_question_notion_and_import_receipt.py` ajoute une notion facultative aux questions existantes et un reçu technique de confirmation. La notion est obligatoire pour les propositions IA ; les anciennes questions ne sont pas complétées artificiellement. Les migrations antérieures sont conservées.

## API et protections

- `POST /api/quizzes/{id}/generate-questions/` : `course_text`, `count`, `level`. Réponse `questions` avec `statement`, `choice_a` à `choice_d`, `correct_answer`, `explanation`, `notion`, `points`. Aucune création de Question ou de reçu à cette étape.
- `POST /api/quizzes/{id}/import-questions/` : `import_key` UUID, `confirmed: true`, `questions` contenant uniquement la sélection. Positions et quiz parent attribués côté serveur. Réponse `results` et `replayed`.

Les routes réutilisent session, CSRF, droits et verrouillage du quiz. La génération vérifie encore les droits et l’état après l’appel externe, sans transaction ouverte pendant l’attente. Les sorties passent les serializers et validations existants : choix distincts après normalisation, champs obligatoires, longueurs et points entiers de 1 à 10. Les champs techniques sont refusés.

Les appels sont limités à cinq par compte et par fenêtre de cinq minutes, tous quiz confondus, avec les compteurs persistants existants. Aucune relance automatique payante. Configuration absente/inutilisable, quota atteint, indisponibilité, délai dépassé et sortie invalide produisent des messages français sans réponse brute du fournisseur. La taille de sa réponse est bornée.

Les erreurs ont des codes distincts : `gemini_not_configured`, `gemini_key_rejected`, `gemini_access_denied`, `gemini_request_invalid`, `gemini_quota`, `gemini_model_unavailable`, `gemini_timeout`, `gemini_overloaded`, `gemini_unavailable`, `gemini_network`, `gemini_tls_error` et `gemini_invalid_response`. Le service examine au plus 16 Kio de réponse d’erreur pour reconnaître une clé refusée ou une saturation, sans conserver ni exposer le texte libre reçu. Les journaux ne contiennent que la catégorie interne et le statut HTTP fournisseur, jamais la clé, le cours, le corps de requête ou les détails d’exception réseau. Une erreur réseau n’est plus présentée comme une indisponibilité confirmée de Gemini.

Le dernier diagnostic précis est dans `quiz-gemini-diagnostic.json` : un seul appel réel, une question validée, HTTP 200 et aucune erreur réseau. Ce diagnostic n’a pas reproduit le 503 signalé et ne permet pas d’attribuer un nouvel incident à une cause externe sans sa trace correspondante. Les 25 tests Gemini ciblés couvrent la distinction des erreurs et vérifient aussi que les messages et journaux n’exposent ni clé ni contenu du cours.

Un même `import_key` avec le même contenu ne crée qu’un lot ; un contenu différent avec cette clé est refusé. Transaction et index unique protègent les confirmations simultanées. Après une réponse réseau perdue, l’interface conserve sélection et clé et propose le même ajout sans doublon ; les modifications du lot restent bloquées jusqu’à résolution. Le reçu ne contient ni cours ni propositions non confirmées.

Pages : `/espace/quiz/{id}/generer` pour l’enseignant Eduleb ; `/administration/quiz/{id}/generer` pour l’administrateur. Les étudiants ne peuvent pas accéder à ces API de gestion.

Références officielles : [generateContent](https://ai.google.dev/api/generate-content) et [sorties structurées Gemini](https://ai.google.dev/gemini-api/docs/generate-content/structured-output). Les validations structurelles ne prouvent pas l’exactitude pédagogique d’une réponse ; une revue reste nécessaire.

## Vérifications

`python backend/manage.py test quizzes --noinput` couvre les tests existants et `test_gemini.py`. Le fournisseur est simulé : permissions, saisies, délais, quotas, erreurs, absence de sauvegarde avant confirmation, validation, ordre et idempotence concurrente. Aucun appel facturé dans ces tests.

`frontend/tests/gemini.spec.ts` vérifie l’interface et l’ajout Django réel sur une base isolée. Démarrer le serveur avec `config.quiz_e2e_settings`, un `QUIZ_TEST_RUN` neuf et `GEMINI_API_KEY` / `GOOGLE_API_KEY` vides dans l’environnement du processus. Après vérification de l’erreur de configuration, les propositions sont simulées au niveau HTTP dans Playwright. L’ajout et sa nouvelle tentative après perte de réponse utilisent les vraies API Django. Utiliser les fixtures `prepare_browser` habituelles et `E2E_BASE_URL` si nécessaire.

Le bilan exécuté est consigné dans `quiz-gemini-verification.json`. Après la vérification initiale sans clé, une clé a été configurée localement et un appel réel d’une question a réussi dans le navigateur avec `gemini-3.1-flash-lite`, sans enregistrement automatique. Le fournisseur refusait `gemini-2.5-flash` pour ce nouveau compte et signalait une saturation de `gemini-3.8-flash` lors du diagnostic ; le modèle reste configurable. Référence : [Gemini 3.1 Flash-Lite et ses sorties structurées](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite).

La page réelle `/espace/quiz/{id}/generer` a été vérifiée après redémarrage des serveurs : ouverture directe et actualisation, sans erreur de module ni exception JavaScript. Le cache Vite a été renouvelé après l’échec du rechargement de `App.tsx`. Une réponse HTTP complète qui ferme sa connexion est correctement lue ; une indisponibilité de modèle renvoie un message français précis. Les 22 tests Gemini ciblés passent après ces corrections, ainsi que les contrôles Django, la cohérence des migrations, le typage et le build React. Aucun commit, push ou merge pour cette étape.
