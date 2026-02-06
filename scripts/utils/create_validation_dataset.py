#!/usr/bin/env python3
"""
Phase 0: Create a representative validation dataset for complexity analysis.

Purpose:
  - Select ~50-100 chunks covering the spectrum of complexity
  - Calculate baseline metrics for each chunk
  - Export for human review and benchmark comparison

Metrics calculated:
  1. Participants (count)
  2. Messages (count)
  3. Average tokens per message (estimated)
  4. Media/links density
  5. Chunk size (message count)
  6. Lexical diversity (unique words / sqrt(total words))
  7. Dialogue patterns (questions + exclamations + emojis per message)

Output: validation_dataset.json with selected chunks and computed metrics
"""
import json
import argparse
import math
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict


def estimate_tokens(text: str) -> int:
    """Rough estimation: ~4 chars per token (GPT rule of thumb)."""
    return len(text) // 4


def count_dialogue_markers(text: str) -> Tuple[int, int, int]:
    """Count questions, exclamations, and emoji-like patterns."""
    questions = len(re.findall(r'\?', text))
    exclamations = len(re.findall(r'!', text))
    # Simple emoji detection: common emoji patterns
    emoji_pattern = r'[\U0001F300-\U0001F9FF]|[😀-🙏]'
    emojis = len(re.findall(emoji_pattern, text))
    return questions, exclamations, emojis


def calculate_lexical_diversity(text: str) -> float:
    """
    Calculate normalized lexical diversity using MATTR approximation.
    Formula: unique_words / sqrt(total_words)

    This normalizes for text length, preventing short texts from having
    artificially high diversity ratios.
    """
    # Simple tokenization: split on whitespace and punctuation
    words = re.findall(r'\b\w+\b', text.lower())
    if not words:
        return 0.0

    total_words = len(words)
    unique_words = len(set(words))

    # Normalized metric
    if total_words < 2:
        return 0.0

    diversity = unique_words / math.sqrt(total_words)
    return min(diversity, 1.0)  # Cap at 1.0


def count_media_and_links(text: str) -> int:
    """Count mentions of media files and URLs/links."""
    # Count URL patterns
    urls = len(re.findall(r'http[s]?://\S+|www\.\S+', text))
    # Count file patterns (.jpg, .mp4, .pdf, etc.)
    files = len(re.findall(r'\.\w{2,4}\b', text))
    # Count media keywords (photo, image, video, etc.) - in French and English
    media_keywords = re.findall(
        r'\b(photo|image|vidéo|video|fichier|file|lien|link|mp4|jpg|png|pdf|document)\b',
        text, re.IGNORECASE
    )
    return urls + files + len(media_keywords)


