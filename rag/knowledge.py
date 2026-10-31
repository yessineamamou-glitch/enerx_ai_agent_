"""
EnerX RAG - Corpus : base de connaissances du projet + articles STEG recents.

Les articles sont lus dans le meme fichier et avec le meme filtre de pertinence que GET /news
(news/news_feed.py), pour que le RAG ne cite jamais un article que le fil d'actualite refuserait.
L'index est reconstruit seulement quand un des fichiers source change (date de modification).
"""
import os
import re
import threading

from news import news_feed, pertinence
from rag.retriever import BM25Index, Passage

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_FILE = os.path.join(HERE, "data", "knowledge.md")

NEWS_PASSAGE_CHARS = 900          # un long article est coupe en passages de cette taille (aux fins de paragraphe)
MAX_NEWS_PASSAGES_PER_ARTICLE = 3

_lock = threading.Lock()
_cache = {"key": None, "index": None}


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def load_doc_passages(path=KNOWLEDGE_FILE):
    """Un passage par section '## Titre'. Le texte qui precede le premier '## ' (en-tete du fichier) est ignore."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return []
    out = []
    for i, block in enumerate(re.split(r"^## ", raw, flags=re.MULTILINE)[1:]):
        title, _, body = block.partition("\n")
        kw = " ".join(re.findall(r"^Keywords \(FR\):(.*)$", body, flags=re.MULTILINE))
        body = re.sub(r"^Keywords \(FR\):.*$", "", body, flags=re.MULTILINE).strip()
        if title.strip() and body:
            out.append(Passage(id=f"doc-{i}", title=title.strip(), text=body, keywords=kw,
                               source="EnerX docs", kind="doc"))
    return out


def _split(texte):
    """Coupe un texte en passages d'environ NEWS_PASSAGE_CHARS caracteres, sur les fins de paragraphe."""
    parts, cur = [], ""
    for para in [p.strip() for p in (texte or "").split("\n") if p.strip()]:
        if cur and len(cur) + len(para) > NEWS_PASSAGE_CHARS:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n{para}".strip()
    if cur:
        parts.append(cur)
    return parts[:MAX_NEWS_PASSAGES_PER_ARTICLE] or [""]


def load_news_passages(path=None):
    path = path or news_feed.ARTICLES_FILE
    out = []
    for i, r in enumerate(news_feed._lire(path)):
        titre, url = (r.get("titre") or "").strip(), r.get("url")
        if not titre or not url:
            continue
        if not pertinence.a_garder(titre, r.get("texte_brut", ""), r.get("date")):
            continue
        for j, chunk in enumerate(_split(r.get("texte_brut"))):
            out.append(Passage(id=f"news-{i}-{j}", title=titre, text=chunk, source=r.get("source") or "",
                               url=url, date=r.get("date"), kind="news"))
    return out


def get_index(with_news=True):
    """Index BM25 en cache ; reconstruit si knowledge.md ou articles_steg.json a change."""
    key = (_mtime(KNOWLEDGE_FILE), _mtime(news_feed.ARTICLES_FILE), with_news)
    with _lock:
        if _cache["key"] != key or _cache["index"] is None:
            _cache["index"] = BM25Index(load_doc_passages() + (load_news_passages() if with_news else []))
            _cache["key"] = key
        return _cache["index"]
