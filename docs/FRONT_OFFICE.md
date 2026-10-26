# Correction : front-office Eduleb et back-office administrateur

Correction appliquée au projet existant le 26 octobre 2026. Les routes et API métier sont conservées. Aucun code Django, compte ou donnée de développement n’a été modifié.

## Interfaces livrées

- **Administrateur** : `AdminLayout`, sidebar, tableau de bord et gestion globale, uniquement sous `/administration/*`.
- **Étudiant** : `FrontOfficeLayout` Eduleb, navigation horizontale, menu mobile, menu avatar, footer ; page « Mon espace » avec bandeau de bienvenue, cartes d’accès, prochaines séances, groupes et résumé de sa propre assiduité.
- **Enseignant** : même front-office, intitulé « Espace enseignant », groupes affectés, création de séance depuis l’accueil, séances à venir, feuilles d’appel et suivi de ses groupes.

Le layout commun est réellement partagé par l’accueil public et les pages pédagogiques protégées. Les pages ne rendent plus de sidebar ni de wrapper administratif dans le DOM ; leur contenu est organisé en sections et cartes dans un conteneur centré. Les tableaux, filtres, formulaires et historiques sont adaptés à cette largeur. Les vues publiques connectées affichent les mêmes menus adaptés au rôle et l’avatar ; les liens d’administration ne sont pas rendus pour STUDENT/TEACHER.

## Résultats obtenus

| Contrôle | Résultat |
| --- | --- |
| Pages étudiant | 8 routes × 2 tailles, avec actualisation |
| Pages enseignant | 9 routes × 2 tailles, avec actualisation |
| Pages administrateur | 10 routes × 2 tailles, avec actualisation |
| Total | **54 combinaisons route/écran** sans débordement horizontal global |
| Test de séparation des trois rôles | Réussi en 56,8 s (59,6 s avec démarrage du runner) |
| Axe sur les trois accueils, ordinateur et mobile | **6 rapports, 0 violation détectée** |
| Profil | Modification et conservation après actualisation, vérifiées pour les trois rôles |
| Enseignant | Création d’une séance depuis son nouvel accueil, vérifiée via formulaire et API |
| Menus | Navigation clavier, Entrée, Échap et retour du focus vérifiés |
| Session | Accès direct, actualisation et déconnexion vérifiés |
| Restrictions | API administrative refusée aux étudiants/enseignants ; accès au back-office redirigé ; scénario métier et tests Django conservés |
| Backend | **34 tests réussis**, dernier passage 15,952 s ; `manage.py check` sans problème |
| Frontend | Build Vite réussi pendant l’implémentation ; typage TypeScript vérifié sur les sources finales |

Le scénario métier existant a réussi sur les nouveaux layouts (18,9 s), de l’inscription à l’appel, correction, statistiques et annulation. Le contrôle des pages publiques et de l’accueil original/React a également réussi (23,3 s). La nouvelle suite de séparation a ensuite permis de corriger deux débordements mobiles : le positionnement de libellés masqués dans les tableaux et la largeur minimale des synthèses administratives. Elle a été relancée avec succès après ces corrections. Les détails des routes sont dans `front-office-routes.json` et la synthèse dans `front-office-verification.json`.

Une dernière relance groupée du build et des trois suites n’a **pas été exécutée** : la revue automatique d’autorisation n’a pas pu aboutir, car la limite d’usage était atteinte. Ce n’est pas une décision indiquant que l’action était dangereuse. Une assertion supplémentaire de redirection de la route d’appel étudiant, ajoutée au test après son dernier passage, reste à rejouer ; le contrôle de permission Django correspondant figure dans les 34 tests backend réussis. Aucun résultat de cette relance n’est présenté comme obtenu.

## Captures

- [Étudiant — ordinateur](screenshots/front-office-student-1440.png) et [mobile](screenshots/front-office-student-390.png).
- [Enseignant — ordinateur](screenshots/front-office-teacher-1440.png) et [mobile](screenshots/front-office-teacher-390.png).
- [Administrateur — ordinateur](screenshots/back-office-admin-1440.png) et [mobile](screenshots/back-office-admin-390.png).

Les captures utilisent uniquement des comptes et données de test. L’agent a inspecté visuellement les versions étudiant/enseignant sur ordinateur et mobile. Les tests automatisés et axe ne remplacent pas un audit humain complet d’accessibilité.

## Messages console avant connexion

L’invitation à installer React DevTools est informative. `GET /api/auth/me/` retourne normalement **401** pour un visiteur sans session ; le client traite ce cas sans erreur dans l’interface. Les deux requêtes proviennent de la répétition des effets sous `React.StrictMode` en développement. Ce comportement ne justifie ni de désactiver les permissions ni de reconstruire l’authentification. Un 401 persistant après une connexion réussie exigerait un diagnostic distinct.

## Validation complémentaire après le choix des rôles

La relance complète a finalement pu être exécutée lors de la mise à jour des rôles : les quatre suites navigateur passent, y compris l’assertion de redirection de l’appel étudiant qui restait à rejouer. Les 39 tests backend et le build React passent également. Les résultats actuels figurent dans [ROLES.md](ROLES.md) et `roles-verification.json`. Le blocage de revue décrit plus haut concerne la vérification historique, désormais complétée.
