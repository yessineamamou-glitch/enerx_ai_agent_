"""
Verifie que le hash Python et le hash JavaScript sont identiques, y compris pour de tres petits
montants (cas qui donnait des hash differents avec l'ancienne regle : Python ecrit 1e-05).
Usage : python -m hedera.check_hash   (depuis la racine du projet)     (necessite Node.js pour la comparaison JavaScript)
"""
import json
import shutil
import subprocess

import os
import tempfile

from production import aggregator

report = {
    "generated_at": "2026-10-06T10:00:00+00:00",
    "location": {"lat": 32.9297, "lon": 10.4518},
    "capacity_kw": 10,
    "n_int": 5939.0,
    "montants": [0.00001, 0.000003, 1e-7, 0.0, 45.95, 123456.789012, 5939.0, -0.0, 2.5e-5],
    "texte": "Prévision très élevée : é à ç — « test »",
    "ok": True,
    "rien": None,
}
report["report_hash"] = aggregator.hash_report(report)
REPORT_FILE = os.path.join(tempfile.gettempdir(), "hash_test_report.json")
VERIFY_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_hash.js")
with open(REPORT_FILE, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print("Hash Python :", report["report_hash"])

# falsification : un seul chiffre change -> hash different
faux = json.loads(json.dumps(report))
faux["montants"][0] = 0.00002
assert aggregator.hash_report(faux) != report["report_hash"], "falsification non detectee"
print("Falsification detectee : OK")

if shutil.which("node"):
    r = subprocess.run(["node", VERIFY_JS, REPORT_FILE], capture_output=True, text=True)
    print(r.stdout.strip())
    raise SystemExit(r.returncode)
print("Node.js absent : installe-le pour comparer avec JavaScript (https://nodejs.org)")
