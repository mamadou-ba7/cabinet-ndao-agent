"""
Paramètres de l'agent, entièrement configurables par le cabinet depuis le
tableau de bord (table Supabase `settings`) — plus rien n'est figé dans le code.
"""
import re
from datetime import datetime, timedelta

JOURS_FR = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
CLES_JOUR = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
ORDRE_SEMAINE = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

DEFAUTS = {
    "avocat_nom": "Maître Cheikh Ahmed Tidiane NDAO",
    "cabinet_nom": "Cabinet d'Avocat",
    "cabinet_email": "",
    "avocat_telephone_mobile": "",
    "avocat_telephone_fixe": "",
    "cabinet_adresse": "",
    "cabinet_specialites": "droit des affaires, droit des sociétés, droit pénal des affaires",
    "rdv_jours": "lundi,mardi,mercredi,jeudi",
    "rdv_heure_debut": "16:00",
    "rdv_heure_fin": "17:30",
    "rdv_duree": "30",
    "rdv_duree_1ere": "45",
    "rdv_intervalle": "10",
    "rdv_nb_jours_proposes": "3",
    "mots_cles_urgence": (
        "urgent,urgence,urgente,tribunal,audience,police,gendarmerie,garde à vue,"
        "convocation,convoqué,délai,prescription,arrêté,arrestation,référé,"
        "signification,saisie,contrainte"
    ),
    "expediteurs_automatiques": (
        "no-reply,noreply,no_reply,ne-pas-repondre,nepasrepondre,donotreply,do-not-reply,"
        "notifications@,notification@,notify@,mailer-daemon,postmaster@,bounce,bounces@,"
        "newsletter,news@,info@,support@,hello@,team@,billing@,invoice@,receipts@,receipt@,"
        "updates@,update@,alerts@,alert@,marketing@,account@,accounts@,noreply.,automated"
    ),
}

_cache = None


def charger_parametres(forcer: bool = False) -> dict:
    """Charge les paramètres depuis Supabase (avec repli sur les valeurs par
    défaut si une clé est absente/vide ou si Supabase est indisponible).
    Mis en cache pour la durée du run — un seul appel réseau par passage de l'agent."""
    global _cache
    if _cache is not None and not forcer:
        return _cache

    valeurs = dict(DEFAUTS)
    try:
        from supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("settings").select("cle,valeur").execute()
        for row in result.data or []:
            if row.get("valeur"):
                valeurs[row["cle"]] = row["valeur"]
    except Exception as e:
        print(f"⚠️  Paramètres Supabase indisponibles, valeurs par défaut utilisées : {e}")

    _cache = valeurs
    return valeurs


def liste(valeurs: dict, cle: str) -> list[str]:
    return [x.strip().lower() for x in (valeurs.get(cle) or "").split(",") if x.strip()]


def _jours_affichage(valeurs: dict) -> str:
    cles = liste(valeurs, "rdv_jours") or ["lundi", "mardi", "mercredi", "jeudi"]
    mapping = dict(zip(CLES_JOUR, JOURS_FR))
    tries = sorted(set(cles), key=lambda c: ORDRE_SEMAINE.index(c) if c in ORDRE_SEMAINE else 99)
    return ", ".join(mapping[c] for c in tries if c in mapping)


def construire_signature(valeurs: dict) -> str:
    lignes = ["Votre bien dévoué,", "", valeurs["avocat_nom"], f"Avocat à la cour | {valeurs['cabinet_nom']}"]
    if valeurs.get("avocat_telephone_mobile"):
        lignes.append(f"M: {valeurs['avocat_telephone_mobile']}")
    if valeurs.get("avocat_telephone_fixe"):
        lignes.append(f"P: {valeurs['avocat_telephone_fixe']}")
    if valeurs.get("cabinet_email"):
        lignes.append(f"E: {valeurs['cabinet_email']}")
    if valeurs.get("cabinet_adresse"):
        lignes.append(f"A: {valeurs['cabinet_adresse']}")
    return "\n".join(lignes)


# Marqueurs de fin de lettre : tout ce qui suit est une signature (celle du
# cabinet ou une formule inventée par le modèle) et sera remplacé par le bloc officiel.
# \s+ (et non \n) : le modèle renvoie parfois toute la réponse sur une seule
# ligne, séparée par des espaces — le marqueur doit être reconnu dans ce cas aussi,
# sinon une seconde signature était ajoutée en doublon.
_FIN_DE_LETTRE = re.compile(
    r"\s+(Votre bien dévoué|Je vous prie d'agréer|Veuillez agréer|Veuillez croire|"
    r"Bien cordialement|Cordialement|Sincères salutations|Salutations distinguées)",
    re.IGNORECASE,
)


def garantir_signature(texte: str, signature: str) -> str:
    """Le prompt exige la signature, mais un modèle l'omet parfois, en invente une
    autre, ou fait les deux — or un email d'avocat parti sans ses coordonnées est un
    vrai défaut côté client. On coupe à la fin de lettre et on réappose le bloc
    officiel : le résultat est toujours identique, et la fonction est idempotente."""
    m = _FIN_DE_LETTRE.search(texte)
    corps = texte[: m.start()] if m else texte
    return f"{corps.strip()}\n\n{signature}"


