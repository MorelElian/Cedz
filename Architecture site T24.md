# Architecture site T24

## Objectif du site

Créer un site web dynamique pour un jeu autour du **T24**, un triathlon 24h entre potes.

Le principe :
1. L'admin prépare la liste des participants.
2. L'admin prépare / modifie les questions.
3. Chaque joueur arrive sur le site, choisit son profil, entre son mail et son téléphone.
4. Il répond aux questions.
5. Les réponses sont stockées en base de données.
6. Dans un premier temps, personne ne voit les réponses des autres.
7. Dans un deuxième temps, on mettra en place un système de révélation progressive par mail, SMS ou via le site.

Note source pour les types de questions : [[Cedilles are shooting.md]]

---

## Vision produit

Le site doit être pensé comme un petit jeu privé entre amis, avec un ton :
- taquin ;
- drôle ;
- second degré ;
- motivant ;
- jamais gratuitement méchant.

Les questions doivent permettre de créer des réponses marrantes autour des participants, mais le système doit aussi éviter que quelqu'un voie trop tôt ce qui a été dit sur lui.

---

## Rôles utilisateurs

## 1. Admin

L'admin doit pouvoir :
- créer des participants ;
- modifier les informations des participants ;
- supprimer ou désactiver un participant ;
- créer des questions ;
- modifier des questions ;
- activer / désactiver des questions ;
- choisir le type de question ;
- voir les réponses collectées ;
- exporter les réponses si besoin ;
- préparer plus tard les révélations par mail / SMS.

## 2. Participant

Le participant doit pouvoir :
- arriver sur une page d'accueil ;
- choisir son personnage / profil ;
- entrer son adresse mail ;
- entrer son numéro de téléphone ;
- répondre aux questions ;
- sauvegarder ses réponses ;
- éventuellement reprendre plus tard si on ajoute une logique de session.

Le participant ne doit pas pouvoir :
- voir les réponses des autres ;
- voir ce que les autres ont dit sur lui ;
- modifier les questions ;
- accéder à l'admin.

---

## Pages principales

## 1. Page d'accueil participant

Route proposée : `/`

Objectif : permettre à quelqu'un de commencer le jeu.

Contenu :
- titre du jeu ;
- courte explication du concept ;
- liste des participants sous forme de cartes ;
- bouton “Je suis cette personne” ;
- champ email ;
- champ téléphone ;
- bouton “Commencer”.

Comportement :
- le joueur choisit son profil ;
- il rentre email + téléphone ;
- le site crée ou met à jour une session de réponse ;
- le joueur est envoyé vers le questionnaire.

À prévoir :
- empêcher deux personnes de répondre en se faisant passer pour le même profil est compliqué sans vraie authentification. Pour le MVP, on accepte cette limite ou on ajoute un petit code secret par participant.

---

## 2. Page questionnaire

Route proposée : `/questionnaire/:sessionId`

Objectif : faire répondre le participant aux questions.

Contenu :
- progression : question X / Y ;
- question actuelle ;
- type de réponse adapté ;
- bouton suivant ;
- bouton précédent ;
- sauvegarde automatique ou bouton sauvegarder.

Types de questions à supporter au MVP :

### A. Réponse texte libre

Exemple :
> Un petit mot à adresser à ...

Réponse attendue : texte court ou moyen.

### B. Question sur une personne

Exemple :
> Sur quel sport devrait se concentrer ... ?

Le système doit remplacer `...` par un participant cible.

### C. Comparaison entre deux personnes

Exemple :
> Entre ... et ..., qui a le plus de chances de finir le T24 avec une vraie aura ?

Réponse attendue : choix entre les deux personnes + commentaire optionnel.

### D. Comparaison entre trois personnes

Exemple :
> Entre ..., ... et ..., qui repartira avec le plus gros capital respect ?

Réponse attendue : choix parmi trois personnes + commentaire optionnel.

### E. Classement

Exemple :
> Classement pour les différentes disciplines.

Réponse attendue : liste ordonnée de participants.

