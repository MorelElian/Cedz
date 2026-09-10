# Plan de discussion — traiter et envoyer les réponses

Ce document sert de base de discussion. Rien n'est encore figé ni envoyé.

## État de l'export actuel

Le fichier `answers/t24-reponses(1).json` contient :

- 252 réponses ;
- 9 auteurs différents ;
- 60 questions représentées ;
- 141 réponses textuelles ;
- 25 réponses numériques ;
- 87 réponses structurées (duels, groupes et classements).

Les participants n'ont pas tous répondu au même nombre de questions. Tous les classements conservés contiennent désormais un `lap_time`.

## Binding ID → participant

| ID | Nom |
|---:|---|
| 5 | Barbs |
| 6 | Diego |
| 7 | Div |
| 8 | JL |
| 9 | Lahaye |
| 10 | Moms |
| 11 | Nav |
| 12 | Peusch |
| 13 | Pilche |
| 14 | Rov |

Ce binding doit être utilisé pour convertir aussi bien `targetParticipantId` que les identifiants présents dans `selected_participant_id`, `ordered_participant_ids`, `category_a` et `category_b`.

## Trois designs possibles pour les envois

### Option A — La révélation individuelle

Un mail court contient une seule révélation. C'est le format le plus adapté à des envois réguliers.

Exemple de structure :

> **Le comité a parlé.**  
> « À partir de quelle minute Nav commence à regretter d'être venu ? »  
> **Verdict : 47 minutes en moyenne.**

Le mail pourrait contenir :

- le logo Cedz ;
- la petite photo du destinataire ;
- une question ;
- la réponse ou le résultat traité ;
- une phrase finale courte et drôle ;
- éventuellement un lien vers une page privée avec davantage de détails.

Avantages : simple, attendu et facile à lire. Une cadence de deux mails par semaine permet de faire durer le jeu.

### Option B — Le bulletin hebdomadaire

Un mail contient trois cartes différentes :

1. une citation reçue par le destinataire ;
2. un résultat collectif ou un podium ;
3. une statistique issue d'un curseur, duel ou classement.

Avantages : plus riche et moins de mails. Inconvénient : les meilleures réponses sont consommées plus rapidement.

### Option C — Le feuilleton avant T24

Les mails suivent des épisodes éditoriaux :

- épisode 1 : les réputations ;
- épisode 2 : les duels ;
- épisode 3 : les futurs craquages ;
- épisode 4 : nage ;
- épisode 5 : vélo ;
- épisode 6 : course ;
- finale : les classements et pronostics complets.

Avantages : très cohérent avec l'événement et facile à scénariser. Cela demande cependant de préparer un calendrier et de choisir les réponses de chaque épisode.

## Recommandation

Je recommande un mélange des options A et C : une révélation courte par mail, organisée dans une progression éditoriale jusqu'au T24.

Cadence proposée :

- mardi : révélation personnelle ;
- vendredi : résultat collectif ou duel ;
- semaine du T24 : classements nage, vélo et course ;
- après le T24 : confrontation entre les pronostics et la réalité.

## Traitement selon le type de réponse

### Texte ciblant une personne

Exemples : petit mot, défaut, phrase de motivation, carrière rugbystique.

- Destinataire principal : `targetParticipantId`.
- Contenu : question rendue puis réponse textuelle.
- Traitement : correction typographique légère uniquement ; ne pas réécrire la blague.
- Choix éditorial à décider : afficher l'auteur, le cacher ou le révéler plus tard.

Format conseillé : une carte « Quelqu'un a dit ça sur toi ».

### Texte concernant un binôme ou un trio

Exemples : comparaison de niveau ; capitaine, joker et ambiance.

- Destinataires possibles : toutes les personnes présentes dans la question.
- Traitement : reconnaître les IDs du binôme ou trio depuis l'instance de question.
- Format conseillé : envoyer le même résultat aux concernés, mais avec une introduction personnalisée.

Il faut éviter de router ces réponses uniquement avec `targetParticipantId`, car les deuxième et troisième cibles ne figurent pas toujours dans ce champ de l'export.

### Duels et comparaisons à trois

