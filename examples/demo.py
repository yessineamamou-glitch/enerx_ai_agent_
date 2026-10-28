"""
EnerX - DEMO de bout en bout (pour la repetition et le pitch)

coordonnees du toit -> meteo -> production prevue -> news -> dividende par token -> hash Hedera
Lancement :  python demo.py        (a mettre dans le meme dossier que les autres fichiers)
Mets PAUSE = True pour avancer etape par etape avec la touche Entree pendant la presentation.
"""
import copy
import os
import json

import requests

from news import news_feed
from production import aggregator, forecast

# ---------------- Parametres de la demo ----------------
NOM_TOIT = "Villa de M. Ben Ali (exemple)"
LAT, LON = 32.9297, 10.4518        # Tataouine : montre que le sud est couvert
CAPACITE_KW = 10
N_TOKENS = 1000
JOURS = 7
PAUSE = False
ANCHOR_ON_HEDERA = False   # True = publie vraiment le hash sur Hedera testnet (necessite .env configure)


def etape(titre):
    print("\n" + "=" * 70)
    print(titre)
    print("=" * 70)
    if PAUSE:
        input("   [Entree pour continuer]")


# ---------------- 1. Le toit ----------------
etape("ETAPE 1 - Un proprietaire enregistre son toit (DID Hedera)")
print(f"   Toit      : {NOM_TOIT}")
print(f"   Position  : lat {LAT}, lon {LON}")
print(f"   Centrale  : {CAPACITE_KW} kW  ->  {N_TOKENS} EnerTokens (1 token = {100 / N_TOKENS:.1f} % des revenus)")

# ---------------- 2. Meteo + production ----------------
etape("ETAPE 2 - L'agent IA predit la production (reseau de neurones + meteo Open-Meteo)")
hors_ligne = None
try:
    payload = forecast.fetch_hourly_forecast(LAT, LON, JOURS)
except requests.RequestException as e:
    print(f"   Open-Meteo indisponible ({e.__class__.__name__}) -> plan B : derniere prevision enregistree")
    payload, hors_ligne = forecast.load_cached_forecast(LAT, LON, JOURS)
    print(f"   {hors_ligne}")
daily = forecast.hourly_to_daily(payload)
pred = forecast.predict_days(daily, LAT, LON, CAPACITE_KW)
avertissements = forecast.quality_warnings(daily, LAT, LON, JOURS) + ([hors_ligne] if hors_ligne else [])
for a in avertissements:
    print(f"   ATTENTION : {a}")
print(f"   {'Date':<12}{'Temp C':>8}{'Irrad Wh/m2':>13}{'kWh':>8}{'Bas':>8}{'Haut':>8}")
for r in pred.itertuples():
    print(f"   {r.date.strftime('%Y-%m-%d'):<12}{r.temperature:>8}{r.irradiance:>13.0f}{r.kwh:>8}{r.low:>8}{r.high:>8}")

# ---------------- 3. News (information seulement) ----------------
etape("ETAPE 3 - Actualites energie / STEG (affichees a l'utilisateur, SANS effet sur le calcul)")
news = news_feed.get_news()
print(f"   Source : {news['origin']}")
for h in news["items"][:5]:
    print(f"   - {h['date'] or '?'} | {h['source']} | {h['title'][:75]}")
if not news["items"]:
    print("   (aucune news en cache : lancer python etape1_collecte.py)")

# ---------------- 4. Dividende ----------------
etape("ETAPE 4 - Calcul du dividende par token (tarif de rachat STEG)")
report = aggregator.build_report(pred, LAT, LON, CAPACITE_KW, n_tokens=N_TOKENS,
                                 warnings=avertissements)
a = report["assumptions"]
print(f"   Tarif STEG : {a['tariff_dt_per_kwh']} DT/kWh ")
print(f"   {'Date':<12}{'kWh':>8}{'Revenu DT':>12}{'Dividende/token DT':>22}")
for d in report["days"]:
    print(f"   {d['date']:<12}{d['kwh']:>8}{d['revenue_dt']:>12}{d['dividend_per_token_dt']:>22}")
t = report["totals"]
print(f"\n   Total {JOURS} jours : {t['kwh']} kWh -> {t['revenue_dt']} DT -> {t['dividend_per_token_dt']} DT par token")
if "fx" in a:
    print(f"   USDC : taux {a['fx']['rate']} ({a['fx']['source']}, {a['fx']['date']}, statut {a['fx']['status']})")
    print(f"          {t['revenue_usdc']} USDC -> {t['dividend_per_token_usdc']} USDC par token (fige dans le hash)")

# ---------------- 5. Hash ----------------
etape("ETAPE 5 - Empreinte (hash) du rapport, a ancrer sur Hedera Consensus Service")
print(f"   SHA-256 : {report['report_hash']}")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print("   Rapport complet sauvegarde : demo_report.json")

# ---------------- 6. Preuve d'integrite ----------------
etape("ETAPE 6 - Preuve d'integrite : modifier UN chiffre change tout le hash")
falsifie = copy.deepcopy(report)
falsifie["days"][0]["kwh"] += 1
print(f"   Hash original  : {report['report_hash'][:32]}...")
print(f"   Hash falsifie  : {aggregator.hash_report(falsifie)[:32]}...")
print(f"   Rapport original intact ? {aggregator.hash_report(report) == report['report_hash']}")
print(f"   Rapport falsifie intact ? {aggregator.hash_report(falsifie) == report['report_hash']}")
if ANCHOR_ON_HEDERA:
    from hedera import hcs_anchor
    etape("ETAPE 7 - Ancrage reel sur Hedera Consensus Service (testnet)")
    res = hcs_anchor.anchor_report(report)
    print(f"   Topic          : {res['topic_id']}")
    print(f"   Message n°     : {res['sequence_number']}")
    print(f"   Transaction ID : {res['transaction_id']}")
    print(f"   Voir sur HashScan : {res['hashscan']}")
    v = hcs_anchor.verify_report(report, res["sequence_number"])
    print(f"   Verification via Mirror Node : {'AUTHENTIQUE' if v['ok'] else 'ECHEC'}")

print("\nDemo terminee.")