def compute_complexity_metrics(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute all complexity metrics for a chunk.

    Returns:
        Dict with computed metrics
    """
    participants = chunk.get('participants', [])
    content = chunk.get('content', '')
    message_count = chunk.get('message_count', 0)

    # 1. Participant count
    participant_count = len(participants)

    # 2. Message count (already available)
    # 3. Average tokens per message
    total_tokens = estimate_tokens(content)
    tokens_per_msg = total_tokens / max(message_count, 1)

    # 4. Media/links density
    media_count = count_media_and_links(content)
    media_density = media_count / max(message_count, 1)

    # 5. Chunk size (message count - already have it)

    # 6. Lexical diversity
    lexical_diversity = calculate_lexical_diversity(content)

    # 7. Dialogue patterns
    questions, exclamations, emojis = count_dialogue_markers(content)
    dialogue_markers = (questions + exclamations + emojis) / max(message_count, 1)

    return {
        'participant_count': participant_count,
        'message_count': message_count,
        'tokens_per_message': tokens_per_msg,
        'media_density': media_density,
        'lexical_diversity': lexical_diversity,
        'dialogue_markers_per_message': dialogue_markers,
        'total_tokens': total_tokens,
        'media_count': media_count,
        'questions_count': questions,
        'exclamations_count': exclamations,
        'emoji_count': emojis,
    }


def classify_chunk_complexity(metrics: Dict[str, Any]) -> Tuple[str, float]:
    """
    Classify chunk as simple/medium/complex based on metrics.

    Simple heuristic (will be refined in Phase 1):
    - Simple: < 3 participants, < 15 messages, < 50 tokens/msg, < 10% media
    - Complex: >= 3 participants AND (>= 30 messages OR >= 100 tokens/msg OR >= 30% media)
    - Medium: everything else

    Returns:
        (category, score) where score is 0.0-1.0 for ranking within category
    """
    participants = metrics['participant_count']
    messages = metrics['message_count']
    tokens_per_msg = metrics['tokens_per_message']
    media_density = metrics['media_density']
    lexical_div = metrics['lexical_diversity']
    dialogue_markers = metrics['dialogue_markers_per_message']

    # Simple heuristic score (0-1)
    score = 0.0

    # Participants factor
    if participants >= 5:
        score += 1.0 * 0.20
    elif participants >= 3:
        score += 0.5 * 0.20

    # Density factor
    if tokens_per_msg >= 100:
        score += 1.0 * 0.25
    elif tokens_per_msg >= 50:
        score += 0.5 * 0.25

    # Media factor
    if media_density >= 0.30:
        score += 1.0 * 0.15
    elif media_density >= 0.10:
        score += 0.5 * 0.15

    # Size factor
    if messages >= 35:
        score += 1.0 * 0.15
    elif messages >= 15:
        score += 0.5 * 0.15

    # Lexical diversity factor
    if lexical_div >= 0.8:
        score += 1.0 * 0.15
    elif lexical_div >= 0.5:
        score += 0.5 * 0.15

    # Dialogue factor
    if dialogue_markers >= 0.5:
        score += 1.0 * 0.10
    elif dialogue_markers >= 0.2:
        score += 0.5 * 0.10

    # Classify
    if score < 0.35:
        return 'simple', score
    elif score >= 0.65:
        return 'complex', score
    else:
        return 'medium', score


def select_representative_chunks(chunks: List[Dict[str, Any]],
                                  target_per_category: int = 20) -> List[Dict[str, Any]]:
    """
    Select representative chunks covering each complexity category.

    Args:
        chunks: All loaded chunks
        target_per_category: Target number of chunks per category

    Returns:
        Selected chunks with metrics and classification
    """
    # Compute metrics and classify all chunks
    classified = defaultdict(list)

    for chunk in chunks:
        metrics = compute_complexity_metrics(chunk)
        category, score = classify_chunk_complexity(metrics)

        chunk['metrics'] = metrics
        chunk['classification'] = {
            'category': category,
            'score': score
        }

        classified[category].append(chunk)

    # Sort each category by score (to get good distribution)
    for category in classified:
        classified[category].sort(key=lambda c: c['classification']['score'])

    # Select evenly distributed chunks from each category
    selected = []
    for category in ['simple', 'medium', 'complex']:
        chunks_in_cat = classified.get(category, [])
        if chunks_in_cat:
            # Take chunks at different positions to get variety within category
            step = max(1, len(chunks_in_cat) // target_per_category)
            for i in range(0, len(chunks_in_cat), step):
                if len([c for c in selected if c['classification']['category'] == category]) < target_per_category:
                    selected.append(chunks_in_cat[i])

    # If we have less than target_per_category for a category, add more
    for category in ['simple', 'medium', 'complex']:
        current_count = len([c for c in selected if c['classification']['category'] == category])
        if current_count < target_per_category:
            chunks_in_cat = classified.get(category, [])
            needed = target_per_category - current_count
            for chunk in chunks_in_cat:
                if chunk not in selected and needed > 0:
                    selected.append(chunk)
                    needed -= 1

    return selected


def main():
    parser = argparse.ArgumentParser(
        description='Create validation dataset for complexity analysis'
    )
    parser.add_argument(
        '--input',
        default='/Users/ismaelsebbane/dev/lab/instagram-assistant/rag_data/chunks.json',
        help='Path to chunks.json'
    )
    parser.add_argument(
        '--output',
        default='/Users/ismaelsebbane/dev/lab/instagram-assistant/validation_dataset.json',
        help='Output path for validation dataset'
    )
    parser.add_argument(
        '--per-category',
        type=int,
        default=20,
        help='Target chunks per complexity category (default: 20)'
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return 1

    print(f"📂 Loading chunks from {input_path}...")
    with open(input_path) as f:
        chunks = json.load(f)

    print(f"✅ Loaded {len(chunks)} chunks")

    print(f"🔍 Computing metrics for all chunks...")
    selected = select_representative_chunks(chunks, target_per_category=args.per_category)

    # Summary statistics
    simple_count = len([c for c in selected if c['classification']['category'] == 'simple'])
    medium_count = len([c for c in selected if c['classification']['category'] == 'medium'])
    complex_count = len([c for c in selected if c['classification']['category'] == 'complex'])

    print(f"""
✅ Dataset Creation Summary
============================
Total chunks selected: {len(selected)}
  - Simple:  {simple_count} chunks
  - Medium:  {medium_count} chunks
  - Complex: {complex_count} chunks

Metrics computed for all chunks.
Saving to {output_path}...
""")

    # Prepare output (keep essential fields to reduce file size)
    output_chunks = []
    for chunk in selected:
        output_chunk = {
            'chunk_id': chunk.get('chunk_id'),
            'conversation_id': chunk.get('conversation_id'),
            'participants': chunk.get('participants'),
            'date_start': chunk.get('date_start'),
            'date_end': chunk.get('date_end'),
            'message_count': chunk.get('message_count'),
            'content': chunk.get('content'),
            'metrics': chunk.get('metrics'),
            'classification': chunk.get('classification'),
        }
        output_chunks.append(output_chunk)

    # Save
    with open(output_path, 'w') as f:
        json.dump(output_chunks, f, indent=2, ensure_ascii=False)

    print(f"💾 Saved {len(output_chunks)} chunks to {output_path}")

    # Print distribution table
    print(f"\n📊 Distribution Analysis:")
    print(f"{'Category':<10} {'Count':<8} {'Avg Score':<12} {'Avg Msgs':<12} {'Avg Tokens/Msg':<15}")
    print("-" * 60)

    for category in ['simple', 'medium', 'complex']:
        category_chunks = [c for c in selected if c['classification']['category'] == category]
        if category_chunks:
            avg_score = sum(c['classification']['score'] for c in category_chunks) / len(category_chunks)
            avg_msgs = sum(c['message_count'] for c in category_chunks) / len(category_chunks)
            avg_tokens = sum(c['metrics']['tokens_per_message'] for c in category_chunks) / len(category_chunks)
            print(f"{category:<10} {len(category_chunks):<8} {avg_score:<12.3f} {avg_msgs:<12.1f} {avg_tokens:<15.1f}")

    print(f"\n✅ Validation dataset ready for benchmarking!")
    return 0


if __name__ == '__main__':
    exit(main())
