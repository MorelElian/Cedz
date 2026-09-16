# PokeCedz 
Final goal is to provide another completely different feature in the webapp wher each user has its pokemon (which represents him) and that can fight against others pokemon
## Representation 
Each participant already has a pokemon representing him 
Pokeced has to progress with xp.
pokecedz has five different "caracteristics" that define their "type" : 

Health
Alcohol
Chiale
Speed
Power
Patrimoine

Attack effectiveness depends on attack type that i will describe later on. 


Each pokemon will have 4 capabilities that I will define + two others that we will unlock when it passes some level (and that he can switch too). 
Every capability can have different effects: 
- attack someone that produces damages depending on you stats 
- increase some of your capability 
- special case ? 
suggest me anything else ?that could introduce interesting mechanics. 

Each attack will trigger an animation? This part I am not sure of how to proceed, how can i make IA do it without explosing the cost, what is a simple way to make it fun 

Every Pokecedz has three different form, baby, normal, bulked. They are anthropomoprh (meaning they look like humans). This depends on their level. 

Pokecedz can gain xp when entering the session they have done 

## Xp System
### Xps
People will have two ways to gain xp. 
They can enter the session they have done: 
Session is defined by its type : swimming, running, cycling, Muscu, Other
Time: 
Difficulty ? (i don't know if it has to be static or computed by us) 
Date 
Hour 
We need a formula to comput ehow much xp do you gain depending on the activity. 
I want several different things to influence the gain of xp, called xp boosts
- when you are on a day streak you gain more xp 
- if you do personal best you gain more xp (unlock after 10 activities) 
- if you do it early < 9h du mat or > 21h , you gain more xp 
- If you beat someone today (that just entered an activity), you gain more xp 

### Levels 
Simple system of levels where it gets more and more difficult to gain levels. At the same time, we should think of a way to change the way you gain xp (lke when you ha ve a higher level your strategy evolves to cnsisency and combo ?, also their are combo only available when you increase level) 
But overall it should remain more and more difficult if you are just go without trying to combo anything. 
When you gain a level, all of your stat increases depending on multiplier i will define for everyone. Also you gain points taht you can distributes. 
Player is not aware of the multiplier I'll give. 
I need an admin page where i ca nset those values + multipliers. 

## Fight 
### Global context 
it's a pokemon style combat, so turn by turn. 
One will be played by the player, who plays the its own caracter and the others is handled by the Computer. 
The fight scene is one on the left one on the right 
The background is a scene, and I will describe a few and then it's randomly chosen. 
You gain xp when you beat someone at the end of the fight.
### Turn By turn 
You choose your attack or your item to use  
Do the stuff and compute the animation 

## Attacks 
An attack can have one or more type. This will affect the computation. 
An attack can 
- attack the guy 
- do some stuff on you 
- increase temporarily one of your caracteristic
- 

### Attacks that attack
Propose me here interesting mechanics that take into account: 
- the stats of the guy attacking 
- the type of the attack 
- the stats of the guy defending 
? 
Other stuff ? 

### Increases your stats 
Depends first of all on your stats, not on ennemi stats 
Can it depend on something else ? 

## Caracteristics 

Health
### Alcohol
The caracteristics that is the most defined by items more than by your stats 
The alcohol increases your defense a lot . But augment the chance ou miss your attacks of type "speed" / "power" . 
### Alcohol absorption 
THis stats will tell you how much you get impact by the items or attacks that gives alcohol 
## Chiale 
Caracteristic you want to decrease, because it increases the damage you take.

### Speed
Self explanatory, the kind of caracteristics that increases the power of attack of type speed. 
This increases your resistent to power attacks 
### Power
same as speed
But the opposite is suppose 
### Patrimoine
This is defnied by me and cannot be changed or increase during the game. 
This increases the impact of 

## Items 
Items can be bought using money you earn during combats.
Beer 
Increases Alcohol 
Vodka 
Increases alcohol  decreases smart 
Mouthgard 
increases ? 
paquet de schmeg 
Increases Smart Decreases 
Paquet de bonbons 
Masque de la honte  

