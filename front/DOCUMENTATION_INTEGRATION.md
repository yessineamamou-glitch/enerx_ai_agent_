# Documentation de liaison EnerxV / EnerX Backend

## 1. Objectif

Le frontend `EnerxV` est une application Next.js. Le backend `EnerX-main/backend` est une API FastAPI.

À l'origine, le frontend affichait une interface fonctionnelle, mais toutes ses actions retournaient des données simulées. La liaison a été corrigée pour que le frontend appelle les routes HTTP du backend FastAPI.

Le rendu visuel de l'interface n'a pas été modifié.

## 2. Projets concernés

### Frontend

```text
C:\Users\Bejia\Desktop\Hackaton\EnerxV
```

### Backend local

```text
C:\Users\Bejia\.copilot\attachments\86fed46c-2796-443c-9b86-41c68ee4ebb8\EnerX-main\backend
```

### Backend actuellement utilisé par le frontend

```text
https://enerx.fastapicloud.dev
```

La présence d'une correction dans le backend local ne signifie pas automatiquement que cette correction est déployée sur cette URL distante.

## 3. Modifications du frontend

### 3.1 `lib/enerx/api.ts`

Fichier :

```text
C:\Users\Bejia\Desktop\Hackaton\EnerxV\lib\enerx\api.ts
```

Modifications :

- Suppression du transport simulé qui ignorait `endpoint` et `payload`.
- Ajout de vrais appels `fetch`.
- Détermination automatique de la méthode :
  - `GET` lorsqu'aucun payload n'est fourni ;
  - `POST` lorsqu'un payload est fourni.
- Envoi automatique du JSON avec `Content-Type: application/json`.
- Lecture de l'URL depuis `NEXT_PUBLIC_API_BASE_URL`.
- Gestion des réponses HTTP en erreur.
- Lecture des erreurs FastAPI au format `{ "detail": "..." }`.
- Ajout de la classe `ApiError`.

Configuration utilisée :

```env
NEXT_PUBLIC_API_BASE_URL=https://enerx.fastapicloud.dev
```

L'URL ne doit pas contenir `/docs`.

### 3.2 `components/enerx/dashboard.tsx`

Fichier :

```text
C:\Users\Bejia\Desktop\Hackaton\EnerxV\components\enerx\dashboard.tsx
```

Modifications :

- Ajout du chargement initial des projets avec `GET /project/`.
- Remplacement des routes frontend fictives par les routes backend réelles.
- Conversion des identifiants frontend texte vers les identifiants numériques backend.
- Adaptation des payloads envoyés au schéma Pydantic du backend.
- Adaptation des réponses backend vers les types utilisés par l'interface.
- Conservation des mêmes composants, écrans, boutons et comportements visuels.

Fonctions concernées :

- Vérification DID/KYC.
- Achat primaire de tokens.
- Création d'une annonce marketplace.
- Achat d'une annonce.
- Création d'un projet.
- Enregistrement d'une production et distribution des revenus.

### 3.3 `lib/enerx/types.ts`

Fichier :

```text
C:\Users\Bejia\Desktop\Hackaton\EnerxV\lib\enerx\types.ts
```

Ajouts :

```ts
backendId?: number
backendTokenId?: number
```

Ces propriétés permettent de conserver les IDs visuels du frontend tout en mémorisant les IDs numériques du backend.

Elles concernent :

- `Profile.backendId`
- `Project.backendId`
- `Project.backendTokenId`

### 3.4 `lib/enerx/mock-data.ts`

Fichier :

```text
C:\Users\Bejia\Desktop\Hackaton\EnerxV\lib\enerx\mock-data.ts
```

Modifications :

- Alignement des profils avec les utilisateurs seedés côté backend.
- Ajout des IDs backend :

| Profil frontend | ID backend | Nom backend | Compte Hedera |
|---|---:|---|---|
| `owner-1` | 1 | Rayen Segni | `0.0.10652075` |
| `investor-1` | 2 | Amen Beji | `0.0.10794965` |
| `investor-2` | 3 | Yassine Ammamo | `0.0.10872211` |

Les IDs visuels restent inchangés afin de ne pas modifier l'interface.

## 4. Mapping des routes frontend/backend

| Fonction | Ancienne route simulée | Route backend utilisée | Méthode |
|---|---|---|---|
| Chargement projets | aucune requête réelle | `/project/` | GET |
| KYC / DID | `/kyc/verify` | `/auth/did` | POST |
| Achat primaire | `/invest/buy` | `/investment/` | POST |
| Créer annonce | `/market/listings` | `/marketplace/list` | POST |
| Acheter annonce | `/market/listings/{id}/buy` | `/marketplace/list/buy` | POST |
| Créer projet | `/projects` | `/project/` | POST |
| Production | `/production/simulate` | `/prod` | POST |

## 5. Payloads envoyés par le frontend

### 5.1 DID

```json
{
  "user_id": 2,
  "legal_name": "Amen Beji",
  "email": "contact.beji@gmail.com",
  "hedera_id": "0.0.10794965"
}
```

Route :

```text
POST /auth/did
```

### 5. Achat primaire

```json
{
  "user_id": 2,
  "project_id": 1,
  "token_amount": 2
}
```

Route :

```text
POST /investment/
```

### 5. Création d'annonce

