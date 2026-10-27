# Finition visuelle du module Quiz

Travail effectué dans `.local/publication`, branche `Syrine`, sans commit, push ou fusion.

La direction conserve le violet, le bleu nuit, les polices et les icônes Eduleb. Les surfaces restent sobres, avec des bordures discrètes, des ombres légères et des espacements réguliers. Les titres, filtres, métadonnées et actions suivent la même hiérarchie dans le front-office et les écrans Quiz du back-office.

## Changements

- `frontend/src/quizzes/quiz.css` : tokens limités au module ; cartes sans description tronquée ; champs, aides, erreurs, badges et actions harmonisés ; réponses sélectionnées et focus différenciés ; chronomètre en flux normal ; tableaux dans leur conteneur défilant ; RTL et réduction des animations respectés.
- `AttemptResult.tsx` et `StudentResultDetail.tsx` : classes visuelles pour les réponses correctes, incorrectes et absentes. Les libellés explicites existants restent présents en complément de la couleur.
- `Progress.tsx`, `Feedback.tsx` et `StudentResults.tsx` : classes pour les statistiques, retours et alignements numériques des tableaux.
- `frontend/tests/quiz-visual.spec.ts` : parcours de vérification visuelle reproductible.

La comparaison syntaxique des composants avant/après, en ignorant uniquement les attributs `className`, confirme que leurs événements, contenus et expressions fonctionnelles sont identiques. Les hashes des autres sources sont inchangés : backend, routes, sessions, validations, calculs, traductions et génération PDF. Les règles CSS globales déjà présentes, dont celles du header/footer et des langues, sont conservées à l’identique. Preuve : [source-integrity.json](quiz-visual/source-integrity.json).

## Vérifications exécutées

- Typage TypeScript et build React réussis via `npm run build`.
- 135 combinaisons : 15 vues Quiz × FR/EN/AR × 390/768/1440 px, avec les rôles étudiant, enseignant et administrateur. Aucun débordement horizontal de page détecté.
- 13 analyses axe, sans violation détectée, sur des formulaires, passages, corrections, résultats et propositions IA.
- Contrôles des états sélectionné, focus au clavier, erreur de saisie, chargement et désactivé ; sauvegarde après sélection au clavier ; `prefers-reduced-motion`.
- Reflow équivalent à un zoom navigateur de 200 %, en FR et AR : contexte Chromium avec une largeur de 720 pixels CSS et une densité de 2 pour une image de 1440 pixels. Il s’agit d’une émulation, pas d’une action sur le menu de zoom d’un navigateur installé.
- Cinq parcours existants réussis : `quizzes`, `attempts`, `student-results`, `quiz-completion`, `generation`. Les données sont créées dans des bases isolées. Le fournisseur IA est simulé pour les propositions ; aucun appel réel Ollama n’est nécessaire à cette intervention.
- Inspection visuelle des captures : listes, formulaires Quiz/Question, passage, correction, progression, résultats enseignants et génération, en desktop et mobile, dont l’arabe RTL.

Rapports : [vérification visuelle](quiz-visual/after/verification.json), [parcours fonctionnels](quiz-visual/regression-results.json).

## Captures avant / après

| Écran | Avant | Après |
|---|---|---|
| Liste enseignant, français, desktop | [Avant](quiz-visual/before/teacher-list-fr-1440.png) | [Après](quiz-visual/after/teacher-list-fr-1440.png) |
| Formulaire Quiz, français, desktop | [Avant](quiz-visual/before/teacher-quiz-form-fr-1440.png) | [Après](quiz-visual/after/teacher-quiz-form-fr-1440.png) |
| Passage étudiant, arabe, mobile | [Avant](quiz-visual/before/student-attempt-ar-390.png) | [Après](quiz-visual/after/student-attempt-ar-390.png) |
| Correction étudiante, français, desktop | [Avant](quiz-visual/before/student-correction-fr-1440.png) | [Après](quiz-visual/after/student-correction-fr-1440.png) |
| Résultats enseignant, français, desktop | [Avant](quiz-visual/before/teacher-results-fr-1440.png) | [Après](quiz-visual/after/teacher-results-fr-1440.png) |

Captures supplémentaires : [formulaire Question](quiz-visual/after/teacher-question-form-fr-1440.png), [progression](quiz-visual/after/student-progress-fr-1440.png), [propositions IA en arabe](quiz-visual/after/generation-proposals-ar-390.png), [focus clavier](quiz-visual/after/attempt-keyboard-selected-focus.png), [validation](quiz-visual/after/form-validation-focus.png), [chargement](quiz-visual/after/generation-loading-disabled.png).

La vérification automatisée concerne Chromium et ne constitue pas une certification WCAG complète. Aucun test backend n’a été relancé pour ce changement de présentation. Le build conserve l’avertissement préexistant concernant un bundle JavaScript supérieur à 500 Ko ; il se termine correctement.
