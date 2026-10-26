# Reproduire les tests

## Backend

Démarrer MongoDB avec `scripts/Start-Mongo.ps1`, puis à la racine :

```powershell
.\backend\.venv\Scripts\python.exe -m coverage run --source=accounts,classrooms,attendance backend\manage.py test accounts --noinput -v 1
.\backend\.venv\Scripts\python.exe -m coverage report --omit="*/migrations/*,*/tests/*,*/management/*"
```

Base dédiée `test_nexora_hub_isolated`. Le runner Django crée puis détruit cette base. Les tests emploient un backend email mémoire et des mots de passe aléatoires. Leur hasher MD5 accélère uniquement les fixtures sous `override_settings` ; l’application normale conserve les hashers Django par défaut. Les validateurs de force de mot de passe restent actifs dans les tests.

39 tests d’intégration couvrent inscription/validation/email unique/rôles, connexion/session/CSRF/throttle, reset/expiration/usage unique/invalidation, profils/avatars/droits, dernier admin y compris concurrence, dépendances de rôles, confidentialité, périodes et réinscriptions, séances/chevauchements/archives, feuilles/participants/validation/corrections/version et véritables requêtes simultanées, statistiques/exclusions/historique/CSV et le scénario métier complet. Les tests de concurrence utilisent deux connexions et deux clients en threads, sans mock de la base.

## Navigateur

Les serveurs de test sont distincts de la base et du backend de développement. Installer les dépendances (`npm.cmd ci` depuis frontend) et Chromium :

```powershell
Set-Location C:\Users\USER\Downloads\edu\frontend
npx.cmd playwright install chromium
```

Terminal 1, à la racine :

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput --settings=config.roles_e2e_settings
.\backend\.venv\Scripts\python.exe backend\manage.py prepare_browser --settings=config.roles_e2e_settings
.\backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8002 --noreload --settings=config.roles_e2e_settings
```

`prepare_browser` refuse toute base autre que `test_nexora_roles_browser_isolated`. Il crée un nouveau jeu de comptes sans écraser les précédents et écrit les identifiants aléatoires dans `.local/browser.json`, ignoré par Git. L’étudiant du scénario s’inscrit ensuite dans l’interface. Relancer cette commande avant chaque nouvel essai du scénario complet.

Terminal 2, depuis frontend :

```powershell
$env:VITE_API_TARGET='http://127.0.0.1:8002'
npm.cmd run dev -- --port 5174 --strictPort
```

Terminal 3, à la racine, pour servir les fichiers Eduleb originaux :

```powershell
.\backend\.venv\Scripts\python.exe -m http.server 8001 --bind 127.0.0.1
```

Terminal 4, depuis frontend :

```powershell
npx.cmd playwright test
```

`scenario.spec.ts` : inscription, reconnexion après actualisation, administrateur attribuant TEACHER, création du groupe et des inscriptions, création de séance par l’enseignant, « tous présents » sans écriture, brouillon, validation via dialogue et clavier, correction motivée, statistiques isolées, refus API 403, vue mobile étudiant, ouverture du menu au clavier et fermeture par Échap avec retour du focus, annulation et consultation de la feuille historique bloquée en écriture.

`visual.spec.ts` : captures de l’original et du React à 1440×1000 et 390×844, défilement préalable de l’original pour activer ses animations, absence de débordement horizontal, menu mobile, pages publiques/404/modules futurs, axe et parcours clavier du lien d’évitement jusqu’au formulaire. Les réponses d’assets en erreur et les exceptions JavaScript non gérées font échouer le contrôle public. Les réponses 401/403 prévues par les tests de sécurité ne constituent pas des erreurs métier inattendues.

Résultats JSON dans `docs/browser-results.json`, rapports axe dans `docs/axe-*.json`, captures dans `docs/screenshots/`. Les traces des échecs sont locales sous `frontend/test-results/`, ignoré par Git. Les tests ne prouvent pas une conformité d’accessibilité complète. Les vérifications humaines restantes sont détaillées dans `VERIFICATIONS.md`.


## Vérifier la séparation des interfaces

`front-office.spec.ts` crée ses affectations dans la base navigateur dédiée, puis vérifie 54 combinaisons route/largeur : 8 pages étudiant, 9 pages enseignant et 10 pages administrateur, chacune à 1440×1000 et 390×844. Chaque page est également rechargée directement. Le test vérifie l’absence effective de shell administratif dans le DOM pédagogique, le header/footer Eduleb, le conteneur centré, les redirections, l’absence de débordement horizontal, les menus au clavier, la modification du profil pour les trois rôles et la création de séance depuis l’accueil enseignant. Il enregistre `docs/front-office-routes.json`, six rapports axe de layout et les captures `front-office-*` / `back-office-*`.

Le scénario métier existant a été adapté au nouveau header et aux intitulés « Mon espace » / « Espace enseignant ». Les 401 sur `auth/me/` avant connexion sont attendus ; ils indiquent une session absente. `React.StrictMode` peut provoquer deux vérifications en développement. Les pages privées restent protégées.


Le nouveau `roles.spec.ts` vérifie les deux choix publics, la redirection selon le rôle et l’absence de choix administrateur. La base historique des anciens tests, qui pouvait contenir plusieurs administrateurs, est conservée intacte. Les nouveaux tests navigateur utilisent `config.roles_e2e_settings` et une base distincte. `prepare_browser` y crée un seul administrateur, puis le réutilise sans changer son mot de passe lors des exécutions suivantes ; les identifiants de fixture aléatoires sont uniquement dans `.local`, ignoré par Git.

## Module Quiz–Question

Les commandes complètes du module figurent dans [QUIZ.md](QUIZ.md). La suite contient maintenant sept tests navigateur, dont `quizzes.spec.ts`, `quiz-validation.spec.ts` et `attempts.spec.ts`. Pour des relances rapprochées, `config.quiz_e2e_settings` et `QUIZ_TEST_RUN` créent une nouvelle base strictement nommée `test_nexora_quiz_<run>`, sur le même MongoDB local et avec les mêmes protections ; les données précédentes restent intactes. Le test de déconnexion attend explicitement la fin du chargement avant d’évaluer une nouvelle URL protégée. Les contrôles de saisie sont détaillés dans [QUIZ-VALIDATION.md](QUIZ-VALIDATION.md) et le passage/correction dans [QUIZ-PASSAGE.md](QUIZ-PASSAGE.md).
