"""
EnerX - Tests de robustesse (sans internet) : python -m pytest -q tests   (depuis la racine du projet)
Verifie que l'agent reste plausible et ne plante pas face a des entrees absurdes.
"""
import math

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from production import aggregator, forecast
from production import fx as fxmod

BUNDLE = joblib.load(forecast.BUNDLE_PATH)


def jours(irr, temp=25.0, n=3):
    return pd.DataFrame({"date": pd.date_range("2026-07-01", periods=n),
                         "temperature": [temp] * n, "irradiance": [irr] * n})


# ---------- plausibilite physique ----------
@pytest.mark.parametrize("irr", [0, 500, 4000, 8000, 9e6, -500, 1e12])
@pytest.mark.parametrize("cap", [1, 10, 500])
def test_production_toujours_dans_les_limites(irr, cap):
    p = forecast.predict_days(jours(irr), 36.8, 10.18, cap, BUNDLE)
    plafond = forecast.PHYS_MAX_KWH_PER_KW * cap
    for c in ("kwh", "low", "high"):
        assert np.isfinite(p[c]).all()
        assert (p[c] >= 0).all() and (p[c] <= plafond + 1e-6).all()
    assert (p["low"] <= p["kwh"] + 1e-6).all() and (p["kwh"] <= p["high"] + 1e-6).all()


def test_irradiance_absurde_est_plafonnee_et_signalee():
    p = forecast.predict_days(jours(1e9), 36.8, 10.18, 10, BUNDLE)
    assert p.attrs["n_capped"] >= 0
    assert (p["kwh"] <= forecast.PHYS_MAX_KWH_PER_KW * 10).all()


def test_nuit_polaire_donne_zero():
    p = forecast.predict_days(jours(0), 36.8, 10.18, 10, BUNDLE)
    assert (p["kwh"] < 3).all()          # pas de soleil -> quasi rien


def test_hiver_moins_que_ete():
    hiv = forecast.predict_days(jours(2500, 11).assign(date=pd.date_range("2026-12-20", periods=3)), 36.8, 10.18, 10, BUNDLE)
    ete = forecast.predict_days(jours(8000, 33), 36.8, 10.18, 10, BUNDLE)
    assert hiv["kwh"].mean() < ete["kwh"].mean()


# ---------- API : entrees invalides ----------
@pytest.fixture(scope="module")
def client(monkeypatch_module=None):
    import api
    forecast_meteo = jours(6000, 28, 5)
    api.forecast.fetch_hourly_forecast = lambda lat, lon, days: {}
    api.forecast.hourly_to_daily = lambda payload: forecast_meteo
    return TestClient(api.app)


@pytest.mark.parametrize("params", [
    {"lat": "abc", "lon": 10}, {"lat": "nan", "lon": 10}, {"lat": 48.8, "lon": 2.3},
    {"lat": 36.8, "lon": 10.18, "capacity_kw": -1}, {"lat": 36.8, "lon": 10.18, "capacity_kw": 1e12},
    {"lat": 36.8, "lon": 10.18, "days": 0}, {"lat": 36.8, "lon": 10.18, "days": 9999},
    {"lat": 36.8, "lon": 10.18, "n_tokens": 0},
    {"lat": 36.8, "lon": 10.18, "tariff": -3}, {"lat": "36.8; DROP TABLE", "lon": 10.18},
    {"lat": "inf", "lon": 10.18},
])
def test_entrees_absurdes_refusees_proprement(client, params):
    r = client.get("/forecast", params=params)
    assert r.status_code == 422, (params, r.status_code, r.text[:200])


def test_rapport_valide_et_hash_intact(client):
    r = client.get("/forecast", params={"lat": 36.8, "lon": 10.18, "capacity_kw": 10, "days": 5})
    assert r.status_code == 200
    rep = r.json()
    assert aggregator.hash_report(rep) == rep["report_hash"]
    falsifie = {**rep, "totals": {**rep["totals"], "kwh": rep["totals"]["kwh"] + 0.01}}
    assert aggregator.hash_report(falsifie) != rep["report_hash"]
    for j in rep["days"]:
        assert all(math.isfinite(v) for v in j.values() if isinstance(v, (int, float)))


# ---------- les news n'influencent PAS le calcul ----------
def test_news_n_influencent_pas_le_dividende(client):
    base = client.get("/forecast", params={"lat": 36.8, "lon": 10.18, "capacity_kw": 10, "days": 5}).json()
    # un ancien client qui enverrait news_coef / use_news : parametres ignores, resultat identique
    autre = client.get("/forecast", params={"lat": 36.8, "lon": 10.18, "capacity_kw": 10, "days": 5,
                                            "news_coef": 1.5, "use_news": "true"}).json()
    assert base["totals"] == autre["totals"]
    assert base["assumptions"]["news_coefficient"] == 1.0
    assert "news" not in base


def test_endpoint_news_forme_et_information_seulement(client, monkeypatch):
    from news import news_feed
    monkeypatch.setattr(news_feed, "maybe_refresh", lambda: False)
    r = client.get("/news")
    assert r.status_code == 200
    body = r.json()
    assert body["informational_only"] is True
    assert isinstance(body["items"], list)
    assert "news_coef" not in body


# ---------- collecte des news ----------
def test_collecte_filtre_whitelist_sujet_fraicheur_doublons():
    from news import news_fetch
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    iso = lambda d: (now - timedelta(days=d)).isoformat()
    brut = [
        {"title": "La STEG lance un appel d'offres solaire", "source_url": "https://www.tap.info.tn/a1", "source_name": "tap", "published": iso(1)},
        {"title": "La STEG lance un appel d'offres solaire", "source_url": "https://www.tap.info.tn/a1", "source_name": "tap", "published": iso(1)},   # doublon
        {"title": "Solaire : faux site", "source_url": "https://managers.tn.evil.com/x", "source_name": "x", "published": iso(1)},
        {"title": "Solaire : http non securise", "source_url": "http://tap.info.tn/b", "source_name": "x", "published": iso(1)},
        {"title": "Match de football", "source_url": "https://www.tap.info.tn/sport", "source_name": "tap", "published": iso(1)},
        {"title": "Energie : vieil article", "source_url": "https://www.tap.info.tn/old", "source_name": "tap", "published": iso(60)},
    ]
    gardes, rej = news_fetch.filtrer(brut, now)
    assert [a["source_url"] for a in gardes] == ["https://www.tap.info.tn/a1"] and rej == 5