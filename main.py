#!/usr/bin/env python3
"""
Agent Email — Cabinet Étude C.A. NDAO
Maître Cheikh Ahmed Tidiane NDAO | Dakar, Sénégal
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from gmail_client import (
    get_gmail_service, get_unread_emails,
    create_draft, send_email, mark_as_read, add_label
)
from email_agent import analyser_email

REPONSE_MODE = os.getenv("REPONSE_MODE", "draft")
GMAIL_LABEL = os.getenv("GMAIL_LABEL", "INBOX")


def sep():
    print("\n" + "─" * 60 + "\n")


def afficher_alerte_urgence(email: dict, classification: dict):
    print("\n" + "=" * 60)
    print("🔴  URGENCE — À TRAITER PAR MAÎTRE NDAO IMMÉDIATEMENT")
    print("=" * 60)
    print(f"De      : {email['from']}")
    print(f"Objet   : {email['subject']}")
    print(f"Date    : {email['date']}")
    mots = classification.get("mots_cles_urgence_detectes", [])
    if mots:
        print(f"Mots-clés détectés : {', '.join(mots)}")
    note = classification.get("note_pour_avocat", "")
    if note:
        print(f"Note    : {note}")
    print("=" * 60 + "\n")


def traiter_emails(max_emails: int = 10, marquer_lu: bool = False):
    print("🔌 Connexion à Gmail...")
    service = get_gmail_service()
    print("✅ Connecté.\n")

    print(f"📬 Récupération des emails non lus ({GMAIL_LABEL})...")
    emails = get_unread_emails(service, max_results=max_emails, label=GMAIL_LABEL)

    if not emails:
        print("✨ Aucun email non lu.")
        return

    print(f"📧 {len(emails)} email(s) à traiter.\n")
    sep()

    urgences = []

    for i, email in enumerate(emails, 1):
        print(f"[{i}/{len(emails)}] De    : {email['from']}")
        print(f"         Objet : {email['subject']}")
        print(f"         Date  : {email['date']}")
        print()
        print("🤖 Analyse en cours...")

        resultat = analyser_email(email)
        classification = resultat.get("classification", {})
        reponse = resultat.get("reponse")
        action = resultat.get("action", "")

        categorie = classification.get("categorie", "?")
        niveau = classification.get("niveau_urgence", "?")
        icone = {
            "CRITIQUE": "🔴",
            "HAUTE": "🟠",
            "NORMALE": "🟡",
            "BASSE": "🟢",
        }.get(niveau, "⚪")

        print(f"📂 Catégorie  : {categorie}")
        print(f"{icone} Urgence    : {niveau}")
        print(f"📝 Résumé     : {classification.get('resume', '')}")

        # Note interne pour l'avocat
        note = classification.get("note_pour_avocat", "")
        if note:
            print(f"📌 Note avocat : {note}")

        # Collecte des urgences pour récap final
        if categorie == "URGENCE":
            urgences.append(email)
            afficher_alerte_urgence(email, classification)

        # Label Gmail
        label_gmail = classification.get("label_gmail")
        if label_gmail:
            try:
                add_label(service, email["id"], label_gmail)
                print(f"🏷️  Label      : {label_gmail}")
            except Exception as e:
                print(f"⚠️  Label échoué : {e}")

        # Brouillon ou envoi
        if reponse:
            print()
            print("✍️  RÉPONSE RÉDIGÉE :")
            print("─" * 40)
            print(reponse["corps_email"])
            print("─" * 40)
            try:
                if REPONSE_MODE == "auto":
                    sid = send_email(
                        service,
                        to=email["from"],
                        subject=email["subject"],
                        body_text=reponse["corps_email"],
                        thread_id=email["thread_id"],
                    )
                    print(f"\n📤 Envoyé automatiquement (ID: {sid})")
                else:
                    did = create_draft(
                        service,
                        to=email["from"],
                        subject=email["subject"],
                        body_text=reponse["corps_email"],
                        thread_id=email["thread_id"],
                    )
                    print(f"\n💾 Brouillon créé dans Gmail (ID: {did})")
                    print("   → À vérifier et envoyer depuis Gmail.")
            except Exception as e:
                print(f"\n❌ Erreur : {e}")
        else:
            print(f"\n⏭️  Action : {action}")

        if marquer_lu:
            mark_as_read(service, email["id"])
            print("✅ Marqué comme lu.")

        sep()

    # Récapitulatif urgences
    if urgences:
        print("\n" + "=" * 60)
        print(f"⚠️  {len(urgences)} URGENCE(S) DÉTECTÉE(S) — ACTION REQUISE")
        for u in urgences:
            print(f"   → {u['subject']} | {u['from']}")
        print("=" * 60 + "\n")

    print("🎉 Traitement terminé.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Email — Cabinet NDAO")
    parser.add_argument("--max", type=int, default=10, help="Nombre max d'emails à traiter")
    parser.add_argument("--marquer-lu", action="store_true", help="Marquer les emails traités comme lus")
    parser.add_argument("--mode", choices=["draft", "auto"], help="Override du mode d'envoi")
    args = parser.parse_args()

    if args.mode:
        os.environ["REPONSE_MODE"] = args.mode
        global REPONSE_MODE
        REPONSE_MODE = args.mode

    print("=" * 60)
    print("   AGENT EMAIL — CABINET ÉTUDE C.A. NDAO")
    print("   Maître Cheikh Ahmed Tidiane NDAO | Dakar")
    print(f"   Mode : {'Brouillons (validation avocat)' if REPONSE_MODE == 'draft' else '⚠️  Envoi automatique'}")
    print("=" * 60)
    print()

    traiter_emails(max_emails=args.max, marquer_lu=args.marquer_lu)


if __name__ == "__main__":
    main()
