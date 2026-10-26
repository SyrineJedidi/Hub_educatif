# Architecture et conventions

## Compatibilité vérifiée

Le choix Django 5.2 / backend MongoDB 5.2 respecte la correspondance majeure/mineure imposée par MongoDB. Cette branche est compatible avec Python 3.13 et le MongoDB 6.0 local. DRF 3.16 annonce la prise en charge de Django 5.2 et Python 3.13. Node 22.23.2 satisfait Vite 7. Les versions effectivement installées sont verrouillées ; `npm audit` a conduit à choisir Vite 7.3.7 et React Router 7.18.4.

Sources officielles consultées : [compatibilité MongoDB](https://www.mongodb.com/docs/drivers/compatibility/?driver-language=python&python-driver-framework=django), [limitations du backend](https://www.mongodb.com/docs/languages/python/django-mongodb/current/limitations-upcoming/), [transactions MongoDB 5.2](https://www.mongodb.com/docs/languages/python/django-mongodb/v5.2/interact-data/transactions/), [DRF 3.16](https://www.django-rest-framework.org/community/3.16-announcement/), [Vite](https://vite.dev/guide/).

## Organisation

`accounts` contient l’utilisateur personnalisé déclaré avant les premières migrations, les sessions Django, serializers et permissions. `classrooms` contient LearningGroup et Enrollment. `attendance` contient LearningSession, Attendance (document embarqué), AttendanceSheet et les statistiques. `frontend/src` sépare client API, authentification, composants, hooks, layouts, routes, pages et styles ; formulaires, listes et détails des groupes/séances sont séparés.

Les migrations compatibles des applications contrib auth/contenttypes, initialement issues du gabarit MongoDB, sont conservées sous `mongo_migrations`. Les clés utilisent ObjectIdAutoField et les identifiants publics sont des chaînes ObjectId validées. Les groupes de permissions Django restent distincts de LearningGroup. L’administration métier est entièrement en React.

## Authentification et profils

Normalisation email : suppression des espaces en début/fin puis `lower()` Unicode sur l’ensemble de l’adresse, avant stockage et recherche. Le projet choisit de traiter aussi la partie locale sans distinction de casse ; ce choix ne prétend pas décrire tous les fournisseurs SMTP. L’index unique en base arbitre aussi les doublons simultanés. Pas de vérification d’email en V1 : `email_verified` reste faux, aucun endpoint de vérification exposé.

Django assure le hashage, la validation des mots de passe, la rotation de session à la connexion, les cookies HttpOnly et les jetons de réinitialisation. Un nonce de session supplémentaire, inclus dans le hash Django, est renouvelé lors des modifications administratives : une réactivation ne rétablit pas les anciennes sessions. Le changement de mot de passe invalide aussi les autres sessions. Toutes les écritures, y compris connexion et déconnexion, sont protégées par CSRF.

Le throttle utilise des compteurs MongoDB atomiques et des fenêtres fixes : connexion 20/IP/5 min et 10/email/5 min ; inscription 10/IP/heure ; réinitialisation 10/IP/heure et 3/email/heure. Les adresses IP proviennent de REMOTE_ADDR ; ne pas faire confiance aux en-têtes de proxy arbitraires. Un index TTL purge les compteurs expirés.

Avatars : PNG/JPEG/WebP réels, au plus 2 Mo et 16 mégapixels, inspection Pillow puis réencodage JPEG 512×512 maximum, nom UUID. Aucun SVG ni chemin client conservé. Les fichiers restent privés et sont servis uniquement au propriétaire via une vue authentifiée. Les mises à jour du profil et de l’avatar ne peuvent réécrire les rôles à partir d’un objet utilisateur devenu obsolète.

## Historique, transactions et concurrence

MongoDB ne fournit ni `select_for_update` ni les transactions Django natives pour cette stack. Les écritures métier utilisent `django_mongodb_backend.transaction.atomic`. Un replica set ou cluster partitionné est obligatoire ; un serveur autonome ne suffit pas. Les index sont créés par migrations, hors transactions métier.

Une garde commune `AdminGuard(key=accounts)` est écrite dans chaque transaction de modification des comptes, affectations, périodes, séances et feuilles. Deux écritures concurrentes sur cette garde provoquent un conflit MongoDB ; une requête relit et revérifie les invariants dans au plus trois tentatives, puis retourne 409. Ce choix empêche le write skew (dernier administrateur, chevauchements et dépendances intercollections). Il privilégie la cohérence au débit pour ce projet académique. En cas de forte charge, partitionner les gardes exige de repenser les invariants transversaux, pas simplement de supprimer cette protection.

Index uniques : email, code de groupe, clé de garde, clé de compteur, séance de chaque feuille. Une contrainte unique partielle sur role=ADMIN garantit un seul administrateur, actif ou inactif. Index composés sur groupe/étudiant/début des inscriptions et groupe/début/fin des séances. Une feuille stocke les Attendance embarqués dans un document unique, avec une liste historique de participants. L’API vérifie l’ensemble des identifiants et rejette tout doublon ; une version entière empêche les écrasements. Les changements et leur historique sont sauvegardés dans la même transaction.

Périodes : intervalles `[entrée, sortie[`, sortie absente = sans fin. Les périodes adjacentes sont autorisées ; les chevauchements ne le sont pas. Chaque réinscription crée une nouvelle période. Une modification des inscriptions ne change pas les participants des anciennes feuilles. Un étudiant figurant sur une ancienne feuille garde accès à sa séance et à ses propres statistiques historiques.

Un groupe archivé refuse nouvelles inscriptions et nouvelles séances. Seul un groupe sans inscription ni séance peut être supprimé. Les séances sont annulées, jamais supprimées. Groupe et horaires d’une séance avec feuille sont conservés.

Un changement de rôle exige de réaffecter ou archiver les groupes enseignés et de terminer les périodes d’inscription en cours/futures. Les anciennes périodes closes sont conservées et n’empêchent pas une évolution de rôle. Le dernier administrateur actif ne peut être rétrogradé ou désactivé, même par deux requêtes simultanées.

## Statistiques et export

Convention Nexora, sans valeur de règlement officiel ESPRIT :

`(PRESENT + LATE) / (PRESENT + LATE + ABSENT) × 100`.

EXCUSED est exclu du dénominateur et compté séparément. UNSET n’est jamais une absence. Un dénominateur nul donne `rate=null`, affiché « Non calculable ». Ne sont retenues que les feuilles validées des séances non annulées dont la fin est passée, dans le périmètre autorisé. Le champ COMPLETED n’est pas suffisant si l’heure de fin est future. Les filtres portent sur le début de séance. Le CSV applique les mêmes droits et neutralise les cellules pouvant être interprétées comme des formules.

Limites de volume : les synthèses et l’export parcourent les feuilles autorisées en Python ; l’historique d’une feuille est embarqué et soumis à la limite documentaire MongoDB de 16 Mo. Pour de très grands effectifs ou un historique volumineux, prévoir une agrégation dédiée et un stockage d’audit séparé, tout en conservant l’atomicité. Les photos et les modules futurs ne sont pas présentés comme des personnes ou services réels de Nexora.


## Séparation du front-office et du back-office

`FrontOfficeLayout` entoure à la fois l’accueil public et les routes `/espace/*`. Il compose le header horizontal Eduleb, les menus déroulants pédagogiques, le menu avatar et le footer. `ProtectedLearningLayout` contrôle la session et le rôle, puis place les pages dans un conteneur centré ; il ne rend aucune sidebar ni aucun élément du shell administratif. `LearningHome` compose les bandeaux et sections spécifiques étudiant/enseignant, avec les séances à venir, groupes, résumé d’assiduité et accès à l’appel pour les enseignants.

`AdminLayout` est monté uniquement sous `/administration/*`, contrôle ADMIN et conserve la sidebar, le dashboard et les outils de gestion globale. Les formulaires, composants de liste, API, modèles et règles Django existants sont réutilisés. Cette correction ne modifie aucun code backend ni aucune donnée de développement. Les écritures des tests sont limitées à la base navigateur dédiée.


## Choix du rôle à l’inscription

La demande actualisée autorise STUDENT et TEACHER lors de l’inscription publique. Le choix est obligatoire, validé par un ChoiceField côté Django et un select HTML requis côté React. ADMIN et les champs inconnus restent refusés. Le serveur décide des permissions à partir du rôle enregistré ; la connexion ne comporte aucun sélecteur de droits.

Un seul compte ADMIN est autorisé dans toute base, même s’il était désactivé techniquement. La contrainte `unique_admin_account` est un index unique partiel MongoDB, déclaré par le modèle et migré. La commande `create_admin` refuse un second compte avant de demander son mot de passe. Aucun secret n’est codé en dur. L’administrateur conserve toutes les fonctions de gestion, avec les protections d’historique et de cohérence.
