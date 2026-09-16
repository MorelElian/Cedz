# Questions suggérées et question du jour — cadrage avant développement

Ce document précise le plan de PLAN_NEW_QUESTIONS.md. Il ne déclenche aucun développement. L'objectif est d'ajouter de la matière au jeu avant le T24, sans modifier les 30 questions déjà attribuées ni dévoiler prématurément les réponses.

## Vision retenue

Depuis son espace connecté, chaque participant voit, dans cet ordre :

1. sa dernière révélation, comme aujourd'hui ;
2. une **question du jour** courte à laquelle répondre ;
3. un bouton très visible **« Proposer une question »** ;
4. les rubriques existantes : classements, historique des révélations et ses réponses.

Une proposition n'est jamais publiée automatiquement : elle attend une décision de l'admin. Les règles de génération, de sélection et d'envoi restent statiques et déterministes ; aucun LLM n'intervient.
 Non le bouton doit être a cote de "comepleter le questionnaire" pour ce ux qui n'ont pas encore compléter le questionnaire 

## Découpage proposé

### 1. Banque de questions et cycle de vie

Séparer clairement :

- une **suggestion** : idée soumise par un participant ;
- une **question approuvée** : question mise dans la banque ;
- une **instance du jour** : version concrète tirée pour une personne et une date ;
- une **réponse du jour** : réponse liée à cette instance.

Cycle proposé : brouillon → soumise → approuvée ou refusée → active / inactive.

Une fois approuvée, l'admin peut toujours réécrire le texte, changer la catégorie, le type ou la désactiver. La suggestion originale reste conservée avec son auteur pour comprendre son intention, mais ne sera pas visible aux autres participants.

### 2. Écran participant

La carte « Question du jour » doit rester légère :

- question rendue avec les personnes concernées ;
- formulaire adapté au type ;
- bouton unique « Répondre » ;
- état clair une fois la réponse enregistrée ;
- pas de bouton pour modifier la réponse dans la première version.
Oui ca doit être petit, mais quand même clair 
La carte « Proposer une question » ouvre un formulaire court :

- texte de la question ;
- type choisi, avec « Réponse libre » sélectionné par défaut ;
- éventuellement une catégorie ;
- explication que l'admin doit l'approuver.

Une même personne ne doit pas pouvoir soumettre accidentellement dix fois la même proposition : un brouillon par personne et une confirmation avant envoi suffisent pour la V1.

### 3. Tirage de la question du jour

Pour chaque participant connecté, le serveur sélectionne une instance compatible dans la banque active. Le résultat doit être enregistré : un rafraîchissement de page ne doit ni changer la question ni créer une deuxième réponse.

Règles proposées :

- exclure les questions auxquelles la personne a déjà répondu ; oui mais on eput reprendre une question si le nom du participant est différent 
- exclure les instances qui la ciblent elle-même, sauf si la question l'autorise explicitement ; OUI 
- préférer un type différent de sa dernière question du jour ; NON 
- éviter de réutiliser immédiatement le même participant cible ; OUI 
- si aucune question compatible n'existe, afficher un état sympathique plutôt qu'une erreur ;
- la date de référence et le renouvellement sont gérés côté serveur, pas dans le navigateur.

### 4. Administration

Ajouter deux rubriques dans l'admin :

**Suggestions à examiner**

- auteur, date, texte proposé et type demandé ;
- aperçu de la façon dont la question serait rendue ;
- modifier puis approuver ;
- refuser avec une note interne facultative.

**Banque des questions du jour**

- toutes les questions actives/inactives ;
- source : catalogue initial ou suggestion d'un participant ;
- type, catégorie et nombre de réponses reçues ;
- modification, activation/désactivation et suppression prudente.

Les réponses du jour rejoignent la vue des réponses existante, avec un filtre « Questions du jour », afin qu'elles puissent ensuite alimenter les révélations si la question s'y prête.

### 5. Données et compatibilité

La base actuelle possède déjà une banque de questions, des instances et des réponses. Il faut préserver les réponses importées et les révélations existantes.

