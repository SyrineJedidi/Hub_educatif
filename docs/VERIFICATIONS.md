# Vérifications de la livraison

Vérifications effectuées localement le 26 octobre 2026 dans `C:\Users\USER\Downloads\edu`. Les résultats bruts sont dans `browser-results.json`, `coverage-summary.txt`, `npm-audit.json`, `axe-*.json` et `verification-summary.json`.

| Contrôle | Résultat obtenu |
| --- | --- |
| Tests Django avec MongoDB réel, base dédiée | **34 tests, 0 échec**, dernière exécution 20,567 s |
| Couverture accounts/classrooms/attendance | **93 %** des instructions ; migrations, commandes et code de test exclus |
| `manage.py check` | Aucun problème, aucun contrôle désactivé |
| `makemigrations --check --dry-run` | Aucune modification non migrée |
| Migrations développement et navigateur | Toutes appliquées sur leurs bases distinctes |
| `npm run build` | Typage TypeScript et build Vite réussis ; 62 modules transformés |
| `npm audit` | **0 vulnérabilité signalée** dans l’arbre installé |
| Playwright Chromium | **2 tests réussis**, 58,1 s au total |
| Axe | **0 violation détectée** dans les rapports enregistrés ; contrôles supplémentaires publics réussis dans le test |
| Exceptions JavaScript non gérées | Aucune dans les parcours testés |
| Ressources publiques image/font/style/script | Aucune réponse HTTP en erreur dans le contrôle final |
| Rendu responsive | 1440×1000 et 390×844 ; pas de débordement horizontal global sur les vues contrôlées |
| Originaux | SHA-256 de `index.html` inchangé ; les assets copiés correspondent octet pour octet aux originaux |

## Parcours réellement exécutés

Le scénario navigateur crée un étudiant dans l’interface, le connecte et conserve sa session après actualisation. Un administrateur attribue TEACHER à un autre compte, crée un groupe et inscrit deux étudiants. L’enseignant crée une séance commencée, prépare « tous présents » sans écriture serveur, enregistre un brouillon puis valide après confirmation. Il corrige un statut avec un motif. L’étudiant ne voit que sa propre assiduité ; les statistiques administrateur et enseignant correspondent à la convention. Un autre enseignant et un étudiant obtiennent 403 pour les API interdites. Enfin la séance est annulée, retirée des statistiques et sa feuille reste consultable avec saisie désactivée.

Les tests backend vérifient également les liens expirés/réutilisés, l’invalidation des anciennes sessions, CSRF, restrictions d’avatar, périodes successives, participants historiques, export, et la concurrence réelle : création de séances qui se chevauchent, inscriptions concurrentes, mises à jour simultanées d’une feuille et désactivation de deux administrateurs. Les bases de développement n’ont pas servi aux fixtures de test.

## Comparaison visuelle Eduleb

Captures complètes de l’original et de React à dimensions de fenêtre identiques : `screenshots/original-desktop.png`, `react-desktop.png`, `original-mobile.png`, `react-mobile.png`. Le test fait défiler l’original avant capture pour déclencher les éléments WOW initialement invisibles. Vues complémentaires : groupe administrateur, appel enseignant, statistiques et assiduité étudiant mobile.

L’agent a inspecté les captures. Les fonds, illustrations principales, polices Jost/DM Sans, palette, sections, classes et boutons d’Eduleb sont repris. Les différences intentionnelles portent sur les textes français, la signature Nexora, les contenus fictifs remplacés par des bénéfices/rôles, les fonctions futures annoncées et la navigation React. Le contrôle de la bannière a notamment corrigé son action peu visible et rétabli la géométrie rectangulaire originale. Le contraste d’un numéro décoratif et la hiérarchie des titres du footer ont été corrigés après axe.

Il ne s’agit pas d’une identité pixel à pixel : les textes français et le contenu honnête du projet ont des longueurs différentes. Les captures constituent les éléments de comparaison livrés.

## Accessibilité : portée et vérifications restantes

Playwright a exécuté le menu mobile public, l’ouverture du menu pédagogique avec focus sur sa première entrée et sa fermeture par Échap avec retour au bouton, le lien d’évitement au clavier jusqu’au premier champ, et le déplacement de focus dans le dialogue de validation. Les dialogues natifs `dialog.showModal()` assurent la modalité, Échap et le retour du focus ; les champs sont associés à leurs labels, les alertes sont annoncées et les styles respectent `prefers-reduced-motion`.

Axe a été exécuté sur l’accueil ordinateur/mobile, les pages publiques d’authentification, module futur, 404, le tableau de bord étudiant, le groupe administrateur, la feuille enseignant et les statistiques des trois rôles, y compris l’assiduité étudiant sur mobile. **Aucun audit humain indépendant n’a été réalisé.** L’inspection des images par l’agent et les tests automatisés ne prouvent pas une conformité complète.

À faire valider par une personne : parcours clavier exhaustif sur tous les formulaires et cas d’erreur, lecture avec NVDA/VoiceOver, zoom 200–400 %, compréhension des messages, focus en cas d’erreurs réseau, contrastes dans tous les états de survol/activation, et essais sur Safari/Firefox ainsi que sur appareils tactiles réels.

## Configuration restante

- Créer votre administrateur dans la base de développement avec `create_admin` ; aucun compte/mot de passe administrateur n’a été imposé. L’aide de cette commande a été exécutée ; sa saisie interactive n’a pas été effectuée dans votre base.
- Renseigner SMTP et paramètres HTTPS/MongoDB authentifié pour une éventuelle production. Aucun déploiement effectué.
- Confirmer les droits détaillés des assets : l’archive ne contient pas le texte intégral de licence.
- Rattacher ce dossier à votre dépôt partagé : il ne contient pas de `.git`. Aucune initialisation ou modification du dépôt parent, aucun push ni fusion.

Les tests ont nécessité l’autorisation d’exécution locale hors du bac à sable Windows pour esbuild/Chromium et l’accès aux registres de dépendances. Ces adaptations de l’environnement n’ont désactivé ni CSRF, ni permissions, ni validation dans l’application.

## Correction ultérieure des interfaces

La séparation Eduleb / administration, les nouveaux contrôles et leurs limites de relance sont détaillés dans [FRONT_OFFICE.md](FRONT_OFFICE.md). Ce rapport remplace la description de l’ancien espace pédagogique avec sidebar. Les résultats historiques ci-dessus restent ceux de la livraison initiale.

## Mise à jour des rôles

Inscription publique avec choix STUDENT/TEACHER et administrateur unique : **39 tests backend, 4 suites navigateur réussies et build React réussi**. La relance de validation précédemment bloquée a été effectuée avec succès. Détails : [ROLES.md](ROLES.md).