### F. Séparation en deux catégories

Exemple :
> Physique ou chance.

Réponse attendue : chaque participant est placé dans une des deux catégories.

### G. Curseur / note

Exemple :
> Sur 100, quelle est la probabilité que ... sorte une vraie perf ?

Réponse attendue : nombre sur une échelle définie.

---

## 3. Page fin de questionnaire

Route proposée : `/merci`

Objectif : confirmer que les réponses ont été enregistrées.

Contenu :
- message de confirmation ;
- rappel que les réponses seront révélées plus tard ;
- ton léger / teasing.

Exemple :
> Tes réponses sont sauvegardées. Pour l'instant, personne ne voit rien. Les dossiers sont en cours de constitution.

---

## 4. Page admin

Route proposée : `/admin`

Objectif : gérer les participants, les questions et les réponses.

L'admin doit être protégé par authentification simple au minimum.

Fonctionnalités admin MVP :

### Participants

- afficher tous les participants ;
- ajouter un participant ;
- modifier nom / surnom / image / statut ;
- désactiver un participant ;
- générer éventuellement un code secret de connexion.

### Questions

- afficher toutes les questions ;
- créer une question ;
- modifier une question ;
- désactiver une question ;
- choisir un type de question ;
- définir si la question cible une personne, deux personnes, trois personnes ou tout le groupe ;
- définir l'ordre d'affichage.

### Réponses

- voir le nombre de réponses par participant ;
- voir les réponses brutes ;
- filtrer par auteur ;
- filtrer par cible ;
- filtrer par question ;
- exporter en CSV / JSON.

---

## Modèle de données proposé

## Table `participants`

Représente les personnes qui participent au jeu.

Champs :
- `id` : identifiant unique ;
- `display_name` : nom affiché ;
- `slug` : nom lisible dans les URLs si besoin ;
- `email` : email renseigné par le participant, nullable au départ ;
- `phone` : téléphone renseigné par le participant, nullable au départ ;
- `avatar_url` : image du personnage, optionnel ;
- `secret_code` : code de connexion optionnel ;
- `is_active` : participant actif ou non ;
- `created_at` ;
- `updated_at`.

---

## Table `questions`

Représente les modèles de questions.

Champs :
- `id` ;
- `title` : intitulé court admin ;
- `body` : texte de la question ;
- `type` : type de question ;
- `category` : catégorie logique ;
- `target_mode` : `none`, `one_person`, `two_people`, `three_people`, `all_people` ;
- `scale_min` : minimum si question curseur ;
- `scale_max` : maximum si question curseur ;
- `is_active` ;
- `display_order` ;
- `created_at` ;
- `updated_at`.

Types possibles :
- `free_text` ;
- `single_person_answer` ;
- `compare_two` ;
- `compare_three` ;
- `ranking` ;
- `binary_split` ;
- `slider`.

---

## Table `question_instances`

Option recommandée : distinguer le modèle de question de son instance concrète.

Exemple :
- modèle : `Sur quel sport devrait se concentrer ... ?`
- instance : `Sur quel sport devrait se concentrer Hugo ?`

Champs :
- `id` ;
- `question_id` ;
- `target_participant_id` ;
- `target_participant_2_id` ;
- `target_participant_3_id` ;
- `rendered_body` : texte final affiché ;
- `is_active` ;
- `created_at`.

Pourquoi c'est utile :
- ça évite de recalculer les combinaisons à chaque chargement ;
- ça permet à l'admin de désactiver une instance précise ;
- ça permet de contrôler le nombre de questions pour ne pas rendre le questionnaire interminable.

---

## Table `answer_sessions`

Représente une session de réponse d'un participant.

Champs :
- `id` ;
- `participant_id` : personne qui répond ;
- `email` ;
- `phone` ;
- `status` : `started`, `completed` ;
- `started_at` ;
- `completed_at` ;
- `created_at` ;
- `updated_at`.

---

## Table `answers`

Représente une réponse donnée à une question.

