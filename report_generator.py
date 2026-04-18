from collections import Counter
from datetime import datetime

# ---------------------------------------------------------------------------
# Constantes visuelles
# ---------------------------------------------------------------------------

COULEUR_ENTETE = "#003f7f"
COULEUR_FOND = "#f4f6f9"
COULEUR_CARTE = "#ffffff"
COULEUR_TEXTE = "#2c2c2c"
COULEUR_SECONDAIRE = "#555555"

BADGE = {
    "acheter": ("background:#1a7a3c;color:#fff", "ACHETER"),
    "conserver": ("background:#e07b00;color:#fff", "CONSERVER"),
    "vendre": ("background:#c0392b;color:#fff", "VENDRE"),
}

LABELS = {
    "quotidien": "Rapport Quotidien",
    "hebdo": "Rapport Hebdomadaire",
    "mensuel": "Rapport Mensuel",
}


# ---------------------------------------------------------------------------
# Helpers HTML
# ---------------------------------------------------------------------------

def _badge_html(recommandation: dict | None) -> str:
    if not recommandation:
        return ""
    decision = (recommandation.get("decision") or "").lower().strip()
    justification = recommandation.get("justification", "")
    style, label = BADGE.get(decision, ("background:#888;color:#fff", decision.upper() or "N/A"))
    return (
        f'<span style="display:inline-block;padding:4px 12px;border-radius:4px;'
        f'font-weight:bold;font-size:13px;{style}">{label}</span>'
        f'<span style="font-size:12px;color:{COULEUR_SECONDAIRE};margin-left:8px">{justification}</span>'
    )


def _indicateurs_html(indicateurs: dict | None) -> str:
    if not indicateurs:
        return ""
    champs = {
        "chiffre_affaires": "Chiffre d'affaires",
        "resultat_net": "Résultat net",
        "dividende": "Dividende",
        "marge_nette": "Marge nette",
        "total_actif": "Total actif",
        "capitaux_propres": "Capitaux propres",
    }
    lignes = []
    for cle, label in champs.items():
        valeur = indicateurs.get(cle)
        if valeur and valeur != "null":
            lignes.append(
                f'<tr>'
                f'<td style="padding:4px 8px;color:{COULEUR_SECONDAIRE};font-size:13px">{label}</td>'
                f'<td style="padding:4px 8px;font-weight:bold;font-size:13px">{valeur}</td>'
                f'</tr>'
            )
    # Champs libres dans "autres"
    for cle, valeur in (indicateurs.get("autres") or {}).items():
        if valeur and valeur != "null":
            lignes.append(
                f'<tr>'
                f'<td style="padding:4px 8px;color:{COULEUR_SECONDAIRE};font-size:13px">{cle}</td>'
                f'<td style="padding:4px 8px;font-weight:bold;font-size:13px">{valeur}</td>'
                f'</tr>'
            )
    if not lignes:
        return ""
    return (
        f'<table style="border-collapse:collapse;margin-top:6px">{"".join(lignes)}</table>'
    )


def _points_html(points: list | None) -> str:
    if not points:
        return ""
    items = "".join(f'<li style="margin:3px 0;font-size:13px">{p}</li>' for p in points)
    return f'<ul style="margin:6px 0;padding-left:18px">{items}</ul>'


