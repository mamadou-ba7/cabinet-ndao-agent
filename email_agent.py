import os
import json
from datetime import datetime, timedelta
from groq import Groq

client = Groq()  # lit la clé depuis la variable d'environnement GROQ_API_KEY
MODELE = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SIGNATURE = (
    "\n\nVotre bien dévoué,\n\n"
    "Cheikh Ahmed Tidiane NDAO\n"
    "Avocat à la cour | Cabinet d'Avocat\n"
    "M: 775692867\n"
    "P: 338225579\n"
    "E: cheikh.ndao@cabinetndao.com\n"
    "A: 4, Blvd Djily Mbaye x Fadiga DAKAR"
)

# Mots-clés déclenchant une alerte urgence — aucune réponse automatique
MOTS_CLES_URGENCE = [
    "urgent", "urgence", "urgente",
    "tribunal", "audience",
    "police", "gendarmerie", "garde à vue",
    "convocation", "convoqué",
    "délai", "prescription",
    "arrêté", "arrestation",
    "référé", "signification",
    "saisie", "contrainte",
]

# Indices d'expéditeur automatique / notification de service → ne JAMAIS répondre.
# Un humain qui écrit au cabinet n'utilise pas ces adresses.
EXPEDITEURS_AUTOMATIQUES = [
    "no-reply", "noreply", "no_reply", "ne-pas-repondre", "nepasrepondre",
    "donotreply", "do-not-reply",
    "notifications@", "notification@", "notify@",
    "mailer-daemon", "postmaster@", "bounce", "bounces@",
    "newsletter", "news@", "info@", "support@", "hello@", "team@",
    "billing@", "invoice@", "receipts@", "receipt@",
    "updates@", "update@", "alerts@", "alert@", "marketing@",
    "account@", "accounts@", "noreply.", "automated",
]


def _est_expediteur_automatique(expediteur: str) -> bool:
    """True si l'email vient d'un robot/service (aucune réponse à rédiger)."""
    e = (expediteur or "").lower()
    return any(indice in e for indice in EXPEDITEURS_AUTOMATIQUES)

