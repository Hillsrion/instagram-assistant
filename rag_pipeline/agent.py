"""
ReAct Agent for RAG Pipeline.
Implements the Reasoning + Acting pattern for multi-step query processing.
"""
import re
import requests
from datetime import datetime
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass, field

from .config import Config, default_config
from .llm_provider import create_provider
from .tools import ToolBox, ToolResult
from .retriever import Retriever
from .logger import get_logger
from .prompts import AGENT_SYSTEM_PROMPT

logger = get_logger()


@dataclass
class AgentStep:
    """A single step in the agent's reasoning."""
    step_num: int
    thought: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[str] = None
    observation: Optional[str] = None
    is_final: bool = False
    final_answer: Optional[str] = None


@dataclass
class AgentResult:
    """Final result from the agent."""
    answer: str
    steps: List[AgentStep] = field(default_factory=list)
    sources: List[dict] = field(default_factory=list)
    summary_sources: List[dict] = field(default_factory=list)
    total_time: float = 0.0
    success: bool = True
    error: Optional[str] = None


class AgentRunner:
    """
    ReAct Agent that uses tools to answer questions.
    Implements the Thought -> Action -> Observation loop.
    """

    def __init__(
        self,
        config: Config = None,
        retriever: Retriever = None,
        analytics=None,
        max_steps: int = 10,
        provider_type: str = "ollama"
    ):
        self.config = config or default_config
        self.tools = ToolBox(config=self.config, retriever=retriever, analytics=analytics)
        self.max_steps = max_steps
        self.model = self.config.llm_model
        self.provider = create_provider(self.config, self.model, provider_type)

    def _build_system_prompt(self) -> str:
        """Build the system prompt with tool descriptions."""
        return AGENT_SYSTEM_PROMPT.format(
            tool_names=", ".join(self.tools.get_tool_names()),
            tools_desc=self.tools.get_tools_description(),
            max_steps=self.max_steps,
            today=datetime.now().strftime("%Y-%m-%d")
        )

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """Format recent conversation history for the agent prompt."""
        if not history:
            return ""
        lines = []
        for msg in history[-4:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long messages
            content = msg["content"][:300] + "..." if len(msg["content"]) > 300 else msg["content"]
            lines.append(f"{role}: {content}")
        return "Historique récent:\n" + "\n".join(lines) + "\n\n"

    def _parse_response(self, response: str) -> Dict:
        """
        Parse the model's response to extract ReAct components.
        Tolerant parser that handles markdown formatting.
        """
        result = {
            "thought": None,
            "action": None,
            "action_input": None,
            "final_answer": None,
        }

        # Normalize: remove markdown bold markers
        normalized = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)

        # Check for Thought (handles numbered lists, multi-line)
        thought_match = re.search(
            r"(?:Thought|Pensée):\s*(.+?)(?=\n\s*(?:Action|Final Answer|Réponse finale):|$)",
            normalized,
            re.DOTALL | re.IGNORECASE
        )
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        # Check for Action (handles backticks)
        action_match = re.search(
            r"Action:\s*`?(\w+)`?",
            normalized,
            re.IGNORECASE
        )
        if action_match:
            result["action"] = action_match.group(1).strip()

        # Check for Action Input (handles JSON, backticks, or simple strings)
        input_match = re.search(
            r"(?:Action Input|Entrée):\s*`?(.+?)`?\s*(?=\n|$)",
            normalized,
            re.IGNORECASE | re.DOTALL
        )
        if input_match:
            raw_input = input_match.group(1).strip().strip('`')
            # Try to extract value from JSON if present
            json_match = re.search(
                r'["\']?(?:query|contact_name)["\']?\s*:\s*["\']([^"\']+)["\']',
                raw_input
            )
            if json_match:
                result["action_input"] = json_match.group(1).strip()
            else:
                result["action_input"] = raw_input.strip('"\'')

        # Check for Final Answer
        final_match = re.search(
            r"(?:Final Answer|Réponse finale):\s*(.+?)$",
            normalized,
            re.DOTALL | re.IGNORECASE
        )
        if final_match:
            result["final_answer"] = final_match.group(1).strip()

        return result

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM with the given messages."""
        try:
            return self.provider.generate(
                messages,
                temperature=0.1,
                max_tokens=512
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _prepare_run(self, query: str, history: List[Dict[str, str]] = None, analysis=None):
        """Common setup for run() and run_stream()."""
        # Inject analysis into tools
        if analysis:
            self.tools.set_analysis(analysis)
        self.tools.set_original_query(query)
        # Reset last context
        self.tools._last_context = None

    def _extract_results(self) -> tuple:
        """Extract sources from tools after agent run."""
        sources = self.tools.get_sources()
        summary_sources = self.tools.get_summary_sources()
        return sources, summary_sources

    def run(
        self,
        query: str,
        history: List[Dict[str, str]] = None,
        analysis=None
    ) -> AgentResult:
        """
        Run the agent on a query.

        Args:
            query: User question
            history: Recent conversation history
            analysis: AnalysisResult from QueryAnalyzer

        Returns:
            AgentResult with answer, reasoning steps, and sources
        """
        import time
        start_time = time.time()

        self._prepare_run(query, history, analysis)

        steps: List[AgentStep] = []
        scratchpad = ""  # Accumulated context

        system_prompt = self._build_system_prompt()
        history_str = self._format_history(history)

        logger.info(f"🤖 Agent starting for: '{query}'")

        for step_num in range(1, self.max_steps + 1):
            # Build messages
            if scratchpad:
                user_content = f"{history_str}Question: {query}\n\n{scratchpad}"
            else:
                user_content = f"{history_str}Question: {query}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]

            # Call LLM
            try:
                llm_response = self._call_llm(messages)
            except Exception as e:
                return AgentResult(
                    answer=f"Erreur lors de l'appel au modèle: {str(e)}",
                    steps=steps,
                    total_time=time.time() - start_time,
                    success=False,
                    error=str(e)
                )

            logger.debug(f"Step {step_num} LLM response:\n{llm_response}")

            # Parse response
            parsed = self._parse_response(llm_response)

            step = AgentStep(step_num=step_num)
            step.thought = parsed["thought"]
            step.action = parsed["action"]
            step.action_input = parsed["action_input"]

            # Check for final answer
            if parsed["final_answer"]:
                step.is_final = True
                step.final_answer = parsed["final_answer"]
                steps.append(step)

                sources, summary_sources = self._extract_results()

                logger.info(f"✅ Agent finished in {step_num} step(s)")
                return AgentResult(
                    answer=parsed["final_answer"],
                    steps=steps,
                    sources=sources,
                    summary_sources=summary_sources,
                    total_time=time.time() - start_time,
                    success=True
                )

            # Execute action if present
            if parsed["action"] and parsed["action_input"] is not None:
                # Prevent repetition
                action_key = f"{parsed['action']}:{parsed['action_input']}"
                if any(f"{s.action}:{s.action_input}" == action_key for s in steps):
                    logger.warning(f"Step {step_num}: Repetitive action detected: {action_key}")
                    scratchpad += f"\nObservation: J'ai déjà essayé cette action avec ce paramètre. Je dois essayer une autre approche ou conclure si j'ai assez d'informations.\n"
                    steps.append(step)
                    continue

                tool_result = self.tools.execute(
                    parsed["action"],
                    parsed["action_input"]
                )
                step.observation = tool_result.output
                steps.append(step)

                logger.info(
                    f"  Step {step_num}: {parsed['action']}('{parsed['action_input']}') "
                    f"→ {'✓' if tool_result.success else '✗'}"
                )

                # Add to scratchpad for next iteration
                scratchpad += (
                    f"\nThought: {parsed['thought'] or '(raisonnement)'}\n"
                    f"Action: {parsed['action']}\n"
                    f"Action Input: {parsed['action_input']}\n"
                    f"Observation: {tool_result.output}\n"
                )
            else:
                # No valid action, try to recover or fail
                steps.append(step)
                logger.warning(f"Step {step_num}: No valid action parsed")

                # Add partial response to scratchpad with a nudge
                scratchpad += f"\n{llm_response}\n"
                scratchpad += "\nObservation: Format invalide détecté. Tu dois impérativement utiliser 'Action: <nom_outil>' et 'Action Input: <input>' ou terminer par 'Final Answer: <réponse>'.\n"

        # Max steps reached or error occurred
        logger.warning(f"⚠️ Agent reached max steps ({self.max_steps}) or failed. Synthesizing fallback answer.")

        sources, summary_sources = self._extract_results()

        # Fallback Synthesis: Call LLM one last time to make sense of the scratchpad
        fallback_answer = self._synthesize_fallback(query, scratchpad)

        return AgentResult(
            answer=fallback_answer,
            steps=steps,
            sources=sources,
            summary_sources=summary_sources,
            total_time=time.time() - start_time,
            success=False,
            error="Max steps reached - Synthesized fallback"
        )

    def _synthesize_fallback(self, query: str, scratchpad: str) -> str:
        """Synthesize a final answer from a partial scratchpad."""
        if not scratchpad:
            return "Désolé, je n'ai pas trouvé assez d'informations pour répondre à votre question."

        prompt = f"""Tu es un assistant de secours. L'agent de recherche n'a pas pu terminer son raisonnement, mais voici ses notes de recherche (scratchpad).
