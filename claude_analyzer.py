import base64
import json
import os
import re
import time

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-20250514"

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


def analyze(societe: str, doc_titre: str, pdf_bytes: bytes, url: str) -> dict | None:
    """
    Analyse un PDF financier via Claude et retourne un dict structuré.

    Args:
        societe: Nom de la société (ex: "SONATEL")
        doc_titre: Titre du document (ex: "Rapport annuel 2025")
        pdf_bytes: Contenu binaire du PDF
        url: URL source du document (pour le logging)

    Returns:
        Dict JSON parsé ou None en cas d'erreur
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERREUR] ANTHROPIC_API_KEY manquante dans .env")
        return None

    try:
        base64_data = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    except Exception as e:
        print(f"[ERREUR] Encodage base64 échoué pour {url} : {e}")
        return None

    prompt = PROMPT_TEMPLATE.format(societe=societe, doc_titre=doc_titre)

    client = anthropic.Anthropic(api_key=api_key)

    def _call_claude() -> anthropic.types.Message:
        return client.messages.create(
            model=MODEL,
            max_tokens=4096,
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
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

    try:
        message = _call_claude()
    except anthropic.RateLimitError:
        print(f"[RATE LIMIT] Rate limit atteint, attente 60 secondes... ({societe} – {doc_titre})")
        time.sleep(60)
        try:
            message = _call_claude()
        except anthropic.APIError as e:
            print(f"[ERREUR] Echec après retry rate limit pour {societe} – {doc_titre} : {e}")
            return None
    except anthropic.APIStatusError as e:
        print(f"[ERREUR] Claude API status {e.status_code} pour {societe} – {doc_titre} : {e.message}")
        return None
    except anthropic.APIConnectionError as e:
        print(f"[ERREUR] Connexion Claude échouée pour {societe} – {doc_titre} : {e}")
        return None
    except anthropic.APIError as e:
        print(f"[ERREUR] Claude API pour {societe} – {doc_titre} : {e}")
        return None

    raw_text = message.content[0].text.strip()

    # Extrait le JSON même si Claude ajoute du texte parasite autour
    json_match = parse_claude_response(raw_text)
    if json_match is None:
        print(f"[ERREUR] Réponse Claude non parseable pour {societe} – {doc_titre}")
        print(f"[DEBUG] Début de la réponse : {raw_text[:300]}")
        return None

    print(f"[OK] Analyse terminée : {societe} – {doc_titre}")
    return json_match


def parse_claude_response(text: str) -> dict | None:
    """Tente de parser du JSON depuis une chaîne, même entourée de texte."""
    # Méthode 1 : extraire entre ```json et ```
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Méthode 2 : extraire entre ``` et ```
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Méthode 3 : trouver le premier { et dernier }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass

    # Méthode 4 : parser le texte brut
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
