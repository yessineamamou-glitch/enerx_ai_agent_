# EnerX — Frontend (Next.js) ↔ Backend FastAPI

Dashboard Web3 de crowdfunding solaire (Hedera RWA + IA). Ce document explique comment relier le frontend au backend FastAPI : **https://enerx.fastapicloud.dev**.

Pour l'instant, **toutes les actions sont simulées** (des mocks avec une latence artificielle). Le code est organisé pour qu'on puisse passer au vrai backend en modifiant **un seul fichier**.

---

## 1. Architecture

```
app/
  layout.tsx                 → Métadonnées, polices, thème
  page.tsx                   → Monte <EnerxDashboard />
components/enerx/
  dashboard.tsx              → ⭐ Tous les useState + tous les handlers API
  top-nav.tsx, profile-menu.tsx, toast-stack.tsx, home-tab.tsx
  invest/                    → Marché primaire, marché secondaire, modal KYC
  owner/                     → Formulaire projet (HTS), simulateur production (HSCS)
  ai/                        → Prédicteur IA + graphiques Recharts
lib/enerx/
  api.ts                     → ⭐ Transport HTTP (mock aujourd'hui)
  types.ts                   → Types TypeScript (Project, Profile, Listing…)
  mock-data.ts               → Données initiales (profils, projets, holdings…)
  utils.ts                   → Règles métier (100 tokens, 30 owner / 70 investisseurs, split des revenus)
  forecast.ts                → Génération des prévisions IA (côté client)
```

Le flux est toujours le même :

```
Composant UI → handler dans dashboard.tsx → apiRequest(endpoint, payload, mock) → mise à jour du state → toast
```

---

## 2. Brancher le vrai backend

### Étape 1 — Remplacer le transport dans `lib/enerx/api.ts`

Version actuelle (mock) :

```ts
export async function apiRequest<T>(endpoint, payload, mockResponse, latencyMs = 900): Promise<T> {
  await wait(latencyMs)
  return mockResponse()
}
```

Version réelle :

```ts
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_ENERX_API_URL ?? 'https://enerx.fastapicloud.dev'

export async function apiRequest<T>(
  endpoint: string,
  payload: unknown,
  _mockResponse?: () => T,
  _latencyMs?: number,
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}
```

Les signatures ne changent pas : **aucun composant n'a besoin d'être modifié**. Les blocs `try / catch` de `dashboard.tsx` affichent déjà un toast d'erreur si le backend répond avec un code ≠ 2xx.

### Étape 2 — Variable d'environnement (optionnel)

Dans v0 : **Settings → Vars**, ou en local dans `.env.local` :

```
NEXT_PUBLIC_ENERX_API_URL=https://enerx.fastapicloud.dev
```

### Étape 3 — CORS côté FastAPI

Le navigateur appelle directement l'API, il faut donc autoriser l'origine du frontend :

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://<votre-projet>.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 3. Contrat d'API attendu

Toutes les requêtes sont en `POST` avec un corps JSON. Les montants et l'énergie sont envoyés sous forme de **chaînes décimales strictes** (`"104.00"`) pour éviter les erreurs d'arrondi des flottants.

| Action UI | Handler (`dashboard.tsx`) | Endpoint | Payload envoyé | Réponse attendue |
|---|---|---|---|---|
| Vérification KYC / DID | `handleKycSubmit` | `POST /kyc/verify` | `{ user_id, legal_name, email }` | `{ did: "did:hedera:testnet:..." }` |
| Achat marché primaire | `handleBuyPrimary` | `POST /invest/buy` | `{ project_id, buyer_id, amount }` | `{ status: "SUCCESS", transaction_id: "0.0.384@171829..." }` |
| Créer une annonce P2P | `handleCreateListing` | `POST /market/listings` | `{ project_id, seller_id, amount, unit_price: "12.50" }` | `{ id, projectId, sellerId, amount, unitPrice }` |
| Acheter une annonce P2P | `handleBuyListing` | `POST /market/listings/{listing_id}/buy` | `{ buyer_id }` | `{ status: "SUCCESS", transaction_id }` |
| Déployer un projet (HTS) | `handleDeployProject` | `POST /projects` | `{ name, description, targetFunding, tokenName, tokenSymbol, region, capacityKwp }` | `{ hedera_token_id: "0.0.xxxxxx" }` |
| Simuler production STEG (HSCS) | `handleSimulateProduction` | `POST /production/simulate` | `{ project_id, energy_kwh: "520.00", revenue: "104.00" }` | `{ contract_transaction_id: "..." }` |

> Les noms exacts des fonctions sont visibles dans `components/enerx/dashboard.tsx`. Si votre backend utilise d'autres routes ou d'autres noms de champs, modifiez uniquement le premier et le deuxième argument de chaque appel `apiRequest(...)`.

