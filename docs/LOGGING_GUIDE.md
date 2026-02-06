# Logging Guide for RAG Pipeline

## Overview

A structured logging system has been added to debug query classification issues. This guide explains how to access and interpret it.

## Log Files

### 1. `rag_data/logs/rag_pipeline.log`
Main real-time pipeline log. Contains all events with timestamps and levels (DEBUG, INFO, WARNING, ERROR).

**Example:**
```
[2026-01-28 19:00:45,123] INFO     rag_pipeline - 📨 Chat stream request: 'who is ayoub ?'
[2026-01-28 19:00:45,234] DEBUG    rag_pipeline - [analysis] mode: retrieval, intent: broad_summary
[2026-01-28 19:00:45,456] INFO     rag_pipeline - 🔄 Using RETRIEVAL flow
```

### 2. `rag_data/logs/debug.jsonl`
JSONL format (JSON Lines) with a structured trace per request. Each line is a complete JSON object with all events for a request.

**Structure Example:**
```json
{
  "request_id": "2026-01-28T19:00:45.123456",
  "query": "who is ayoub ?",
  "duration_seconds": 2.45,
  "event_count": 5,
  "events": [
    {
      "timestamp": "2026-01-28T19:00:45.234",
      "type": "query_analysis",
      "data": {
        "mode": "analytics",
        "intent": "broad_summary",
        "rewritten_query": "Who is Ayoub?",
        "top_k": 15
      }
    },
    {
      "timestamp": "2026-01-28T19:00:45.456",
      "type": "retrieval",
      "data": {
        "source_count": 12,
        "top_scores": [0.85, 0.82, 0.79]
      }
    }
  ]
}
```

## Using the `scripts/utils/view_logs.py` script

### Show latest logs
```bash
python scripts/utils/view_logs.py debug        # The last 10 requests
python scripts/utils/view_logs.py debug 20     # The last 20 requests
```

### Show RAG logs in real-time
```bash
python scripts/utils/view_logs.py tail         # The last 50 lines
python scripts/utils/view_logs.py tail 100     # The last 100 lines
```

### Search for a specific query
```bash
python scripts/utils/view_logs.py search "who is ayoub"
```

### View the latest request in detail
```bash
python scripts/utils/view_logs.py latest
```

## Interpreting Logs

### The Problem to Debug

You reported that for the question **"who is ayoub ?"**:
- **Answer 1 (bad):** Just stats (587 messages, 1 conversation)
- **Answer 2 (correct):** Detailed answer with 15 sources

### Tracing in Logs

1. **Search for your query:**
   ```bash
   python scripts/utils/view_logs.py search "who is ayoub"
   ```

2. **Look at the `mode` field:**
   ```
   MODE: analytics | INTENT: broad_summary  ← PROBLEM!
   MODE: retrieval | INTENT: broad_summary  ← CORRECT
   ```

3. **If mode = "analytics":**
   - The query was misclassified
   - It was routed to `handle_discovery_query` or `handle_computational_query`
   - Result: just stats, no RAG retrieval

4. **If mode = "retrieval":**
   - Classification is correct
   - The full RAG pipeline executes
   - Sources and complete answer

### Important Events

| Event Type | Meaning | Important Key |
|------------|---------|---------------|
| `query_analysis` | Query analysis by LLM | `mode` (analytics/retrieval) |
| `retrieval` | Source retrieval | `source_count` |
| `llm_response` | Response generation | `response_length` |
| `error` | Pipeline error | `message` |

## Case Study: "who is ayoub ?"

### The Query
```
"who is ayoub ?"
```

### Observed Answers
1. Analytics mode → Answer: "Ayoub ait-addi: 587 messages, 1 conversations" ❌
2. Retrieval mode → Answer: Full detail with sources ✅

### Probable Cause
The QueryAnalyzer prompt says:
```python
"analytics' = count the TOTAL messages, conversations or contacts
 Examples: 'How many messages do I have?', 'Number of messages with Marie?', 'List my contacts'"
```

For "who is ayoub ?", the LLM must decide:
- **analytics**: "It's a question about a person, so count their messages?"
- **retrieval**: "It's a semantic question, search who is Ayoub in conversations"

The problem is that the QueryAnalyzer prompt is ambiguous or inconsistent.

## Recommended Solution

1. **Improve QueryAnalyzer prompt** (rag_pipeline/query_analyzer.py):
   - Clarify what is "analytics" vs "retrieval"
   - Add more examples for "who is..." questions

2. **Add telemetry** (already done!):
   - Structured logs to debug each decision

3. **Monitor results**:
   ```bash
   python scripts/utils/view_logs.py search "who is"
   # Verify that mode=retrieval for all these questions
   ```

## Real-time Logging Options

### During Development
Leave the main log open in a terminal:
```bash
tail -f rag_data/logs/rag_pipeline.log
```

You will see each request in real-time:
```
[19:00:45] INFO - 📨 Chat stream request: 'who is ayoub ?'
[19:00:45] INFO - 🎯 Analysis result: mode=analytics, intent=broad_summary
[19:00:45] WARNING - ⚠️ Routing to ANALYTICS mode for: 'who is ayoub ?'
```

### Analyzing Structured Traces Afterwards
```bash
python scripts/utils/view_logs.py debug 20
# Examine each request with its detailed events
```

## Log Levels

- **DEBUG**: Technical details (LLM response, parameters)
- **INFO**: Important events (analysis, retrieval, response)
- **WARNING**: ⚠️ Unexpected behavior (analytics mode for a factual question)
- **ERROR**: ❌ Pipeline error

## Logging Configuration

To modify log levels, edit `rag_pipeline/logger.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change here: DEBUG, INFO, WARNING, ERROR
    # ...
)
```

## Summary

The logging system allows you to:
1. ✅ Trace each request end-to-end
2. ✅ Identify classification (analytics vs retrieval)
3. ✅ Debug problems quickly
4. ✅ Archive traces for analysis

**Next Step:** Use `python scripts/utils/view_logs.py search "who is ayoub"` after testing the query to see why it is classified differently between calls.