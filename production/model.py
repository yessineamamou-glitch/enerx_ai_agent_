"""
EnerX - Agent de prediction de production solaire (kWh/jour)
Reseau de neurones : entrees -> 64 -> 32 -> 1 sortie

Pipeline : chargement -> agregation par jour -> features -> split train/dev/test
           -> normalisation -> entrainement -> evaluation -> intervalle -> sauvegarde
"""
import copy
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

# ----------------------------------------------------------------------------
# 0. CONFIGURATION (c'est ici que tu changes les choses)
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "data", "dataset_solar_global_tunisie.csv")   # dans le meme dossier que le script
OUTPUT_DIR = os.path.join(HERE, "data")          # solar_agent.pkl
REPORTS_DIR = os.path.join(HERE, "reports")       # graphiques / resultats

# Split par DATE (dates de fin exclues). Pour 2019-2023 :
#   train = 2019-2021 | dev = 2022 | test = 2023
TRAIN_UNTIL = "2022-01-01"
DEV_UNTIL = "2023-01-01"

BASE_CAPACITY_KW = 10        # capacite utilisee pour generer les donnees PVGIS
HIDDEN_LAYERS = (128, 64, 32)     # 3 couches cachees : 128 -> 64 -> 32 neurones, puis 1 sortie (kWh/jour)
MAX_EPOCHS = 500                 # On augmente le maximum d'époques
PATIENCE = 40                    # On laisse plus de temps au modèle pour converger

SEED = 42

FEATURES = ["latitude", "longitude", "temperature", "irradiance", "jour_sin", "jour_cos"]
TARGET = "production"

# ----------------------------------------------------------------------------
# 1. CHARGEMENT
# ----------------------------------------------------------------------------
print("1. Chargement des donnees...")
df = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])
df = df.dropna(subset=["temperature", "solar_irradiance", "production_kwh"])
print(f"   {len(df)} lignes horaires ({df['timestamp'].min().date()} -> {df['timestamp'].max().date()})")

# ----------------------------------------------------------------------------
# 2. AGREGATION PAR JOUR (heures -> jours)
#    temperature = moyenne | irradiance = somme (Wh/m2/jour) | production = somme (kWh/jour)
# ----------------------------------------------------------------------------
print("2. Agregation par jour...")
df["date"] = df["timestamp"].dt.normalize()
daily = (
    df.groupby(["latitude", "longitude", "date"])
    .agg(
        temperature=("temperature", "mean"),
        irradiance=("solar_irradiance", "sum"),
        production=("production_kwh", "sum"),
    )
    .reset_index()
    .sort_values(["latitude", "longitude", "date"])
    .reset_index(drop=True)
)
print(f"   {len(daily)} lignes journalieres")

# ----------------------------------------------------------------------------
# 3. ENCODAGE DE LA DATE (cyclique : le 31 decembre est proche du 1er janvier)
# ----------------------------------------------------------------------------
jour_annee = daily["date"].dt.dayofyear
daily["jour_sin"] = np.sin(2 * np.pi * jour_annee / 365.25)
daily["jour_cos"] = np.cos(2 * np.pi * jour_annee / 365.25)

# ----------------------------------------------------------------------------
# 4. SPLIT TRAIN / DEV / TEST (par date)
# ----------------------------------------------------------------------------
train = daily[daily["date"] < TRAIN_UNTIL]
dev = daily[(daily["date"] >= TRAIN_UNTIL) & (daily["date"] < DEV_UNTIL)]
test = daily[daily["date"] >= DEV_UNTIL]
print(f"3. Split : train={len(train)} | dev={len(dev)} | test={len(test)}")

X_train, y_train = train[FEATURES].values, train[TARGET].values
X_dev, y_dev = dev[FEATURES].values, dev[TARGET].values
X_test, y_test = test[FEATURES].values, test[TARGET].values

# ----------------------------------------------------------------------------
# 5. NORMALISATION (fit UNIQUEMENT sur le train)
# ----------------------------------------------------------------------------
x_scaler = StandardScaler().fit(X_train)
y_scaler = StandardScaler().fit(y_train.reshape(-1, 1))

