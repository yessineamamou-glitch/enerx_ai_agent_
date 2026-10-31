"""
Nettoie articles_steg.json : ne garde que les articles pertinents pour le prix du token (voir pertinence.py).
Une copie de securite est faite dans articles_steg.backup.json. Affiche ce qui est retire pour verification.

Usage :  python nettoyer_articles.py            (fichier par defaut : articles_steg.json)
"""
import json
import os
import sys

from news import pertinence

FICHIER = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "articles_steg.json")

with open(FICHIER, encoding="utf-8") as f:
    articles = json.load(f)

gardes, retires = [], []
for a in articles:
    ok, termes = pertinence.analyser(a.get("titre", ""), a.get("texte_brut", ""))
    if ok and not pertinence.est_de_cette_annee(a.get("date")):     # annee courante seulement, date obligatoire
        ok = False
    (gardes if ok else retires).append((a, termes))

with open(os.path.splitext(FICHIER)[0] + ".backup.json", "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)
with open(FICHIER, "w", encoding="utf-8") as f:
    json.dump([a for a, _ in gardes], f, ensure_ascii=False, indent=2)

print(f"{len(gardes)} articles gardes sur {len(articles)}.\n")
for a, termes in gardes:
    print(f"  GARDE  {a['titre'][:70]}   <- {', '.join(termes[:4])}")
for a, _ in retires:
    print(f"  RETIRE {a['titre'][:70]}")
