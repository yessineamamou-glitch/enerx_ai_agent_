"""
EnerX - Test de la VILLE CACHEE (leave-one-city-out)

Question : le modele sait-il predire pour un lieu qu'il n'a JAMAIS vu ?
Il compare 2 versions : AVEC latitude/longitude comme entrees, et SANS (le reseau ne peut alors
pas "reconnaitre" une ville, il doit se baser uniquement sur la meteo).
Methode  : pour chaque ville cachee H
           - entrainement sur toutes les AUTRES villes (train/dev comme dans model.py)
           - test sur H, annee de test uniquement (nouveau lieu ET nouvelle periode = test le plus strict)
Ce script n'ecrase pas solar_agent.pkl.
"""
import copy
import os

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # dossier production/
CSV_PATH = os.path.join(HERE, "data", "dataset_solar_global_tunisie.csv")   # dans le meme dossier que le script
OUTPUT_DIR = os.path.join(HERE, "reports")

# Noms exacts de la colonne "ville" de ton CSV
VILLES_CACHEES = ["Tataouine", "Kasserine", "Bizerte", "Tozeur"]

TRAIN_UNTIL = "2022-01-01"   # train : avant cette date
DEV_UNTIL = "2023-01-01"     # dev : entre les deux | test : apres
FEATURES_AVEC = ["latitude", "longitude", "temperature", "irradiance", "jour_sin", "jour_cos"]
FEATURES_SANS = ["temperature", "irradiance", "jour_sin", "jour_cos"]   # sans coordonnees
TARGET = "production"
MAX_EPOCHS, PATIENCE, SEED = 500, 40, 42


def charger_journalier(path):
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.dropna(subset=["temperature", "solar_irradiance", "production_kwh"])
    df["date"] = df["timestamp"].dt.normalize()
    d = (df.groupby(["ville", "latitude", "longitude", "date"])
         .agg(temperature=("temperature", "mean"),
              irradiance=("solar_irradiance", "sum"),
              production=("production_kwh", "sum"))
         .reset_index())
    doy = d["date"].dt.dayofyear
    d["jour_sin"] = np.sin(2 * np.pi * doy / 365.25)
    d["jour_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return d


def entrainer(train, dev, FEATURES):
    """Meme procedure que model.py. Retourne des fonctions de prediction."""
    xs = StandardScaler().fit(train[FEATURES].values)
    ys = StandardScaler().fit(train[[TARGET]].values)

    def predire(model, df):
        p = model.predict(xs.transform(df[FEATURES].values)).reshape(-1, 1)
        return np.maximum(ys.inverse_transform(p).ravel(), 0)

    Xtr = xs.transform(train[FEATURES].values)
    ytr = ys.transform(train[[TARGET]].values).ravel()

    model = MLPRegressor(hidden_layer_sizes=(128,64, 32), activation="relu", solver="adam",
                         learning_rate_init=0.001, batch_size=64, random_state=SEED)
    best, best_mae, wait = None, np.inf, 0
    for _ in range(MAX_EPOCHS):
        model.partial_fit(Xtr, ytr)
        mae = mean_absolute_error(dev[TARGET], predire(model, dev))
        if mae < best_mae - 1e-4:
            best, best_mae, wait = copy.deepcopy(model), mae, 0
        else:
            wait += 1
        if wait >= PATIENCE:
            break

    lin = LinearRegression().fit(Xtr, train[TARGET].values)
    return (lambda df: predire(best, df),
            lambda df: np.maximum(lin.predict(xs.transform(df[FEATURES].values)), 0))


print("Chargement et agregation...")
daily = charger_journalier(CSV_PATH)
villes = sorted(daily["ville"].unique())
print(f"   {len(villes)} villes : {villes}")

# --- Reference : modele entraine sur TOUTES les villes (comme model.py) -------------
tr = daily[daily["date"] < TRAIN_UNTIL]
dv = daily[(daily["date"] >= TRAIN_UNTIL) & (daily["date"] < DEV_UNTIL)]
te = daily[daily["date"] >= DEV_UNTIL]
print("Entrainement de reference (toutes les villes)...")
pred_ref, _ = entrainer(tr, dv, FEATURES_AVEC)

lignes = []
for h in VILLES_CACHEES:
    if h not in villes:
        print(f"- {h} : introuvable dans le CSV, ignoree")
        continue
    print(f"- Ville cachee : {h} (entrainement sur les {len(villes) - 1} autres)...")
    autres = daily[daily["ville"] != h]
    tr_h = autres[autres["date"] < TRAIN_UNTIL]
    dv_h = autres[(autres["date"] >= TRAIN_UNTIL) & (autres["date"] < DEV_UNTIL)]
    cible = te[te["ville"] == h]                      # ville jamais vue + annee jamais vue

    pred_nn, pred_lin = entrainer(tr_h, dv_h, FEATURES_AVEC)
    pred_nn2, _ = entrainer(tr_h, dv_h, FEATURES_SANS)
    mae_avec = mean_absolute_error(cible[TARGET], pred_nn(cible))
    mae_sans = mean_absolute_error(cible[TARGET], pred_nn2(cible))
    mae_lin = mean_absolute_error(cible[TARGET], pred_lin(cible))
    mae_connue = mean_absolute_error(cible[TARGET], pred_ref(cible))
    lignes.append({
        "ville": h,
        "MAE_ville_connue": round(mae_connue, 2),
        "MAE_cachee_AVEC_coord": round(mae_avec, 2),
        "MAE_cachee_SANS_coord": round(mae_sans, 2),
        "MAE_lineaire_cachee": round(mae_lin, 2),
        "erreur_relative_SANS_%": round(100 * mae_sans / cible[TARGET].mean(), 1),
    })

if lignes:
    res = pd.DataFrame(lignes)
    print("\n=== RESULTATS (MAE en kWh/jour, annee de test) ===")
    print(res.to_string(index=False))
    m_avec, m_sans = res["MAE_cachee_AVEC_coord"].mean(), res["MAE_cachee_SANS_coord"].mean()
    print(f"\nMoyennes : ville connue {res['MAE_ville_connue'].mean():.2f} | "
          f"cachee AVEC coord {m_avec:.2f} | cachee SANS coord {m_sans:.2f} | "
          f"lineaire {res['MAE_lineaire_cachee'].mean():.2f}")
    meilleur = "SANS" if m_sans < m_avec else "AVEC"
    print(f"=> Pour des lieux nouveaux, la version {meilleur} coordonnees est la meilleure.")
    out = os.path.join(OUTPUT_DIR, "resultat_ville_cachee.csv")
    res.to_csv(out, index=False)
    print(f"Sauvegarde : {out}")