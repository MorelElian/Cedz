# Questions et précisions avant de coder

Ce document reprend les décisions écrites dans `PLAN_ENVOI_REPONSES.md` et liste uniquement les points à préciser. Aucun développement ne doit commencer avant validation des décisions importantes.

## Ce que j'ai compris et que je considère comme validé

- Chaque participant aura un compte associé à son profil existant.
- L'admin attribuera le mot de passe initial.
- Un participant ne pourra pas modifier les réponses données au questionnaire.
- Chaque participant aura une page privée avec ses réponses et les révélations déjà reçues à son sujet.
- Les auteurs des réponses seront toujours visibles.
- Les mails seront courts et envoyés deux ou trois fois par semaine.
- L'admin verra les dix prochains mails proposés et devra les valider.
- L'admin pourra remplacer une proposition par une autre. -> Non il pourra demander à regénérer une autre.  
- Les mails et traitements seront générés par des règles déterministes, sans LLM.
- Le style des mails reprendra le thème Cedz, le logo et la photo de l'auteur.
- Les formats de mail seront différents pour réponse libre, duel, trio, séparation en deux groupes et classement.
- Le `lap_time` sera ignoré dans les mails et les statistiques.
- L'automatisation de l'envoi sera traitée plus tard.

## Questions indispensables

### 1. Quand une réponse devient-elle visible sur la page du participant ?

Je recommande de n'afficher dans « Ce que les gens pensent de moi » que les révélations effectivement envoyées. Sinon, un participant pourrait se connecter et découvrir toutes les réponses avant de recevoir les mails. 

Choix à confirmer :

- uniquement après l'envoi du mail correspondant ; OUI 
- dès que l'admin accepte le mail ;
- toutes les réponses importées immédiatement. NON 

### 2. Que signifie exactement « accepter » dans l'admin ?

Deux comportements différents apparaissent dans le document initial : validation pour un envoi le lendemain à 8 h, puis envoi déclenché quand l'admin accepte.

Je recommande : accepter place le mail dans la file du prochain envoi à 8 h, avec un bouton séparé « Envoyer maintenant » réservé aux tests.

À confirmer :

- acceptation et envoi immédiat ; ENVOI IMMEDIAT OUI 
- acceptation puis choix manuel de la date.

### 3. Les dix prochains mails sont-ils globaux ou par participant ?

Je suppose qu'il s'agit des dix prochains mails sur l'ensemble du groupe, avec des destinataires variés.

Faut-il garantir qu'une personne n'apparaisse pas deux fois dans ces dix propositions ? OUI A CHAQUE FOIS c'EST UN MAIL EXACTEMENT PAR PERSONNE 

### 4. Que fait le bouton « Refresh » ?

Je recommande que la proposition remplacée retourne dans le stock et puisse réapparaître plus tard. Il faudrait un second bouton « Rejeter définitivement » pour une réponse que tu ne veux jamais envoyer.

À confirmer :

- remettre la proposition dans le stock ; 
- l'écarter définitivement ;
- demander le comportement à chaque refresh. OUI CELUI LA 

### 5. Qui reçoit une réponse de duel ou de trio ?

Une réponse à un duel peut produire deux révélations différentes :

- pour la personne choisie : « Il t'a choisi » ;
- pour l'autre : « Il ne t'a pas choisi ».

Un trio peut produire trois révélations. Je recommande donc de générer une proposition indépendante pour chaque personne citée, sans forcément les envoyer la même semaine. OUI EXACTEMENT 

Veux-tu envoyer la réponse à tous les participants du duel ou trio, ou uniquement à la personne sélectionnée ? AUX TROIS PERSONNES MAIS PEUT-ÊTRE PAS LE MÊME JOUR 

### 6. Que montre le mail « séparation en deux groupes » ?

Tu as écrit « Il t'a mis… Voilà le bilan de la question ». Cela peut vouloir dire :

- montrer uniquement le camp dans lequel le destinataire a été placé ;
- montrer les deux groupes complets ; JE VEUX MONTRER LES DEUX GROUS 
- montrer le camp du destinataire et un résultat agrégé, sans révéler tous les autres noms.

