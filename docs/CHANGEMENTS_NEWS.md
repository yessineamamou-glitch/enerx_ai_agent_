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