Forme : `selected_participant_id` et commentaire facultatif.

- Convertir l'ID sélectionné en nom.
- Regrouper les votes par question.
- Calculer le nombre et le pourcentage de sélections de chaque personne.
- Sélectionner au maximum un commentaire marquant par résultat.

Formats possibles :

- « 4 personnes sur 6 te confieraient le dernier relais » ;
- « Dans ce trio, 67 % des votes sont tombés sur Diego » ;
- résultat anonyme dans un premier mail, auteurs révélés dans un mail ultérieur.

### Curseurs et réponses numériques

- Grouper par question et personne ciblée.
- Afficher de préférence la médiane, plus résistante à une réponse volontairement absurde.
- Ajouter la moyenne et l'étendue seulement s'il y a au moins trois réponses.
- Toujours rappeler l'unité : minutes, note sur 10, probabilité sur 100 ou nombre de fois.

Format conseillé : une jauge simple avec une phrase comme « Le groupe te donne 38 minutes avant la première négociation avec ton âme ».

### Classements

Forme récente : `ordered_participant_ids` et `lap_time`.

- Donner 10 points au premier, 9 au deuxième, jusqu'à 1 point au dernier.
- Additionner les points séparément pour la nage, le vélo et la course.
- En cas d'égalité, départager avec la meilleure place médiane, sans inventer de différence si l'égalité persiste.
- Pour `lap_time`, accepter temporairement du texte libre et afficher la médiane seulement après normalisation dans une unité commune.

Format conseillé : podium de la discipline, puis encart « chrono imaginé par le groupe ».

### Séparation en deux groupes

Forme : `category_a` et `category_b`.

- Convertir chaque ID en nom.
- Conserver les vrais intitulés propres à la question, par exemple « Zug » et « Bellagio ».
- Pour chaque personne, calculer son pourcentage de placement dans chacun des deux camps.

Format conseillé : « 75 % du jury te voit négocier avec ton âme après minuit ».

## Règles de sélection des contenus

Pour éviter les mails pauvres ou gênants :

- ne rien envoyer lorsqu'une statistique ne repose que sur une réponse, sauf s'il s'agit d'un petit mot explicitement destiné à quelqu'un ;
- éviter deux mails consécutifs visant la même personne ou provenant du même auteur ;
- ne pas envoyer deux fois la même réponse ;
- marquer chaque contenu comme `pending`, `approved`, `scheduled`, `sent` ou `rejected` ;
- prévoir un aperçu admin exact avant tout envoi ;
- permettre de corriger uniquement les fautes évidentes, tout en conservant la réponse originale ;
- conserver une trace de la date, du destinataire et du contenu réellement envoyé.

## Fichier d'adresses à fournir

Format CSV recommandé :

```csv
participant_id,display_name,email
5,Barbs,adresse@example.com
6,Diego,adresse@example.com
```

L'ID est la clé fiable. Le nom sert uniquement à détecter une erreur humaine. Avant chaque campagne, le programme devra refuser :

- un ID inconnu ;
- un ID présent deux fois ;
- une adresse invalide ;
- un nom ne correspondant pas au binding connu ;
- un participant sans adresse.

Ce fichier ne devrait pas être ajouté au dépôt Git. Il faudra l'ignorer avec `.gitignore` et charger les adresses dans la base ou dans les variables privées de Railway.

## Interface de traitement proposée

Une page admin « Révélations » pourrait afficher :

1. les réponses brutes à gauche ;
2. un aperçu du mail à droite ;
3. le destinataire calculé ;
4. l'auteur visible ou anonyme ;
5. les boutons Rejeter, Approuver et Programmer ;
6. les filtres par personne, type de question et statut ;
7. l'historique des envois.

Pour les réponses agrégées, l'interface générerait automatiquement le résultat, tout en laissant l'admin choisir le titre et le commentaire final.

## Architecture d'envoi envisagée