Champs :
- `id` ;
- `session_id` ;
- `author_participant_id` : qui répond ;
- `question_instance_id` ;
- `target_participant_id` : personne principalement visée, si applicable ;
- `answer_text` : réponse libre ;
- `answer_number` : réponse numérique, si curseur ;
- `answer_json` : réponse structurée pour classement, comparaison, séparation en deux catégories ;
- `created_at` ;
- `updated_at`.

Exemples de `answer_json` :

Pour un classement :
```json
{
  "ordered_participant_ids": ["p1", "p3", "p2"]
}
```

Pour une comparaison :
```json
{
  "selected_participant_id": "p2",
  "comment": "Il a l'air fragile mais il va surprendre."
}
```

Pour une séparation en deux catégories :
```json
{
  "category_a": ["p1", "p4"],
  "category_b": ["p2", "p3"]
}
```

---

## Logique de génération des questions

L'admin écrit des modèles de questions avec des placeholders.

Exemples :
- `Sur quel sport devrait se concentrer {person} ?`
- `Entre {person1} et {person2}, qui a le plus de chances de finir le T24 avec une vraie aura ?`
- `Entre {person1}, {person2} et {person3}, qui repartira avec le plus gros capital respect ?`

Le système génère ensuite des instances selon le `target_mode`.

Modes :
- `none` : question générale, une seule instance ;
- `one_person` : une instance par participant ciblé ;
- `two_people` : combinaisons de deux participants ;
- `three_people` : combinaisons de trois participants ;
- `all_people` : question où tous les participants sont utilisés, par exemple classement.

Règle importante :
- un participant ne doit pas répondre à une question qui parle de lui si on veut éviter l'auto-évaluation, sauf si l'admin l'autorise.

Champ possible à ajouter sur `questions` :
- `allow_self_target` : booléen.

---

## Confidentialité MVP

Dans la première version :
- les réponses sont stockées ;
- seuls les admins peuvent les voir ;
- les participants ne voient aucune réponse après avoir répondu ;
- aucune page publique ne révèle les résultats.

C'est important pour éviter que les gens adaptent leurs réponses ou se vexent trop tôt.

---

## Révélation progressive — phase 2

Cette partie ne doit pas bloquer le MVP.

Idées possibles :

## Option A — révélation sur le site

Chaque participant revient sur son profil et voit progressivement :
- les réponses qui parlent de lui ;
- une réponse par jour ;
- ou une réponse par catégorie ;
- ou les réponses débloquées par l'admin.

Tables à ajouter :
- `reveal_batches` ;
- `revealed_answers`.

## Option B — email

Envoyer des mails du type :
> Nouvelle réponse débloquée sur ton profil T24.

Besoin futur :
- service email ;
- templates ;
- gestion des désinscriptions ou au moins consentement clair.

## Option C — SMS

Envoyer des SMS courts pour teaser.

Besoin futur :
- service SMS ;
- validation du format téléphone ;
- consentement explicite ;
- attention au coût.

Recommandation :
- commencer par la révélation sur le site ;
- ajouter l'email ensuite ;
- garder le SMS pour plus tard si ça apporte vraiment quelque chose.

---

## Architecture technique proposée

## Frontend

Application web dynamique.

Responsabilités :
- afficher les pages participant ;
- afficher les formulaires de réponse ;
- afficher l'admin ;
- appeler l'API backend ;
- gérer les états de chargement / erreur.

## Backend

API serveur.

Responsabilités :
- gérer les participants ;
- gérer les questions ;
- générer les instances de questions ;
- enregistrer les sessions ;
- enregistrer les réponses ;
- protéger les routes admin ;
- préparer les futures révélations.

## Base de données

Base relationnelle recommandée, car les relations sont importantes :
- participants ;
- questions ;
- instances ;
- sessions ;
- réponses.

---

## Routes API proposées

## Public / participant

- `GET /api/participants`
  - liste les participants actifs.

- `POST /api/sessions`
  - crée ou reprend une session.
  - body : `participantId`, `email`, `phone`, éventuellement `secretCode`.

