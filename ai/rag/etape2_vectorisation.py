"""
ETAPE 2 - Base vectorielle : articles_steg.json  ->  ChromaDB (dossier ./chroma_steg)

1. Decoupage de chaque article en morceaux (chunks) qui se chevauchent, sans couper les phrases.
2. Embeddings multilingues (francais et arabe dans le meme espace vectoriel).
3. Stockage dans ChromaDB avec metadonnees (source, url, date, titre, langue).

Incremental : un article deja indexe et inchange est ignore ; un article modifie est re-indexe.
On peut donc relancer ce script apres chaque collecte sans rien dupliquer.

Usage :  python -m rag.etape2_vectorisation                      (lit articles_steg.json)
         python -m rag.etape2_vectorisation --reset              (vide la base et reindexe tout)
Modele  : variable d'environnement EMBED_MODEL (defaut : sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2).
          Attention : ce modele ne lit que ~128 tokens (environ 500 caracteres) par morceau ; le reste
          est ignore. D'ou CHUNK_SIZE = 500. Avec 'intfloat/multilingual-e5-small' (512 tokens) tu peux
          monter CHUNK_SIZE a 1000.
"""
import argparse
import hashlib
import json
import os
import re

import chromadb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(ROOT, "rag", "data", "chroma_steg"))
COLLECTION = "steg_actualite"
EMBED_MODEL = os.environ.get("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 500))       # caracteres par morceau (maximum)
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 100))  # caracteres repetes entre deux morceaux
BATCH = 64


# ----------------------------------------------------------------------------
# 1. Decoupage en morceaux (chunking)
# ----------------------------------------------------------------------------
# Fin de phrase : . ! ? et le point d'interrogation arabe ؟ (suivis d'un espace), ou saut de ligne
_FIN_PHRASE = re.compile(r"(?<=[.!?؟…])\s+|\n+")


def decouper_en_phrases(texte, taille_max):
    """Phrases du texte ; une phrase plus longue que taille_max est coupee aux espaces."""
    phrases = []
    for p in _FIN_PHRASE.split(texte):
        p = p.strip()
        while len(p) > taille_max:
            coupe = p.rfind(" ", 0, taille_max)
            coupe = coupe if coupe > taille_max // 2 else taille_max
            phrases.append(p[:coupe].strip())
            p = p[coupe:].strip()
        if p:
            phrases.append(p)
    return phrases


def decouper(texte, taille=CHUNK_SIZE, chevauchement=CHUNK_OVERLAP):
    """Morceaux de `taille` caracteres au plus, avec `chevauchement` caracteres repris du morceau precedent.
    On avance phrase par phrase : un morceau commence et finit toujours a une limite de phrase."""
    if chevauchement >= taille:
        raise ValueError("chevauchement doit etre inferieur a taille")
    phrases = decouper_en_phrases(texte, taille)
    morceaux, courant = [], []
    for ph in phrases:
        if courant and len(" ".join(courant + [ph])) > taille:
            morceaux.append(" ".join(courant))
            reprise, n = [], 0                       # on reprend les dernieres phrases (jusqu'a `chevauchement`)
            for x in reversed(courant):
                if n + len(x) > chevauchement:
                    break
                reprise.insert(0, x)
                n += len(x) + 1
            courant = reprise
            while courant and len(" ".join(courant + [ph])) > taille:
                courant.pop(0)                       # la phrase suivante ne rentre pas : on reduit la reprise
        courant.append(ph)
    if courant:
        dernier = " ".join(courant)
        if not morceaux or dernier != morceaux[-1]:
            morceaux.append(dernier)
    return morceaux


def detecter_langue(texte):
    """'ar' si au moins 30 % des lettres sont arabes, sinon 'fr' (suffisant pour ce corpus fr/ar)."""
    lettres = [c for c in texte if c.isalpha()]
    if not lettres:
        return "fr"
    arabes = sum("؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ" for c in lettres)
    return "ar" if arabes / len(lettres) >= 0.30 else "fr"


