import argparse
import sys
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
    doc_exists,
    get_rapports_recent,
    insert_rapport,
    mark_sent,
)

SOCIETES = [
    "SONATEL", "ORANGE CI", "CORIS BANK", "BOA CI", "NSIA BANQUE",
    "ECOBANK CI", "TOTAL CI", "PALMCI", "SETAO CI", "SODE CI", "ONATEL", "ETI",
]

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
    log(f"Sociétés ciblées : {', '.join(SOCIETES)}")

    log("Scraping de la page BRVM en cours...")
    rapports = get_rapports(SOCIETES)
    log(f"{len(rapports)} rapport(s) trouvé(s) par le scraper")

    nb_nouveaux = 0
    nb_ignores = 0
    nb_erreurs = 0
    societes_traitees: set[str] = set()

    for i, rapport in enumerate(rapports, 1):
        url = rapport.get("url", "")
        societe = rapport.get("societe", "?")
        doc_titre = rapport.get("doc_titre", "")
        annee = rapport.get("annee", "")
        type_rapport = rapport.get("type_rapport", "")

        log(f"[{i}/{len(rapports)}] {societe} – {doc_titre} ({type_rapport} {annee})")

        # Vérification doublon
        if doc_exists(url):
            log(f"  → Déjà en base, ignoré")
            nb_ignores += 1
            continue

        # Téléchargement du PDF
        log(f"  → Téléchargement : {url}")
        try:
            resp = requests.get(url, headers=HEADERS_DL, timeout=30, verify=False)
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
            url=url,
        )
        if analyse is None:
            log(f"  → [ERREUR] Analyse Claude échouée, rapport ignoré")
            nb_erreurs += 1
            continue

        recommandation = analyse.get("recommandation") or {}
        decision = (recommandation.get("decision") or "N/A").upper()
        log(f"  → Analyse OK — Recommandation : {decision}")

        # Insertion Supabase
        data = {
            "societe": societe,
            "annee": annee,
            "type_rapport": type_rapport,
            "doc_titre": doc_titre,
            "doc_url": url,
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
    log(f"  Ignorés (doublons)  : {nb_ignores}")
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

    log("Envoi de l'email via Gmail...")
    ok = send_report(
        subject=contenu["subject"],
        body_html=contenu["body_html"],
        body_text=contenu["body_text"],
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
