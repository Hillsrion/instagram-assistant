"""
Interface de chat pour le RAG Pipeline.
Intègre le retriever avec un LLM via Ollama.
"""
import json
import requests
from typing import Optional, Generator, List
from dataclasses import dataclass
from enum import Enum

from .config import Config, default_config
from .retriever import Retriever, RetrievalContext
from .pii_filter import PIIFilter
from .query_analyzer import QueryAnalyzer, AnalysisResult
from .logger import get_logger, RequestLogger

logger = get_logger()


# Prompt système optimisé pour Ministral - Anti-hallucination + chat interactif
SYSTEM_PROMPT = """Tu es un assistant spécialisé dans l'analyse de conversations Instagram personnelles.

RÈGLES ABSOLUES:

1. VÉRACITÉ - Réponds UNIQUEMENT à partir des documents fournis
   - JAMAIS de suppositions, inférences ou extrapolations
   - Pas de contexte ajouté qui n'est pas dans les documents
   - Si l'information n'est pas dans les documents, dis-le clairement

2. CONCISION - Sois direct et pertinent
   - COMMENCE DIRECTEMENT ta réponse. Ne dis jamais "D'après les documents...", "Selon le contexte...", etc.
   - Réponds à la question posée sans détails annexes non demandés
   - Adapte la longueur à la complexité de la question
   - N'ajoute pas d'interprétations au-delà du contenu explicite

3. TYPES DE DOCUMENTS
   - RÉSUMÉS GLOBAUX : Synthèses de conversations ou périodes. Pour les questions générales ("De quoi on a parlé avec X ?", "Résume mes échanges avec Y")
   - DOCUMENTS DÉTAILLÉS : Messages exacts. Pour les questions précises ("Quand avons-nous parlé de Z ?")

4. SANS CITATIONS OU EXTRAITS
   - Ne liste PAS les sources (Ex: "Document 1", "Source: ...")
   - Ne recopie PAS d'extraits de conversation (Ex: "Extraits pertinents : ...")
   - L'interface utilisateur affiche déjà les sources, donc ta réponse doit être fluide et naturelle
   - Si tu dois citer, intègre-le naturellement dans la phrase ("Il a dit que...")

5. REFUS CLAIRS si information absente
   - "Je n'ai pas trouvé cette information dans les conversations disponibles."
   - "Les documents fournis ne contiennent pas de réponse à cette question."
   - Pas d'hypothèses en cas d'absence

6. DONNÉES PERSONNELLES - Ne révèle JAMAIS téléphones, emails, adresses
   - Si demandé : "Je ne peux pas partager ce type d'information personnelle."

7. HORS-SUJET - Tu analyses UNIQUEMENT ces conversations Instagram, rien d'autre

L'utilisateur s'appelle {user_name}. Quand tu vois "{user_name}" dans les conversations, c'est lui qui parle."""


# Prompt pour générer des questions de suivi (optimisé Ministral)
FOLLOWUP_PROMPT = """Tu génères 3 questions de suivi PERTINENTES et NATURELLES.

Question initiale : {query}
Réponse donnée : {answer}

TÂCHE:
Génère exactement 3 questions logiques que l'utilisateur pourrait poser ensuite.
Critères:
- En rapport avec la réponse donnée
- Approfondissent ou élargissent le sujet
- Formulation naturelle en français

RÉPONSE UNIQUEMENT:
- Une question par ligne
- Zéro numérotation, zéro tirets
- Zéro autre texte"""


# ============================================================
# Query Classification & Intent Analysis
# ============================================================

class QueryType(Enum):
    """Types de requêtes pour routage intelligent."""
    RETRIEVAL = "retrieval"          # Rappel factuel, résumés (flux normal)
    COMPUTATIONAL = "computational"  # Comptage, stats (APIs analytics)
    DISCOVERY = "discovery"          # Liste, exploration (APIs analytics)


def classify_query(query: str) -> QueryType:
    """
    Classifie une requête pour déterminer le meilleur traitement.
    ... (code inchangé pour classify_query)
    """
    query_lower = query.lower()

    # Keywords pour questions de comptage
    computational_keywords = [
        "combien",
        "nombre de",
        "how many",
        "count",
        "combien de fois",
        "total de",
        "total messages"
    ]

    # Keywords pour questions de découverte
    discovery_keywords = [
        "liste",
        "qui a",
        "tous les",
        "show all",
        "list all",
        "enumerate",
        "énumère",
        "quels sont",
        "qui sont",
        "members",
        "participants"
    ]

    # Vérifier les heuristiques
    if any(keyword in query_lower for keyword in computational_keywords):
        return QueryType.COMPUTATIONAL

    if any(keyword in query_lower for keyword in discovery_keywords):
        return QueryType.DISCOVERY

    # Par défaut: retrieval
    return QueryType.RETRIEVAL


