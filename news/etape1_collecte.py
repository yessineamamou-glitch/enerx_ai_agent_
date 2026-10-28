"""
ETAPE 1 - Collecte et nettoyage des articles sur la STEG  ->  articles_steg.json

Pour chaque source :
  1. on cherche un flux RSS (declare dans SOURCES, sinon decouvert automatiquement dans la page) ;
  2. s'il y en a un -> feedparser lit la liste des articles ;
  3. sinon -> on lit la page d'accueil/de rubrique et on suit les liens qui ressemblent a des articles ;
  4. le texte de chaque article est extrait par trafilatura (retire menus, pubs, pieds de page),
     avec BeautifulSoup en secours. Francais et arabe sont gardes tels quels (UTF-8).

Sortie : liste d'objets {"titre", "date", "url", "source", "texte_brut"}.
Le fichier est COMPLETE a chaque lancement (pas ecrase) : un article deja connu (meme URL) est ignore.

Usage :  python etape1_collecte.py                      (toutes les sources)
         python etape1_collecte.py --source tap --max 10
         python etape1_collecte.py --no-filtre           (garde aussi les articles hors sujet)
Respect des sites : robots.txt est lu et respecte, 1,5 s de pause entre deux requetes. User-Agent Chrome.
"""
import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup

from news import pertinence
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "articles_steg.json")
# User-Agent de navigateur Chrome (certains sites bloquent les User-Agent de scripts)
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0.0.0 Safari/537.36")
HEADERS_NAVIGATEUR = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8,en;q=0.5",
}
TIMEOUT_DEFAUT = 15        # secondes (surchargeable par source avec "timeout")
DELAI_SECONDES = 1.5
MIN_CHARS = 200            # en dessous : page vide, menu ou erreur -> ecartee
MAX_EXAMINES = 40          # pages ouvertes au maximum par source (pour les sites sans RSS : 100+ liens, trop lent)
BUDGET_SECONDES = 150      # temps max par source ; au-dela on passe a la suivante
MAX_PAR_SOURCE = 30        # nombre maximum d'articles pris par source et par lancement

# filtre : True = ne garder que les articles qui parlent d'energie/STEG (flux generalistes)
# rss    : (optionnel) URL(s) du flux si tu la connais ; sinon decouverte automatique
SOURCES = [
    # Vieux site PHP : timeout 10 s ; si le certificat est invalide, on retente SANS verification SSL (ssl_secours)
       {"nom": "STEG (site officiel)",   "url": "https://www.steg.com.tn/fr/news",                           "filtre": True,
     "timeout": 10, "ssl_secours": True, "rss": "DESACTIVE"},

    {"nom": "Managers.tn - Business", "url": "https://managers.tn/category/business/",        "filtre": True},
    #{"nom": "TAP",                    "url": "https://tap.info.tn",                       "filtre": True},
    {"nom": "Ministere de l'Energie", "url": "https://energiemines.gov.tn",                   "filtre": True},
    {"nom": "IlBoursa",               "url": "https://www.ilboursa.com",                      "filtre": True},
    {"nom": "Webmanagercenter",       "url": "https://www.webmanagercenter.com",              "filtre": True},
]

# Mots-cles de pertinence (francais + arabe)
MOTS_CLES = [
    "steg", "électricité", "electricite", "énergie", "energie", "solaire", "photovolta", "gaz naturel",
    "renouvelable", "centrale", "réseau électrique", "coupure", "délestage", "bess", "stockage", "mégawatt",
    "الشركة التونسية للكهرباء والغاز", "الستاغ", "كهرباء", "الكهرباء", "طاقة", "الطاقة", "شمسية", "الغاز",
    "انقطاع", "محطة", "ميغاواط",
]
RE_MOTS_CLES = re.compile("|".join(re.escape(m) for m in MOTS_CLES), re.IGNORECASE)

# Liens a ne pas suivre quand on cherche des articles dans une page de liste
EXT_IGNOREES = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".mp4")
CHEMINS_IGNORES = ("/category/", "/tag/", "/author/", "/page/", "/wp-content/", "/wp-json/", "/login",
                   "/contact", "/feed", "/search", "/?s=", "#")


