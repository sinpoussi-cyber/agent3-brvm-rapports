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
    {"nom": "LNB", "url": "https://www.brvm.org/fr/rapports-societe-cotes/lnb"},
    {"nom": "FILTISAC CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/filtisac-ci"},
    {"nom": "ECOBANK TG", "url": "https://www.brvm.org/fr/rapports-societe-cotes/ecobank-tg"},
    {"nom": "ECOBANK CI", "url": "https://www.brvm.org/fr/rapports-societe-cotes/ecobank-ci"},
    {"nom": "CORIS BANK", "url": "https://www.brvm.org/fr/rapports-societe-cotes/coris-bank-international"},
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
    {"nom": "SONATEL", "url": "https://www.brvm.org/fr/rapports-societe-cotes/sonatel"},
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

def get_rapports(societes: list[dict] | None = None) -> list[dict]:
    """
    Scrape la page dédiée de chaque société BRVM et retourne les rapports PDF
    depuis 2025. Chaque élément de `societes` doit avoir les clés `nom` et `url`.
    """
    if societes is None:
        societes = DEFAULT_SOCIETES

    rapports: list[dict] = []
    urls_vues: set[str] = set()

    for societe_info in societes:
        nom = societe_info["nom"]
        url_page = societe_info["url"]

        soup = _fetch(url_page)
        if soup is None:
            continue

        liens_pdf = _extraire_liens_pdf(soup, url_page)

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

            urls_vues.add(url)
            rapports.append({
                "url": url,
                "societe": nom,
                "annee": annee,
                "type_rapport": _detecter_type_rapport(titre),
                "doc_titre": titre or f"Document {nom} {annee}",
            })

    print(f"[INFO] {len(rapports)} rapport(s) trouvé(s) pour {len(societes)} société(s)")
    return rapports


if __name__ == "__main__":
    for rapport in get_rapports():
        print(rapport)
