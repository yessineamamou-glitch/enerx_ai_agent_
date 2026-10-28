# EnerX — AI Agent (solar yield forecasting + auditable reports on Hedera)

EnerX is a decentralized platform that finances residential solar plants in Tunisia through tokenized real-world assets on Hedera. Investors buy EnerTokens (HTS), funds are escrowed in a smart contract (HSCS), owners prove roof ownership with a Hedera DID, and dividends come from the electricity sold to the national utility (STEG).

This repository contains the **AI agent module**: it forecasts the daily production of any solar roof in Tunisia, converts it into an expected dividend per token, adjusts the figure with a news-risk agent, and anchors a hash of every report on **Hedera Consensus Service (HCS)** so that forecasts are immutable and auditable.

> Hackathon: ISGT Campus Edition — Hedera Cross Campus Challenge 2026 (themes: Real-World Assets, DeFi, Digital Identity, AI × Web3 Agents).
> Team: [TODO: team members and roles]

## How it works

```
 roof (lat, lon, kW)
        |
        v
 Open-Meteo forecast --> daily temperature + irradiance
        |
        v
 Neural network (MLP 128-64-32-1) --> kWh/day  (+ 80 % error range)
        |
        v
 News agent (keywords or Claude LLM) --> coefficient 0.90 - 1.10 + risk level
        |
        v
 Aggregator: kWh x STEG tariff x news coefficient / number of tokens
        |
        v
 JSON report + SHA-256 hash --> anchored on Hedera Consensus Service
        ^
        |
 FastAPI  (/forecast, /news, /health)  <-- called by the dashboard / backend
```

## Results

Trained on 12 Tunisian cities, 2019–2023 (daily data). Split by date: train 2019–2021, dev 2022, test 2023.

| Metric (test year 2023) | Result |
|---|---|
| MAE | 0.65 kWh/day (about 1.4 % of mean production) |
| R² | 0.995 |
| Linear regression baseline | 0.87 kWh/day |
| "Yesterday = today" baseline | 6.99 kWh/day |
| Error range coverage (10th–90th percentile of dev errors) | 80 % of test days |
| **Cities never seen in training** (Tataouine, Kasserine, Bizerte, Tozeur; test year only) | **0.85 kWh/day** (linear regression: 1.11) |

Reproduce the last row with `python -m production.tools.test_ville_cachee`.

## Limitations (please read)

- **Training data is simulated.** Production values come from the PVGIS photovoltaic simulation (10 kWp system, 14 % losses, optimal angles), not from measured plants. The scores measure agreement with that simulation. The model is meant to be retrained on real STEG meter data.
- **The error range reflects model error when the weather is known.** Weather forecasts beyond 2–3 days are less reliable, so the real uncertainty is larger.
- The tilt/azimuth requested from Open-Meteo are read from the PVGIS responses (`check_pvgis_tilt.py` -> `pvgis_tilts.json`) and interpolated on latitude. [TODO: confirm the file was generated and committed; without it the code falls back to an unverified 30°]
- **End-to-end error.** The 0.65 kWh/day figure uses PVGIS weather as input. With Open-Meteo weather (what the API really uses) the error is measured by `evaluate_chain.py`: [TODO: paste MAE, bias and interval coverage from the script output]. This measures the weather-source mismatch on historical data, not the (larger) error of a multi-day forecast.
- The model was trained on latitudes 32.9–37.3 and longitudes 8.1–10.9. Outside this area (+0.5°) the report carries a warning (or the API refuses with `ENERX_STRICT_RANGE=1`).
- **The news coefficient (max ±10 %) is a design choice, not a calibrated value.** In the default mode the news agent applies keyword rules to fictitious example headlines; the LLM mode is optional. [TODO: update once the LLM mode has been tested with a real API key]
- STEG purchase tariff: 0.217 DT/kWh (excl. tax) for plants under 1 MW, taken from the 2024 JORT decree as reported by the press; to be re-checked against the official text.

## Quick start

Requires Python 3.10+.

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in your values (see below)
# ALL commands are run from this folder (project root), with `python -m`

# 1. (optional) retrain the production model
python -m production.model                    # trains the network -> production/data/solar_agent.pkl

# 1b. recommended checks (internet needed)
python -m production.tools.check_pvgis_tilt   # real PVGIS tilt per city -> production/data/pvgis_tilts.json
python -m production.tools.evaluate_chain     # end-to-end error + calibrated interval -> production/data/chain_calibration.json
python -m hedera.check_hash                   # Python and JavaScript hashes must match
python -m pytest -q tests                     # unit and robustness tests (no internet)

# 2. news feed (optional, fills news/data/articles_steg.json)
python -m news.run_pipeline

# 3. run the API
uvicorn api:app --reload --port 8001          # docs: http://127.0.0.1:8001/docs (the front expects port 8001)

