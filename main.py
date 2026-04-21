import argparse
import sys
import time
import warnings
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from brvm_rapports_scraper import get_rapports
from claude_analyzer import analyze
from email_sender import send_report
from report_generator import generate
from supabase_client import (
    _get_client,
    get_rapports_recent,
    insert_rapport,
    mark_sent,
)

SOCIETES = [
    {"nom": "SONATEL", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sonatel"},
    {"nom": "CORIS BANK", "url": "https://www.brvm.org/fr/rapports-societe-cotes/coris-bank-international"},
    {"nom": "ECOBANK CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/ecobank-ci"},
    {"nom": "LNB", "url": "https://www.brvm.org/fr/rapports-societe-cotes/lnb"},
    {"nom": "FILTISAC CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/filtisac-ci"},
    {"nom": "ECOBANK TG", "url": "https://www.brvm.org/fr/rapports-societe-cotes/ecobank-tg"},
    {"nom": "CIE CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/cie-ci"},
    {"nom": "CFAO MOTORS CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/cfao-motors-ci"},
    {"nom": "AGL", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bollore-transport-logistics"},
    {"nom": "BIIC", "url": "https://www.brvm.org/fr/rapports-societe-cotes/biic"},
    {"nom": "BICI CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bici-ci"},
    {"nom": "BERNABE CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bernabe-ci"},
    {"nom": "BOA SN", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bank-africa-sn"},
    {"nom": "BOA NG", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bank-africa-ng"},
    {"nom": "BOA ML", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bank-africa-ml"},
    {"nom": "BOA CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bank-africa-ci"},
    {"nom": "BOA BN", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bank-africa-bn"},
    {"nom": "BOA BF", "url": "https://www.brvm.org/fr/rapports-societe-cotes/bank-africa-bf"},
    {"nom": "AIR LIQUIDE CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/air-liquide-ci"},
    {"nom": "SUCRIVOIRE", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sucrivoire"},
    {"nom": "SOLIBRA", "url": "https://www.brvm.org/fr/rapports-societe-cotes/solibra"},
    {"nom": "SOGB", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sogb"},
    {"nom": "SODECI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sodeci"},
    {"nom": "SMB", "url": "https://www.brvm.org/fr/rapports-societe-cotes/smb"},
    {"nom": "SITAB", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sitab"},
    {"nom": "SICOR", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sicor"},
    {"nom": "SIB", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sib"},
    {"nom": "SICABLE", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sicable"},
    {"nom": "SGB CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sgb-ci"},
    {"nom": "SETAO CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/setao-ci"},
    {"nom": "SERVAIR CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/servair-abidjan-ci"},
    {"nom": "SAPH CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/saph-ci"},
    {"nom": "SAFCA CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/safca-ci"},
    {"nom": "PALM CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/palm-ci"},
    {"nom": "ORANGE CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/orange-ci"},
    {"nom": "ORAGROUP", "url": "https://www.brvm.org/fr/rapports-societe-cotes/oragroup"},
    {"nom": "ONATEL BF", "url": "https://www.brvm.org/fr/rapports-societe-cotes/onatel-bf"},
    {"nom": "NSBC", "url": "https://www.brvm.org/fr/rapports-societe-cotes/nsbc"},
    {"nom": "NESTLE CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/nestle-ci"},
    {"nom": "NEI CEDA CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/nei-ceda-ci"},
    {"nom": "TOTAL CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/total"},
    {"nom": "TOTAL SENEGAL", "url": "https://www.brvm.org/fr/rapports-societe-cotes/total-senegal-sa"},
    {"nom": "TRACTAFRIC CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/tractafric-ci"},
    {"nom": "UNILEVER CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/unilever-ci"},
    {"nom": "UNIWAX CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/uniwax-ci"},
    {"nom": "VIVO ENERGY CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/vivo-energy-ci"},
]
# TODO: retirer après validation — limite le collect aux 3 premières sociétés
SOCIETES = SOCIETES[:3]

HEADERS_DL = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}")


# ---------------------------------------------------------------------------
# Mode collect
# ---------------------------------------------------------------------------

def cmd_collect() -> None:
    log("=== DÉBUT COLLECT ===")
    log(f"Sociétés ciblées : {', '.join(s['nom'] for s in SOCIETES)}")

    log("Scraping de la page BRVM en cours...")
    rapports = get_rapports(SOCIETES)
    log(f"{len(rapports)} rapport(s) trouvé(s) par le scraper")

    supabase = _get_client()
    nb_nouveaux = 0
    total_skipped = 0
    nb_erreurs = 0
    societes_traitees: set[str] = set()

    for i, rapport in enumerate(rapports, 1):
        pdf_url = rapport.get("url", "")
        societe = rapport.get("societe", "?")
        doc_titre = rapport.get("doc_titre", "")
        annee = rapport.get("annee", "")
        type_rapport = rapport.get("type_rapport", "")

        log(f"[{i}/{len(rapports)}] {societe} – {doc_titre} ({type_rapport} {annee})")

        # Vérification doublon
        result = supabase.table("brvm_rapports_societes").select("id").eq("doc_url", pdf_url).execute()
        if result.data:
            log(f"[SKIP] Déjà en base : {pdf_url[:80]}")
            total_skipped += 1
            continue

        # Téléchargement du PDF
        log(f"  → Téléchargement : {pdf_url}")
        try:
            resp = requests.get(pdf_url, headers=HEADERS_DL, timeout=30, verify=False)
            resp.raise_for_status()
            pdf_bytes = resp.content
            log(f"  → PDF reçu ({len(pdf_bytes) // 1024} Ko)")
        except requests.exceptions.RequestException as e:
            log(f"  → [ERREUR] Téléchargement échoué : {e}")
            nb_erreurs += 1
            continue

        # Analyse Claude
        log(f"  → Analyse Claude en cours...")
        analyse = analyze(
            societe=societe,
            doc_titre=doc_titre,
            pdf_bytes=pdf_bytes,
            url=pdf_url,
        )
        if analyse is None:
            log(f"  → [ERREUR] Analyse Claude échouée, rapport ignoré")
            nb_erreurs += 1
            continue

        recommandation = analyse.get("recommandation") or {}
        decision = (recommandation.get("decision") or "N/A").upper()
        log(f"  → Analyse OK — Recommandation : {decision}")
        time.sleep(65)

        # Insertion Supabase
        data = {
            "societe": societe,
            "annee": annee,
            "type_rapport": type_rapport,
            "doc_titre": doc_titre,
            "doc_url": pdf_url,
            "resume": analyse.get("resume"),
            "points_cles": analyse.get("points_cles"),
            "indicateurs": analyse.get("indicateurs"),
            "recommandation": analyse.get("recommandation"),
            "risques": analyse.get("risques"),
            "perspectives": analyse.get("perspectives"),
            "envoye_email": False,
        }
        inserted = insert_rapport(data)
        if inserted:
            log(f"  → Sauvegardé en base (id={inserted.get('id')})")
            nb_nouveaux += 1
            societes_traitees.add(societe)
        else:
            log(f"  → [ERREUR] Insertion Supabase échouée")
            nb_erreurs += 1

    log("=== RÉSUMÉ COLLECT ===")
    log(f"  Sociétés scrapées   : {len(SOCIETES)}")
    log(f"  Sociétés avec docs  : {len(societes_traitees)}")
    log(f"  Nouveaux rapports   : {nb_nouveaux}")
    log(f"  Ignorés (doublons)  : {total_skipped}")
    log(f"  Erreurs             : {nb_erreurs}")

    log("=== FIN COLLECT ===")


# ---------------------------------------------------------------------------
# Modes rapport
# ---------------------------------------------------------------------------

def cmd_rapport(type_rapport: str) -> None:
    labels = {"quotidien": "JOUR", "hebdo": "HEBDO", "mensuel": "MENSUEL"}
    label = labels.get(type_rapport, type_rapport.upper())

    log(f"=== DÉBUT RAPPORT-{label} ===")

    log("Récupération des rapports récents depuis Supabase...")
    rapports = get_rapports_recent(jours=_jours_pour(type_rapport))
    log(f"{len(rapports)} rapport(s) récupéré(s)")

    if not rapports:
        log("Aucun rapport — génération d'un email vide")

    log("Génération du contenu email...")
    contenu = generate(rapports, type_rapport)
    log(f"Sujet : {contenu['subject']}")

    log("Envoi de l'email via SMTP...")
    ok = send_report(
        subject=contenu["subject"],
        html_body=contenu["body_html"],
    )

    if ok:
        log("Email envoyé avec succès")
        if rapports:
            ids = [r["id"] for r in rapports if r.get("id")]
            if ids:
                log(f"Marquage de {len(ids)} rapport(s) comme envoyés...")
                mark_sent(ids)
    else:
        log("[ERREUR] Échec de l'envoi email")
        sys.exit(1)

    log(f"=== FIN RAPPORT-{label} ===")


def _jours_pour(type_rapport: str) -> int:
    return {"quotidien": 1, "hebdo": 7, "mensuel": 30}.get(type_rapport, 30)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent BRVM Rapports – collecte et envoi de rapports financiers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes disponibles :
  collect         Scrape la BRVM, télécharge et analyse les nouveaux PDFs
  rapport-jour    Envoie le rapport quotidien (dernières 24h)
  rapport-hebdo   Envoie le rapport hebdomadaire (7 derniers jours)
  rapport-mensuel Envoie le rapport mensuel (30 derniers jours)

Exemples :
  python main.py collect
  python main.py rapport-jour
""",
    )
    parser.add_argument(
        "mode",
        choices=["collect", "rapport-jour", "rapport-hebdo", "rapport-mensuel"],
        help="Mode d'exécution",
    )
    args = parser.parse_args()

    mode_map = {
        "collect": cmd_collect,
        "rapport-jour": lambda: cmd_rapport("quotidien"),
        "rapport-hebdo": lambda: cmd_rapport("hebdo"),
        "rapport-mensuel": lambda: cmd_rapport("mensuel"),
    }
    mode_map[args.mode]()


if __name__ == "__main__":
    main()