- `GET /api/sessions/:sessionId/questions`
  - renvoie les questions à afficher pour cette session.

- `POST /api/sessions/:sessionId/answers`
  - sauvegarde une réponse.

- `POST /api/sessions/:sessionId/complete`
  - marque la session comme terminée.

## Admin

- `GET /api/admin/participants`
- `POST /api/admin/participants`
- `PATCH /api/admin/participants/:id`
- `DELETE /api/admin/participants/:id` ou désactivation logique

- `GET /api/admin/questions`
- `POST /api/admin/questions`
- `PATCH /api/admin/questions/:id`
- `DELETE /api/admin/questions/:id` ou désactivation logique

- `POST /api/admin/questions/generate-instances`
  - génère les questions concrètes à partir des modèles.

- `GET /api/admin/answers`
  - consulte les réponses.

- `GET /api/admin/export`
  - export JSON / CSV.

---

## Priorités de réalisation

## MVP 1 — collecte simple

Objectif : pouvoir faire jouer les potes et stocker les réponses.

À faire :
1. base de données ;
2. page admin participants ;
3. page admin questions ;
4. génération simple des questions ;
5. page accueil participant ;
6. page questionnaire ;
7. stockage des réponses ;
8. page merci ;
9. accès admin protégé.

Non inclus :
- envoi mail ;
- envoi SMS ;
- révélation automatique ;
- scoring avancé ;
- vraie authentification participant.

## MVP 2 — exploitation des réponses

Objectif : rendre les réponses utilisables.

À faire :
1. dashboard admin des réponses ;
2. filtres par participant / question / cible ;
3. export CSV / JSON ;
4. aperçu “ce qui a été dit sur X”.

## Phase 3 — révélations

Objectif : débloquer les réponses progressivement.

À faire :
1. page profil participant ;
2. système de réponses révélées ;
3. choix manuel admin des révélations ;
4. éventuellement mails ;
5. éventuellement SMS.

---

## Points d'attention pour l'agent développeur

## 1. Ne pas surcomplexifier l'authentification au début

Pour le MVP, l'objectif est un jeu privé entre amis.

Solution simple :
- admin protégé par mot de passe ;
- participant identifié par choix du profil + email + téléphone ;
- option code secret par participant si nécessaire.

## 2. Prévoir les questions dynamiques dès le début

Ne pas stocker uniquement du texte figé.

Il faut pouvoir gérer :
- une personne cible ;
- deux personnes cibles ;
- trois personnes cibles ;
- tout le groupe ;
- des réponses structurées.

## 3. Ne pas afficher les réponses côté participant dans le MVP

Même si les données existent, aucune route publique ne doit permettre de lire les réponses.

## 4. Garder le ton éditable par l'admin

Les questions doivent être modifiables facilement parce que le ton est central : drôle, taquin, motivant.

## 5. Prévoir l'export

Même si l'interface de révélation n'est pas prête, l'admin doit pouvoir récupérer les réponses.

---

## Questions ouvertes à clarifier plus tard

- Est-ce que chaque participant doit répondre à toutes les questions ou seulement à un échantillon ?
- Est-ce qu'un participant peut répondre à une question qui parle de lui ?
- Est-ce qu'on veut un code secret par participant ?
- Est-ce qu'on veut des avatars / images pour rendre la page d'accueil plus marrante ?
- Est-ce que les réponses doivent être anonymes lors de la révélation ?
- Est-ce que les révélations seront manuelles ou programmées ?
- Est-ce que les numéros de téléphone sont vraiment nécessaires dès le MVP ?

---

## Livrable attendu pour le premier agent développeur

L'agent qui réalise le site doit commencer par livrer :
- une application web fonctionnelle ;
- une base de données ;
- une interface admin minimale ;
- un parcours participant complet ;
- le stockage fiable des réponses ;
- aucune révélation côté participant pour l'instant.

Critère de succès :
> On peut créer des participants, créer des questions, faire répondre chaque personne, puis retrouver toutes les réponses côté admin.
