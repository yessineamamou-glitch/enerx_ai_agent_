# EnerX: handoff for the backend developer

## Project layout

```
├── front/    Next.js dashboard (pnpm)
└── ai/       AI agent: FastAPI service (Python)
    ├── production/   solar forecast -> dividend per token
    ├── news/         energy news feed + daily news coefficient (RAG)
    ├── rag/          "Ask EnerX": cited Q&A over docs + news (information only)
    ├── hedera/       report hash + anchoring on Hedera
    ├── tests/ examples/ docs/
    └── api.py        entry point (/health, /forecast, /news, /ask)
```

Two separate backends exist:

| Service | Where | Used for |
|---|---|---|
| **AI service** (`ai/api.py`) | `http://localhost:8001` | solar forecast, dividend per token, energy news |
| **Main backend** | `NEXT_PUBLIC_API_BASE_URL` (`front/.env.local`) | auth, projects, marketplace, investments |

The AI service is read-only and independent: the front calls it directly from the browser (CORS is open).

## Run everything (all Python commands from `ai/`, with `python -m`)

```bash
# AI service
cd ai
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m news.run_pipeline                              # fills news/data/articles_steg.json
uvicorn api:app --port 8001

# Front
cd front
pnpm install
pnpm dev                                                 # http://localhost:3000
```

`front/.env.local`:
```
NEXT_PUBLIC_API_BASE_URL=<main backend url>
NEXT_PUBLIC_AI_API_URL=http://localhost:8001
```
Restart `pnpm dev` after changing it.

## AI service contract

- `GET /health` → `{"status":"ok"}`
- `GET /forecast?lat&lon&capacity_kw&days&n_tokens` → report with `days[]`, `totals`, `assumptions`, `warnings`, `report_hash`
  - lat 30–37.6, lon 7.4–11.7, capacity ≤ 10000 kW, days 1–14 (accuracy is best up to 7)
  - dividend = forecast kWh × STEG tariff × daily news coefficient / n_tokens. The coefficient (0.90–1.10, `use_news=false` to disable) is read from the day's report written by `python -m rag.coefficient_news` (schedule it daily); without a report it is 1.0 and the report carries a warning. The `news` block and coefficient are covered by `report_hash`: hashes anchored before this version no longer match.
  - USDC amounts are computed by Python (`fx_rate.json`), the front never converts.
- `GET /news` → `{items:[{title,source,url,date,summary}], origin, informational_only:true}`
  - reads `news/data/articles_steg.json`, refreshed in the background every hour

- `GET /ask?q=...` (2–300 chars) → `{answer, mode: llm|extractive|no_match, sources:[{id,title,source,url,date,kind,snippet}], informational_only:true}`
  - RAG over `rag/data/knowledge.md` + the news file. Works without any key (extractive); `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` switch it to written answers. 20 questions/min/IP (429 after). Behind a proxy, all users share one IP: adjust `ASK_LIMIT` in `api.py`.
  - Optional vector backend for the news: `pip install -r requirements-rag.txt`, `python -m rag.etape2_vectorisation`, `ENERX_RAG_BACKEND=chroma`. Tune `RAG_MAX_DISTANCE` first (not calibrated).
  - The front's "Ask EnerX" panel (`front/components/enerx/ai/ask-panel.tsx`) only shows when `NEXT_PUBLIC_AI_API_URL` is set.

The front shows a badge on the AI predictor tab: green = real AI service, orange = simulated fallback.

## To do before the demo

1. **Main backend routes return 404**: the front calls `/auth/verification/{id}` and `/marketplace/listings` (see `apiRequest` in `front/components/enerx/dashboard.tsx`). Compare with `<backend>/docs` and align the routes.
2. **FX rate**: `ai/production/data/fx_rate.json` has status `EXEMPLE`. Put the official TND→USDC rate, otherwise every report carries a warning.
3. **Hedera**: `report_hash` is a SHA-256 of the canonical JSON (see `production/aggregator.py: hash_report`, cross-checked by `hedera/verify_hash.js`, run `python -m hedera.check_hash`). `python -m hedera.hcs_anchor` (`ai/hedera/hcs_anchor.py`) publishes it to an HCS topic. Fill `ai/.env` from `.env.example` (never commit it). Hashes anchored before this version no longer match.
4. **Deploy the AI service**: `uvicorn api:app --host 0.0.0.0 --port $PORT`, then set `NEXT_PUBLIC_AI_API_URL` to its public https URL (the browser blocks http calls from an https front).
5. `scikit-learn` must be **1.9.1** (version used to create `production/data/solar_agent.pkl`).

## Known limits

- Forecast needs internet (Open-Meteo); without it `/forecast` returns 502 and the front shows simulated data.
- Training area: lat 32.9–37.3, lon 8.1–10.9. Outside it the report carries a warning.
- STEG tariff (0.217 DT/kWh under 1 MW) comes from press reports of the 2024 JORT decree: re-check the official text.
