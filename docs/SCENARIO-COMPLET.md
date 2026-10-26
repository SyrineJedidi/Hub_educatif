# Scénario de test complet — Hub Éducatif Nexora

Parcours étape par étape de toute l’application avec les données de démonstration. Chaque étape indique **où cliquer** et **le résultat attendu** (✅). Les valeurs chiffrées correspondent à l’état initial créé par `seed_demo`.

Durée : environ 45 minutes en entier, ou 10 minutes en suivant uniquement les étapes marquées ⭐.

---

## 0. Préparation

### Démarrer l’application

Trois terminaux PowerShell, depuis la racine du projet :

```powershell
# 1. MongoDB (replica set nexora sur 127.0.0.1:27019)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Start-Mongo.ps1   # ou, avec Docker : docker start nexora-mongo
# 2. Django
.\backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
# 3. React
Set-Location frontend; npm.cmd run dev
```

Pour le traitement asynchrone de l’IA (recommandé pour la démonstration), deux terminaux de plus :

```powershell
# 4. Redis (file de messages)
docker start nexora-redis    # ou, la première fois : docker run -d --name nexora-redis -p 127.0.0.1:6379:6379 redis:7-alpine
# 5. Worker Celery (depuis backend\)
.\.venv\Scripts\celery.exe -A config worker --pool=solo --loglevel=info
```

Sans Redis, laissez `CELERY_BROKER_URL` vide : les générations utilisent la file intégrée, avec le même comportement. Facultatif : lancer Ollama (`ollama serve`) pour le secours local des résumés.