La solution la plus sûre est d'ajouter des champs/tables dédiés au cycle des suggestions et d'indiquer qu'une instance appartient au flux « quotidien ». Les 30 questions du questionnaire restent inchangées : un participant ayant terminé ne se retrouve jamais avec un questionnaire rouvert ou rallongé.

Les ajouts doivent être créés au démarrage par migration non destructive, afin que le push Railway n'efface ni comptes, ni réponses, ni mails envoyés. Les nouveaux secrets éventuels restent dans les variables Railway, jamais dans Git.

## Décisions indispensables

Réponds directement sous chaque question.

### 1. La question du jour est-elle une réponse supplémentaire ?

Je comprends qu'elle est distincte des 30 questions du questionnaire initial et qu'elle n'en modifie pas le compteur.

- oui, une question bonus par jour / par période ;
- non, elle doit seulement remettre en avant une question non répondue du questionnaire.
Nan il y a la banque de qeustions , le questionnaire en était issue, mais maintenant la question du jour aussi. 

### 2. Même question pour tout le groupe ou tirage individuel ?

Le plan dit « randomly pooled from questions » et « randomly pooled from other participants ».

- **recommandé :** chaque participant reçoit sa propre question, avec une cible tirée pour lui ; OUI 
- une même question thématique est donnée à tous, avec des cibles éventuellement différentes ; NON 
- une même instance exacte est donnée à tout le monde. NON 

### 3. Que signifie « du jour » ?

- renouvellement strict chaque jour à minuit ; NON 
- une nouvelle question apparaît seulement après réponse ;
- **recommandé :** question figée par personne jusqu'à sa réponse, puis délai avant le prochain tirage ; OUI 
- rythme manuel décidé par l'admin.

Cette décision évite le cas où une personne ouvre le site le lendemain et perd sa question sans avoir répondu.
Côté admin je dois pouvoir cahnger la question affiché / pouvoir la regénrer

### 4. Quels types sont autorisés à la suggestion en V1 ?

Les interfaces ne coûtent pas toutes la même chose.

- **recommandé :** réponse libre, choix entre 2, choix entre 3 et note/curseur ; OUI ca c'est bien 
- ajouter aussi séparation en deux groupes ;
- ajouter aussi classements des 10 ;
- laisser chaque type disponible dès le début.

Les groupes et les classements exigent que la personne proposant définisse des intitulés cohérents ; ils sont donc mieux gardés pour une deuxième étape, sauf volonté contraire.

### 5. Qui décide des personnes ciblées ?

Pour une suggestion comme « Qui serait le meilleur coach ? », il faut savoir qui apparaît dans la question.

- l'auteur de la suggestion choisit les personnes ciblées ; 
- le système tire les cibles au moment de publier ;
- **recommandé :** l'auteur propose le texte et le type, puis l'admin choisit/valide les cibles et les règles lors de l'approbation. Nan les mecs qui appraissent dans les questions sont générer aléatoirement quand la question est propsoé a quelqun 

### 6. Les suggestions doivent-elles utiliser des placeholders ?

Exemple : « Entre {person1} et {person2}, qui… ? »

- oui, l'auteur peut saisir des placeholders avec une aide ;
- non, il écrit une question simple et l'admin ajoute les cibles ; 
- **recommandé :** formulaire guidé selon le type, sans demander d'écrire des placeholders. OUI 

### 7. L'auteur d'une suggestion doit-il être visible ?

L'admin le voit forcément. Pour les participants et les révélations futures :

- jamais visible ;
- visible seulement dans la réponse/révélation ;
- visible dès la publication de la question ;
- **recommandé :** invisible à la publication, auteur visible seulement si la réponse devient une révélation, conformément au fonctionnement actuel. OUI 

### 8. Peut-on répondre plusieurs fois à une question du jour ?

- une seule réponse définitive ; OUI
- une réponse modifiable tant que la question est active ;
- plusieurs réponses, avec la dernière utilisée.

Je recommande une réponse unique, cohérente avec les révélations et plus simple à relire.

### 9. Les réponses aux questions du jour servent-elles aux mails ?

- oui, tous les types compatibles alimentent exactement la même file de révélations ; OUI 
- oui, mais l'admin doit cocher explicitement « utilisable pour les révélations » ;
- non, elles sont seulement visibles dans les réponses.

