import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

TABLE = "brvm_rapports_societes"

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise EnvironmentError("SUPABASE_URL et SUPABASE_KEY doivent être définis dans .env")
        _client = create_client(url, key)
    return _client


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def doc_exists(url: str) -> bool:
    """Retourne True si un document avec cette URL existe déjà en base."""
    try:
        res = _get_client().table(TABLE).select("id").eq("doc_url", url).limit(1).execute()
        return len(res.data) > 0
    except Exception as e:
        print(f"[ERREUR] doc_exists({url}) : {e}")
        return False


def get_rapports_by_societe(societe: str) -> list[dict]:
    """Retourne tous les rapports d'une société, triés par date décroissante."""
    try:
        res = (
            _get_client()
            .table(TABLE)
            .select("*")
            .eq("societe", societe)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"[ERREUR] get_rapports_by_societe({societe}) : {e}")
        return []


def get_rapports_recent(jours: int = 30) -> list[dict]:
    """Retourne les rapports insérés dans les N derniers jours."""
    try:
        depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()
        res = (
            _get_client()
            .table(TABLE)
            .select("*")
            .gte("created_at", depuis)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"[ERREUR] get_rapports_recent(jours={jours}) : {e}")
        return []


def get_all_rapports() -> list[dict]:
    """Retourne tous les rapports, triés par date décroissante."""
    try:
        res = (
            _get_client()
            .table(TABLE)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"[ERREUR] get_all_rapports() : {e}")
        return []


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------

def insert_rapport(data: dict) -> dict | None:
    """
    Insère un rapport en base. Retourne la ligne insérée ou None.

    Champs attendus dans data :
        societe, annee, type_rapport, doc_titre, doc_url,
        resume, points_cles, indicateurs, recommandation,
        risques, perspectives
    """
    try:
        res = _get_client().table(TABLE).insert(data).execute()
        if res.data:
            print(f"[OK] Rapport inséré : {data.get('societe')} – {data.get('doc_titre')}")
            return res.data[0]
        print(f"[WARN] insert_rapport : réponse vide pour {data.get('doc_url')}")
        return None
    except Exception as e:
        print(f"[ERREUR] insert_rapport({data.get('doc_url')}) : {e}")
        return None


def mark_sent(ids: list[int | str]) -> bool:
    """Met envoye_email=True pour les IDs donnés. Retourne True si succès."""
    if not ids:
        return True
    try:
        _get_client().table(TABLE).update({"envoye_email": True}).in_("id", ids).execute()
        print(f"[OK] {len(ids)} rapport(s) marqué(s) comme envoyés")
        return True
    except Exception as e:
        print(f"[ERREUR] mark_sent({ids}) : {e}")
        return False
