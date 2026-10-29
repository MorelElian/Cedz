# Réponses, révélations et suivi admin — design

## Objectif

Faire de chaque réponse, du questionnaire initial comme des questions bonus, une source fiable et datée de candidats de révélations. L'admin doit pouvoir consulter, pour chaque participant, toutes les révélations envoyées et toutes celles encore disponibles.

## Constats confirmés

- `imported_answers` est déjà le registre dont part `generate_revelation_candidates`.
- Une réponse bonus crée une ligne importée et appelle le générateur dans la même transaction, mais n'écrit pas `source_created_at`.
- Le JSON local `answers/t24-reponses(1).json` est valide : 252 réponses et 666 candidats sont produits dans une base isolée.
- L'interface d'import ne recharge pas les données après succès et son message de résultat est trop vague.
- Les cartes Peloton ne peuvent pas dépendre de `final_content` seul : ce champ peut être vide avant édition alors que `revelation_payload` possède un repli formaté.

## Cycle de vie unique

`imported_answers` reste la source de vérité de toutes les réponses utilisables.

1. Le questionnaire initial crée ou met à jour une ligne datée avec sa session et sa réponse structurée.
2. Une réponse bonus utilise `source_key = daily:<daily_question_id>` et écrit `source_created_at = daily_questions.answered_at`.
3. Un import JSON conserve `createdAt` dans `source_created_at` et demeure idempotent par `source_key`.
4. Toute écriture réussie appelle `generate_revelation_candidates(commit=False)` avant le commit.
5. Au démarrage, les anciennes lignes bonus sans date sont réparées depuis `daily_questions.answered_at`, ou `imported_at` en repli.

La transaction est atomique : une bonus ne passe jamais à `answered` sans réponse importée liée, et une erreur de validation ne crée pas de candidat.

## Inventaire admin

Deux endpoints admin seront ajoutés.

- `GET /api/admin/revelation-inventory` : participant, `sentCount`, `readyCount` (`in_review`) et `remainingCount` (`candidate`).
- `GET /api/admin/revelation-inventory/<participant_id>` :
  - `sent`, filtré `status='sent'`, trié `sent_at DESC` ;
  - `remaining`, filtré `status IN ('in_review','candidate')`, avec `in_review` en premier puis `created_at DESC`.

`rejected` et `skipped` ne sont pas affichés dans le stock restant : ils ne sont plus envoyables. Les cartes portent statut, auteur, question, réponse typée, timestamp et identifiant.

## Interface admin

L'onglet « Suivi révélations » est desktop-first : rail de dix participants avec compteurs, fiche du participant sélectionné, colonne « Déjà révélées » et colonne « À révéler ». Les listes contiennent réellement toutes les cartes de la personne ; elles sont chargées seulement à la sélection afin de rester fluides.

L'historique global « Révélations envoyées » reste exclusivement filtré sur `sent` et ordonné de la plus récente à la plus ancienne.

## Import et rendu

Après un import, l'admin voit `X importées · Y mises à jour · Z candidats créés`, puis les réponses, propositions et inventaire se rechargent. Un import invalide reste atomique.

Les cartes ne présentent jamais du JSON brut ni une réponse vide : texte, curseur, choix/commentaire, comparaison, classement et groupes disposent tous d'un résumé lisible. Peloton prend `final_content` si disponible, sinon le contenu généré serveur, et affiche un état explicite quand aucune révélation n'est sélectionnée.

## Validation

- Une bonus répondue devient immédiatement une réponse importée datée et produit des candidats.
- Les anciennes bonus obtiennent un timestamp.
- Le JSON local reste importable et rejouable.
- L'inventaire retourne toutes les cartes envoyées/restantes du participant avec le tri défini.
- Les tests existants restent verts.