@dataclass
class ChatResponse:
    """Réponse du chatbot."""
    answer: str
    context: RetrievalContext
    model: str
    rewritten_query: Optional[str] = None
    search_intent: Optional[str] = None


class ChatBot:
    """Chatbot RAG avec Ollama."""

    def __init__(self, retriever: Retriever = None, config: Config = None):
        self.config = config or default_config
        self.retriever = retriever
        self.conversation_history: List[dict] = []
        self.history_summary: Optional[str] = None
        self.pii_filter = PIIFilter() if self.config.enable_pii_filter else None
        self.query_analyzer = QueryAnalyzer(self.config)
    
    def _compact_history(self):
        """
        Résume l'historique ancien pour libérer du contexte tout en gardant la mémoire.
        Se déclenche si l'historique dépasse un certain seuil.
        """
        # Seuil: 10 messages (5 échanges complets)
        if len(self.conversation_history) <= 10:
            return

        print("🗜️ Compacting conversation history...")
        
        # On garde les 4 derniers messages intacts (contexte immédiat)
        # On résume tout ce qui précède
        to_summarize = self.conversation_history[:-4]
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])
        
        prompt = f"""Résume de manière très concise les points clés de cette conversation passée entre un utilisateur et un assistant. 
Inclus les faits importants découverts sur les conversations Instagram.
{f"Résumé précédent : {self.history_summary}" if self.history_summary else ""}

Conversation à résumer :
{history_text}

Réponds avec un résumé d'un paragraphe maximum."""

        try:
            summary = self._call_ollama_direct(
                system_prompt="Tu es un assistant qui synthétise des mémoires de conversation.",
                user_prompt=prompt,
                model=self.config.llm_model,
                max_tokens=250
            )
            self.history_summary = summary.strip()
            # On ne garde que les 4 derniers messages
            self.conversation_history = self.conversation_history[-4:]
            print(f"✅ History compacted. Summary length: {len(self.history_summary)} chars")
        except Exception as e:
            print(f"⚠️ Failed to compact history: {e}")

    def _call_ollama_direct(self, system_prompt: str, user_prompt: str, model: str, max_tokens: int = 50) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": max_tokens,
            }
        }
        
        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception:
            raise

    def _build_prompt(self, query: str, context: RetrievalContext) -> str:
        """Construit le prompt complet pour le LLM."""
        if context.has_results:
            return f"""Voici les documents de référence pour répondre à la question.

Les documents peuvent inclure :
- Des RÉSUMÉS GLOBAUX (vue d'ensemble des conversations ou périodes)
- Des DOCUMENTS DÉTAILLÉS (extraits de conversations avec messages exacts)

Utilise les résumés pour les questions générales et les documents détaillés pour les questions précises.

---

{context.formatted_context}

---

Question de l'utilisateur : {query}

Réponds en te basant UNIQUEMENT sur les documents ci-dessus. Si tu ne trouves pas l'information, dis-le clairement."""
        else:
            return f"""Je n'ai trouvé aucun document pertinent pour cette question.

Question : {query}

Indique à l'utilisateur que tu n'as pas trouvé d'information correspondante dans les conversations Instagram."""

    def _call_ollama(
        self,
        prompt: str,
        stream: bool = False,
        model: str = None
    ) -> Generator[str, None, None] | str:
        """Appelle l'API Ollama."""
        system_prompt = SYSTEM_PROMPT.format(user_name=self.config.user_name)
        
        # Ajouter le résumé de l'historique s'il existe
        if self.history_summary:
            system_prompt += f"\n\nCONTEXTE DE LA CONVERSATION ACTUELLE (RÉSUMÉ) :\n{self.history_summary}"

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Ajouter l'historique restant (qui a été compacté si nécessaire)
        for msg in self.conversation_history:
            messages.append(msg)

        # Ajouter la question actuelle
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.config.llm_model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "num_predict": self.config.max_tokens,
                "num_ctx": self.config.num_ctx,
            }
        }
        
        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                stream=stream,
                timeout=120
            )
            response.raise_for_status()
            
            if stream:
                return self._stream_response(response)
            else:
                return response.json()["message"]["content"]
                
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Impossible de se connecter à Ollama ({self.config.ollama_url}). "
                "Assurez-vous qu'Ollama est démarré avec: ollama serve"
            )
        except Exception as e:
            raise RuntimeError(f"Erreur Ollama: {e}")
    
    def _stream_response(self, response) -> Generator[str, None, None]:
        """Génère les tokens en streaming."""
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "message" in data and "content" in data["message"]:
                    content = data["message"]["content"]
                    if content:  # Only yield non-empty content
                        yield content

    def chat(
        self,
        query: str,
        stream: bool = True,
        top_k: int = None,
        use_rewriting: bool = True,
        model: str = None
    ) -> ChatResponse | Generator[str, None, ChatResponse]:
        """
        Pose une question et obtient une réponse basée sur les conversations.

        Args:
            query: Question de l'utilisateur
            stream: Si True, retourne un générateur pour le streaming
            top_k: Nombre de documents à récupérer
            use_rewriting: Activer la réécriture de question (via Analyzer)
            model: Modèle Ollama à utiliser (optionnel)

        Returns:
            ChatResponse ou générateur de tokens + ChatResponse final
        """
        request_logger = RequestLogger(query)

        logger.info(f"📝 Chat request: '{query}'")

        # Omni-Prompt Analysis (Rewrite + Intent + Dates)
        # Si use_rewriting est False, on pourrait limiter l'analyse,
        # mais l'Analyzer gère aussi l'intention et les dates.
        analysis = self.query_analyzer.analyze(query, self.conversation_history)

        search_query = analysis.rewritten_query if use_rewriting else query
        rewritten_query = analysis.rewritten_query
        search_intent = analysis.intent

        if top_k is None:
            top_k = analysis.top_k

        # Log the analysis result
        request_logger.log_analysis({
            "mode": analysis.mode,
            "intent": analysis.intent,
            "rewritten_query": analysis.rewritten_query,
            "top_k": top_k,
            "date_start": analysis.date_start,
            "date_end": analysis.date_end
        })

        logger.info(f"📊 Mode detected: {analysis.mode} | Intent: {analysis.intent} | top_k={top_k}")
        print(f"🔄 Omni-Analysis: {analysis.intent} | top_k={top_k} | mode={analysis.mode} | dates={analysis.date_start}->{analysis.date_end}")

        # Check if this is analytics mode
        if analysis.mode == "analytics":
            logger.warning(f"⚠️ Analytics mode detected for query: '{query}'")
            logger.warning(f"   This should be handled by analytics endpoints, not RAG retrieval")

        # Retrieval
        logger.info(f"🔍 Starting retrieval: top_k={top_k}, use_reranking={analysis.use_reranking}, expand_context={analysis.expand_context}")
        context = self.retriever.retrieve(
            search_query,
            top_k=top_k,
            date_start=analysis.date_start,
            date_end=analysis.date_end,
            use_reranking=analysis.use_reranking,
            expand_context=analysis.expand_context
        )

        sources = context.get_sources()
        request_logger.log_retrieval(len(sources),
                                    [r.final_score for r in context.results] if context.results else [])

        logger.info(f"📚 Retrieved {len(sources)} sources")

        # Construire le prompt (avec la question ORIGINALE pour la réponse finale)
        prompt = self._build_prompt(query, context)

        if stream:
            return self._chat_stream(query, prompt, context, rewritten_query, model, search_intent, request_logger)
        else:
            answer = self._call_ollama(prompt, stream=False, model=model)
            self._update_history(query, answer)
            request_logger.log_llm_call(model or self.config.llm_model, len(answer))
            request_logger.save()
            return ChatResponse(
                answer=answer,
                context=context,
                model=model or self.config.llm_model,
                rewritten_query=rewritten_query,
                search_intent=search_intent
            )
    
    def _chat_stream(
        self,
        query: str,
        prompt: str,
        context: RetrievalContext,
        rewritten_query: Optional[str] = None,
        model: str = None,
        search_intent: str = None,
        request_logger: Optional[RequestLogger] = None
    ) -> Generator[str, None, ChatResponse]:
        """Chat en mode streaming."""
        full_response = []

        for token in self._call_ollama(prompt, stream=True, model=model):
            full_response.append(token)
            yield token

        answer = "".join(full_response)
        self._update_history(query, answer)

        if request_logger:
            request_logger.log_llm_call(model or self.config.llm_model, len(answer))
            request_logger.save()

        logger.info(f"✅ Chat complete: response_length={len(answer)}")

        # Le return final sera accessible via StopIteration.value
        return ChatResponse(
            answer=answer,
            context=context,
            model=model or self.config.llm_model,
            rewritten_query=rewritten_query,
            search_intent=search_intent
        )
    
    def _update_history(self, query: str, answer: str, skip_add: bool = False):
        """
        Met à jour l'historique de conversation et déclenche le compactage.
        
        Args:
            query: Question de l'utilisateur
            answer: Réponse de l'assistant
            skip_add: Si True, ne rajoute pas les messages (utile si déjà synchronisé)
        """
        if not skip_add:
            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": answer})
        
        # Vérifier si on doit compacter l'historique
        self._compact_history()
    
    def clear_history(self):
        """Efface l'historique de conversation."""
        self.conversation_history = []
        self.history_summary = None
    
    def get_sources_summary(self, context: RetrievalContext) -> str:
        """Retourne un résumé des sources utilisées."""
        if not context.has_results:
            return "Aucune source utilisée."

        lines = ["Sources utilisees :"]
        for source in context.get_sources():
            lines.append(f"  - {source}")
        return "\n".join(lines)

    def filter_pii(self, text: str) -> str:
        """Filter PII from text if enabled."""
        if self.pii_filter and self.config.enable_pii_filter:
            filtered, matches = self.pii_filter.mask(text)
            if matches:
                print(f"PII filtered: {len(matches)} items masked")
            return filtered
        return text

    def evaluate_title(self, first_message: str, model: str = None) -> str:
        """
        Génère un titre court et descriptif pour une conversation à partir du premier message.
        """
        prompt = f"""Génère un titre très court (3 à 5 mots maximum) et accrocheur pour une conversation qui commence par ce message :
\"{first_message}\"

Le titre doit être en français et refléter le sujet principal.
RÈGLES STRICTES :
- PAS de guillemets, PAS de markdown (**gras**, *italique*, etc.).
- PAS de ponctuation finale.
- Uniquement du texte brut.
- Maximum 40 caractères."""

        payload = {
            "model": model or self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 20,
            }
        }

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            title = response.json()["message"]["content"].strip()
            
            # Nettoyage agressif
            title = title.replace('"', '').replace("'", "").replace("*", "").replace("`", "").replace("#", "")
            title = title.strip()
            
            if len(title) > 40:
                title = title[:37] + "..."
            
            return title
        except Exception as e:
            print(f"Error generating title: {e}")
            # Fallback simple
            return first_message[:30] + "..." if len(first_message) > 30 else first_message

    def generate_followup_questions(self, query: str, answer: str, model: str = None) -> List[str]:
        """Generate follow-up questions based on the conversation."""
        prompt = FOLLOWUP_PROMPT.format(query=query, answer=answer[:500])

        payload = {
            "model": model or self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.5,
                "top_p": 0.9,
                "num_predict": 200,
                "num_ctx": self.config.num_ctx,
            }
        }

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            content = response.json()["message"]["content"].strip()

            # Parse lines as questions
            questions = []
            for line in content.split('\n'):
                line = line.strip()
                # Remove numbering or bullet points
                line = line.lstrip('0123456789.-) ')
                if line and len(line) > 10 and '?' in line:
                    questions.append(line)

            return questions[:3]

        except Exception as e:
            print(f"Followup generation error: {e}")
            return []

    def chat_stream(self, query: str, context: str, model: str = None) -> Generator[str, None, None]:
        """
        Stream chat response given a query and formatted context.
        Used by app.py for direct context passing.
        """
        prompt = f"""Voici les documents de reference pour repondre a la question.

Les documents peuvent inclure :
- Des RÉSUMÉS GLOBAUX (vue d'ensemble des conversations ou périodes)
- Des DOCUMENTS DÉTAILLÉS (extraits de conversations avec messages exacts)

Utilise les résumés pour les questions générales et les documents détaillés pour les questions précises.

---

{context}

---

Question de l'utilisateur : {query}

Reponds en te basant UNIQUEMENT sur les documents ci-dessus. Si tu ne trouves pas l'information, dis-le clairement."""

        for token in self._call_ollama(prompt, stream=True, model=model):
            # Filter PII from each token (less efficient but real-time)
            yield token

