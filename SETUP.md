# Setup — Agent Email | Cabinet Étude C.A. NDAO

## Étape 1 — Clé API Anthropic

1. Aller sur https://console.anthropic.com
2. Se connecter → "API Keys" → "Create Key"
3. Copier la clé (commence par `sk-ant-...`)

## Étape 2 — Accès Gmail de Maître NDAO (OAuth2)

1. Aller sur https://console.cloud.google.com
2. Créer un projet : "Cabinet NDAO Agent"
3. Activer l'API Gmail :
   - Menu → "APIs & Services" → "Library"
   - Chercher "Gmail API" → Activer
4. Créer les credentials :
   - "APIs & Services" → "Credentials"
   - "Create Credentials" → "OAuth 2.0 Client IDs"
   - Application type : **Desktop app**
   - Télécharger le JSON → le renommer **`credentials.json`**
   - Le placer dans ce dossier (`cabinet-avocat-agent/`)
5. Écran de consentement :
   - "OAuth consent screen" → External
   - Remplir avec les infos du cabinet
   - Ajouter `cheikh.ndao@cabinetndao.com` comme "Test user"

## Étape 3 — Fichier de configuration

```bash
cp .env.example .env
```

Éditer `.env` :

```
ANTHROPIC_API_KEY=sk-ant-VOTRE_CLE_ICI
GMAIL_LABEL=INBOX
REPONSE_MODE=draft
```

## Étape 4 — Premier lancement

```bash
python3 main.py
```

Une fenêtre de navigateur s'ouvre pour autoriser l'accès au compte Gmail du cabinet.
Après autorisation, un fichier `token.json` est créé automatiquement.

## Utilisation quotidienne

```bash
# Traiter les emails non lus (crée des brouillons dans Gmail)
python3 main.py

# Traiter 20 emails
python3 main.py --max 20

# Traiter et marquer comme lus
python3 main.py --marquer-lu
```

## Ce que fait l'agent sur chaque email

| Catégorie | Action |
|---|---|
| **URGENCE** (tribunal, police, convocation…) | 🔴 Alerte — aucune réponse automatique |
| **DEMANDE_SENSIBLE** (dossier, juridique…) | 🟡 Transmis à Maître NDAO |
| **RENDEZ_VOUS** | 💾 Brouillon avec créneaux disponibles |
| **DEMANDE_SIMPLE** | 💾 Brouillon d'accusé de réception |
| **SPAM** | ⏭️ Ignoré |

## Sécurité importante

- `credentials.json` et `token.json` : **ne jamais partager, ne jamais envoyer par email**
- `REPONSE_MODE=draft` : Maître NDAO **valide toujours** avant envoi
- L'agent **ne donne jamais de conseil juridique**
- Les urgences (tribunal, police, convocation, délai…) ne reçoivent **aucune réponse automatique**

## Automatisation (toutes les heures, Mac)

Ouvrir Terminal et taper `crontab -e`, puis ajouter :

```
0 * * * * cd /Users/macbookairm2/Desktop/dossier\ sans\ titre\ 3/cabinet-avocat-agent && python3 main.py --marquer-lu >> agent.log 2>&1
```