Comme tu veux que chacun voie seulement ce qui le concerne, je recommande la troisième option.  NON 2ème option 

### 7. Que signifie « Découvre son classement » ?

Pour un classement des dix, le mail peut afficher seulement :

- la position du destinataire ;
- la personne juste devant ;
- un bouton ouvrant le classement complet de l'auteur. Non pas ça 

Le classement complet révèle aussi les positions des neuf autres participants. Est-ce une exception assumée à la règle « seulement ce qui les concerne » ? Non tu as réison on ne verra  que ton placement et celui de la personne de devant. 

### 8. Comment calculer le classement moyen visible sur la page ?

Je propose de calculer, pour chaque discipline, la moyenne uniquement à partir des classements déjà révélés à ce participant. Cela permet à la statistique d'évoluer au fil des mails sans dévoiler les classements encore cachés.

À confirmer : moyenne basée sur :

- les classements déjà révélés ; oui exacteement 
- tous les classements importés dès le départ ; NON 
- les classements complets que le participant a ouverts sur le site. NON 

### 9. Que faire des curseurs et réponses numériques ?

Ce type existe dans l'export mais n'a pas encore de modèle de mail validé.

Proposition :

> « Gustave estime que tu commenceras à regretter d'être venu après 43 minutes. Il te connaît bien, ou il te méprise correctement. »

Veux-tu envoyer chaque estimation individuellement avec son auteur, ou attendre plusieurs réponses pour envoyer une moyenne ? Nan même chose que pour les réponses ave texte 

### 10. Comment fonctionne « Tu souhaites lui répondre ? » ?

Je suppose que le lien ouvre la révélation sur le site avec un petit champ de réponse.

Points à décider :

- la réponse est-elle visible uniquement par l'auteur initial ? OUI 
- l'auteur reçoit-il un mail quand on lui répond ? NON 
- l'admin doit-il valider cette réponse ? NON 
- peut-on répondre une seule fois ou créer une conversation ? PAS DE CONVERSATION 
- la réponse peut-elle être modifiée ou supprimée ? NON 

Je recommande une réponse unique, non modifiable, visible par l'auteur initial et par l'admin. Cela évite de construire immédiatement une messagerie complète.

## Questions sur les comptes

### 11. Le participant peut-il changer son mot de passe ?

Même pour un petit site, les mots de passe devront être stockés sous forme de hash et jamais en clair. OUI EXACT

Je recommande pour la première version : mot de passe initial défini par l'admin, changement facultatif depuis le compte, et réinitialisation manuelle par l'admin en cas d'oubli. EXACTEMENT 

### 12. Que devient l'ancien accès au questionnaire ?

Choix possibles :

- le questionnaire reste accessible comme aujourd'hui et le compte sert seulement aux nouvelles pages ; 
- il faut désormais être connecté pour ouvrir le questionnaire ; OUI ON VA FAIRE CA car des gens n'ont pas encore répondu au questionnaire. CEUX QUI ONT REPONDU ENTIEREMENT n'ont plus accès au questionnaire
- le questionnaire est définitivement fermé maintenant que les réponses sont exportées.

### 13. Quelle page apparaît après connexion ?

Je propose :

1. photo et nom du participant ;
2. dernier contenu reçu ;
3. classement moyen nage, vélo et course ;
4. historique des révélations ;
5. section repliable « Mes réponses » classée par catégorie. 
Très bien 

## Questions sur l'import et l'administration

### 14. L'export JSON devient-il la source définitive ?

Faut-il prévoir un seul import initial, ou pouvoir importer plus tard un nouvel export contenant des réponses supplémentaires ? Il y aura des exports plus tard. 

Je recommande un import rejouable sans doublons, utilisant l'ID de réponse et l'ID d'instance comme identifiants. Cela protège contre un double clic ou un nouvel export partiel. TRES BIEN 

### 15. Que signifie « enlever une réponse » ?

Possibilités :

- la masquer sans la supprimer ;
- la supprimer définitivement ;
- empêcher seulement sa transformation en mail.

Je recommande de la masquer avec un motif, afin de conserver l'historique et d'éviter les suppressions accidentelles. Ca on aura pas besoin car je validerais a la mano les réponses

