"""Tests hors ligne du pipeline RAG :  python -m pytest -q test_rag.py"""
import json

import hashlib
import math
import re

import pytest

import etape1_collecte as e1
import etape2_vectorisation as e2
import etape3_rag as e3

FR = ("La STEG a annoncé le lancement d'un projet de stockage par batteries BESS de 100 MW à Tozeur. "
      "Le projet vise à stabiliser le réseau électrique du sud. Les travaux débuteront en 2027. ") * 6
AR = ("أعلنت الشركة التونسية للكهرباء والغاز عن انقطاع الكهرباء في ولاية صفاقس بسبب عطب في المحطة. "
      "تم إصلاح العطب في المساء؟ عادت الكهرباء إلى جميع الأحياء. ") * 6
ARTICLES = [
    {"titre": "BESS Tozeur", "date": "2026-10-01", "url": "https://tap.info.tn/bess", "source": "TAP", "texte_brut": FR},
    {"titre": "Panne Sfax", "date": "2026-10-02", "url": "https://managers.tn/panne", "source": "Managers", "texte_brut": AR},
]


# ---------- etape 1 ----------
def test_decouverte_flux_dans_la_page():
    html = '<html><head><link rel="alternate" type="application/rss+xml" href="/flux.xml"></head></html>'
    assert e1.decouvrir_flux("https://site.tn/", html) == ["https://site.tn/flux.xml"]


def test_liens_articles_filtres():
    html = """<a href="/contact">c</a><a href="/2026/10/la-steg-lance-un-grand-projet-solaire">a</a>
              <a href="/category/eco/">cat</a><a href="https://autre.com/x-y-z-long-slug-article">ext</a>
              <a href="/doc/rapport.pdf">pdf</a>"""
    liens = [x["url"] for x in e1.liens_articles_depuis_page("https://site.tn/", html)]
    assert liens == ["https://site.tn/2026/10/la-steg-lance-un-grand-projet-solaire"]


def test_extraction_retire_menus_et_garde_l_arabe():
    html = f"""<html><head><title>T</title></head><body><nav>MENU ACCUEIL CONTACT</nav>
    <article><h1>انقطاع الكهرباء</h1><p>{AR}</p></article><footer>PIED DE PAGE</footer></body></html>"""
    _, _, texte = e1.extraire_texte(html, "https://x.tn/a")
    assert "الكهرباء" in texte and "MENU ACCUEIL" not in texte and "PIED DE PAGE" not in texte


def test_pertinence_fr_et_ar():
    assert e1.est_pertinent("Coupure d'électricité", "") and e1.est_pertinent("", "الشركة التونسية للكهرباء والغاز")
    assert not e1.est_pertinent("Football : résultats", "Le match s'est terminé 2-1.")


def test_collecte_source_avec_rss(monkeypatch):
    rss = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
      <item><title>Projet BESS</title><link>https://tap.info.tn/a1</link><pubDate>Wed, 21 Oct 2026 10:00:00 GMT</pubDate></item>
      <item><title>Foot</title><link>https://tap.info.tn/a2</link></item></channel></rss>"""
    page = {"https://tap.info.tn/a1": f"<html><body><article><p>{FR}</p></article></body></html>",
            "https://tap.info.tn/a2": "<html><body><article><p>" + "Le match de football s'est termine par un nul. " * 10 + "</p></article></body></html>"}

    class R:
        def __init__(self, content): self.content, self.headers, self.encoding = content, {"content-type": "text/html; charset=utf-8"}, "utf-8"
        text = property(lambda s: s.content.decode("utf-8"))

    def faux_get(url):
        if url == "https://tap.info.tn/feed.xml": return R(rss)
        if url in page: return R(page[url].encode())
        return R(b"<html></html>")
    monkeypatch.setattr(e1, "http_get", faux_get)
    res = e1.collecter_source({"nom": "TAP", "url": "https://tap.info.tn", "filtre": True,
                               "rss": "https://tap.info.tn/feed.xml"}, set())
    assert [a["url"] for a in res] == ["https://tap.info.tn/a1"]       # le football est ecarte
    assert set(res[0]) == {"titre", "date", "url", "source", "texte_brut"} and res[0]["date"] == "2026-10-21"


# ---------- etape 2 ----------
def test_chunking_taille_chevauchement_et_phrases():
    morceaux = e2.decouper(FR, 300, 80)
    assert len(morceaux) > 1 and all(len(m) <= 300 for m in morceaux)
    assert all(m.rstrip().endswith((".", "?", "!")) for m in morceaux)           # on ne coupe pas les phrases
    assert any(morceaux[i][-30:] in morceaux[i + 1] for i in range(len(morceaux) - 1))   # chevauchement reel


def test_chunking_phrase_geante_et_arabe():
    assert all(len(m) <= 200 for m in e2.decouper("mot " * 500, 200, 40))
    assert len(e2.decouper(AR, 200, 40)) > 1
    assert e2.decouper("", 200, 40) == []


def test_langue():
    assert e2.detecter_langue(AR) == "ar" and e2.detecter_langue(FR) == "fr"


class FauxEmbedder:
    """Embedder de TEST (sac de mots hache) : meme interface que e2.Embedder, sans telechargement."""
    def _v(self, texte, dim=384):
        v = [0.0] * dim
        for mot in re.findall(r"\w+", texte.lower()):
            v[int(hashlib.md5(mot.encode()).hexdigest(), 16) % dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]
    def documents(self, textes): return [self._v(t) for t in textes]
    def question(self, texte): return self._v(texte)


