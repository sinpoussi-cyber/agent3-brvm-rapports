import re
import warnings
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = "https://www.brvm.org"
RAPPORTS_URL = "https://www.brvm.org/fr/rapports-societes-cotees"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

DEFAULT_SOCIETES = [
    "SONATEL", "ORANGE CI", "CORIS BANK", "BOA CI", "NSIA BANQUE",
    "ECOBANK CI", "TOTAL CI", "PALMCI", "SETAO CI", "SODE CI", "ONATEL", "ETI",
]

ANNEE_MIN = 2025


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normaliser(texte: str) -> str:
    return texte.upper().replace("-", " ").replace("_", " ")


def _societe_dans_texte(societe: str, texte: str) -> bool:
    texte_n = _normaliser(texte)
    societe_n = _normaliser(societe)
    if societe_n in texte_n:
        return True
    mots = societe_n.split()
    if len(mots) > 1:
        return all(m in texte_n for m in mots)
    return False


def _extraire_annee(texte: str) -> int | None:
    for annee in re.findall(r"\b(202\d)\b", texte):
        if int(annee) >= ANNEE_MIN:
            return int(annee)
    return None


def _detecter_type_rapport(titre: str) -> str:
    t = titre.lower()
    if "annuel" in t or "annual" in t:
        return "rapport annuel"
    if "semestriel" in t or "semestre" in t:
        return "rapport semestriel"
    if "trimestriel" in t or "trimestre" in t:
        return "rapport trimestriel"
    if "états financiers" in t or "etats financiers" in t or "financial" in t:
        return "états financiers"
    if "prospectus" in t:
        return "prospectus"
    if "note d'information" in t or "note information" in t:
        return "note d'information"
    if "rapport" in t:
        return "rapport"
    return "document"


def _contexte_lien(tag) -> str:
    """Remonte jusqu'à 3 niveaux parents pour récupérer le texte contextuel."""
    parties = [tag.get_text(" ", strip=True), tag.get("href", ""), tag.get("title", "")]
    parent = tag.parent
    for _ in range(3):
        if parent is None:
            break
        parties.append(parent.get_text(" ", strip=True)[:300])
        parent = parent.parent
    return " ".join(filter(None, parties))


def _est_pdf(href: str) -> bool:
    return href.lower().endswith(".pdf") or "/pdf" in href.lower() or "pdf" in href.lower()


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _fetch(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"[ERREUR] {url} → {e}")
        return None


def _extraire_liens_pdf(soup: BeautifulSoup, url_base: str) -> list[dict]:
    """Retourne tous les liens PDF trouvés dans la page avec leur contexte."""
    liens = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if not _est_pdf(href):
            continue
        url_complete = href if href.startswith("http") else urljoin(url_base, href)
        contexte = _contexte_lien(tag)
        titre = tag.get_text(strip=True) or tag.get("title", "") or href.split("/")[-1]
        liens.append({"url": url_complete, "titre": titre, "contexte": contexte})
    return liens


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_rapports(societes: list[str] | None = None) -> list[dict]:
    """
    Scrape la page BRVM des rapports et retourne les rapports PDF depuis 2025
    pour les sociétés demandées.
    """
    if societes is None:
        societes = DEFAULT_SOCIETES

    rapports: list[dict] = []
    urls_vues: set[str] = set()

    # --- Page principale ---
    soup_principale = _fetch(RAPPORTS_URL)
    if soup_principale is None:
        return rapports

    # Collecte les liens directs vers des PDFs sur la page principale
    liens_pdf = _extraire_liens_pdf(soup_principale, BASE_URL)

    # Cherche aussi les sous-pages société (liens non-PDF qui pourraient
    # mener à des pages de rapports individuelles)
    sous_pages: list[str] = []
    for tag in soup_principale.find_all("a", href=True):
        href = tag["href"]
        if _est_pdf(href):
            continue
        texte_lien = _contexte_lien(tag)
        for societe in societes:
            if _societe_dans_texte(societe, texte_lien):
                url_sous = href if href.startswith("http") else urljoin(BASE_URL, href)
                if url_sous not in sous_pages and BASE_URL in url_sous:
                    sous_pages.append(url_sous)
                break

    # --- Sous-pages société ---
    for url_sous in sous_pages:
        soup_sous = _fetch(url_sous)
        if soup_sous:
            liens_pdf.extend(_extraire_liens_pdf(soup_sous, url_sous))

    # --- Filtrage et construction des résultats ---
    for lien in liens_pdf:
        url = lien["url"]
        titre = lien["titre"]
        contexte = lien["contexte"]

        if url in urls_vues:
            continue

        texte_complet = f"{titre} {contexte} {url}"
        annee = _extraire_annee(texte_complet)
        if annee is None:
            continue

        for societe in societes:
            if _societe_dans_texte(societe, texte_complet):
                urls_vues.add(url)
                rapports.append({
                    "url": url,
                    "societe": societe,
                    "annee": annee,
                    "type_rapport": _detecter_type_rapport(titre),
                    "doc_titre": titre or f"Document {societe} {annee}",
                })
                break

    print(f"[INFO] {len(rapports)} rapport(s) trouvé(s) pour {len(societes)} société(s)")
    return rapports


if __name__ == "__main__":
    for rapport in get_rapports():
        print(rapport)
