# Scénario complet — Résumés et illustrations

Parcours de démonstration de toute la gestion des fiches de révision, rôle par rôle. Chaque étape a été jouée dans le navigateur avec les vraies IA (Gemini, Hugging Face) le 26/10/2026 ; les durées indiquées sont celles mesurées.

## Préparation (5 minutes avant la démo)

1. MongoDB, Django et Vite démarrés (voir le README), Ollama lancé si le secours local est souhaité.
2. `backend/.env` contient `GEMINI_API_KEY`, `HF_TOKEN` (et `OLLAMA_MODEL=qwen3:8b` pour le secours).
3. Comptes de démonstration : un enseignant responsable d’un groupe, un étudiant inscrit dans ce groupe, l’administrateur.
4. Un support de cours au format PDF (texte, pas scanné), par exemple « Chapitre 5 — La respiration cellulaire ».
5. Ouvrir http://127.0.0.1:5173.

| Rôle | Ce qu’il peut faire |
|---|---|
| Enseignant | Créer des fiches pour ses groupes, générer avec l’IA, relire, illustrer, publier, archiver, exporter. |
| Étudiant | Lire les fiches publiées de ses groupes, les copier dans ses fiches, créer des fiches personnelles privées (IA comprise), exporter. |
| Administrateur | Voir et gérer toutes les fiches, créer une fiche au nom d’un enseignant. |

---

## Acte 1 — L’enseignant prépare une fiche avec l’IA

**1. Bibliothèque.** *Mes activités → Mes fiches de révision* (ou *Les modules → Résumés et illustrations*).
On voit le bandeau, les compteurs (fiches, publiées, brouillons, générées avec Gemini), la recherche, les filtres (cours, statut, groupe, tri) et les étiquettes cliquables.

**2. Création guidée.** Bouton **« Partir d’un cours avec Gemini »**. Étape 1 sur 3 :
- Titre : *La respiration cellulaire* · Cours : *Biologie cellulaire* · Groupe : *Biologie L1 — Groupe A*
- Couleur : Rose · Étiquette : `chapitre-5` (Entrée pour valider)
- **« Continuer vers Gemini → »**. La fiche est créée en brouillon et la fenêtre Gemini s’ouvre.

**3. Génération Gemini depuis un PDF.** Onglet **« Importer un fichier »** → déposer le PDF du chapitre → niveau *Standard* → **« Lancer la génération »**.
La requête répond immédiatement (202) : un bandeau de progression avec chronomètre s’affiche et la génération continue en arrière-plan (worker Celery). La fiche se met à jour toute seule à la fin.
➜ Résultat en **~19 s** : résumé structuré en parties, 9 points clés, glossaire de 8 notions, étiquettes proposées (`#atp`, `#mitochondrie`…) et une idée d’illustration.

**4. Relecture obligatoire.** Un bandeau violet indique *« Contenu généré par l’IA — relecture requise »*, avec le modèle, la date et la source. Le panneau *« Avant de publier »* bloque la publication.
L’enseignant vérifie le contenu puis clique **« J’ai relu ce contenu »**. Le badge passe de *IA · à relire* à *IA · relue*.

> Point à souligner devant le jury : aucun contenu généré n’atteint les étudiants sans validation humaine. C’est contrôlé par le serveur, pas seulement par l’interface.

**5. Illustration générée (Hugging Face).** Bouton flottant **Studio IA** → **« Créer une illustration »** (ou *Générer avec Hugging Face* dans la galerie).
La description est préremplie avec l’idée proposée par Gemini. Choisir un style (schéma, flat design, réaliste, aquarelle) et saisir la **description accessible** (obligatoire, pour les lecteurs d’écran) → **« Générer l’image »**.
➜ Image FLUX.1-schnell ajoutée en **~5 s**, avec un badge *IA*.

**6. Illustration importée.** **« Importer »** → glisser une image PNG/JPEG/WebP (8 Mo max) → description → **« Ajouter à la fiche »**. L’image est vérifiée, redimensionnée et convertie en WebP.

**7. Organiser les illustrations.** Flèches ← → pour réordonner, crayon pour modifier la légende, corbeille pour supprimer (avec confirmation). Cliquer sur une image l’agrandit (navigation précédente / suivante).

**8. Retouches manuelles.** **« Modifier »** : titre, cours, couleur, étiquettes, résumé (onglets *Rédiger* / *Aperçu*), points clés (ajouter, monter, descendre, supprimer), glossaire. Quitter sans enregistrer déclenche un avertissement. **« Enregistrer les modifications »**.

