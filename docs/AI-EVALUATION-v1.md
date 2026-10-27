# Évaluation de l’IA — Résumés et illustrations

Mesures réelles produites par `manage.py evaluate_ai` le 26/10/2026 à 16:53 (résumés « STANDARD », traitement des tâches identique à la production). Relancer la commande régénère ce rapport.

## Configuration

- Résumés : `gemini-3.5-flash` ; secours local : `qwen3:8b`
- Illustrations : `black-forest-labs/FLUX.1-schnell` (Hugging Face)
- Corpus : 6 extraits de cours (Biologie, Informatique, Histoire, Physique, Économie, Chimie), 3 illustrations

## Synthèse

| Indicateur | Valeur |
|---|---|
| Résumés réussis | 6 / 6 (100 %) |
| Recours au secours Ollama | 0 |
| Durée de génération — médiane / p95 / max | 19.2 s / 34.0 s / 34.0 s |
| Couverture des mots-clés (moyenne) | 97 % |
| Taux de compression (moyenne) | 90 % |
| Conformité de structure (moyenne) | 80 % |
| Illustrations réussies | 3 / 3 |
| Durée illustration — médiane / max | 14.4 s / 21.0 s |

## Détail par cours

| Matière | Cours | Statut | Moteur | Durée | Mots source → résumé | Compression | Couverture | Structure | Points clés | Glossaire | Mots-clés manquants |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Biologie | La photosynthèse | SUCCEEDED | gemini | 34.0 s | 176 → 178 | 101 % | 100 % | 80 % | 9 | 9 | — |
| Informatique | Les algorithmes de tri | SUCCEEDED | gemini | 29.4 s | 201 → 186 | 92 % | 100 % | 80 % | 8 | 8 | — |
| Histoire | La révolution industrielle | SUCCEEDED | gemini | 24.4 s | 171 → 111 | 65 % | 93 % | 80 % | 8 | 6 | designe |
| Physique | Les lois de Newton | SUCCEEDED | gemini | 17.7 s | 176 → 146 | 83 % | 93 % | 80 % | 9 | 6 | fondent |
| Économie | L’inflation | SUCCEEDED | gemini | 16.6 s | 187 → 136 | 73 % | 93 % | 80 % | 7 | 6 | causes |
| Chimie | Les réactions acido-basiques | SUCCEEDED | gemini | 19.2 s | 199 → 256 | 129 % | 100 % | 80 % | 8 | 8 | — |

## Illustrations

| Style | Statut | Durée | Attente |
|---|---|---|---|
| SCHEMA | SUCCEEDED | 14.4 s | 0.0 s |
| WATERCOLOR | SUCCEEDED | 12.6 s | 0.0 s |
| FLAT | SUCCEEDED | 21.0 s | 0.0 s |

## Méthode et lecture des indicateurs

Un résumé génératif n’a pas de « bonne réponse » unique : précision, rappel ou F1 ne s’appliquent pas directement. La qualité est donc estimée par des indicateurs reproductibles, complétés par les signaux humains collectés dans l’application.

- **Couverture des mots-clés** : part des 15 termes les plus fréquents du cours (hors mots outils, 5 lettres minimum) retrouvés dans le résumé, les points clés ou le glossaire, avec tolérance aux flexions (préfixe de 6 lettres). C’est un rappel des notions essentielles.
- **Compression** : nombre de mots du résumé divisé par celui du cours. Une valeur inférieure à 100 % indique une vraie synthèse. Pour des extraits courts comme ce corpus, la longueur « Standard » peut s’en approcher.
- **Conformité de structure** : moyenne de cinq contrôles (sections titrées, nombre de points clés attendu, glossaire présent, longueur dans la cible à ±25 %, idée d’illustration).
- **Signaux humains** (tableau de bord *Pilotage IA*) : note de pertinence de 1 à 5 donnée par l’auteur, et taux de contenus relus avant publication (relecture obligatoire).
- **Performance** : la requête HTTP répond en environ 0,2 s (202 Accepted) ; la génération s’exécute dans un worker Celery (Redis) ou dans la file de tâches intégrée, et l’interface suit la tâche par interrogation régulière.

Limites : corpus réduit (6 cours) ; les mots-clés fréquents ne capturent pas toutes les notions ; les durées dépendent de la charge des services externes au moment de la mesure.