### Exemple — achat primaire

Requête :

```http
POST https://enerx.fastapicloud.dev/invest/buy
Content-Type: application/json

{ "project_id": "p-djerba-1", "buyer_id": "investor-1", "amount": 5 }
```

Réponse :

```json
{ "status": "SUCCESS", "transaction_id": "0.0.384@171829" }
```

Le frontend affiche alors le toast : `Hedera HTS Transaction: SUCCESS [Tx ID: 0.0.384@171829]`.

---

## 4. Règles métier à garantir côté backend

Le frontend applique déjà ces règles pour la démo, mais **le backend doit rester la source de vérité** :

- Supply totale : **100 tokens**, 0 décimale (1 token = 1 % de propriété).
- Le propriétaire conserve **30 tokens**, il en reste **70** pour les investisseurs.
- Un achat est refusé si le solde est insuffisant ou si `amount > tokens disponibles`.
- Une campagne passe à **CLOSED** quand il reste 0 token disponible.
- Le revenu est réparti au prorata des holdings réels (ex. 104.00 $ → Owner 30 % = 31.20 $, investisseurs 70 % = 72.80 $).
- Seuls les profils `Owner` peuvent créer un projet ou déclencher une simulation de production.
- Seuls les profils au DID vérifié peuvent investir.

---

## 5. Charger les données initiales depuis l'API (GET)

Aujourd'hui, le state est initialisé à partir de `lib/enerx/mock-data.ts`. Pour lire les données depuis le backend, remplacez les valeurs initiales en haut de `dashboard.tsx`. Endpoints suggérés :

| State (`dashboard.tsx`) | Mock actuel | Endpoint suggéré |
|---|---|---|
| `profiles` | `INITIAL_PROFILES` | `GET /profiles` |
| `kycRecords` | `INITIAL_KYC` | `GET /kyc` |
| `projects` | `INITIAL_PROJECTS` | `GET /projects` |
| `holdings` | `INITIAL_HOLDINGS` | `GET /holdings` |
| `listings` | `INITIAL_LISTINGS` | `GET /market/listings` |
| `productionHistory` | `INITIAL_HISTORY` | `GET /production/history` |

Approche recommandée : charger ces données dans `app/page.tsx` (Server Component) et les passer à `<EnerxDashboard />` en props.

```tsx
// app/page.tsx
const API = process.env.NEXT_PUBLIC_ENERX_API_URL ?? 'https://enerx.fastapicloud.dev'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}

export default async function Page() {
  const [profiles, projects, holdings, listings] = await Promise.all([
    get('/profiles'),
    get('/projects'),
    get('/holdings'),
    get('/market/listings'),
  ])
  return <EnerxDashboard initialData={{ profiles, projects, holdings, listings }} />
}
```

Ensuite, dans `dashboard.tsx` : `useState(initialData.projects)` au lieu de `useState(INITIAL_PROJECTS)`.

> **Correspondance des noms de champs :** le frontend utilise le camelCase (`targetFunding`, `availableTokens`, `hederaTokenId`) et FastAPI le snake_case. Il faut soit configurer Pydantic avec `alias_generator=to_camel` + `populate_by_name=True`, soit ajouter une petite fonction de mapping dans `lib/enerx/api.ts`. Les formes attendues sont définies dans `lib/enerx/types.ts`.

---

## 6. Prédicteur IA

Les courbes (irradiance, couverture nuageuse, production IA vs injection STEG) sont aujourd'hui générées côté client par `lib/enerx/forecast.ts`, de manière déterministe. Pour utiliser un vrai modèle :

```
GET /ai/forecast?project_id=...&range=7d|30d|12m&sunlight_hours=...&grid_spike=...
```

Le backend doit renvoyer un tableau dont la forme correspond à celle produite par `forecast.ts` (voir les types qui y sont exportés), puis on remplace l'appel local par un `fetch` (avec SWR, par exemple).

---

## 7. Lancer le projet en local

```bash
pnpm install
pnpm dev
# http://localhost:3000
```

## 8. Checklist de mise en production

- [ ] `apiRequest` remplacé par un vrai `fetch` dans `lib/enerx/api.ts`
- [ ] `NEXT_PUBLIC_ENERX_API_URL` défini sur Vercel
- [ ] CORS FastAPI configuré avec le domaine Vercel
- [ ] Noms des routes et des champs vérifiés par rapport au tableau de la section 3
- [ ] Données initiales chargées via GET (section 5)
- [ ] Règles métier (section 4) validées côté serveur
- [ ] Authentification ajoutée (aujourd'hui, le changement de profil est simulé dans l'UI)
