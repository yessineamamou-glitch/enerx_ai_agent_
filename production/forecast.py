"""
EnerX - Prevision de production solaire pour les prochains jours
Utilise le modele entraine (solar_agent.pkl, cree par model.py) + les previsions meteo Open-Meteo.

IMPORTANT : ce fichier ne re-entraine rien. Il charge juste le modele sauvegarde.
Mets-le dans le MEME dossier que solar_agent.pkl, puis lance :  python forecast.py

Fichiers optionnels (crees par les scripts de verification, utilises automatiquement s'ils existent) :
  - pvgis_tilts.json        (check_pvgis_tilt.py)  : inclinaison reelle des angles optimaux PVGIS
  - chain_calibration.json  (evaluate_chain.py)    : intervalle calibre sur la chaine complete
"""
import json
import os
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import requests

# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
BUNDLE_PATH = os.path.join(DATA_DIR, "solar_agent.pkl")
REPORT_PATH = os.path.join(DATA_DIR, "forecast_report.json")
TILTS_PATH = os.path.join(DATA_DIR, "pvgis_tilts.json")
CALIB_PATH = os.path.join(DATA_DIR, "chain_calibration.json")
LAST_FORECAST_PATH = os.path.join(DATA_DIR, "last_forecast_cache.json")   # plan B de la demo uniquement

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Valeurs par defaut si pvgis_tilts.json n'existe pas encore (NON VERIFIEES : lance
# check_pvgis_tilt.py pour obtenir les vraies valeurs). Open-Meteo : azimut 0 = plein sud.
PANEL_TILT = 30
PANEL_AZIMUTH = 0

# CORRECTION DE SOURCE METEO : l'irradiance Open-Meteo est en moyenne 7 % plus basse que celle de PVGIS
# (evaluate_chain.py : rapport OM/PVGIS = 0,927 en 2023 ; 1/0,927 = 1,08). Sans correction le reseau
# sous-estime la production d'environ 3 kWh/jour (biais mesure). Facteur calibre sur 2022, verifie sur 2023.
# A recalibrer si la source meteo change : relancer evaluate_chain.py et regarder irradiance_ratio.
IRRADIANCE_SCALE = 1.08

# Zone couverte par les 12 villes d'entrainement (+ marge) : en dehors, le reseau extrapole.
TRAIN_LAT = (32.93, 37.27)
TRAIN_LON = (8.13, 10.85)
BOX_MARGIN = 0.5            # degres
IRRADIANCE_MAX_OK = 9000    # entrainement : 546 a 8396 Wh/m2/jour
MAX_RELIABLE_DAYS = 7
PHYS_MAX_KWH_PER_KW = 7.2   # plafond physique : max PVGIS observe 6.87 kWh/kWp/jour (+5 %)
REL_FLOOR_KWH = 5.0         # plancher du denominateur pour l'intervalle relatif (base 10 kW)

VILLES = {
    "Tunis": (36.8065, 10.1815),
    "Sousse": (35.8256, 10.6369),
    "Tozeur": (33.9197, 8.1335),
    "Gabes": (33.8881, 10.0982),
}


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


TILTS = _load_json(TILTS_PATH)           # {"Tunis": {"lat":..,"tilt":..,"azimuth":..}, ...} ou None
CALIBRATION = _load_json(CALIB_PATH)     # voir evaluate_chain.py ou None


def tilt_for(lat):
    """Inclinaison/azimut a demander a Open-Meteo : interpolation sur la latitude des 12 valeurs
    PVGIS reelles si pvgis_tilts.json existe, sinon valeurs par defaut."""
    if not TILTS:
        return PANEL_TILT, PANEL_AZIMUTH
    pts = sorted(TILTS.values(), key=lambda v: v["lat"])
    lats = [p["lat"] for p in pts]
    return (float(np.interp(lat, lats, [p["tilt"] for p in pts])),
            float(np.interp(lat, lats, [p["azimuth"] for p in pts])))


# ----------------------------------------------------------------------------
# 1. TELECHARGER LES PREVISIONS METEO (par heure)
# ----------------------------------------------------------------------------
def fetch_hourly_forecast(lat, lon, days=7):
    """Telecharge la prevision. 3 essais (pause 1 s puis 2 s) si Open-Meteo est surcharge (429, 5xx)
    ou injoignable ; la derniere reponse valide est gardee dans last_forecast_cache.json (plan B demo)."""
    tilt, azimuth = tilt_for(lat)
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,global_tilted_irradiance",
        "tilt": round(tilt, 1),
        "azimuth": round(azimuth, 1),
        "forecast_days": days,
        "timezone": "UTC",   # PVGIS (donnees d'entrainement) est en UTC -> memes jours
    }
    derniere_erreur = None
    for essai in range(3):
        try:
            r = requests.get(OPEN_METEO_URL, params=params, timeout=30)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{r.status_code} (service surcharge)", response=r)
            r.raise_for_status()
            payload = r.json()
            _sauver_cache(payload, lat, lon, days)
            return payload
        except requests.RequestException as e:
            derniere_erreur = e
            if essai < 2:
                time.sleep(2 ** essai)
    raise derniere_erreur


