
import json
import re

examples = [
    "{\n  \"narrative_summary\": \"Ismaël partage une anecdote humoristique sur une \"partenaire de poisse\" (un animal exotique, le zebu), générant une réaction positive et légère de l'autre partie\",\n  \"questions\": []\n}",
    "{\n  \"speaker_intents\": {\n    \"Ismaël\": \"Exprimer son indignation et sa frustration face à l'accident, tout en cherchant à clarifier les dégâts (carrosserie vs égratignure).\",\n    \"🧃🛏️\": \"Atténuer la gravité de la situation, minimiser les risques (prie pour une \"solution\")\"\n  }\n}"
]

def fix_json(text):
    # Strategy: 
    # 1. Identify all content that looks like "key": "value"
    # 2. Extract the value part.
    # 3. Inside the value part, escape any quotes.
    
    # Simple regex for top-level fields (doesn't handle nested objects well)
    # text = re.sub(r'":\s*"([^"]*)"([^"]*)"', r'"\1"\2"', text)
    
    # Better approach: Use the fact that valid keys are "key":
    # valid string starts with " and ends with " followed by , or } or ] or \s
    
    # Let's try to match "key": "VALUE" where VALUE contains quotes
    # Pattern: "key":\s*" (capture until lookahead sees ", or "} or "])
    
    # Actually, the issue is specifically unescaped quotes inside the value string.
    # We can try to replace " that is NOT:
    # 1. At the start of a value (preceded by :\s*)
    # 2. At the end of a value (followed by \s*[,}\]])
    # 3. Part of a key (followed by \s*:)
    # 4. Start of a key (preceded by { or ,)
    
    # This is hard with regex. 
    # Alternative: The model outputs invalid JSON.
    # The specific error seen is: "text "quoted" text"
    
    def replace_inner_quotes(match):
        full_str = match.group(1)
        # Escape quotes that are not already escaped
        fixed = full_str.replace('"', '\\"')
        return f': "{fixed}"'

    # Regex to capture the content of a string value, assuming it might contain quotes
    # Look for: "key": "CONTENT" [,}\]]
    # Limitation: greedy match might consume too much if multiple fields on one line?
    # Usually LLM outputs multiline JSON.
    
    # Match: "key": " ... " ... "
    # We can rely on the fact that keys don't have spaces usually, or at least no newlines.
    
    # Try 1: Fix specific pattern " ... " ... " on a single line
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        # Check if line has "key": "value" pattern
        if ':' in line and '"' in line:
            # Split by first colon
            parts = line.split(':', 1)
            if len(parts) == 2:
                key_part = parts[0]
                val_part = parts[1].strip()
                
                # If value starts and ends with ", check for middle quotes
                if val_part.startswith('"') and (val_part.endswith(',') or val_part.endswith('"')):
                    # Remove trailing comma if exists
                    has_comma = False
                    if val_part.endswith(','):
                        val_part = val_part[:-1]
                        has_comma = True
                    
                    content = val_part[1:-1] # Strip outer quotes
                    if '"' in content:
                        # Escape them!
                        content = content.replace('"', '\\"')
                        val_part = f'"{content}"'
                        if has_comma:
                            val_part += ','
                        
                        line = f"{key_part}: {val_part}"
        fixed_lines.append(line)
        
    return '\n'.join(fixed_lines)

print("---"" Testing Fix ---")
for ex in examples:
    print(f"Original:\n{ex}")
    fixed = fix_json(ex)
    print(f"Fixed:\n{fixed}")
    try:
        json.loads(fixed)
        print("✅ Valid JSON")
    except Exception as e:
        print(f"❌ Invalid JSON: {e}")
    print("-" * 20)
