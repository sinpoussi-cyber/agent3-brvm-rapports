"""
Analyseur de documents financiers BRVM.

Stratégie à deux niveaux :
  1. DeepSeek EN PRIORITÉ  — API compatible OpenAI, texte extrait du PDF
     localement (pypdf) puis envoyé au modèle.
  2. Claude (Anthropic) EN SECOURS — si DeepSeek échoue pour quelque raison
     que ce soit (erreur API, solde insuffisant, réponse non parseable, ou
     PDF scanné sans texte extractible), on bascule sur Claude, qui lit le
     PDF nativement en base64.

Interface publique inchangée : analyze(societe, doc_titre, pdf_bytes, url)
-> dict | None. main.py n'a donc rien à modifier.

Clés attendues dans .env / secrets :
  - DEEPSEEK_API_KEY   (primaire)
  - ANTHROPIC_API_KEY  (secours)
"""

import base64
import io
import json
import os
import re
import time

import anthropic
from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    OpenAI,
    RateLimitError,
)
from pypdf import PdfReader

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# DeepSeek (primaire). Les alias deepseek-chat / deepseek-reasoner ont été
# dépréciés le 2026-07-24 ; on utilise les modèles V4 actuels.
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# Claude (secours).
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Borne de texte PDF envoyée à DeepSeek (maîtrise coût/latence).
MAX_CHARS = int(os.getenv("DEEPSEEK_MAX_CHARS", "120000"))

PROMPT_TEMPLATE = """Tu es un analyste financier expert en marchés boursiers africains, spécialisé sur la BRVM.

Analyse ce document financier de la société {societe} ({doc_titre}).

Retourne UNIQUEMENT un objet JSON valide, sans texte avant ni après, avec exactement cette structure :

{{
  "resume": "Résumé exécutif en 5 phrases couvrant la situation globale de la société.",
  "points_cles": [
    "Point important 1",
    "Point important 2",
    "Point important 3",
    "Point important 4",
    "Point important 5",
    "Point important 6",
    "Point important 7"
  ],
  "indicateurs": {{
    "chiffre_affaires": "valeur avec unité ou null",
    "resultat_net": "valeur avec unité ou null",
    "dividende": "valeur par action ou null",
    "marge_nette": "pourcentage ou null",
    "total_actif": "valeur avec unité ou null",
    "capitaux_propres": "valeur avec unité ou null",
    "autres": {{}}
  }},
  "recommandation": {{
    "decision": "acheter | conserver | vendre",
    "justification": "Justification courte en 2 phrases maximum."
  }},
  "risques": [
    "Risque principal 1",
    "Risque principal 2",
    "Risque principal 3"
  ],
  "perspectives": "Outlook pour l'année suivante en 2 à 3 phrases."
}}

Si une information n'est pas disponible dans le document, utilise null pour les champs scalaires et [] pour les listes."""


# ---------------------------------------------------------------------------
# Point d'entrée : DeepSeek en priorité, Claude en secours
# ---------------------------------------------------------------------------

def analyze(societe: str, doc_titre: str, pdf_bytes: bytes, url: str) -> dict | None:
    """
    Analyse un PDF financier. Essaie DeepSeek d'abord ; en cas d'échec,
    bascule sur Claude. Retourne un dict JSON parsé ou None si les deux
    échouent.
    """
    # 1) Tentative DeepSeek (primaire)
    resultat = _analyze_deepseek(societe, doc_titre, pdf_bytes, url)
    if resultat is not None:
        return resultat

    # 2) Bascule sur Claude (secours)
    print(f"[FALLBACK] DeepSeek indisponible, bascule sur Claude : {societe} – {doc_titre}")
    resultat = _analyze_claude(societe, doc_titre, pdf_bytes, url)
    if resultat is not None:
        return resultat

    print(f"[ERREUR] Analyse échouée sur DeepSeek ET Claude : {societe} – {doc_titre}")
    return None


