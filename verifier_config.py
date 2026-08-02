#!/usr/bin/env python3
"""Vérifie que l'agent email du cabinet est correctement configuré.
Usage : python3 verifier_config.py
"""
import json
import os
import urllib.request

from dotenv import load_dotenv

load_dotenv()

ok = 0
total = 0


def verif(libelle: str, reussite: bool, aide: str = "") -> None:
    global ok, total
    total += 1
    if reussite:
        ok += 1
        print(f"✅ {libelle}")
    else:
        print(f"❌ {libelle}" + (f"\n   → {aide}" if aide else ""))


def est_placeholder(v: str) -> bool:
    return not v or "COLLE" in v or "VOTRE_" in v


print("── Vérification de l'agent email Cabinet NDAO ──\n")

# 1. Fichiers d'identification Gmail
verif("credentials.json présent", os.path.exists("credentials.json"),
      "Place ton fichier credentials.json (Google Cloud Console) à la racine du projet")

token_ok = os.path.exists("token.json")
verif("token.json présent (connexion Gmail déjà faite)", token_ok,
      "Lance 'python3 demo_gmail.py' une première fois pour te connecter à Gmail")

if token_ok:
    try:
        with open("token.json") as f:
            token = json.load(f)
        a_refresh = bool(token.get("refresh_token"))
        verif("Jeton Gmail rechargeable (refresh_token présent)", a_refresh,
              "Reconnecte-toi : supprime token.json puis relance 'python3 demo_gmail.py'")
    except Exception:
        verif("token.json lisible", False, "Le fichier token.json est corrompu — supprime-le et reconnecte-toi")

# 2. Fournisseur IA
ai_key = os.getenv("AI_API_KEY", "")
ai_base = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
ai_model = os.getenv("AI_MODEL", "")
verif("Clé IA renseignée (AI_API_KEY)", not est_placeholder(ai_key), "Ajoute AI_API_KEY dans le fichier .env")

if not est_placeholder(ai_key):
    try:
        req = urllib.request.Request(
            ai_base.rstrip("/") + "/chat/completions",
            data=json.dumps({
                "model": ai_model,
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "ok"}],
            }).encode(),
            headers={"Authorization": f"Bearer {ai_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            verif("Clé IA fonctionnelle", resp.status == 200, f"Réponse {resp.status} du fournisseur IA")
    except Exception as e:
        verif("Clé IA fonctionnelle", False, f"Fournisseur IA injoignable : {e}")

# 3. Supabase (tableau de bord)
sb_url = os.getenv("SUPABASE_URL", "")
sb_key = os.getenv("SUPABASE_SERVICE_KEY", "")
verif("SUPABASE_URL renseignée", not est_placeholder(sb_url),
      "Ajoute SUPABASE_URL dans .env (même valeur que NEXT_PUBLIC_SUPABASE_URL du tableau de bord)")
verif("SUPABASE_SERVICE_KEY renseignée", not est_placeholder(sb_key),
      "Ajoute SUPABASE_SERVICE_KEY dans .env (clé secrète Supabase — Settings → API Keys)")

if not est_placeholder(sb_url) and not est_placeholder(sb_key):
    try:
        req = urllib.request.Request(
            sb_url.rstrip("/") + "/rest/v1/settings?select=cle&limit=1",
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            verif("Connexion à la base du tableau de bord", resp.status == 200,
                  "Vérifie SUPABASE_URL / SUPABASE_SERVICE_KEY")
    except Exception as e:
        verif("Connexion à la base du tableau de bord", False, f"Supabase injoignable : {e}")
else:
    print("ℹ️  Sans Supabase, l'agent classe et répond aux emails mais rien n'apparaît dans le tableau de bord.")

# 4. Mode de réponse
mode = os.getenv("REPONSE_MODE", "draft")
verif("Mode de réponse sûr (brouillon, jamais d'envoi auto)", mode == "draft",
      "REPONSE_MODE devrait rester 'draft' tant que l'avocat n'a pas validé le fonctionnement")

print(f"\n{ok}/{total} vérifications réussies.")
if ok < total:
    print("→ Corrige les points ❌ ci-dessus, puis relance ce script.")
    raise SystemExit(1)
else:
    print("→ Tout est prêt ✅")
