# Passage des quiz et correction automatique

La consultation pédagogique des résultats pour enseignants et administrateur est décrite dans [QUIZ-RESULTATS.md](QUIZ-RESULTATS.md).

Le dépôt de travail est `C:\Users\USER\Downloads\edu\.local\publication`, branche `feature/quiz-progression`. Les changements du CRUD sont conservés. Cette étape est développée directement dans ce dépôt ; l’ancienne copie à la racine `edu` ne contient pas ces ajouts. Aucun commit, push ou merge.

## Migration et démarrage

Migration additive : `quizzes/0002_attempt_answer_and_more.py`. Elle crée les collections Tentative (`Attempt`) et Réponse (`Answer`) et leurs index uniques, sans supprimer de données. Depuis le dépôt, dans l’environnement Python existant :

```powershell
python backend/manage.py migrate
python backend/manage.py check
python backend/manage.py runserver 127.0.0.1:8000
```

Dans `frontend`, `npm.cmd run dev`. Aucune dépendance supplémentaire. MongoDB reste le même replica set, nécessaire aux transactions existantes.

Dans cet environnement, le port habituel `http://127.0.0.1:5173` et l’API 8000 utilisent désormais ce dépôt. Les points d’entrée locaux de la copie racine redirigent vers le code courant pour éviter de resservir l’ancien écran ; voir [QUIZ-ACCES.md](QUIZ-ACCES.md). Les dépendances déjà installées sont réutilisées localement ; les environnements, fichiers `.env`, journaux et identifiants restent ignorés par Git.

## Historique et correction

Une tentative conserve l’étudiant, le quiz, le groupe ciblé au démarrage, un numéro, les dates de début/échéance/fin, son statut IN_PROGRESS/SUBMITTED/EXPIRED, le total possible et les points obtenus après finalisation. Le titre et un instantané ordonné des questions, des choix, des bonnes réponses, des explications et des points restent côté serveur.

Les réponses possèdent une révision et sont uniques par tentative/question. Un index unique protège le numéro de tentative par étudiant/quiz et un index partiel interdit deux tentatives en cours pour le même étudiant et quiz. Les contraintes sont appliquées dans MongoDB ; la garde transactionnelle commune protège les départs, sauvegardes, soumissions, archivages et changements d’accès concurrents.

La correction utilise exclusivement l’instantané et les réponses enregistrées : réponse correcte = points prévus ; réponse incorrecte ou absente = zéro. Le pourcentage est calculé côté serveur. Les dates persistées sont normalisées à la précision milliseconde de MongoDB pour que les soumissions répétées conservent la même date de fin et le même résultat.

## API étudiant

Routes sous `/api/`, réservées à l’étudiant connecté et actif, avec les sessions et protections CSRF existantes.

| Route | Méthode | Usage |
| --- | --- | --- |
| `student/quizzes/{quiz_id}/attempts/` | GET | Tentatives du quiz, quota restant et tentative en cours |
| `student/quizzes/{quiz_id}/attempts/` | POST `{}` | Commencer ou reprendre |
| `student/attempts/` | GET | Historique personnel paginé, y compris les quiz archivés encore autorisés |
| `student/attempts/{attempt_id}/` | GET | Questions sans correction et réponses enregistrées |
| `student/attempts/{attempt_id}/answers/{question_id}/` | PUT | `selected_choice` A–D et `expected_revision` (0 à la première sauvegarde) |
| `student/attempts/{attempt_id}/submit/` | POST | `answer_revisions` : dictionnaire complet des identifiants de questions répondues et des révisions confirmées |
| `student/attempts/{attempt_id}/result/` | GET | Résultat et correction après soumission ou expiration |

Exemple : `{"answer_revisions":{"<question_id>":1}}`. Un dictionnaire vide soumet une tentative sans réponse si aucune réponse n’est enregistrée. Les champs client de score, statut, échéance ou identité ne sont pas acceptés pour modifier une tentative. Les questions doivent appartenir à son instantané.

Les bonnes réponses et explications ne figurent jamais dans les données de passage : les réponses API utilisent des listes explicites de champs. Un résultat demandé pendant une tentative en cours renvoie 409 sans correction. Une tentative étrangère reste inaccessible par URL directe. Les enseignants et administrateurs n’utilisent pas ces API personnelles étudiantes.

## Durée, quota et archivage

