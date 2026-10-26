<div align="center">

# Nexora — Hub Éducatif Multimodal

### Vos cours prennent vie. Votre potentiel aussi.

Plateforme éducative intégrant l’intelligence artificielle pour accompagner la compréhension des cours, l’entraînement et l’organisation des révisions.

**React · Django · MongoDB · Intelligence artificielle**

Projet académique — ESPRIT · 5e année TWIN  
Équipe Nexora · 5 membres

**Statut : en cours de développement**

</div>

---

## Présentation

Le Hub Éducatif Multimodal permet de transformer des supports pédagogiques PDF et audio en ressources d’apprentissage interactives.

La plateforme vise à centraliser les cours, les résumés, les illustrations, les échanges avec un assistant pédagogique, les quiz et les plannings de révision.

## Objectifs

- Faciliter la compréhension des contenus pédagogiques.
- Réduire le temps consacré à préparer les supports de révision.
- Permettre de poser des questions par écrit ou par voix.
- Évaluer les acquis grâce à des quiz et des corrections expliquées.
- Organiser les révisions selon les objectifs et les disponibilités.
- Proposer une interface accessible, responsive et cohérente.

## Utilisateurs et rôles prévus

| Rôle | Actions principales |
|---|---|
| Étudiant | Consulter ses ressources, utiliser l’assistant, passer des quiz et organiser ses révisions. |
| Enseignant | Gérer les contenus pédagogiques, vérifier les contenus générés et suivre les résultats des étudiants. |
| Administrateur | Administrer les comptes, les rôles et les accès à la plateforme. |

Les autorisations seront contrôlées côté serveur pour chaque fonctionnalité.

## Modules fonctionnels prévus

| Module | Fonctionnalités | Intégration IA |
|---|---|---|
| Cours et ressources | Gestion des cours et chapitres, import PDF/audio, classement et recherche. | Transcription des cours audio avec Whisper. |
| Résumés et illustrations | Gestion des résumés, fiches de révision et illustrations pédagogiques. | Génération de textes avec Gemini et d’illustrations avec un modèle disponible sur Hugging Face. |
| Assistant pédagogique | Questions écrites et vocales, conversations et historique. | Réponses fondées sur les cours avec Gemini et transcription vocale avec Whisper. |
| Quiz et progression | Gestion des quiz, questions, tentatives, corrections et résultats. | Génération de questions et d’explications avec Gemini. |
| Planification et coaching | Objectifs, disponibilités, échéances et séances de révision. | Proposition de plannings personnalisés avec Gemini. |

### Fonctionnalités transversales

- Authentification et gestion des profils.
- Gestion des rôles et permissions.
- Groupes, inscriptions, séances et assiduité.
- Navigation et composants graphiques communs.

La répartition de ces tâches communes sera confirmée avec l’équipe et l’enseignant.

## Architecture prévue

- **React** : interfaces utilisateur et interactions.
- **Django et Django REST Framework** : API, validations, permissions et logique métier.
- **MongoDB** : stockage des données applicatives.
- **Stockage de fichiers** : conservation des PDF, fichiers audio et illustrations.
- **Services IA** : appels effectués depuis le backend Django.

Le frontend communique avec Django via une API REST.
Django gère l’accès aux données et aux services IA.

Le connecteur Django–MongoDB et les versions des dépendances seront documentés lors de l’initialisation technique.

## Organisation cible du dépôt

| Dossier | Contenu prévu |
|---|---|
| `frontend/` | Application React, pages et composants partagés. |
| `backend/` | Projet Django, applications métier, API et tests. |
| `docs/` | Architecture, installation, évaluation IA et déploiement. |

Cette structure sera mise en place pendant l’initialisation du projet.

## Travail en équipe

Chaque membre développe son module de bout en bout :
interface React, API Django, données, validations, tests et documentation.

| Branche prévue | Périmètre |
|---|---|
| `main` | Version commune intégrée et vérifiée. |
| `feature/cours-ressources` | Cours et ressources. |
| `feature/resumes-illustrations` | Résumés et illustrations. |
| `feature/assistant-pedagogique` | Assistant pédagogique. |
| `feature/quiz-progression` | Quiz et progression. |
| `feature/planning-coaching` | Planification et coaching. |

### Règles de contribution

1. Partir d’une version à jour de `main`.
2. Travailler sur une branche dédiée.
3. Réaliser des commits réguliers et explicites.
4. Vérifier son module et exécuter les tests concernés.
5. Ouvrir une Pull Request vers `main`.
6. Faire relire les modifications par un autre membre avant la fusion.
7. Résoudre les conflits avec les personnes concernées.

Chaque membre utilise son propre compte et sa propre identité Git.

### Exemple de création d’une branche

Depuis une copie locale du dépôt, sans modifications en attente :

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/quiz-progression
git push -u origin feature/quiz-progression
```

Si la branche existe déjà, la sélectionner au lieu de la recréer.

## Installation et démarrage

L’initialisation technique est en cours.

Après acceptation de l’invitation GitHub, chaque membre peut récupérer
l’URL HTTPS du dépôt depuis le bouton **Code**, puis le cloner :

```bash
git clone <URL_HTTPS_DU_DEPOT>
cd Hub_educatif
```

Les versions requises, les commandes d’installation, la configuration
de MongoDB et les commandes de démarrage seront ajoutées après
vérification sur la base commune.

## Configuration et secrets

- Conserver les secrets et clés API dans des variables d’environnement.
- Ne jamais publier les fichiers `.env` contenant de vraies valeurs.
- Fournir des fichiers `.env.example` sans secrets.
- Ne jamais exposer la clé Gemini dans le frontend.
- Exclure de Git les dépendances, environnements virtuels et fichiers générés.
- Conserver les fichiers de verrouillage des dépendances pour faciliter une installation reproductible.

## Qualité et validation

Les objectifs de validation comprennent :

- Des opérations CRUD fonctionnelles et des contrôles de saisie cohérents.
- Des tests unitaires et des tests d’intégration/API.
- Des vérifications explicites des permissions.
- Un rapport de couverture des tests.
- Une navigation au clavier et un focus visible.
- Des formulaires correctement étiquetés et des contrastes vérifiés.
- Une interface responsive.
- Une intégration commune et un déploiement vérifié.

Les commandes de test et les résultats seront documentés
au fur et à mesure de leur mise en place.

## Évaluation des fonctionnalités IA

Chaque intégration IA devra être accompagnée de :

- Un cas d’usage clairement défini.
- Une gestion des erreurs et des limites d’utilisation.
- Un retour visuel pendant le traitement.
- Une vérification de la pertinence des contenus générés.
- Des mesures réelles de qualité et de temps de réponse.
- Un traitement en arrière-plan si les appels sont longs.

Les questions générées pour les quiz devront être vérifiées
par l’enseignant avant publication.

## Feuille de route

- [ ] Initialiser le dépôt et les accès de l’équipe.
- [ ] Intégrer le template React et la structure Django.
- [ ] Configurer les données et l’authentification commune.
- [ ] Développer les cinq modules métier.
- [ ] Intégrer et évaluer les fonctionnalités IA.
- [ ] Vérifier les tests, la sécurité et l’accessibilité.
- [ ] Intégrer et déployer la plateforme.
- [ ] Finaliser la documentation et préparer la soutenance.

## Équipe

**Nexora — ESPRIT**

Les noms, profils GitHub et responsabilités des cinq membres seront
ajoutés après confirmation de la répartition.


