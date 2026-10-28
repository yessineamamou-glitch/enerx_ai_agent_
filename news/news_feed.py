"""
EnerX - Fil d'actualite (ETAPE 1 seulement : on cherche les news, on les AFFICHE).

Il n'y a plus de RAG, plus de note d'impact, plus de coefficient : les news n'entrent PAS dans
le calcul du dividende. L'utilisateur lit les titres et decide lui-meme.

Fonctionnement :
  - etape1_collecte.py (scraping RSS/pages) ecrit articles_steg.json ;
  - ce module lit ce fichier, enleve le texte complet et renvoie titre / source / date / lien / extrait ;
  - si le fichier est absent ou vide, repli sur news_headlines.json (news_fetch.py, GDELT) ;
  - la collecte est relancee en arriere-plan (sous-processus) au maximum toutes les REFRESH_SECONDS,
    sans jamais bloquer une requete de l'API.
"""
import json
import os
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse

from news import pertinence

HERE = os.path.dirname(os.path.abspath(__file__))              # dossier news/
ROOT = os.path.dirname(HERE)                                   # racine du projet (cwd des sous-processus)
DATA_DIR = os.path.join(HERE, "data")
ARTICLES_FILE = os.path.join(DATA_DIR, "articles_steg.json")      # sortie de etape1_collecte.py
HEADLINES_FILE = os.path.join(DATA_DIR, "news_headlines.json")    # sortie de news_fetch.py (secours)

REFRESH_SECONDS = int(os.environ.get("ENERX_NEWS_REFRESH_SECONDS", "3600"))
MAX_ITEMS = 8
SNIPPET_CHARS = 220

_lock = threading.Lock()
_state = {"last_start": 0.0, "running": False}


def _lire(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _extrait(texte):
    t = " ".join((texte or "").split())
    return t if len(t) <= SNIPPET_CHARS else t[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


def _depuis_etape1(rows):
    # filtre de securite a la lecture : jamais d'article hors sujet ni d'une autre annee, meme si le fichier en contient
    return [{"title": (r.get("titre") or "").strip(), "source": r.get("source") or "",
             "url": r.get("url"), "date": r.get("date"), "summary": _extrait(r.get("texte_brut"))}
            for r in rows if r.get("titre") and r.get("url")
            and pertinence.a_garder(r["titre"], r.get("texte_brut", ""), r.get("date"))]


def _depuis_gdelt(rows):
    return [{"title": (r.get("title") or "").strip(), "source": r.get("source_name") or "",
             "url": r.get("source_url"), "date": (r.get("published") or "")[:10] or None, "summary": ""}
            for r in rows if r.get("title") and r.get("source_url")
            and pertinence.a_garder(r["title"], "", (r.get("published") or "")[:10])]


def load_items():
    """Retourne (items, origine). Tri : plus recents d'abord, sans doublon d'URL ni de titre."""
    items, origin = _depuis_etape1(_lire(ARTICLES_FILE)), "etape1"
    if not items:
        items, origin = _depuis_gdelt(_lire(HEADLINES_FILE)), "gdelt"
    vus_titres, vus_urls, out = set(), set(), []
    for it in sorted(items, key=lambda x: x["date"] or "", reverse=True):
        titre = " ".join(it["title"].lower().split())
        # une URL de page d'accueil (ex. https://steg.com.tn) est partagee par plusieurs avis :
        # on ne deduplique par URL que pour de vraies pages d'article
        generique = urlparse(it["url"]).path in ("", "/")
        if titre in vus_titres or (not generique and it["url"] in vus_urls):
            continue
        vus_titres.add(titre)
        vus_urls.add(it["url"])
        out.append(it)
    return out[:MAX_ITEMS], (origin if out else "vide")


def _collecte_en_arriere_plan():
    try:
        # etape1 d'abord ; si rien n'est ressorti, le secours GDELT (leger) prend le relais
        subprocess.run([sys.executable, "-m", "news.etape1_collecte", "--max", "6"],
                       cwd=ROOT, timeout=600, check=False, capture_output=True)
        if not _depuis_etape1(_lire(ARTICLES_FILE)):
            subprocess.run([sys.executable, "-m", "news.news_fetch"],
                           cwd=ROOT, timeout=180, check=False, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        with _lock:
            _state["running"] = False


def maybe_refresh():
    """Lance la collecte en arriere-plan si les donnees sont trop vieilles. Ne bloque jamais."""
    with _lock:
        if _state["running"] or time.time() - _state["last_start"] < REFRESH_SECONDS:
            return False
        _state.update(running=True, last_start=time.time())
    threading.Thread(target=_collecte_en_arriere_plan, daemon=True).start()
    return True


def get_news():
    maybe_refresh()
    items, origin = load_items()
    return {
        "items": items,
        "origin": origin,                      # etape1 | gdelt | vide
        "refreshing": _state["running"],
        "informational_only": True,            # ces news ne modifient AUCUN chiffre de prevision
    }
