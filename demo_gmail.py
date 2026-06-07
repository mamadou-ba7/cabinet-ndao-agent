#!/usr/bin/env python3
"""
DÉMO Gmail (lecture seule) — Cabinet NDAO
Lit tes vrais emails non lus et AFFICHE comment l'agent les classerait
+ la réponse qu'il rédigerait — SANS rien créer/modifier dans Gmail.

Aucun brouillon, aucun label, rien marqué comme lu. 100% non-destructif.

Lancer :  python3 demo_gmail.py
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()

from gmail_client import get_gmail_service, get_unread_emails
from email_agent import analyser_email

MAX = int(os.getenv("DEMO_MAX", "5"))


def analyser_resilient(email):
    """Analyse avec gestion de la limite gratuite Groq (réessai une fois)."""
    try:
        return analyser_email(email, sauvegarder_supabase=False)
    except Exception as e:
        msg = str(e)
        if "rate_limit" in msg or "429" in msg or "413" in msg:
            print("⏳ Limite gratuite atteinte — pause 30s puis nouvel essai...")
            time.sleep(30)
            try:
                return analyser_email(email, sauvegarder_supabase=False)
            except Exception as e2:
                return {"erreur": f"ignoré (limite/volume) : {str(e2)[:80]}"}
        return {"erreur": f"{msg[:100]}"}


def main():
    print("=" * 60)
    print("   DÉMO GMAIL (LECTURE SEULE) — AGENT CABINET NDAO")
    print("   Rien ne sera modifié dans ta boîte.")
    print("=" * 60)

    print("\n🔌 Connexion à Gmail (autorise dans le navigateur si demandé)...")
    service = get_gmail_service()
    print("✅ Connecté.\n")

    emails = get_unread_emails(service, max_results=MAX, label="INBOX")
    if not emails:
        print("✨ Aucun email non lu dans ta boîte.")
        return

    print(f"📧 {len(emails)} email(s) non lu(s) analysé(s) :\n")

    for i, email in enumerate(emails, 1):
        print("─" * 60)
        print(f"[{i}/{len(emails)}] De    : {email['from']}")
        print(f"         Objet : {email['subject']}")
        print("🤖 Analyse...\n")

        resultat = analyser_resilient(email)
        if "erreur" in resultat:
            print(f"⏭️  {resultat['erreur']}\n")
            time.sleep(2)
            continue

        c = resultat["classification"]
        print(f"📂 Catégorie  : {c.get('categorie')}")
        print(f"🚨 Urgence    : {c.get('niveau_urgence')}")
        print(f"📝 Résumé     : {c.get('resume')}")
        if c.get("mots_cles_urgence_detectes"):
            print(f"🔑 Mots-clés  : {', '.join(c['mots_cles_urgence_detectes'])}")
        print(f"➡️  Action     : {resultat['action']}  (DÉMO : non appliqué)")

        if resultat.get("reponse"):
            print("\n✍️  Réponse qui SERAIT proposée en brouillon :")
            print("┄" * 40)
            print(resultat["reponse"]["corps_email"])
            print("┄" * 40)
        print()
        time.sleep(5)  # espace les appels pour rester sous la limite gratuite

    print("=" * 60)
    print("✅ Démo terminée — ta boîte Gmail n'a PAS été modifiée.")
    print("=" * 60)


if __name__ == "__main__":
    main()
