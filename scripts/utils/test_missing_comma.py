import json
import re

# Constructing malformed JSON strings explicitly
# Example 1: Missing comma after property
ex1 = """{
  "summary": "text"
  "questions": []
}"""

# Example 2: Missing comma in list
ex2 = """{
  "list": [
    "item1"
    "item2"
  ]
}"""

examples = [ex1, ex2]

def fix_json(text):
    lines = text.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        line = line.rstrip() # remove trailing whitespace
        
        # --- Fix 1: Unescaped quotes ---
        if ':' in line and '"' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                key_part = parts[0]
                val_part = parts[1].strip()
                if val_part.startswith('"') and (val_part.endswith(',') or val_part.endswith('"')):
                    has_comma = False
                    if val_part.endswith(','):
                        val_part = val_part[:-1]
                        has_comma = True
                    if len(val_part) >= 2:
                        content = val_part[1:-1]
                        if '"' in content:
                            content = content.replace('"', '\"')
                            val_part = f'"{content}"'
                            if has_comma:
                                val_part += ','
                            line = f"{key_part}: {val_part}"
        
        # --- Fix 2: Missing commas ---
        next_line = None
        for j in range(i + 1, len(lines)):
            if lines[j].strip():
                next_line = lines[j].strip()
                break
        
        if next_line:
            stripped = line.strip()
            # If current line ends with " or ] or }
            if stripped.endswith('"') or stripped.endswith(']') or stripped.endswith('}'):
                # And next line starts with " (key or string) or { or [
                if next_line.startswith('"') or next_line.startswith('{') or next_line.startswith('['):
                     line += ","

        fixed_lines.append(line)
            
    return '\n'.join(fixed_lines)

print("-- Testing Fix --")
for i, ex in enumerate(examples):
    print(f"Example {i+1}:")
    try:
        json.loads(ex)
        print("Original is valid (unexpected)")
    except Exception as e:
        print(f"Original Invalid: {e}")
        
    fixed = fix_json(ex)
    try:
        json.loads(fixed)
        print("✅ Fixed Valid JSON")
    except Exception as e:
        print(f"❌ Fixed Invalid JSON: {e}")
        print("Fixed content:")
        print(fixed)
    print("-" * 20)