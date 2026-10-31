"""
EnerX - Pont entre coefficient_news.py (RAG -> indice du jour) et GET /forecast.

Regles :
  - /forecast ne calcule JAMAIS le coefficient (4 questions LLM = lent et payant) : il LIT le rapport du jour
    (rag/data/rapports_news/coefficient_news_AAAA-MM-JJ.json) ;
  - rapport absent ou 'indisponible' -> coefficient NEUTRE 1.0 + avertissement dans le rapport, et un calcul est lance
    en arriere-plan (au plus un toutes les REFRESH_COOLDOWN_S) ;
  - le multiplicateur reste dans [0.90, 1.10] (MAX_AJUST) ; le bloc `news` du rapport de prevision (donc le hash Hedera)
    cite l'empreinte du rapport du jour, ses questions, impacts et URL de sources, pour l'audit.
Calcul planifie recommande : python -m rag.coefficient_news --planifier 06:30
"""
import os
import threading
import time
from datetime import datetime

from rag import coefficient_news as cn

REFRESH_COOLDOWN_S = int(os.environ.get("ENERX_NEWS_COEF_COOLDOWN_S", "1800"))
_lock = threading.Lock()
_state = {"running": False, "last_start": 0.0}


def _llm():
    if os.environ.get("ENERX_NEWS_LLM"):
        return os.environ["ENERX_NEWS_LLM"]
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    return "claude" if os.environ.get("ANTHROPIC_API_KEY") else "ollama"


def _calcul():
    try:
        cn.coefficient_du_jour(llm=_llm())
    except BaseException as e:                       # SystemExit (embedder absent), reseau, base vide...
        print(f"   [coefficient_news] calcul impossible ({e.__class__.__name__}) -> coefficient neutre")
    finally:
        with _lock:
            _state["running"] = False


def _lancer_calcul():
    with _lock:
        if _state["running"] or time.time() - _state["last_start"] < REFRESH_COOLDOWN_S:
            return
        _state.update(running=True, last_start=time.time())
    threading.Thread(target=_calcul, daemon=True).start()


def _lire_rapport_du_jour():
    import json
    chemin = cn.chemin_rapport(datetime.now(cn.TUNIS).date())
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def bloc_news(rapport):
    """Version compacte et deterministe du rapport quotidien, destinee au rapport de prevision (et donc au hash)."""
    return {
        "date": rapport["date"],
        "version_methode": rapport["version_methode"],
        "coefficient_news": rapport["coefficient_news"],
        "coefficient_multiplicateur": rapport["coefficient_multiplicateur"],
        "max_adjustment": cn.MAX_AJUST,
        "tendance": rapport["tendance"],
        "statut": rapport["statut"],
        "couverture": rapport["couverture"],
        "rapport_sha256": rapport["empreinte_sha256"],
        "avertissement": rapport["methode"]["avertissement"],
        "questions": [{"id": d["id"], "categorie": d["categorie"], "statut": d["statut"], "poids": d["poids"],
                       "impact": d["impact"],
                       "sources": [{"url": s["url"], "date": s["date_article"]} for s in d["sources"]]}
                      for d in rapport["details"]],
    }


def current():
    """Retourne (multiplicateur, bloc_news | None, avertissement | None). Ne bloque jamais."""
    rapport = _lire_rapport_du_jour()
    if rapport and rapport.get("statut") in ("ok", "degrade"):
        warn = None
        if rapport["statut"] == "degrade":
            warn = "Coefficient news partiel : certaines questions ont echoue (voir news.questions)."
        if rapport.get("statut") != "ok":
            _lancer_calcul()                          # tente de completer un rapport degrade
        return float(rapport["coefficient_multiplicateur"]), bloc_news(rapport), warn
    _lancer_calcul()
    return 1.0, None, "Coefficient news indisponible aujourd'hui : coefficient neutre 1.0 applique."
