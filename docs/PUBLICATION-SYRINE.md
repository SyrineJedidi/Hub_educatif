# Livraison du module Quiz–Question sur Syrine

Le module comprend le CRUD des quiz et questions, les contrôles de saisie, la publication et l’archivage, le passage étudiant avec sauvegarde et reprise, la soumission, la correction automatique et la consultation des résultats par l’enseignant propriétaire ou l’administrateur. Les étudiants et enseignants utilisent le front-office Eduleb ; l’administration conserve son back-office.

Les documents `QUIZ*.md` conservent l’historique des étapes. Leurs mentions de fonctionnalités « à venir » et d’absence de publication décrivent ces étapes antérieures. Le présent bilan décrit la livraison complète actuelle, sans génération Gemini ni statistiques avancées.

## Données et migrations

Les trois migrations `quizzes/0001_initial.py`, `0002_attempt_answer_and_more.py` et `0003_alter_question_explanation_alter_quiz_description_and_more.py` sont conservées. Sur une autre installation, appliquer `python backend/manage.py migrate` avec la configuration et l’environnement habituels. Aucune donnée existante n’est supprimée ou complétée artificiellement. Le rapport des anciennes saisies non conformes reste dans `quiz-required-inputs-legacy.json`.

Le clone local utilisé est `.local/publication`. Avant le changement de branche, les sources suivies et nouvelles, l’historique Git et les fichiers privés de fonctionnement ont été sauvegardés séparément sous `.local/backups/quiz-before-Syrine-20261026-134840` du dossier local `edu`. Ces archives privées ne font pas partie du dépôt. Les bases locales, `.env`, environnements, dépendances et fichiers de compilation restent ignorés.

## Vérifications du 26 octobre 2026

- `python backend/manage.py check` : aucun problème.
- `python backend/manage.py makemigrations --check --dry-run` : aucune migration manquante.
- `python backend/manage.py test quizzes --noinput` : 72 tests réussis, couvrant les permissions, validations, états des quiz, instantanés privés, tentatives, concurrence, sauvegarde, expiration, soumission idempotente, scores et résultats en lecture seule.
- `python backend/manage.py test accounts classrooms attendance --noinput` : 39 tests existants réussis.
- `npm.cmd run build` : typage TypeScript et compilation Vite réussis.
- Quatre scénarios Playwright Chromium réussis, chacun dans une nouvelle base isolée : `quizzes.spec.ts`, `quiz-validation.spec.ts`, `attempts.spec.ts` et `student-results.spec.ts`.

Ces parcours vérifient notamment enseignant → publication → étudiant inscrit → passage → réponses → soumission → correction, la reprise après actualisation, les formulaires et la consultation enseignant/administrateur. Ils incluent les contrôles clavier, mobile et axe prévus par ces scénarios. La suite navigateur générale n’a pas été relancée pour cette publication ; Safari, Firefox et un audit humain complet d’accessibilité ne sont pas couverts.

Le résumé exploitable figure dans `quiz-publication-verification.json`. Les captures `screenshots/quiz-*` et `screenshots/student-results-*` sont conservées comme preuves visuelles. La fusion finale reste à effectuer sur GitHub après revue de la Pull Request `Syrine` → `main`.
