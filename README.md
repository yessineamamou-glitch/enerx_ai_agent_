# EnerX

**AI-forecast solar dividends for tokenized rooftop plants in Tunisia, with reports anyone can verify on Hedera.**

EnerX is a decentralized platform that finances residential solar plants in Tunisia through tokenized real-world assets on [Hedera](https://hedera.com). Investors buy **EnerTokens** (HTS), funds are escrowed in a smart contract (HSCS), roof owners prove ownership with a Hedera DID, and dividends come from the electricity sold to the national utility **STEG**.

This repository contains the **AI agent** (a FastAPI service) and the **web dashboard** (Next.js) that uses it. The agent forecasts the daily production of any roof in Tunisia, turns it into an expected **dividend per token**, adjusts it with a bounded news signal, and publishes a **SHA-256 fingerprint of every report on the Hedera Consensus Service (HCS)**, so a forecast cannot be silently edited after the fact.

> Built for the **ISGT Campus Edition – Hedera Cross Campus Challenge 2026**
> (themes: Real-World Assets · DeFi · Digital Identity · AI × Web3 Agents).

---

## Table of contents

1. [What it does](#what-it-does)
2. [Architecture](#architecture)
3. [Results](#results)
4. [How the dividend is computed](#how-the-dividend-is-computed)
5. [Quick start](#quick-start)
6. [API](#api)
7. [News, RAG and the news coefficient](#news-rag-and-the-news-coefficient)
8. [Hedera integration](#hedera-integration)
9. [Configuration](#configuration)
10. [Testing](#testing)
11. [Repository layout](#repository-layout)
12. [Limitations](#limitations)
13. [Roadmap](#roadmap)
14. [Team, data sources and license](#team-data-sources-and-license)

---

## What it does

| Capability | Description |
|---|---|
| **Production forecast** | Neural network (MLP 128‑64‑32) turns Open‑Meteo weather into kWh/day for any roof in Tunisia, with an 80 % error range. |
| **Dividend per token** | `forecast kWh × STEG tariff × news coefficient ÷ tokens`, in DT and in USDC (the exchange rate is computed by the backend, never the front end). |
| **News feed** | Relevant Tunisian energy / STEG articles are collected, filtered and displayed. |
| **Ask EnerX (RAG)** | Cited question answering over the project documentation and recent news, in French or English. Works offline; an LLM is optional. |
| **News coefficient** | A daily index (0.90 – 1.10) derived from four standard questions put to the news RAG. Neutral (1.0) when unavailable. |
| **Auditable reports** | Every report carries a canonical SHA-256 hash that can be anchored on Hedera HCS and verified by anyone. |
| **Dashboard** | Investor marketplace, owner tools and an AI predictor tab (charts, revenue split, news panel, Ask EnerX). |

## Architecture

```
 roof (lat, lon, kW)
        │
        ▼
 Open-Meteo forecast ──► daily temperature + irradiance
        │
        ▼
 Neural network (MLP 128-64-32-1) ──► kWh/day  (+ 80 % error range)
        │
        │            ┌──────────────────────────────────────────────┐
        │            │ Daily news coefficient (0.90 – 1.10)         │
        │            │ press scraping → ChromaDB / BM25 → 4 standard│
        │            │ questions → rules + freshness → index 0–1    │
        │            └──────────────────┬───────────────────────────┘
        ▼                               ▼
 Aggregator: kWh × STEG tariff × news coefficient ÷ tokens   (+ TND → USDC)
        │
        ▼
 JSON report + SHA-256 hash ──► anchored on Hedera Consensus Service (HCS)
        ▲
        │
 FastAPI  /forecast · /news · /ask · /health   ◄── Next.js dashboard
```

Two backends exist side by side: this **AI service** (`ai/`, port 8001, read-only) and the platform's **main backend** (auth, projects, marketplace, investments), configured in `front/.env.local`. See [`HANDOFF.md`](HANDOFF.md) for the integration notes.

## Results

Trained on **12 Tunisian cities, 2019–2023** (daily data). Split by date: train 2019–2021, dev 2022, test 2023.

| Metric (test year 2023) | Result |
|---|---|
| MAE (PVGIS weather as input) | **0.65 kWh/day** (about 1.4 % of mean production) |
| R² | 0.995 |
| Linear regression baseline | 0.87 kWh/day |
| "Yesterday = today" baseline | 6.99 kWh/day |
| 80 % error range, empirical coverage | 80 % of test days |
| Cities never seen in training (Tataouine, Kasserine, Bizerte, Tozeur) | 0.85 kWh/day (linear regression: 1.11) |
| **End-to-end MAE with Open‑Meteo weather** (what the API really uses) | **3.64 kWh/day**, bias −0.13 kWh/day, interval coverage 80.3 % (4 380 city-days) |

> **Read the last row.** The headline 0.65 kWh/day measures the model when it is fed the same weather data it was trained on. With Open‑Meteo weather the error is larger (about 8 % of mean daily production). Both are measured on *historical* weather: a multi-day *forecast* is less accurate still. The error range shipped with the API is calibrated on the end-to-end chain (`production/data/chain_calibration.json`).

Reproduce: `python -m production.tools.test_ville_cachee` (unseen cities) and `python -m production.tools.evaluate_chain` (end-to-end, needs internet).

## How the dividend is computed

```
dividend per token = forecast kWh × STEG tariff (DT/kWh) × news coefficient ÷ number of tokens
```

* **STEG tariff** (DT/kWh, excl. tax): 0.217 under 1 MW · 0.201 for 1–2 MW · 0.142 for 2–10 MW. Source: the 2024 JORT decree as reported by the press — *to be re-checked against the official text*.
* **News coefficient**: between 0.90 and 1.10, applied to revenue only. It never modifies the forecast kWh. `use_news=false` removes it.
* **USDC** amounts use the rate in `ai/production/data/fx_rate.json` (or a live rate). While its status is not `OFFICIEL`, every report carries a warning.

## Quick start

Requirements: **Python 3.10+**, **Node 20+** and **pnpm** for the front end.

```bash
# 1. AI service  (run every command from ai/, with `python -m`)
cd ai
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # all keys are optional
python -m news.run_pipeline                              # (optional) collect the news, needs internet
uvicorn api:app --reload --port 8001                     # docs: http://127.0.0.1:8001/docs

# 2. Dashboard
cd ../front
pnpm install
pnpm dev                                                 # http://localhost:3000
```

`front/.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=<main backend URL>
NEXT_PUBLIC_AI_API_URL=http://localhost:8001
```

The AI predictor tab shows a **green badge** when it uses the real AI service and an **orange badge** when it falls back to a built-in simulation (service unreachable).

**No API key is needed to run the project.** Without one, `/ask` answers with extractive citations and the news coefficient stays at 1.0 with an explicit warning.

The trained model (`solar_agent.pkl`) is included. The 33 MB training dataset is not (see [Limitations](#limitations)).

## API

Interactive documentation: `http://127.0.0.1:8001/docs`.

### `GET /forecast`

`/forecast?lat=32.9297&lon=10.4518&capacity_kw=10&days=7`

| Parameter | Meaning | Default / range |
|---|---|---|
| `lat`, `lon` | Roof position | required · 30–37.6 · 7.4–11.7 |
| `capacity_kw` | Plant size | 10 · up to 10 000 |
| `days` | Forecast horizon (best up to 7) | 7 · 1–14 |
| `n_tokens` | Tokens issued for the plant | 1000 |
| `tariff` | DT/kWh | STEG tariff for the plant size |
| `use_news` | Apply the daily news coefficient | `true` |

The response contains, per day, `kwh`, `kwh_low`, `kwh_high`, `revenue_dt`, `dividend_per_token_dt` (+ USDC and low/high variants), then `totals`, `assumptions`, `warnings`, a `news` block and `report_hash`.

### `GET /news`
Latest relevant articles `{title, source, url, date, summary}`, refreshed in the background about every hour.

### `GET /ask?q=...`
Cited answer `{answer, mode: llm | extractive | no_match, sources[]}`. Limited to 20 questions per minute per IP. Informational only.

### `GET /health`
`{"status": "ok"}`

## News, RAG and the news coefficient

**Ask EnerX (`/ask`).** The corpus is the project knowledge base (`ai/rag/data/knowledge.md`) plus the collected press articles, filtered with the same relevance rules as the feed. Retrieval is BM25 in pure Python (accent-insensitive, French/English) — no model to download. With an API key a language model writes a short answer from the retrieved passages **only**, with `[n]` citations that are verified against the sources; retrieved text is treated as untrusted data. Without a key the endpoint returns the most relevant sentences. A question with no relevant source gets an honest "not found" instead of an invented answer.

**Optional vector backend.** `pip install -r ai/requirements-rag.txt`, then `python -m rag.etape2_vectorisation` (sentence chunks, multilingual embeddings, ChromaDB; incremental) and `ENERX_RAG_BACKEND=chroma`. If anything is missing, the service silently stays on BM25.

**Daily news coefficient.** Once a day four standard questions (grid incidents, tariff/regulation, BESS and solar projects, overall trend) are put to the RAG. Each answer becomes an impact in [−1, +1] using keyword rules with negation handling, weighted by the freshness of its sources (half-life 14 days), then combined into an index in [0, 1] mapped to a multiplier in [0.90, 1.10]. `/forecast` never computes it: it **reads the day's report** (`coefficient_news_YYYY-MM-DD.json`); if absent, it applies 1.0, adds a warning and starts a background computation. The forecast report embeds the index, the questions, the impacts and the source URLs, so the adjustment is **fully traceable and covered by the Hedera hash**.

```bash
python -m rag.coefficient_news --planifier 06:30    # compute it every day at 06:30 (Tunis time)
```

It needs a filled vector base and an LLM (Gemini, Claude or a local [Ollama](https://ollama.com) model). The weights and rules are a **design choice, not calibrated on data**, and the adjustment is capped at ±10 %.

## Hedera integration

Every report has a SHA-256 hash computed over its canonical JSON: `report_hash` removed, every number written as a fixed-decimal string (6 decimals, trailing zeros removed), keys sorted, compact separators, UTF-8. Two reference implementations exist — `aggregator.hash_report` (Python) and `hedera/verify_hash.js` (Node.js) — and `python -m hedera.check_hash` verifies that they agree.

```bash
cd ai
python -m hedera.hcs_anchor create-topic                          # once
python -m hedera.hcs_anchor anchor examples/demo_report.json      # publish the hash on HCS
python -m hedera.hcs_anchor verify examples/demo_report.json 1    # compare with message #1 on the Mirror Node
pip install -r hedera/requirements-hedera.txt                     # needed for anchoring
```

Anyone can verify a report later by recomputing its hash and comparing it with the message on the Mirror Node: changing a single number changes the hash. Anchoring is deliberately **not a public API route**, because it spends HBAR from the operator account.

## Configuration

Copy `ai/.env.example` to `ai/.env`. **Never commit `.env`.**

| Variable | Used for |
|---|---|
| `OPERATOR_ID`, `OPERATOR_KEY`, `OPERATOR_KEY_TYPE`, `NETWORK`, `HCS_TOPIC_ID` | Hedera testnet account and topic for anchoring ([free account](https://portal.hedera.com)) |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | Optional LLM for `/ask` and the news coefficient |
| `ENERX_NEWS_LLM` | Force `gemini`, `claude` or `ollama` for the news coefficient |
| `ENERX_RAG_BACKEND` | `chroma` enables vector search for the news in `/ask` |
| `RAG_MAX_DISTANCE` | Vector distance threshold (default 0.75, **not calibrated**) |
| `ENERX_STRICT_RANGE` | `1` refuses roofs outside the training area |

## Testing

```bash
cd ai
pip install pytest httpx
python -m pytest -q tests          # 91 tests, no internet and no API key needed
```

The suite covers physical plausibility of the forecast, absurd inputs, the report hash, the relevance filter, the RAG (retrieval, fallbacks, prompt-injection handling, rate limit), the vector pipeline (with a stand-in embedder) and the news coefficient (applied, neutral, degraded, hash-covered).

## Repository layout

```
.

├── ai/                          FastAPI AI service (Python)
│   ├── api.py                   entry point: /health /forecast /news /ask
│   ├── production/              forecast model, aggregator (dividend + hash), FX, evaluation tools
│   ├── news/                    press collector, relevance filter, news feed
│   ├── rag/                     Ask EnerX, vector pipeline, daily news coefficient
│   ├── hedera/                  hash reference implementations + HCS anchoring
│   ├── tests/  examples/  docs/
│   └── requirements*.txt  .env.example
└── front/                       Next.js dashboard (pnpm)
    ├── app/  components/enerx/  lib/enerx/
    └── README.md                front end ↔ backend integration guide (French)
```

Source comments and some module names are in French (the team's working language); the public interfaces, the API and the documentation are in English.

## Limitations

* **Training data is simulated.** Production values come from the PVGIS photovoltaic simulation (10 kWp, 14 % losses, optimal angles), not from measured plants. Scores measure agreement with that simulation; the model is meant to be retrained on real STEG meter data.
* **Weather forecast error is not included in the reported error ranges** beyond 2–3 days; the real uncertainty is larger than the interval shown.
* **Training area**: latitudes 32.9–37.3, longitudes 8.1–10.9. Outside it (+0.5°) the report carries a warning (or the API refuses with `ENERX_STRICT_RANGE=1`).
* **The news coefficient is a design choice**, not a calibrated value, and the RAG distance threshold is untuned. The coefficient needs an LLM to be computed; without one it stays neutral.
* **The TND → USDC rate is an example** (`status: EXEMPLE`) until the official rate is set.
* **STEG tariff** to be re-checked against the official decree.
* **The training dataset** (`dataset_solar_global_tunisie.csv`, 33 MB) is not versioned: retraining requires obtaining it separately.
* The AI service needs internet access to Open-Meteo; without it `/forecast` returns 502 and the dashboard shows simulated data.

## Roadmap

* Retrain on measured STEG meter data and report real-plant error.
* Calibrate the news rules, weights and the RAG distance threshold on labelled examples.
* Multi-day weather uncertainty in the error range.
* Official TND/USDC rate feed and automatic anchoring of each published report.
* Align the dashboard with the main backend routes (see `HANDOFF.md`).

## Team, data sources and license

**Team:** *[add names and roles]*

**Data and services:** [Open‑Meteo](https://open-meteo.com) (weather forecast and historical weather) · [PVGIS](https://joint-research-centre.ec.europa.eu/pvgis-photovoltaic-geographical-information-system_en) (EU Joint Research Centre, simulated PV production and tilt) · Tunisian press and official STEG notices (news) · [Hedera](https://hedera.com) (HTS, HSCS, HCS).

**License:** *[choose a license, e.g. MIT, and add a `LICENSE` file]*
