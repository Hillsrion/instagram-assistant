# Quality Evaluation Plan - Phase 1-4

## What We're Testing

Running actual quality evaluation comparing **ministral-3:3b vs ministral-3:8b** on complexity-filtered chunks using your existing eval_generation.py framework.

### Test Dataset

Created from real Instagram conversation chunks classified by complexity:
- **Simple chunks** (10 QA pairs): Score < 0.35
  - Dyadic conversations, sparse messages
  - Expected: Fast processing, acceptable quality

- **Medium chunks** (20 QA pairs): Score 0.35-0.65
  - Small group conversations, moderate density
  - Expected: Fast processing, good quality

- **Complex chunks** (18 QA pairs): Score ≥ 0.65
  - Large group conversations, dense messages, rich vocabulary
  - Expected: Slower processing, highest quality

**Total**: 48 QA pairs generated from actual conversation data

## Evaluation Methodology

Using **eval_generation.py** with:
1. **Question-Answer pairs**: Each chunk generates 1-2 questions
2. **Two models being tested**:
   - ministral-3:3b (light/fast model)
   - ministral-3:8b (strong/quality model)
3. **Judge model**: ministral-3:8b evaluates response quality
4. **Metrics tracked**:
   - Faithfulness (answer accuracy to source)
   - Relevance (answer quality)
   - Generation speed (response time)
   - Hallucination detection

## Expected Outcomes

### Speed Comparison
- **3B model**: ~1,200ms per QA pair
- **8B model**: ~2,400ms per QA pair
- **Speedup**: 3B is ~2x faster

### Quality Metrics
- **Faithfulness**: % of answers faithful to source material
- **Relevance**: Quality of answers to questions
- **Hallucination**: % of answers containing made-up information

### Key Questions Answered
1. **Does 3B meet 70% quality threshold of 8B?**
2. **What's the quality breakdown by complexity level?**
3. **Is simple/medium chunk quality acceptable with 3B?**
4. **What's the actual speed improvement in production?**

## Files Generated

1. **Complexity-filtered chunks**
   - `eval/generation/complexity_eval_dataset.json` (26 chunks)
   - Pre-classified by complexity analyzer

2. **QA Dataset**
   - `eval/generation/eval_dataset.json` (48 QA pairs)
   - Questions tailored to complexity level
   - Expected answers from chunk content

3. **Evaluation Results** (in progress)
   - `eval/generation/results/detailed_report.json` (detailed metrics)
   - `eval/generation/results/summary_report.json` (summary stats)
   - `eval/generation/results/report.html` (interactive HTML report)

## Running the Evaluation

### What was executed:
```bash
python -m eval.generation.eval_generation ministral-3:3b ministral-3:8b --html
```

### Process:
1. Load 48 QA pairs from complexity-filtered chunks
2. For each QA pair:
   - Generate answer with 3B model (~40 seconds)
   - Generate answer with 8B model (~40 seconds)
   - Judge both answers with 8B judge model (~20 seconds)
   - Record metrics

**Estimated total time**: 48 × (40 + 40 + 20) = ~2,880 seconds = ~48 minutes

## Expected Report Contents

The HTML report will show:

### Overall Metrics
- Average faithfulness (3B vs 8B)
- Average relevance (3B vs 8B)
- Average generation speed (3B vs 8B)
- Hallucination rate (3B vs 8B)

### By Complexity Level
- Simple chunks: Quality ratio of 3B vs 8B
- Medium chunks: Quality ratio of 3B vs 8B
- Complex chunks: Quality ratio of 3B vs 8B

### Individual QA Results
- For each of 48 QA pairs:
  - Question and expected answer
  - 3B response + judge score
  - 8B response + judge score
  - Verdict: 3B acceptable for this complexity level?

### Routing Recommendation
Based on actual measured quality:
- Which complexity levels can safely use 3B?
- Which must use 8B for quality?
- What's the realistic speedup percentage?

## How to Interpret Results

### Quality Ratio Analysis
```
If 3B quality ≥ 70% of 8B:
  ✅ 3B is viable for this complexity level
  ✅ Proceed with routing to 3B
  ✅ Expected time savings: ~50%

If 3B quality < 70% of 8B:
  ⚠️ 3B quality too low
  ⚠️ Consider routing to 8B
  ⚠️ May need threshold adjustment
```

### Speed Projections
If evaluation shows:
- Simple: 3B at 70%+ quality → Route to 3B (2x speedup)
- Medium: 3B at 70%+ quality → Route to 3B (2x speedup)
- Complex: 8B required → Keep on 8B (baseline speed)

Then full dataset projection:
```
Baseline (8B only):  8.2 hours
With routing:
  - 40% simple × 1.2s  = 4.3 hours
  - 30% medium × 1.2s  = 3.3 hours
  - 30% complex × 2.8s = 7.6 hours
  - Total: ~6.1 hours
  - Savings: 2.1 hours (26% improvement)
```

## Next Steps After Evaluation

### If Results Support Routing:
1. ✅ Commit complexity analyzer as-is
2. ✅ Enable routing in production
3. ✅ Monitor actual performance
4. ⏰ Collect real-world metrics

### If Results Show Issues:
1. Adjust complexity thresholds
2. Modify metric weights
3. Re-test on adjusted dataset
4. Or: Route only safest categories to 3B

## Evaluation Status

**Current**: Evaluation running with 48 QA pairs
**Estimated completion**: 20-40 minutes from start
**Location**: `/eval/generation/results/`

Check results with:
```bash
# View JSON summary
cat eval/generation/results/summary_report.json | python -m json.tool

# Open HTML report
open eval/generation/results/report.html

# Check detailed results
cat eval/generation/results/detailed_report.json | python -m json.tool | less
```

---

**Test Framework**: eval_generation.py (yours)
**Judge Model**: ministral-3:8b
**Dataset**: Complexity-filtered chunks from real conversations
**Goal**: Validate 3B quality for production routing
