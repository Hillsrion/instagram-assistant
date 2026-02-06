"""
Utility functions for cleaning and parsing LLM-generated JSON.
"""
import json
import re
from typing import Any, Dict, List, Tuple, Optional

def clean_llm_json(json_str: str) -> str:
    """Cleans JSON string from common LLM artifacts and fixes unescaped quotes."""
    cleaned = json_str.strip()
    
    # Remove markdown code blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    
    if "```" in cleaned:
        cleaned = cleaned.split("```")[0]
        
    cleaned = cleaned.strip()
    
    # If it doesn't start with {, try to find it
    if not cleaned.startswith("{") and "{" in cleaned:
        cleaned = cleaned[cleaned.find("{"):]
        
    # Fix trailing commas before closing symbols
    cleaned = re.sub(r",\s*([\"\]\}})", r"\1", cleaned)
    
    # Robust fix for unescaped quotes inside string values
    lines = cleaned.split('\n')
    fixed_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        
        # Case 1: "key": "value"
        if ':' in line and '"' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                key_part = parts[0]
                val_part = parts[1].strip()
                if val_part.startswith('"') and (val_part.endswith(',') or val_part.endswith('"')):
                    has_comma = val_part.endswith(',')
                    content = val_part[1:-2] if has_comma else val_part[1:-1]
                    if '"' in content:
                        content = content.replace('"', '\"')
                        val_part = f'"{content}"'
                        if has_comma: val_part += ','
                        line = f"{key_part}: {val_part}"
        
        # Case 2: List item: "value" or "value",
        elif stripped_line.startswith('"') and (stripped_line.endswith('"') or stripped_line.endswith('",')):
            has_comma = stripped_line.endswith(',')
            content_part = stripped_line[1:-2] if has_comma else stripped_line[1:-1]
            if '"' in content_part:
                fixed_content = content_part.replace('"', '\"')
                indent = line[:line.find('"')]
                line = f'{indent}"{fixed_content}"'
                if has_comma: line += ","
        
        fixed_lines.append(line)
    
    # Second pass: Fix missing commas between fields
    final_lines = []
    for i, line in enumerate(fixed_lines):
        line = line.rstrip()
        next_line = None
        for j in range(i + 1, len(fixed_lines)):
            if fixed_lines[j].strip():
                next_line = fixed_lines[j].strip()
                break
        if next_line:
            stripped = line.strip()
            if stripped.endswith('"') or stripped.endswith(']') or stripped.endswith('}'):
                if next_line.startswith('"') or next_line.startswith('{') or next_line.startswith('['):
                     line += ","
        final_lines.append(line)
        
    return '\n'.join(final_lines)

def repair_and_load_json(json_str: str) -> Dict[str, Any]:
    """Attempts to repair and load a potentially truncated or malformed JSON."""
    if not json_str:
        raise ValueError("Empty JSON string")
        
    cleaned = clean_llm_json(json_str)
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Fallback: if it's truncated, try to close the JSON manually
        if "{" in cleaned and not cleaned.endswith("}"):
            try:
                # Very simple recovery for partial objects
                recovered = cleaned
                if recovered.count("{") > recovered.count("}"):
                     recovered += "}" * (recovered.count("{") - recovered.count("}") )
                return json.loads(recovered)
            except:
                raise e
        else:
            raise e

def parse_enrichment_data(data: dict) -> Tuple:
    """Robustly parse the JSON data specifically for conversation enrichment."""
    
    # Helper to ensure string lists
    def ensure_str_list(lst):
        if isinstance(lst, list):
            return [str(x) if not isinstance(x, str) else x for x in lst]
        if isinstance(lst, str) and lst.strip():
            return [lst.strip()]
        return []

    # Helper to ensure string dict values
    def ensure_str_dict(dct):
        if isinstance(dct, dict):
             return {str(k): (", ".join(v) if isinstance(v, list) else str(v)) for k, v in dct.items()}
        return {}

    summary = data.get("narrative_summary", "")
    if isinstance(summary, list):
        summary = " ".join(ensure_str_list(summary))
    summary = str(summary)

    questions = ensure_str_list(data.get("questions", []))
    speaker_intents = ensure_str_dict(data.get("speaker_intents", {{}}))
    
    temporal_context = data.get("temporal_context", "")
    if isinstance(temporal_context, list):
        temporal_context = ", ".join(ensure_str_list(temporal_context))
    else:
        temporal_context = str(temporal_context)
    
    entities = data.get("entities", {{}})
    cleaned_entities = {{}}
    if isinstance(entities, dict):
        for key, val in entities.items():
            # Some LLMs nest emotions or other fields inside entities
            if key in ["emotions", "interaction_pattern", "initiative", "emotional_shift", "open_loops", "speaker_intents"]:
                continue
            
            if isinstance(val, list):
                cleaned_entities[key] = ensure_str_list(val)
            elif isinstance(val, dict):
                # Flatten nested dicts or just take keys as strings
                items = []
                for k2, v2 in val.items():
                    if isinstance(v2, list):
                        items.extend([f"{k2}: {i}" for i in ensure_str_list(v2)])
                    else:
                        items.append(f"{k2}: {v2}")
                cleaned_entities[key] = items
            else:
                cleaned_entities[key] = [str(val)]
    
    # Extract optional fields that might be nested or direct
    def get_field(key, source_dict):
        val = source_dict.get(key)
        if not val and isinstance(source_dict.get("entities"), dict):
            val = source_dict["entities"].get(key)
        return val

    emotions = get_field("emotions", data)
    if not isinstance(emotions, dict):
        emotions = {{}}

    interaction_pattern = get_field("interaction_pattern", data)
    initiative = get_field("initiative", data)
    emotional_shift = get_field("emotional_shift", data)
    
    open_loops = get_field("open_loops", data)
    open_loops = ensure_str_list(open_loops)

    return (summary, questions, speaker_intents, temporal_context, cleaned_entities, 
            emotions, interaction_pattern, initiative, emotional_shift, open_loops)
