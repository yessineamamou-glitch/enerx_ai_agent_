# Changements : news en information seulement (plus de RAG)

- `/forecast` : le dividende = production prevue x tarif STEG. Plus de coefficient news
  (`use_news` et `news_coef` sont supprimes ; s'ils sont envoyes, ils sont ignores).
- `/news` : renvoie les articles collectes par l'etape 1 (`etape1_collecte.py` -> `articles_steg.json`),
  avec titre, source, date, lien et un extrait. Secours : `news_headlines.json` (GDELT).
  Champ `informational_only: true`.
- `news_feed.py` (nouveau) lit ces fichiers et relance la collecte en arriere-plan (toutes les heures).
- RAG, vectorisation et coefficient news deplaces dans `_archive_rag/` (non utilises).
- `requirements.txt` allege (plus de chromadb / sentence-transformers / hiero). Hedera : `requirements-hedera.txt`.
- `fx_rate.json` ajoute (taux de repli STATUT EXEMPLE a remplacer par le taux officiel).

## Lancer
    pip install -r requirements.txt
    python -m news.etape1_collecte       # AVANT la demo : remplit articles_steg.json (a commiter)
    uvicorn api:app --host 0.0.0.0 --port 8001

Hebergement (Render / Railway / FastAPI Cloud) : commande de demarrage
`uvicorn api:app --host 0.0.0.0 --port $PORT`. Mettre l'URL obtenue dans le frontend :
`NEXT_PUBLIC_AI_API_URL=https://...` (fichier `.env.local` ou variables Vercel).

## RAG reconstruit (module `rag/`, endpoint `GET /ask`)
- L'ancien code RAG (`_archive_rag/`, chromadb + sentence-transformers) n'etait pas dans le projet : le RAG a ete
  reecrit, plus leger (BM25 en Python pur, aucune base vectorielle, aucun modele a telecharger).
- Reste INFORMATIF, comme les news : aucune influence sur le dividende, la prevision ou le hash.
- Corpus : `rag/data/knowledge.md` + `articles_steg.json` (meme filtre que `/news`). Reponses citees ;
  LLM facultatif (Gemini / Claude), repli extractif hors ligne ; "no_match" plutot qu'une reponse inventee.
- Pipeline vectoriel d'origine reintegre dans `rag/` : `etape2_vectorisation.py` (inchange, chemins ancres au projet),
  `etape3_rag.py` (REECRIT : le fichier fourni contenait en fait les tests ; interface deduite de `test_rag_pipeline.py`),
  `coefficient_news.py` (NON branche sur /forecast). Backend optionnel `ENERX_RAG_BACKEND=chroma` (requirements-rag.txt).
- `RAG_MAX_DISTANCE` (0.75) NON calibre : modele d'embedding non telecharge lors de l'ecriture. Tests du pipeline avec un
  faux embedder ; les tests `est_pertinent` / RSS ont ete adaptes au filtre `news/pertinence.py`, plus strict que l'ancien.
- Tests : `tests/test_rag.py`, `tests/test_rag_pipeline.py`.

## Coefficient news RE-ACTIVE (decision du proprietaire du projet)
- `/forecast` : `use_news` (defaut true) applique le multiplicateur du jour (0.90-1.10) lu par `rag/coefficient_service.py`
  dans le rapport `coefficient_news_AAAA-MM-JJ.json` ; jamais calcule pendant la requete. Sans rapport : 1.0 + avertissement.
- Le rapport contient `assumptions.news_coefficient` et un bloc `news` (indice, tendance, questions, impacts, URL, SHA-256 du
  rapport du jour) ; tout est dans `report_hash` -> les hash ancres avant cette version ne correspondent plus.
- Les kWh prevus ne sont jamais modifies : seul le revenu l'est. `/news` et `/ask` restent informatifs.
- Front : coefficient affiche dans le panneau "Revenue forecast". Front : panneau "Ask EnerX" (`ask-panel.tsx`).
