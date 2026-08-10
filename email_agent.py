import os
import re
import html
import json
from openai import OpenAI
from parametres_agent import charger_parametres, liste, construire_system_prompt, proposer_creneaux

# ── Fournisseur d'IA interchangeable (compatible OpenAI) ──────────────────────
# Par défaut : Gemini GRATUIT. Pour passer à Claude plus tard, il suffit de
# changer AI_BASE_URL / AI_API_KEY / AI_MODEL dans le .env — aucun code à toucher.
#   Gemini  : https://generativelanguage.googleapis.com/v1beta/openai/  | gemini-2.0-flash
#   Claude  : https://api.anthropic.com/v1/                             | claude-sonnet-4-6
#   Groq    : https://api.groq.com/openai/v1                            | llama-3.3-70b-versatile
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
MODELE = os.getenv("AI_MODEL", "gemini-2.0-flash")

client = OpenAI(base_url=AI_BASE_URL, api_key=AI_API_KEY)


def _est_expediteur_automatique(expediteur: str, indices: list[str]) -> bool:
    """True si l'email vient d'un robot/service (aucune réponse à rédiger)."""
    e = (expediteur or "").lower()
    return any(indice in e for indice in indices)

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
                        "description": (
                            "Corps complet de l'email incluant la signature officielle du cabinet. "
                            "Texte brut uniquement : de vrais retours à la ligne, jamais de balises HTML "
                            "(pas de <br>, <p>, etc.)."
                        ),
                    },
                },
                "required": ["corps_email"],
            },
        },
    },
]


def analyser_email(email: dict, sauvegarder_supabase: bool = True) -> dict:
    """Pipeline complet : classification → sécurité → rédaction → Supabase si activé."""
    try:
        from supabase_client import sauvegarder_email, sauvegarder_brouillon, marquer_email_urgent
        _supabase_ok = sauvegarder_supabase
    except Exception:
        _supabase_ok = False

    valeurs = charger_parametres()
    system_prompt = construire_system_prompt(valeurs)
    mots_cles_urgence = liste(valeurs, "mots_cles_urgence")
    expediteurs_automatiques = liste(valeurs, "expediteurs_automatiques")

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
    urgence_detectee = [m for m in mots_cles_urgence if m in contenu_lower]

    # ── Étape 1 : Classification par l'IA ────────────────────────────────────
    messages = [
        {"role": "system", "content": system_prompt},
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
    if _est_expediteur_automatique(email.get("from", ""), expediteurs_automatiques) and not urgence_detectee:
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
    creneaux_rdv = proposer_creneaux(valeurs) if categorie == "RENDEZ_VOUS" else ""
    # Seule exception au format court : une demande de RDV, où l'on propose les
    # créneaux configurés dans les Réglages (sans jamais confirmer le rendez-vous).
    contexte_supplementaire = (
        "\n\nEXCEPTION pour cette demande de rendez-vous : après la phrase d'accusé "
        "de réception, propose ces créneaux tels quels, sans confirmer le rendez-vous "
        f"(« sous réserve de confirmation »). N'ajoute rien d'autre.\n{creneaux_rdv}"
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
            f"Rédige l'accusé de réception pour la catégorie {categorie}."
            f"{contexte_supplementaire}\n\n"
            "Applique strictement la structure imposée. Choisis la formule d'appel "
            "d'après l'expéditeur (client ou confrère).\n\n"
            "Rappels : n'écris RIEN sur le contenu de sa demande, ne la résume pas et "
            "ne la reformule pas | vouvoiement | 2 à 4 lignes | termine par la formule "
            "de politesse et la signature officielle complète."
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

    # Filet de sécurité : certains modèles ignorent la consigne "texte brut" et
    # renvoient des balises HTML (<br>…) ou des entités (&#39;). Le brouillon Gmail
    # part en text/plain — sans nettoyage, le client reçoit le balisage tel quel.
    if reponse_redigee and reponse_redigee.get("corps_email"):
        corps = reponse_redigee["corps_email"]
        corps = re.sub(r"<br\s*/?>", "\n", corps, flags=re.IGNORECASE)
        corps = re.sub(r"</?p\s*/?>", "\n", corps, flags=re.IGNORECASE)
        corps = re.sub(r"<[^>]+>", "", corps)
        corps = html.unescape(corps)
        corps = re.sub(r"\n{3,}", "\n\n", corps)
        reponse_redigee["corps_email"] = corps.strip()

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
