#!/usr/bin/env python3
"""
Test script to evaluate if ministral-8b can follow the strict ReAct format.
This helps decide if implementing a full ReAct agent is viable with this model.
"""

import re
import requests
from typing import NamedTuple

# Use the same Ollama URL as the rest of the project
OLLAMA_URL = "http://localhost:11434"

# The ReAct prompt format we want the model to follow
REACT_SYSTEM_PROMPT = """Tu es un assistant expert Instagram capable d'utiliser des outils.
Pour répondre à une question, tu DOIS suivre ce format strict :

Question: la question de l'utilisateur
Thought: analyse ce que tu dois faire (décomposer la demande)
Action: le nom de l'outil à utiliser (parmi: search_conversations, count_messages, get_todays_date)
Action Input: l'argument pour l'outil

STOP ICI. N'écris PAS d'Observation - le système la génèrera.

Outils disponibles :
1. search_conversations(query: str): Cherche dans l'historique des discussions via le sens sémantique.
2. count_messages(contact_name: str): Donne le nombre exact de messages échangés avec un contact.
3. get_todays_date(): Donne la date actuelle.

IMPORTANT :
- Ne devine jamais des faits. Utilise search_conversations.
- Pour compter, utilise TOUJOURS count_messages.
- Si tu peux répondre directement (ex: salutation), écris juste: Final Answer: [ta réponse]
"""

# Test cases with expected behavior
TEST_CASES = [
    {
        "query": "Combien de messages j'ai échangé avec Alice ?",
        "expected_action": "count_messages",
        "description": "Simple counting query - should use count_messages"
    },
    {
        "query": "De quoi on a parlé avec Marco la semaine dernière ?",
        "expected_action": "search_conversations",
        "description": "Semantic search query - should use search_conversations"
    },
    {
        "query": "Quelle est la date d'aujourd'hui ?",
        "expected_action": "get_todays_date",
        "description": "Date query - should use get_todays_date"
    },
    {
        "query": "Salut, ça va ?",
        "expected_action": "Final Answer",
        "description": "Simple greeting - should go directly to Final Answer"
    },
    {
        "query": "Retrouve le message où Sarah parle de son voyage",
        "expected_action": "search_conversations",
        "description": "Content search - should use search_conversations"
    },
]


class TestResult(NamedTuple):
    query: str
    description: str
    expected_action: str
    detected_action: str | None
    has_thought: bool
    has_action_input: bool
    hallucinated_observation: bool
    raw_response: str
    passed: bool


