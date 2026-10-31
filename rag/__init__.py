"""
EnerX - RAG (questions/reponses sur la base de connaissances EnerX et les news STEG recentes).

/ask est INFORMATIF : il repond avec des citations et ne modifie rien. Seul coefficient_service.py (indice news du jour,
borne a +-10 %) alimente GET /forecast ; les chiffres du dividende viennent uniquement de GET /forecast.

  knowledge.py  corpus : rag/data/knowledge.md + articles_steg.json (meme filtre que GET /news)
  retriever.py  recherche BM25 (pur Python, sans modele a telecharger ni base vectorielle)
  llm.py        generation facultative (Gemini / Claude) ; sans cle -> reponse extractive
  coefficient_news.py / coefficient_service.py  indice news quotidien -> multiplicateur lu par /forecast
  answer.py     orchestration : retrieve -> (LLM | extractif) -> reponse + sources
"""