Utilise ces informations pour donner la meilleure réponse possible à la question initiale.

IMPORTANT:
- Si les informations sont incomplètes, dis-le honnêtement.
- Ne mentionne pas que tu es un "système de secours" ou que l'agent a échoué, réponds naturellement.
- Si le scratchpad contient des preuves contradictoires, expose-les.

QUESTION INITIALE: {query}

NOTES DE RECHERCHE:
{scratchpad}

RÉPONSE FINALE:"""

        try:
            messages = [{"role": "user", "content": prompt}]
            return self.provider.generate(messages, temperature=0.3, max_tokens=512)
        except Exception as e:
            logger.error(f"Fallback synthesis failed: {e}")
            return "Désolé, une erreur est survenue lors de la synthèse des résultats."

    def run_stream(
        self,
        query: str,
        history: List[Dict[str, str]] = None,
        analysis=None
    ) -> Generator[Dict, None, None]:
        """
        Run the agent with streaming output for UI integration.

        Args:
            query: User question
            history: Recent conversation history
            analysis: AnalysisResult from QueryAnalyzer

        Yields:
            Dict with step information for real-time display
        """
        import time
        start_time = time.time()

        self._prepare_run(query, history, analysis)

        scratchpad = ""
        system_prompt = self._build_system_prompt()
        history_str = self._format_history(history)

        yield {"type": "start", "query": query}

        for step_num in range(1, self.max_steps + 1):
            if scratchpad:
                user_content = f"{history_str}Question: {query}\n\n{scratchpad}"
            else:
                user_content = f"{history_str}Question: {query}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]

            yield {"type": "thinking", "step": step_num}

            try:
                llm_response = self._call_llm(messages)
            except Exception as e:
                yield {"type": "error", "message": str(e)}
                return

            parsed = self._parse_response(llm_response)

            if parsed["thought"]:
                yield {"type": "thought", "step": step_num, "content": parsed["thought"]}

            if parsed["final_answer"]:
                sources, summary_sources = self._extract_results()
                yield {
                    "type": "final",
                    "answer": parsed["final_answer"],
                    "sources": sources,
                    "summary_sources": summary_sources,
                    "total_time": time.time() - start_time,
                    "steps": step_num
                }
                return

            if parsed["action"] and parsed["action_input"] is not None:
                yield {
                    "type": "action",
                    "step": step_num,
                    "tool": parsed["action"],
                    "input": parsed["action_input"]
                }

                tool_result = self.tools.execute(parsed["action"], parsed["action_input"])

                yield {
                    "type": "observation",
                    "step": step_num,
                    "success": tool_result.success,
                    "content": tool_result.output[:500]  # Truncate for UI
                }

                scratchpad += (
                    f"\nThought: {parsed['thought'] or '(raisonnement)'}\n"
                    f"Action: {parsed['action']}\n"
                    f"Action Input: {parsed['action_input']}\n"
                    f"Observation: {tool_result.output}\n"
                )

        sources, summary_sources = self._extract_results()
        
        # Fallback Synthesis for stream
        yield {"type": "thinking", "step": "fallback"}
        fallback_answer = self._synthesize_fallback(query, scratchpad)
        
        yield {
            "type": "final",
            "answer": fallback_answer,
            "sources": sources,
            "summary_sources": summary_sources,
            "total_time": time.time() - start_time,
            "steps": self.max_steps,
            "is_fallback": True
        }
