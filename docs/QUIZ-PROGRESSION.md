# Quiz : calendrier, progression, notes et langues

Le module existant conserve ses sessions, permissions, brouillons verrouillés après publication, corrections historiques et génération locale Ollama.

- **Calendrier facultatif** : ouverture et fermeture avec fuseau, contrôlées par l’heure serveur. Une tentative reçoit l’échéance la plus proche entre sa durée et la fermeture. Les échéances déjà enregistrées restent fixes. L’interface indique Africa/Tunis (UTC+01:00) et le temps disponible avant le départ.
- **Priorités étudiantes** : à terminer, à commencer, à venir ; compteurs de quiz distincts et échéances proches en premier. Les reprises facultatives et quiz archivés ne constituent pas du travail obligatoire.
- **Mes résultats** : quiz terminés, travail restant, moyenne des meilleurs pourcentages corrigés par quiz et historique chronologique. Les résultats non corrigés sont exclus des statistiques de score. Ces pourcentages ne mesurent pas exactement la maîtrise entre quiz différents.
- **PDF des notes** : export par quiz pour son enseignant et l’administrateur, inscrits actuels et anciens inscrits séparés, zéro distingué d’une absence de participation. La lecture et l’export projettent les tentatives expirées sans modifier les réponses ou notes en base.
- **Retour facultatif** : après une tentative terminée, appréciation et commentaire de 1 000 caractères maximum ; un retour modifiable par étudiant et quiz. Les autres étudiants ne peuvent pas le consulter. Le texte est affiché sans interprétation HTML.
- **FR / EN / AR** : sélecteur persistant, dictionnaires fixes, RTL, dates et nombres localisés. Le contenu pédagogique conserve sa langue ; aucun appel Ollama pour traduire l’interface.

## Installation et migrations

Installer `backend/requirements.lock` puis lancer `python backend/manage.py migrate --noinput` avec l’environnement du projet. Les migrations additives `0005_quiz_opening_closing_dates` et `0006_student_quiz_feedback` préservent les objets existants. Elles sont appliquées sur la base locale de développement.

L’export utilise fpdf2 et HarfBuzz, avec les polices Noto livrées sous licence OFL dans `backend/quizzes/fonts`. Le frontend charge sa police arabe locale. PyMuPDF dans `backend/requirements-dev.txt` sert uniquement à inspecter les PDF pendant les vérifications.

## Pages

- Étudiant : `/espace/etudiant`, `/espace/quiz`, `/espace/tentatives` ; retour sous la correction `/espace/tentatives/<id>/resultat`.
- Enseignant : `/espace/quiz/<id>/modifier` pour les dates en brouillon, `/espace/quiz/<id>/resultats` pour notes PDF et retours.
- Administrateur : mêmes fonctions dans `/administration/quiz/<id>/modifier` et `/administration/quiz/<id>/resultats` avec le back-office conservé.

API ajoutées : `GET /api/student/quiz-progress/`, `GET /api/quizzes/<id>/grades.pdf?lang=fr|en|ar`, `GET|PUT /api/student/quizzes/<id>/feedback/`, `GET /api/quizzes/<id>/feedback/`.

## Vérifications exécutées

- 116 tests Django du module Quiz, incluant dates/fuseaux/expiration, permissions, validations, tentatives et concurrence, progression, PDF, retours et simulation Ollama.
- `manage.py check`, `makemigrations --check --dry-run`, typage TypeScript et build React.
- Quatre parcours Chromium : CRUD et publication, passage/reprise/correction, résultats des étudiants, puis calendrier/priorités/progression/retours/PDF/FR-EN-AR. Le dernier parcourt huit pages Quiz enseignant dans les trois langues ; il contrôle également la persistance des saisies/langues, les erreurs de formulaire et le RTL mobile/tablette.
- PDF de cinq pages générés en français et en arabe, première et dernière pages inspectées visuellement : accents, noms arabes, en-têtes répétés et pagination.

Les tests navigateur créent leurs données dans des bases isolées. Rapports : `quiz-completion-browser-verification.json`, `axe-quiz-completion-ar.json` et captures `screenshots/quiz-completion-*.png`. Aucun nouvel appel réel Ollama n’a été nécessaire pour ces ajouts. Le build signale un bundle JavaScript supérieur à 500 Ko ; cette alerte ne bloque pas sa production.
