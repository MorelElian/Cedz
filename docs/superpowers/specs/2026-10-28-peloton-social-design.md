# Peloton social

## Objectif

Faire de Cedz un jeu social autour des opinions déjà collectées, sans intégrer
de données Garmin. Les participants consultent des fiches publiques, réagissent
et commentent les contenus, puis alimentent le mur d'un autre participant.

## Navigation participant

La navigation principale est limitée à quatre onglets :

1. Accueil
2. Dossiers
3. Peloton
4. Profil

`Dossiers` réunit les révélations reçues et `Mes réponses`, au moyen d'un
sélecteur secondaire simple. `Profil` contient les réglages du compte, les
réponses reçues et l'édition de la phrase d'accroche personnelle.

## Peloton

Chaque participant possède une fiche publique.

- Sur ordinateur, une colonne gauche affiche les dix portraits et sélectionne
  la fiche à droite.
- Sur mobile, cette colonne devient un rail horizontal collant afin de laisser
  la largeur nécessaire aux cartes et aux commentaires.
- La tête de fiche affiche portrait, nom et phrase d'accroche du participant.
- Les quatre rangs agrégés (global, nage, vélo, course) restent lisibles en
  premier. Un détail dépliable montre les votes nominaux associés à chaque
  classement.
- Cinq révélations reçues sont mises en avant. Elles sont choisies et ordonnées
  manuellement par l'administrateur, et non automatiquement par date.
- Un mur de profil permet à tout participant connecté de publier directement un
  message sur la fiche d'un autre participant.
- Un bloc `Les plus commentés` met en avant les contenus les plus actifs du
  moment.

## Interactions

Les réactions sont publiques et nominatives. Pour chaque contenu, un même
participant possède au plus une réaction, modifiable ou supprimable :

- `J'avoue`
- `N'importe quoi`
- `Autre…` : libellé court saisi par le participant

Les révélations mises en avant acceptent réactions et commentaires. Les votes
de classement acceptent les réactions, sans fil de commentaires. Les messages
du mur sont des publications distinctes et visibles immédiatement.

## Profil

Le participant peut définir une phrase d'accroche courte. Elle apparaît sous
son nom sur sa fiche Peloton. Elle est validée côté serveur (texte simple,
longueur courte) et peut être modifiée à tout moment.

## Administration

Un espace Peloton dans l'administration permet de :

- choisir jusqu'à cinq révélations envoyées pour chaque fiche ;
- définir leur ordre ;
- retirer un message de mur, un commentaire ou une réaction qui poserait
  problème ;
- visualiser les contenus les plus commentés.

L'édition du texte d'une révélation reste dans l'outil de gestion des
révélations existant. La sélection Peloton ne modifie jamais l'historique
d'envoi.

## Données et autorisations

Nouvelles données : phrase d'accroche participant, publications de mur,
commentaires, réactions et emplacements de révélations mises en avant.

- Les participants créent/modifient/suppriment uniquement leurs propres
  messages, commentaires et réactions.
- Les profils, réactions, commentaires et murs sont lisibles par les
  participants authentifiés.
- L'administration peut modérer ou retirer tout contenu social.
- Les activités Garmin, OAuth et données sportives connectées sont hors scope.

## Robustesse

Les champs libres sont limités, échappés à l'affichage et protégés par le CSRF
existant. Les compteurs de réactions/commentaires sont recalculés depuis les
données persistées afin d'éviter les incohérences. La suppression d'un contenu
parent retire ses interactions associées.

## Vérification

Les tests couvriront les autorisations, les limites de texte, les réactions
uniques et modifiables, les commentaires, le mur, la sélection admin des cinq
révélations et les données exposées sur une fiche Peloton.
