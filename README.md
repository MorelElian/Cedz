# Cedz Are Shooting

Application Flask locale pour collecter les réponses du groupe, préparer des
révélations et donner à chaque participant un espace personnel.

## Lancer en local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Pour tester les envois Gmail réels, lancer plutôt
`./scripts/run_local_gmail.sh` et saisir le mot de passe d'application demandé.

Ouvrir ensuite <http://127.0.0.1:5000>.

- Administration : <http://127.0.0.1:5000/admin>
- Mot de passe local initial : `t24-admin`
- Base locale : `instance/t24.sqlite3`

Au premier lancement, les dix profils illustrés et les 61 questions du catalogue
T24 sont créés. Tout est ensuite modifiable ou désactivable dans
l'administration.
Lors d'une mise à jour d'une ancienne base, les six questions de démonstration
sont simplement désactivées afin de préserver les éventuelles réponses liées.

L'administration permet aussi de déposer le logo du site et deux photos par
participant (grande photo de choix et petite photo de profil). Les fichiers PNG,
JPEG, GIF et WebP de 5 Mo maximum sont stockés dans `instance/uploads/`.

Une seule participation principale est utilisée par participant. Depuis
**Administration → Participants**, définir son mot de passe avant de lui donner
accès. Il se connecte avec son nom affiché et ce mot de passe. Un questionnaire
commencé peut être repris ; un questionnaire terminé reste verrouillé.

## Importer les réponses existantes

Dans **Administration → Réponses**, importer directement l'export JSON. Un même
fichier peut être importé plusieurs fois : les réponses déjà connues ne sont pas
dupliquées. L'import est transactionnel et reconstruit aussi l'avancement des
questionnaires. Les exports placés dans `answers/` et le fichier local
`mails.csv` sont ignorés par Git pour ne pas publier de données privées.

## Préparer les révélations

L'onglet **Révélations** propose exactement dix cartes, une par participant.
Chaque carte peut être retouchée, remise à plus tard ou rejetée. L'acceptation
fige le contenu puis l'envoie réellement avec Gmail. Si Gmail refuse l'envoi, la
révélation reste en attente et peut être retentée. L'adresse de chaque
participant se règle dans l'onglet **Participants**.

Le participant ne voit que les révélations marquées comme envoyées. Il peut
répondre une seule fois à chacune ; cette réponse est visible uniquement par
l'auteur de la réponse d'origine et par l'administrateur.

Avant d'envoyer le lien aux joueurs, finaliser les participants et les questions,
puis cliquer sur « Générer les instances ». Ne plus régénérer après le début du
jeu : une modification de la population changerait les sessions déjà ouvertes.

Pour une question de comparaison à deux, le générateur crée un cycle aléatoire :
chaque participant apparaît deux fois, sans produire toutes les combinaisons.
Chaque répondant voit un tirage stable de 30 questions, dont les trois
classements obligatoires, avec au maximum deux variantes de chaque question
ciblée. Les cibles des deux variantes sont différentes. Le choix est stable et
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
export T24_MAIL_MODE="gmail_api"
export T24_GMAIL_USER="cedzt24@gmail.com"
export T24_GMAIL_CLIENT_ID="client OAuth Google"
export T24_GMAIL_CLIENT_SECRET="secret OAuth Google"
export T24_GMAIL_REFRESH_TOKEN="refresh token OAuth Google"
export T24_MAIL_FROM="Cedz Are Shooting <cedzt24@gmail.com>"
export T24_PUBLIC_BASE_URL="https://cedz-production.up.railway.app"
```

Le mode historique `gmail` utilise SMTP et reste disponible pour les essais
locaux. En production Railway Hobby, utiliser `gmail_api`, qui communique avec
Google exclusivement en HTTPS.

### Obtenir les identifiants Gmail API

1. Créer un projet dans Google Cloud Console et activer **Gmail API**.
2. Configurer l'écran de consentement OAuth en **External**, avec
   `cedzt24@gmail.com` comme utilisateur de test.
3. Ajouter uniquement le scope
   `https://www.googleapis.com/auth/gmail.send`.
4. Créer un client OAuth **Web application** et ajouter l'URI de redirection
   `https://developers.google.com/oauthplayground`.
5. Dans Google OAuth 2.0 Playground, ouvrir les réglages, activer **Use your own
   OAuth credentials**, puis renseigner le client ID et le client secret.
6. Autoriser le scope `gmail.send` avec `cedzt24@gmail.com`, échanger le code,
   puis copier le `refresh_token` dans Railway.

Un projet OAuth laissé en statut **Testing** produit un refresh token qui expire
au bout de sept jours. Avant de générer le jeton définitif, passer l'application
OAuth en **In production**. Les trois valeurs OAuth sont des secrets : ne jamais
les mettre dans Git, un fichier `.env` commité ou une capture d'écran.

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
   - `T24_MAIL_MODE=gmail_api`
   - `T24_GMAIL_USER=cedzt24@gmail.com`
   - `T24_GMAIL_CLIENT_ID` avec l'identifiant du client OAuth
   - `T24_GMAIL_CLIENT_SECRET` avec le secret du client OAuth
   - `T24_GMAIL_REFRESH_TOKEN` avec le refresh token OAuth
   - `T24_MAIL_FROM=Cedz Are Shooting <cedzt24@gmail.com>`
   - `T24_PUBLIC_BASE_URL=https://cedz-production.up.railway.app`
5. Dans **Settings → Deploy**, définir le healthcheck sur `/health`.
6. Dans **Settings → Networking**, cliquer sur **Generate Domain**.

Conserver une seule réplique tant que SQLite est utilisé. Le volume contient les
réponses et les images : sa suppression efface ces données, donc activer les
sauvegardes Railway avant d'ouvrir le questionnaire.