def _carte_rapport_html(rapport: dict) -> str:
    analyse = rapport.get("analyse") or {}
    societe = rapport.get("societe", "—")
    type_r = rapport.get("type_rapport", "").capitalize()
    annee = rapport.get("annee", "")
    doc_titre = rapport.get("doc_titre", "")
    url = rapport.get("doc_url") or rapport.get("url", "#")

    resume = analyse.get("resume") or rapport.get("resume", "Résumé non disponible.")
    points = analyse.get("points_cles") or rapport.get("points_cles") or []
    indicateurs = analyse.get("indicateurs") or rapport.get("indicateurs")
    recommandation = analyse.get("recommandation") or rapport.get("recommandation")
    risques = analyse.get("risques") or rapport.get("risques") or []

    badge = _badge_html(recommandation)
    indic = _indicateurs_html(indicateurs)
    pts = _points_html(points[:5])  # Limite à 5 points pour l'email
    risques_html = _points_html(risques)

    return f"""
<div style="background:{COULEUR_CARTE};border-radius:8px;padding:20px;margin-bottom:20px;
            border-left:5px solid {COULEUR_ENTETE};box-shadow:0 1px 4px rgba(0,0,0,0.08)">

  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
    <div>
      <span style="font-size:18px;font-weight:bold;color:{COULEUR_ENTETE}">{societe}</span>
      <span style="margin-left:10px;font-size:13px;color:{COULEUR_SECONDAIRE}">{type_r} {annee}</span>
    </div>
    <a href="{url}" style="font-size:12px;color:{COULEUR_ENTETE}">Voir le document →</a>
  </div>

  <p style="font-size:12px;color:{COULEUR_SECONDAIRE};margin:4px 0 12px">{doc_titre}</p>

  <p style="font-size:14px;color:{COULEUR_TEXTE};line-height:1.6;margin:0 0 12px">{resume}</p>

  {'<div style="margin-bottom:12px"><strong style="font-size:13px">Points clés</strong>' + pts + '</div>' if pts else ''}

  {'<div style="margin-bottom:12px"><strong style="font-size:13px">Indicateurs financiers</strong>' + indic + '</div>' if indic else ''}

  {'<div style="margin-bottom:12px"><strong style="font-size:13px">Recommandation</strong><br>' + badge + '</div>' if badge else ''}

  {'<div><strong style="font-size:13px">Risques identifiés</strong>' + risques_html + '</div>' if risques_html else ''}

</div>"""


def _tableau_recapitulatif_html(rapports: list[dict]) -> str:
    compteur = Counter(r.get("societe", "—") for r in rapports)
    lignes = ""
    for i, (societe, nb) in enumerate(sorted(compteur.items())):
        bg = "#f0f4f8" if i % 2 == 0 else COULEUR_CARTE
        lignes += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:8px 14px;font-size:13px">{societe}</td>'
            f'<td style="padding:8px 14px;font-size:13px;text-align:center;font-weight:bold">{nb}</td>'
            f'</tr>'
        )
    return f"""
<table style="width:100%;border-collapse:collapse;margin-top:8px;border-radius:6px;overflow:hidden">
  <thead>
    <tr style="background:{COULEUR_ENTETE};color:#fff">
      <th style="padding:10px 14px;text-align:left;font-size:13px">Société</th>
      <th style="padding:10px 14px;text-align:center;font-size:13px">Rapports</th>
    </tr>
  </thead>
  <tbody>{lignes}</tbody>
</table>"""


# ---------------------------------------------------------------------------
# Corps HTML complet
# ---------------------------------------------------------------------------

