"""
EnerX - Taux de change TND -> USDC en direct (API Frankfurter, fournisseur BCT).

get_fx() renvoie (fx, avertissement) comme aggregator.load_fx, avec le meme format.
Ordre : cache memoire (6 h) -> API en direct -> repli sur fx_rate.json (statut EXEMPLE).
Hypothese affichee : 1 USDC = 1 USD. Le taux, sa source et sa date vont dans le rapport (donc le hash).
"""
import math
import time
from datetime import datetime, timezone

import requests

URL = "https://api.frankfurter.dev/v2/rate/USD/TND"
TTL_SECONDS = 6 * 3600
_cache = {"t": 0.0, "value": None}


def _extraire_taux(data):
    """Accepte {"rate": x}, {"rates": {"TND": x}} ou une liste de ces objets. Retourne (TND par USD, date, fournisseur)."""
    if isinstance(data, list):
        data = data[0]
    rate = data.get("rate")
    if rate is None:
        rate = (data.get("rates") or {}).get("TND")
    return float(rate), str(data.get("date", "")), str(data.get("provider") or data.get("providers") or "")


def fetch_live():
    r = requests.get(URL, params={"providers": "BCT"}, timeout=10)
    r.raise_for_status()
    tnd_par_usd, date, provider = _extraire_taux(r.json())
    if not math.isfinite(tnd_par_usd) or not (1.0 < tnd_par_usd < 10.0):     # 1 USD vaut ~3 TND
        raise ValueError(f"taux invraisemblable : {tnd_par_usd}")
    return {
        "from": "TND", "to": "USDC",
        "rate": round(1.0 / tnd_par_usd, 6),
        "source": f"Frankfurter API ({provider or 'BCT'}) USD/TND={tnd_par_usd}; 1 USDC = 1 USD (hypothese)",
        "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "OFFICIEL" if "BCT" in provider.upper() or not provider else "MARCHE",
    }


def get_fx(fallback):
    """fallback : fonction sans argument qui renvoie (fx, warn), par ex. aggregator.load_fx."""
    if _cache["value"] and time.time() - _cache["t"] < TTL_SECONDS:
        return _cache["value"], None
    try:
        fx = fetch_live()
        _cache.update(t=time.time(), value=fx)
        return fx, None
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as e:
        fx, warn = fallback()
        extra = f"Taux en direct indisponible ({e.__class__.__name__}), repli sur fx_rate.json."
        return fx, (extra + " " + warn) if warn else extra