**9. Organiser la bibliothèque.** L’épingle place la fiche en tête de liste et dans le filtre *Épinglées*.

**10. Publier.** **« Publier »** → confirmation. La fiche passe en *Publiée*, visible par les étudiants inscrits du groupe.

**11. Exporter.**
- **« Markdown »** télécharge `fiche-la-respiration-cellulaire.md` (résumé, points clés, glossaire, légendes, mention de l’IA).
- **« Imprimer / PDF »** produit une version A4 propre : navigation masquée, illustrations incluses.

---

## Acte 2 — L’étudiant révise

**12. Fiches partagées.** Connexion étudiant → *Fiches de révision* → onglet **« Partagées par mes enseignants »**. Seules les fiches *publiées* des groupes où il est **actuellement inscrit** apparaissent. Les brouillons restent invisibles.

**13. Lecture.** Résumé mis en forme, encadré *À retenir* numéroté, glossaire, illustrations agrandissables, mention *« Rédigé avec l’aide de gemini-3.5-flash, relu par … »*. Aucun bouton de modification. Il peut exporter ou imprimer.

**14. « Ajouter à mes fiches ».** Crée une **copie personnelle** modifiable, illustrations comprises. Il la renomme *Ma fiche — respiration (examen)* et peut l’annoter. Cette copie est **privée** : ni l’enseignant ni les autres étudiants ne la voient.

**15. Fiche personnelle avec l’IA.** **« Nouvelle fiche »** (ou *Partir d’un cours avec Gemini*) : l’étudiant colle ses propres notes. Gemini les résume et Hugging Face les illustre. Une fiche personnelle ne peut jamais être publiée.

---

## Acte 3 — Cycle de vie et administration

**16. Retirer, archiver, restaurer.** Sur la fiche publiée :
- **« Repasser en brouillon »** la retire aux étudiants.
- **« Archiver »** la conserve en lecture seule : modification et génération IA sont bloquées.
- **« Restaurer en brouillon »** la rend de nouveau modifiable.

**17. Dupliquer et supprimer.** **« Dupliquer »** crée une copie en brouillon, illustrations comprises. **« Supprimer »** est définitif et efface aussi les images. Une fiche publiée doit d’abord être retirée.

**18. Filtres.** Cliquer sur `#chapitre-5` dans la bibliothèque n’affiche plus que les fiches de ce chapitre. Le filtre se combine avec la recherche, le cours, le statut et le groupe.

**19. Administrateur.** *Administration → Fiches de révision* : toutes les fiches de tous les enseignants, avec un filtre par enseignant. Il peut tout gérer et créer une fiche au nom d’un enseignant.

---

**Bonus jury — Pilotage IA.** Administration → *Pilotage IA* : métriques mesurées (couverture, compression, structure, notes, relecture), latences p50/p95 par moteur et journal. Le rapport de la campagne d’évaluation est dans `docs/AI-EVALUATION.md`.

## Robustesse à montrer (optionnel)

| Situation | Comportement |
|---|---|
| Gemini surchargé (503) ou limite atteinte (429) | Deux nouvelles tentatives automatiques, puis bascule sur le modèle local **Ollama qwen3:8b** (~45-65 s). Le message l’indique et la fiche garde le nom du modèle utilisé. |
| Aucune clé configurée | Le module fonctionne en saisie manuelle ; les boutons IA expliquent comment configurer. |
| PDF scanné (sans texte), fichier non pris en charge | Message clair, aucun appel IA consommé. |
| Quota GPU Hugging Face du jour atteint | Message *« quota GPU gratuit atteint »* ; l’import d’images reste possible. |
| Trop de générations | Limite par utilisateur : 20 résumés et 12 illustrations par heure. |
| Accès direct à l’URL d’une fiche d’un autre enseignant ou d’une image privée | Réponse « introuvable » (404), sans divulgation. |

## Résultats mesurés lors de la répétition

| Étape | Durée |
|---|---|
| Résumé Gemini 3.5 Flash depuis un PDF (niveau Standard) | 19 s |
| Illustration FLUX.1-schnell (Space Hugging Face) | 5 s |
| Résumé de secours Ollama qwen3:8b (niveau Synthétique) | 47 à 63 s |
| Tests automatisés du module | 23 tests, tous réussis |
