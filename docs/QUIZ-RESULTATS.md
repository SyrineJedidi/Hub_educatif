# Consultation des résultats des étudiants

La consultation réutilise `Attempt` et `Answer`, leurs scores enregistrés et l’instantané historique des questions. Aucun modèle, migration ou dépendance supplémentaire. Les nouvelles vues sont accessibles aux comptes enseignants actifs et à l’administrateur, en lecture seule.

## Pages

| Espace | Accès |
| --- | --- |
| Enseignant, résultats d’un quiz | Bouton « Résultats des étudiants » sur ses quiz ; `/espace/quiz/{quiz_id}/resultats` |
| Enseignant, tous ses quiz | `/espace/resultats-quiz` |
| Enseignant, détail des réponses | `/espace/resultats-quiz/{attempt_id}` |
| Administrateur, tous les résultats | Menu « Résultats des quiz » ; `/administration/resultats-quiz` |
| Administrateur, résultats d’un quiz | `/administration/quiz/{quiz_id}/resultats` |
| Administrateur, détail des réponses | `/administration/resultats-quiz/{attempt_id}` |

Le front-office conserve le header, le footer et les composants Eduleb, sans sidebar administrative. L’administrateur utilise son back-office existant. Les listes sont paginées et disposent d’une recherche par nom/prénom, d’un filtre par statut et d’états vides distincts. L’administrateur peut aussi filtrer par quiz, groupe et enseignant. Le tableau se défile dans son conteneur sur mobile et reste accessible au clavier.

Chaque ligne indique nom, prénom, groupe, numéro de tentative, statut, date de début et score. Les tentatives en cours affichent « En cours » sans note définitive. Une tentative soumise ou expirée affiche les points et le pourcentage. « Voir les réponses » ouvre l’instantané de la tentative avec les quatre choix, le choix enregistré de l’étudiant, la bonne réponse, le barème, les points obtenus et l’explication.

Pour une tentative encore en cours, la correction de référence est visible à l’enseignant propriétaire et à l’administrateur, sans calcul de note définitive ni points obtenus par question. Les API étudiantes restent séparées et ne transmettent pas cette correction avant la soumission ou l’expiration.

## API et permissions

| Route sous `/api/` | Méthode | Usage |
| --- | --- | --- |
| `quizzes/results/` | GET | Liste globale administrateur, ou limitée aux quiz de l’enseignant connecté |
| `quizzes/{quiz_id}/results/` | GET | Liste d’un quiz autorisé |
| `quizzes/results/{attempt_id}/` | GET | Détail d’une tentative autorisée |

Filtres : `q` (nom/prénom, ordre des mots indifférent), `status` (IN_PROGRESS, SUBMITTED, EXPIRED), `quiz`, `group`, `teacher` (administrateur uniquement), `page`. Les filtres s’appliquent après la restriction par propriétaire et ne peuvent pas élargir les droits.

Un autre enseignant obtient 404 en ciblant un quiz ou une tentative qui ne lui appartient pas. L’étudiant obtient 403 sur les routes de consultation pédagogique, y compris pour sa propre tentative ; il conserve ses API personnelles avec vérification du propriétaire et du groupe. Un compte inactif ou anonyme est refusé. Les nouvelles routes n’acceptent aucune méthode d’écriture et leurs réponses portent `Cache-Control: private, no-store`.

## Lecture seule et échéances

La consultation ne sauvegarde aucune tentative, réponse ou note et ne modifie pas la garde transactionnelle. Elle n’appelle pas les fonctions de soumission ou de finalisation.

Lorsqu’une tentative stockée en cours a dépassé son échéance, la vue présente l’état « Expirée », sa date d’échéance et le résultat calculé à partir des réponses enregistrées et de l’instantané, sans persister ce calcul. Ce calcul partage la règle de notation du passage étudiant. Les scores déjà finalisés sont lus tels qu’ils sont enregistrés. L’accès ultérieur de l’étudiant conserve son mécanisme existant de finalisation ; il n’est pas remplacé par la consultation enseignant.

Les noms des étudiants et des groupes sont issus des entités existantes. Le groupe est celui référencé par la tentative au démarrage. Les questions, choix, bonnes réponses et explications du détail proviennent de l’instantané, même si les questions sources ont été modifiées ensuite.

## Vérifications

```powershell
python backend/manage.py test quizzes --noinput
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
# Depuis frontend
npm.cmd run build
npm.cmd run test:e2e -- tests/student-results.spec.ts
```

Les tests backend vérifient les permissions par rôle et propriétaire, les filtres, la recherche, la pagination, les scores, l’absence de note en cours, les corrections historiques, les méthodes d’écriture refusées et l’égalité des données avant/après toutes les consultations, y compris après dépassement d’une échéance. Les tests du CRUD et du passage sont conservés.

Résultats exécutés : **72 tests backend du module réussis, dont 11 nouveaux tests de résultats**, contrôles Django sans problème et aucune migration manquante ; typage et build React réussis. Le parcours navigateur ciblé `student-results.spec.ts` réussit avec les deux enseignants, l’administrateur et l’étudiant. Il vérifie les filtres, les scores 3/5 (60 %) et 2/2 (100 %), l’absence de note définitive en cours, la correction expliquée, les refus d’accès directs, le défilement au clavier et l’absence de débordement horizontal de la page à 390 × 844. Aucune requête d’écriture de quiz n’est émise pendant la consultation. Les deux contrôles axe ciblés ne détectent aucune violation. La suite générale navigateur n’a pas été relancée.

| Espace | Ordinateur | Mobile |
| --- | --- | --- |
| Enseignant Eduleb | [Correction détaillée](screenshots/student-results-teacher-desktop.png) | [Liste des résultats](screenshots/student-results-teacher-mobile.png) |
| Administrateur | [Correction détaillée](screenshots/student-results-admin-desktop.png) | [Correction détaillée](screenshots/student-results-admin-mobile.png) |

Les résultats exécutés figurent dans `quiz-student-results-verification.json` et `quiz-student-results-browser-results.json`. Les bases de test sont isolées des données locales. Les captures `student-results-*` illustrent les deux espaces sur ordinateur et mobile. Les contrôles axe ciblés ne constituent pas un audit humain complet d’accessibilité.

Le travail est conservé dans `.local/publication`, sur `feature/quiz-progression`, sans commit, push ni fusion.
