"""
JSON Schemas for Ollama structured output.
"""

ENRICHMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative_summary": {"type": "string"},
        "questions": {
            "type": "array",
            "items": {"type": "string"}
        },
        "speaker_intents": {
            "type": "object",
            "additionalProperties": {"type": "string"}
        },
        "temporal_context": {"type": "string"},
        "entities": {
            "type": "object",
            "properties": {
                "locations": {"type": "array", "items": {"type": "string"}},
                "people": {"type": "array", "items": {"type": "string"}},
                "media": {"type": "array", "items": {"type": "string"}},
                "events": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["locations", "people", "media", "events"]
        },
        "emotions": {
            "type": "object",
            "properties": {
                "dominant": {"type": "string"},
                "tone": {"type": "string"},
                "tension_level": {"type": "string", "enum": ["low", "medium", "high"]}
            },
            "required": ["dominant", "tone", "tension_level"]
        },
        "interaction_pattern": {"type": ["string", "null"]},
        "initiative": {"type": "string"},
        "emotional_shift": {"type": "string"},
        "open_loops": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": [
        "narrative_summary", "questions", "speaker_intents", 
        "temporal_context", "entities", "emotions", 
        "interaction_pattern", "initiative", "emotional_shift", "open_loops"
    ]
}

CONVERSATION_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "main_topics": {
            "type": "array",
            "items": {"type": "string"}
        },
        "relationship_dynamic": {"type": "string"},
        "notable_events": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["summary", "main_topics", "relationship_dynamic", "notable_events"]
}

PERIOD_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "topics": {
            "type": "array",
            "items": {"type": "string"}
        },
        "mood": {"type": "string"}
    },
    "required": ["summary", "topics", "mood"]
}

QUERY_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {"type": "string", "enum": ["analytics", "retrieval"]},
        "rewritten_query": {"type": "string"},
        "intent": {"type": "string", "enum": ["specific_fact", "broad_summary", "complex_reasoning"]},
        "date_range": {
            "type": ["object", "null"],
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"}
            },
            "required": ["start", "end"]
        }
    },
    "required": ["mode", "rewritten_query", "intent", "date_range"]
}
