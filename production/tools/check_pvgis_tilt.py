"""
EnerX - Verifie l'inclinaison et l'azimut REELS utilises par PVGIS (optimalangles=1)

Probleme : forecast.py demandait 30 degres a Open-Meteo "a peu pres". Les angles optimaux PVGIS
different un peu selon la ville. Ce script les lit dans la reponse PVGIS (meme appel que la collecte
de donnees) et ecrit pvgis_tilts.json. forecast.py interpole ensuite l'inclinaison sur la latitude.

Usage :  python check_pvgis_tilt.py        (internet requis, environ 1 a 2 minutes)
"""
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # dossier production/
BASE_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"

VILLES = {
    "Tunis": (36.8065, 10.1815), "Bizerte": (37.2744, 9.8739), "Le_Kef": (36.1742, 8.7049),
    "Sousse": (35.8256, 10.6369), "Kairouan": (35.6781, 10.0963), "Kasserine": (35.1676, 8.8365),
    "Sfax": (34.7400, 10.7600), "Tozeur": (33.9197, 8.1335), "Gabes": (33.8881, 10.0982),
    "Matmata": (33.5435, 9.9671), "Djerba": (33.8076, 10.8451), "Tataouine": (32.9297, 10.4518),
}


def lire_angles(data):
    fixed = data["inputs"]["mounting_system"]["fixed"]
    return float(fixed["slope"]["value"]), float(fixed["azimuth"]["value"])


resultats = {}
for ville, (lat, lon) in VILLES.items():
    # MEMES parametres que la collecte (periode comprise : l'angle optimal en depend)
    params = {"lat": lat, "lon": lon, "startyear": 2019, "endyear": 2023, "pvcalculation": 1,
              "peakpower": 10, "loss": 14, "optimalangles": 1, "outputformat": "json"}
    try:
        r = requests.get(BASE_URL, params=params, timeout=120)
        r.raise_for_status()
        tilt, azimuth = lire_angles(r.json())
        resultats[ville] = {"lat": lat, "lon": lon, "tilt": tilt, "azimuth": azimuth}
        print(f"{ville:<10} inclinaison = {tilt:5.1f} deg | azimut = {azimuth:5.1f} deg")
    except (KeyError, TypeError) as e:
        print(f"{ville:<10} structure PVGIS inattendue ({e}). Cles de 'inputs' : "
              f"{list(r.json().get('inputs', {}).keys())} -> adapte lire_angles()")
    except Exception as e:
        print(f"{ville:<10} ERREUR : {e}")
    time.sleep(2)

if len(resultats) == len(VILLES):
    chemin = os.path.join(HERE, "data", "pvgis_tilts.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(resultats, f, indent=2, ensure_ascii=False)
    tilts = sorted(v["tilt"] for v in resultats.values())
    print(f"\nInclinaisons : de {tilts[0]:.0f} a {tilts[-1]:.0f} deg (mediane {tilts[len(tilts) // 2]:.0f}).")
    print(f"Sauvegarde : {chemin}\nRedemarre l'API : forecast.py utilise ces valeurs automatiquement.")
    print("Tu peux maintenant retirer 'non verifie' de la partie Limites du README.")
else:
    print("\nIncomplet : relance le script (pvgis_tilts.json n'a pas ete ecrit).")
