# IA locale — Qwen3 via Ollama

La génération du module Quiz appelle désormais le serveur Ollama depuis Django. Le parcours reste : texte collé → propositions → modification et sélection → ajout confirmé au brouillon. L’endpoint `POST /api/quizzes/{id}/generate-questions/` conserve ses entrées `course_text`, `count` (1 à 10), `level` et sa réponse `questions`. L’ajout utilise toujours `import-questions/`, avec confirmation et clé d’idempotence. React ne contacte pas directement Ollama.

## Configuration

Dans `backend/.env` du dépôt actif `.local/publication`, ou dans l’environnement du processus Django :

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT_SECONDS=180
```

Aucune clé API nécessaire pour cette instance locale. L’URL et le modèle proviennent uniquement de la configuration serveur ; les champs utilisateur supplémentaires sont refusés par le serializer existant. Les variables Gemini ne sont plus utilisées par la génération. Redémarrer Django après modification du `.env`.

Le backend vérifié s’exécute avec le Python Windows existant, hors Docker et WSL : `127.0.0.1:11434` désigne bien le serveur Windows. Si Django est déplacé dans un conteneur ou WSL, définir une adresse joignable depuis cet environnement (par exemple `http://host.docker.internal:11434` sous Docker Desktop) et vérifier la connexion depuis ce même environnement. Il n’est pas nécessaire de modifier les URL du frontend.

Vérification locale sans lancer de génération :

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/version
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

## Appel et limites

Le service `backend/quizzes/generation.py` vérifie `/api/version` et `/api/show`, notamment la capacité de complétion, le support de `think=false` et la taille native du contexte. Puis il appelle une seule fois `POST /api/chat` avec `stream=false`, `think=false`, un schéma JSON dans `format`, des messages système/utilisateur distincts et une sortie française concise. La réponse est lue dans `message.content`. Aucune relance automatique et aucun remplacement par de fausses questions.

Le cours est une donnée à analyser ; les instructions qu’il contient ne doivent pas remplacer les règles système. Le service ne fournit aucun outil au modèle. Les propositions passent ensuite les serializers et les validations de modèle existants : nombre exact demandé, champs obligatoires, longueurs, quatre choix distincts après normalisation, bonne réponse unique A/B/C/D, notion et points de 1 à 10. Une réponse non finale, tronquée (`done_reason` différent de `stop`), mal formée ou ne respectant pas `think=false` est refusée.

La requête réserve `512 + 600 × nombre de questions` tokens de sortie. Le contexte demandé tient compte des messages complets, du schéma, d’une marge pour le template de conversation et de cette réserve. Une borne conservatrice en octets UTF-8 évite de sous-estimer les tokens du tokenizer Qwen3. Le contexte est arrondi au multiple supérieur de 1 024 tokens et plafonné au plus petit de 16 384 tokens et de la capacité native annoncée. Ce plafond limite aussi la mémoire nécessaire au modèle 8b. Un cours trop long est refusé explicitement sous le champ du cours ; aucune découpe silencieuse.

Le délai total est de 180 secondes par défaut, partagé entre les vérifications et la génération ; chaque vérification de métadonnées a au plus 10 secondes. Le délai serveur configurable est compris entre 1 et 600 secondes. Les réponses sont bornées en taille. Les erreurs distinguent : configuration invalide, Ollama arrêté/inaccessible, modèle absent, version incompatible, serveur occupé, mémoire insuffisante, délai dépassé, sortie tronquée et sortie invalide. Les journaux ne contiennent que catégorie interne et statut HTTP, sans cours ni corps de réponse du modèle.

La limite existante de cinq demandes par compte sur cinq minutes est conservée. Un bail atomique partagé en base, avec échéance et libération après succès/erreur, empêche deux générations simultanées vers le même serveur depuis les workers Django utilisant cette base. Ce bail réutilise les compteurs existants sans migration supplémentaire.

## Interfaces et permissions

L’enseignant propriétaire ouvre un quiz en brouillon → **Générer des questions avec l’IA**, route `/espace/quiz/{id}/generer`. L’administrateur utilise `/administration/quiz/{id}/generer`. Le header/footer Eduleb, les formulaires, le clavier, le responsive, la conservation des saisies après erreur et les sauvegardes confirmées restent en place. Les étudiants, enseignants extérieurs, comptes inactifs et quiz verrouillés sont refusés côté Django. La publication reste manuelle.

Aucun modèle métier ni migration ajouté pour le changement de fournisseur. Les comptes, groupes, anciennes questions, tentatives, corrections et le reçu d’ajout existant sont conservés. Les modifications précédentes ont été archivées sous `.local/backups/before-ollama-*` avant remplacement des fichiers Gemini ; ces sauvegardes privées ne sont pas publiées.

## Vérifications exécutées

- `python backend/manage.py test quizzes --noinput` : **101 tests réussis**, dont les 72 tests existants du module et 29 tests de génération et d’ajout. Ollama est simulé dans les tests automatisés habituels.
- `python backend/manage.py check` et `makemigrations --check --dry-run` : vérifiés, sans problème ni nouvelle migration.
- `npm.cmd run build` : typage TypeScript et build Vite réussis.
- `tests/generation.spec.ts` : parcours Chromium avec erreurs simulées, validation, édition, retrait/sélection, confirmation après perte de réponse, ordinateur/mobile et axe ciblé.
- `tests/ollama-live.spec.ts` : parcours Chromium réel, opt-in avec `RUN_OLLAMA_LIVE=1`, sur une base navigateur isolée. **Trois questions générées en 25,568 secondes**, modification et sélection puis ajout confirmé de deux questions. Zéro question enregistrée avant confirmation, quiz toujours en brouillon, zéro appel direct du navigateur à Ollama et aucune exception JavaScript.

L’instance réelle annonce Ollama **0.40.10**, Qwen3 **8b Q4_K_M** et une capacité native de **40 960 tokens** ; `think=false` est explicitement supporté et a fonctionné dans l’essai réel. Le temps mesuré est celui de la requête vue par le navigateur, incluant les vérifications Django et le chargement éventuel du modèle. Il dépend du matériel et du texte ; les demandes longues peuvent dépasser le délai configuré. Aucun essai de dix questions ou de cours de longueur maximale n’est revendiqué.

Pour les tests navigateur, préparer une nouvelle base avec `config.quiz_e2e_settings`, `QUIZ_TEST_RUN` et `prepare_browser` selon le protocole existant. Le test simulé `generation.spec.ts` attend une instance backend configurée avec `OLLAMA_BASE_URL=http://127.0.0.1:1` et un court délai, afin de vérifier le message de serveur inaccessible sans lancer de génération. Le test réel utilise l’URL Ollama correcte et le délai de 180 secondes. Exécuter ces deux scénarios sur des bases distinctes ; le test réel est ignoré tant que `RUN_OLLAMA_LIVE` n’est pas égal à `1`.

Rapports : `quiz-ollama-verification.json`, `ollama-live-verification.json`. Captures : `screenshots/quiz-ollama-desktop.png`, `screenshots/quiz-ollama-mobile.png`, `screenshots/quiz-ollama-live.png`. La suite navigateur générale, les autres navigateurs et un audit humain complet d’accessibilité n’ont pas été relancés. Aucun commit, push ou merge pour cette intervention.

Références officielles : [API chat](https://docs.ollama.com/api/chat), [sorties structurées](https://docs.ollama.com/capabilities/structured-outputs), [contrôle de réflexion](https://docs.ollama.com/capabilities/thinking), [contexte](https://docs.ollama.com/context-length).
