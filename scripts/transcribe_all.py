#!/usr/bin/env python3
"""
Batch Audio Transcriber.

Scans a directory for audio files and transcribes them using the configured VLLM endpoint.
Results are automatically cached by the AudioTranscriber.

Usage:
    python scripts/transcribe_all.py --source /path/to/instagram_export
"""
import sys
import argparse
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.audio.audio import AudioTranscriber

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Batch Transcribe Audio Files.")
    parser.add_argument("--source", type=Path, default=Path("original_import_folders"), help="Directory to scan")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent requests")
    parser.add_argument("--force", action="store_true", help="Force re-transcription even if cached")
    args = parser.parse_args()

    if not default_config.enable_audio_transcription:
        print("⚠️  Audio transcription is DISABLED in config.")
        print("    Enable it with ENABLE_AUDIO_TRANSCRIPTION=true in .env")
        return

    source_dir = args.source
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return

    print(f"🔍 Scanning {source_dir} for audio files...")
    # Find all mp4/m4a/mp3/wav files
    audio_extensions = ['*.mp4', '*.m4a', '*.mp3', '*.wav']
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(list(source_dir.glob(f"**/{ext}")))

    print(f"Found {len(audio_files)} audio files.")
    
    transcriber = AudioTranscriber()
    
    # Filter out already cached if not force
    to_process = []
    if args.force:
        to_process = audio_files
    else:
        for f in audio_files:
            if transcriber.cache.get(f):
                continue
            to_process.append(f)
            
    print(f"📝 Transcribing {len(to_process)} files (skipping {len(audio_files) - len(to_process)} cached)...")
    
    if not to_process:
        print("✅ Nothing to do!")
        return

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_map = {executor.submit(transcriber.transcribe, f): f for f in to_process}
        
        # Progress bar
        with tqdm(total=len(to_process), unit="file") as pbar:
            for future in as_completed(future_map):
                f = future_map[future]
                try:
                    result = future.result()
                    if result:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    logger.error(f"Error processing {f}: {e}")
                    fail_count += 1
                pbar.update(1)

    # Save cache explicitly just in case (though transcriber saves on each hit)
    transcriber.cache.save()
    
    print("\n" + "="*40)
    print(f"🎉 Done!")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed:     {fail_count}")
    print(f"📦 Cache saved to: {transcriber.cache.cache_path}")
    print("="*40)

if __name__ == "__main__":
    main()
