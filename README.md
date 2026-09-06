# Cedz Are Shooting

MVP local Flask pour préparer les participants et les questions, collecter les
réponses du groupe, puis les consulter uniquement depuis l'administration.

## Lancer en local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Ouvrir ensuite <http://127.0.0.1:5000>.

- Administration : <http://127.0.0.1:5000/admin>
- Mot de passe local initial : `t24-admin`
- Base locale : `instance/t24.sqlite3`

Au premier lancement, les dix profils illustrés et les 59 questions du catalogue
T24 sont créés. Tout est ensuite modifiable ou désactivable dans
l'administration.
Lors d'une mise à jour d'une ancienne base, les six questions de démonstration
sont simplement désactivées afin de préserver les éventuelles réponses liées.

L'administration permet aussi de déposer le logo du site et deux photos par
participant (grande photo de choix et petite photo de profil). Les fichiers PNG,
JPEG, GIF et WebP de 5 Mo maximum sont stockés dans `instance/uploads/`.

Une seule participation principale est utilisée par participant. Un jeton de
reprise aléatoire est conservé dans le navigateur afin de retrouver et modifier
les réponses sans exposer la session avec la seule adresse email. Pour une
ancienne session créée avant cette version, définir un code secret participant
dans l'administration permet la reprise depuis un nouveau navigateur.

Avant d'envoyer le lien aux joueurs, finaliser les participants et les questions,
puis cliquer sur « Générer les instances ». Ne plus régénérer après le début du
jeu : une modification de la population changerait les sessions déjà ouvertes.

Pour une question de comparaison à deux, le générateur crée un cycle aléatoire :
chaque participant apparaît deux fois, sans produire toutes les combinaisons.
Chaque répondant voit au maximum deux questions par catégorie. Si le même modèle
est retenu deux fois, les cibles sont différentes. Le choix est stable et
pseudo-aléatoire parmi les questions qui ne concernent pas le répondant. Une
régénération sans changement conserve le même tirage.

## Configuration

Avant toute mise en ligne, définir des secrets propres :

```bash
export T24_SECRET_KEY="une-longue-valeur-aleatoire"
export T24_ADMIN_PASSWORD="un-mot-de-passe-solide"
export T24_SECURE_COOKIE=1
export T24_ENV=production
export T24_DATABASE="/chemin/persistant/t24.sqlite3"
```

Le téléphone participant est facultatif. Les réponses ne sont jamais exposées
par les routes publiques ; seule une session admin permet de les lire/exporter.

## Tests

```bash
.venv/bin/python -m pytest -q
source .venv/bin/activate
node --check static/js/*.js
```

Node.js 24 LTS, npm et npx sont installés localement dans le venv. Ils sont
disponibles après `source .venv/bin/activate` sans installation système.

## Personnaliser le visuel

- `static/css/background.css` contient uniquement le décor de fond.
- `static/css/app.css` contient la mise en page et les composants.

On peut donc remplacer ou ajuster l'ambiance de fond sans toucher aux écrans ni
à leur comportement.

## Mise en ligne

Cette application ne peut pas être un simple site statique : Flask doit tourner
sur un hébergement Python et SQLite doit vivre sur un disque persistant. Pour un
petit groupe, un seul service Flask suffit. Sauvegarder régulièrement le fichier
SQLite ; passer à PostgreSQL seulement si l'usage ou le nombre d'utilisateurs
augmente nettement.

### Railway

1. Mettre le projet dans un dépôt GitHub, puis choisir **New Project → Deploy
   from GitHub repo** dans Railway.
2. Dans le service, définir la commande de démarrage :
   `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60`.
3. Ajouter un volume au service, monté sur `/app/storage`.
4. Ajouter les variables Railway suivantes :
   - `T24_ENV=production`
   - `T24_SECURE_COOKIE=1`
   - `T24_DATABASE=/app/storage/t24.sqlite3`
   - `T24_UPLOAD_FOLDER=/app/storage/uploads`
   - `T24_SECRET_KEY` avec une longue valeur aléatoire
   - `T24_ADMIN_PASSWORD` avec un mot de passe administrateur solide
5. Dans **Settings → Deploy**, définir le healthcheck sur `/health`.
6. Dans **Settings → Networking**, cliquer sur **Generate Domain**.

Conserver une seule réplique tant que SQLite est utilisé. Le volume contient les
réponses et les images : sa suppression efface ces données, donc activer les
sauvegardes Railway avant d'ouvrir le questionnaire.
