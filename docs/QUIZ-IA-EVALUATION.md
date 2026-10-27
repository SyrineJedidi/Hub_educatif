# Évaluation de la génération de questions (Quiz et progression)

Mesures du 27/10/2026 à 03:12, modèle local `qwen3:8b` (Ollama), 3 questions demandées par cours, corpus fixe de 3 cours.
Commande : `python manage.py evaluate_quiz_generation`.

## Indicateurs

| Indicateur | Valeur | Lecture |
|---|---|---|
| Générations réussies | 3 / 3 (100 %) | réponse complète et conforme au schéma |
| Questions valides | 9 / 9 | toutes passent les validations du quiz (4 choix distincts, réponse A–D, explication, notion) |
| Énoncés distincts | 100 % | absence de doublons dans une génération |
| Ancrage dans le cours | 78 % | part des mots de la bonne réponse présents dans le cours (indicateur d’hallucination) |
| Répartition des bonnes réponses | A 22 %, B 56 %, C 11 %, D 11 % | une répartition équilibrée évite qu’on devine la réponse |
| Temps de réponse médian | 30.1 s | appel complet à Ollama |
| Temps de réponse maximal | 51.1 s | justifie le traitement en arrière-plan |

## Détail par cours

| Matière | Cours | Résultat | Durée | Questions | Notions | Ancrage |
|---|---|---|---|---|---|---|
| Biologie | La photosynthèse | réussie | 51.1 s | 3 | 3 | 67 % |
| Informatique | Les listes en Python | réussie | 27.7 s | 3 | 3 | 69 % |
| Histoire | La Révolution française | réussie | 30.1 s | 3 | 3 | 100 % |

## Méthode

- La génération tourne en arrière-plan (Celery + Redis, ou un thread sans broker) : la requête répond 202 et la page interroge la tâche ; aucune requête HTTP ne reste bloquée pendant l’appel au modèle.
- Chaque tâche enregistre ses mesures (durée, modèle, questions valides, répartition des réponses) sans conserver le cours ni les propositions, effacés après lecture par l’enseignant.
- Les propositions restent relues par l’enseignant avant tout ajout au quiz.
