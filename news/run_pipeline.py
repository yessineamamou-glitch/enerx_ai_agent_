"""Pipeline news EnerX : collecte -> nettoyage -> injection -> articles_steg.json (lu par GET /news)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.chdir(ROOT)           # les modules se lancent avec -m depuis la racine du projet
print("Lancement du pipeline d'analyse EnerX...")

# (commande, bloquant ?) : la collecte web peut echouer (hors-ligne) sans empecher l'injection
STEPS = [
    ([sys.executable, "-m", "news.etape1_collecte", "--max", "6"], False),
    ([sys.executable, "-m", "news.nettoyer_articles"], False),
    ([sys.executable, "-m", "news.injecter_steg"], True),
]
for cmd, bloquant in STEPS:
    print("\nExecution :", " ".join(cmd[1:]))
    if subprocess.run(cmd).returncode != 0:
        print("Erreur dans", cmd[1], "->", "arret" if bloquant else "on continue")
        if bloquant:
            sys.exit(1)
print("\nPipeline termine : articles_steg.json est pret pour le frontend.")
