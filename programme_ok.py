import openai
from supabase import create_client, Client
import datetime
import base64
import json
import os
from PyPDF2 import PdfReader
import imaplib
import email
from email.policy import default
from PyPDF2 import PdfReader
from docx import Document  # Pour les fichiers .docx
import subprocess
import olefile


def save_attachment(part, file_name):
    """
    Sauvegarde une pièce jointe localement.
    """
    try:
        file_path = os.path.join("temp_attachments", file_name)
        os.makedirs("temp_attachments", exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(part.get_payload(decode=True))
        return file_path
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde de la pièce jointe : {e}")
        return None


def is_cv_attachment(cv_content: str):
    """
    Utilise GPT pour déterminer si une pièce jointe est un CV.
    """
    try:
        prompt = f"""
        Le fichier suivant est-il un CV ? Réponds uniquement par "oui" ou "non".
        Voici le CONTENU du fichier : {cv_content}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Tu es un assistant expert en détection de CV, tu reponds uniquement par oui ou par non"},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        answer = response["choices"][0]["message"]["content"].strip().lower()
        return answer == "oui"
    except Exception as e:
        print(f"❌ Erreur lors de la détection du CV : {e}")
        return False


def connect_to_email(email_address, password, imap_server, imap_port=993):
    """
    Connecte au serveur IMAP et retourne une connexion.
    """
    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(email_address, password)
        return mail
    except Exception as e:
        print(f"❌ Erreur lors de la connexion à l'email : {e}")
        return None

def get_unread_emails_with_attachments(mail):
    """
    Recherche des emails non lus avec des pièces jointes.
    Retourne une liste de tuples (file_name, part, email_msg).
    """
    emails_with_attachments = []
    mail.select("inbox")
    status, messages = mail.search(None, 'UNSEEN')

    if status != "OK":
        print("❌ Impossible de rechercher les emails.")
        return []

    for num in messages[0].split():
        status, data = mail.fetch(num, '(RFC822)')
        if status != "OK":
            print(f"❌ Impossible de récupérer l'email {num}.")
            continue

        email_msg = email.message_from_bytes(data[0][1])
        for part in email_msg.walk():
            if part.get_content_disposition() == "attachment":
                file_name = part.get_filename()
                if file_name:
                    emails_with_attachments.append((file_name, part, email_msg))

    return emails_with_attachments


# Configuration
OPENAI_API_KEY = "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"
SUPABASE_URL = "https://ahrjubvfqubphxzylixd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFocmp1YnZmcXVicGh4enlsaXhkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzE5NDA3MzYsImV4cCI6MjA0NzUxNjczNn0.CEEokI-zJrY0poanGAG8uPkEqmVm6LQLp3-IanUSNeY"
EMAIL = "vivazio.serv@gmail.com"
PASSWORD = "fbfnccfznvxfbglv"
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
# Initialisation des clients
openai.api_key = OPENAI_API_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_text_from_file(file_path: str) -> str:
    """
    Extrait le texte d'un fichier (PDF, DOCX, DOC, TXT).
    """
    try:
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == ".pdf":
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text.strip()

        elif file_extension == ".txt":
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read().strip()

        elif file_extension == ".docx":
            from docx import Document
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs]).strip()

        elif file_extension == ".doc":
            try:
                # Méthode avec olefile
                return extract_text_from_doc(file_path)
            except Exception:
                print("❌ Échec avec olefile. Essayez LibreOffice pour convertir le fichier.")

        else:
            raise ValueError("Format non pris en charge : PDF, TXT, DOCX, ou DOC uniquement.")
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction : {e}")
        return ""

def analyze_cv(cv_content: str, email_body: str):
    """
    Analyse un CV avec GPT-4o-mini et extrait les informations sous forme de JSON.
    """
    prompt =f"""
    **Analyse de l'Email et du CV du Candidat**

    En tant qu'expert RH avec une vaste expérience, tu es chargé d'analyser le contenu d'un email de candidature ainsi que le CV qui y est associé. L'objectif est d'extraire les informations pertinentes et de les présenter sous forme de JSON valide.

    **1. Analyse de l'Email de Candidature**

    - **Identification du Poste Ciblé :**
      - Identifie le poste visé mentionné dans l'email.
      - Si aucune information n'est trouvée, indique "Non spécifié".

    - **Résumé de l'Email :**
      - Fournis un résumé court de l'email en mettant en évidence les points importants à prendre en considération.
      - Si aucune information n'est trouvée, indique "Non spécifié".

    **2. Analyse du CV**

    - Procède au nettoyage et au formatage du texte du CV pour une lecture complète.
    - Récupère toutes les informations disponibles et les organise de manière structurée.
    - Extrait les compétences, expériences, formations et autres informations pertinentes du candidat.

    **3. Évaluation de la Correspondance avec le Poste Ciblé**

    - **Calcul du Pourcentage de Correspondance :**
      - Évalue le pourcentage de correspondance entre la fiche de poste du poste cible et l'analyse approfondie du CV du candidat.
      - Applique les pondérations suivantes pour le calcul du score de correspondance :
        - **Compétences techniques critiques :** 50%
        - **Expériences professionnelles récentes (dans les 5 dernières années ou correspondant au secteur) :** 30%
        - **Soft skills (leadership, communication, gestion de projet, etc.) :** 20%

    - **Justification du Matching :**
      - Fournis une explication textuelle du score de correspondance dans le champ `justification_matching`.
      - Prends en compte les synonymes et le contexte dans les descriptions des compétences et expériences.
      - Si un mot-clé exact est absent mais que le contexte est pertinent, ajuste la correspondance en conséquence.

    **4. Vérification des Incohérences**

    - **Détection d'Incohérences :**
      - Vérifie les dates incohérentes (par exemple, une date de fin antérieure à une date de début).
      - Identifie les expériences professionnelles qui se chevauchent.
      - Repère les durées improbables pour un poste.

    - **Rapport des Incohérences :**
      - Si des incohérences sont détectées, indique-les dans le champ `erreurs_detection` du JSON avec des suggestions de correction.
      - Si aucune incohérence n’est trouvée, indique `"erreurs_detection": "Aucune incohérence détectée"`.

    **5. Détection de la Langue et Traduction**

    - **Langue du CV :**
      - Détecte automatiquement la langue du CV.
      - Si le CV est rédigé dans une langue autre que le français, procède à une traduction en français avant de poursuivre l’analyse.
      - Indique dans le JSON le champ `langue_source` pour indiquer la langue d'origine détectée.
      - Indique si une traduction a été nécessaire avec le champ `traduction_necessaire` (valeurs possibles : `true` ou `false`).

    **6. Déduction des Soft Skills**

    - **Inférence des Compétences Humaines :**
      - Déduis les soft skills à partir des descriptions des expériences professionnelles.
        - Par exemple, si le candidat mentionne la gestion d’équipes, infère "Leadership" ou "Gestion de conflits".
        - Si des interactions avec des clients ou partenaires sont mentionnées, infère "Communication" ou "Négociation".
        - Si des exemples de résolution de problèmes complexes sont donnés, infère "Résolution de problèmes" ou "Pensée critique".

    - **Score de Confiance :**
      - Attribue un score de confiance (entre 1 et 5) à chaque soft skill déduite.
      - Inclue ce score dans le champ `soft_skills` du JSON.

    **7. Processus de Statut de Candidature**

    - **Décision sur le Statut :**
      - Prends une décision pour statuer sur cette candidature en choisissant parmi les options suivantes : "À traiter", "À contacter", "Refusé", "Sélectionné".
      - Indique la date du statut avec la date d'aujourd'hui (`date_statut`).
      - Fournis des commentaires justifiant ta décision dans le champ `commentaires`.

    **8. Format des Données à Extraire**

    Les informations à extraire et à inclure dans le JSON sont les suivantes :

    - **Informations Personnelles :**
      - `nom` : Nom du candidat.
      - `prenom` : Prénom du candidat.
      - `date_naissance` : Date de naissance au format "YYYY-MM-DD".
      - `nationalite` : Nationalité du candidat.
      - `adresse` : Adresse actuelle du candidat.
      - `code_postal` : Code postal de l'adresse.
      - `ville` : Ville de résidence.
      - `email` : Email professionnel ou personnel.
      - `telephone` : Numéro de téléphone au format standard international.
      - `poste_cible` : Titre du poste concerné, bien formaté et corrigé.
      - `date_candidature` : Date d'aujourd'hui au format "YYYY-MM-DD".
      - `resume_email` : Court résumé de l'email avec les notes importantes à prendre en considération.
      - `disponibilite_geographique` : Disponibilité à se déplacer géographiquement (`true` ou `false`).
      - `disponibilite_immediate` : Disponibilité immédiate (`true` ou `false`).
      - `mobilite_geographique` : Type de mobilité (par exemple : régionale, nationale, internationale).
      - `permis_conduire` : Possession du permis de conduire (`true` ou `false`).

    - **Scores et Justifications :**
      - `matching_percentage` : Pourcentage de correspondance entre 0 et 100.
      - `matching_score` : Score global de correspondance (0 à 100).
      - `competences_techniques_score` : Score des compétences techniques (0 à 100).
      - `experiences_recentes_score` : Score des expériences récentes (0 à 100).
      - `soft_skills_score` : Score des soft skills (0 à 100).
      - `justification_matching` : Explication détaillée du score de correspondance.
      - `pond_comptences_techniques` : Pondération appliquée sur les compétences techniques.
      - `pond_experiences_recentes` : Pondération appliquée sur les expériences récentes.
      - `pond_soft_skills` : Pondération appliquée sur les soft skills.

    - **Langue et Traduction :**
      - `langue_source` : Langue d'origine du CV (par exemple : "français").
      - `traduction_necessaire` : Indique si une traduction a été nécessaire (`true` ou `false`).

    - **Vérification des Incohérences :**
      - `erreurs_detection` : Liste des incohérences détectées ou "Aucune incohérence détectée".
      - `dates_incoherentes` : Indique s'il y a des dates incohérentes (`true` ou `false`).
      - `chevauchement_experiences` : Indique s'il y a des chevauchements d'expériences (`true` ou `false`).
      - `durees_improbables` : Indique s'il y a des durées improbables (`true` ou `false`).

    - **Processus de Statut :**
      - `process_status` : Liste contenant le statut, la date du statut et les commentaires.

    - **Langues :**
      - `langues` : Liste des langues maîtrisées avec leur niveau respectif. Niveaux acceptés : "Débutant", "Intermédiaire", "Avancé", "Expert", "Courant".

    - **Formations Académiques :**
      - `formations` : Liste des diplômes, établissements, dates d'obtention et détails pertinents.

    - **Expériences Professionnelles :**
      - `experiences` : Liste des postes, entreprises, secteurs, dates et missions principales.

    - **Compétences Techniques et Humaines :**
      - `hard_skills` : Liste des compétences techniques spécifiques avec leur niveau de maîtrise.
        - Niveaux acceptés : "Débutant", "Intermédiaire", "Avancé", "Expert".
      - `soft_skills` : Liste des compétences humaines avec un score de confiance entre 1 et 5.

    **9. Format Attendu du JSON**

    Le format de la réponse doit être un JSON valide, structuré comme l'exemple ci-dessous. Toutes les dates doivent être au format "YYYY-MM-DD". Si tu n'as que l'année et pas le jour ou le mois, utilise le premier jour de l'année ; sinon, mets `null`.

    ```json
    {{
      "nom": "string",
      "prenom": "string",
      "date_naissance": "YYYY-MM-DD",
      "date_candidature": "YYYY-MM-DD",
      "poste_cible": "string",
      "resume_email": "string",
      "matching_percentage": integer,
      "nationalite": "string",
      "adresse": "string",
      "code_postal": "string",
      "ville": "string",
      "email": "string",
      "telephone": "string",
      "disponibilite_geographique": true,
      "disponibilite_immediate": true,
      "mobilite_geographique": "string",
      "permis_conduire": true,
      "matching_score": integer,
      "competences_techniques_score": integer,
      "experiences_recentes_score": integer,
      "soft_skills_score": integer,
      "justification_matching": "string",
      "langue_source": "string",
      "traduction_necessaire": true,
      "erreurs_detection": "string",
      "dates_incoherentes": true,
      "chevauchement_experiences": true,
      "durees_improbables": true,
      "pond_comptences_techniques": integer,
      "pond_experiences_recentes": integer,
      "pond_soft_skills": integer,
      "process_status": [
        {{
          "statut": "string",  // Choix possibles : "À traiter", "À contacter", "Refusé", "Sélectionné"
          "date_statut": "YYYY-MM-DD",
          "commentaires": "string"
        }}
      ],
      "langues": [
        {{
          "langue": "string",
          "niveau": "string"  // Niveaux possibles : "Débutant", "Intermédiaire", "Avancé", "Expert", "Courant"
        }}
      ],
      "formations": [
        {{
          "diplome": "string",
          "etablissement": "string",
          "date_obtention": "YYYY-MM-DD",
          "details": "string"
        }}
      ],
      "experiences": [
        {{
          "poste": "string",
          "entreprise": "string",
          "secteur": "string",
          "date_debut": "YYYY-MM-DD",
          "date_fin": "YYYY-MM-DD",
          "missions": "string"
        }}
      ],
      "hard_skills": [
        {{
          "competence": "string",
          "niveau": "string"
        }}
      ],
      "soft_skills": [
        {{
          "competence": "string",
          "score_confiance": integer  // Entre 1 et 5
        }}
        
      ]
    }}
    ```

    **Remarques Importantes :**

    - **Précision et Exhaustivité :**
      - Sois le plus précis et complet possible dans tes réponses et extractions.
      - Prends en compte tous les détails fournis dans le CV et l'email.

    - **Niveaux de Langues et de Compétences :**
      - Utilise uniquement les niveaux suivants pour les langues et les hard skills : "Débutant", "Intermédiaire", "Avancé", "Expert", "Courant".
      - Les niveaux tels que "C2" ne sont pas acceptés.

    - **Format des Dates :**
      - Toutes les dates doivent être au format "YYYY-MM-DD".
      - Si le jour ou le mois ne sont pas disponibles, utilise le premier jour du mois ou de l'année correspondante.

    - **Processus de Statut :**
      - Justifie ta décision dans le champ `commentaires` en motivant le choix du statut.

    - **Synonymes et Contexte :**
      - Prends en compte les synonymes et le contexte dans les descriptions des compétences et expériences.
      - Si un mot-clé exact est absent mais que le contexte est pertinent, ajuste la correspondance en conséquence.

            ```

    Le texte du CV est le suivant :
    {cv_content}
    le contenu de l'email est le suivant :
    {email_body}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Tu es un assistant expert rh ainsi qu'en extraction d'informations de CV."},
                {"role": "user", "content": prompt}
            ],
            #max_tokens=2048,
            temperature=0.5
        )
        response_text = response["choices"][0]["message"]["content"]

        # Nettoyer la réponse pour extraire le JSON
        if "```json" in response_text:
            start = response_text.find("```json") + len("```json")
            end = response_text.find("```", start)
            json_text = response_text[start:end].strip()
        else:
            json_text = response_text.strip()

        # Convertir en dictionnaire Python
        parsed_data = json.loads(json_text)
        return parsed_data
    except json.JSONDecodeError as e:
        print(f"❌ Erreur lors du parsing de la réponse GPT : {e}")
        print("Texte brut retourné par GPT :", response_text)
        return None
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse du CV : {e}")
        return None

def map_language_level(level):
    mapping = {
        "courant": "Avancé",
        "débutant": "Débutant",
        "intermédiaire": "Intermédiaire",
        "avancé": "Avancé",
        "expert": "Expert",
        "Notions":"Débutant",
        "c2": "Avancé",
        "c1": "Avancé",
        "b2": "Intermédiaire",
        "b1": "Intermédiaire",
        "a2": "Débutant",
        "a1": "Débutant"
    }
    return mapping.get(level.lower(), "Débutant")  # Par défaut à "Débutant" si non reconnu

def insert_data_into_db(data: dict, file_name:str):
    """
    Insère les données extraites dans la base de données Supabase.
    """
    try:
        candidate_data = {
            "nom": data.get("nom", ""),
            #"date_candidature": sanitize_date(data.get("date_candidature", "")),
            "poste_cible": data.get("poste_cible", ""),
            "resume_email": data.get("resume_email", ""),
            "matching_percentage": data.get("matching_percentage", ""),
            "prenom": data.get("prenom", ""),
            "date_naissance": sanitize_date(data.get("date_naissance", "")),
            "nationalite": data.get("nationalite", ""),
            "adresse": data.get("adresse", ""),
            "code_postal": data.get("code_postal", ""),
            "ville": data.get("ville", ""),
            "email": data.get("email", ""),
            "telephone": data.get("telephone", ""),
            "disponibilite_geographique": data.get("disponibilite_geographique", False),
            "disponibilite_immédiate": data.get("disponibilite_immediate", False),
            "mobilite_geographique": data.get("mobilite_geographique", ""),
            "permis_conduire": data.get("permis_conduire", False),
            "matching_score": data.get("matching_score", ""),
            "competences_techniques_score": data.get("competences_techniques_score", ""),
            "experiences_recentes_score": data.get("experiences_recentes_score", ""),
            "soft_skills_score": data.get("soft_skills_score", ""),
            "justification_matching": data.get("justification_matching", ""),
            "langue_source": data.get("langue_source", ""),
            "traduction_necessaire": data.get("traduction_necessaire", False),
            "erreurs_detection": data.get("erreurs_detection", ""),
            "dates_incoherentes": data.get("dates_incoherentes", False),
            "chevauchement_experiences": data.get("chevauchement_experiences", False),
            "durees_improbables": data.get("durees_improbables", False),
            "pond_comptences_techniques": data.get("pond_comptences_techniques", ""),
            "pond_experiences_recentes": data.get("pond_experiences_recentes", ""),
            "pond_soft_skills": data.get("pond_soft_skills", "")
        }

        candidate_response = supabase.table("candidates").insert(candidate_data).execute()
        candidate_id = candidate_response.data[0]["id"]

        # Insertion dans les tables liées
        if "langues" in data:
            languages_data = [
                {"candidate_id": candidate_id, "langue": lang["langue"], "niveau": lang["niveau"]}
                for lang in data["langues"]
            ]
            supabase.table("languages").insert(languages_data).execute()

        if "formations" in data:
            formations_data = [
                {
                    "candidate_id": candidate_id,
                    "diplome": form["diplome"],
                    "etablissement": form["etablissement"],
                    "date_obtention": sanitize_date(form["date_obtention"]),
                    "details": form.get("details", "")
                }
                for form in data["formations"]
            ]
            supabase.table("formations").insert(formations_data).execute()

        if "experiences" in data:

            experiences_data = [
                {
                    "candidate_id": candidate_id,
                    "poste": exp["poste"],
                    "entreprise": exp["entreprise"],
                    "secteur": exp.get("secteur", ""),
                    "date_debut": sanitize_date(exp["date_debut"]),
                    "date_fin": sanitize_date(exp.get("date_fin", "")),
                    "missions": exp.get("missions", "")
                }
                for exp in data["experiences"]
            ]
            supabase.table("experiences").insert(experiences_data).execute()

        if "hard_skills" in data:
            hard_skills_data = [
                {"candidate_id": candidate_id, "competence": skill["competence"], "niveau": skill["niveau"]}
                for skill in data["hard_skills"]
            ]
            supabase.table("hard_skills").insert(hard_skills_data).execute()

        if "soft_skills" in data:

            soft_skills_data = [
                {
                    "candidate_id": candidate_id,
                    "competence": skill["competence"],
                    "score_confiance": skill.get("score_confiance", "")
                    
                }
                for skill in data["soft_skills"]
              ]
            
            supabase.table("soft_skills").insert(soft_skills_data).execute()

        if "process_status" in data:


            process_status_data = [
                {
                    "candidate_id": candidate_id,
                    "statut": skil.get("statut", ""),
                    #"date_statut": sanitize_date(skil.get("date_statut", "")),
                    "commentaires": skil.get("commentaires", "")
                    
                }
                for skil in data["process_status"]
              ]
            
            supabase.table("process_status").insert(process_status_data).execute()
        cv_data = {
            
                
            "candidate_id": candidate_id,
            "nom_document": file_name,
            "type_document": file_name.split(".")[-1],  # Exemple : 'pdf', 'docx'
            "contenu": "CV" # Stocker le lien vers le fichier
            #"date_ajout": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  }

            # Insérer dans la table CV_save
        response = supabase.table("documents").insert(cv_data).execute()

        print("✅ Données insérées avec succès dans la base de données.")
    except Exception as e:
        print(f"❌ Erreur lors de l'insertion dans la base de données : {e}")
from datetime import datetime

def sanitize_date(date_str):
    """
    Convertit une chaîne de date en un format valide 'YYYY-MM-DD' ou renvoie None si invalide.
    Si seule l'année est fournie, la complète avec '01-01'.
    """
    if date_str is None or date_str.strip().upper() == "NULL":
        return None

    try:
        # Si seule l'année est donnée, compléter avec '-01-01'
        if len(date_str) == 4 and date_str.isdigit():
            return f"{date_str}-01-01"
        # Tenter de parser une date complète
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%Y-%m-%d")
    except ValueError:
        print(f"⚠️ Format de date invalide : {date_str}")
        return None
def clean_data(data):
    """
    Nettoie les données pour remplacer les valeurs non valides par None
    et formater les dates correctement.
    """
    for key, value in data.items():
        if isinstance(value, str) and value.upper() == "NULL":
            data[key] = None
        elif "date" in key.lower() and isinstance(value, str):
            data[key] = sanitize_date(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    clean_data(item)
    return data

def extract_email_body(email_msg):
    """
    Extrait le contenu texte de l'email.
    """
    if email_msg.is_multipart():
        for part in email_msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode('utf-8')
    else:
        if email_msg.get_content_type() == "text/plain":
            return email_msg.get_payload(decode=True).decode('utf-8')
    return ""



def upload_cv_to_bucket(file_path, file_name):
    """
    Charge le fichier CV dans le bucket Supabase et retourne l'URL publique.

    :param file_path: Chemin complet du fichier local.
    :param file_name: Nom sous lequel le fichier sera sauvegardé dans le bucket.
    :return: URL publique du fichier ou None en cas d'erreur.
    """
    try:
        # Charger le fichier dans le bucket
        with open(file_path, "rb") as file:
            response = supabase.storage.from_("CV_save").upload(file_name, file)



            # Gestion de la réponse après l'upload
            if "error" in response and response["error"]:
                print(f"❌ Erreur lors de l'upload dans le bucket : {response['error']['message']}")
            else:
                print("✅ Fichier uploadé avec succès.")


        if response.status_code == 200:
            print(f"✅ Fichier '{file_name}' chargé avec succès dans le bucket.")

            # Obtenir l'URL publique
            public_url_response = supabase.storage.from_("CV_save").get_public_url(file_name)
            public_url = public_url_response.get("publicURL")
            return public_url
        else:
            print(f"❌ Erreur lors du chargement du fichier '{file_name}' dans le bucket : {response.data}")
            return None
    except Exception as e:
        print(f"❌ Erreur lors de l'upload dans le bucket : {e}")
        return None
from datetime import datetime

def register_cv_in_db(file_path, file_name, candidate_id=None):
    """
    Enregistre un CV dans la base de données Supabase avec l'URL publique du fichier.

    :param file_path: Chemin complet du fichier local.
    :param file_name: Nom du fichier CV.
    :param candidate_id: ID du candidat associé au CV (optionnel).
    """
    try:
        # Charger le fichier dans le bucket et obtenir l'URL publique
        public_url = upload_cv_to_bucket(file_path,cleaned_data, file_name)
        if not public_url:
            print(f"❌ Impossible de charger le fichier '{file_name}' dans le bucket.")
            return

        # Préparer les données pour l'insertion dans la base
        #cv_data = {
        #    "candidate_id": candidate_id,
        #    "nom_document": file_name,
        #    "type_document": file_name.split(".")[-1],  # Exemple : 'pdf', 'docx'
        #    "contenu": public_url,  # Stocker le lien vers le fichier
        #    "date_ajout": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #}

        # Insérer dans la table CV_save
        #response = supabase.table("documents").insert(cv_data).execute()

        # Vérifier le statut de la réponse et afficher un message approprié
        if response.get("status", "") == "201":  # Vérifier le code de succès
            print(f"✅ CV '{file_name}' enregistré avec succès dans la base de données.")
        else:
            print(f"❌ Erreur lors de l'insertion du CV '{file_name}' : {response.get('error', 'Erreur inconnue')}")

    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement du CV '{file_name}' dans la base de données ")



def main():


    print("🔄 Connexion à la boîte email...")
    mail = connect_to_email(EMAIL, PASSWORD, IMAP_SERVER)
    if not mail:
        return

    print("🔄 Recherche des emails avec pièces jointes...")
    emails_with_attachments = get_unread_emails_with_attachments(mail)

    if not emails_with_attachments:
        print("✅ Aucun email non lu avec pièces jointes trouvé.")
        return

    print(f"🔍 {len(emails_with_attachments)} email(s) avec pièces jointes trouvé(s).")

    for email_data in emails_with_attachments:
        file_name, part, email_msg = email_data  # Ajout de l'objet email_msg pour le contenu de l'email
        print(f"🔄 Traitement de la pièce jointe : {file_name}...")

        # Sauvegarde de la pièce jointe
        file_path = save_attachment(part, file_name)
        if not file_path:
            continue

        # Extraction du contenu de l'email
        print("🔄 Extraction du contenu de l'email...")
        email_body = extract_email_body(email_msg)  # Fonction pour extraire le corps de l'email

        # Vérification si la pièce jointe est un CV
        print("🔄 Vérification si c'est un CV...")
        cv_content = extract_text_from_file(file_path)
        if is_cv_attachment(cv_content):
            print("✅ Pièce jointe identifiée comme un CV.")
            
            # Extraction du texte
            print("🔄 Extraction du texte du CV...")
            if cv_content:
                print("🔄 Analyse du CV avec GPT en incluant le contenu de l'email...")
                gpt_response = analyze_cv(cv_content, email_body)  # Passe le contenu du CV et de l'email

                if gpt_response:
                    print("🔄 Insertion des données dans la base...")
                    cleaned_data = clean_data(gpt_response)
                    insert_data_into_db(cleaned_data, file_name)

            # Enregistrement du CV dans la base de données avec upload au bucket
            print("🔄 Enregistrement du CV dans le bucket et la base de données...")
            register_cv_in_db(file_path, file_name)
        else:
            print("❌ Pièce jointe non identifiée comme un CV. Ignorée.")

    print("✅ Traitement terminé.")


if __name__ == "__main__":
    main()
