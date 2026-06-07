"""
Client Supabase pour le Cabinet NDAO.
Stocke les emails classifiés et les brouillons pour le dashboard web.
"""
import os
from supabase import create_client, Client

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "Variables manquantes : SUPABASE_URL et SUPABASE_SERVICE_KEY requis dans .env"
            )
        _client = create_client(url, key)
    return _client


def sauvegarder_email(email: dict, classification: dict) -> str:
    """
    Insère ou met à jour un email dans la table `emails`.
    Retourne l'UUID de la ligne Supabase.
    """
    sb = get_supabase()
    payload = {
        "gmail_id": email["id"],
        "thread_id": email.get("thread_id", ""),
        "from_address": email["from"],
        "subject": email["subject"],
        "date": email["date"],
        "snippet": email.get("snippet", ""),
        "body": email.get("body", ""),
        "categorie": classification.get("categorie", ""),
        "niveau_urgence": classification.get("niveau_urgence", ""),
        "resume": classification.get("resume", ""),
        "mots_cles_urgence": classification.get("mots_cles_urgence_detectes", []),
        "note_pour_avocat": classification.get("note_pour_avocat", ""),
        "label_gmail": classification.get("label_gmail", ""),
        "statut": "en_attente",
    }
    result = (
        sb.table("emails")
        .upsert(payload, on_conflict="gmail_id")
        .execute()
    )
    return result.data[0]["id"] if result.data else ""


def sauvegarder_brouillon(email_uuid: str, corps_email: str) -> str:
    """
    Insère un brouillon dans la table `drafts`.
    Retourne l'UUID du brouillon.
    """
    sb = get_supabase()
    result = (
        sb.table("drafts")
        .insert({
            "email_id": email_uuid,
            "corps_email": corps_email,
            "statut": "brouillon",
        })
        .execute()
    )
    return result.data[0]["id"] if result.data else ""


def marquer_email_urgent(email_uuid: str) -> None:
    """Passe le statut de l'email à 'urgent' dans Supabase."""
    get_supabase().table("emails").update({"statut": "urgent"}).eq("id", email_uuid).execute()
