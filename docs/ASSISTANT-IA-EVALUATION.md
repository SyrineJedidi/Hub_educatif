# Évaluation de l’assistant pédagogique

Mesures du 27/10/2026, fournisseur Gemini réel, jeu de 20 questions (`backend/assistant/evaluation/demo_dataset.json`) : 15 questions couvertes par trois notes de cours et 5 questions hors cours.

Commande : `python manage.py seed_assistant_demo --group EVALIA` puis `python manage.py evaluate_assistant --scope EVALIA --pause 2`.

_Évaluation de l’assistant — Évaluation de l’assistant (gemini gemini-3.5-flash-lite, seuil 1.0)_

## Indicateurs

| Indicateur | Valeur | Lecture |
|---|---|---|
| Bonne source en premier (hit@1) | 100 % | l’extrait attendu est le premier cité |
| Sources retrouvées (hit@5) | 100 % | l’extrait attendu figure parmi les 5 sources |
| Refus hors cours corrects | 100 % | question hors cours refusée sans appeler le modèle |
| Refus à tort | 0 | question du cours refusée par erreur |
| Appels au modèle | 15 ; échecs : 0 |  |
| Latence p50 / p95 | 1125 / 1780 ms | temps de réponse médian et 95e centile |
| Jetons | 9390 en entrée, 2449 en sortie | coût mesuré du jeu complet |

## Détail

| Statut | Question | Source | Score | Latence |
|---|---|---|---|---|
| COMPLETE | Qu’est-ce qu’une fonction affine ? | source OK | 4.5694 | 1328 ms |
| COMPLETE | Comment calculer le coefficient directeur d’une droite à partir de deux points ? | source OK | 11.191 | 1155 ms |
| COMPLETE | Quand une fonction affine est-elle croissante ? | source OK | 7.6667 | 1047 ms |
| COMPLETE | Où lit-on l’ordonnée à l’origine sur le graphique ? | source OK | 12.6603 | 1077 ms |
| COMPLETE | Comment trouver la racine de ax + b ? | source OK | 7.0765 | 1078 ms |
| COMPLETE | Qu’appelle-t-on l’univers d’une expérience aléatoire ? | source OK | 11.5963 | 1030 ms |
| COMPLETE | Comment calculer une probabilité quand les issues sont équiprobables ? | source OK | 7.8789 | 1297 ms |
| COMPLETE | Quelle est la probabilité de l’événement contraire ? | source OK | 8.2208 | 1125 ms |
| COMPLETE | Quelle formule donne la probabilité de la réunion de deux événements ? | source OK | 9.241 | 1077 ms |
| COMPLETE | Que dit la loi des grands nombres ? | source OK | 8.2335 | 953 ms |
| COMPLETE | D’où vient le dioxyde de carbone présent dans l’atmosphère ? | source OK | 5.1777 | 1046 ms |
| COMPLETE | Comment fonctionne l’effet de serre ? | source OK | 4.2171 | 1328 ms |
| COMPLETE | Quels sont les principaux gaz à effet de serre ? | source OK | 8.9818 | 1780 ms |
| COMPLETE | Que montre la courbe de Keeling ? | source OK | 4.7575 | 1328 ms |
| COMPLETE | Pourquoi les océans deviennent-ils plus acides ? | source OK | 3.8283 | 1375 ms |
| OUT_OF_SCOPE | Qui a écrit Les Misérables ? | hors cours | None | 0 ms |
| OUT_OF_SCOPE | Quelle est la capitale de l’Australie ? | hors cours | None | 0 ms |
| OUT_OF_SCOPE | Comment conjuguer le verbe aller au futur ? | hors cours | None | 0 ms |
| OUT_OF_SCOPE | Quel est le meilleur joueur de football de l’histoire ? | hors cours | None | 0 ms |
| OUT_OF_SCOPE | Donne-moi une recette de couscous. | hors cours | None | 0 ms |

Les questions hors cours sont écartées par la recherche (aucun extrait au-dessus de `ASSISTANT_MIN_SCORE`) : elles ne consomment pas de quota et ne peuvent pas produire de réponse inventée.