# 4. run the end-to-end demo
python -m examples.demo
```

The trained model `solar_agent.pkl` is included, so steps 1 can be skipped.

### Configuration (`.env`)

| Variable | Used for |
|---|---|
| `OPERATOR_ID`, `OPERATOR_KEY`, `OPERATOR_KEY_TYPE`, `NETWORK` | Hedera testnet account that pays for HCS messages (free account at https://portal.hedera.com) |
| `HCS_TOPIC_ID` | The HCS topic where report hashes are published |
| `GEMINI_API_KEY` | Optional: enables the LLM mode of the news agent (free key from Google AI Studio) |
| `ANTHROPIC_API_KEY` | Optional alternative LLM provider (used only if `GEMINI_API_KEY` is absent) |
| `ENERX_STRICT_RANGE` | Optional: `1` makes the API refuse roofs outside the training area |

Never commit `.env`. Only `.env.example` (placeholders) belongs in the repository.


## API

`GET /forecast?lat=32.9297&lon=10.4518&capacity_kw=10&days=7&use_news=true`

| Parameter | Meaning | Default |
|---|---|---|
| `lat`, `lon` | Roof position (Tunisia) | required |
| `capacity_kw` | Plant size | 10 |
| `days` | Forecast horizon, 1–14 | 7 |
| `n_tokens` | Tokens issued for the plant | 1000 |
| `tariff` | DT/kWh | STEG tariff for the plant size (0.217 under 1 MW) |
| `use_news` | Let the news agent set the coefficient | false |
| `news_coef` | Manual coefficient (ignored if `use_news=true`) | 1.0 |

The response contains, per day, `kwh`, `kwh_low`, `kwh_high`, `revenue_dt`, `dividend_per_token_dt` (+ low/high), then `totals`, an optional `news` block and `report_hash`. `GET /news` returns the news analysis alone, `GET /health` a status check.

## USDC and news provenance

- **USDC amounts are computed by the backend, not the frontend.** `aggregator.py` reads `fx_rate.json` (rate = USDC per 1 TND, source, date, status) and writes `revenue_usdc`, `dividend_per_token_usdc` (+ low/high) and the `assumptions.fx` block into the report, so the exchange rate is covered by `report_hash`. While `status` is not `OFFICIEL`, the report carries a warning. USDC is treated as 1 USD.
- **News sources.** `news_headlines.json` items must carry a `source_url` on an allow-listed domain (e.g. TAP, Managers.tn, Business News). Items without a valid https source are rejected and listed under `news.rejected`. The allow-list is a design choice that limits invented or anonymous sources; it does not guarantee that a listed outlet is right. Without `news_headlines.json`, the agent runs on fictitious demo headlines, labelled as such.

## Hedera integration (HCS)

Every report has a SHA-256 hash, computed over the canonical JSON: `report_hash` removed, every number replaced by a fixed-decimal string (6 decimals, trailing zeros removed: `5939.0` → `"5939"`, `0.00001` → `"0.00001"`), keys sorted, compact separators, UTF-8 (reference implementations: `aggregator.hash_report` in Python and `verify_hash.js` in Node.js; `python -m hedera.check_hash` checks both agree). `hcs_anchor.py` publishes this hash, with a few readable fields, as a message in an HCS topic:

```bash
python -m hedera.hcs_anchor create-topic              # once: creates the topic
python -m hedera.hcs_anchor anchor examples/demo_report.json   # anchors a report
python -m hedera.hcs_anchor verify examples/demo_report.json 1 # checks the report against message #1 (Mirror Node)
```

Anyone can verify a report later: recompute its hash and compare it with the message on the Mirror Node. If a single number was changed, the hashes differ.

Anchoring is deliberately **not exposed as a public API route**, because it spends HBAR from the operator account. It is triggered by the backend or by the demo script.

Example anchored message: [TODO: paste the HashScan link after the first successful run]

## Repository layout

```
ai/
├── api.py                    FastAPI entry point (GET /health, /forecast, /news)
├── requirements.txt          .env.example   .gitignore
├── production/               SOLAR PRODUCTION FORECAST -> dividend
│   ├── forecast.py           Open-Meteo weather -> daily features -> model prediction
│   ├── aggregator.py         dividend per token, report, SHA-256 hash
│   ├── fx.py                 TND -> USDC rate (live, fallback data/fx_rate.json)
│   ├── model.py              trains the neural network
│   ├── data/                 solar_agent.pkl, fx_rate.json, pvgis_tilts.json, chain_calibration.json, dataset (csv)
│   ├── reports/              training outputs (graphs, csv)
│   └── tools/                check_pvgis_tilt.py, evaluate_chain.py, test_ville_cachee.py
├── news/                     ENERGY NEWS (information only, never changes the numbers)
│   ├── news_feed.py          what GET /news serves (reads data/articles_steg.json)
│   ├── etape1_collecte.py    web collector       pertinence.py   relevance filter
│   ├── nettoyer_articles.py  cleaning            injecter_steg.py  official STEG notices
│   ├── run_pipeline.py       runs collect -> clean -> inject
│   ├── news_fetch.py, news_agent.py   GDELT fallback (legacy)
│   └── data/                 articles_steg.json (+ backup)
├── hedera/                   HASH + ANCHORING ON HEDERA
│   ├── hcs_anchor.py         publish / verify a report hash on HCS
│   ├── verify_hash.js        JavaScript reference implementation
│   ├── check_hash.py         Python vs JavaScript cross-check
│   └── requirements-hedera.txt
├── tests/                    pytest suite (robustness, relevance filter)
├── examples/                 demo.py, demo_report.json
└── docs/                     CHANGEMENTS_NEWS.md
```

Dependencies flow one way: `api.py` -> `production` and `news`; `hedera` -> `production`; nothing in `production` imports `news`.|