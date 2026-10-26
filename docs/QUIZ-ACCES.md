# Accès au passage depuis la présentation étudiante

Le passage du quiz était déjà implémenté dans `.local/publication` : Tentative/Réponse, instantanés, sauvegarde, reprise, soumission, correction et pages React. La présentation de ce dépôt utilisait déjà `QuizAttemptAccess`.

Le blocage venait de la copie servie sur le port habituel 5173 : son fichier `QuizDetail.tsx` contenait encore le message provisoire et son API au port 8000 renvoyait 404 sur `student/attempts/`. Le dépôt à jour était servi séparément sur 5175/8003.

## Correction

- Le démarrage habituel sur **5173/8000** utilise désormais le code de `.local/publication`.
- Dans la copie de travail `edu`, les scripts npm de `frontend/package.json` délèguent au frontend du dépôt ; la configuration Vite vise aussi ce dossier pour les lancements directs. `backend/manage.py` charge les modules Django du dépôt et conserve la configuration locale de `backend/.env`.
- Les trois points d’entrée locaux d’origine sont conservés dans `.local/legacy-entrypoints`, avec leurs empreintes. Les anciennes sources ne sont pas supprimées.
- La présentation affiche **Commencer le quiz**, **Reprendre**, les liens de correction et un message explicite **Limite de tentatives atteinte**. Un échec de chargement des tentatives propose de réessayer.
- Les routes et règles métier existantes sont réutilisées. Aucune génération Gemini, aucun nouveau modèle ni nouvelle migration.

Pages courantes : [Quiz étudiant](http://127.0.0.1:5173/espace/quiz), [tentatives et corrections](http://127.0.0.1:5173/espace/tentatives). Le résultat reste sous `/espace/tentatives/{id}/resultat`.

Depuis `edu`, la commande habituelle `python backend/manage.py runserver 127.0.0.1:8000` utilise le backend courant. Depuis `edu/frontend`, `npm.cmd run dev` utilise le frontend courant. On peut également travailler directement dans `.local/publication` avec les commandes normales du dépôt.

## Vérifications exécutées

- Les imports Django lancés depuis `edu/backend/manage.py` résolvent bien les modules `quizzes` et `config` du dépôt `.local/publication`.
- `manage.py check` : aucun problème. `makemigrations --check --dry-run` : aucune migration manquante.
- `manage.py test quizzes.test_attempts --noinput` : **22 tests réussis**, sur une base isolée. Ces tests couvrent permissions de rôle et groupe, publication, quota, départs concurrents, expiration, confidentialité, sauvegarde/reprise, score et soumission répétée.
- `npm.cmd run build` : typage TypeScript et build Vite réussis.
- Deux parcours Playwright réussis **sur le port 5173**, avec `E2E_BASE_URL=http://127.0.0.1:5173`, et une API/base de test isolée au port 8002 pendant leur exécution. Après les tests, 5173 a été rétabli sur l’API locale habituelle 8000.
- `quizzes.spec.ts` vérifie la publication dans l’interface enseignant, l’ouverture par un étudiant inscrit, le bouton Commencer le quiz, les trois réponses sauvegardées, la soumission et le résultat de **6/6**. Les autres rôles et actions du CRUD sont également vérifiés.
- `attempts.spec.ts` vérifie les sauvegardes retardées, une panne réseau, la reprise depuis la présentation sur le même identifiant de tentative, l’actualisation, la soumission coordonnée, la correction expliquée de **5/6 (83,33 %)**, l’accès au résultat depuis la présentation, la reprise après archivage et le message de limite après épuisement d’un quiz à tentative unique.
- Aucun corrigé n’est renvoyé dans la réponse API de passage ; la demande de résultat pendant une tentative en cours est refusée. Les captures ordinateur/mobile et contrôles axe ciblés sont conservés par les scénarios existants.
- Vérification après retour aux données locales : les modules servis sur 5173 contiennent `QuizAttemptAccess` et le nouveau bouton, sans le texte provisoire ; `/api/student/attempts/` répond **401** pour un visiteur sur le proxy 5173 et directement sur 8000, ce qui confirme que la route existe et reste protégée.

Les résultats sont enregistrés dans `quiz-access-verification.json` et `quiz-access-browser-results.json`. La suite générale n’a pas été relancée. Aucun point bloquant constaté. Aucun commit, push ou merge ; `main` reste inchangée.