# ----------------------------------------------------------------------------
# Reseau poli : robots.txt + pause + en-tetes de navigateur + options par site
# ----------------------------------------------------------------------------
_robots = {}
_dernier_appel = [0.0]
_options_hote = {}         # {"steg.com.tn": {"timeout": 10, "ssl_secours": True}} rempli par collecter_source


def _hote(url):
    return urlparse(url).netloc.replace("www.", "")


def _get(url, timeout=None):
    """GET avec en-tetes de navigateur. Si le site a `ssl_secours` et que son certificat est invalide,
    on retente SANS verification SSL (verify=False) : acceptable pour lire des pages publiques,
    mais le contenu pourrait alors etre altere par un intermediaire (voir l'avertissement affiche)."""
    opt = _options_hote.get(_hote(url), {})
    timeout = timeout or opt.get("timeout", TIMEOUT_DEFAUT)
    try:
        return requests.get(url, headers=HEADERS_NAVIGATEUR, timeout=timeout)
    except requests.exceptions.SSLError:
        if not opt.get("ssl_secours"):                  # seuls les sites marques ssl_secours (STEG) ont ce secours
            raise
        print(f"    certificat SSL invalide pour {_hote(url)} : nouvelle tentative sans verification SSL")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return requests.get(url, headers=HEADERS_NAVIGATEUR, timeout=timeout, verify=False)


def autorise_par_robots(url):
    hote = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if hote not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = _get(hote + "/robots.txt", timeout=10)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])   # pas de robots.txt = tout permis
        except requests.RequestException:
            rp.parse([])
        _robots[hote] = rp
    return _robots[hote].can_fetch(USER_AGENT, url)


def http_get(url):
    """Retourne la reponse HTTP, ou None si interdit / en erreur. Ne leve jamais d'exception reseau."""
    if not autorise_par_robots(url):
        print(f"    robots.txt interdit : {url}")
        return None
    attente = DELAI_SECONDES - (time.time() - _dernier_appel[0])
    if attente > 0:
        time.sleep(attente)
    _dernier_appel[0] = time.time()
    try:
        r = _get(url)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        print(f"    echec {url} ({e.__class__.__name__})")
        return None


def texte_html(reponse):
    """Decode correctement le francais ET l'arabe (requests suppose ISO-8859-1 si le serveur ne precise rien)."""
    if "charset" not in reponse.headers.get("content-type", "").lower():
        reponse.encoding = reponse.apparent_encoding or "utf-8"
    return reponse.text


# ----------------------------------------------------------------------------
# Decouverte des articles : RSS, sinon page de liste
# ----------------------------------------------------------------------------
def decouvrir_flux(url, html=None):
    """Cherche <link rel="alternate" type="application/rss+xml"> dans la page, puis les chemins usuels."""
    flux = []
    if html is None:
        r = http_get(url)
        html = texte_html(r) if r else ""
    for lien in BeautifulSoup(html, "lxml").find_all("link", href=True):
        type_ = (lien.get("type") or "").lower()
        if "alternate" in (lien.get("rel") or []) and ("rss" in type_ or "atom" in type_):
            flux.append(urljoin(url, lien["href"]))
    if not flux:                                   # convention WordPress : /feed/ (et /category/xxx/feed/)
        base = url.rstrip("/")
        for c in (base + "/feed/", base + "/rss", base + "/rss.xml"):
            r = http_get(c)
            if r is not None and feedparser.parse(r.content).entries:
                flux.append(c)
                break
    return list(dict.fromkeys(flux))               # sans doublons, ordre conserve