```json
{
  "user_id": 2,
  "token_id": 3,
  "u_price": "1200.00",
  "amount": 5
}
```

Route :

```text
POST /marketplace/list
```

### 5. Achat d'annonce

```json
{
  "user_id": 1,
  "listing_id": 8,
  "amount": 2
}
```

Route :

```text
POST /marketplace/list/buy
```

### 5. Création de projet

```json
{
  "user_id": 1,
  "name": "Solar Test",
  "description": "Projet solaire de test",
  "target_amount": 84000,
  "token_name": "Solar Test Token",
  "token_symbol": "STT"
}
```

Route :

```text
POST /project/
```

### 5. Production

```json
{
  "project_id": 1,
  "energy_kwh": "520.00",
  "revenue": "104.00"
}
```

Route :

```text
POST /prod
```

## 6. Modification du backend local

### `app/routes/auth.py`

Fichier :

```text
C:\Users\Bejia\.copilot\attachments\86fed46c-2796-443c-9b86-41c68ee4ebb8\EnerX-main\backend\app\routes\auth.py
```

La fonction `create_did` contenait initialement `pass`. Elle a été implémentée pour :

1. Rechercher l'utilisateur en base de données.
2. Retourner `404` si l'utilisateur n'existe pas.
3. Comparer :
   - `hedera_id` ;
   - `legal_name` ;
   - `email`.
4. Retourner `400` si les données ne correspondent pas.
5. Générer le DID :

```text
did:hedera:<network>:<hedera_account_id>
```

6. Enregistrer le DID dans `users.did`.
7. Retourner :

```json
{
  "user_id": 2,
  "did": "did:hedera:testnet:0.0.10794965"
}
```

La route doit être enregistrée par cette ligne dans `app/main.py` :

```python
app.include_router(auth.router)
```

## 7. Configuration frontend

Créer le fichier :

```text
C:\Users\Bejia\Desktop\Hackaton\EnerxV\.env.local
```

Contenu :

```env
NEXT_PUBLIC_API_BASE_URL=https://enerx.fastapicloud.dev
```

Après toute modification de ce fichier, redémarrer Next.js.

## 8. Configuration backend

Le frontend n'a pas besoin du fichier `.env` backend pour fonctionner. Ce fichier est nécessaire uniquement au serveur FastAPI.

Le backend doit disposer de paramètres PostgreSQL et Hedera valides. Ces secrets ne doivent jamais être placés dans le frontend.

Pour PostgreSQL Render, le backend utilise normalement :

```env
DATABASE_HOST=<hostname Render>
DATABASE_PORT=5432
DATABASE_NAME=enerx
DATABASE_USER=<utilisateur Render>
DATABASE_PASSWORD=<mot de passe Render>
```

Si le backend se connecte à PostgreSQL Render depuis l'extérieur, une connexion SSL est généralement nécessaire :

```python
DATABASE_URL = (
    f"postgresql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}"
    f"@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    "?sslmode=require"
)
```

Les clés Hedera doivent rester uniquement dans l'environnement backend :

```env
OPERATOR_ID=0.0.xxxxx
OPERATOR_KEY=<clé privée opérateur>
HEDERA_USER_1_KEY=<clé privée utilisateur 1>
HEDERA_USER_2_KEY=<clé privée utilisateur 2>
HEDERA_USER_3_KEY=<clé privée utilisateur 3>
```

Pour les comptes ECDSA, le code backend actuel utilise :

```python
PrivateKey.from_string_ecdsa(...)
```

## 9. Validation effectuée

Le frontend a été validé avec :

```powershell
pnpm exec tsc --noEmit
```

Résultat :

```text
Succès, aucune erreur TypeScript.
```

Le backend local n'a pas pu être exécuté dans l'environnement frontend car Python/`uv` n'y sont pas installés. La validation backend doit être faite par la personne responsable du backend ou sur l'environnement de déploiement.

## 10. État actuel du déploiement distant

Le frontend appelle correctement :

```text
https://enerx.fastapicloud.dev/auth/did
```

Une réponse `500 Internal Server Error` signifie :

- la variable frontend est correcte ;
- la requête atteint bien le backend ;
- le problème se trouve dans le backend distant, sa base de données ou sa configuration ;
- la correction locale de `app/routes/auth.py` n'est pas encore forcément déployée sur l'URL distante.

Le responsable backend doit donc :

1. intégrer `app/routes/auth.py` corrigé ;
2. vérifier la base de données ;
3. vérifier les variables d'environnement ;
4. redéployer le backend ;
5. consulter les logs du service au moment de l'appel `POST /auth/did`.

## 11. Démarrage du frontend

Depuis le dossier frontend :

```powershell
cd "C:\Users\Bejia\Desktop\Hackaton\EnerxV"
pnpm install
pnpm dev
```

Ouvrir :

```text
http://localhost:3000
```

La documentation Swagger du backend est accessible à :

```text
https://enerx.fastapicloud.dev/docs
```

La variable frontend doit contenir l'URL racine, sans `/docs`.

## 12. Sécurité

Les mots de passe PostgreSQL et clés privées Hedera ne doivent jamais être :

- ajoutés au frontend ;
- préfixés par `NEXT_PUBLIC_` ;
- commités dans Git ;
- envoyés dans le chat ;
- publiés dans une capture d'écran.

Tout secret déjà exposé doit être révoqué et remplacé.
