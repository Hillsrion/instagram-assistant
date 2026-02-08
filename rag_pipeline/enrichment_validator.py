"""
Validation logic for LLM-generated enrichment data.
Detects corruption, repetition loops, and low-quality/sparse outputs.
"""
import re
from typing import Tuple, List, Dict, Optional

def is_corrupted_output(raw: str) -> bool:
    """
    Detect corrupted LLM outputs (repetition loops, truncation).
    
    Returns True if the output looks corrupted and should be retried.
    """
    if not raw:
        return True
    
    # Pattern: 10+ identical characters in a row (repetition loop)
    if re.search(r'(.)\1{10,}', raw):
        return True
    
    # Very short output after stripping markdown (likely truncated)
    stripped = raw.strip()
    if '```' in stripped:
        # Extract content between markdown fences
        parts = stripped.split('```')
        if len(parts) >= 2:
            stripped = parts[1].replace('json', '').strip()
    
    if len(stripped) < 50:
        return True
    
    return False

def is_low_quality_enrichment(data: Tuple) -> bool:
    """
    Detect low-quality enrichments where the model produced a summary
    but left other critical fields empty.
    
    Args:
        data: Tuple (summary, questions, intents, temporal, entities, emotions, 
                    pattern, initiative, shift, loops)
    
    Returns:
        True if enrichment is too sparse.
    """
    (narrative_summary, hypothetical_questions, speaker_intents, 
     temporal_context, entities, emotions, interaction_pattern,
     initiative, emotional_shift, open_loops) = data
    
    # If there's no summary, it's a hard failure
    if not narrative_summary:
        return False
    
    # Count populated fields (excluding summary)
    populated = 0
    
    if hypothetical_questions and len(hypothetical_questions) > 0:
        populated += 1
    
    if speaker_intents and len(speaker_intents) > 0:
        populated += 1
    
    if temporal_context and len(temporal_context.strip()) > 0:
        populated += 1
    
    if entities and isinstance(entities, dict):
        if any(v for v in entities.values() if v):
            populated += 1
    
    if emotions and isinstance(emotions, dict) and emotions.get('dominant'):
        populated += 1
    
    if interaction_pattern:
        populated += 1
    
    if initiative:
        populated += 1
    
    if emotional_shift:
        populated += 1
    
    if open_loops and len(open_loops) > 0:
        populated += 1
    
    # If less than 3 out of 9 fields are populated, it's low quality
    return populated < 3
