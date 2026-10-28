"""
EnerX - Collecte des VRAIS titres d'actualite -> news_headlines.json

Sources (gratuites, sans cle) :
  1. GDELT DOC 2.0 : moteur d'articles de presse mondial ; on filtre les articles tunisiens
     sur l'energie / le solaire / la STEG.
  2. Flux RSS des medias de la liste blanche (a renseigner dans RSS_FEEDS une fois l'URL verifiee
     dans ton navigateur : cherche l'icone RSS ou ajoute /feed au site).
Ne garde QUE les domaines de la liste blanche (news_agent.WHITELIST_DOMAINS) et une fenetre de
MAX_AGE_DAYS jours. Chaque titre garde son URL : c'est ce qui rend le coefficient news verifiable.

Utilisation :  python news_fetch.py      (puis l'API lit news_headlines.json)
Lancer toutes les heures suffit (tache planifiee ou boucle) ; l'API garde 15 min de cache.
"""
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

from news import news_agent, pertinence

OUT = news_agent.HEADLINES_FILE
MAX_AGE_DAYS = 14
MAX_ARTICLES = 40
HEADERS = {"User-Agent": "EnerX-hackathon/1.0 (veille presse)"}

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERIES = [        # une requete par sujet : eviter les requetes trop longues
    '(STEG OR "énergie solaire" OR photovoltaïque) sourcecountry:TS',
    '(Tunisie AND (solaire OR "énergies renouvelables" OR électricité)) sourcecountry:TS',
    '(Tunisia AND (solar OR "renewable energy" OR STEG)) sourcecountry:TS',
]

# Flux RSS : {nom du media: URL du flux}. A COMPLETER apres verification manuelle, exemple :
# "Managers.tn": "https://managers.tn/feed/"
RSS_FEEDS = {}

# Le sujet doit concerner l'energie : filtre simple sur le titre (evite le sport, la politique...)
MOTS_SUJET = ("solaire", "photovolta", "steg", "électricité", "electricite", "énergie", "energie",
              "renouvelable", "solar", "energy", "electricity", "kwh", "mégawatt", "megawatt", "ANME".lower())


def _sujet_ok(titre):
    t = titre.lower()
    return any(m in t for m in MOTS_SUJET)


def depuis_gdelt():
    out = []
    for q in GDELT_QUERIES:
        try:
            r = requests.get(GDELT_URL, headers=HEADERS, timeout=30, params={
                "query": q, "mode": "artlist", "format": "json", "maxrecords": 50,
                "timespan": f"{MAX_AGE_DAYS}d", "sort": "datedesc"})
            r.raise_for_status()
            arts = r.json().get("articles", [])
        except (requests.RequestException, ValueError) as e:
            print(f"  GDELT indisponible pour une requete ({e.__class__.__name__})")
            continue
        for a in arts:
            # seendate : "20261020T101500Z"
            try:
                pub = datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except (KeyError, ValueError):
                pub = None
            out.append({"title": (a.get("title") or "").strip(), "source_url": a.get("url"),
                        "source_name": a.get("domain"), "published": pub.isoformat() if pub else None})
    return out


def depuis_rss(nom, url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        racine = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError) as e:
        print(f"  RSS {nom} indisponible ({e.__class__.__name__})")
        return []
    out = []
    for it in racine.iter("item"):
        titre, lien, date = it.findtext("title"), it.findtext("link"), it.findtext("pubDate")
        try:
            pub = parsedate_to_datetime(date).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pub = None
        out.append({"title": (titre or "").strip(), "source_url": (lien or "").strip(),
                    "source_name": nom, "published": pub})
    return out


def filtrer(articles, maintenant=None):
    """Whitelist + sujet energie + fraicheur + dedoublonnage. Retourne (gardes, nb_rejetes)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = maintenant - timedelta(days=MAX_AGE_DAYS)
    vus, gardes, rejetes = set(), [], 0
    for a in articles:
        titre, url = a.get("title", ""), a.get("source_url")
        cle = (titre.lower(), urlparse(url or "").path)
        ok = bool(titre) and news_agent.domaine_autorise(url) and pertinence.est_pertinent(titre) and cle not in vus
        if ok:                       # date obligatoire, recente (MAX_AGE_DAYS) et de l'annee courante
            try:
                ok = (datetime.fromisoformat(a["published"]) >= limite
                      and pertinence.est_de_cette_annee(a["published"]))
            except (KeyError, TypeError, ValueError):
                ok = False
        if ok:
            vus.add(cle)
            gardes.append(a)
        else:
            rejetes += 1
    gardes.sort(key=lambda a: a.get("published") or "", reverse=True)
    return gardes[:MAX_ARTICLES], rejetes


def main():
    print("Collecte GDELT...")
    brut = depuis_gdelt()
    for nom, url in RSS_FEEDS.items():
        print(f"Collecte RSS {nom}...")
        brut += depuis_rss(nom, url)
    gardes, rejetes = filtrer(brut)
    print(f"{len(brut)} articles trouves, {len(gardes)} retenus, {rejetes} ecartes "
          "(domaine hors liste blanche, hors sujet, trop vieux ou doublon)")
    if not gardes:
        print("Aucun article retenu : news_headlines.json NON modifie (l'API garde l'ancien fichier ou le mode demo).")
        return
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(gardes, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)
    for a in gardes[:10]:
        print(f"  - {a['published'][:10] if a['published'] else '?'} | {a['source_name']} | {a['title'][:80]}")
    print(f"Ecrit : {OUT}")


if __name__ == "__main__":
    main()