def _build_html(rapports: list[dict], label: str, date_str: str) -> str:
    if not rapports:
        contenu = f"""
<div style="text-align:center;padding:40px 20px;color:{COULEUR_SECONDAIRE}">
  <p style="font-size:22px">📭</p>
  <p style="font-size:16px">Aucun nouveau rapport disponible pour cette période.</p>
</div>"""
        recapitulatif = ""
    else:
        contenu = "".join(_carte_rapport_html(r) for r in rapports)
        recapitulatif = f"""
<div style="background:{COULEUR_CARTE};border-radius:8px;padding:20px;margin-bottom:24px">
  <h2 style="color:{COULEUR_ENTETE};font-size:16px;margin:0 0 10px">Récapitulatif</h2>
  {_tableau_recapitulatif_html(rapports)}
  <p style="font-size:12px;color:{COULEUR_SECONDAIRE};margin:10px 0 0">
    Total : <strong>{len(rapports)}</strong> rapport(s) analysé(s)
  </p>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{label} BRVM – {date_str}</title>
</head>
<body style="margin:0;padding:0;background:{COULEUR_FOND};font-family:Arial,Helvetica,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{COULEUR_FOND}">
    <tr><td align="center" style="padding:24px 12px">
      <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%">

        <!-- En-tête -->
        <tr>
          <td style="background:{COULEUR_ENTETE};border-radius:8px 8px 0 0;padding:28px 30px">
            <h1 style="color:#fff;margin:0;font-size:22px">{label}</h1>
            <p style="color:#a8c4e0;margin:6px 0 0;font-size:14px">
              Bourse Régionale des Valeurs Mobilières (BRVM) &mdash; {date_str}
            </p>
          </td>
        </tr>

        <!-- Corps -->
        <tr>
          <td style="padding:24px 30px;background:{COULEUR_FOND}">
            {recapitulatif}
            {contenu}
          </td>
        </tr>

        <!-- Pied de page -->
        <tr>
          <td style="background:{COULEUR_ENTETE};border-radius:0 0 8px 8px;padding:16px 30px;text-align:center">
            <p style="color:#a8c4e0;font-size:12px;margin:0">
              Ce rapport est généré automatiquement à partir des documents publics de la BRVM.<br>
              Les analyses sont produites par intelligence artificielle et ne constituent pas un conseil en investissement.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Texte brut
# ---------------------------------------------------------------------------

def _build_text(rapports: list[dict], label: str, date_str: str) -> str:
    lignes = [f"{label} – {date_str}", "=" * 60, ""]

    if not rapports:
        lignes.append("Aucun nouveau rapport disponible pour cette période.")
        return "\n".join(lignes)

    compteur = Counter(r.get("societe", "—") for r in rapports)
    lignes.append("RÉCAPITULATIF")
    for societe, nb in sorted(compteur.items()):
        lignes.append(f"  {societe} : {nb} rapport(s)")
    lignes += ["", "-" * 60, ""]

    for r in rapports:
        analyse = r.get("analyse") or {}
        societe = r.get("societe", "—")
        type_r = r.get("type_rapport", "").capitalize()
        annee = r.get("annee", "")
        doc_titre = r.get("doc_titre", "")
        url = r.get("doc_url") or r.get("url", "")
        resume = analyse.get("resume") or r.get("resume", "Résumé non disponible.")
        recommandation = analyse.get("recommandation") or r.get("recommandation") or {}

        decision = (recommandation.get("decision") or "").upper()
        justification = recommandation.get("justification", "")

        lignes += [
            f"[{societe}] {type_r} {annee}",
            f"  {doc_titre}",
            f"  {url}",
            "",
            f"  Résumé : {resume}",
            "",
        ]
        if decision:
            lignes.append(f"  Recommandation : {decision} – {justification}")
            lignes.append("")
        lignes.append("-" * 60)
        lignes.append("")

    lignes.append(
        "Ce rapport est généré automatiquement. "
        "Les analyses ne constituent pas un conseil en investissement."
    )
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def generate(rapports: list[dict], type_rapport: str) -> dict:
    """
    Génère le contenu d'un email de rapport BRVM.

    Args:
        rapports: Liste de dicts (champs de supabase_client + clé optionnelle "analyse")
        type_rapport: "quotidien", "hebdo" ou "mensuel"

    Returns:
        {"subject": str, "body_html": str, "body_text": str}
    """
    label = LABELS.get(type_rapport, "Rapport BRVM")
    date_str = datetime.now().strftime("%d/%m/%Y")
    nb = len(rapports)

    if nb == 0:
        subject = f"[BRVM] {label} – Aucun nouveau rapport ({date_str})"
    elif nb == 1:
        societe = rapports[0].get("societe", "")
        subject = f"[BRVM] {label} – 1 rapport : {societe} ({date_str})"
    else:
        societes_uniques = len({r.get("societe") for r in rapports})
        subject = f"[BRVM] {label} – {nb} rapports / {societes_uniques} sociétés ({date_str})"

    return {
        "subject": subject,
        "body_html": _build_html(rapports, label, date_str),
        "body_text": _build_text(rapports, label, date_str),
    }