SYSTEM_PROMPT = """Tu es l'assistant virtuel du Cabinet Étude C.A. NDAO — Maître Cheikh Ahmed Tidiane NDAO, Avocat à la Cour à Dakar, Sénégal. Spécialités : droit des affaires, droit des sociétés, droit pénal des affaires.

━━━ IDENTITÉ ━━━
Langue : français uniquement.
Ton : formel, professionnel, respectueux. Vouvoiement systématique.

━━━ RÈGLES ABSOLUES ━━━
❌ Jamais de conseil ou d'analyse juridique
❌ Jamais de promesse de résultat
❌ Jamais confirmation qu'une personne est cliente
❌ Jamais divulgation d'information sur un dossier
❌ Jamais confirmation de rendez-vous (proposer seulement)
❌ Jamais envoi de document
❌ Jamais réponse si mots-clés urgence présents (tribunal, police, convocation, délai, garde à vue…)

Si doute → accuser réception uniquement, sans entrer dans le fond.

━━━ CATÉGORIES DE TRAITEMENT ━━━
DEMANDE_SIMPLE    : réponse automatique autorisée (accusé de réception basique)
RENDEZ_VOUS       : proposer des créneaux uniquement, sans confirmer
DEMANDE_SENSIBLE  : transmettre à l'avocat, ne pas répondre
URGENCE           : alerte immédiate, AUCUNE réponse automatique
SPAM              : ignorer — inclut TOUTES les notifications automatiques, newsletters,
                    publicités, factures de services en ligne, e-mails d'expéditeurs
                    « no-reply / notifications / support / billing ». On ne répond JAMAIS
                    à un robot ou à un service. Seul un humain qui sollicite réellement
                    le cabinet mérite une réponse.

━━━ DISPONIBILITÉS RDV ━━━
Jours       : Lundi à Jeudi
Horaires    : 16h00 – 17h30
Standard    : 30 minutes | Première consultation : 45 minutes
Délai inter : 10 minutes
Indisponible: 13h00 – 15h30 et jours d'audience

━━━ SIGNATURE OBLIGATOIRE (toutes les réponses) ━━━
Votre bien dévoué,

Cheikh Ahmed Tidiane NDAO
Avocat à la cour | Cabinet d'Avocat
M: 775692867
P: 338225579
E: cheikh.ndao@cabinetndao.com
A: 4, Blvd Djily Mbaye x Fadiga DAKAR
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "classifier_email",
            "description": "Analyse et classifie l'email entrant selon les règles strictes du Cabinet NDAO",
            "parameters": {
                "type": "object",
                "properties": {
                    "categorie": {
                        "type": "string",
                        "enum": ["DEMANDE_SIMPLE", "RENDEZ_VOUS", "DEMANDE_SENSIBLE", "URGENCE", "SPAM"],
                        "description": "Catégorie de traitement de l'email",
                    },
                    "niveau_urgence": {
                        "type": "string",
                        "enum": ["CRITIQUE", "HAUTE", "NORMALE", "BASSE"],
                        "description": "Niveau d'urgence détecté",
                    },
                    "mots_cles_urgence_detectes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Mots-clés d'urgence trouvés dans le message (liste vide si aucun)",
                    },
                    "resume": {
                        "type": "string",
                        "description": "Résumé en 1-2 phrases de l'objet du message",
                    },
                    "peut_repondre_automatiquement": {
                        "type": "boolean",
                        "description": "True uniquement pour DEMANDE_SIMPLE ou RENDEZ_VOUS sans mot-clé urgence",
                    },
                    "label_gmail": {
                        "type": "string",
                        "description": "Label Gmail à appliquer : Cabinet/Nouveau-Client | Cabinet/RDV | Cabinet/URGENT | Cabinet/Sensible | Cabinet/Spam",
                    },
                    "note_pour_avocat": {
                        "type": "string",
                        "description": "Note interne pour Maître NDAO — ce qui nécessite son attention",
                    },
                },
                "required": [
                    "categorie", "niveau_urgence", "mots_cles_urgence_detectes",
                    "resume", "peut_repondre_automatiquement", "label_gmail", "note_pour_avocat",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rediger_reponse",
            "description": "Rédige la réponse email appropriée selon la catégorie et les règles du cabinet",
            "parameters": {
                "type": "object",
                "properties": {
                    "corps_email": {
                        "type": "string",
                        "description": "Corps complet de l'email incluant la signature officielle du cabinet",
                    },
                },
                "required": ["corps_email"],
            },
        },
    },
]


def _proposer_creneaux() -> str:
    """Génère 3 jours de créneaux disponibles (Lundi–Jeudi, 16h00–17h30)."""
    creneaux = []
    today = datetime.now()
    jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    horaires = [("16h00", "16h45"), ("16h50", "17h35")]
    jours_proposes = 0
    delta = 1

    while jours_proposes < 3:
        candidate = today + timedelta(days=delta)
        if candidate.weekday() <= 3:  # Lundi(0) à Jeudi(3)
            jour = f"{jours_fr[candidate.weekday()]} {candidate.strftime('%d/%m/%Y')}"
            for debut, fin in horaires:
                creneaux.append(f"  • {jour} de {debut} à {fin}")
            jours_proposes += 1
        delta += 1

    return "\n".join(creneaux)


def analyser_email(email: dict, sauvegarder_supabase: bool = True) -> dict:
    """Pipeline complet : classification → sécurité → rédaction → Supabase si activé."""
    try:
        from supabase_client import sauvegarder_email, sauvegarder_brouillon, marquer_email_urgent
        _supabase_ok = sauvegarder_supabase
    except Exception:
        _supabase_ok = False

    # Tronque le corps : les newsletters/pubs sont énormes et dépassent
    # les limites de tokens. Un vrai email client tient largement dans 2500 caractères.
    MAX_CORPS = 2500
    corps = (email["body"] or email["snippet"] or "")
    if len(corps) > MAX_CORPS:
        corps = corps[:MAX_CORPS] + "\n[…message tronqué…]"

    email_content = (
        f"EXPÉDITEUR : {email['from']}\n"
        f"OBJET : {email['subject']}\n"
        f"DATE : {email['date']}\n"
        f"---\n"
        f"{corps}"
    )

    # Détection locale des mots-clés urgence (filet de sécurité côté code)
    contenu_lower = email_content.lower()
    urgence_detectee = [m for m in MOTS_CLES_URGENCE if m in contenu_lower]

    # ── Étape 1 : Classification par l'IA ────────────────────────────────────
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Analyse et classifie cet email reçu au cabinet :\n\n{email_content}\n\n"
                f"Mots-clés urgence détectés par le système : {urgence_detectee or 'aucun'}"
            ),
        },
    ]

    response = client.chat.completions.create(
        model=MODELE,
        max_tokens=1024,
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": "classifier_email"}},
        messages=messages,
    )

    message1 = response.choices[0].message
    classification = None
    tool_use_id = None
    for tc in (message1.tool_calls or []):
        if tc.function.name == "classifier_email":
            classification = json.loads(tc.function.arguments)
            tool_use_id = tc.id
            break

    if not classification:
        return {"erreur": "Impossible de classifier l'email"}

    # Sécurité : forcer URGENCE si mots-clés détectés localement
    if urgence_detectee:
        classification["categorie"] = "URGENCE"
        classification["niveau_urgence"] = "CRITIQUE"
        classification["peut_repondre_automatiquement"] = False
        classification["mots_cles_urgence_detectes"] = urgence_detectee
        if not classification.get("note_pour_avocat"):
            classification["note_pour_avocat"] = (
                f"⚠️ Mots-clés urgence détectés : {', '.join(urgence_detectee)}"
            )

    # Sécurité : expéditeur automatique (no-reply, notifications, newsletters…)
    # → SPAM, jamais de réponse. On ne répond pas à un robot.
    if _est_expediteur_automatique(email.get("from", "")) and not urgence_detectee:
        classification["categorie"] = "SPAM"
        classification["peut_repondre_automatiquement"] = False
        classification["label_gmail"] = "Cabinet/Spam"
        if not classification.get("note_pour_avocat"):
            classification["note_pour_avocat"] = "Expéditeur automatique (notification/service)"

    categorie = classification["categorie"]

    # Sauvegarde Supabase (email + classification)
    email_uuid = ""
    if _supabase_ok:
        try:
            email_uuid = sauvegarder_email(email, classification)
            if categorie == "URGENCE":
                marquer_email_urgent(email_uuid)
        except Exception as e:
            print(f"⚠️  Supabase non disponible : {e}")

    # ── Décision de traitement ────────────────────────────────────────────────
    if categorie == "URGENCE":
        return {
            "classification": classification,
            "reponse": None,
            "email_uuid": email_uuid,
            "action": "🔴 ALERTE — transmis à Maître NDAO immédiatement",
        }

    if categorie == "DEMANDE_SENSIBLE":
        return {
            "classification": classification,
            "reponse": None,
            "email_uuid": email_uuid,
            "action": "🟡 Transmis à Maître NDAO pour traitement",
        }

    if categorie == "SPAM":
        return {
            "classification": classification,
            "reponse": None,
            "email_uuid": email_uuid,
            "action": "⏭️ Ignoré (spam)",
        }

    if not classification.get("peut_repondre_automatiquement"):
        return {
            "classification": classification,
            "reponse": None,
            "email_uuid": email_uuid,
            "action": "🟡 Transmis à Maître NDAO (validation requise)",
        }

    # ── Étape 2 : Rédaction de la réponse ────────────────────────────────────
    creneaux_rdv = _proposer_creneaux() if categorie == "RENDEZ_VOUS" else ""
    contexte_supplementaire = (
        f"\n\nCréneaux disponibles à proposer dans la réponse :\n{creneaux_rdv}"
        if creneaux_rdv else ""
    )

    messages.append({
        "role": "assistant",
        "content": message1.content or "",
        "tool_calls": [
            {
                "id": tool_use_id,
                "type": "function",
                "function": {
                    "name": "classifier_email",
                    "arguments": json.dumps(classification, ensure_ascii=False),
                },
            }
        ],
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tool_use_id,
        "content": json.dumps(classification, ensure_ascii=False),
    })
    messages.append({
        "role": "user",
        "content": (
            f"Rédige la réponse pour la catégorie {categorie}.{contexte_supplementaire}\n\n"
            "EXIGENCES DE PERSONNALISATION (très important) :\n"
            "1. Commence par t'adresser à la personne par son nom si tu le connais "
            "(sinon « Madame, Monsieur, »).\n"
            "2. Reformule en UNE phrase ce que la personne demande précisément, "
            "pour montrer que son message a été lu et compris.\n"
            "3. Réponds de façon adaptée à SA demande concrète (pas un texte générique "
            "réutilisable pour n'importe quel email).\n"
            "4. Termine par une formule de politesse + la signature officielle complète.\n\n"
            "Rappels stricts : vouvoiement obligatoire | aucun conseil ni analyse juridique | "
            "ne jamais promettre de résultat | ne jamais confirmer qu'une personne est cliente."
        ),
    })

    response2 = client.chat.completions.create(
        model=MODELE,
        max_tokens=2048,
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": "rediger_reponse"}},
        messages=messages,
    )

    reponse_redigee = None
    for tc in (response2.choices[0].message.tool_calls or []):
        if tc.function.name == "rediger_reponse":
            reponse_redigee = json.loads(tc.function.arguments)
            break

    # Sauvegarde du brouillon dans Supabase
    if _supabase_ok and reponse_redigee and email_uuid:
        try:
            sauvegarder_brouillon(email_uuid, reponse_redigee["corps_email"])
        except Exception as e:
            print(f"⚠️  Supabase brouillon : {e}")

    return {
        "classification": classification,
        "reponse": reponse_redigee,
        "email_uuid": email_uuid,
        "action": "✅ Brouillon créé" if reponse_redigee else "❌ Erreur rédaction",
    }
