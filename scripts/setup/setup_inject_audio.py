#!/usr/bin/env python3
"""
Audio Injection Script.

Injects audio transcriptions from cache into existing chunks that have [Audio] placeholders.
Marks modified chunks for re-enrichment.

Usage:
    python scripts/setup/setup_inject_audio.py              # Apply injection
    python scripts/setup/setup_inject_audio.py --dry-run    # Preview only
    python scripts/setup/setup_inject_audio.py --reenrich   # Also re-enrich modified chunks
"""
import sys
import json
import re
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.core.models import Chunk
from rag_pipeline.indexing.chunker import ConversationChunker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def build_audio_timestamp_map(source_dir: Path) -> Dict[str, datetime]:
    """
    Scan original JSONs to build a map of audio filename -> timestamp.
    
    Returns:
        {audio_filename: datetime} e.g. {"285756700457691.mp4": datetime(...)}
    """
    audio_map = {}
    json_files = list(source_dir.glob("**/message_*.json"))
    
    logger.info(f"📂 Scanning {len(json_files)} JSON files for audio timestamps...")
    
    for json_path in json_files:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for msg in data.get('messages', []):
                if 'audio_files' in msg:
                    timestamp_ms = msg.get('timestamp_ms', 0)
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
                    
                    for audio_item in msg['audio_files']:
                        uri = audio_item.get('uri', '')
                        filename = Path(uri).name  # e.g. "285756700457691.mp4"
                        audio_map[filename] = timestamp
                        
        except Exception as e:
            logger.debug(f"Error reading {json_path}: {e}")
            continue
    
    logger.info(f"📊 Found {len(audio_map)} audio files with timestamps")
    return audio_map


def load_transcription_cache(config: Config) -> Dict[str, str]:
    """
    Load transcription cache and return {filename: transcript}.
    """
    cache_path = config.audio_cache_path
    if not cache_path.exists():
        logger.warning(f"⚠️ Audio cache not found: {cache_path}")
        return {}
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    
    # Convert {hash: {file_name, transcript, ...}} to {filename: transcript}
    result = {}
    for entry in cache.values():
        filename = entry.get('file_name')
        transcript = entry.get('transcript')
        if filename and transcript:
            result[filename] = transcript
    
    logger.info(f"📦 Loaded {len(result)} transcriptions from cache")
    return result


def extract_audio_lines(content: str) -> List[Tuple[int, datetime, str]]:
    """
    Find all [Audio] lines in chunk content.
    
    Returns:
        List of (line_index, timestamp, full_line)
    """
    pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] .+?: .*\[Audio\]')
    results = []
    
    for i, line in enumerate(content.split('\n')):
        match = pattern.match(line)
        if match:
            timestamp_str = match.group(1)
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M')
            results.append((i, timestamp, line))
    
    return results


def inject_audio_into_chunk(
    chunk: Chunk,
    audio_timestamp_map: Dict[str, datetime],
    transcription_cache: Dict[str, str]
) -> Tuple[bool, int]:
    """
    Inject audio transcriptions into a chunk's content.
    
    Returns:
        (was_modified, injection_count)
    """
    audio_lines = extract_audio_lines(chunk.content)
    if not audio_lines:
        return False, 0
    
    # Find audio files that match chunk's date range and conversation
    # Convert chunk dates to datetime for comparison
    chunk_start = datetime.strptime(chunk.date_start, '%Y-%m-%d %H:%M:%S')
    chunk_end = datetime.strptime(chunk.date_end, '%Y-%m-%d %H:%M:%S')
    
    # Get audio files in time range
    matching_audios = []
    for filename, audio_ts in audio_timestamp_map.items():
        # Check if audio timestamp is within chunk's date range (with some tolerance)
        if chunk_start <= audio_ts <= chunk_end:
            transcript = transcription_cache.get(filename)
            if transcript:
                matching_audios.append((audio_ts, filename, transcript))
    
    # Sort by timestamp
    matching_audios.sort(key=lambda x: x[0])
    
    if not matching_audios:
        return False, 0
    
    # Match audio lines to transcriptions by timestamp
    lines = chunk.content.split('\n')
    injection_count = 0
    
    for line_idx, line_ts, line in audio_lines:
        # Find best matching audio by closest timestamp
        best_match = None
        best_diff = float('inf')
        
        for audio_ts, filename, transcript in matching_audios:
            diff = abs((audio_ts - line_ts).total_seconds())
            if diff < best_diff and diff < 120:  # Within 2 minutes
                best_diff = diff
                best_match = (filename, transcript)
        
        if best_match:
            filename, transcript = best_match
            # Truncate long transcriptions for readability
            display_transcript = transcript[:200] + "..." if len(transcript) > 200 else transcript
            # Replace [Audio] with [Audio: "transcription"]
            new_line = lines[line_idx].replace('[Audio]', f'[Audio: "{display_transcript}"]')
            lines[line_idx] = new_line
            injection_count += 1
            # Remove used audio to avoid double-matching
            matching_audios = [(ts, fn, tr) for ts, fn, tr in matching_audios if fn != filename]
    
    if injection_count > 0:
        chunk.content = '\n'.join(lines)
        chunk.needs_reenrichment = True
        return True, injection_count
    
    return False, 0


def run(config: Config = None, dry_run: bool = False, reenrich: bool = False) -> bool:
    """
    Main entry point for audio injection.
    """
    config = config or default_config
    source_dir = Path("original_import_folders")
    
    if not source_dir.exists():
        logger.error(f"❌ Source directory not found: {source_dir}")
        return False
    
    # 1. Build audio timestamp map from original JSONs
    audio_timestamp_map = build_audio_timestamp_map(source_dir)
    if not audio_timestamp_map:
        logger.warning("⚠️ No audio files found in source")
        return False
    
    # 2. Load transcription cache
    transcription_cache = load_transcription_cache(config)
    if not transcription_cache:
        logger.warning("⚠️ No transcriptions in cache - run setup_transcriptions.py first")
        return False
    
    # 3. Load existing chunks
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    
    if not chunks:
        logger.error("❌ No chunks found")
        return False
    
    logger.info(f"📝 Processing {len(chunks)} chunks...")
    
    # 4. Process chunks
    modified_count = 0
    total_injections = 0
    
    for chunk in chunks:
        was_modified, count = inject_audio_into_chunk(
            chunk, audio_timestamp_map, transcription_cache
        )
        if was_modified:
            modified_count += 1
            total_injections += count
    
    # 5. Summary
    logger.info("=" * 50)
    logger.info("📊 AUDIO INJECTION SUMMARY")
    logger.info("=" * 50)
    logger.info(f"📝 Chunks processed:   {len(chunks)}")
    logger.info(f"✅ Chunks modified:    {modified_count}")
    logger.info(f"🎙️  Audio injected:     {total_injections}")
    logger.info(f"🔄 Need re-enrichment: {modified_count}")
    
    if dry_run:
        logger.info("🔍 DRY RUN - no changes saved")
        return True
    
    # 6. Save chunks
    chunker.save_chunks(chunks)
    logger.info(f"💾 Saved to {config.chunks_cache_path}")
    
    # 7. Optionally re-enrich
    if reenrich and modified_count > 0:
        logger.info("🔄 Re-enriching modified chunks...")
        import setup_enrich
        setup_enrich.run(config, only_needs_reenrichment=True)
    
    return True


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Inject audio transcriptions into chunks")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--reenrich", action="store_true", help="Re-enrich modified chunks")
    args = parser.parse_args()
    
    run(dry_run=args.dry_run, reenrich=args.reenrich)


if __name__ == "__main__":
    main()
