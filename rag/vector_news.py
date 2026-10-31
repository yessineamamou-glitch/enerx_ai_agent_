"""
EnerX RAG - Recherche vectorielle OPTIONNELLE sur les articles (ChromaDB + embeddings multilingues).

Active avec  ENERX_RAG_BACKEND=chroma  (et  pip install -r requirements-rag.txt ; python -m rag.etape2_vectorisation).
Sinon, ou si la base est absente / vide / en erreur, /ask reste sur BM25 (rag/retriever.py) : jamais d'erreur 500.
Les documents du projet (knowledge.md) restent toujours en BM25 ; seules les news passent par les vecteurs.
"""
import os
import threading

from rag.retriever import Passage

_lock = threading.Lock()
_state = {"tried": False, "collection": None, "embedder": None}


def enabled():
    return os.environ.get("ENERX_RAG_BACKEND", "").lower() == "chroma"


def _load():
    """Ouvre ChromaDB et charge le modele UNE seule fois ; (None, None) si indisponible."""
    with _lock:
        if not _state["tried"]:
            _state["tried"] = True
            try:
                from rag import etape2_vectorisation as e2
                col = e2.ouvrir_collection()
                if col.count() > 0:
                    _state.update(collection=col, embedder=e2.Embedder())
                else:
                    print("   [rag] base vectorielle vide -> BM25 (lancer : python -m rag.etape2_vectorisation)")
            except BaseException as e:               # SystemExit si sentence-transformers absent, ImportError, etc.
                print(f"   [rag] backend vectoriel indisponible ({e.__class__.__name__}) -> BM25")
        return _state["collection"], _state["embedder"]


def search(question, k=4):
    """Passages 'news' les plus proches (distance <= MAX_DISTANCE), ou None si le backend n'est pas utilisable."""
    if not enabled():
        return None
    col, emb = _load()
    if col is None:
        return None
    from rag import etape3_rag as e3
    try:
        morceaux = e3.rechercher(question, col, emb, k=k * 2)
    except Exception as e:
        print(f"   [rag] recherche vectorielle en erreur ({e.__class__.__name__}) -> BM25")
        return None
    return [Passage(id=f"vec-{i}", text=m["texte"], title=m["titre"], source=m["source"], url=m["url"] or None,
                    date=m["date"] or None, kind="news")
            for i, m in enumerate(morceaux) if m["distance"] <= e3.MAX_DISTANCE][:k]
