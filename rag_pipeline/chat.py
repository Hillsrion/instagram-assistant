"""Chat interface for RAG Pipeline.
Integrates the retriever with an LLM via Ollama."""
import json
import requests
from typing import Optional, Generator, List
from dataclasses import dataclass
from enum import Enum

from .config import Config, default_config
from .llm_provider import create_provider
from .retriever import Retriever, RetrievalContext
from .pii_filter import PIIFilter
from .query_analyzer import QueryAnalyzer, AnalysisResult
from .logger import get_logger, RequestLogger

logger = get_logger()


# System prompt optimized for Ministral - Anti-hallucination + interactive chat
# (Kept in French as the bot interacts in French with French data)
SYSTEM_PROMPT = """
Tu es un assistant spécialisé dans l'analyse de conversations Instagram personnelles.

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

5. REFUS CLAIRS ET CONSTRUCTIFS
   - Si l'information n'est pas dans les documents, dis-le clairement.
   - PROPOSE DE L'AIDE : Si c'est la première fois que tu mentionnes ne pas trouver l'info pour ce sujet, demande des précisions (date, nom).
   - STOP : Si l'utilisateur a déjà répondu à tes questions de précision sur CE sujet et que tu ne trouves toujours rien, clos le sujet poliment sans relancer.
   - Pas d'hypothèses en cas d'absence

6. DONNÉES PERSONNELLES - Ne révèle JAMAIS téléphones, emails, adresses
   - Si demandé : "Je ne peux pas partager ce type d'information personnelle."

7. HORS-SUJET - Tu analyses UNIQUEMENT ces conversations Instagram, rien d'autre

L'utilisateur s'appelle {user_name}. Quand tu vois "{user_name}" dans les conversations, c'est lui qui parle."""


# Follow-up questions generation prompt (optimized for Ministral)
# (Kept in French)
FOLLOWUP_PROMPT = """
Tu génères 3 questions de suivi PERTINENTES et NATURELLES.

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
    """Query types for intelligent routing."""
    RETRIEVAL = "retrieval"          # Factual recall, summaries (normal flow)
    COMPUTATIONAL = "computational"  # Counting, stats (Analytics APIs)
    DISCOVERY = "discovery"          # List, exploration (Analytics APIs)


def classify_query(query: str) -> QueryType:
    """
    Classifies a query to determine the best processing path.
    """
    query_lower = query.lower()

    # Keywords for counting questions
    computational_keywords = [
        "combien",
        "nombre de",
        "how many",
        "count",
        "combien de fois",
        "total de",
        "total messages"
    ]

    # Keywords for discovery questions
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

    # Check heuristics
    if any(keyword in query_lower for keyword in computational_keywords):
        return QueryType.COMPUTATIONAL

    if any(keyword in query_lower for keyword in discovery_keywords):
        return QueryType.DISCOVERY

    # Default: retrieval
    return QueryType.RETRIEVAL


@dataclass
class ChatResponse:
    """Chatbot response."""
    answer: str
    context: RetrievalContext
    model: str
    rewritten_query: Optional[str] = None
    search_intent: Optional[str] = None


class ChatBot:
    """RAG Chatbot with Ollama."""

    def __init__(self, retriever: Retriever = None, config: Config = None, provider_type: str = "ollama"):
        self.config = config or default_config
        self.retriever = retriever
        self.conversation_history: List[dict] = []
        self.history_summary: Optional[str] = None
        self.pii_filter = PIIFilter() if self.config.enable_pii_filter else None
        self.provider_type = provider_type
        self.provider = create_provider(self.config, self.config.llm_model, provider_type)
        self.query_analyzer = QueryAnalyzer(self.config, provider_type=provider_type)
    
    def _compact_history(self):
        """
        Summarizes old history to free up context while keeping memory.
        Triggered if history exceeds a certain threshold.
        """
        # Threshold: 10 messages (5 complete exchanges)
        if len(self.conversation_history) <= 10:
            return

        print("🗜️ Compacting conversation history...")
        
        # Keep the last 4 messages intact (immediate context)
        # Summarize everything before
        to_summarize = self.conversation_history[:-4]
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in to_summarize])
        
        # Safety: Truncate history_text to avoid context overflow (~3000 chars ≈ 750-1000 tokens)
        MAX_HISTORY_CHARS = 3000
        if len(history_text) > MAX_HISTORY_CHARS:
            history_text = history_text[:MAX_HISTORY_CHARS] + "\n[...tronqué...]"
        
        prompt = f"""Fais une synthèse concise de cette conversation passée entre l'utilisateur et l'assistant.
Ton objectif est de conserver le contexte pour la suite de la discussion.

RÈGLES IMPORTANTES :
1. Garde IMPÉRATIVEMENT les entités nommées (Noms, Dates, Lieux) et les faits précis mentionnés.
2. Synthétise la dynamique de la discussion.
3. Rédige le résumé en FRANÇAIS.

{f"Résumé précédent à mettre à jour : {self.history_summary}" if self.history_summary else ""}

Nouveaux échanges à intégrer :
{history_text}

