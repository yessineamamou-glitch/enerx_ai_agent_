"""
EnerX - Agregateur : kWh prevus -> revenu -> dividende par token (+ hash pour Hedera)

dividende/token = kWh prevus x tarif STEG (DT/kWh) x coef news / nombre de tokens

CORRECTIF HASH : la regle de canonisation a change (voir hash_report). Tout hash ancre
avant cette version ne correspond plus : regenerer les rapports et prevenir le dev Hedera.
"""
import hashlib
import json
import math
import os
from datetime import datetime, timezone

from production import forecast

FX_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "fx_rate.json")


def load_fx(path=FX_FILE):
    """Taux TND -> USDC fige dans le rapport (et donc dans le hash). Retourne (fx, avertissement).
    Le taux vient d'un fichier maintenu par l'equipe : valeur, source, date, statut (EXEMPLE / OFFICIEL).
    Le frontend ne doit JAMAIS convertir lui-meme : il affiche les champs *_usdc du rapport."""
    try:
        with open(path, encoding="utf-8") as f:
            fx = json.load(f)
        rate = float(fx["rate"])
        if not (0 < rate < 10) or not math.isfinite(rate):
            raise ValueError("taux hors plage")
        out = {"from": "TND", "to": "USDC", "rate": rate, "source": str(fx["source"]),
               "date": str(fx["date"]), "status": str(fx.get("status", "NON PRECISE"))}
        warn = None
        if out["status"].upper() != "OFFICIEL":
            warn = ("Taux de change TND/USDC non officiel (statut : %s) : montants USDC indicatifs." % out["status"])
        return out, warn
    except (OSError, KeyError, ValueError, TypeError) as e:
        return None, f"Taux de change TND/USDC indisponible ({e.__class__.__name__}) : montants USDC absents."

# Tarifs d'achat STEG du photovoltaique (DT/kWh, hors taxes), selon la capacite du projet.
# Source : arrete publie au JORT, rapporte par managers.tn le 14 octobre 2024.
# A reverifier avant la presentation finale.
def steg_tariff(capacity_kw):
    if capacity_kw < 1000:        # moins de 1 MW
        return 0.217
    if capacity_kw < 2000:        # 1 a 2 MW
        return 0.201
    if capacity_kw <= 10000:      # 2 a 10 MW
        return 0.142
    raise ValueError("Capacite au-dela de 10 MW : tarif non couvert")


def build_report(pred, lat, lon, capacity_kw, tariff=None, n_tokens=1000, news_coef=1.0,
                 news=None, warnings=None, interval_source=None, fx=None):
    """
    pred : DataFrame avec colonnes date, temperature, irradiance, kwh, low, high
           (sortie de forecast.predict_days)
    warnings : liste de textes (forecast.quality_warnings) -> incluse dans le rapport et le hash
    """
    tariff = steg_tariff(capacity_kw) if tariff is None else tariff
    warnings = list(warnings or [])
    if fx is None:
        from production import fx as fxlive            # taux en direct, repli sur fx_rate.json
        fx, fx_warn = fxlive.get_fx(load_fx)
        if fx_warn:
            warnings.append(fx_warn)
    rate = fx["rate"] if fx else None
    if interval_source is None:
        interval_source = forecast.interval_source()

    days = []
    for r in pred.itertuples():
        rev = r.kwh * tariff * news_coef
        rev_low = r.low * tariff * news_coef
        rev_high = r.high * tariff * news_coef
        days.append({
            "date": r.date.strftime("%Y-%m-%d"),
            "temperature_c": float(r.temperature),
            "irradiance_wh_m2": float(r.irradiance),
            "kwh": float(r.kwh),
            "kwh_low": float(r.low),
            "kwh_high": float(r.high),
            "revenue_dt": round(rev, 3),
            "dividend_per_token_dt": round(rev / n_tokens, 6),
            "dividend_per_token_low_dt": round(rev_low / n_tokens, 6),
            "dividend_per_token_high_dt": round(rev_high / n_tokens, 6),
        })
        if rate:
            days[-1].update({
                "revenue_usdc": round(rev * rate, 4),
                "dividend_per_token_usdc": round(rev * rate / n_tokens, 6),
                "dividend_per_token_low_usdc": round(rev_low * rate / n_tokens, 6),
                "dividend_per_token_high_usdc": round(rev_high * rate / n_tokens, 6),
            })

    total_kwh = sum(d["kwh"] for d in days)
    total_rev = sum(d["revenue_dt"] for d in days)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "location": {"lat": lat, "lon": lon},
        "capacity_kw": capacity_kw,
        "assumptions": {
            "tariff_dt_per_kwh": tariff,
            "n_tokens": n_tokens,
            "news_coefficient": news_coef,
            "weather_source": "Open-Meteo forecast API",
            "irradiance_correction": forecast.IRRADIANCE_SCALE,
            "interval": interval_source,
            "model": "MLP 128-64-32 (sklearn) trained on PVGIS simulated data 2019-2023",
        },
        "days": days,
        "totals": {
            "kwh": round(total_kwh, 2),
            "revenue_dt": round(total_rev, 3),
            "dividend_per_token_dt": round(total_rev / n_tokens, 6),
        },
    }
    if fx:
        report["assumptions"]["fx"] = fx
        total_usdc = sum(d["revenue_usdc"] for d in days)
        report["totals"]["revenue_usdc"] = round(total_usdc, 4)
        report["totals"]["dividend_per_token_usdc"] = round(total_usdc / n_tokens, 6)
    if warnings:
        report["warnings"] = list(warnings)
    if news is not None:
        report["news"] = news      # analyse de l'agent news (incluse dans le hash)
    report["report_hash"] = hash_report(report)
    return report


# ----------------------------------------------------------------------------
# HASH : meme resultat en Python et en JavaScript
# ----------------------------------------------------------------------------
def _nombre_canonique(x):
    """Nombre -> texte decimal fixe (6 decimales, zeros de fin retires).
    Evite les ecarts d'ecriture entre langages : Python ecrit 1e-05 la ou JavaScript
    ecrit 0.00001, et 5939.0 / 5939. Exemples : 5939.0 -> "5939", 0.00001 -> "0.00001"."""
    if not math.isfinite(x):
        raise ValueError("Valeur non finie (NaN/inf) dans le rapport : refus de calculer le hash")
    s = f"{float(x):.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _normaliser(x):
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (int, float)):
        return _nombre_canonique(x)
    if isinstance(x, dict):
        return {k: _normaliser(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_normaliser(v) for v in x]
    return x


def hash_report(report):
    """SHA-256 du rapport (sans le champ report_hash) -> a ancrer sur Hedera HCS.

    Methode de verification (n'importe quel langage) :
      1. retirer le champ report_hash ;
      2. remplacer CHAQUE nombre par un texte : arrondi a 6 decimales, zeros de fin retires
         (5939.0 -> "5939", 0.00001 -> "0.00001", 45.95 -> "45.95") ;
      3. trier les cles de tous les objets, JSON compact (separateurs , et :), UTF-8 sans echappement ;
      4. SHA-256 en hexadecimal.
    Un exemple JavaScript complet est fourni dans verify_hash.js."""
    body = {k: v for k, v in report.items() if k != "report_hash"}
    canonical = json.dumps(_normaliser(body), sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()