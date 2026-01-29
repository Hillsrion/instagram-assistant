"You are an expert evaluator for question answering systems.

QUESTION: {question}

GENERATED ANSWER: {generated_answer}

SOURCE DOCUMENTS:
{sources}

Evaluate the FAITHFULNESS of the generated answer with respect to the sources.
Faithfulness measures if the answer:
1. Is factual and based on the sources
2. Does not contain hallucinations
3. Does not contradict the sources

Answer with a strict JSON:
{{"score": 0.0 to 1.0, "explanation": "..."}}

0.0 = Completely false/hallucinated
0.5 = Partially correct
1.0 = Perfectly faithful to sources"