### 16. L'admin peut-il modifier le texte avant l'envoi ?

Le système peut rester entièrement déterministe tout en permettant à l'admin de corriger une faute ou la phrase d'introduction.

Je recommande de conserver séparément : 

- la réponse originale, jamais modifiée ;
- le contenu final du mail, éditable avant validation ;
- une copie exacte du mail envoyé.
PARFAIT

### 17. Comment équilibrer les envois ?

Je recommande que le générateur évite automatiquement :

- deux mails consécutifs au même destinataire ;
- deux réponses consécutives du même auteur ;
- trop de contenus négatifs pour la même personne ;
- l'envoi d'un duel aux deux concernés le même jour ;
- une répétition du même type de question.

Souhaites-tu une répartition strictement équitable entre les dix participants, ou seulement un tirage qui essaie de rester équilibré ?
Nan seulement tirage au sort a chaque fois, on essaye juste de faire un truc différent de l'ancien : type de réponse difféerent si possible 

## Questions sur les phrases d'introduction

### 18. Comment tourner les quinze phrases ?

Je recommande une rotation indépendante par participant : une personne ne revoit pas une phrase avant d'avoir parcouru toute la liste. Cela évite que tout le groupe reçoive la même introduction le même jour. Oui réponse indépendantes 

Faut-il autoriser l'admin à remplacer manuellement la phrase proposée ? Oui l'admin doit pouvoir les ajouter directement sur 
LEs phrases c'est toi qui va les créermais je veux pouvoir modifier ou delete ou en rajouter. 

### 19. Les phrases dépendent-elles du type de contenu ?

Certaines introductions peuvent convenir à une pique mais être étranges avant un petit mot motivant. On peut :

- utiliser une seule liste universelle ;
- classer les phrases par ton : pique, motivation, classement, neutre ;
- associer chaque phrase à certains types de mail.

Je recommande au minimum deux tons : « pique » et « positif ». Oui très bien 

## Suggestions de structure avant développement

### A. Séparer une réponse d'une révélation

Une réponse importée est une donnée brute. Une révélation est un contenu destiné à une personne précise. Une réponse de trio peut donc créer trois révélations différentes.

Cette séparation facilitera l'historique, la validation et le calcul de ce que chaque participant est autorisé à voir. 
OUI 

### B. Utiliser des statuts explicites

Proposition de cycle :

`candidate` → `in_review` → `approved` → `scheduled` → `sent`

Avec deux sorties possibles : `skipped` pour remettre plus tard et `rejected` pour ne jamais envoyer.
 OUI 

### C. Figer le contenu validé

Au moment de l'acceptation, il faut enregistrer le sujet, le HTML, le destinataire et les données utilisées. Ainsi, une future modification de template ne changera pas silencieusement un mail déjà validé.
OIO 

### D. Ne révéler que ce qui est envoyé

La page participant devrait être alimentée par les révélations envoyées, pas directement par toutes les réponses brutes. C'est la règle la plus importante pour préserver le feuilleton.
OIO

### E. Commencer sans automatisation

Pour la première étape, un bouton admin « Envoyer le mail validé » permettrait de tester les formats et le routage. La tâche planifiée à 8 h pourra venir ensuite sans changer le modèle de données.

## Découpage de travail proposé après validation

1. Import fiable des réponses et modèle de données des révélations.
2. Comptes participants et contrôle d'accès.
3. Pages privées et règle de visibilité.
4. Génération déterministe des différents types de révélations.
5. File de review admin et remplacement des propositions.
6. Templates HTML des mails et envoi manuel de test.
7. Réponses aux révélations.
8. Planification automatique à 8 h et suivi des erreurs.

Ce découpage est une suggestion de discussion, pas un début d'implémentation.

Ok très bien. Ensuite rapelle toi d'un truc c'est que le site est en ligne quand je vais push mes modif avec railway ca doit fonctionnet et je ne dois pas perdre ce qui a été fait précédemment. 
Pour l'instant on teste tout ça en local. 
JE t'ai mis dans mail.txt les mails pour tout le monde donc tu me formattes ça et tu mets ça en csv. 