#!/usr/bin/env python3
"""Étape 1/2 — Génère le lien d'autorisation Google à ouvrir sur n'importe quel PC."""
import warnings
warnings.filterwarnings("ignore")

from google_auth_oauthlib.flow import Flow
from gmail_client import SCOPES, CREDENTIALS_FILE

flow = Flow.from_client_secrets_file(
    CREDENTIALS_FILE, scopes=SCOPES, redirect_uri="http://localhost"
)
url, _ = flow.authorization_url(
    prompt="consent", access_type="offline", include_granted_scopes="true"
)

# Sauvegarde le vérificateur PKCE pour l'étape 2 (auth_finish.py)
with open(".pkce_verifier", "w") as f:
    f.write(flow.code_verifier or "")

print("\n" + "=" * 70)
print("OUVRE CE LIEN dans un navigateur (sur n'importe quel ordinateur) :")
print("=" * 70 + "\n")
print(url)
print("\n" + "=" * 70)
print("Après avoir autorisé, le navigateur essaiera d'aller sur")
print("  http://localhost/?code=XXXXXX...   (la page affichera une ERREUR,")
print("  c'est NORMAL). Copie TOUTE l'URL de la barre d'adresse")
print("  (ou juste la valeur après 'code=') et renvoie-la moi.")
print("=" * 70)
