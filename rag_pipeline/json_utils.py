"""
Robust JSON Parser for LLM-Generated Output.

WHY THIS EXISTS
===============
Local LLMs (Ollama, MLX) frequently generate malformed JSON when asked to produce
structured enrichment data. Common issues include:

1. **Unescaped internal quotes**: LLM writes `"He said "hello" to me"` instead of
   properly escaping the inner quotes as `\"hello\"`.

2. **Missing commas**: LLM forgets commas between properties, especially after
   multi-line values:
   ```
   "summary": "some text"
   "questions": [...]  // Missing comma!
   ```

3. **Inline comments**: LLM adds `// comment` annotations which are invalid JSON.

4. **Orphan values in objects**: LLM produces keys without values like:
   ```
   "speaker_intents": {
     "Alice": "She wants X",
     "No other participant"  // This is not a valid key:value pair!
   }
   ```

HOW IT WORKS
============
The parser uses a multi-stage approach:

1. **Markdown stripping**: Removes ```json fences if present.

2. **Comment removal**: Pre-processes line-by-line to strip `//` comments
   outside of string literals.

3. **State-machine parsing**: Character-by-character scan that tracks:
   - Whether we're inside a string (`in_string`)
   - Whether the previous char was an escape (`escaped`)
   - Whether a value just ended (`last_value_ended`)
   
   Key logic:
   - **Quote detection**: Uses look-ahead to determine if a `"` is structural
     (followed by `:,}]"` or end-of-input) or internal (needs escaping).
   - **Missing comma insertion**: If a new string starts after a value ended
     without a comma, one is inserted.

4. **Fallback repairs** in `repair_and_load_json`:
   - Removes orphan string values in objects (`, "string"` not followed by `:`)
   - Auto-closes truncated JSON by adding missing `}`

USAGE
=====
```python
from rag_pipeline.json_utils import repair_and_load_json, parse_enrichment_data

raw_llm_output = '''```json
{"summary": "He said "hello"", "tags": ["a", "b"]}
```'''

data = repair_and_load_json(raw_llm_output)
enrichment = parse_enrichment_data(data)
```
"""
import re
import json
from typing import Any, Dict, List, Tuple, Optional

