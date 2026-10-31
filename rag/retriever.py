"""
EnerX RAG - Recherche BM25 en pur Python.

Choix : pas de base vectorielle ni de modele d'embeddings (le corpus fait quelques dizaines de passages,
et chromadb / sentence-transformers alourdissaient le deploiement : voir docs/CHANGEMENTS_NEWS.md).
BM25 suffit a cette echelle et se teste sans internet.
"""
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

K1 = 1.5
B = 0.75

# mots vides FR + EN (courts : on ne veut garder que les mots porteurs de sens)
STOPWORDS = set("""
a au aux avec ce ces cet cette dans de des du elle en est et il ils je la le les leur lui ma mais me meme mes
moi mon ne nos notre nous on ou par pas pour qu que quel quelle quels quelles qui sa se ses son sur ta te tes toi
ton tu un une vos votre vous y ont sont etre avoir fait comment pourquoi quand combien est-ce c d j l m n s t
the a an and are as at be by can do does for from how i in is it its me of on or that the their this to was what
when where which who why will with you your my
""".split())

_TOKEN = re.compile(r"\w+", re.UNICODE)


def fold(text):
    """Minuscules + accents retires (l'arabe n'est pas touche : ses lettres ne sont pas des marques)."""
    t = unicodedata.normalize("NFD", (text or "").lower().replace("’", "'"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _stem(w):
    # racinisation tres legere (pluriels) : suffisante pour "tokens"/"token", "tarifs"/"tarif"
    if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    if len(w) > 4 and w.endswith("x"):
        return w[:-1]
    return w


def tokenize(text, keep_stopwords=False):
    out = []
    for w in _TOKEN.findall(fold(text)):
        if not keep_stopwords and (w in STOPWORDS or len(w) < 2):
            continue
        out.append(_stem(w))
    return out


@dataclass
class Passage:
    id: str
    text: str
    title: str = ""
    source: str = ""
    url: str | None = None
    date: str | None = None
    kind: str = "doc"                       # doc | news
    keywords: str = ""                      # mots-cles indexes mais jamais affiches (aide les questions en francais)
    tokens: list = field(default_factory=list, repr=False)


@dataclass
class Hit:
    passage: Passage
    score: float
    matched: int                            # nombre de termes DISTINCTS de la question retrouves dans le passage


class BM25Index:
    def __init__(self, passages):
        self.passages = list(passages)
        for p in self.passages:
            p.tokens = tokenize(f"{p.title} {p.title} {p.text} {p.keywords}")     # le titre compte double
        n = len(self.passages)
        self.avgdl = (sum(len(p.tokens) for p in self.passages) / n) if n else 0.0
        df = Counter()
        for p in self.passages:
            df.update(set(p.tokens))
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self._tf = [Counter(p.tokens) for p in self.passages]

    def search(self, question, k=4):
        q_terms = list(dict.fromkeys(tokenize(question)))          # distincts, ordre conserve
        if not q_terms or not self.passages:
            return [], q_terms
        hits = []
        for p, tf in zip(self.passages, self._tf):
            dl = len(p.tokens) or 1
            score, matched = 0.0, 0
            for t in q_terms:
                f = tf.get(t, 0)
                if not f:
                    continue
                matched += 1
                score += self.idf.get(t, 0.0) * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / (self.avgdl or 1)))
            if matched:
                hits.append(Hit(p, score, matched))
        hits.sort(key=lambda h: (h.score, h.matched), reverse=True)
        return hits[:k], q_terms


def is_relevant(hits, q_terms):
    """Garde-fou 'hors sujet' : le meilleur passage doit retrouver une part suffisante des termes de la question.
    Une question dont aucun terme n'apparait dans le corpus (ou un seul terme sur beaucoup) n'obtient pas de reponse."""
    if not hits or not q_terms:
        return False
    need = 1 if len(q_terms) <= 2 else math.ceil(0.4 * len(q_terms))
    return hits[0].matched >= need