- Un nouveau départ exige un quiz publié et une inscription actuelle à son groupe actif. Les tentatives soumises et expirées comptent dans la limite ; une tentative encore en cours est reprise.
- L’échéance provient du serveur ; elle est nulle pour une durée illimitée. Le navigateur affiche une estimation avec l’heure serveur et une horloge monotone, mais ne décide jamais de l’acceptation d’une réponse.
- Au prochain accès serveur, une tentative arrivée à échéance est finalisée avec les réponses enregistrées. Une réponse tardive est refusée. Cette finalisation est conservée même si un départ ou une réponse tardive est ensuite refusé.
- L’archivage empêche les nouveaux départs. Une tentative commencée reste accessible jusqu’à l’échéance si les droits au groupe sont conservés. Son résultat reste accessible avec les mêmes droits. L’historique permet de la retrouver même lorsque le quiz disparaît de la liste publiée.
- La fin d’inscription, une inscription future, l’archivage du groupe ou la désactivation du compte révoquent les accès concernés.

## Sauvegardes et soumission

Le frontend sérialise les sauvegardes. Une ancienne réponse réseau met uniquement à jour l’accusé de réception ; elle ne remplace jamais une sélection plus récente. « Enregistré » apparaît seulement après confirmation pour la sélection courante. Un échec conserve la sélection et propose de réessayer.

La confirmation indique les questions sans réponse. La soumission bloque les nouvelles sélections, attend les sauvegardes et transmet les révisions confirmées. Si une réponse reste non synchronisée, aucun POST de soumission n’est envoyé. Le serveur vérifie aussi ce manifeste : une modification depuis une autre fenêtre bloque la soumission et demande de recharger. Une sauvegarde ancienne ne peut pas écraser une révision plus récente. Un accusé de réception perdu peut être rejoué sans modifier une réponse déjà confirmée ; une soumission répétée renvoie le résultat existant.

En cas d’expiration pendant une sauvegarde, seules les réponses effectivement enregistrées à temps sont corrigées. Le résultat l’indique explicitement. Aucune réponse locale non confirmée n’est présentée comme soumise.

## Pages Eduleb

| Page | Route |
| --- | --- |
| Présentation, Commencer/Reprendre et historique du quiz | `/espace/quiz/{quiz_id}` |
| Mes tentatives, reprise des quiz archivés et corrections | `/espace/tentatives` |
| Passage | `/espace/tentatives/{attempt_id}` |
| Résultat et correction | `/espace/tentatives/{attempt_id}/resultat` |

Ces pages partagent le header et le footer Eduleb, sans sidebar administrative. Elles réutilisent les dialogues, messages, boutons et cartes existants. Les radios sont accessibles au clavier et les sauvegardes disposent d’états annoncés. Aucun design global n’est remplacé.

## Vérifications ciblées

```powershell
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test quizzes --noinput
# Dans frontend
npm.cmd run build
npx.cmd playwright test tests/attempts.spec.ts tests/quizzes.spec.ts
```

Les tests backend couvrent le CRUD et les tentatives : confidentialité, accès, sauvegarde/reprise, notation, instantané historique, durée illimitée, échéance exacte, expiration après fermeture du navigateur, quotas, index uniques réels, départs concurrents, double soumission et concurrence sauvegarde/soumission. Les bases de test sont isolées des données de développement.

Résultats de cette livraison : 55 tests backend du module réussis (33 CRUD et 22 tentatives), contrôles Django sans problème, aucune migration manquante, typage et build React réussis, deux tests navigateur ciblés réussis. La suite générale des sept scénarios navigateur n’a pas été relancée. Les lectures ordinaires des tentatives ne modifient pas la garde transactionnelle ; seules les expirations à finaliser prennent cette garde, ce qui permet le rechargement par lectures simultanées.

Le parcours navigateur retarde une sauvegarde pour vérifier la conservation du choix récent, simule une panne et une reprise, recharge la page puis confirme la soumission pendant qu’une réponse attend son accusé de réception. Il vérifie que la soumission attend cet accusé avant de calculer 5/6 points (83,33 %), puis reprend une tentative après archivage depuis l’historique.

Une panne persistante pendant la confirmation laisse également la tentative en cours, avec une erreur explicite et une sélection conservée. Deux contrôles axe ciblés (passage et correction) ne détectent aucune violation ; affichage mobile à 390 × 844 sans débordement horizontal, radios manipulées au clavier et captures inspectées visuellement.

Résultats exécutés : `quiz-attempt-verification.json` et `quiz-attempt-browser-results.json`. Captures : `screenshots/quiz-attempt-*` et `quiz-result-mobile.png`. Les contrôles axe de ces pages ne constituent pas un audit humain complet d’accessibilité.

Pas de Gemini, mélange aléatoire, correction différée ni statistiques avancées dans cette étape.