def clean_llm_json(json_str: str) -> str:
    """
    Cleans JSON string with high robustness using a state-machine parser.
    Handles:
    - Unescaped internal quotes (e.g., "He said "hello" to me")
    - Missing commas between properties
    - // comments from LLM
    - Trailing commas
    """
    if not json_str:
        return ""

    # 1. Basic markdown stripping
    cleaned = json_str.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0]
    cleaned = cleaned.strip()

    # 2. Extract object boundary
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return cleaned
    
    raw = cleaned[start_idx : end_idx + 1]
    
    # 3. Pre-process: remove // comments outside strings
    lines = raw.split('\n')
    processed_lines = []
    temp_in_string = False
    temp_escaped = False
    for line in lines:
        clean_line_chars = []
        temp_in_string = False  # Reset per line for simplicity in comment detection
        temp_escaped = False
        comment_start = -1
        for ci, c in enumerate(line):
            if temp_escaped:
                temp_escaped = False
            elif c == '\\':
                temp_escaped = True
            elif c == '"':
                temp_in_string = not temp_in_string
            elif not temp_in_string and c == '/' and ci + 1 < len(line) and line[ci + 1] == '/':
                comment_start = ci
                break
        if comment_start != -1:
            clean_line_chars = list(line[:comment_start])
        else:
            clean_line_chars = list(line)
        processed_lines.append(''.join(clean_line_chars))
    raw = '\n'.join(processed_lines)
    
    # 4. State machine parser
    # Include '"' because if we see a quote after value, it means missing comma before new key/value
    STRUCTURAL_CHARS = frozenset(':,}]"')
    
    result = []
    in_string = False
    escaped = False
    last_value_ended = False  # True after a string value ends (not after ':')
    
    i = 0
    while i < len(raw):
        char = raw[i]
        
        if escaped:
            escaped = False
            result.append(char)
            i += 1
            continue
            
        if char == '\\':
            escaped = True
            result.append(char)
            i += 1
            continue
        
        if char == '"':
            if not in_string:
                # Starting a string
                # Check if we need to insert a missing comma
                if last_value_ended:
                    # Look backwards: was the last non-whitespace char a structural char?
                    # If not, we need a comma
                    needs_comma = True
                    for ri in range(len(result) - 1, -1, -1):
                        rc = result[ri]
                        if rc.isspace():
                            continue
                        if rc in ',:{[':
                            needs_comma = False
                        break
                    
                    if needs_comma:
                        # Find position to insert comma (before trailing whitespace)
                        insert_pos = len(result)
                        while insert_pos > 0 and result[insert_pos - 1].isspace():
                            insert_pos -= 1
                        result.insert(insert_pos, ',')
                
                in_string = True
                last_value_ended = False
                result.append(char)
            else:
                # Potential end of string - use look-ahead
                # Find first non-whitespace character after this quote
                j = i + 1
                while j < len(raw) and raw[j] in ' \t\n\r':
                    j += 1
                
                is_structural_quote = False
                if j >= len(raw):
                    # End of input - this quote ends the string
                    is_structural_quote = True
                elif raw[j] in STRUCTURAL_CHARS:
                    # Followed by :, }, ], , - this is a structural quote
                    is_structural_quote = True
                
                if is_structural_quote:
                    in_string = False
                    # Only mark value ended if this wasn't a key (next char is not ':')
                    if j < len(raw) and raw[j] == ':':
                        last_value_ended = False  # This was a key
                    else:
                        last_value_ended = True  # This was a value
                    result.append(char)
                else:
                    # Internal quote - escape it
                    result.append('\\')
                    result.append('"')
        
        elif not in_string:
            # Outside string - handle structural characters
            if char == ':':
                last_value_ended = False
                result.append(char)
            elif char == ',':
                last_value_ended = False
                result.append(char)
            elif char == '{':
                last_value_ended = False
                result.append(char)
            elif char == '[':
                last_value_ended = False
                result.append(char)
            elif char in '}]':
                last_value_ended = True
                result.append(char)
            elif char.isspace():
                result.append(char)
            else:
                # Could be true/false/null or numbers
                rem = raw[i:]
                matched = False
                for token in ['true', 'false', 'null']:
                    if rem.startswith(token):
                        # Verify it's a complete token (not part of a word)
                        end_pos = len(token)
                        if len(rem) > end_pos and rem[end_pos].isalnum():
                            continue  # Not a complete token
                        result.extend(list(token))
                        i += len(token) - 1
                        last_value_ended = True
                        matched = True
                        break
                if not matched:
                    result.append(char)
        else:
            # Inside string - escape control characters that JSON doesn't allow
            if char == '\n':
                result.append('\\')
                result.append('n')
            elif char == '\r':
                result.append('\\')
                result.append('r')
            elif char == '\t':
                result.append('\\')
                result.append('t')
            elif ord(char) < 32:
                # Other control characters - escape as unicode
                result.append('\\')
                result.append('u')
                result.append(f'{ord(char):04x}')
            else:
                result.append(char)
        
        i += 1
        
    cleaned = "".join(result)
    
    # 5. Final cleanup: remove trailing commas before } or ]
    cleaned = re.sub(r',(\s*[\}\]])', r'\1', cleaned)
    
    return cleaned

def repair_and_load_json(json_str: str) -> Dict[str, Any]:
    """Attempts to repair and load a potentially truncated or malformed JSON."""
    if not json_str:
        raise ValueError("Empty JSON string")
        
    cleaned = clean_llm_json(json_str)
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Attempt to fix common structural errors
        
        # Fix 1: Remove orphan values in objects (value without key)
        # Pattern: ,"string_without_colon_after" followed by } or ,
        # This handles LLM errors like: {"key": "val", "orphan string"}
        fixed = re.sub(
            r',\s*"([^"\\]|\\.)*"\s*(?=[,}])',  # Match: , "string" followed by , or }
            '',
            cleaned
        )
        if fixed != cleaned:
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass  # Continue with other fixes
        
        # Fix 2: If truncated, try to close the JSON manually
        if "{" in cleaned and not cleaned.endswith("}"):
            try:
                recovered = cleaned
                if recovered.count("{") > recovered.count("}"):
                     recovered += "}" * (recovered.count("{") - recovered.count("}"))
                return json.loads(recovered)
            except json.JSONDecodeError:
                pass
        
        # If all fixes failed, raise the original error
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
    speaker_intents = ensure_str_dict(data.get("speaker_intents", {}))
    
    temporal_context = data.get("temporal_context", "")
    if isinstance(temporal_context, list):
        temporal_context = ", ".join(ensure_str_list(temporal_context))
    else:
        temporal_context = str(temporal_context)
    
    entities = data.get("entities", {})
    cleaned_entities = {}
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
        emotions = {}

    interaction_pattern = get_field("interaction_pattern", data)
    initiative = get_field("initiative", data)
    emotional_shift = get_field("emotional_shift", data)
    
    open_loops = get_field("open_loops", data)
    open_loops = ensure_str_list(open_loops)

    return (summary, questions, speaker_intents, temporal_context, cleaned_entities, 
            emotions, interaction_pattern, initiative, emotional_shift, open_loops)