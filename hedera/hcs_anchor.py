"""
EnerX - Ancrage des rapports de l'agent IA sur Hedera Consensus Service (HCS)

Ce script publie l'EMPREINTE (hash SHA-256) d'un rapport de prevision dans un topic HCS.
Le rapport complet reste chez nous ; Hedera garde une preuve horodatee et immuable :
si quelqu'un modifie le rapport apres coup, son hash ne correspond plus au message ancre.

Utilisation (3 commandes) :
  python hcs_anchor.py create-topic                      # une seule fois : cree le topic
  python -m hedera.hcs_anchor anchor examples/demo_report.json           # publie le hash du rapport
  python -m hedera.hcs_anchor verify examples/demo_report.json 1         # verifie le rapport contre le message n°1

Configuration : fichier .env (voir .env.example). La cle privee ne doit JAMAIS etre commitee.
"""
import base64
import json
import os
import sys

import requests
from dotenv import load_dotenv

from production import aggregator

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))   # .env a la racine

NETWORK = os.getenv("NETWORK", "testnet").lower()
MIRROR = f"https://{NETWORK}.mirrornode.hedera.com"
HASHSCAN = f"https://hashscan.io/{NETWORK}"
MAX_MESSAGE_BYTES = 1000      # un message HCS simple est limite a 1024 octets


# ----------------------------------------------------------------------------
# Client Hedera (necessite OPERATOR_ID et OPERATOR_KEY dans .env)
# ----------------------------------------------------------------------------
def get_client():
    from hiero_sdk_python import AccountId, Client, PrivateKey

    # Accepte les deux noms : OPERATOR_ID / OPERATOR_KEY ou HEDERA_OPERATOR_ID / HEDERA_OPERATOR_KEY
    operator_id = os.getenv("OPERATOR_ID") or os.getenv("HEDERA_OPERATOR_ID")
    operator_key = os.getenv("OPERATOR_KEY") or os.getenv("HEDERA_OPERATOR_KEY")
    if not operator_id or not operator_key:
        sys.exit("OPERATOR_ID et OPERATOR_KEY (ou HEDERA_OPERATOR_ID / HEDERA_OPERATOR_KEY) manquants. Copie .env.example en .env et remplis-les "
                 "(compte testnet gratuit sur https://portal.hedera.com).")

    # Les cles du portail Hedera peuvent etre ECDSA ou Ed25519 : un mauvais type donne
    # une erreur INVALID_SIGNATURE. Precise OPERATOR_KEY_TYPE dans .env si besoin.
    key_type = (os.getenv("OPERATOR_KEY_TYPE") or os.getenv("HEDERA_OPERATOR_KEY_TYPE") or "auto").lower()
    if key_type == "ecdsa":
        key = PrivateKey.from_string_ecdsa(operator_key.removeprefix("0x"))
    elif key_type == "ed25519":
        key = PrivateKey.from_string_ed25519(operator_key.removeprefix("0x"))
    else:
        key = PrivateKey.from_string(operator_key)    # cle DER : type detecte automatiquement

    client = {"testnet": Client.for_testnet, "mainnet": Client.for_mainnet,
              "previewnet": Client.for_previewnet}[NETWORK]()
    client.set_operator(AccountId.from_string(operator_id), key)
    return client


# ----------------------------------------------------------------------------
# 1. Creer le topic (une seule fois)
# ----------------------------------------------------------------------------
def create_topic(memo="EnerX - rapports de prevision de l'agent IA"):
    from hiero_sdk_python import TopicCreateTransaction

    client = get_client()
    receipt = TopicCreateTransaction(memo=memo).execute(client)
    topic_id = str(receipt.topic_id)
    print(f"Topic cree : {topic_id}")
    print(f"Ajoute cette ligne dans ton .env :  HCS_TOPIC_ID={topic_id}")
    print(f"Voir sur HashScan : {HASHSCAN}/topic/{topic_id}")
    return topic_id


