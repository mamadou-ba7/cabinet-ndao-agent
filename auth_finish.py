#!/usr/bin/env python3
"""Étape 2/2 — Échange le code d'autorisation contre un token et crée token.json.

Usage : python3 auth_finish.py "<URL complète ou code copié>"
"""
import sys
import os
import warnings
warnings.filterwarnings("ignore")
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from urllib.parse import urlparse, parse_qs, unquote
from google_auth_oauthlib.flow import Flow
from gmail_client import SCOPES, CREDENTIALS_FILE, TOKEN_FILE

if len(sys.argv) < 2:
    print("❌ Donne le code ou l'URL : python3 auth_finish.py \"<url-ou-code>\"")
    raise SystemExit(1)

arg = sys.argv[1].strip()

# Extraire le code que l'utilisateur ait collé l'URL complète ou juste le code
if arg.startswith("http"):
    qs = parse_qs(urlparse(arg).query)
    code = qs.get("code", [None])[0]
else:
    code = arg
code = unquote(code) if code else None

if not code:
    print("❌ Code introuvable dans ce que tu as fourni.")
    raise SystemExit(1)

flow = Flow.from_client_secrets_file(
    CREDENTIALS_FILE, scopes=SCOPES, redirect_uri="http://localhost"
)

# Recharge le vérificateur PKCE généré à l'étape 1
flow.autogenerate_code_verifier = False
if os.path.exists(".pkce_verifier"):
    with open(".pkce_verifier") as f:
        flow.code_verifier = f.read().strip() or None

flow.fetch_token(code=code)
creds = flow.credentials

with open(TOKEN_FILE, "w") as f:
    f.write(creds.to_json())

print("✅ token.json créé — autorisation Gmail réussie !")
print("   Tu peux maintenant lancer :  python3 demo_gmail.py")
