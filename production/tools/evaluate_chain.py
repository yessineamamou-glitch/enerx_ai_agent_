"""
EnerX - Erreur REELLE de la chaine complete + intervalle calibre

Probleme : le modele est entraine avec l'irradiance PVGIS, mais en production on lui donne
l'irradiance Open-Meteo. Le MAE de 0,65 kWh/jour mesure le reseau avec la meteo PVGIS ; il ne
mesure PAS cette difference de source. Ce script mesure l'erreur de bout en bout :

    meteo Open-Meteo (2022-2023) -> reseau -> kWh   compare a   production PVGIS (verite du dataset)

Calibration sur 2022, evaluation sur 2023 (meme logique train/dev/test que model.py).
Il ecrit chain_calibration.json, que forecast.py utilise ensuite automatiquement pour l'intervalle.

Usage :
    python evaluate_chain.py            # meteo reanalysee (archive-api.open-meteo.com) : source verifiee
    python evaluate_chain.py forecast   # anciennes PREVISIONS (historical-forecast-api) : plus proche de la
                                        # realite ; verifie l'URL et la disponibilite sur open-meteo.com/en/docs

Necessite internet, dataset_solar_global_tunisie.csv et solar_agent.pkl dans le meme dossier.
Lance d'abord check_pvgis_tilt.py (inclinaisons reelles) pour une evaluation correcte.
"""
import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
import requests
from sklearn.metrics import mean_absolute_error

from production import forecast

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # dossier production/
DATA_DIR = os.path.join(HERE, "data")
CSV_PATH = os.path.join(DATA_DIR, "dataset_solar_global_tunisie.csv")
CACHE_DIR = os.path.join(DATA_DIR, "om_cache")

SOURCES = {
    "archive": "https://archive-api.open-meteo.com/v1/archive",
    "forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
}
CAL_YEAR, TEST_YEAR = 2022, 2023
RANGE = ("2022-01-01", "2023-12-31")
TARGET_COVERAGE = 0.80


def load_pvgis_daily(path=CSV_PATH):
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.dropna(subset=["temperature", "solar_irradiance", "production_kwh"])
    df["date"] = df["timestamp"].dt.normalize()
    return (df.groupby(["ville", "latitude", "longitude", "date"])
            .agg(temp_pvgis=("temperature", "mean"),
                 irr_pvgis=("solar_irradiance", "sum"),
                 production=("production_kwh", "sum"))
            .reset_index())