X_train_s = x_scaler.transform(X_train)
X_dev_s = x_scaler.transform(X_dev)
X_test_s = x_scaler.transform(X_test)
y_train_s = y_scaler.transform(y_train.reshape(-1, 1)).ravel()


def predict_kwh(model, X_scaled):
    """Predit en kWh reels (on annule la normalisation de y, et pas de valeur negative)."""
    p = model.predict(X_scaled).reshape(-1, 1)
    return np.maximum(y_scaler.inverse_transform(p).ravel(), 0)


# ----------------------------------------------------------------------------
# 6. RESEAU DE NEURONES : entrees -> 64 -> 32 -> 1
#    activation ReLU | optimiseur Adam | arret automatique sur le DEV
# ----------------------------------------------------------------------------
print("4. Entrainement du reseau de neurones...")
model = MLPRegressor(
    hidden_layer_sizes=HIDDEN_LAYERS,
    activation="relu",
    solver="adam",
    learning_rate_init=0.001,
    batch_size=64,
    random_state=SEED,
)

best_model, best_dev_mae, wait = None, np.inf, 0
for epoch in range(1, MAX_EPOCHS + 1):
    model.partial_fit(X_train_s, y_train_s)          # 1 epoque d'apprentissage
    dev_mae = mean_absolute_error(y_dev, predict_kwh(model, X_dev_s))

    if dev_mae < best_dev_mae - 1e-4:                # amelioration -> on garde ce modele
        best_dev_mae, best_model, wait = dev_mae, copy.deepcopy(model), 0
    else:
        wait += 1

    if epoch % 10 == 0 or epoch == 1:
        print(f"   epoque {epoch:3d} | MAE dev = {dev_mae:.3f} kWh/jour (meilleur : {best_dev_mae:.3f})")
    if wait >= PATIENCE:
        print(f"   arret anticipe a l'epoque {epoch} (plus d'amelioration sur le dev)")
        break

model = best_model

# ----------------------------------------------------------------------------
# 7. EVALUATION SUR LE TEST (une seule fois, a la fin)
# ----------------------------------------------------------------------------
print("5. Evaluation sur le jeu de TEST (donnees jamais vues)")
pred_test = predict_kwh(model, X_test_s)
mae_nn = mean_absolute_error(y_test, pred_test)
r2_nn = r2_score(y_test, pred_test)

# Baseline 1 : "demain = aujourd'hui" (production de la veille, meme ville)
daily["veille"] = daily.groupby(["latitude", "longitude"])["production"].shift(1)
test_b = daily.loc[test.index].dropna(subset=["veille"])
mae_persist = mean_absolute_error(test_b["production"], test_b["veille"])

# Baseline 2 : regression lineaire simple (pour verifier que le reseau apporte quelque chose)
lin = LinearRegression().fit(X_train_s, y_train)
mae_lin = mean_absolute_error(y_test, np.maximum(lin.predict(X_test_s), 0))

print(f"   Reseau de neurones : MAE = {mae_nn:.2f} kWh/jour | R2 = {r2_nn:.3f}")
print(f"   Regression lineaire: MAE = {mae_lin:.2f} kWh/jour")
print(f"   Baseline veille    : MAE = {mae_persist:.2f} kWh/jour")
print(f"   Production moyenne : {y_test.mean():.1f} kWh/jour "
      f"(erreur relative du reseau : {100 * mae_nn / y_test.mean():.1f} %)")

test_eval = test.copy()
test_eval["pred"] = pred_test
print("   MAE par ville (test) :")
for (lat, lon), g in test_eval.groupby(["latitude", "longitude"]):
    print(f"     lat={lat:.2f} lon={lon:.2f} -> {mean_absolute_error(g[TARGET], g['pred']):.2f} kWh/jour")