# ---------------------------------------------------------------------------
# Niveau 1 : DeepSeek
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_bytes: bytes, url: str) -> str | None:
    """
    Extrait le texte d'un PDF. Retourne None si le PDF est illisible ou
    sans couche texte (PDF scanné → sera pris en charge par Claude).
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        print(f"[DeepSeek] Lecture PDF échouée pour {url} : {e}")
        return None

    morceaux = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt:
            morceaux.append(txt)

    texte = "\n".join(morceaux).strip()
    if not texte:
        print(f"[DeepSeek] PDF sans texte extractible (probablement scanné) : {url}")
        return None

    if len(texte) > MAX_CHARS:
        texte = texte[:MAX_CHARS]
    return texte


def _analyze_deepseek(societe: str, doc_titre: str, pdf_bytes: bytes, url: str) -> dict | None:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("[DeepSeek] DEEPSEEK_API_KEY manquante, on saute vers le secours")
        return None

    contenu = extract_pdf_text(pdf_bytes, url)
    if contenu is None:
        return None  # PDF scanné/illisible → laisser Claude essayer

    prompt = (
        PROMPT_TEMPLATE.format(societe=societe, doc_titre=doc_titre)
        + "\n\n--- DÉBUT DU TEXTE DU DOCUMENT ---\n"
        + contenu
        + "\n--- FIN DU TEXTE DU DOCUMENT ---"
    )

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            max_tokens=8000,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un analyste financier expert de la BRVM. "
                        "Tu réponds toujours uniquement par un objet JSON valide."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except RateLimitError:
        print(f"[DeepSeek] Rate limit ({societe} – {doc_titre}) → bascule Claude")
        return None
    except APIStatusError as e:
        message = getattr(e, "message", str(e))
        print(f"[DeepSeek] API status {e.status_code} pour {societe} – {doc_titre} : {message}")
        return None
    except APIConnectionError as e:
        print(f"[DeepSeek] Connexion échouée pour {societe} – {doc_titre} : {e}")
        return None
    except APIError as e:
        print(f"[DeepSeek] Erreur API pour {societe} – {doc_titre} : {e}")
        return None

    try:
        raw_text = (response.choices[0].message.content or "").strip()
    except (AttributeError, IndexError) as e:
        print(f"[DeepSeek] Réponse inattendue pour {societe} – {doc_titre} : {e}")
        return None

    resultat = parse_json_response(raw_text)
    if resultat is None:
        print(f"[DeepSeek] Réponse non parseable pour {societe} – {doc_titre}")
        return None

    print(f"[OK] Analyse DeepSeek terminée : {societe} – {doc_titre}")
    return resultat


# ---------------------------------------------------------------------------
# Niveau 2 : Claude (Anthropic) — lit le PDF nativement en base64
# ---------------------------------------------------------------------------

def _analyze_claude(societe: str, doc_titre: str, pdf_bytes: bytes, url: str) -> dict | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[Claude] ANTHROPIC_API_KEY manquante")
        return None

    try:
        base64_data = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    except Exception as e:
        print(f"[Claude] Encodage base64 échoué pour {url} : {e}")
        return None

    prompt = PROMPT_TEMPLATE.format(societe=societe, doc_titre=doc_titre)
    client = anthropic.Anthropic(api_key=api_key)

    def _call_claude() -> anthropic.types.Message:
        return client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

    try:
        message = _call_claude()
    except anthropic.RateLimitError:
        print(f"[Claude] Rate limit atteint, attente 60 s... ({societe} – {doc_titre})")
        time.sleep(60)
        try:
            message = _call_claude()
        except anthropic.APIError as e:
            print(f"[Claude] Echec après retry rate limit pour {societe} – {doc_titre} : {e}")
            return None
    except anthropic.APIStatusError as e:
        print(f"[Claude] API status {e.status_code} pour {societe} – {doc_titre} : {e.message}")
        return None
    except anthropic.APIConnectionError as e:
        print(f"[Claude] Connexion échouée pour {societe} – {doc_titre} : {e}")
        return None
    except anthropic.APIError as e:
        print(f"[Claude] Erreur API pour {societe} – {doc_titre} : {e}")
        return None

    raw_text = message.content[0].text.strip()
    resultat = parse_json_response(raw_text)
    if resultat is None:
        print(f"[Claude] Réponse non parseable pour {societe} – {doc_titre}")
        print(f"[DEBUG] Début de la réponse : {raw_text[:300]}")
        return None

    print(f"[OK] Analyse Claude terminée : {societe} – {doc_titre}")
    return resultat


# ---------------------------------------------------------------------------
# Utilitaire commun
# ---------------------------------------------------------------------------

def parse_json_response(text: str) -> dict | None:
    """Tente de parser du JSON depuis une chaîne, même entourée de texte."""
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage : python claude_analyzer.py <chemin_pdf>")
        sys.exit(1)

    chemin = sys.argv[1]
    with open(chemin, "rb") as f:
        contenu = f.read()

    resultat = analyze(
        societe="TEST",
        doc_titre="Document de test",
        pdf_bytes=contenu,
        url=chemin,
    )
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
