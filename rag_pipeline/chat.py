"""
Interface de chat pour le RAG Pipeline.
Intègre le retriever avec un LLM via Ollama.
"""
import json
import requests
from typing import Optional, Generator, List
from dataclasses import dataclass

from .config import Config, default_config
from .retriever import Retriever, RetrievalContext


# Prompt système strict pour éviter les hallucinations
SYSTEM_PROMPT = """Tu es un assistant spécialisé dans l'analyse de conversations Instagram personnelles.

RÈGLES STRICTES À SUIVRE :

1. **Réponds UNIQUEMENT à partir des documents fournis**
   - Ne jamais inventer ou supposer des informations
   - Si l'information n'est pas dans les documents, dis-le clairement

2. **Cite tes sources**
   - Mentionne toujours le document source (numéro, date, participants)
   - Utilise des citations directes quand c'est pertinent

3. **Format de réponse**
   - Sois concis et factuel
   - Structure ta réponse si plusieurs éléments

4. **Gestion de l'incertitude**
   - Si les documents ne contiennent pas l'information : "Je n'ai pas trouvé cette information dans les conversations."
   - Si l'information est partielle : "D'après les conversations disponibles, [info]. Cependant, je n'ai pas de détails sur [ce qui manque]."
   - Si la question est ambiguë : demande des précisions

5. **Confidentialité**
   - Ces conversations sont privées
   - Traite le contenu avec respect

L'utilisateur s'appelle {user_name}. Quand tu vois "{user_name}" dans les conversations, c'est lui qui parle."""


# Prompt pour la réécriture de requête (Query Rewriting)
REWRITE_PROMPT = """Tu es un expert en analyse de conversations Instagram. 
Ta tâche est de transformer une question utilisateur en une liste de mots-clés et de phrases courtes qui sont plus susceptibles d'apparaître dans une conversation Instagram réelle (style informel, abréviations, slang).

Question originale : {query}

RÈGLES :
1. Imagine comment les gens en parlent naturellement par message (ex: "anniversaire" -> "anniv", "restaurant" -> "resto", "est-ce que" -> "tu veux/on va").
2. Inclus des variations de vocabulaire.
3. Retourne uniquement la liste de termes optimisés pour la recherche, séparés par des virgules.
4. Ne réponds pas à la question, réécris-la pour la recherche uniquement.

Requête optimisée :"""


@dataclass
class ChatResponse:
    """Réponse du chatbot."""
    answer: str
    context: RetrievalContext
    model: str
    rewritten_query: Optional[str] = None
    

class ChatBot:
    """Chatbot RAG avec Ollama."""
    
    def __init__(self, retriever: Retriever, config: Config = None):
        self.config = config or default_config
        self.retriever = retriever
        self.conversation_history: List[dict] = []
    
    def _rewrite_query(self, query: str) -> str:
        """Réécrit la requête pour améliorer le retrieval."""
        prompt = REWRITE_PROMPT.format(query=query)
        
        payload = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 100,
            }
        }
        
        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            rewritten = response.json()["message"]["content"].strip()
            # Combiner l'originale et la réécrite pour ne rien perdre
            return f"{query} {rewritten}"
        except Exception as e:
            print(f"⚠️ Échec de la réécriture de requête: {e}")
            return query

    def _build_prompt(self, query: str, context: RetrievalContext) -> str:
        """Construit le prompt complet pour le LLM."""
        if context.has_results:
            return f"""Voici les documents de référence pour répondre à la question :

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
        stream: bool = False
    ) -> Generator[str, None, None] | str:
        """Appelle l'API Ollama."""
        system_prompt = SYSTEM_PROMPT.format(user_name=self.config.user_name)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Ajouter l'historique de conversation (limité aux 4 derniers échanges)
        for msg in self.conversation_history[-8:]:
            messages.append(msg)
        
        # Ajouter la question actuelle
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.config.llm_model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "num_predict": self.config.max_tokens,
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
                    yield data["message"]["content"]
    
    def chat(
        self, 
        query: str,
        stream: bool = True,
        top_k: int = None,
        use_rewriting: bool = True
    ) -> ChatResponse | Generator[str, None, ChatResponse]:
        """
        Pose une question et obtient une réponse basée sur les conversations.
        
        Args:
            query: Question de l'utilisateur
            stream: Si True, retourne un générateur pour le streaming
            top_k: Nombre de documents à récupérer
            use_rewriting: Activer la réécriture de question
            
        Returns:
            ChatResponse ou générateur de tokens + ChatResponse final
        """
        search_query = query
        rewritten_query = None
        
        if use_rewriting:
            rewritten_query = self._rewrite_query(query)
            search_query = rewritten_query

        # Retrieval
        context = self.retriever.retrieve(search_query, top_k=top_k)
        
        # Construire le prompt (avec la question ORIGINALE pour la réponse finale)
        prompt = self._build_prompt(query, context)
        
        if stream:
            return self._chat_stream(query, prompt, context, rewritten_query)
        else:
            answer = self._call_ollama(prompt, stream=False)
            self._update_history(query, answer)
            return ChatResponse(
                answer=answer,
                context=context,
                model=self.config.llm_model,
                rewritten_query=rewritten_query
            )
    
    def _chat_stream(
        self, 
        query: str, 
        prompt: str, 
        context: RetrievalContext,
        rewritten_query: Optional[str] = None
    ) -> Generator[str, None, ChatResponse]:
        """Chat en mode streaming."""
        full_response = []
        
        for token in self._call_ollama(prompt, stream=True):
            full_response.append(token)
            yield token
        
        answer = "".join(full_response)
        self._update_history(query, answer)
        
        # Le return final sera accessible via StopIteration.value
        return ChatResponse(
            answer=answer,
            context=context,
            model=self.config.llm_model,
            rewritten_query=rewritten_query
        )
    
    def _update_history(self, query: str, answer: str):
        """Met à jour l'historique de conversation."""
        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": answer})
    
    def clear_history(self):
        """Efface l'historique de conversation."""
        self.conversation_history = []
    
    def get_sources_summary(self, context: RetrievalContext) -> str:
        """Retourne un résumé des sources utilisées."""
        if not context.has_results:
            return "Aucune source utilisée."
        
        lines = ["📚 Sources utilisées :"]
        for source in context.get_sources():
            lines.append(f"  • {source}")
        return "\n".join(lines)