Réponds uniquement par un paragraphe de synthèse."""

        try:
            # Use fast model for summarization (lighter task, faster response)
            summary = self._call_ollama_direct(
                system_prompt="Tu es un assistant expert en synthèse de mémoire conversationnelle.",
                user_prompt=prompt,
                model=self.config.llm_model_fast,
                max_tokens=250
            )
            self.history_summary = summary.strip()
            # Keep only the last 4 messages
            self.conversation_history = self.conversation_history[-4:]
            print(f"✅ History compacted. Summary length: {len(self.history_summary)} chars")
        except Exception as e:
            print(f"⚠️ Failed to compact history: {e}")
            # Fallback: Truncate history anyway to prevent unbounded growth
            if len(self.conversation_history) > 12:
                self.conversation_history = self.conversation_history[-6:]
                print("⚠️ Fallback: History truncated to 6 messages without summary.")

    def _call_ollama_direct(self, system_prompt: str, user_prompt: str, model: str, max_tokens: int = 50) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # If model is different from main provider model, create a temporary provider
        target_provider = self.provider
        if model != self.config.llm_model:
            target_provider = create_provider(self.config, model, self.provider_type)

        try:
            return target_provider.generate(
                messages,
                temperature=0.1,
                max_tokens=max_tokens
            )
        except Exception:
            raise

    def _build_prompt(self, query: str, context: RetrievalContext) -> str:
        """Builds the complete prompt for the LLM."""
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
            return f"""Je n'ai trouvé aucun document pertinent pour cette question dans les conversations analysées.

Question : {query}

Tâche :
1. Informe l'utilisateur que tu n'as pas trouvé d'information spécifique.
2. CONTEXTE : Regarde l'historique. Si tu as déjà posé une question de précision sur CE SUJET précis, n'insiste plus et propose de passer à autre chose.
3. RELANCE : Si c'est un nouveau sujet, demande un indice (ex: "S'agissait-il d'une discussion récente ?") pour aider ta recherche."""

    def _call_ollama(
        self,
        prompt: str,
        stream: bool = False,
        model: str = None
    ) -> Generator[str, None, None] | str:
        """Calls the LLM provider."""
        system_prompt = SYSTEM_PROMPT.format(user_name=self.config.user_name)
        
        # Add history summary if it exists
        if self.history_summary:
            system_prompt += f"\n\nCONTEXTE DE LA CONVERSATION ACTUELLE (RÉSUMÉ) :\n{self.history_summary}"

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add remaining history (compacted if necessary)
        for msg in self.conversation_history:
            messages.append(msg)

        # Add current question
        messages.append({"role": "user", "content": prompt})

        # If model is different from main provider model, create a temporary provider
        target_provider = self.provider
        if model and model != self.config.llm_model:
            target_provider = create_provider(self.config, model, self.provider_type)

        try:
            if stream:
                 # Streaming is currently only supported via Ollama direct call in this repo's architecture
                 # If using MLX, we might need a different approach or just fallback to non-streaming
                 # MLX provider doesn't support stream yet in its current implementation
                 if self.provider_type == "mlx":
                     logger.warning("Streaming not supported for MLX provider, falling back to non-streaming")
                     answer = target_provider.generate(
                         messages,
                         temperature=self.config.temperature,
                         max_tokens=self.config.max_tokens
                     )
                     def mock_stream():
                         yield answer
                     return mock_stream()
                 
                 # Fallback to direct Ollama call for streaming if provider is Ollama
                 payload = {
                    "model": model or self.config.llm_model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": self.config.temperature,
                        "top_p": self.config.top_p,
                        "num_predict": self.config.max_tokens,
                        "num_ctx": self.config.num_ctx,
                    }
                }
                 response = requests.post(
                    f"{self.config.ollama_url}/api/chat",
                    json=payload,
                    stream=True,
                    timeout=120
                )
                 response.raise_for_status()
                 return self._stream_response(response)
            else:
                return target_provider.generate(
                    messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                    
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama ({self.config.ollama_url}). "
                "Make sure Ollama is running with: ollama serve"
            )
        except Exception as e:
            raise RuntimeError(f"Ollama Error: {e}")
    
    def _stream_response(self, response) -> Generator[str, None, None]:
        """Generates tokens in streaming."""
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
        Asks a question and gets a response based on conversations.

        Args:
            query: User question
            stream: If True, returns a generator for streaming
            top_k: Number of documents to retrieve
            use_rewriting: Enable query rewriting (via Analyzer)
            model: Ollama model to use (optional)

        Returns:
            ChatResponse or generator of tokens + final ChatResponse
        """
        request_logger = RequestLogger(query)

        logger.info(f"📝 Chat request: '{query}'")

        # Omni-Prompt Analysis (Rewrite + Intent + Dates)
        # If use_rewriting is False, we could limit analysis,
        # but Analyzer also handles intent and dates.
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

        # Build prompt (with ORIGINAL question for final answer)
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
        """Chat in streaming mode."""
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

        # Final return will be accessible via StopIteration.value
        return ChatResponse(
            answer=answer,
            context=context,
            model=model or self.config.llm_model,
            rewritten_query=rewritten_query,
            search_intent=search_intent
        )
    
    def _update_history(self, query: str, answer: str, skip_add: bool = False):
        """
        Updates conversation history and triggers compaction.
        
        Args:
            query: User question
            answer: Assistant response
            skip_add: If True, does not add messages (useful if already synchronized)
        """
        if not skip_add:
            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": answer})
        
        # Check if we need to compact history
        self._compact_history()
    
    def clear_history(self):
        """Clears conversation history."""
        self.conversation_history = []
        self.history_summary = None
    
    def get_sources_summary(self, context: RetrievalContext) -> str:
        """Returns a summary of sources used."""
        if not context.has_results:
            return "No sources used."

        lines = ["Sources used:"]
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
        Generates a short and descriptive title for a conversation from the first message.
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
            
            # Aggressive cleaning
            title = title.replace('"', '').replace("'", '').replace("*", '').replace("`", '').replace("#", "")
            title = title.strip()
            
            if len(title) > 40:
                title = title[:37] + "..."
            
            return title
        except Exception as e:
            print(f"Error generating title: {e}")
            # Simple fallback
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