# ----------------------------------------------------------------------------
# 2. Ancrer le hash d'un rapport
# ----------------------------------------------------------------------------
def build_anchor_message(report):
    """Message compact (moins de 1 Ko) : le hash + quelques repères lisibles."""
    h = aggregator.hash_report(report)
    if report.get("report_hash") and report["report_hash"] != h:
        raise ValueError("Le report_hash du fichier ne correspond pas au contenu : rapport modifie ?")
    msg = {
        "app": "EnerX",
        "type": "ai_forecast_report",
        "v": 1,
        "alg": "sha256",
        "hash": h,
        "generated_at": report.get("generated_at"),
        "lat": report.get("location", {}).get("lat"),
        "lon": report.get("location", {}).get("lon"),
        "capacity_kw": report.get("capacity_kw"),
        "total_kwh": report.get("totals", {}).get("kwh"),
        "dividend_per_token_dt": report.get("totals", {}).get("dividend_per_token_dt"),
        "dividend_per_token_usdc": report.get("totals", {}).get("dividend_per_token_usdc"),
        "fx_rate": report.get("assumptions", {}).get("fx", {}).get("rate"),
    }
    payload = json.dumps(msg, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    if len(payload.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("Message trop long pour un message HCS simple")
    return payload


def anchor_report(report, topic_id=None):
    """Publie le hash sur HCS. Retourne {topic_id, sequence_number, transaction_id, hash, hashscan}."""
    from hiero_sdk_python import TopicId, TopicMessageSubmitTransaction

    topic_id = topic_id or os.getenv("HCS_TOPIC_ID")
    if not topic_id:
        sys.exit("HCS_TOPIC_ID manquant : lance d'abord  python hcs_anchor.py create-topic")

    payload = build_anchor_message(report)
    client = get_client()
    receipt = TopicMessageSubmitTransaction(
        topic_id=TopicId.from_string(topic_id), message=payload
    ).execute(client)

    seq = receipt.topic_sequence_number
    return {
        "topic_id": topic_id,
        "sequence_number": seq,
        "transaction_id": str(receipt.transaction_id),
        "hash": json.loads(payload)["hash"],
        "hashscan": f"{HASHSCAN}/topic/{topic_id}",
    }


# ----------------------------------------------------------------------------
# 3. Verifier un rapport contre le message ancre (lecture seule, aucune cle necessaire)
# ----------------------------------------------------------------------------
def fetch_anchored_message(topic_id, sequence_number):
    url = f"{MIRROR}/api/v1/topics/{topic_id}/messages/{sequence_number}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    msg = json.loads(base64.b64decode(data["message"]).decode("utf-8"))
    return msg, data.get("consensus_timestamp")


def verify_report(report, sequence_number, topic_id=None):
    topic_id = topic_id or os.getenv("HCS_TOPIC_ID")
    if not topic_id:
        sys.exit("HCS_TOPIC_ID manquant dans .env")
    msg, ts = fetch_anchored_message(topic_id, sequence_number)
    local_hash = aggregator.hash_report(report)
    return {
        "ok": msg.get("hash") == local_hash,
        "local_hash": local_hash,
        "anchored_hash": msg.get("hash"),
        "consensus_timestamp": ts,
    }


# ----------------------------------------------------------------------------
# Ligne de commande
# ----------------------------------------------------------------------------
def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["create-topic"]:
        create_topic()
    elif args[:1] == ["anchor"] and len(args) == 2:
        res = anchor_report(_load(args[1]))
        print("Rapport ancre sur Hedera :")
        for k, v in res.items():
            print(f"  {k:16}: {v}")
    elif args[:1] == ["verify"] and len(args) == 3:
        res = verify_report(_load(args[1]), args[2])
        print(f"Hash du fichier : {res['local_hash']}")
        print(f"Hash ancre      : {res['anchored_hash']}  (consensus {res['consensus_timestamp']})")
        print("=> RAPPORT AUTHENTIQUE" if res["ok"] else "=> ATTENTION : le rapport a ete modifie")
    else:
        print(__doc__)