def articles_depuis_flux(url_flux):
    """Retourne [{url, titre, date, resume}] depuis un flux RSS/Atom (lu par feedparser)."""
    r = http_get(url_flux)
    if r is None:
        return []
    out = []
    for e in feedparser.parse(r.content).entries:
        date = None
        if getattr(e, "published_parsed", None):
            date = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).date().isoformat()
        resume = BeautifulSoup(getattr(e, "summary", "") or "", "lxml").get_text(" ", strip=True)
        if getattr(e, "link", None):
            out.append({"url": e.link, "titre": (getattr(e, "title", "") or "").strip(), "date": date,
                        "resume": resume})
    return out


def liens_articles_depuis_page(url_page, html):
    """Pour un site sans RSS : liens internes qui ressemblent a des articles (slug long ou chiffres)."""
    hote = urlparse(url_page).netloc.replace("www.", "")
    vus, out = set(), []
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        lien = urljoin(url_page, a["href"]).split("#")[0]
        p = urlparse(lien)
        if p.netloc.replace("www.", "") != hote or lien.rstrip("/") == url_page.rstrip("/"):
            continue
        if p.path.lower().endswith(EXT_IGNOREES) or any(c in lien.lower() for c in CHEMINS_IGNORES):
            continue
        dernier = p.path.rstrip("/").split("/")[-1]
        if len(dernier) < 15 and not re.search(r"\d{3,}", p.path):    # "contact", "accueil"... ce ne sont pas des articles
            continue
        if lien not in vus:
            vus.add(lien)
            out.append({"url": lien, "titre": a.get_text(" ", strip=True), "date": None, "resume": ""})
    return out


# ----------------------------------------------------------------------------
# Extraction du texte propre d'un article
# ----------------------------------------------------------------------------
def _champ(doc, nom):
    return doc.get(nom) if isinstance(doc, dict) else getattr(doc, nom, None)