1. Importer l'export JSON sans le modifier.
2. Normaliser chaque réponse dans un format commun.
3. Résoudre tous les IDs avec le binding des participants.
4. Produire des contenus individuels et des agrégats.
5. Les faire valider dans l'administration.
6. Placer les contenus approuvés dans une file d'envoi.
7. Exécuter régulièrement un petit script planifié.
8. Envoyer via un fournisseur transactionnel tel que Brevo, Resend ou Postmark.
9. Enregistrer succès, erreur et identifiant du fournisseur.

Le serveur Flask existant suffit. Railway peut lancer le site et une tâche planifiée séparée, mais il faudra une base persistante pour ne pas perdre les programmations et l'historique.

## Décisions à prendre ensemble

1. Les auteurs restent-ils anonymes, toujours visibles, ou révélés progressivement ?
Les auteurs sont toujours visibles 
2. Préfère-t-on un mail court deux fois par semaine ou un bulletin hebdomadaire ?
Un mail court deux trois fois semaines. 
3. Les réponses sensibles doivent-elles être validées une par une ?
Oui je veux dans l'onglet admin pouvoir review ce qui va être envoyé le lendemain à 8h. 
4. Les destinataires voient-ils seulement ce qui les concerne ou aussi les résultats collectifs ?
Seulement ce qui les concerne. 
5. Veut-on un lien vers une page privée, ou tout afficher directement dans le mail ?
Je veux un mail et je veux faire une page par participant avec le détail de ce que les gnes ont dit sur lui. 
6. Quelle est la date du T24 afin de construire le calendrier éditorial ?
Ca tu n'as pas a le savoir 

### Autres reflexions 
Nous allons découper en plusieurs tâches. 
Une fois codés les tâches ne doivent plus dépendre d'un llm. Ca doit être "statique". 
# 1  Refont du système d'authentification, On va créer des comptes par personnes 
Depuis l'admin je vais attribuer un mdp à chacun des mecs, ils auront chacun leur compte. C'est un petit site ne te prends pas trop la tête avec la sécurité. 
# 2 Création de page utilisateur. 
Pour chacun des joueurs deux parties dans la page : 
-  Ses réponses, pour l'instant il ne peux pas les changer, réponses triées par catégorie
- Ce que pense les gens de lui, en gros l'historique des choses 
- La seule stats est sur les classements, tu fais le classement moyen en fonction des réponses dont ils ont connaissances dans les trois disciplines. 
# 3 Intégration de toutes les réponses dans la db
Les réponses doivent être dans la db et je dois pouvoir enlever certaines etc 
# 3 review côté admin 
Admin doit pouvoir voir pour les 10 prochains mails envoyés et les review. Il doit pouvoir "refresh" c'est à dire pick un autre mail. 
L'envoi se déchlenche quand l'admin accepte.  
On verra plus tard pour automatiser l'envoi de la tâche
L'admin doit pouvoir aussi voir les réponses actuellemnet envoyés etc... 
# 4 Structure d'un mail / architecture du serveur 
Je veux des jolis mails. Je veux des mails difféernts dépendamment du type de réponse. Je veux le cedz , je veux la gueule du mec qui as répondu sur toi et que le thème du site soit respecté.

# 5 Types de mail. 
Le mail commence toujours par une phrase type : "Pas la pêche aujourd'hui ?" Je vais te fournir une liste de 15 phrases. Il faudra tourner 
## 5.1 Réponse libre 
POur une réponse libre : Voila ce que Gustave pense de toi lorsqu'on lui demande : [Nom de la question]
Et voilà la réponse. 

Tu souhaites lui répondre ?  lien vers la page du site ou tu peux répondre.

## 5.2 Duel Entre machin et Machin 
"On a demandé a [..] de choisir entre [..] et [...]". 
- Il t'a choisi. 
- Il t'as pas choisi.
+ le petit commentaire que le mec a mis. 

## 5.3 Trio 
Même chose que pour le duo. 

## 5.4 Classement en deux côté 
"[...] machin a du classer selon la question suivante: [question]. 
Il t'a mis ... 
Voila le bilan de la question. 

### 5.5 Classement des 10 
Ignore lap time ça sert a rien. 
[..] pour le {classement} t'as classé xème, il te voit derrière : et tu mets un mec qui est juste devant, mange-le ! si il est premier, bah tu lui dis bravo. 
Découvre son classement 