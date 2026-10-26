# Contrôles de saisie Quiz–Question

Les formulaires de création, modification et duplication partagent les mêmes validations. Tous les champs éditables affichés sont obligatoires. Les enseignants utilisent le front-office Eduleb et l’administrateur les mêmes formulaires métier dans le back-office. Aucun champ « notion » n’existe dans ces formulaires et aucun n’a été ajouté.

Les champs sont vérifiés à la sortie du champ et lors de l’enregistrement, puis les erreurs sont actualisées pendant la correction de la saisie. Les erreurs françaises sont reliées aux champs avec `aria-describedby` et `aria-invalid`. Le focus revient sur la première erreur. Une saisie invalide détectée par React n’envoie aucune requête d’écriture ; les erreurs Django restent associées aux champs sans effacer les valeurs. Le verrou de soumission partagé empêche les doubles écritures, y compris pendant une requête retardée. Les autres formulaires conservent leur fonctionnement.

| Champ | Règle |
| --- | --- |
| Titre | Obligatoire, espaces seuls refusés, 50 caractères maximum |
| Description | Obligatoire, 2 000 caractères maximum |
| Enseignant, administrateur uniquement | Enseignant actif sélectionné dans la liste |
| Groupe pédagogique | Groupe actif autorisé, affecté à l’enseignant sélectionné |
| Niveau | Choix obligatoire : facile, intermédiaire ou difficile |
| Durée | Choix explicite entre « Durée limitée » avec un entier de 1 à 2 147 483 647 minutes, ou « Sans limite de temps » représenté par `null` |
| Tentatives autorisées | Entier de 1 à 10 |
| Énoncé | Obligatoire, espaces seuls refusés, 2 000 caractères maximum |
| Propositions A, B, C, D | Toutes obligatoires, 500 caractères maximum chacune, différentes après normalisation des espaces et de la casse |
| Bonne réponse | Exactement une réponse parmi A, B, C et D |
| Explication | Obligatoire dès l’enregistrement du brouillon |
| Points | Entier de 1 à 10 |
| Position | Entier positif, maximum 2 147 483 647, unique dans le quiz |

Les décimales, booléens, valeurs hors bornes et chaînes numériques en notation scientifique sont refusés par les serializers Django. Les champs texte attendent du texte : les nombres ou objets JSON ne sont pas convertis silencieusement en titre ou proposition. Les références de groupe/enseignant invalides ou inexistantes produisent une erreur de champ. Les valeurs numériques entières envoyées sous forme de chaîne restent acceptées pour compatibilité API.

À la création, omettre `duration_minutes` provoque une erreur ; transmettre explicitement `null` choisit la durée illimitée. Le formulaire neuf ne préselectionne aucune durée. Un PATCH conserve les champs non transmis puis valide l’état final complet de l’objet. La position reste attribuée automatiquement à la création si elle est omise. L’auteur, le statut, le quiz parent et les dates sont contrôlés côté serveur. Les accents, apostrophes, symboles et extraits de code restent autorisés.

La publication revalide les règles métier et les explications. Les brouillons restent les seuls éléments modifiables et supprimables ; la suppression demande une confirmation. Publication, archivage, duplication et réordonnancement restent des actions dédiées. Une copie valide respecte aussi la limite de titre, sans changer l’original. Une ancienne question invalide empêche sa duplication avec une erreur explicite et un rollback complet, sans copie partielle. L’archivage et le passage des quiz existants sont préservés.

La migration `quizzes.0003_alter_question_explanation_alter_quiz_description_and_more` ajuste les règles des champs sans réécrire les données MongoDB. Les cinq enregistrements Quiz/Question présents avant la migration ont été comparés par empreinte et sont inchangés.

La commande en lecture seule `python backend/manage.py audit_quiz_inputs --json` signale les anciennes données non conformes. Le [rapport local](quiz-required-inputs-legacy.json) indique un quiz avec un titre de 55 caractères. Il n’a été ni raccourci, ni supprimé. L’utilisateur doit corriger les champs signalés avant d’enregistrer une modification ; aucun texte n’est inventé pour compléter une ancienne description ou explication.

## Vérification

La suite ciblée `python backend/manage.py test quizzes --noinput` réussit ses 61 tests, dont les tentatives existantes. Les tests couvrent les valeurs absentes, nulles, vides ou composées d’espaces, les bornes de longueur, les nombres invalides, les choix dupliqués, les groupes non autorisés/archivés en création et modification, les PATCH partiels, l’audit en lecture seule et la duplication transactionnelle. Le test de groupes a aussi été relancé après ajout des assertions PATCH. `manage.py check` et `makemigrations --check --dry-run` ne signalent aucun problème ; le typage TypeScript et le build React réussissent.

## Visibilité selon le statut

| Statut choisi par l’enseignant | Enseignant propriétaire | Administrateur | Étudiants actuellement inscrits dans le groupe ciblé | Autres étudiants ou enseignants |
| --- | --- | --- | --- | --- |
| Brouillon | Visible | Visible | Masqué | Masqué |
| Publié | Visible | Visible | Présentation et passage autorisés ; correction après soumission ou expiration | Masqué |
| Archivé | Visible | Visible | Masqué | Masqué |

L’enregistrement conserve le quiz en brouillon. La publication est une action dédiée depuis la prévisualisation après validation du contenu. L’archivage d’un quiz publié le masque immédiatement aux étudiants sans supprimer ses questions. La duplication d’un publié ou archivé crée un nouveau brouillon privé. Ces règles sont appliquées sur les listes et détails API ; une URL directe ne contourne pas la visibilité.

Le parcours navigateur `frontend/tests/quiz-validation.spec.ts` contrôle les erreurs, l’absence de requête d’écriture pour les données invalides, le focus, la correction puis l’enregistrement, une position occupée refusée par le serveur avec conservation des saisies, les formulaires administrateur/enseignant et le rendu mobile. Le scénario complet de conception/publication/consultation/duplication/archivage est également relancé dans `quizzes.spec.ts`.

Les trois parcours ciblés `quiz-validation.spec.ts`, `quizzes.spec.ts` et `attempts.spec.ts` réussissent : validation des formulaires, cycle de vie et passage/correction avec sauvegardes coordonnées. La suite générale n’a pas été relancée. Résultats : [quiz-required-inputs-verification.json](quiz-required-inputs-verification.json) et [quiz-required-inputs-browser-results.json](quiz-required-inputs-browser-results.json). [Capture mobile](screenshots/quiz-validation-mobile.png). Le contrôle axe ciblé ne détecte pas de violation ; il ne constitue pas un audit humain complet d’accessibilité.

Le travail reste local sur `feature/quiz-progression`, dans `.local/publication`, sans commit, push ni fusion. Le compte administrateur local n’est pas modifié par ces validations.
