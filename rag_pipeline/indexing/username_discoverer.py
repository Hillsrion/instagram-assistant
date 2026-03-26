"""
Utility for automated username discovery from Instagram exports.
Identifies the account owner by analyzing participant frequencies.
"""
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter
from rag_pipeline.core.config import Config
from rag_pipeline.indexing.parser import InstagramParser

def discover_usernames(config: Config) -> List[str]:
    """
    Analyzes all conversations to find the most frequent participants.
    The account owner is typically present in all or most conversations.
    """
    files = list(config.conversations_dir.glob('*.txt'))
    if not files:
        return []

    parser = InstagramParser()
    participant_counts = Counter()
    total_files = len(files)

    print(f"🔍 Analyzing {total_files} conversations for username discovery...")

    for file_path in files:
        try:
            metadata, _ = parser.parse_file(file_path)
            participants = metadata.get('participants', [])
            for p in participants:
                # Basic cleaning
                p_clean = p.strip()
                if p_clean and p_clean.lower() not in ["me", "user"]:
                    participant_counts[p_clean] += 1
        except Exception:
            continue

    if not participant_counts:
        return []

    # Filter participants present in more than 90% of conversations
    candidates = []
    for name, count in participant_counts.most_common():
        presence_ratio = count / total_files
        if presence_ratio >= 0.9:
            candidates.append(name)
        elif not candidates and presence_ratio >= 0.5:
            # Fallback to the most common one if none cross 90%
            candidates.append(name)
            break
    
    # Sort candidates by frequency (highest first)
    return candidates
