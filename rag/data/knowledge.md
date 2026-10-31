# EnerX knowledge base

Each "## " section is one retrievable passage. Keep every section short and self-contained, and
state facts only if they are true in the code (re-check `aggregator.py`, `forecast.py`, README after changes).
Keywords (FR) lines help French questions match, because the passages are written in English.

## What is EnerX
EnerX is a decentralized platform that finances residential solar plants in Tunisia through tokenized real-world assets on Hedera. Investors buy EnerTokens (HTS), funds are escrowed in a smart contract (HSCS), owners prove roof ownership with a Hedera DID, and dividends come from the electricity sold to the national utility STEG.
Keywords (FR): plateforme, financement, centrale solaire residentielle, toit, investisseur, token, EnerToken, Hedera, STEG, dividende.

## How the dividend per token is computed
Dividend per token = forecast kWh x STEG purchase tariff (DT/kWh) x daily news coefficient / number of tokens issued for the plant. The AI agent forecasts the daily production of the roof, multiplies it by the tariff and by the news coefficient (between 0.90 and 1.10, neutral 1.0), and divides by the number of tokens (1000 by default). The news coefficient never changes the forecast kWh, only the revenue. Passing use_news=false to /forecast removes it.
Keywords (FR): calcul du dividende, dividende par token, production prevue, tarif, coefficient news, nombre de tokens, formule, revenu.

## News coefficient
Once a day the news RAG answers four standard questions about the Tunisian energy context (grid incidents, tariff and regulation changes, BESS and solar projects, general trend). Each answer is turned into an impact between -1 and +1 by keyword rules, weighted by the freshness of its sources (half-life 14 days), and combined into an index between 0 and 1 (0.5 is neutral) which becomes a revenue multiplier between 0.90 and 1.10. The weights and rules are a design choice, not calibrated on data, and the maximum adjustment is 10 %. If the daily report is missing or the sources are unavailable, the coefficient is 1.0 and the report carries a warning. The /forecast report lists the questions, impacts and source links, and the hash of the daily report, so the adjustment can be audited and is covered by report_hash.
Keywords (FR): coefficient news, indice, actualites, impact, plus ou moins 10 %, risque, audit, sources, fraicheur.

## STEG purchase tariff
The tariff used for photovoltaic electricity sold to STEG depends on plant size (DT/kWh, excluding tax): 0.217 for plants under 1 MW, 0.201 from 1 to 2 MW, 0.142 from 2 to 10 MW. Plants above 10 MW are not covered and are refused. These values come from the 2024 JORT decree as reported by the press (managers.tn, 14 October 2024) and must be re-checked against the official text. The caller can override the tariff with the `tariff` parameter.
Keywords (FR): tarif de rachat, STEG, 0,217 dinar, kWh, JORT, arrete, puissance, megawatt.

## Production forecast model
The forecast uses Open-Meteo hourly weather (temperature and solar irradiance) for the roof position, turns it into daily features, and feeds a neural network (MLPRegressor, layers 128-64-32) that predicts kWh per day, with an 80 % error range (kwh_low / kwh_high). On the 2023 test year the model has a MAE of 0.65 kWh/day (about 1.4 % of mean production) and R2 0.995 against the PVGIS simulation. On four cities never seen in training the MAE is 0.85 kWh/day.
Keywords (FR): prevision, modele, reseau de neurones, meteo, irradiance, temperature, erreur, intervalle, precision.

## Limits of the forecast
The training data is simulated by PVGIS (10 kWp system, 14 % losses, optimal angles), not measured on real plants, so the scores measure agreement with that simulation; the model should be retrained on real STEG meter data. The error range reflects model error when the weather is known: weather forecasts beyond 2-3 days are less reliable, the horizon accepts 1 to 14 days and is most accurate up to 7. The model was trained on latitudes 32.9-37.3 and longitudes 8.1-10.9; outside that area (plus 0.5 degree) the report carries a warning. Without internet access to Open-Meteo, /forecast returns a 502 error.
Keywords (FR): limites, donnees simulees, PVGIS, zone d'entrainement, avertissement, horizon, fiabilite, incertitude.

## API input limits
GET /forecast accepts latitude 30 to 37.6, longitude 7.4 to 11.7, capacity up to 10000 kW, 1 to 14 forecast days, and n_tokens of at least 1. With ENERX_STRICT_RANGE=1 the API refuses (422) roofs outside the training area instead of returning a warning.
Keywords (FR): parametres, latitude, longitude, capacite, jours, limites de l'API.

## Report hash and Hedera verification
Every forecast report has a SHA-256 hash (report_hash) computed over its canonical JSON: report_hash removed, numbers written as fixed-decimal strings (6 decimals, trailing zeros removed), keys sorted, compact separators, UTF-8. The hash can be published as a message on a Hedera Consensus Service (HCS) topic so anyone can recompute it and compare it with the message on the Mirror Node; changing a single number changes the hash. Anchoring spends HBAR from the operator account, so it is not a public API route: the backend or the demo script triggers it.
Keywords (FR): hash, SHA-256, ancrage, HCS, verification, Mirror Node, immuable, auditable, rapport.

## USDC amounts and exchange rate
USDC amounts are computed by the Python backend, never by the front end: the report contains revenue_usdc and dividend_per_token_usdc computed from the TND to USDC rate in fx_rate.json (or a live rate), and the rate is covered by report_hash. USDC is treated as 1 USD. While the rate status is not OFFICIEL, the report carries a warning and the USDC amounts are indicative.
Keywords (FR): USDC, taux de change, dinar, TND, conversion, indicatif.

## Energy news feed
The news feed lists recent Tunisian energy and STEG articles collected from the press and official STEG notices, filtered for relevance to solar electricity and refreshed in the background about every hour. The articles are listed for information and the investor decides how to use them; only the daily news coefficient (a separate computation) adjusts revenue, never the kWh forecast. Each item has a title, source, date, link and short excerpt.
Keywords (FR): actualites, news, presse, avis STEG, information, collecte, pertinence.
