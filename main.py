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
    get_gmail_service, get_unread_emails, get_recent_email_ids, get_email_details,
    create_draft, mark_as_read, add_label
)
from email_agent import analyser_email
from supabase_client import gmail_ids_deja_traites

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

    print(f"📬 Recherche des nouveaux emails ({GMAIL_LABEL}, 3 derniers jours)...")
    ids = get_recent_email_ids(service, max_results=50, label=GMAIL_LABEL)
    deja = gmail_ids_deja_traites(ids)
    nouveaux = [i for i in ids if i not in deja][:max_emails]
    emails = [e for e in (get_email_details(service, i) for i in nouveaux) if e]

    if not emails:
        print("✨ Aucun nouvel email.")
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
            # L'agent ne PEUT PAS envoyer : il ne crée que des brouillons.
            # Un email ne part qu'après relecture et validation explicite de
            # l'avocat, depuis le tableau de bord ou depuis Gmail.
            try:
                did = create_draft(
                    service,
                    to=email["from"],
                    subject=email["subject"],
                    body_text=reponse["corps_email"],
                    thread_id=email["thread_id"],
                )
                print(f"\n💾 Brouillon créé dans Gmail (ID: {did})")
                print("   → À valider depuis le tableau de bord ou Gmail. Aucun envoi automatique.")
            except Exception as e:
                print(f"\n❌ Erreur : {e}")
        else:
            print(f"\n⏭️  Action : {action}")

        # On ne marque comme lu QUE si l'email a bien été classifié : sinon un
        # échec passager de l'IA le ferait disparaître de la boîte sans qu'il
        # soit jamais traité ni visible dans le tableau de bord. Non marqué, il
        # sera repris au prochain passage.
        if marquer_lu:
            if classification:
                mark_as_read(service, email["id"])
                print("✅ Marqué comme lu.")
            else:
                print("↩️  Laissé non lu (classification échouée) — repris au prochain passage.")

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
    args = parser.parse_args()


    print("=" * 60)
    print("   AGENT EMAIL — CABINET ÉTUDE C.A. NDAO")
    print("   Maître Cheikh Ahmed Tidiane NDAO | Dakar")
    print("   Mode : Brouillons uniquement — aucun envoi automatique possible")
    print("=" * 60)
    print()

    traiter_emails(max_emails=args.max, marquer_lu=args.marquer_lu)


if __name__ == "__main__":
    main()
