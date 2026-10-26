# Vérification du module Quiz–Question

Vérifications exécutées le 26 octobre 2026, sur Django–MongoDB et React existants. La première étape est fonctionnelle : création, modification et suppression des brouillons, gestion des QCM, prévisualisation, publication, verrouillage, duplication et archivage.

Mise à jour des contrôles de saisie et de la visibilité : [QUIZ-VALIDATION.md](QUIZ-VALIDATION.md) détaille les validations renforcées et les derniers résultats (72 tests backend et relance ciblée des deux tests navigateur Quiz). Le tableau ci-dessous conserve les résultats de la livraison initiale du module.

## Résultats exécutés

| Contrôle | Résultat |
| --- | --- |
| `python backend/manage.py check` | Aucun problème |
| `python backend/manage.py makemigrations --check --dry-run` | Aucune migration manquante |
| `coverage run --source=accounts,classrooms,attendance,quizzes backend/manage.py test accounts quizzes --noinput` | 66 tests réussis, dont 27 nouveaux tests Quiz–Question |
| Couverture du code métier mesuré, hors tests/migrations/commandes | 94 % ; services Quiz 100 %, vues Quiz 96 % |
| `npm.cmd run build` dans `frontend` | Typage TypeScript et build Vite réussis |
| `npx.cmd playwright test` dans `frontend` | 5 tests réussis, aucun échec ni test ignoré |
| Axe sur les pages du module | 8 rapports, aucune violation détectée |

Les résultats lisibles par machine sont dans [quiz-verification.json](quiz-verification.json), [quiz-browser-results.json](quiz-browser-results.json) et [quiz-coverage-summary.txt](quiz-coverage-summary.txt).

La suite backend utilise `test_nexora_hub_isolated`. Le dernier parcours navigateur complet utilise une nouvelle base `test_nexora_quiz_<run>` via `config.quiz_e2e_settings`. Les anciennes bases et les données de développement sont préservées. Les quotas de sécurité restent actifs. Les identifiants de fixture aléatoires restent exclusivement dans `.local`, ignoré par Git.

## Règles et protections couvertes

- Bornes, espaces seuls, quatre propositions distinctes après normalisation, réponse unique, groupe actif et affectation cohérente.
- Propriétaire enseignant issu de la session, isolation des listes/détails/actions, question appartenant au quiz de son URL.
- Administrateur autorisé à gérer tous les quiz, avec sélection d’un enseignant actif et de son groupe ; mêmes verrouillages métier.
- Étudiant limité aux présentations publiées de ses groupes avec inscription actuelle. Groupe archivé, inscription future/terminée et quiz hors groupe exclus.
- Aucune question, proposition, bonne réponse ou explication dans les réponses étudiantes ; API de gestion interdite aux étudiants.
- Publication vide/incomplète refusée avec raisons précises ; métadonnées et questions verrouillées après publication ; suppression réservée aux brouillons.
- Duplication indépendante sans date de publication, conservation de l’ordre et des points ; archivage conservant les données.
- Protection CSRF, comptes inactifs, refus des champs inconnus et changements arbitraires de statut.
- Index unique MongoDB `(quiz_id, position)` vérifié directement et créations réellement concurrentes testées. La garde transactionnelle existante peut répondre 409 en cas de contention persistante ; aucune position dupliquée n’est acceptée.
- Suppression d’un groupe référencé par un quiz refusée avec une erreur métier.

## Parcours et présentation

Le scénario demandé est exécuté dans `frontend/tests/quizzes.spec.ts` : « Les bases de Python », groupe de l’enseignant, niveau facile, 10 minutes, deux tentatives autorisées comme paramètre, trois questions valant six points, proposition dupliquée refusée, publication sans explication refusée, correction puis publication. Le test vérifie ensuite le verrouillage, la présentation de l’étudiant inscrit, le refus à un étudiant extérieur, la consultation administrateur, la duplication indépendante et l’archivage.

Les formulaires sont également vérifiés après erreur réseau et après annulation d’une navigation interne ou d’un retour navigateur, sans perte de saisie. Les radios de correction sont manipulées au clavier ; les dialogues sont contrôlés avec Échap et retour du focus. Les pages protégées sont rechargées directement.

Les suites existantes vérifient aussi l’inscription par rôle, la déconnexion, l’assiduité, les protections API et 54 combinaisons route/largeur des trois espaces. L’accueil Eduleb existant est contrôlé à nouveau sur ordinateur et mobile.

Dimensions des contrôles navigateur : 1440 × 1000 et 390 × 844. Le module est vérifié avec de longs titres et énoncés, sans débordement horizontal. Les étudiants et enseignants ont le header/footer Eduleb sans sidebar permanente ; l’administrateur conserve son back-office. Les styles du module restent isolés, et la préférence de réduction des animations reste respectée par les styles communs.

| Espace | Ordinateur | Mobile |
| --- | --- | --- |
| Enseignant, prévisualisation | [Capture](screenshots/quiz-teacher-preview-desktop.png) | [Capture](screenshots/quiz-teacher-preview-mobile.png) |
| Étudiant, présentation | [Capture](screenshots/quiz-student-desktop.png) | [Capture](screenshots/quiz-student-mobile.png) |
| Administrateur | [Capture](screenshots/quiz-admin-desktop.png) | [Capture avec titre long](screenshots/quiz-admin-mobile.png) |

Les huit rapports `axe-quiz-*.json` couvrent les formulaires Quiz et Question, la prévisualisation ordinateur/mobile, la présentation étudiante ordinateur/mobile et la gestion administrateur ordinateur/mobile avec contenu long. Les captures ont également été inspectées visuellement par l’agent. Ces contrôles Chromium et axe ne constituent pas un audit humain complet, ni une vérification Safari/Firefox ou avec lecteur d’écran.

## Mise en route et état Git

La migration additive `quizzes/0001_initial.py` a été appliquée à la base de développement et aux bases de test ; aucune migration destructive. Pour une autre installation, lancer `python backend/manage.py migrate` dans l’environnement existant, puis les serveurs habituels. Les commandes détaillées, API et routes sont dans [QUIZ.md](QUIZ.md).

Entrées principales : `/espace/quiz` pour enseignant/étudiant et `/administration/quiz` pour administrateur. L’alias `/modules/quiz` redirige selon la session et le rôle.

Le clone Git est `.local/publication`, sur `feature/quiz-progression`. Le code de développement est synchronisé dans ce clone pour revue. `main` reste au commit `1af567a9c23bae07aa0c7fbbfbd654db51d66aa7`. Aucun commit, push ou merge de cette étape ; aucun dépôt parent modifié.

Aucun point bloquant restant constaté dans le périmètre demandé. La génération IA, le passage des quiz, les tentatives, les scores et la progression restent réservés aux étapes suivantes.
