"""
EnerX RAG - Orchestration : question -> passages -> reponse citee.

Trois issues, toujours avec `informational_only: true` :
  - mode "llm"        : un LLM redige la reponse a partir des seuls passages recuperes (citations [n] verifiees) ;
  - mode "extractive" : sans cle API (ou si le LLM echoue) : on renvoie les phrases les plus proches de la question ;
  - mode "no_match"   : rien de pertinent dans le corpus -> on le dit, on n'invente pas.
Le RAG ne touche jamais au calcul du dividende.
"""
import re

from rag import knowledge, llm, vector_news
from rag.retriever import is_relevant, tokenize

MAX_QUESTION_CHARS = 300
TOP_K = 4
SNIPPET_CHARS = 240
EXTRACT_SENTENCES = 3

NO_MATCH_TEXT = ("I could not find this in the EnerX knowledge base or the latest STEG news. "
                 "Je n'ai pas trouvé cette information dans la base EnerX ni dans les dernières actualités STEG.")
NOTE = "Informational only: this answer does not change any forecast or dividend. Numbers come from the /forecast report."


def _snippet(text):
    t = " ".join((text or "").split())
    return t if len(t) <= SNIPPET_CHARS else t[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


MIN_SCORE_RATIO = 0.4          # un passage doit atteindre 40 % du score du meilleur pour etre cite


def _unique_sources(hits):
    """Un seul passage par article / section (le meilleur), dans l'ordre de score, sans passages peu pertinents."""
    seen, out = set(), []
    top = hits[0].score if hits else 0.0
    for h in hits:
        if h.score < MIN_SCORE_RATIO * top:
            continue
        key = (h.passage.kind, h.passage.url or h.passage.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(h.passage)
    return out


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+|\n+", text) if len(s.strip()) > 25]


def _extractive(q_terms, passages):
    """Les phrases qui contiennent le plus de termes de la question, avec la citation de leur passage."""
    wanted = set(q_terms)
    scored = []
    for n, p in enumerate(passages, 1):
        for s in _sentences(p.text):
            overlap = len(wanted & set(tokenize(s)))
            if overlap:
                scored.append((overlap, -n, s, n))
    if not scored:                                    # aucune phrase ne recoupe : debut du meilleur passage
        return f"{_snippet(passages[0].text)} [1]"
    scored.sort(reverse=True)
    best = scored[:EXTRACT_SENTENCES]
    best.sort(key=lambda x: (x[3], x[2]))             # ordre des sources, pour une lecture naturelle
    return " ".join(f"{s} [{n}]" for _, _, s, n in best)


def _clean_citations(text, n_sources):
    """Retire les citations [k] qui ne correspondent a aucune source fournie (le LLM ne doit pas en inventer)."""
    return re.sub(r"\[(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", text)


def ask(question):
    q = " ".join((question or "").split())[:MAX_QUESTION_CHARS]
    base = {"question": q, "informational_only": True, "note": NOTE}
    if not q:
        return {**base, "answer": NO_MATCH_TEXT, "mode": "no_match", "sources": []}

    vec_news = vector_news.search(q, k=TOP_K)          # None : backend vectoriel desactive ou indisponible -> BM25
    hits, q_terms = knowledge.get_index(with_news=vec_news is None).search(q, k=TOP_K * 2)
    docs_ok = is_relevant(hits, q_terms)
    if not docs_ok and not vec_news:
        return {**base, "answer": NO_MATCH_TEXT, "mode": "no_match", "sources": []}

    passages = (_unique_sources(hits) if docs_ok else [])
    if vec_news:                                       # docs d'abord, puis les articles les plus proches
        seen = {p.url for p in passages if p.url}
        passages += [p for p in vec_news if p.url not in seen]
    passages = passages[:TOP_K]
    sources = [{"id": i, "title": p.title, "source": p.source, "url": p.url, "date": p.date, "kind": p.kind,
                "snippet": _snippet(p.text)} for i, p in enumerate(passages, 1)]

    mode, answer = "extractive", None
    if llm.provider():
        try:
            generated = _clean_citations(llm.generate(q, passages), len(passages))
            if generated:
                mode, answer = "llm", generated
        except Exception as e:                        # reseau, quota, reponse inattendue -> repli, jamais une erreur 500
            print(f"   [rag] LLM indisponible ({e.__class__.__name__}) -> reponse extractive")
    if answer is None:
        answer = _extractive(q_terms, passages)
    return {**base, "answer": answer, "mode": mode, "sources": sources}