def extraire_texte(html, url):
    """Retourne (titre, date, texte). trafilatura en priorite (format d'article standard, ex. managers.tn) ;
    si le texte est vide ou trop court, secours BeautifulSoup. Texte vide si la page est vide."""
    if not html or not html.strip():
        return "", None, ""                                   # page vide : rien a extraire
    try:
        doc = trafilatura.bare_extraction(html, url=url, with_metadata=True, include_comments=False,
                                          include_tables=False, favor_precision=True)
    except Exception:                                         # une page illisible ne doit pas arreter la collecte
        doc = None
    texte = (_champ(doc, "text") or "").strip() if doc else ""
    titre = (_champ(doc, "title") or "").strip() if doc else ""
    date = _champ(doc, "date") if doc else None
    if len(texte) < MIN_CHARS:                                # secours : paragraphes <p> du corps de la page
        soupe = BeautifulSoup(html, "lxml")
        for t in soupe(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
            t.decompose()
        paragraphes = [p.get_text(" ", strip=True) for p in soupe.find_all("p")]
        texte = "\n".join(p for p in paragraphes if len(p) > 40)
        titre = titre or (soupe.title.get_text(strip=True) if soupe.title else "")
    return titre, (str(date)[:10] if date else None), re.sub(r"\n{3,}", "\n\n", texte).strip()


def est_pertinent(titre, texte):
    """Filtre a score (voir pertinence.py) : garde seulement ce qui peut influencer le prix d'un token solaire."""
    return pertinence.est_pertinent(titre, texte)


# ----------------------------------------------------------------------------
# Collecte d'une source
# ----------------------------------------------------------------------------
def collecter_source(src, deja_vus, max_articles=MAX_PAR_SOURCE, filtrer=True):
    print(f"\n== {src['nom']}  ({src['url']})")
    _options_hote[_hote(src["url"])] = {"timeout": src.get("timeout", TIMEOUT_DEFAUT),
                                        "ssl_secours": src.get("ssl_secours", False)}
    
    # Gestion du débrayage manuel du RSS
    if src.get("rss") == "DESACTIVE":
        flux = []
        r = http_get(src["url"])
    else:
        r = http_get(src["url"])
        if r is None and not src.get("rss"):                # site injoignable : inutile de deviner des flux (30 s chacun)
            print("   source injoignable, on passe")
            return []
        page = texte_html(r) if r else ""
        flux = src.get("rss") or decouvrir_flux(src["url"], page)
        
    if isinstance(flux, str):
        flux = [flux]

    page = texte_html(r) if r else ""
    candidats = []
    for f in flux:
        candidats += articles_depuis_flux(f)
    if candidats:
        print(f"   RSS : {len(candidats)} articles ({', '.join(flux)})")
    elif page:
        candidats = liens_articles_depuis_page(src["url"], page)
        print(f"   pas de RSS : {len(candidats)} liens candidats dans la page")

    resultats, examines, debut = [], 0, time.time()
    for c in candidats:
        if len(resultats) >= max_articles or examines >= MAX_EXAMINES or time.time() - debut > BUDGET_SECONDES:
            break
        if c["url"] in deja_vus:
            continue
        if c["date"] and not pertinence.est_de_cette_annee(c["date"]):
            continue                                 # date connue par le flux et pas de cette annee : inutile de telecharger
        examines += 1
        rep = http_get(c["url"])
        if rep is None:
            continue
        titre, date, texte = extraire_texte(texte_html(rep), c["url"])
        if len(texte) < MIN_CHARS and len(c.get("resume", "")) >= MIN_CHARS:
            texte = c["resume"]                      # le flux contenait deja le texte
        if len(texte) < MIN_CHARS:
            continue
        titre = titre or c["titre"]
        
        # --- EXTRACTION ET CONVERSION DYNAMIQUE DE LA DATE ---
        date_article = c["date"] or date
        
        if not date_article:
            # On cherche un motif JJ/MM/AAAA dans le titre ou les 300 premiers caractères du texte
            match = re.search(r"(\d{2})/(\d{2})/(\d{4})", titre + " " + texte[:300])
            if match:
                jj, mm, aaaa = match.groups()
                date_article = f"{aaaa}-{mm}-{jj}"   # Reconstruction au format standard AAAA-MM-JJ
        # -----------------------------------------------------

        if not date_article or not pertinence.est_de_cette_annee(date_article):
            continue                                 # vieux article, ou sans date : on n'affiche que les news de l'annee
        if filtrer and src.get("filtre") and not est_pertinent(titre, texte):
            continue
        resultats.append({"titre": titre, "date": date_article, "url": c["url"],
                          "source": src["nom"], "texte_brut": texte})
        deja_vus.add(c["url"])
    print(f"   -> {len(resultats)} articles retenus")
    return resultats


# ----------------------------------------------------------------------------
# Sauvegarde (on complete le fichier, on ne l'ecrase pas)
# ----------------------------------------------------------------------------
def charger_existant(chemin):
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    return []


def sauvegarder(articles, chemin):
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)      # ensure_ascii=False : l'arabe reste lisible
    os.replace(tmp, chemin)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT_FILE)
    ap.add_argument("--source", help="ne collecter que les sources dont le nom contient ce texte")
    ap.add_argument("--max", type=int, default=MAX_PAR_SOURCE, help="articles max par source")
    ap.add_argument("--no-filtre", action="store_true", help="ne pas filtrer par mots-cles")
    args = ap.parse_args()

    # on repart d'un fichier propre : les anciens articles (autres annees) et les hors-sujet sont retires
    existants = [a for a in charger_existant(args.out)
                 if pertinence.a_garder(a.get("titre", ""), a.get("texte_brut", ""), a.get("date"))]
    deja_vus = {a["url"] for a in existants}
    nouveaux = []
    for src in SOURCES:
        if args.source and args.source.lower() not in src["nom"].lower():
            continue
        try:
            nouveaux += collecter_source(src, deja_vus, args.max, filtrer=not args.no_filtre)
        except KeyboardInterrupt:                    # Ctrl+C : on garde ce qui a deja ete collecte
            print("\nInterrompu : sauvegarde de ce qui a ete collecte.")
            break

    sauvegarder(existants + nouveaux, args.out)
    print(f"\nTermine : {len(nouveaux)} nouveaux articles, {len(existants) + len(nouveaux)} au total dans {args.out}")


if __name__ == "__main__":
    main()