def fetch_om(ville, lat, lon, source):
    """Meteo horaire Open-Meteo 2022-2023 pour une ville (avec cache disque et nouvelle tentative)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f"{ville}_{source}.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    tilt, azimuth = forecast.tilt_for(lat)
    params = {"latitude": lat, "longitude": lon, "start_date": RANGE[0], "end_date": RANGE[1],
              "hourly": "temperature_2m,global_tilted_irradiance",
              "tilt": round(tilt, 1), "azimuth": round(azimuth, 1), "timezone": "UTC"}
    for essai in range(4):
        r = requests.get(SOURCES[source], params=params, timeout=90)
        if r.status_code == 429:
            print("   limite de requetes atteinte, pause 60 s...")
            time.sleep(60)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Open-Meteo {r.status_code} : {r.text[:300]}")
        payload = r.json()
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        time.sleep(1)
        return payload
    raise RuntimeError("Open-Meteo : trop de tentatives")


def build_dataset(pv, source):
    """Une ligne par (ville, jour) avec la meteo PVGIS ET la meteo Open-Meteo."""
    parts = []
    villes = pv.drop_duplicates("ville")[["ville", "latitude", "longitude"]]
    for v in villes.itertuples():
        print(f"- {v.ville}...")
        om = forecast.hourly_to_daily(fetch_om(v.ville, v.latitude, v.longitude, source))
        om = om.rename(columns={"temperature": "temp_om", "irradiance": "irr_om"})
        parts.append(pv[pv["ville"] == v.ville].merge(om, on="date", how="inner"))
    return pd.concat(parts, ignore_index=True)


def predire(data, bundle, temp_col, irr_col):
    """Predit kWh/jour (10 kW) ville par ville avec les colonnes meteo choisies."""
    out = pd.Series(index=data.index, dtype=float)
    for (lat, lon), g in data.groupby(["latitude", "longitude"]):
        d = pd.DataFrame({"date": g["date"], "temperature": g[temp_col], "irradiance": g[irr_col]})
        pred = forecast.predict_days(d, lat, lon, 10, bundle)
        out.loc[g.index] = pred["kwh"].values
    return out


def main(source="archive"):
    if source not in SOURCES:
        raise SystemExit(f"source inconnue : {source} (archive ou forecast)")
    bundle = joblib.load(forecast.BUNDLE_PATH)
    print(f"Chargement PVGIS... | meteo Open-Meteo : {source}")
    pv = load_pvgis_daily()
    data = build_dataset(pv, source)
    data["pred_chain"] = predire(data, bundle, "temp_om", "irr_om")      # chaine reelle
    data["pred_pvgis"] = predire(data, bundle, "temp_pvgis", "irr_pvgis")  # meteo PVGIS (comme model.py)
    data["res"] = data["production"] - data["pred_chain"]
    den = np.maximum(data["pred_chain"], forecast.REL_FLOOR_KWH)
    data["res_rel"] = data["res"] / den

    cal = data[data["date"].dt.year == CAL_YEAR]
    test = data[data["date"].dt.year == TEST_YEAR]

    # --- 1. Erreur de bout en bout (annee de test) ---
    mae_pvgis = mean_absolute_error(test["production"], test["pred_pvgis"])
    mae_chain = mean_absolute_error(test["production"], test["pred_chain"])
    prod_moy = test["production"].mean()
    ratio_irr = test["irr_om"].sum() / test["irr_pvgis"].sum()
    mae_irr = (test["irr_om"] - test["irr_pvgis"]).abs().mean()
    print(f"\n=== ERREUR SUR {TEST_YEAR} ({len(test)} jours-villes) ===")
    print(f"Reseau avec meteo PVGIS  : MAE = {mae_pvgis:.2f} kWh/jour")
    print(f"CHAINE REELLE (Open-Meteo): MAE = {mae_chain:.2f} kWh/jour "
          f"({100 * mae_chain / prod_moy:.1f} % de la production moyenne {prod_moy:.1f})")
    print(f"Biais (verite - prediction): {test['res'].mean():+.2f} kWh/jour")
    print(f"Irradiance Open-Meteo / PVGIS : rapport des totaux = {ratio_irr:.3f} | "
          f"ecart absolu moyen = {mae_irr:.0f} Wh/m2/jour")
    print("MAE par ville (chaine reelle) :")
    par_ville = test.groupby("ville").apply(
        lambda g: mean_absolute_error(g["production"], g["pred_chain"]), include_groups=False)
    for ville, m in par_ville.sort_values().items():
        print(f"   {ville:<10} {m:.2f}")

    # --- 2. Intervalle : absolu et relatif, calibres sur 2022, verifies sur 2023 ---
    res_low, res_high = np.percentile(cal["res"], [10, 90])
    rel_low, rel_high = np.percentile(cal["res_rel"], [10, 90])
    cov_abs = ((test["res"] >= res_low) & (test["res"] <= res_high)).mean()
    cov_rel = ((test["res_rel"] >= rel_low) & (test["res_rel"] <= rel_high)).mean()
    mode = "absolute" if abs(cov_abs - TARGET_COVERAGE) <= abs(cov_rel - TARGET_COVERAGE) else "relative"
    print(f"\n=== INTERVALLE 80 % (calibre {CAL_YEAR}, verifie {TEST_YEAR}) ===")
    print(f"absolu  : [{res_low:+.2f} ; {res_high:+.2f}] kWh -> couvre {100 * cov_abs:.0f} % des jours de test")
    print(f"relatif : [{100 * rel_low:+.1f} % ; {100 * rel_high:+.1f} %] -> couvre {100 * cov_rel:.0f} %")
    print(f"=> mode retenu : {mode} (couverture la plus proche de {100 * TARGET_COVERAGE:.0f} %)")

    result = {
        "source": source, "mode": mode,
        "calibration_year": CAL_YEAR, "test_year": TEST_YEAR,
        "res_low": round(float(res_low), 3), "res_high": round(float(res_high), 3),
        "rel_low": round(float(rel_low), 4), "rel_high": round(float(rel_high), 4),
        "coverage_absolute": round(float(cov_abs), 3), "coverage_relative": round(float(cov_rel), 3),
        "mae_pvgis_weather": round(float(mae_pvgis), 3), "mae_chain": round(float(mae_chain), 3),
        "bias": round(float(test["res"].mean()), 3),
        "irradiance_ratio_om_over_pvgis": round(float(ratio_irr), 4),
        "n_test_days": int(len(test)),
        "note": ("Meteo historique : mesure l'ecart de source meteo + modele, PAS l'erreur de prevision "
                 "a plusieurs jours (plus grande)."),
    }
    out = os.path.join(DATA_DIR, "chain_calibration.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nSauvegarde : {out}\nRedemarre l'API (uvicorn) pour utiliser le nouvel intervalle.")
    return result


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "archive")