def construire_system_prompt(valeurs: dict) -> str:
    heure_debut = valeurs["rdv_heure_debut"].replace(":", "h")
    heure_fin = valeurs["rdv_heure_fin"].replace(":", "h")
    return f"""Tu es l'assistant virtuel du {valeurs['cabinet_nom']} — {valeurs['avocat_nom']}, Avocat à la Cour à Dakar, Sénégal. Spécialités : {valeurs['cabinet_specialites']}.

━━━ IDENTITÉ ━━━
Langue : français uniquement.
Ton : formel, professionnel, respectueux. Vouvoiement systématique.

━━━ RÈGLES ABSOLUES ━━━
❌ Ne JAMAIS résumer, reformuler ni répéter la demande de l'expéditeur. Aucune allusion au contenu de son message.
❌ Jamais de conseil ou d'analyse juridique
❌ Jamais de promesse de résultat
❌ Jamais confirmation qu'une personne est cliente
❌ Jamais divulgation d'information sur un dossier
❌ Jamais confirmation de rendez-vous (proposer seulement)
❌ Jamais envoi de document
❌ Jamais de promesse ferme de délai sans base explicite dans le message reçu
❌ Jamais réponse si mots-clés urgence présents (tribunal, police, convocation, délai, garde à vue…)

Si doute → accuser réception uniquement, sans entrer dans le fond.

━━━ FORMULE D'APPEL (à déduire de l'expéditeur et de sa signature) ━━━
• Client, particulier ou entreprise → « Monsieur, » ou « Madame, »
• Avocat confrère → « Cher Confrère, » (ou « Chère Consœur, » si l'expéditrice est une femme)
• Identité ou statut pas clairement identifiable → « Monsieur, Madame, »

━━━ STRUCTURE DE LA RÉPONSE (2 à 4 lignes, jamais plus) ━━━
1. Accuser réception par une formule d'usage — jamais de résumé
2. Annoncer un retour :
   • par défaut : « dans les meilleurs délais »
   • si l'expéditeur mentionne explicitement une urgence ou une échéance : indiquer un délai cohérent, en restant prudent, sans engagement ferme
3. Reproduire ensuite le bloc de signature officiel ci-dessous INTÉGRALEMENT et TEL QUEL,
   de « Votre bien dévoué, » jusqu'à la dernière ligne d'adresse.
   ⚠️ Ce bloc contient DÉJÀ la formule de politesse : n'en ajoute aucune autre
   (pas de « Veuillez agréer… », pas de « Cordialement »).
   ⚠️ Une réponse sans ce bloc complet est invalide.

Ton : formel, sobre, impersonnel. Pas de chaleur excessive, pas de familiarité.

Exemple complet attendu (client, sans urgence) :
Monsieur,

J'accuse bonne réception de votre message et vous remercie de l'attention portée à ce dossier. Je vous reviendrai dans les meilleurs délais.

[ICI, le bloc de signature officiel reproduit intégralement, tel qu'indiqué plus bas]

Autre début possible (confrère) — la fin reste toujours le bloc de signature :
Cher Confrère,

J'accuse bonne réception de votre correspondance. Je vous reviendrai dans les meilleurs délais.

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
Jours       : {_jours_affichage(valeurs)}
Horaires    : {heure_debut} – {heure_fin}
Standard    : {valeurs['rdv_duree']} minutes | Première consultation : {valeurs['rdv_duree_1ere']} minutes
Délai inter : {valeurs['rdv_intervalle']} minutes

━━━ SIGNATURE OBLIGATOIRE (toutes les réponses) ━━━
{construire_signature(valeurs)}
"""


def _generer_creneaux_jour(heure_debut: str, heure_fin: str, duree_min: int, intervalle_min: int) -> list[tuple[str, str]]:
    def vers_minutes(hhmm: str) -> int:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    def vers_texte(total: int) -> str:
        return f"{total // 60}h{total % 60:02d}"

    debut, fin = vers_minutes(heure_debut), vers_minutes(heure_fin)
    creneaux = []
    cur = debut
    while cur + duree_min <= fin:
        creneaux.append((vers_texte(cur), vers_texte(cur + duree_min)))
        cur += duree_min + intervalle_min
    return creneaux


def proposer_creneaux(valeurs: dict) -> str:
    """Génère les créneaux RDV disponibles à partir des paramètres du cabinet
    (jours, horaires, durée, intervalle, nombre de jours à proposer)."""
    jours_autorises = liste(valeurs, "rdv_jours") or ["lundi", "mardi", "mercredi", "jeudi"]
    creneaux_jour = _generer_creneaux_jour(
        valeurs["rdv_heure_debut"], valeurs["rdv_heure_fin"],
        int(valeurs["rdv_duree"] or 30), int(valeurs["rdv_intervalle"] or 10),
    )
    nb_jours = int(valeurs["rdv_nb_jours_proposes"] or 3)

    creneaux = []
    today = datetime.now()
    jours_proposes = 0
    delta = 1
    while jours_proposes < nb_jours and delta < 30:
        candidate = today + timedelta(days=delta)
        cle_jour = CLES_JOUR[(candidate.weekday() + 1) % 7]
        if cle_jour in jours_autorises:
            jour = f"{JOURS_FR[(candidate.weekday() + 1) % 7]} {candidate.strftime('%d/%m/%Y')}"
            for debut, fin in creneaux_jour:
                creneaux.append(f"  • {jour} de {debut} à {fin}")
            jours_proposes += 1
        delta += 1
    return "\n".join(creneaux)