Je recommande le deuxième choix : cela évite qu'une question proposée pour rire parte automatiquement dans les mails.

### 10. Peut-on suggérer une question après avoir terminé le questionnaire ?

Je suppose que oui : la nouvelle carte est dans l'espace compte et non dans le questionnaire.

- oui, pour tous les comptes actifs ; OUI
- seulement pour les personnes ayant terminé les 30 questions ;
- seulement pour les personnes que l'admin autorise.

### 11. Limites et modération

Choix nécessaires pour éviter le spam et les malentendus :

- nombre maximal de suggestions par personne et par jour/semaine ; NON 
- longueur maximale de la question ; OUI 
- l'admin peut-il supprimer définitivement une suggestion refusée, ou seulement la conserver en archive ?

Proposition V1 : 3 suggestions soumises maximum par personne et par semaine, 300 caractères, et archive admin des refus.

### 12. La question du jour doit-elle être visible même si le questionnaire initial est incomplet ?

Le site autorise actuellement certains participants à finir leurs 30 réponses après connexion.

- **recommandé :** non, priorité à « Finir mon questionnaire » pour ne pas mélanger les flux ; OUI 
- oui, la question du jour est disponible immédiatement ;
- oui, seulement après un seuil de réponses au questionnaire.

## Manquements et risques repérés

1. **Épuisement de la banque.** Avec dix personnes et une question quotidienne individuelle, les combinaisons non répétées partent vite. Il faut soit une cadence souple, soit assez de questions approuvées. 

2. **Questions sans destinataire.** Une réponse libre générale est difficile à transformer en révélation privée. Une case « peut devenir une révélation » et une règle de ciblage sont importantes. Nan mais réponse libre c'est tu sais ca vise une personne donc il faudra un systeme de place holder 

3. **Question ambiguë pour les types structurés.** Un classement ou une séparation nécessite des libellés, une population et parfois une discipline ; le seul choix du type ne suffit pas.

4. **Effet spoiler.** Une réponse publiée dans « Mes réponses » est visible à son auteur, mais ne doit jamais apparaître dans « Ce que les gens pensent de moi » avant une révélation envoyée. 

5. **Fuseau horaire.** Si le renouvellement est journalier, il faut choisir explicitement l'heure et le fuseau, probablement Europe/Paris malgré Railway. EuropE PARIS 

6. **Doublons de sens.** Deux formulations presque identiques doivent pouvoir coexister dans les suggestions, mais l'admin doit voir les questions similaires avant approbation. C'est moi qui gererait

7. **Suppression après réponses.** Désactiver une question doit empêcher de nouveaux tirages, sans effacer les réponses ou les révélations qui existent déjà.

8. **Droits et confidentialité.** Les propositions et réponses sont des données privées : elles ne doivent apparaître ni dans les exports publics ni dans une URL devinable sans connexion.

9. **Mobile.** Le formulaire de suggestion doit être très court ; faire un classement de dix personnes au téléphone est une expérience distincte, à concevoir séparément. :w


10. **Déploiement Railway.** La base persistante doit déjà être celle utilisée en production. Une base SQLite locale non montée sur volume serait perdue lors d'un redéploiement ; avant d'ajouter cette feature, il faut confirmer le stockage persistant actuel.

## Critères d'acceptation une fois les décisions prises

- Une personne connectée voit une question du jour stable et ne peut répondre qu'une fois.
- Une réponse quotidienne n'augmente jamais le total des 30 questions historiques.
- Un participant peut soumettre une suggestion en quelques champs ; elle n'est visible que par lui et l'admin avant approbation.
- L'admin peut approuver, modifier, refuser, activer et désactiver les questions sans perdre les données existantes.
- Une question approuvée n'apparaît dans le tirage que selon les règles confirmées.
- Les révélations ne montrent que des contenus effectivement envoyés.
- Après push sur Railway, les anciennes réponses, comptes, révélations et nouveaux contenus restent présents.

## Hors périmètre de cette itération

- envoi automatique planifié ;
- SMS / WhatsApp ;
- conversations entre participants ;
- LLM pour générer, modérer ou reformuler les questions ;
- modification d'une réponse après validation ;
- notifications push.
