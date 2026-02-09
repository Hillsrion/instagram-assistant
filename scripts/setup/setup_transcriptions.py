#!/usr/bin/env python3
"""
Audio Transcription Setup.

Scans a directory for audio files and transcribes them using the local MLX model.
Results are automatically cached by the AudioTranscriber.

Usage:
    python scripts/setup/setup_transcriptions.py --source /path/to/instagram_export

Can also be run via the orchestrator:
    python scripts/setup/setup_rag.py --only transcribe
    python scripts/setup/setup_rag.py --with-transcribe
"""
import sys
import argparse
import logging
import time
import os
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Prevent deadlocks
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.audio.audio import AudioTranscriber

# Logging setup - console only (human readable)
LOG_FILE = Path(__file__).parent.parent.parent / "logs" / "setup_transcriptions.jsonl"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def log_jsonl(event: str, **kwargs):
    """Append a structured JSON line to the log file."""
    entry = {"ts": time.strftime('%Y-%m-%dT%H:%M:%S'), "event": event, **kwargs}
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("mistral_common").setLevel(logging.WARNING)


def run(config: Config = None, source_dir: Path = None, force: bool = False) -> bool:
    """
    Run audio transcription for all audio files in the source directory.
    
    Args:
        config: Optional config override
        source_dir: Directory to scan for audio files (default: original_import_folders)
        force: Force re-transcription even if cached
        
    Returns:
        True if successful, False otherwise
    """
    config = config or default_config
    source_dir = source_dir or Path("original_import_folders")
    
    logger.info(f"📁 JSONL logging to: {LOG_FILE}")
    
    if not config.enable_audio_transcription:
        logger.warning("⚠️  Audio transcription is DISABLED in config.")
        logger.warning("    Enable it with ENABLE_AUDIO_TRANSCRIPTION=true in .env")
        return False

    if not source_dir.exists():
        logger.error(f"❌ Source directory not found: {source_dir}")
        return False

    logger.info(f"🔍 Scanning {source_dir} for audio files in 'audio/' subfolders...")
    audio_extensions = ['*.mp4', '*.m4a', '*.mp3', '*.wav', '*.aac']
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(list(source_dir.glob(f"**/audio/{ext}")))

    logger.info(f"🔍 Found {len(audio_files)} audio files.")
    
    logger.info("📦 Initializing transcriber...")
    transcriber = AudioTranscriber()
    
    # Filter out already cached if not force
    logger.info(f"🔍 Filtering cached files...")
    to_process = []
    if force:
        to_process = audio_files
    else:
        for f in audio_files:
            if transcriber.cache.get(f):
                continue
            to_process.append(f)
    
    cached_count = len(audio_files) - len(to_process)
    logger.info(f"📝 Transcribing {len(to_process)} files (skipping {cached_count} cached)...")
    log_jsonl("start", total=len(audio_files), to_process=len(to_process), cached=cached_count)
    
    if not to_process:
        logger.info("✅ Nothing to do!")
        return True

    success_count = 0
    fail_count = 0
    start_time = time.time()

    # Sequential processing
    for i, f in enumerate(to_process):
        elapsed = time.time() - start_time
        avg_per_file = elapsed / (i + 1) if i > 0 else 4.0
        remaining = avg_per_file * (len(to_process) - i)
        eta = time.strftime('%H:%M:%S', time.gmtime(remaining))
        
        logger.info(f"🎙️  [{i+1}/{len(to_process)}] {f.name} (ETA: {eta})")
        file_start = time.time()
        try:
            result = transcriber.transcribe(f)
            duration = time.time() - file_start
            if result:
                success_count += 1
                logger.info(f"   ✨ Success! ({len(result)} chars)")
                log_jsonl("success", file=str(f), chars=len(result), duration=round(duration, 2))
            else:
                fail_count += 1
                logger.warning(f"   ❌ Failed (No result)")
                log_jsonl("fail", file=str(f), reason="no_result", duration=round(duration, 2))
        except Exception as e:
            duration = time.time() - file_start
            logger.error(f"   💥 Error: {e}")
            log_jsonl("error", file=str(f), error=str(e), duration=round(duration, 2))
            fail_count += 1

    # Final save
    transcriber.cache.save()
    
    total_time = time.time() - start_time
    avg_time = total_time / success_count if success_count > 0 else 0
    
    logger.info("="*50)
    logger.info("📊 AUDIO TRANSCRIPTION SUMMARY")
    logger.info("="*50)
    logger.info(f"✅ Successful:      {success_count}")
    logger.info(f"❌ Failed:          {fail_count}")
    logger.info(f"💾 Cached:          {cached_count}")
    logger.info(f"⏱️  Total Time:      {total_time:.1f}s")
    logger.info(f"⚡ Avg/Audio:       {avg_time:.2f}s")
    logger.info(f"📦 Cache saved to:  {transcriber.cache.cache_path}")
    log_jsonl("summary", success=success_count, fail=fail_count, cached=cached_count, 
              total_time=round(total_time, 1), avg_time=round(avg_time, 2))
    logger.info("="*50)
    
    return True


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Batch Transcribe Audio Files.")
    parser.add_argument("--source", type=Path, default=Path("original_import_folders"), help="Directory to scan")
    parser.add_argument("--force", action="store_true", help="Force re-transcription even if cached")
    args = parser.parse_args()
    
    run(source_dir=args.source, force=args.force)


if __name__ == "__main__":
    main()