# ----------------------------------------------------------------------------
# 8. INTERVALLE DE CONFIANCE (percentiles 10 % et 90 % des erreurs sur le DEV)
# ----------------------------------------------------------------------------
residus_dev = y_dev - predict_kwh(model, X_dev_s)
RES_LOW, RES_HIGH = np.percentile(residus_dev, [10, 90])
inside = ((y_test >= pred_test + RES_LOW) & (y_test <= pred_test + RES_HIGH)).mean()
print(f"6. Intervalle : prediction {RES_LOW:+.2f} / {RES_HIGH:+.2f} kWh "
      f"(couvre {100 * inside:.0f} % des jours du test, cible = 80 %)")

# ----------------------------------------------------------------------------
# 9. SAUVEGARDE (a charger dans l'API FastAPI)
# ----------------------------------------------------------------------------
bundle = {
    "model": model,
    "x_scaler": x_scaler,
    "y_scaler": y_scaler,
    "features": FEATURES,
    "res_low": float(RES_LOW),
    "res_high": float(RES_HIGH),
    "base_capacity_kw": BASE_CAPACITY_KW,
}
bundle_path = os.path.join(OUTPUT_DIR, "solar_agent.pkl")
joblib.dump(bundle, bundle_path)
print(f"7. Modele sauvegarde : {bundle_path}")

# ----------------------------------------------------------------------------
# 10. GRAPHIQUE POUR LE PITCH (reel vs prediction, 90 derniers jours du test)
# ----------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    g = test_eval[(test_eval["latitude"] == test_eval["latitude"].iloc[0])].tail(90)
    plt.figure(figsize=(10, 4))
    plt.plot(g["date"], g[TARGET], label="Reel (PVGIS)", color="#1f77b4")
    plt.plot(g["date"], g["pred"], label="Prediction du reseau", color="#ff7f0e")
    plt.fill_between(g["date"], g["pred"] + RES_LOW, g["pred"] + RES_HIGH,
                     color="#ff7f0e", alpha=0.2, label="Intervalle 80 %")
    plt.ylabel("kWh / jour")
    plt.title("EnerX - production solaire : reel vs prediction (jeu de test)")
    plt.legend()
    plt.tight_layout()
    png_path = os.path.join(REPORTS_DIR, "resultat_test.png")
    plt.savefig(png_path, dpi=150)
    print(f"8. Graphique sauvegarde : {png_path}")
except Exception as e:
    print("   (graphique ignore :", e, ")")


# ----------------------------------------------------------------------------
# 11. FONCTION A UTILISER PAR LE RESTE DU PROJET (API, agregateur)
# ----------------------------------------------------------------------------
def predict_production(latitude, longitude, temperature, irradiance, date, capacity_kw=10,
                       bundle_file=bundle_path):
    """
    Retourne {"kwh": ..., "low": ..., "high": ...} pour UN jour.
      temperature : temperature moyenne du jour (deg C)
      irradiance  : irradiance totale du jour (somme des valeurs horaires, Wh/m2)
      date        : "YYYY-MM-DD"
      capacity_kw : puissance de la centrale (le modele est entraine sur 10 kW)
    """
    b = joblib.load(bundle_file)
    d = pd.Timestamp(date)
    doy = d.dayofyear
    x = np.array([[latitude, longitude, temperature, irradiance,
                   np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)]])
    xs = b["x_scaler"].transform(x)
    p = b["model"].predict(xs).reshape(-1, 1)
    kwh = max(float(b["y_scaler"].inverse_transform(p)[0, 0]), 0.0)
    scale = capacity_kw / b["base_capacity_kw"]
    return {
        "kwh": round(kwh * scale, 2),
        "low": round(max(kwh + b["res_low"], 0) * scale, 2),
        "high": round(max(kwh + b["res_high"], 0) * scale, 2),
    }


if __name__ == "__main__":
    # Exemple : un jour d'ete a Tunis, centrale de 10 kW
    print("\nExemple de prediction :")
    print(predict_production(36.8065, 10.1815, temperature=28, irradiance=8000,
                             date="2023-07-15", capacity_kw=10))