### Charger les données de test

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py migrate
.\backend\.venv\Scripts\python.exe backend\manage.py seed_demo --password "Nexora-Test-2026"
```

La commande peut être relancée sans créer de doublons. Pour revenir à l’état initial après avoir joué le scénario, videz la base de développement puis relancez `migrate` et `seed_demo`.

Ouvrir **http://127.0.0.1:5173**.

### Comptes (mot de passe commun : `Nexora-Test-2026`)

| Compte | Rôle | Situation |
|---|---|---|
| `admin@demo.nexora.test` | Administrateur | Gère toute la plateforme |
| `enseignant@demo.nexora.test` | Enseignant — Amel Ben Salah | Responsable de BIO-L1 et du groupe archivé CHIM-2025 |
| `enseignant2@demo.nexora.test` | Enseignant — Karim Haddad | Responsable de INFO-L2 |
| `etudiant@demo.nexora.test` | Étudiant — Yassine Trabelsi | Inscrit en BIO-L1 |
| `etudiante2@demo.nexora.test` | Étudiante — Salma Gharbi | Inscrite en BIO-L1 **et** INFO-L2 |
| `etudiant3@demo.nexora.test` | Étudiant — Mehdi Jlassi | Inscrit en INFO-L2 |
| `etudiant.sans.groupe@demo.nexora.test` | Étudiante — Ines Ferchichi | Aucun groupe |
| `ancien.etudiant@demo.nexora.test` | Étudiant — Omar Mansouri | Inscription BIO-L1 terminée il y a 5 jours |

### Données disponibles

| Module | Contenu |
|---|---|
| Groupes | BIO-L1 (3 inscrits dont 1 ancien), INFO-L2 (2 inscrits), CHIM-2025 (archivé) |
| Séances | 9 : 5 terminées avec appel validé, 1 passée **sans appel** (*Cours 3 — La respiration cellulaire*, hier), 1 annulée, 2 à venir |
| Quiz | *Photosynthèse — les bases* (publié, 10 min, 2 tentatives), *La cellule eucaryote* (brouillon), *Écologie — session 2025* (archivé), *Algorithmes de tri* (publié, sans limite, 3 tentatives) |
| Tentatives | Yassine 4/6 et Salma 6/6 en photosynthèse ; Salma 3/5 et Mehdi 4/5 en tri |
| Fiches | 8 fiches : publiées, brouillon IA à relire, brouillon vide, archivée, fiche personnelle ; 4 illustrations |

---

## Parcours A — Visiteur (sans compte)

**A1. Accueil.** Ouvrir `/`.
✅ Header Eduleb, bandeau « Vos cours prennent vie », section des cinq modules et footer.

**A2. Module protégé.** Cliquer *Les modules → Résumés et illustrations* (ou ouvrir `/modules/resumes`).
✅ Redirection vers la page de connexion.

**A3. Inscription.** *S’inscrire* : prénom, nom, email (par exemple `test.visiteur@demo.nexora.test`), rôle **Étudiant**, mot de passe d’au moins 10 caractères, confirmation.
✅ « Compte créé ». Le rôle Administrateur n’est jamais proposé.

**A4. Mot de passe oublié.** *Mot de passe oublié* → saisir un email.
✅ Message neutre (identique que le compte existe ou non). En développement, le lien de réinitialisation s’affiche dans le terminal de Django.

---

## Parcours B — Administrateur ⭐ (`admin@demo.nexora.test`)

**B1. Connexion** ⭐
✅ Redirection vers `/administration` : back-office avec barre latérale, tableau de bord, *Prochaines séances*, *Vos groupes*.

**B2. Utilisateurs.** Barre latérale → *Utilisateurs*.
✅ 9 comptes (10 si A3 a été joué). Recherche par nom ou email, filtres par rôle et statut. Le rôle ADMIN ne peut pas être attribué.

**B3. Groupes.** *Mes groupes*.
✅ 3 groupes. Le filtre *Archivés* n’affiche que CHIM-2025.
Ouvrir **BIO-L1** :
✅ Yassine et Salma en cours, Omar avec une date de sortie passée (historique conservé).

**B4. Inscrire un étudiant.** Dans BIO-L1, ajouter **Ines Ferchichi** (entrée : maintenant).
✅ Ines apparaît parmi les inscrits. *(Pensez à terminer son inscription ensuite si vous voulez garder le cas « sans groupe » pour le parcours E.)*

**B5. Séances.** *Séances*.
✅ 9 séances, dont une annulée. Le bouton *Créer une séance +* est réservé à l’administrateur.

**B6. Assiduité.** *Assiduité*.
✅ Taux global **81,8 %** : présents et retards divisés par présents, retards et absents. Les absences justifiées sont exclues du calcul. Vues *Par étudiant* et *Par séance*, export CSV.

**B7. Quiz.** *Quiz*.
✅ Les 4 quiz de tous les enseignants, filtrables par statut, niveau, groupe et enseignant.
*Résultats des quiz* :
✅ 4 tentatives soumises, avec score et correction.

**B8. Fiches de révision** ⭐ *Fiches de révision*.
✅ 8 fiches de tous les enseignants et étudiants. Le filtre *Enseignant* fonctionne.

**B9. Pilotage de l’IA** ⭐ *Pilotage IA* (barre latérale).
✅ Indicateurs (générations, taux de réussite, couverture des mots-clés, conformité de structure, note de pertinence, taux de relecture, recours au secours), générations par jour avec infobulles et tableau de données, latences p50/p95 par moteur, journal des dernières générations avec moteur, durée et statut. Le sélecteur 7 / 30 / 90 jours recalcule tout.

---

## Parcours C — Enseignant ⭐ (`enseignant@demo.nexora.test`)

### C1. Espace enseignant
✅ `/espace/enseignant` : prochaines séances, groupes, résumé d’assiduité, accès aux feuilles d’appel. Le menu *Mes activités* contient *Mes quiz*, *Mes fiches de révision*, *Mes groupes*, *Séances et feuilles d’appel* et *Assiduité de mes groupes*.

### C2. Faire l’appel ⭐
1. *Mes activités → Séances et feuilles d’appel* → **Cours 3 — La respiration cellulaire** (hier).
2. **Ouvrir la feuille d’appel ↗**.
   ✅ 2 participants, Yassine et Salma. Omar n’y figure pas : son inscription était terminée à la date de la séance.
3. **Marquer tous présents**, puis passer Salma en **En retard**.
4. **Valider la feuille ↗** → **Confirmer la validation**.
   ✅ « Feuille validée ».
5. Corriger ensuite Salma en *Présent*.
   ✅ Un **motif est obligatoire**, et la correction apparaît dans *Historique des modifications*.

### C3. Séances non saisissables
- *Cours 4 — Génétique* (à venir) : ✅ « L’appel sera disponible après le début de la séance. »
- *Sortie terrain* (annulée) : ✅ « La saisie est fermée pour cette séance annulée. »

### C4. Assiduité
*Assiduité de mes groupes*.
✅ Le taux passe de **85,7 %** à **88,9 %** après l’appel du C2.

### C5. Quiz
1. *Mes quiz*.
   ✅ 3 quiz : publié, brouillon et archivé.
2. **Créer un quiz +** : titre, description, groupe BIO-L1, niveau, durée 5 min, 1 tentative → enregistrer.
   ✅ Brouillon créé.
3. **Ajouter une question** : énoncé, propositions A–D, bonne réponse, points, explication (2 questions).
4. *Prévisualisation*, puis **Publier**.
   ✅ Publication refusée tant qu’une condition manque, avec la liste des raisons. Sinon le quiz est publié et verrouillé.
5. Ouvrir *Écologie — session 2025* (archivé) → **Dupliquer en brouillon**.
   ✅ Nouveau brouillon modifiable.
6. *Résultats des étudiants* sur *Photosynthèse — les bases*.
   ✅ Yassine 4/6, Salma 6/6, avec le détail de chaque réponse.

### C6. Fiches de révision avec l’IA ⭐
Scénario détaillé : [SCENARIO-RESUMES-ILLUSTRATIONS.md](SCENARIO-RESUMES-ILLUSTRATIONS.md). Version courte :
1. *Mes fiches de révision*.
   ✅ 5 fiches ; *La photosynthèse* est épinglée en tête.
2. **Partir d’un cours avec l’IA** (ou le bouton flottant **Créer avec l’IA**) : titre *La respiration cellulaire*, cours *Biologie cellulaire*, groupe BIO-L1 → **Continuer vers Gemini**.
3. Coller un cours (ou importer un PDF texte) → **Lancer la génération**.
   ✅ La fenêtre se ferme **immédiatement** (réponse 202) ; un bandeau violet « L’IA rédige le résumé… » affiche un chronomètre et le bouton flottant **Studio IA** indique 1 génération en cours. On peut continuer à naviguer dans la fiche.
   ✅ En 15 à 40 s, la fiche se remplit toute seule : résumé structuré, points clés, glossaire, étiquettes ; message « Résumé rédigé par Gemini en … s ». Un bandeau *relecture requise* bloque la publication.
4. Noter la pertinence (étoiles) puis **J’ai relu ce contenu**.
5. Bouton flottant **Studio IA** → **Créer une illustration** : la description est préremplie par Gemini → style + description accessible → **Lancer la création**.
   ✅ Le panneau montre la tâche *En cours* avec sa durée ; l’image FLUX apparaît dans la galerie après 10 à 20 s environ. L’activité affiche ensuite durée, couverture des mots-clés et structure de chaque génération.
6. **Importer** une image, la réordonner avec les flèches, modifier sa légende.
7. **Modifier** : ajouter un point clé → **Enregistrer les modifications**.
8. **Publier** → confirmer.
9. Exporter en **Markdown**, puis avec **Imprimer / PDF**.
10. Ouvrir *La cellule eucaryote*.
    ✅ Brouillon IA *à relire* : bouton **Publier** → refus « Confirmez la relecture… ».
11. Ouvrir *Biologie — révisions 2025* (archivée).
    ✅ Lecture seule ; **Restaurer en brouillon** disponible ; dans le Studio IA, les actions sont désactivées avec la raison affichée.
12. *Mes fiches de révision* → **Mes statistiques IA ↗**.
    ✅ Le même tableau de bord que l’administrateur, limité à ses propres générations.

---

## Parcours D — Étudiant ⭐ (`etudiant@demo.nexora.test`)

**D1. Mon espace.**
✅ Prochaines séances, groupe BIO-L1, assiduité.

**D2. Mes séances.**
✅ 6 séances de BIO-L1. Aucun bouton d’appel. Une URL `/appel` saisie à la main redirige vers la séance.

**D3. Mon assiduité.**
✅ **100 %** (présent, en retard, présent). On ne voit que ses propres lignes.

**D4. Passer un quiz** ⭐
1. *Quiz de mes groupes* → *Photosynthèse — les bases*.
   ✅ « 1 tentative(s) utilisée(s) sur 2 », tentative 1 à 4/6 avec *Voir ma correction*.
2. **Commencer le quiz**.
   ✅ Minuteur de 10 min ; chaque réponse est enregistrée automatiquement.
3. Répondre **B, C, A, B** → **Terminer ma tentative** → **Enregistrer et soumettre**.
   ✅ **6 / 6 points**, avec la correction et l’explication de chaque question.
4. Revenir au quiz.
   ✅ « 2 tentative(s) utilisée(s) sur 2 », plus de bouton *Commencer*.

**D5. Fiches de révision** ⭐
1. *Fiches de révision* → **Partagées par mes enseignants**.
   ✅ *La photosynthèse* et *Chaînes alimentaires* uniquement : les brouillons et l’archive sont invisibles.
2. Ouvrir *La photosynthèse*.
   ✅ Résumé, *À retenir*, glossaire, illustrations agrandissables, mention « relu par Amel Ben Salah ». Aucun bouton de modification.
3. **Ajouter à mes fiches** → **Créer la copie**.
   ✅ Copie personnelle modifiable, illustrations comprises.
4. **Créer avec l’IA** (bouton flottant) → titre et cours → **Continuer vers Gemini** → coller ses notes → **Lancer la génération**.
   ✅ Fiche personnelle privée ; le bouton *Publier* n’existe pas.

---

## Parcours E — Contrôles d’accès

| Étape | Compte | Action | Résultat attendu |
|---|---|---|---|
| E1 | `etudiante2` | Quiz, séances, fiches | ✅ Contenus des **deux** groupes (9 séances, 2 quiz) ; assiduité **75 %** |
| E2 | `etudiant3` | Fiches | ✅ Uniquement *Les algorithmes de tri* ; quiz de tri 4/5 |
| E3 | `etudiant.sans.groupe` | Tous les modules | ✅ Listes vides avec messages d’accueil ; seules ses propres fiches |
| E4 | `ancien.etudiant` | Séances / assiduité / quiz / fiches | ✅ 3 séances historiques et 100 % d’assiduité, mais **aucun** quiz ni fiche (inscription terminée) |
| E5 | `enseignant2` | Ouvrir l’URL d’une fiche ou d’un quiz de BIO-L1 (copiée depuis le compte `enseignant`) | ✅ « introuvable » : aucune fuite d’information |
| E6 | `etudiant` | Ouvrir `/espace/quiz/nouveau` ou `/espace/fiches/<id>/modifier` d’une fiche d’enseignant | ✅ Redirection ou « ne peut pas être modifiée » ; l’API répond 404 |
| E7 | `enseignant2` | Publier *Les structures de données* | ✅ Visible ensuite par Salma et Mehdi, **pas** par Yassine |
| E8 | Tout compte | Se déconnecter puis faire *Précédent* dans le navigateur | ✅ Retour à la connexion, aucune donnée affichée |

---

## Parcours F — Robustesse de l’IA

| Situation | Comment la provoquer | Résultat attendu |
|---|---|---|
| Gemini indisponible | Mettre `GEMINI_MODEL=modele-inexistant` dans `.env`, redémarrer le worker (ou Django sans Celery), générer | ✅ Ollama `qwen3:8b` prend le relais (45 à 130 s), message « Gemini indisponible : modèle local », moteur « Ollama (local) » dans le Studio et le Pilotage IA |
| Worker arrêté | Arrêter le worker Celery puis lancer une génération | ✅ La tâche reste *En attente* ; elle est traitée dès que le worker redémarre |
| Aucune IA configurée | Vider `GEMINI_API_KEY` et `OLLAMA_MODEL` | ✅ Message clair ; la saisie manuelle fonctionne |
| PDF scanné ou fichier `.exe` | L’importer dans la fenêtre Gemini | ✅ Refus explicite, aucun appel IA consommé |
| Image non valide | Importer un `.svg` ou un faux `.png` | ✅ « Choisissez une image PNG, JPEG ou WebP valide » |
| Génération sur une fiche publiée | Ouvrir une fiche publiée → **Studio IA** | ✅ *Résumer un cours* est désactivé avec la raison « Fiche publiée : repassez-la en brouillon… » ; l’appel API direct est refusé |

Remettez ensuite le `.env` dans son état normal et redémarrez Django.

---

## Grille de validation

| # | Fonctionnalité | OK |
|---|---|---|
| 1 | Inscription, connexion, déconnexion, mot de passe oublié | ☐ |
| 2 | Administration des utilisateurs, groupes et inscriptions | ☐ |
| 3 | Séances : à venir, passées, annulées | ☐ |
| 4 | Appel, validation, correction avec motif et historique | ☐ |
| 5 | Statistiques d’assiduité et export CSV | ☐ |
| 6 | Quiz : création, questions, publication, duplication, archive | ☐ |
| 7 | Passage d’un quiz, minuteur, soumission, correction | ☐ |
| 8 | Résultats des étudiants côté enseignant et administrateur | ☐ |
| 9 | Fiches : création, modification, organisation (épingle, filtres, étiquettes) | ☐ |
| 10 | Résumé Gemini (texte et PDF) avec relecture obligatoire | ☐ |
| 11 | Illustration Hugging Face, import, réordonnancement, légendes | ☐ |
| 12 | Publication, retrait, archivage, restauration, duplication, suppression des fiches | ☐ |
| 13 | Export Markdown et PDF | ☐ |
| 14 | Copie personnelle étudiante et fiches privées | ☐ |
| 15 | Contrôles d’accès E1 à E8 | ☐ |
| 16 | Secours Ollama et messages d’erreur IA | ☐ |
| 16 bis | Studio IA : génération en arrière-plan (202), suivi en temps réel, note de pertinence | ☐ |
| 16 ter | Pilotage IA : métriques, latences, journal (administrateur et enseignant) | ☐ |
| 17 | Affichage mobile (fenêtre réduite à 390 px) | ☐ |