def parse_react_response(response: str) -> dict:
    """
    Parse the model's response to extract ReAct components.
    Tolerant parser that handles:
    - Markdown bold: **Action:** or **Thought:**
    - JSON inputs: {"query": "..."}
    - Backtick-wrapped values: `search_conversations`
    """
    result = {
        "thought": None,
        "action": None,
        "action_input": None,
        "has_observation": False,  # We DON'T want this - means hallucination
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
    
    # Check for Action (handles backticks and extra whitespace)
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
        json_match = re.search(r'["\']?(?:query|contact_name)["\']?\s*:\s*["\']([^"\']+)["\']', raw_input)
        if json_match:
            result["action_input"] = json_match.group(1).strip()
        else:
            result["action_input"] = raw_input
    
    # Check if model hallucinated an Observation (BAD!)
    if re.search(r"\*?\*?Observation\*?\*?:", response, re.IGNORECASE):
        result["has_observation"] = True
    
    # Check for Final Answer
    final_match = re.search(
        r"Final Answer:\s*(.+?)$", 
        normalized, 
        re.DOTALL | re.IGNORECASE
    )
    if final_match:
        result["final_answer"] = final_match.group(1).strip()
    
    return result


def test_model(model_name: str = "ministral-3:8b") -> list[TestResult]:
    """Run all test cases against the model."""
    results = []
    
    print(f"\n{'='*60}")
    print(f"Testing ReAct format compliance with: {model_name}")
    print(f"{'='*60}\n")
    
    for i, test in enumerate(TEST_CASES, 1):
        print(f"Test {i}/{len(TEST_CASES)}: {test['description']}")
        print(f"  Query: {test['query']}")
        
        prompt = f"{REACT_SYSTEM_PROMPT}\n\nQuestion: {test['query']}\n"
        
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=120
            )
            response.raise_for_status()
            raw_response = response.json()["response"]
        except Exception as e:
            print(f"  ❌ Error calling model: {e}")
            results.append(TestResult(
                query=test["query"],
                description=test["description"],
                expected_action=test["expected_action"],
                detected_action=None,
                has_thought=False,
                has_action_input=False,
                hallucinated_observation=False,
                raw_response=str(e),
                passed=False
            ))
            continue
        
        parsed = parse_react_response(raw_response)
        
        # Determine detected action
        if parsed["final_answer"] and not parsed["action"]:
            detected_action = "Final Answer"
        else:
            detected_action = parsed["action"]
        
        # Check if the test passed
        correct_action = (
            detected_action and 
            detected_action.lower() == test["expected_action"].lower().replace(" ", "_")
        ) or (
            test["expected_action"] == "Final Answer" and 
            parsed["final_answer"] is not None
        )
        
        has_thought = parsed["thought"] is not None
        has_action_input = parsed["action_input"] is not None or test["expected_action"] == "Final Answer"
        no_hallucination = not parsed["has_observation"]
        
        passed = correct_action and has_thought and no_hallucination
        
        result = TestResult(
            query=test["query"],
            description=test["description"],
            expected_action=test["expected_action"],
            detected_action=detected_action,
            has_thought=has_thought,
            has_action_input=has_action_input,
            hallucinated_observation=parsed["has_observation"],
            raw_response=raw_response,
            passed=passed
        )
        results.append(result)
        
        # Print result
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}")
        print(f"    - Thought present: {'✓' if has_thought else '✗'}")
        print(f"    - Correct action: {'✓' if correct_action else '✗'} (expected: {test['expected_action']}, got: {detected_action})")
        print(f"    - No hallucinated Observation: {'✓' if no_hallucination else '✗'}")
        
        if not passed:
            print(f"\n  --- Raw Response ---")
            print(f"  {raw_response[:500]}...")
        print()
    
    return results


def print_summary(results: list[TestResult]):
    """Print a summary of test results."""
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{total} tests passed ({100*passed/total:.0f}%)")
    print(f"{'='*60}")
    
    # Analysis
    hallucinations = sum(1 for r in results if r.hallucinated_observation)
    wrong_actions = sum(1 for r in results if not r.passed and r.detected_action != r.expected_action)
    no_thoughts = sum(1 for r in results if not r.has_thought)
    
    print(f"\nIssue breakdown:")
    print(f"  - Hallucinated Observations: {hallucinations}")
    print(f"  - Wrong action selected: {wrong_actions}")
    print(f"  - Missing Thought: {no_thoughts}")
    
    # Verdict
    print(f"\n{'='*60}")
    if passed >= 4:
        print("✅ VERDICT: Model is VIABLE for ReAct pattern")
        print("   The model can follow the format reasonably well.")
    elif passed >= 2:
        print("⚠️  VERDICT: Model is MARGINAL for ReAct pattern")
        print("   Consider using few-shot examples or a simpler approach.")
    else:
        print("❌ VERDICT: Model is NOT RECOMMENDED for ReAct pattern")
        print("   The format compliance is too low. Use multi-tool router instead.")
    print(f"{'='*60}")


if __name__ == "__main__":
    results = test_model("ministral-3:8b")
    print_summary(results)
    
    # Save raw responses for analysis
    print("\n\nSaving detailed results to test_react_results.txt...")
    with open("test_react_results.txt", "w") as f:
        for i, r in enumerate(results, 1):
            f.write(f"\n{'='*60}\n")
            f.write(f"TEST {i}: {r.description}\n")
            f.write(f"Query: {r.query}\n")
            f.write(f"Expected: {r.expected_action}\n")
            f.write(f"Detected: {r.detected_action}\n")
            f.write(f"Passed: {r.passed}\n")
            f.write(f"\n--- RAW RESPONSE ---\n{r.raw_response}\n")
    print("Done!")