@pytest.fixture()
def base(tmp_path):
    col = e2.ouvrir_collection(chemin=str(tmp_path / "db"))
    emb = FauxEmbedder()
    return col, emb


def test_indexation_incrementale(base):
    col, emb = base
    n_art, n_chunks, ign = e2.indexer(ARTICLES, col, emb)
    assert n_art == 2 and col.count() == n_chunks and ign == 0
    assert e2.indexer(ARTICLES, col, emb) == (0, 0, 2)                 # relance : rien n'est duplique
    modif = [{**ARTICLES[0], "texte_brut": FR + " Nouvelle information importante sur le calendrier."}]
    assert e2.indexer(modif, col, emb)[0] == 1                          # article modifie : re-indexe
    meta = col.get(where={"url": ARTICLES[0]["url"]})["metadatas"][0]
    assert meta["source"] == "TAP" and meta["date"] == "2026-10-01" and meta["langue"] == "fr"


# ---------- etape 3 ----------
def test_recherche_retrouve_le_bon_article(base):
    col, emb = base
    e2.indexer(ARTICLES, col, emb)
    top = e3.rechercher("projet de stockage par batteries BESS Tozeur", col, emb, k=3)
    assert top[0]["url"] == "https://tap.info.tn/bess"


def test_prompt_strict_et_extraits_numerotes():
    morceaux = [{"texte": "texte A", "source": "TAP", "url": "u1", "date": "2026-10-01", "titre": "T1", "distance": 0.1}]
    sysm, user = e3.construire_prompt("Question ?", morceaux)
    assert "EXCLUSIVEMENT" in sysm and "N'invente rien" in sysm and "全球" not in sysm
    assert "[1] TAP | 2026-10-01 | T1 | u1" in user and "QUESTION : Question ?" in user


def test_aiguillage_llm_et_sources(base, monkeypatch):
    col, emb = base
    e2.indexer(ARTICLES, col, emb)
    vu = {}
    monkeypatch.setitem(e3.LLMS, "ollama", lambda s, u: vu.update(s=s, u=u) or "Réponse [1]")
    res = e3.poser_question("batteries BESS Tozeur", llm="ollama", collection=col, embedder=emb)
    assert res["reponse"] == "Réponse [1]" and "BESS" in vu["u"] and res["sources"]


def test_sans_extrait_le_llm_nest_pas_appele(base, monkeypatch):
    col, emb = base                                                      # base VIDE
    monkeypatch.setitem(e3.LLMS, "gemini", lambda s, u: pytest.fail("LLM appele sans extrait"))
    assert e3.poser_question("n'importe quoi", llm="gemini", collection=col, embedder=emb)["reponse"] == e3.REPONSE_INCONNUE


def test_seuil_de_distance(base, monkeypatch):
    col, emb = base
    e2.indexer(ARTICLES, col, emb)
    monkeypatch.setattr(e3, "MAX_DISTANCE", 0.0001)
    monkeypatch.setitem(e3.LLMS, "gemini", lambda s, u: pytest.fail("LLM appele hors seuil"))
    assert e3.poser_question("zzz qqq", llm="gemini", collection=col, embedder=emb)["reponse"] == e3.REPONSE_INCONNUE


def test_appels_http_gemini_et_ollama(monkeypatch):
    envoyes = []
    class R:
        def __init__(self, j): self.j = j
        def raise_for_status(self): pass
        def json(self): return self.j
    def faux_post(url, **kw):
        envoyes.append((url, kw))
        return R({"candidates": [{"content": {"parts": [{"text": "ok gemini"}]}}]} if "google" in url
                 else {"message": {"content": "ok ollama"}})
    monkeypatch.setattr(e3.requests, "post", faux_post)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert e3.appeler_gemini("S", "U") == "ok gemini" and e3.appeler_ollama("S", "U") == "ok ollama"
    assert envoyes[0][1]["json"]["generationConfig"]["temperature"] == 0.0
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(RuntimeError):
        e3.appeler_gemini("S", "U")


# ---------- reseau : en-tetes, SSL, timeout ----------
def test_user_agent_chrome_et_timeout_steg(monkeypatch):
    vus = []
    class R:
        status_code, text = 200, ""
        def raise_for_status(self): pass
    monkeypatch.setattr(e1.requests, "get", lambda url, **kw: vus.append(kw) or R())
    e1._options_hote["steg.com.tn"] = {"timeout": 10, "ssl_secours": True}
    e1._get("https://steg.com.tn/")
    assert "Chrome/" in vus[0]["headers"]["User-Agent"] and vus[0]["timeout"] == 10 and "verify" not in vus[0]


def test_ssl_secours_seulement_pour_steg(monkeypatch):
    appels = []
    class R:
        status_code, text = 200, ""
    def get(url, **kw):
        appels.append(kw.get("verify", True))
        if kw.get("verify", True):
            raise e1.requests.exceptions.SSLError("certificat")
        return R()
    monkeypatch.setattr(e1.requests, "get", get)
    e1._options_hote["steg.com.tn"] = {"timeout": 10, "ssl_secours": True}
    e1._get("https://steg.com.tn/")
    assert appels == [True, False]                     # d'abord verifie, puis secours sans verification
    with pytest.raises(e1.requests.exceptions.SSLError):   # un autre site n'a PAS ce secours
        e1._get("https://tap.info.tn/")


def test_page_vide_ne_plante_pas():
    assert e1.extraire_texte("", "https://x.tn") == ("", None, "")
    assert e1.extraire_texte("<html><body></body></html>", "https://x.tn")[2] == ""