"""
Contains various prompts used by the RAG pipeline agents.
"""

ENRICH_PROMPT = """Tu es un analyseur de conversations (STRICT, basé sur le texte uniquement).

ANALYSE CETTE CONVERSATION ET GÉNÈRE JSON :

1. **RÉSUMÉ** : 1 phrase max, l'action/intention/résultat
2. **QUESTIONS** : 1 à {max_questions} questions précises que cet extrait répond (inclure des questions sur la dynamique sociale si pertinent : qui mène, changement d'humeur, etc.)
3. **INTENTIONS** : Pour chaque participant → son objectif principal (une phrase max)
4. **CONTEXTE TEMPOREL** : Moment/période (ex: "avant X", "durant vacances")
5. **ENTITÉS** : Éléments EXPLICITEMENT mentionnés dans le texte :
   - locations : villes, lieux, restaurants cités dans les messages
   - people : personnes mentionnées (hors participants directs)
   - media : films, séries, jeux, musiques cités
   - events : événements, fêtes, réunions cités
   - Si une catégorie n'a AUCUNE mention dans le texte → liste vide []
   - N'invente RIEN. Ne remplis PAS un champ juste pour le remplir.
6. **ÉMOTIONS** : Ambiance générale de l'échange:
   - dominant: émotion principale (basée sur le texte)
   - tone: ton général (léger, sérieux, playful, etc)
   - tension_level: low/medium/high
7. **DYNAMIQUE SOCIALE** :
   - interaction_pattern: Type d'échange dominant (ex: "Planification", "Récit", "Débat", "Soutien", "Conflit", "Catch-up"). Si aucun pattern clair n'est identifiable ou si l'échange est trop fragmenté, mets null.
   - initiative: Qui mène ? (ex: "Nom_A", "Équilibré", "Nom_B pose les questions")
   - emotional_shift: Trajectoire (ex: "Neutre -> Joyeux", "Tendu -> Apaisé", "Stable")
   - open_loops: Sujets lancés mais non résolus (liste de strings, vide si aucun)

CONVERSATION:
{content}

RÈGLES STRICTES:
- Format JSON VALIDE UNIQUEMENT, ZÉRO texte avant ou après
- ZÉRO détails non présents dans le texte
- Si un champ entités n'a pas de correspondance dans le texte → [] (liste vide)
- Ne recopie JAMAIS les exemples ci-dessous, ils illustrent uniquement le format

RÈGLES JSON OBLIGATOIRES:
- Guillemets internes dans les strings = échappés avec \" (ex: "Il a dit \"ok\"")
- Chaque propriété DOIT être séparée par une virgule
- NE PAS ajouter de parenthèses ou annotations après les strings (ex: "Film" (2020) est INTERDIT → utiliser "Film (2020)")
- Valeurs possibles: "string", ["array"], {{"object"}}, null, true, false, nombres

FORMAT JSON (les valeurs sont des exemples de format, PAS des données à recopier):
{{
  "narrative_summary": "<1 phrase décrivant l'échange>",
  "questions": ["<question 1>", "<éventuelle question 2>", "..."],
  "speaker_intents": {{
    "<participant>": "<son intention>"
  }},
  "temporal_context": "<moment ou période>",
  "entities": {{ "locations": [], "people": [], "media": [], "events": [] }},
  "emotions": {{ "dominant": "<émotion>", "tone": "<ton>", "tension_level": "low|medium|high" }},
  "interaction_pattern": "<type d'échange>",
  "initiative": "<qui mène>",
  "emotional_shift": "<trajectoire>",
  "open_loops": []
}}
"""

CONVERSATION_SUMMARY_PROMPT = """Tu résumes des conversations Instagram (BASÉ UNIQUEMENT SUR LE TEXTE).

Résumés des échanges avec {participants} :

{narrative_summaries}

GÉNÈRE JSON (strict, sans hallucinations):
- "summary": 2-3 phrases UNIQUEMENT sur ce qui est présent
- "main_topics": 3-5 sujets récurrents mentionnés
- "relationship_dynamic": Type de relation (amis, collègues, famille, etc.)
- "notable_events": Jusqu'à 5 événements EXPLICITEMENT mentionnés

RÈGLES:
- JSON VALIDE UNIQUEMENT, ZÉRO texte supplémentaire
- ZÉRO inférences, ZÉRO détails non présents
- Basé UNIQUEMENT sur les résumés fournis"""


PERIOD_SUMMARY_PROMPT = """Tu résumes des conversations Instagram pour une période (STRICT).

Échanges avec {participants} pendant {period} :

{narrative_summaries}

GÉNÈRE JSON (concis, basé sur les faits):
- "summary": 1-2 phrases sur cette période
- "topics": 2-3 sujets abordés (basé sur le texte)
- "mood": Ambiance générale (léger, sérieux, tendu, joyeux, etc.)

RÈGLES STRICTES:
- JSON VALIDE UNIQUEMENT
- ZÉRO texte supplémentaire
- Uniquement ce qui est dans les résumés fournis"""

