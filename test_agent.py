#!/usr/bin/env python3
"""
Test HORS-LIGNE de l'agent — Cabinet NDAO
Envoie des faux emails à l'agent IA pour valider la classification
et la rédaction SANS Gmail ni Supabase.

Lancer :  python3 test_agent.py
Prérequis : ANTHROPIC_API_KEY dans le fichier .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("GROQ_API_KEY") or "VOTRE_CLE" in os.getenv("GROQ_API_KEY", ""):
    print("❌ Ajoute ta vraie clé GROQ_API_KEY dans le fichier .env d'abord.")
    print("   (obtenir GRATUITEMENT sur https://console.groq.com/keys)")
    raise SystemExit(1)

from email_agent import analyser_email

# ── Faux emails de test (un par catégorie attendue) ──────────────────────────
EMAILS_TEST = [
    {
        "id": "test-1",
        "thread_id": "t1",
        "from": "Aminata Diop <aminata.diop@example.com>",
        "to": "cheikh.ndao@cabinetndao.com",
        "subject": "Horaires d'ouverture du cabinet",
        "date": "2026-06-06",
        "snippet": "",
        "body": "Bonjour, pourriez-vous m'indiquer vos horaires d'ouverture et votre adresse ? Merci.",
    },
    {
        "id": "test-2",
        "thread_id": "t2",
        "from": "Moussa Fall <moussa.fall@example.com>",
        "to": "cheikh.ndao@cabinetndao.com",
        "subject": "Demande de rendez-vous",
        "date": "2026-06-06",
        "snippet": "",
        "body": "Bonjour Maître, je souhaiterais prendre rendez-vous pour une première consultation concernant la création de ma société. Quelles sont vos disponibilités ?",
    },
    {
        "id": "test-3",
        "thread_id": "t3",
        "from": "Société SOTRAC <contact@sotrac.sn>",
        "to": "cheikh.ndao@cabinetndao.com",
        "subject": "Litige commercial avec un fournisseur",
        "date": "2026-06-06",
        "snippet": "",
        "body": "Maître, nous avons un différend avec un fournisseur qui n'a pas livré la marchandise payée. Nous aimerions savoir comment vous pourriez nous accompagner.",
    },
    {
        "id": "test-4",
        "thread_id": "t4",
        "from": "Ibrahima Sarr <i.sarr@example.com>",
        "to": "cheikh.ndao@cabinetndao.com",
        "subject": "URGENT - convocation tribunal demain",
        "date": "2026-06-06",
        "snippet": "",
        "body": "Maître, j'ai reçu une convocation du tribunal pour une audience demain matin. Que dois-je faire ? C'est urgent !",
    },
]


def main():
    print("=" * 60)
    print("   TEST HORS-LIGNE — AGENT EMAIL CABINET NDAO")
    print("   (sans Gmail, sans Supabase)")
    print("=" * 60)

    for i, email in enumerate(EMAILS_TEST, 1):
        print("\n" + "─" * 60)
        print(f"[{i}/{len(EMAILS_TEST)}] Objet : {email['subject']}")
        print(f"         De    : {email['from']}")
        print("🤖 Analyse en cours...\n")

        resultat = analyser_email(email, sauvegarder_supabase=False)

        if "erreur" in resultat:
            print(f"❌ {resultat['erreur']}")
            continue

        c = resultat["classification"]
        print(f"📂 Catégorie  : {c.get('categorie')}")
        print(f"🚨 Urgence    : {c.get('niveau_urgence')}")
        print(f"📝 Résumé     : {c.get('resume')}")
        if c.get("mots_cles_urgence_detectes"):
            print(f"🔑 Mots-clés  : {', '.join(c['mots_cles_urgence_detectes'])}")
        print(f"🏷️  Label      : {c.get('label_gmail')}")
        print(f"➡️  Action     : {resultat['action']}")

        if resultat.get("reponse"):
            print("\n✍️  RÉPONSE RÉDIGÉE :")
            print("┄" * 40)
            print(resultat["reponse"]["corps_email"])
            print("┄" * 40)

    print("\n" + "=" * 60)
    print("✅ Test terminé.")
    print("   Vérifie que : l'urgence n'a PAS de réponse auto,")
    print("   le RDV propose des créneaux, et la signature est présente.")
    print("=" * 60)


if __name__ == "__main__":
    main()