def _cle_cache(lat, lon, days):
    return f"{lat:.2f},{lon:.2f},{days}"


def _sauver_cache(payload, lat, lon, days):
    try:
        with open(LAST_FORECAST_PATH, "w", encoding="utf-8") as f:
            json.dump({"key": _cle_cache(lat, lon, days),
                       "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "payload": payload}, f)
    except OSError:
        pass   # le cache est facultatif


def load_cached_forecast(lat, lon, days=7):
    """PLAN B DEMO UNIQUEMENT (jamais utilise par l'API : des dividendes ne doivent pas etre
    calcules sur une meteo ancienne). Retourne (payload, avertissement). Leve FileNotFoundError
    s'il n'y a pas de cache pour ces coordonnees et ce nombre de jours."""
    data = _load_json(LAST_FORECAST_PATH)
    if not data or data.get("key") != _cle_cache(lat, lon, days):
        raise FileNotFoundError("Pas de prevision enregistree pour cette position : lance la demo une fois "
                                "avec internet pour creer last_forecast_cache.json")
    return data["payload"], (f"MODE HORS-LIGNE : meteo enregistree le {data['saved_at']} (Open-Meteo "
                             "injoignable) ; dates et montants non actuels, demonstration uniquement.")


# ----------------------------------------------------------------------------
# 2. HEURES -> JOURS (comme dans model.py)
#    temperature = moyenne | irradiance = somme des valeurs horaires (W/m2 x 1h = Wh/m2)
# ----------------------------------------------------------------------------
def hourly_to_daily(payload):
    h = payload["hourly"]
    df = pd.DataFrame({
        "time": pd.to_datetime(h["time"]),
        "temperature": h["temperature_2m"],
        "irradiance": h["global_tilted_irradiance"],
    })
    # CORRECTIF 1 : une valeur manquante (null) ne doit pas passer pour une heure valide
    df = df.dropna(subset=["temperature", "irradiance"])
    # CORRECTIF 2 : Open-Meteo peut renvoyer une petite irradiance NEGATIVE la nuit
    # (probleme connu) qui diminuerait la somme journaliere -> on la ramene a 0
    df["irradiance"] = df["irradiance"].clip(lower=0) * IRRADIANCE_SCALE   # voir IRRADIANCE_SCALE
    df["date"] = df["time"].dt.normalize()
    daily = (
        df.groupby("date")
        .agg(temperature=("temperature", "mean"),
             irradiance=("irradiance", "sum"),
             n_heures=("time", "count"))
        .reset_index()
    )
    return daily[daily["n_heures"] == 24].drop(columns="n_heures")   # jours complets seulement


# ----------------------------------------------------------------------------
# 3. CONTROLES DE QUALITE (a inclure dans le rapport)
# ----------------------------------------------------------------------------
def quality_warnings(daily, lat, lon, days_requested=None):
    w = []
    if not (TRAIN_LAT[0] - BOX_MARGIN <= lat <= TRAIN_LAT[1] + BOX_MARGIN and
            TRAIN_LON[0] - BOX_MARGIN <= lon <= TRAIN_LON[1] + BOX_MARGIN):
        w.append(f"Position hors de la zone d'entrainement (lat {TRAIN_LAT[0]}-{TRAIN_LAT[1]}, "
                 f"lon {TRAIN_LON[0]}-{TRAIN_LON[1]}) : le modele extrapole, prevision moins fiable.")
    if days_requested is not None and days_requested > MAX_RELIABLE_DAYS:
        w.append(f"Horizon superieur a {MAX_RELIABLE_DAYS} jours : la prevision meteo est peu fiable "
                 "et l'intervalle sous-estime l'incertitude.")
    n_hors = int((daily["irradiance"] > IRRADIANCE_MAX_OK).sum()) if len(daily) else 0
    if n_hors:
        w.append(f"{n_hors} jour(s) avec une irradiance hors de la plage d'entrainement "
                 f"(> {IRRADIANCE_MAX_OK} Wh/m2) : verifier l'inclinaison/l'azimut demandes a Open-Meteo.")
    if days_requested is not None and 0 < len(daily) < days_requested - 1:
        w.append("Plusieurs jours incomplets ont ete ecartes de la prevision.")
    return w


def interval_source():
    """Texte decrivant d'ou vient l'intervalle (copie dans le rapport, donc dans le hash)."""
    if CALIBRATION:
        return (f"calibre sur la chaine complete (meteo Open-Meteo '{CALIBRATION['source']}' vs PVGIS, "
                f"mode {CALIBRATION['mode']}, calibration {CALIBRATION['calibration_year']})")
    return "erreurs du modele seul (meteo supposee connue) : optimiste"


# ----------------------------------------------------------------------------
# 4. PREDICTION AVEC LE MODELE ENTRAINE
# ----------------------------------------------------------------------------
def predict_days(daily, lat, lon, capacity_kw=10, bundle=None):
    b = bundle or joblib.load(BUNDLE_PATH)
    out = daily.copy()
    if len(out) == 0:
        for c in ("kwh", "low", "high"):
            out[c] = []
        return out

    doy = daily["date"].dt.dayofyear
    X = pd.DataFrame({
        "latitude": lat,
        "longitude": lon,
        "temperature": daily["temperature"].values,
        "irradiance": daily["irradiance"].values,
        "jour_sin": np.sin(2 * np.pi * doy / 365.25).values,
        "jour_cos": np.cos(2 * np.pi * doy / 365.25).values,
    })[b["features"]]

    xs = b["x_scaler"].transform(X.values)
    p = b["model"].predict(xs).reshape(-1, 1)
    kwh = np.maximum(b["y_scaler"].inverse_transform(p).ravel(), 0)   # kWh pour la capacite de base

    # Intervalle : calibre sur la chaine complete si disponible, sinon erreurs du modele seul
    if CALIBRATION and CALIBRATION["mode"] == "relative":
        den = np.maximum(kwh, REL_FLOOR_KWH)
        low = kwh + CALIBRATION["rel_low"] * den
        high = kwh + CALIBRATION["rel_high"] * den
    elif CALIBRATION:
        low = kwh + CALIBRATION["res_low"]
        high = kwh + CALIBRATION["res_high"]
    else:
        low = kwh + b["res_low"]
        high = kwh + b["res_high"]

    scale = capacity_kw / b["base_capacity_kw"]
    cap = PHYS_MAX_KWH_PER_KW * capacity_kw          # une centrale ne peut pas depasser ce plafond
    brut = kwh * scale
    out["kwh"] = np.minimum(brut, cap).round(2)
    out["low"] = np.minimum(np.maximum(low, 0) * scale, cap).round(2)
    out["high"] = np.minimum(np.maximum(high, 0) * scale, cap).round(2)
    out.attrs["n_capped"] = int((brut > cap).sum())
    out["temperature"] = out["temperature"].round(1)
    out["irradiance"] = out["irradiance"].round(0)
    return out


def forecast_city(nom, capacity_kw=10, days=7, bundle=None):
    lat, lon = VILLES[nom]
    payload = fetch_hourly_forecast(lat, lon, days)
    daily = hourly_to_daily(payload)
    for msg in quality_warnings(daily, lat, lon, days):
        print(f"   ATTENTION {nom} : {msg}")
    return predict_days(daily, lat, lon, capacity_kw, bundle)


# ----------------------------------------------------------------------------
# 5. RAPPORT JSON simple (a donner a l'agregateur / a ancrer sur Hedera HCS)
# ----------------------------------------------------------------------------
def build_report(nom, capacity_kw=10, days=7):
    pred = forecast_city(nom, capacity_kw, days)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "city": nom,
        "capacity_kw": capacity_kw,
        "unit": "kWh/day",
        "model": "MLP 128-64-32 (sklearn), trained on PVGIS simulated data 2019-2023",
        "weather_source": "Open-Meteo forecast API",
        "interval": interval_source(),
        "forecast": [
            {"date": r.date.strftime("%Y-%m-%d"), "kwh": r.kwh, "low": r.low, "high": r.high,
             "temperature_c": r.temperature, "irradiance_wh_m2": r.irradiance}
            for r in pred.itertuples()
        ],
        "total_kwh_period": round(float(pred["kwh"].sum()), 2),
    }


if __name__ == "__main__":
    NOM = "Tunis"
    CAPACITE_KW = 10

    print(f"Prevision {NOM} - centrale {CAPACITE_KW} kW - 7 prochains jours")
    rapport = build_report(NOM, CAPACITE_KW, days=7)

    print(f"\n{'Date':<12}{'Temp C':>8}{'Irrad Wh/m2':>13}{'kWh':>8}{'Bas':>8}{'Haut':>8}")
    for j in rapport["forecast"]:
        print(f"{j['date']:<12}{j['temperature_c']:>8}{j['irradiance_wh_m2']:>13.0f}"
              f"{j['kwh']:>8}{j['low']:>8}{j['high']:>8}")
    print(f"\nTotal sur la periode : {rapport['total_kwh_period']} kWh")
    print(f"Intervalle : {rapport['interval']}")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)
    print(f"Rapport JSON sauvegarde : {REPORT_PATH}")