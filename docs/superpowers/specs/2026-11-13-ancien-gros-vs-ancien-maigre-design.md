# Ancien gros vs Ancien maigre — Design

## But

Ajouter un duel d'équipes vivant, basé exclusivement sur les révélations de
classement déjà envoyées. Il doit rendre immédiatement visible la comparaison
entre les Anciens gros et les Anciens maigres, tout en restant correct lorsque
des classements attendent encore d'être révélés.

## Règles de données

- Les camps sont fixes : `ancien_gros` et `ancien_maigre`.
- Un participant peut ne pas être attribué à un camp.
- Une seule source de vérité : les révélations de type `ranking` avec
  `status='sent'`.
- Les disciplines sont Nage, Vélo et Course. Une plus petite position moyenne
  est meilleure.
- Chaque affichage recalcule les chiffres depuis les révélations et les
  équipes actuelles. Un changement d'affectation admin met donc à jour le
  présent et l'historique immédiatement.

## Calculs

Pour chaque discipline et chaque équipe :

- moyenne des positions révélées ;
- écart-type de population (`0` avec une seule valeur) ;
- nombre d'avis révélés ;
- personnes et positions à l'origine des données.

La comparaison contient la différence absolue des deux moyennes, le camp
gagnant (ou une égalité) et l'état de complétude. La complétude compare les
classements envoyés aux classements encore candidates ou en revue ; les
chiffres restent visibles mais sont marqués provisoires tant que ce dernier
compteur n'est pas nul.

La tendance est reconstruite par semaine ISO depuis `revelations.sent_at`.
Chaque point contient la moyenne cumulative de chaque équipe à la fin de la
semaine, sans inventer de valeur lorsqu'une équipe n'a pas encore de donnée.

## API et persistance

- Ajouter `participants.team` nullable, avec seulement `ancien_gros` et
  `ancien_maigre` comme valeurs applicatives admises.
- `GET /api/team-duel`, réservé à un participant connecté, retourne équipes,
  statistiques par discipline et historique.
- `GET /api/admin/team-duel`, réservé à l'admin, retourne le même tableau de
  bord et la liste complète des participants.
- `PATCH /api/admin/team-duel/participants/<id>` accepte `team` à `null`,
  `ancien_gros` ou `ancien_maigre` et renvoie l'état recalculé.

## Interface participant

Un cinquième onglet, `Ancien gros vs Ancien maigre`, présente :

- deux équipes face à face, toujours visibles ;
- les trois disciplines sous forme de lignes comparatives, moyennes au centre
  du duel et écart compact (`+ 0,45`) ;
- un clic sur une discipline qui déplie les écarts-types, le volume d'avis,
  les positions individuelles et une mini-courbe cumulative ;
- un état vide ou provisoire explicite mais discret.

La page n'emploie pas de bibliothèque de graphiques : la courbe est un SVG
responsive construit en JavaScript, avec les couleurs existantes du site.

## Interface admin

Un onglet `Ancien gros vs Ancien maigre` permet l'affectation immédiate de
chaque participant à l'un des deux camps, ou à aucun. Il réutilise le style
des panneaux admin et affiche le même résumé de duel pour permettre une
vérification immédiate.

## Vérification

- API : accès protégé, validation des équipes, statistiques vides, sent-only,
  écart-type, incomplétude, tendance chronologique et recalcul après mutation.
- JavaScript : vérification syntaxique des scripts ajoutés.
- Visuel : vue mobile et bureau, détail ouvert/fermé, équipes incomplètes et
  absence de classement.
