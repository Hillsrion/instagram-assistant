# Evaluator Agent ("The Judge")

**Component:** `eval/models.py`
**Trigger:** Manual evaluation scripts
**Default Model:** `qwen3:14b` (Recommended)

Used to benchmark the quality of the system.

## Role

It acts as a neutral third party to score:
1.  **Context Precision:** Was the retrieved document actually relevant?
2.  **Faithfulness:** Did the answer hallucinate?
3.  **Answer Relevance:** Did it actually answer the user's question?

**Note:** It is recommended to use a *larger* model (like `qwen3:14b` or `gpt-4`) for this agent to ensure the judge is smarter than the subject.