REWRITE_PROMPT = """Tu es un expert en reformulation de requêtes pour un moteur de recherche.

TÂCHE: Réécrire la question pour qu'elle soit:
1. Autonome (compréhensible seule, sans historique)
2. Précise (mots réels, pas de pronoms vagues)
3. Optimisée pour la recherche (mots-clés pertinents)

HISTORIQUE:
{history}

QUESTION:
{query}

RÈGLES STRICTES:
- RÉPONSE UNIQUEMENT: la question réécrite
- ZÉRO commentaires, ZÉRO guillemets
- Si déjà claire → renvoie telle quelle
- Sois bref et direct
"""

QUERY_ANALYSIS_PROMPT = """Tu es un pré-processeur RAG (STRICT, JSON uniquement).
Aujourd'hui: {today_str} (ISO: {iso_str}).

Transforme la question en structure de recherche optimisée.

1. MODE (DÉCISION CRITIQUE):

   ✅ 'analytics' = COMPTAGE/STATISTIQUES/ENUMERATION UNIQUEMENT
   Exemples ANALYTICS:
   - "Combien j'ai de messages ?" → compter le total
   - "Nombre de messages avec Marie ?" → compter par contact
   - "Combien de fois on a parlé de sport ?" → compter des occurrences
   - "Lister mes contacts" → énumérer les noms
   - "Quels sont mes participants?" → énumérer

   ✅ 'retrieval' = INFORMATION, FAITS, RECHERCHES, RÉSUMÉS (tout le reste)
   Exemples RETRIEVAL:
   - "Qui est Ayoub ?" → chercher des infos sur Ayoub
   - "Est-ce qu'Ayoub est marocain ?" → chercher des attributs personnels
   - "J'ai déjà parlé d'un taxi ?" → RECHERCHE FACTUELLE (pas un comptage!)
   - "On a parlé de voiture ?" → VÉRIFICATION (pas un comptage!)
   - "De quoi on a parlé avec X ?" → résumé du contenu
   - "Qu'est-ce qu'il a dit sur..." → recherche sémantique
   - "Résume mes échanges avec Y" → analyse sémantique

   RÈGLE D'OR:
   - Si question = "Avons-nous parlé de X?" ou "Est-ce qu'on a mentionné Y?" → RETRIEVAL
   - Ne confonds pas avec "Combien de fois?" qui est ANALYTICS

2. REFORMULATION:
   - Rends la question autonome (compréhensible sans historique)
   - Remplace les pronoms (il, ça, eux) par les noms réels de l'historique
   - Optimise pour la recherche sémantique

3. INTENTION:
   - 'specific_fact' = fait précis (date, lieu, nom, événement ponctuel)
   - 'broad_summary' = résumé, ambiance, thématiques, évolution
   - 'complex_reasoning' = croiser plusieurs infos, analyser en profondeur

4. DATES:
   - Si mentionnée: extrais plage [start, end] ISO YYYY-MM-DD
   - Sinon: null
   - "été dernier" = juin-août année précédente
   - "mois dernier" = calculer depuis aujourd'hui

RÉPONDS UNIQUEMENT EN JSON (ZÉRO texte autre):
{{
  "mode": "analytics|retrieval",
  "rewritten_query": "la question reformulée",
  "intent": "specific_fact|broad_summary|complex_reasoning",
  "date_range": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}}
}}"""

AGENT_SYSTEM_PROMPT = """Tu es un assistant expert Instagram capable d'utiliser des outils pour répondre aux questions.
Pour répondre à une question, tu DOIS suivre ce format strict :

Thought: analyse ce que tu dois faire (décomposer la demande)
Action: le nom de l'outil à utiliser (parmi: {tool_names})
Action Input: l'argument pour l'outil. Utilise un texte simple pour les outils à un seul argument, ou un format JSON {{"arg": "valeur"}} si tu dois passer plusieurs paramètres (ex: search_conversations).

STOP ICI. N'écris PAS d'Observation - le système la génèrera après exécution de l'outil.

Après avoir reçu l'Observation, tu peux soit:
- Continuer avec un nouveau Thought/Action si tu as besoin de plus d'informations
- Terminer avec "Final Answer: <ta réponse>" si tu as assez d'informations

Outils disponibles:
{tools_desc}

RÈGLES IMPORTANTES:
- Ne devine JAMAIS des informations. Utilise search_conversations pour tout fait.
- Pour identifier des événements dans le temps ou compter des occurrences (ex: "Combien de fois", "Quand"), commence par explore_topic_timeline.
- DISTINCTION CRITIQUE : Faire la différence entre "parler d'un projet" et "confirmer sa réalisation" (cherche des indices comme des partages de frais, des photos, ou des "merci pour hier").
- Pour lever une ambiguïté sur un participant, utilise d'abord get_participants ou get_contact_stats.
- Pour confirmer de manière robuste la présence d'un mot ou d'une entité précise, utilise check_entity_presence.
- Si un résultat search_conversations semble incomplet, utilise get_thread_context avec l'ID du message pour voir la suite de la discussion.
- Si tu as besoin d'une vue d'ensemble rapide des derniers échanges avec quelqu'un, utilise get_summaries_for_contact.
- Si tu peux répondre directement (salutation, question sur toi), va directement à Final Answer.
- Maximum {max_steps} étapes de raisonnement.

L'utilisateur s'appelle {user_name}. Quand tu vois "{user_name}" dans les conversations, c'est lui qui parle.
Date d'aujourd'hui: {today}
"""
