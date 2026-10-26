# Rôles et inscription

La règle actuelle autorise le choix du rôle **Étudiant** ou **Enseignant** à l’inscription. Elle remplace la règle initiale imposant STUDENT à toute inscription.

- Le formulaire demande un choix explicite entre STUDENT et TEACHER.
- Le backend exige ce champ et rejette ADMIN, les valeurs inconnues, vides et les champs de privilèges supplémentaires.
- Un compte enseignant peut se connecter immédiatement à son front-office. Ses groupes restent affectés par l’administrateur.
- La connexion utilise toujours email et mot de passe, sans sélecteur de droits. Le rôle provient du serveur.
- STUDENT est redirigé vers `/espace/etudiant`, TEACHER vers `/espace/enseignant`, ADMIN vers `/administration`.

## Administrateur unique

Il ne peut exister qu’un seul compte ADMIN dans une base, qu’il soit actif ou inactif. La contrainte Django `unique_admin_account` crée un index unique partiel MongoDB sur les comptes dont `role=ADMIN`. Cette contrainte protège également contre deux créations concurrentes ou une promotion directe par l’ORM.

Le rôle administrateur n’est proposé ni à l’inscription publique ni pour attribuer un rôle à un autre utilisateur dans le back-office. La commande `create_admin` refuse de créer un second administrateur, et l’API protège le compte actif contre sa désactivation ou sa rétrogradation. L’administrateur conserve la gestion globale des comptes, groupes, inscriptions, séances, appels et statistiques, dans les règles de conservation d’historique du projet.

Dans la base de développement inspectée pour cette modification, **aucun administrateur n’existait**. Aucun email ou mot de passe administrateur n’a été inventé. Pour créer le compte unique, depuis la racine du projet :

```powershell
.\backend\.venv\Scripts\python.exe backend\manage.py create_admin --email votre-email@exemple.tn --first-name Votre --last-name Nom
```

Le mot de passe est demandé de manière masquée et validé par Django. La migration `accounts.0005_user_unique_admin_account` a déjà été appliquée dans l’environnement local de développement. Sur une autre installation, lancer `manage.py migrate` avant utilisation. Si une base historique contient plusieurs ADMIN, la migration doit être précédée d’une décision explicite sur le compte à conserver ; aucun compte existant n’est supprimé ou rétrogradé automatiquement.

## Tests

Les tests backend couvrent les deux rôles publics, les valeurs refusées, les sessions et permissions, le refus d’une deuxième création ADMIN, les requêtes concurrentes, la promotion directe en base et la commande de création.

Les tests navigateur `roles.spec.ts` vérifient les options du formulaire, la sélection obligatoire, les deux inscriptions et redirections, l’API administrative refusée, le compte admin unique et l’absence de promotion ADMIN dans son formulaire de gestion.

Les nouveaux tests navigateur utilisent `config.roles_e2e_settings` avec la base isolée `test_nexora_roles_browser_isolated`. Ils réutilisent un seul administrateur de fixture avec des identifiants aléatoires stockés uniquement dans `.local`, sans modifier les données de développement ni l’ancienne base de tests.

Résultats obtenus : **39 tests backend réussis**, **4 tests navigateur réussis** (inscriptions et rôles, parcours métier, 54 combinaisons de pages/écrans et comparaison visuelle), build React réussi et contrôles Django sans problème. Voir `roles-verification.json` et `browser-results.json`.