# ----------------------------------------------------------------------------
# 2. Embeddings multilingues
# ----------------------------------------------------------------------------
class Embedder:
    """Modele d'embedding multilingue de Hugging Face (gratuit, execute en local, francais + arabe).
    Le MEME objet sert a l'indexation (etape 2) et aux questions (etape 3).
    Premier lancement : telechargement du modele (~470 Mo) dans le cache Hugging Face, puis hors ligne."""

    def __init__(self, nom=EMBED_MODEL, device=None):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise SystemExit("Installe la bibliotheque :  pip install sentence-transformers") from e
        self.nom = nom
        self.modele = SentenceTransformer(nom, device=device)   # device=None : GPU si disponible, sinon CPU
        # Ce modele tronque au-dela de max_seq_length tokens (128 par defaut) : CHUNK_SIZE est regle en consequence
        self.max_tokens = self.modele.max_seq_length

    def _prefixe(self, textes, role):
        # Les modeles e5 exigent "passage: " pour les documents et "query: " pour les questions
        if "e5" in self.nom.lower():
            return [f"{role}: {t}" for t in textes]
        return textes

    def documents(self, textes):
        return self._encoder(self._prefixe(textes, "passage"))

    def question(self, texte):
        return self._encoder(self._prefixe([texte], "query"))[0]

    def _encoder(self, textes):
        # normalize_embeddings=True : vecteurs de norme 1, adaptes a la distance cosinus de la collection Chroma
        return self.modele.encode(textes, normalize_embeddings=True, batch_size=32,
                                  show_progress_bar=False).tolist()


# ----------------------------------------------------------------------------
# 3. Stockage dans ChromaDB
# ----------------------------------------------------------------------------
def ouvrir_collection(reset=False, chemin=CHROMA_DIR):
    client = chromadb.PersistentClient(path=chemin)
    if reset:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
    # distance cosinus : 0 = identique, plus c'est grand moins c'est proche
    return client.get_or_create_collection(COLLECTION, configuration={"hnsw": {"space": "cosine"}})


def empreinte(article):
    return hashlib.sha1((article["titre"] + article["texte_brut"]).encode("utf-8")).hexdigest()


def indexer(articles, collection, embedder):
    """Indexe les articles nouveaux ou modifies. Retourne (articles_indexes, morceaux_ajoutes, ignores)."""
    n_art = n_chunks = ignores = 0
    for a in articles:
        if not a.get("texte_brut") or not a.get("url"):
            continue
        h = empreinte(a)
        deja = collection.get(where={"url": a["url"]}, include=["metadatas"])
        if deja["ids"]:
            if deja["metadatas"][0].get("empreinte") == h:
                ignores += 1                            # deja indexe, inchange
                continue
            collection.delete(ids=deja["ids"])          # article modifie : on remplace ses morceaux
        morceaux = decouper(a["texte_brut"])
        if not morceaux:
            continue
        base = hashlib.sha1(a["url"].encode("utf-8")).hexdigest()[:16]
        meta = {"source": a.get("source") or "", "url": a["url"], "date": a.get("date") or "",
                "titre": a.get("titre") or "", "langue": detecter_langue(a["texte_brut"]), "empreinte": h}
        for i in range(0, len(morceaux), BATCH):
            lot = morceaux[i:i + BATCH]
            collection.upsert(
                ids=[f"{base}-{i + j}" for j in range(len(lot))],
                documents=lot,
                embeddings=embedder.documents(lot),
                metadatas=[{**meta, "chunk": i + j} for j in range(len(lot))])
        n_art += 1
        n_chunks += len(morceaux)
    return n_art, n_chunks, ignores


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="entree", default=os.path.join(ROOT, "news", "data", "articles_steg.json"))
    ap.add_argument("--reset", action="store_true", help="vider la base avant d'indexer")
    args = ap.parse_args()

    with open(args.entree, encoding="utf-8") as f:
        articles = json.load(f)
    print(f"{len(articles)} articles lus dans {args.entree}")
    print(f"Chargement du modele d'embedding : {EMBED_MODEL}")
    col = ouvrir_collection(reset=args.reset)
    n_art, n_chunks, ignores = indexer(articles, col, Embedder())
    print(f"{n_art} articles indexes ({n_chunks} morceaux), {ignores} deja a jour. "
          f"Total dans la base : {col.count()} morceaux.")


if __name__ == "__main__":
    main()