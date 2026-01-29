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
from .tools import ToolBox, ToolResult
from .retriever import Retriever
from .logger import get_logger

logger = get_logger()


# ============================================================
# Agent System Prompt
# ============================================================

AGENT_SYSTEM_PROMPT = """Tu es un assistant expert Instagram capable d'utiliser des outils pour répondre aux questions.
Pour répondre à une question, tu DOIS suivre ce format strict :

Thought: analyse ce que tu dois faire (décomposer la demande)
Action: le nom de l'outil à utiliser (parmi: {tool_names})
Action Input: l'argument pour l'outil

STOP ICI. N'écris PAS d'Observation - le système la génèrera après exécution de l'outil.

Après avoir reçu l'Observation, tu peux soit:
- Continuer avec un nouveau Thought/Action si tu as besoin de plus d'informations
- Terminer avec "Final Answer: <ta réponse>" si tu as assez d'informations

Outils disponibles:
{tools_desc}

RÈGLES IMPORTANTES:
- Ne devine JAMAIS des informations. Utilise search_conversations pour tout fait.
- Pour les statistiques ou comptages, utilise TOUJOURS count_messages.
- Si tu peux répondre directement (salutation, question sur toi), va directement à Final Answer.
- Maximum {max_steps} étapes de raisonnement.

Date d'aujourd'hui: {today}
"""


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
        max_steps: int = 5
    ):
        self.config = config or default_config
        self.tools = ToolBox(config=self.config, retriever=retriever)
        self.max_steps = max_steps
        self.model = self.config.llm_model

    def _build_system_prompt(self) -> str:
        """Build the system prompt with tool descriptions."""
        return AGENT_SYSTEM_PROMPT.format(
            tool_names=", ".join(self.tools.get_tool_names()),
            tools_desc=self.tools.get_tools_description(),
            max_steps=self.max_steps,
            today=datetime.now().strftime("%Y-%m-%d")
        )

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
            r"Thought:\s*(.+?)(?=\n\s*Action:|Final Answer:|$)",
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
            r"Action Input:\s*`?(.+?)`?\s*(?=\n|$)",
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
            r"Final Answer:\s*(.+?)$",
            normalized,
            re.DOTALL | re.IGNORECASE
        )
        if final_match:
            result["final_answer"] = final_match.group(1).strip()

        return result

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call the LLM with the given messages."""
        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 512
                    }
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def run(self, query: str) -> AgentResult:
        """
        Run the agent on a query.
        
        Args:
            query: User question
            
        Returns:
            AgentResult with answer and reasoning steps
        """
        import time
        start_time = time.time()

        steps: List[AgentStep] = []
        scratchpad = ""  # Accumulated context

        system_prompt = self._build_system_prompt()

        logger.info(f"🤖 Agent starting for: '{query}'")

        for step_num in range(1, self.max_steps + 1):
            # Build messages
            user_content = f"Question: {query}\n\n{scratchpad}" if scratchpad else f"Question: {query}"

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

                logger.info(f"✅ Agent finished in {step_num} step(s)")
                return AgentResult(
                    answer=parsed["final_answer"],
                    steps=steps,
                    total_time=time.time() - start_time,
                    success=True
                )

            # Execute action if present
            if parsed["action"] and parsed["action_input"] is not None:
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

                # Add partial response to scratchpad
                scratchpad += f"\n{llm_response}\n"

        # Max steps reached
        logger.warning(f"⚠️ Agent reached max steps ({self.max_steps})")

        # Try to synthesize an answer from observations
        observations = [s.observation for s in steps if s.observation]
        if observations:
            synthesized = "Voici ce que j'ai trouvé:\n" + "\n".join(observations[-2:])
        else:
            synthesized = "Désolé, je n'ai pas réussi à trouver une réponse."

        return AgentResult(
            answer=synthesized,
            steps=steps,
            total_time=time.time() - start_time,
            success=False,
            error="Max steps reached"
        )

    def run_stream(self, query: str) -> Generator[Dict, None, None]:
        """
        Run the agent with streaming output for UI integration.
        
        Yields:
            Dict with step information for real-time display
        """
        import time
        start_time = time.time()

        scratchpad = ""
        system_prompt = self._build_system_prompt()

        yield {"type": "start", "query": query}

        for step_num in range(1, self.max_steps + 1):
            user_content = f"Question: {query}\n\n{scratchpad}" if scratchpad else f"Question: {query}"

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
                yield {
                    "type": "final",
                    "answer": parsed["final_answer"],
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

        yield {
            "type": "max_steps",
            "message": f"Maximum d'étapes atteint ({self.max_steps})",
            "total_time": time.time() - start_time
        }
