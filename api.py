"""
EnerX - API de l'agent IA (a appeler par le dashboard / le backend)

Installation :  pip install fastapi uvicorn
Lancement   :  uvicorn api:app --reload --port 8001   (le front attend le port 8001 : NEXT_PUBLIC_AI_API_URL)
Documentation interactive automatique : http://127.0.0.1:8001/docs

Structure : production/ (prevision + dividende), news/ (fil d'actualite), hedera/ (ancrage).
Les news sont affichees a titre informatif : elles ne modifient JAMAIS la prevision ni le dividende.
Option : ENERX_STRICT_RANGE=1 refuse (422) les positions hors de la zone d'entrainement
         au lieu de les accepter avec un avertissement dans le rapport.
"""
import os
import joblib
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from news import news_feed
from production import aggregator, forecast

try:                      # lit le fichier .env s'il existe (options facultatives)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

app = FastAPI(title="EnerX AI Agent", version="2.0")

# Autorise le frontend (React, etc.) a appeler l'API depuis le navigateur
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BUNDLE = joblib.load(forecast.BUNDLE_PATH)   # modele charge une seule fois au demarrage
STRICT_RANGE = os.environ.get("ENERX_STRICT_RANGE") == "1"

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/news")
def get_news():
    """Dernieres actualites energie / STEG (etape 1 : collecte seulement). Information, pas de calcul."""
    return news_feed.get_news()


@app.get("/forecast")
def get_forecast(
    lat: float = Query(..., ge=30.0, le=37.6, description="Latitude de la centrale (Tunisie)"),
    lon: float = Query(..., ge=7.4, le=11.7, description="Longitude de la centrale (Tunisie)"),
    capacity_kw: float = Query(10, gt=0, le=10000, description="Puissance de la centrale en kW"),
    days: int = Query(7, ge=1, le=14, description="Nombre de jours de prevision"),
    n_tokens: int = Query(1000, ge=1, description="Nombre de tokens de la centrale"),
    tariff: float | None = Query(None, gt=0, description="Tarif DT/kWh (par defaut : tarif STEG selon la capacite)"),
):
    try:
        payload = forecast.fetch_hourly_forecast(lat, lon, days)
        daily = forecast.hourly_to_daily(payload)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Service meteo indisponible, reessayer plus tard")
    except (KeyError, ValueError):
        raise HTTPException(status_code=502, detail="Reponse meteo inattendue, reessayer plus tard")

    if daily.empty:
        raise HTTPException(status_code=502, detail="Aucun jour complet dans la prevision meteo")

    warnings = forecast.quality_warnings(daily, lat, lon, days)
    if STRICT_RANGE and any(w.startswith("Position hors") for w in warnings):
        raise HTTPException(status_code=422, detail=warnings[0])

    pred = forecast.predict_days(daily, lat, lon, capacity_kw, BUNDLE)
    if pred.attrs.get("n_capped"):
        warnings.append(f"{pred.attrs['n_capped']} jour(s) plafonne(s) au maximum physique "
                        f"({forecast.PHYS_MAX_KWH_PER_KW} kWh/kW/jour).")
    # Le dividende ne depend que de la production prevue x tarif STEG : coefficient news fixe a 1.
    return aggregator.build_report(pred, lat, lon, capacity_kw, tariff, n_tokens, 1.0, None,
                                   warnings=warnings)


@app.get("/")
def home():
    return {
        "project": "EnerX AI Agent",
        "status": "running",
        "model_architecture": "MLPRegressor (128, 64, 32)",
        "documentation": "http://127.0.0.1:8001/docs"
    }